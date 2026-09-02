import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.exceptions import AuthenticationError, FeatureDisabledError, PCTException, TokenExpiredError
from src.core.redis import get_redis_async
from src.core.security import create_access_token, create_refresh_token, decode_token
from src.core.sms import sms_service
from src.core.wechat import wechat_oauth_service
from src.models.user import User
from src.repositories.user_repo import UserRepository
from src.schemas.auth import TokenResponse


def _sms_code_key(phone: str) -> str:
    return f"sms:code:{phone}"


def _sms_cooldown_key(phone: str) -> str:
    return f"sms:cooldown:{phone}"


def _sms_attempts_key(phone: str) -> str:
    return f"sms:attempts:{phone}"


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(User, db)

    @staticmethod
    def _is_mock_sms() -> bool:
        return settings.PCT_SMS_PROVIDER == "mock"

    @staticmethod
    def _ensure_phone_allowed(phone: str) -> None:
        """Gate real SMS login by an optional phone allowlist (empty = allow all)."""
        raw = settings.PCT_SMS_PHONE_ALLOWLIST or ""
        allowlist = {p.strip() for p in raw.split(",") if p.strip()}
        if allowlist and phone not in allowlist:
            raise FeatureDisabledError("This phone number is not allowed to log in.")

    async def send_sms_code(self, phone: str) -> bool:
        if not settings.PCT_ENABLE_SMS_LOGIN or settings.PCT_AUTH_MODE != "sms":
            raise FeatureDisabledError("SMS login is disabled in this environment")

        # Mock environments keep a fixed, well-known code and skip Redis entirely.
        if self._is_mock_sms():
            return await sms_service.send_verification_code(phone, settings.PCT_MOCK_SMS_CODE)

        self._ensure_phone_allowed(phone)
        redis = get_redis_async()
        if redis is None:
            raise PCTException("SMS service is temporarily unavailable. Please try again later.")

        if await redis.get(_sms_cooldown_key(phone)):
            raise PCTException("Please wait before requesting another verification code.")

        code = f"{secrets.randbelow(1_000_000):06d}"
        await redis.set(_sms_code_key(phone), code, ex=settings.PCT_SMS_CODE_TTL_SECONDS)
        await redis.set(_sms_cooldown_key(phone), "1", ex=settings.PCT_SMS_CODE_COOLDOWN_SECONDS)
        await redis.delete(_sms_attempts_key(phone))

        try:
            sent = await sms_service.send_verification_code(phone, code)
        except Exception:
            await redis.delete(_sms_code_key(phone))
            raise
        if not sent:
            await redis.delete(_sms_code_key(phone))
            raise PCTException("Failed to send SMS verification code.")
        return True

    async def login_with_sms(self, phone: str, code: str) -> TokenResponse:
        """Login with SMS code. If user doesn't exist, register them."""
        if not settings.PCT_ENABLE_SMS_LOGIN or settings.PCT_AUTH_MODE != "sms":
            raise FeatureDisabledError("SMS login is disabled in this environment")

        if self._is_mock_sms():
            if code != settings.PCT_MOCK_SMS_CODE:
                raise AuthenticationError("Invalid SMS verification code")
        else:
            self._ensure_phone_allowed(phone)
            await self._verify_sms_code(phone, code)

        user = await self._get_or_create_phone_user(phone)
        return self._generate_tokens(user)

    async def _verify_sms_code(self, phone: str, code: str) -> None:
        redis = get_redis_async()
        if redis is None:
            raise AuthenticationError("Verification code expired. Please request a new one.")

        stored = await redis.get(_sms_code_key(phone))
        if stored is None:
            raise AuthenticationError("Verification code expired. Please request a new one.")

        attempts = await redis.incr(_sms_attempts_key(phone))
        if attempts == 1:
            await redis.expire(_sms_attempts_key(phone), settings.PCT_SMS_CODE_TTL_SECONDS)
        if attempts > settings.PCT_SMS_MAX_VERIFY_ATTEMPTS:
            await redis.delete(_sms_code_key(phone), _sms_attempts_key(phone))
            raise AuthenticationError("Too many incorrect attempts. Please request a new code.")

        if not secrets.compare_digest(stored, code):
            raise AuthenticationError("Invalid SMS verification code")

        await redis.delete(_sms_code_key(phone), _sms_attempts_key(phone))

    async def login_demo(self) -> TokenResponse:
        """Issue tokens for the shared demo account."""
        if settings.PCT_AUTH_MODE != "demo":
            raise FeatureDisabledError("Demo login is not enabled in this environment")

        user = await self.user_repo.get_by_phone(settings.PCT_DEMO_USER_PHONE)
        if not user:
            user = await self.user_repo.create(
                User(
                    phone=settings.PCT_DEMO_USER_PHONE,
                    nickname=settings.PCT_DEMO_USER_NICKNAME,
                    monthly_quota=settings.PCT_DEFAULT_MONTHLY_QUOTA,
                )
            )
        else:
            await self.user_repo.update(
                user,
                {
                    "nickname": settings.PCT_DEMO_USER_NICKNAME,
                    "monthly_quota": settings.PCT_DEFAULT_MONTHLY_QUOTA,
                    "monthly_used": 0,
                },
            )

        await self.db.commit()
        await self.db.refresh(user)

        return self._generate_tokens(user)

    async def login_with_wechat(self, code: str) -> TokenResponse:
        """Login with WeChat OAuth. If user doesn't exist, register them."""
        # WeChat OAuth is still a mock placeholder — gated off until real OAuth lands so
        # mock openids can never mint accounts in production.
        if not settings.PCT_ENABLE_WECHAT_LOGIN:
            raise FeatureDisabledError("WeChat login is not available in this environment")

        openid = await wechat_oauth_service.get_openid_by_code(code)

        user = await self.user_repo.get_by_wechat_openid(openid)
        if not user:
            user = await self.user_repo.create(User(wechat_openid=openid))
            await self.db.commit()
            await self.db.refresh(user)

        return self._generate_tokens(user)

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh token pair using a valid refresh token."""
        try:
            payload = decode_token(refresh_token)
            if payload.get("token_type") != "refresh":
                raise AuthenticationError("Invalid token type")

            user_id_str = payload.get("sub")
            if not user_id_str:
                raise AuthenticationError("Invalid token payload")

            user_id = uuid.UUID(user_id_str)
            user = await self.user_repo.get(user_id)
            if not user:
                raise AuthenticationError("User not found")

            return self._generate_tokens(user)
        except Exception as exc:
            if isinstance(exc, (TokenExpiredError, AuthenticationError)):
                raise
            raise AuthenticationError("Could not refresh token")

    async def _get_or_create_phone_user(self, phone: str) -> User:
        user = await self.user_repo.get_by_phone(phone)
        if not user:
            user = await self.user_repo.create(User(phone=phone))
            await self.db.commit()
            await self.db.refresh(user)
        return user

    def _generate_tokens(self, user: User) -> TokenResponse:
        data = {"sub": str(user.id)}
        access_token = create_access_token(data)
        refresh_token = create_refresh_token(data)

        decoded = decode_token(access_token)
        from datetime import datetime, timezone

        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            exp=exp,
        )
