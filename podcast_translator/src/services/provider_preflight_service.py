import asyncio
import hashlib
import logging
import shutil
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass

import httpx

from src.config import settings
from src.core.provider_errors import (
    TaskPausedError,
    classify_provider_error,
    extract_provider_error_code,
)
from src.pipeline.context import TaskStage
from src.pipeline.utils import run_sync
from src.services.storage_service import StorageService
from src.services.user_api_key_service import ProviderCredentials, resolve_provider_credentials

logger = logging.getLogger(__name__)

PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "deepseek": "DeepSeek",
    "openai": "OpenAI",
    "dashscope": "DashScope（阿里云百炼）",
    "huggingface": "Hugging Face",
    "elevenlabs": "ElevenLabs",
}


def _provider_display_name(provider: str) -> str:
    return PROVIDER_DISPLAY_NAMES.get(provider, provider)


class ProviderProbeError(RuntimeError):
    """Provider 凭证校验失败（携带中文提示）。"""


def _raise_for_probe_status(provider: str, status_code: int, body: str) -> None:
    if 200 <= status_code < 300:
        return
    name = _provider_display_name(provider)
    if status_code in (401, 403):
        raise ProviderProbeError(
            f"{name} 的 API Key 无效或没有访问权限（HTTP {status_code}）。请确认密钥填写正确、未过期，并已开通对应服务。"
        )
    if status_code in (402, 429):
        raise ProviderProbeError(
            f"{name} 余额不足或调用频率受限（HTTP {status_code}）。请检查账户余额与调用配额后重试。"
        )
    snippet = " ".join((body or "").split())[:200]
    raise ProviderProbeError(f"{name} 接口返回异常（HTTP {status_code}）：{snippet}")


PREFLIGHT_STAGE_ORDER: tuple[TaskStage, ...] = (
    TaskStage.PREPARING,
    TaskStage.SEPARATING,
    TaskStage.DIARIZING,
    TaskStage.TRANSCRIBING,
    TaskStage.TRANSLATING,
    TaskStage.SYNTHESIZING,
    TaskStage.ALIGNING,
    TaskStage.MIXING,
)


@dataclass(frozen=True)
class ProviderPreflightResult:
    provider: str
    cache_hit: bool = False


