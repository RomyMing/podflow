import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from src.config import settings

V1_PREFIX = "pct-v1."
V2_PREFIX = "pct-v2."


def _secret_material() -> bytes:
    credential_key = (
        settings.PCT_CREDENTIALS_ENCRYPTION_KEY.get_secret_value()
        if settings.PCT_CREDENTIALS_ENCRYPTION_KEY
        else ""
    )
    secret_key = settings.PCT_SECRET_KEY.get_secret_value()
    secret = credential_key or secret_key
    if not secret:
        raise ValueError("Credential encryption requires PCT_CREDENTIALS_ENCRYPTION_KEY or PCT_SECRET_KEY.")
    return secret.encode("utf-8")


def _derive_legacy_key() -> bytes:
    return hashlib.sha256(_secret_material()).digest()


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(_secret_material()).digest())
    return Fernet(key)


def _legacy_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    chunks: list[bytes] = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < length:
        chunks.append(hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return b"".join(chunks)[:length]


def encrypt_secret(value: str) -> str:
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{V2_PREFIX}{token}"


def decrypt_secret(token: str) -> str:
    if token.startswith(V2_PREFIX):
        payload = token.removeprefix(V2_PREFIX).encode("ascii")
        try:
            return _fernet().decrypt(payload).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise ValueError("Encrypted secret integrity check failed") from exc

    if token.startswith(V1_PREFIX):
        return _decrypt_legacy_secret(token)

    raise ValueError("Unsupported encrypted secret format")


def _decrypt_legacy_secret(token: str) -> str:
    if not token.startswith(V1_PREFIX):
        raise ValueError("Unsupported encrypted secret format")
    payload = base64.urlsafe_b64decode(token.removeprefix(V1_PREFIX).encode("ascii"))
    if len(payload) < 33:
        raise ValueError("Encrypted secret payload is invalid")

    nonce = payload[:16]
    tag = payload[-16:]
    ciphertext = payload[16:-16]
    key = _derive_legacy_key()
    expected_tag = hmac.new(key, b"pct-v1" + nonce + ciphertext, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Encrypted secret integrity check failed")

    stream = _legacy_keystream(key, nonce, len(ciphertext))
    plaintext = bytes(left ^ right for left, right in zip(ciphertext, stream))
    return plaintext.decode("utf-8")


def mask_secret(value: str) -> str:
    stripped = value.strip()
    if len(stripped) <= 8:
        return "****" + stripped[-2:]
    return f"{stripped[:4]}...{stripped[-4:]}"
