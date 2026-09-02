"""
AuthService unit tests
"""
import uuid

import pytest

from src.config import settings
from src.core.exceptions import AuthenticationError, FeatureDisabledError, PCTException
from src.core.security import create_access_token, create_refresh_token
from src.schemas.auth import TokenResponse
from src.services import auth_service as auth_service_module
from src.services.auth_service import AuthService


class FakeAsyncRedis:
    """Minimal in-memory async Redis stand-in for SMS verification tests."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = str(value)

    async def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)

    async def incr(self, key):
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = str(value)
        return value

    async def expire(self, key, ttl):
        return True


def _use_real_sms(monkeypatch):
    """Switch to a real (aliyun) provider backed by a fake Redis + captured sender."""
    monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")
    monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", True)
    monkeypatch.setattr(settings, "PCT_SMS_PROVIDER", "aliyun")
    fake_redis = FakeAsyncRedis()
    monkeypatch.setattr(auth_service_module, "get_redis_async", lambda: fake_redis)

    sent_codes: list[tuple[str, str]] = []

    async def fake_send(phone, code):
        sent_codes.append((phone, code))
        return True

    monkeypatch.setattr(auth_service_module.sms_service, "send_verification_code", fake_send)
    return fake_redis, sent_codes


class TestRealSmsVerification:
    async def test_send_generates_and_stores_code(self, db_session, monkeypatch):
        fake_redis, sent_codes = _use_real_sms(monkeypatch)
        service = AuthService(db_session)

        assert await service.send_sms_code("13800138000") is True
        assert len(sent_codes) == 1
        phone, code = sent_codes[0]
        assert phone == "13800138000"
        assert len(code) == 6 and code.isdigit()
        # Code persisted in Redis; cooldown set.
        assert fake_redis.store["sms:code:13800138000"] == code
        assert fake_redis.store["sms:cooldown:13800138000"] == "1"

    async def test_send_respects_cooldown(self, db_session, monkeypatch):
        _use_real_sms(monkeypatch)
        service = AuthService(db_session)

        await service.send_sms_code("13800138000")
        with pytest.raises(PCTException, match="wait"):
            await service.send_sms_code("13800138000")

    async def test_login_with_correct_code_succeeds_and_clears(self, db_session, monkeypatch):
        fake_redis, sent_codes = _use_real_sms(monkeypatch)
        service = AuthService(db_session)

        await service.send_sms_code("13800001111")
        _, code = sent_codes[0]
        result = await service.login_with_sms("13800001111", code)

        assert isinstance(result, TokenResponse)
        # Single-use: code removed after successful login.
        assert "sms:code:13800001111" not in fake_redis.store

    async def test_login_with_wrong_code_fails(self, db_session, monkeypatch):
        _use_real_sms(monkeypatch)
        service = AuthService(db_session)

        await service.send_sms_code("13800138000")
        with pytest.raises(AuthenticationError, match="Invalid SMS"):
            await service.login_with_sms("13800138000", "000000")

    async def test_login_without_requesting_code_fails(self, db_session, monkeypatch):
        _use_real_sms(monkeypatch)
        service = AuthService(db_session)

        with pytest.raises(AuthenticationError, match="expired"):
            await service.login_with_sms("13800138000", "123456")

    async def test_send_blocked_when_phone_not_allowlisted(self, db_session, monkeypatch):
        _use_real_sms(monkeypatch)
        monkeypatch.setattr(settings, "PCT_SMS_PHONE_ALLOWLIST", "13800138000, 13900139000")
        service = AuthService(db_session)

        with pytest.raises(FeatureDisabledError, match="not allowed"):
            await service.send_sms_code("13700137000")

    async def test_send_allowed_when_phone_in_allowlist(self, db_session, monkeypatch):
        _, sent_codes = _use_real_sms(monkeypatch)
        monkeypatch.setattr(settings, "PCT_SMS_PHONE_ALLOWLIST", "13800138000")
        service = AuthService(db_session)

        assert await service.send_sms_code("13800138000") is True
        assert len(sent_codes) == 1

    async def test_login_locks_out_after_max_attempts(self, db_session, monkeypatch):
        fake_redis, sent_codes = _use_real_sms(monkeypatch)
        service = AuthService(db_session)

        await service.send_sms_code("13800138000")
        for _ in range(settings.PCT_SMS_MAX_VERIFY_ATTEMPTS):
            with pytest.raises(AuthenticationError, match="Invalid SMS"):
                await service.login_with_sms("13800138000", "000000")
        # Next attempt is locked out and the code is purged.
        with pytest.raises(AuthenticationError, match="Too many"):
            await service.login_with_sms("13800138000", "000000")
        assert "sms:code:13800138000" not in fake_redis.store


class TestSendSmsCode:
    async def test_send_sms_code_success(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", True)

        service = AuthService(db_session)
        result = await service.send_sms_code("13800138000")
        assert result is True

    async def test_send_sms_code_disabled_in_demo_mode(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "demo")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", False)

        service = AuthService(db_session)
        with pytest.raises(FeatureDisabledError, match="SMS login is disabled"):
            await service.send_sms_code("13800138000")


class TestLoginWithSms:
    async def test_login_new_user_auto_register(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", True)

        service = AuthService(db_session)
        result = await service.login_with_sms("13800001111", "123456")

        assert isinstance(result, TokenResponse)
        assert result.access_token
        assert result.refresh_token
        assert result.token_type == "bearer"

    async def test_login_existing_user(self, db_session, mock_user, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", True)

        service = AuthService(db_session)
        result = await service.login_with_sms(mock_user.phone, "123456")

        assert isinstance(result, TokenResponse)
        assert result.access_token

    async def test_login_wrong_code(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", True)

        service = AuthService(db_session)
        with pytest.raises(AuthenticationError, match="Invalid SMS"):
            await service.login_with_sms("13800138000", "000000")

    async def test_login_sms_disabled_in_demo_mode(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "demo")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", False)

        service = AuthService(db_session)
        with pytest.raises(FeatureDisabledError, match="SMS login is disabled"):
            await service.login_with_sms("13800138000", "123456")


class TestDemoLogin:
    async def test_demo_login_creates_demo_user(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "demo")
        monkeypatch.setattr(settings, "PCT_DEMO_USER_PHONE", "13800990000")
        monkeypatch.setattr(settings, "PCT_DEMO_USER_NICKNAME", "Portfolio Demo")

        service = AuthService(db_session)
        result = await service.login_demo()

        assert isinstance(result, TokenResponse)
        user = await service.user_repo.get_by_phone("13800990000")
        assert user is not None
        assert user.nickname == "Portfolio Demo"

    async def test_demo_login_disabled_outside_demo_mode(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")

        service = AuthService(db_session)
        with pytest.raises(FeatureDisabledError, match="Demo login is not enabled"):
            await service.login_demo()


class TestWechatLogin:
    async def test_wechat_login_disabled_by_default(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PCT_ENABLE_WECHAT_LOGIN", False)

        service = AuthService(db_session)
        with pytest.raises(FeatureDisabledError, match="WeChat login is not available"):
            await service.login_with_wechat("any-code")

    async def test_wechat_login_when_enabled(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PCT_ENABLE_WECHAT_LOGIN", True)

        async def fake_openid(code):
            return f"openid-{code}"

        monkeypatch.setattr(
            auth_service_module.wechat_oauth_service, "get_openid_by_code", fake_openid
        )

        service = AuthService(db_session)
        result = await service.login_with_wechat("any-code")
        assert isinstance(result, TokenResponse)


class TestRefreshToken:
    async def test_refresh_token_success(self, db_session, mock_user):
        service = AuthService(db_session)
        refresh = create_refresh_token({"sub": str(mock_user.id)})
        result = await service.refresh_token(refresh)

        assert isinstance(result, TokenResponse)
        assert result.access_token
        assert result.refresh_token

    async def test_refresh_with_access_token_fails(self, db_session, mock_user):
        service = AuthService(db_session)
        access = create_access_token({"sub": str(mock_user.id)})
        with pytest.raises(AuthenticationError):
            await service.refresh_token(access)

    async def test_refresh_invalid_token(self, db_session):
        service = AuthService(db_session)
        with pytest.raises(AuthenticationError):
            await service.refresh_token("invalid.token.here")

    async def test_refresh_nonexistent_user(self, db_session):
        service = AuthService(db_session)
        fake_id = str(uuid.uuid4())
        refresh = create_refresh_token({"sub": fake_id})
        with pytest.raises(AuthenticationError):
            await service.refresh_token(refresh)
