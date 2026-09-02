import jwt
from datetime import datetime, timezone, timedelta
from src.config import settings
from src.core.exceptions import AuthenticationError, TokenExpiredError

ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.PCT_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "token_type": "access"})
    return jwt.encode(to_encode, settings.PCT_SECRET_KEY.get_secret_value(), algorithm=ALGORITHM)

def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a long-lived refresh token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=settings.PCT_REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "token_type": "refresh"})
    return jwt.encode(to_encode, settings.PCT_SECRET_KEY.get_secret_value(), algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """Decode a token and validate expiration"""
    try:
        payload = jwt.decode(token, settings.PCT_SECRET_KEY.get_secret_value(), algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")
