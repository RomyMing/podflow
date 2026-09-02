import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.credentials import decrypt_secret, encrypt_secret, mask_secret
from src.core.database import AsyncSessionLocal
from src.models.user_api_key import UserApiKey
from src.pipeline.utils import run_sync

ApiKeyProvider = Literal["dashscope", "openai", "deepseek", "huggingface", "elevenlabs"]
SUPPORTED_PROVIDERS: set[str] = {"dashscope", "openai", "deepseek", "huggingface", "elevenlabs"}


@dataclass(frozen=True)
class ProviderCredentials:
    provider: str
    api_key: str
    base_url: str | None = None
    region: str | None = None
    source: Literal["user", "system"] = "system"


class UserApiKeyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_api_keys(self, user_id: uuid.UUID) -> list[UserApiKey]:
        result = await self.db.execute(
            select(UserApiKey).where(UserApiKey.user_id == user_id).order_by(UserApiKey.provider)
        )
        return list(result.scalars().all())

    async def get_api_key(self, user_id: uuid.UUID, provider: str) -> UserApiKey | None:
        self._validate_provider(provider)
        result = await self.db.execute(
            select(UserApiKey).where(
                UserApiKey.user_id == user_id,
                UserApiKey.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_api_key(
        self,
        user_id: uuid.UUID,
        provider: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        region: str | None = None,
        enabled: bool = True,
    ) -> UserApiKey:
        self._validate_provider(provider)
        existing = await self.get_api_key(user_id, provider)
        if existing is None and not api_key:
            raise ValueError("API key is required when creating provider credentials.")

        updates = {
            "base_url": base_url.strip() if base_url else None,
            "region": region.strip() if region else None,
            "enabled": enabled,
            "last_error": None,
        }
        if api_key:
            clean_key = api_key.strip()
            updates.update(
                {
                    "encrypted_api_key": encrypt_secret(clean_key),
                    "masked_key": mask_secret(clean_key),
                    "verified_at": None,
                }
            )

        if existing is None:
            existing = UserApiKey(
                user_id=user_id,
                provider=provider,
                encrypted_api_key=str(updates.pop("encrypted_api_key")),
                masked_key=str(updates.pop("masked_key")),
                **updates,
            )
            self.db.add(existing)
        else:
            for field, value in updates.items():
                setattr(existing, field, value)

        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def delete_api_key(self, user_id: uuid.UUID, provider: str) -> None:
        existing = await self.get_api_key(user_id, provider)
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()

    async def verify_api_key(self, user_id: uuid.UUID, provider: str) -> UserApiKey:
        existing = await self.get_api_key(user_id, provider)
        if existing is None:
            raise ValueError("尚未配置该 Provider 的 API Key，请先保存后再验证。")

        try:
            credentials = self._credentials_from_record(existing)
            self._validate_credentials_shape(credentials)
            from src.services.provider_preflight_service import ProviderPreflightService

            await ProviderPreflightService().verify_credentials(credentials)
        except Exception as exc:
            existing.last_error = str(exc)
            existing.verified_at = None
            await self.db.commit()
            await self.db.refresh(existing)
            raise ValueError(str(exc)) from exc

        existing.verified_at = datetime.now(timezone.utc)
        existing.last_error = None
        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def resolve_credentials(self, user_id: uuid.UUID | None, provider: str) -> ProviderCredentials | None:
        self._validate_provider(provider)
        if user_id is not None:
            existing = await self.get_api_key(user_id, provider)
            if existing is not None and existing.enabled:
                return self._credentials_from_record(existing)
        return resolve_system_credentials(provider)

    def _credentials_from_record(self, record: UserApiKey) -> ProviderCredentials:
        try:
            api_key = decrypt_secret(record.encrypted_api_key)
        except ValueError as exc:
            raise ValueError(
                f"已保存的 {record.provider} API Key 无法解密，"
                "请在「个人中心 → API 管理」重新填写并验证该密钥。"
            ) from exc
        return ProviderCredentials(
            provider=record.provider,
            api_key=api_key,
            base_url=record.base_url,
            region=record.region,
            source="user",
        )

    def _validate_credentials_shape(self, credentials: ProviderCredentials) -> None:
        if not credentials.api_key.strip():
            raise ValueError("API Key 不能为空。")
        if credentials.provider in {"dashscope", "openai", "deepseek"} and not credentials.api_key.startswith("sk-"):
            raise ValueError("该 Provider 的 API Key 应以 sk- 开头，请检查是否复制完整。")
        if credentials.provider == "huggingface" and not credentials.api_key.startswith("hf_"):
            raise ValueError("Hugging Face 令牌应以 hf_ 开头，请检查是否复制完整。")
        if credentials.base_url:
            parsed = urlparse(credentials.base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("接口地址必须是合法的 http(s) URL。")

    def _validate_provider(self, provider: str) -> None:
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported API key provider: {provider}")


def resolve_system_credentials(provider: str) -> ProviderCredentials | None:
    if provider == "dashscope" and settings.PCT_DASHSCOPE_API_KEY:
        return ProviderCredentials(
            provider="dashscope",
            api_key=settings.PCT_DASHSCOPE_API_KEY.get_secret_value(),
            base_url=settings.PCT_DASHSCOPE_BASE_HTTP_URL,
            region=None,
            source="system",
        )
    if provider == "openai" and settings.PCT_OPENAI_API_KEY:
        return ProviderCredentials(
            provider="openai",
            api_key=settings.PCT_OPENAI_API_KEY.get_secret_value(),
            base_url=settings.PCT_OPENAI_BASE_URL,
            region=None,
            source="system",
        )
    if provider == "deepseek" and settings.PCT_DEEPSEEK_API_KEY:
        return ProviderCredentials(
            provider="deepseek",
            api_key=settings.PCT_DEEPSEEK_API_KEY.get_secret_value(),
            base_url=settings.PCT_DEEPSEEK_BASE_URL,
            region=None,
            source="system",
        )
    if provider == "huggingface" and settings.PCT_HF_TOKEN:
        return ProviderCredentials(
            provider="huggingface",
            api_key=settings.PCT_HF_TOKEN.get_secret_value(),
            base_url=None,
            region=None,
            source="system",
        )
    if provider == "elevenlabs" and settings.PCT_ELEVENLABS_API_KEY:
        return ProviderCredentials(
            provider="elevenlabs",
            api_key=settings.PCT_ELEVENLABS_API_KEY.get_secret_value(),
            base_url=settings.PCT_ELEVENLABS_BASE_URL,
            region=None,
            source="system",
        )
    return None


async def resolve_provider_credentials(
    user_id: uuid.UUID | None,
    provider: str,
) -> ProviderCredentials | None:
    async with AsyncSessionLocal() as session:
        return await UserApiKeyService(session).resolve_credentials(user_id, provider)


def resolve_provider_credentials_sync(
    user_id: uuid.UUID | None,
    provider: str,
) -> ProviderCredentials | None:
    return run_sync(resolve_provider_credentials(user_id, provider))