class ProviderPreflightService:
    _cache: dict[str, float] = {}

    def __init__(self, storage_service: StorageService | None = None):
        self.storage_service = storage_service or StorageService()

    async def verify_credentials(self, credentials: ProviderCredentials) -> ProviderPreflightResult:
        cache_key = self._cache_key(credentials.provider, credentials.api_key, credentials.base_url, credentials.region)
        if self._cache_valid(cache_key):
            return ProviderPreflightResult(provider=credentials.provider, cache_hit=True)

        try:
            if credentials.provider in {"openai", "deepseek"}:
                await self._probe_openai_compatible(credentials)
            elif credentials.provider == "dashscope":
                await self._probe_dashscope_tts(credentials)
            elif credentials.provider == "huggingface":
                await self._probe_huggingface(credentials)
            elif credentials.provider == "elevenlabs":
                await self._probe_elevenlabs(credentials)
            else:
                raise ValueError(f"Unsupported provider preflight: {credentials.provider}")
        except TaskPausedError:
            raise
        except Exception as exc:
            raise self._as_paused_error(credentials.provider, exc, TaskStage.PREPARING) from exc

        self._remember(cache_key)
        return ProviderPreflightResult(provider=credentials.provider, cache_hit=False)

    def verify_credentials_sync(self, credentials: ProviderCredentials) -> ProviderPreflightResult:
        return run_sync(self.verify_credentials(credentials))

    def preflight_task_sync(
        self,
        *,
        user_id: uuid.UUID | None,
        config: dict | None,
        stage: TaskStage,
    ) -> list[ProviderPreflightResult]:
        return run_sync(self.preflight_task(user_id=user_id, config=config, stage=stage))

    async def preflight_task(
        self,
        *,
        user_id: uuid.UUID | None,
        config: dict | None,
        stage: TaskStage,
    ) -> list[ProviderPreflightResult]:
        config = config or {}
        results: list[ProviderPreflightResult] = []

        self._verify_local_runtime(stage)
        await self._verify_storage(stage)
        if self._stage_reaches(stage, TaskStage.DIARIZING):
            results.append(await self._verify_huggingface(user_id, stage))

        for provider in self._required_api_providers(config, stage):
            try:
                credentials = await resolve_provider_credentials(user_id, provider)
            except ValueError as exc:
                raise TaskPausedError(
                    str(exc),
                    provider=provider,
                    reason_code="provider_invalid_api_key",
                    provider_error_code="credential_decryption_failed",
                    stage=stage,
                ) from exc
            if credentials is None:
                raise TaskPausedError(
                    f"{provider} API key is not configured. Add it in Profile > API management.",
                    provider=provider,
                    reason_code="provider_credentials_missing",
                    stage=stage,
                )
            try:
                results.append(await self.verify_credentials(credentials))
            except TaskPausedError as exc:
                raise TaskPausedError(
                    str(exc),
                    provider=exc.provider,
                    reason_code=exc.reason_code,
                    provider_error_code=exc.provider_error_code,
                    stage=stage,
                ) from exc

        return results

    def _required_api_providers(self, config: dict, stage: TaskStage) -> list[str]:
        providers: list[str] = []
        translation_provider = str(config.get("translation_provider") or settings.PCT_TRANSLATION_PROVIDER)
        if self._should_preflight_provider(stage, TaskStage.TRANSLATING) and translation_provider in {"openai", "deepseek"}:
            providers.append(translation_provider)

        voice_clone_mode = str(config.get("voice_clone_mode") or "best_effort")
        voice_clone_provider = str(config.get("voice_clone_provider") or settings.PCT_VOICE_CLONE_PROVIDER)
        tts_provider = str(config.get("tts_provider") or settings.PCT_TTS_PROVIDER)
        if (
            self._should_preflight_provider(stage, TaskStage.SYNTHESIZING)
            and tts_provider == "cosyvoice"
            and (voice_clone_mode == "off" or voice_clone_provider not in ("elevenlabs", "voxcpm"))
        ):
            providers.append("dashscope")
        if (
            self._should_preflight_provider(stage, TaskStage.SYNTHESIZING)
            and voice_clone_mode != "off"
            and voice_clone_provider == "elevenlabs"
        ):
            providers.append("elevenlabs")

        return list(dict.fromkeys(providers))

    def _should_preflight_provider(self, stage: TaskStage, provider_stage: TaskStage) -> bool:
        if stage == TaskStage.PREPARING:
            return True
        return stage == provider_stage

    @staticmethod
    async def _httpx_get_with_retry(url: str, *, headers: dict, timeout: int) -> "httpx.Response":
        """httpx GET that retries transient transport failures (connect/read/network blips)
        before giving up. Status codes (401/403/quota) come back in the response and are
        evaluated by the caller, so they are never retried here."""
        attempts = max(1, int(settings.PCT_PREFLIGHT_RETRY_ATTEMPTS))
        backoff = max(0.0, float(settings.PCT_PREFLIGHT_RETRY_BACKOFF_SECONDS))
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    return await client.get(url, headers=headers)
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < attempts - 1:
                    logger.warning(
                        "Preflight GET %s failed (attempt %s/%s): %s; retrying",
                        url, attempt + 1, attempts, exc,
                    )
                    await asyncio.sleep(backoff * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    async def _probe_openai_compatible(self, credentials: ProviderCredentials) -> None:
        # 通过 OpenAI 兼容的 /models 端点校验密钥，无需依赖 openai SDK（后端容器不安装重依赖）。
        base_url = credentials.base_url
        if credentials.provider == "deepseek" and not base_url:
            base_url = settings.PCT_DEEPSEEK_BASE_URL
        base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        name = _provider_display_name(credentials.provider)
        timeout = max(1, settings.PCT_PROVIDER_PREFLIGHT_TIMEOUT_SECONDS)
        try:
            response = await self._httpx_get_with_retry(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {credentials.api_key}"},
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderProbeError(f"无法连接到 {name} 接口：{exc}") from exc
        _raise_for_probe_status(credentials.provider, response.status_code, response.text)

    async def _probe_dashscope_tts(self, credentials: ProviderCredentials) -> None:
        # 通过 DashScope 兼容模式的 /models 端点校验密钥，无需依赖 dashscope SDK。
        host = "https://dashscope.aliyuncs.com"
        if credentials.base_url and "dashscope-intl" in credentials.base_url:
            host = "https://dashscope-intl.aliyuncs.com"
        elif credentials.base_url and "dashscope-us" in credentials.base_url:
            host = "https://dashscope-us.aliyuncs.com"
        url = f"{host}/compatible-mode/v1/models"
        name = _provider_display_name("dashscope")
        timeout = max(1, settings.PCT_PROVIDER_PREFLIGHT_TIMEOUT_SECONDS)
        try:
            response = await self._httpx_get_with_retry(
                url,
                headers={"Authorization": f"Bearer {credentials.api_key}"},
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderProbeError(f"无法连接到 {name} 接口：{exc}") from exc
        _raise_for_probe_status("dashscope", response.status_code, response.text)

    async def _verify_huggingface(self, user_id: uuid.UUID | None, stage: TaskStage) -> ProviderPreflightResult:
        try:
            credentials = await resolve_provider_credentials(user_id, "huggingface")
        except ValueError as exc:
            raise TaskPausedError(
                str(exc),
                provider="huggingface",
                reason_code="provider_invalid_api_key",
                provider_error_code="credential_decryption_failed",
                stage=stage,
            ) from exc
        if credentials is None:
            raise TaskPausedError(
                "Hugging Face token is not configured. Pyannote speaker diarization needs authorization.",
                provider="huggingface",
                reason_code="provider_credentials_missing",
                stage=stage,
            )
        try:
            return await self.verify_credentials(credentials)
        except TaskPausedError as exc:
            raise TaskPausedError(
                str(exc),
                provider=exc.provider,
                reason_code=exc.reason_code,
                provider_error_code=exc.provider_error_code,
                stage=stage,
            ) from exc

    @staticmethod
    def _urlopen_with_retry(request: "urllib.request.Request", *, timeout: int):
        """urlopen that retries transient network/TLS failures (URLError, SSL EOF, resets)
        with linear backoff, but re-raises HTTPError immediately since 401/403/quota are
        definitive answers, not blips."""
        attempts = max(1, int(settings.PCT_PREFLIGHT_RETRY_ATTEMPTS))
        backoff = max(0.0, float(settings.PCT_PREFLIGHT_RETRY_BACKOFF_SECONDS))
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return urllib.request.urlopen(request, timeout=timeout)
            except urllib.error.HTTPError:
                raise
            except Exception as exc:  # URLError / ssl / socket / etc.
                last_exc = exc
                if attempt < attempts - 1:
                    logger.warning(
                        "Preflight request to %s failed (attempt %s/%s): %s; retrying",
                        getattr(request, "full_url", "?"), attempt + 1, attempts, exc,
                    )
                    time.sleep(backoff * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    async def _probe_huggingface(self, credentials: ProviderCredentials) -> None:
        await asyncio.to_thread(self._probe_huggingface_sync, credentials)

    async def _probe_elevenlabs(self, credentials: ProviderCredentials) -> None:
        await asyncio.to_thread(self._probe_elevenlabs_sync, credentials)

    def _probe_elevenlabs_sync(self, credentials: ProviderCredentials) -> None:
        base_url = (credentials.base_url or settings.PCT_ELEVENLABS_BASE_URL).rstrip("/")
        request = urllib.request.Request(
            f"{base_url}/v1/user/subscription",
            headers={"xi-api-key": credentials.api_key},
        )
        try:
            with self._urlopen_with_retry(
                request,
                timeout=max(1, settings.PCT_PROVIDER_PREFLIGHT_TIMEOUT_SECONDS),
            ) as response:
                if response.status >= 400:
                    raise RuntimeError(f"ElevenLabs preflight failed with HTTP {response.status}")
        except urllib.error.HTTPError as exc:
            code = "InvalidApiKey" if exc.code in {401, 403} else f"HTTP{exc.code}"
            raise TaskPausedError(
                f"ElevenLabs preflight failed: {exc}",
                provider="elevenlabs",
                reason_code="provider_invalid_api_key" if exc.code in {401, 403} else "provider_unavailable",
                provider_error_code=code,
            ) from exc
        except Exception as exc:
            raise TaskPausedError(
                f"ElevenLabs preflight failed: {exc}",
                provider="elevenlabs",
                reason_code="provider_unavailable",
                provider_error_code=extract_provider_error_code(exc),
            ) from exc

    def _probe_huggingface_sync(self, credentials: ProviderCredentials) -> None:
        request = urllib.request.Request(
            "https://huggingface.co/api/models/pyannote/speaker-diarization-3.1",
            headers={"Authorization": f"Bearer {credentials.api_key}"},
        )
        try:
            with self._urlopen_with_retry(
                request,
                timeout=max(1, settings.PCT_PROVIDER_PREFLIGHT_TIMEOUT_SECONDS),
            ) as response:
                if response.status >= 400:
                    raise RuntimeError(f"Hugging Face preflight failed with HTTP {response.status}")
        except urllib.error.HTTPError as exc:
            code = "InvalidApiKey" if exc.code in {401, 403} else f"HTTP{exc.code}"
            raise TaskPausedError(
                f"Hugging Face preflight failed: {exc}",
                provider="huggingface",
                reason_code="provider_invalid_api_key" if exc.code in {401, 403} else "provider_unavailable",
                provider_error_code=code,
            ) from exc
        except Exception as exc:
            raise TaskPausedError(
                f"Hugging Face preflight failed: {exc}",
                provider="huggingface",
                reason_code="provider_unavailable",
                provider_error_code=extract_provider_error_code(exc),
            ) from exc

    async def _verify_storage(self, stage: TaskStage) -> None:
        if await self.storage_service.check_connection():
            return
        raise TaskPausedError(
            "Object storage is unavailable.",
            provider="storage",
            reason_code="provider_unavailable",
            provider_error_code="storage_unavailable",
            stage=stage,
        )

    def _verify_local_runtime(self, stage: TaskStage) -> None:
        required = ["ffmpeg", "ffprobe"]
        if self._stage_reaches(stage, TaskStage.SEPARATING):
            required.append("demucs")
        missing = [binary for binary in required if shutil.which(binary) is None]
        if not missing:
            return
        raise TaskPausedError(
            f"Pipeline runtime dependency is missing: {', '.join(missing)}",
            provider="local_runtime",
            reason_code="provider_unavailable",
            provider_error_code=f"missing_{missing[0]}",
            stage=stage,
        )

    def _stage_reaches(self, start_stage: TaskStage, target_stage: TaskStage) -> bool:
        try:
            return PREFLIGHT_STAGE_ORDER.index(start_stage) <= PREFLIGHT_STAGE_ORDER.index(target_stage)
        except ValueError:
            return True

    def _as_paused_error(self, provider: str, exc: Exception, stage: TaskStage) -> TaskPausedError:
        name = _provider_display_name(provider)
        info = classify_provider_error(exc, provider)
        if info is not None:
            return TaskPausedError(
                f"{name} 校验失败：{exc}",
                provider=info.provider,
                reason_code=info.reason_code,
                provider_error_code=info.provider_error_code,
                stage=stage,
            )
        return TaskPausedError(
            f"{name} 校验失败：{exc}",
            provider=provider,
            reason_code="provider_unavailable",
            provider_error_code=extract_provider_error_code(exc),
            stage=stage,
        )

    def _cache_valid(self, key: str) -> bool:
        expires_at = self._cache.get(key)
        if expires_at is None:
            return False
        if expires_at <= time.monotonic():
            self._cache.pop(key, None)
            return False
        return True

    def _remember(self, key: str) -> None:
        ttl = max(0, settings.PCT_PROVIDER_PREFLIGHT_CACHE_SECONDS)
        if ttl <= 0:
            return
        self._cache[key] = time.monotonic() + ttl

    def _cache_key(self, provider: str, api_key: str, base_url: str | None, region: str | None) -> str:
        raw = "\0".join([provider, api_key, base_url or "", region or ""])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
