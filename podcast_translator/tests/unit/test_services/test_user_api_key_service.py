import base64
import hashlib
import hmac
from unittest.mock import AsyncMock, patch

from src.config import settings
from src.core.credentials import decrypt_secret
from src.services.user_api_key_service import UserApiKeyService


def make_legacy_secret(value: str) -> str:
    secret = (
        settings.PCT_CREDENTIALS_ENCRYPTION_KEY.get_secret_value()
        if settings.PCT_CREDENTIALS_ENCRYPTION_KEY
        else settings.PCT_SECRET_KEY.get_secret_value()
    )
    plaintext = value.encode("utf-8")
    key = hashlib.sha256(secret.encode("utf-8")).digest()
    nonce = b"0" * 16
    stream = hmac.new(key, nonce + (0).to_bytes(4, "big"), hashlib.sha256).digest()[: len(plaintext)]
    ciphertext = bytes(left ^ right for left, right in zip(plaintext, stream))
    tag = hmac.new(key, b"pct-v1" + nonce + ciphertext, hashlib.sha256).digest()[:16]
    return "pct-v1." + base64.urlsafe_b64encode(nonce + ciphertext + tag).decode("ascii")


class TestUserApiKeyService:
    async def test_upsert_masks_and_encrypts_key(self, db_session, mock_user):
        service = UserApiKeyService(db_session)

        record = await service.upsert_api_key(
            mock_user.id,
            "dashscope",
            api_key="sk-test-secret",
            base_url="https://dashscope.aliyuncs.com/api/v1",
        )

        assert record.masked_key == "sk-t...cret"
        assert record.encrypted_api_key != "sk-test-secret"
        assert record.encrypted_api_key.startswith("pct-v2.")
        assert decrypt_secret(record.encrypted_api_key) == "sk-test-secret"

    def test_decrypts_legacy_v1_secret(self):
        legacy = make_legacy_secret("sk-legacy-secret")

        assert decrypt_secret(legacy) == "sk-legacy-secret"

    async def test_resolve_user_key_precedes_system_key(self, db_session, mock_user):
        service = UserApiKeyService(db_session)
        await service.upsert_api_key(mock_user.id, "openai", api_key="sk-user-key")

        credentials = await service.resolve_credentials(mock_user.id, "openai")

        assert credentials is not None
        assert credentials.api_key == "sk-user-key"
        assert credentials.source == "user"

    async def test_resolves_saved_huggingface_token(self, db_session, mock_user):
        service = UserApiKeyService(db_session)
        await service.upsert_api_key(mock_user.id, "huggingface", api_key="hf_user_token_1234")

        credentials = await service.resolve_credentials(mock_user.id, "huggingface")

        assert credentials is not None
        assert credentials.provider == "huggingface"
        assert credentials.api_key == "hf_user_token_1234"
        assert credentials.source == "user"

    async def test_verify_api_key_runs_provider_preflight(self, db_session, mock_user):
        service = UserApiKeyService(db_session)
        await service.upsert_api_key(mock_user.id, "openai", api_key="sk-user-key")

        with patch(
            "src.services.provider_preflight_service.ProviderPreflightService.verify_credentials",
            new=AsyncMock(),
        ) as verify:
            record = await service.verify_api_key(mock_user.id, "openai")

        assert record.verified_at is not None
        assert record.last_error is None
        verify.assert_awaited_once()
