import re
from dataclasses import dataclass

from src.pipeline.context import TaskStage


@dataclass(frozen=True)
class ProviderErrorInfo:
    provider: str
    reason_code: str
    provider_error_code: str | None = None


class TaskPausedError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        reason_code: str,
        provider_error_code: str | None = None,
        stage: TaskStage | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.reason_code = reason_code
        self.provider_error_code = provider_error_code
        self.stage = stage


PAUSABLE_PROVIDER_ERROR_CODES: dict[str, str] = {
    "Arrearage": "provider_billing_required",
    "PrepaidBillOverdue": "provider_billing_required",
    "PostpaidBillOverdue": "provider_billing_required",
    "AllocationQuota.FreeTierOnly": "provider_quota_exhausted",
    "Throttling.AllocationQuota": "provider_quota_exhausted",
    "insufficient_quota": "provider_quota_exhausted",
    "InvalidApiKey": "provider_invalid_api_key",
    "invalid_api_key": "provider_invalid_api_key",
    "NOT AUTHORIZED": "provider_invalid_api_key",
    "AccessDenied.Unpurchased": "provider_billing_required",
    "CommodityNotPurchased": "provider_billing_required",
}

PAUSABLE_MESSAGE_MARKERS: tuple[tuple[str, str], ...] = (
    ("arrearage", "provider_billing_required"),
    ("bill is overdue", "provider_billing_required"),
    ("postpaidbilloverdue", "provider_billing_required"),
    ("prepaidbilloverdue", "provider_billing_required"),
    ("insufficient balance", "provider_billing_required"),
    ("free tier", "provider_quota_exhausted"),
    ("quota exceeded", "provider_quota_exhausted"),
    ("insufficient_quota", "provider_quota_exhausted"),
    ("allocated quota", "provider_quota_exhausted"),
    ("invalid api", "provider_invalid_api_key"),
    ("invalidapi", "provider_invalid_api_key"),
    ("api key", "provider_invalid_api_key"),
    ("invalid xi-api-key", "provider_invalid_api_key"),
    ("unauthenticated", "provider_invalid_api_key"),
    ("unauthorized", "provider_invalid_api_key"),
    ("not authorized", "provider_invalid_api_key"),
    ("too many requests", "provider_quota_exhausted"),
    ("rate limit", "provider_quota_exhausted"),
    # Transient connectivity / availability failures. Pausing (resumable) is strictly
    # safer than a hard fail that refunds quota and restarts the whole pipeline: the
    # user/network recovers and the task resumes from where it stopped.
    ("could not establish", "provider_unavailable"),
    ("could not established", "provider_unavailable"),
    ("connection could not", "provider_unavailable"),
    ("websocket", "provider_unavailable"),
    ("timed out", "provider_unavailable"),
    ("timeout", "provider_unavailable"),
    ("connection refused", "provider_unavailable"),
    ("connection reset", "provider_unavailable"),
    ("connection aborted", "provider_unavailable"),
    ("connection error", "provider_unavailable"),
    ("failed to establish", "provider_unavailable"),
    ("max retries exceeded", "provider_unavailable"),
    ("network is unreachable", "provider_unavailable"),
    ("temporarily unavailable", "provider_unavailable"),
    ("service unavailable", "provider_unavailable"),
    ("bad gateway", "provider_unavailable"),
    ("gateway timeout", "provider_unavailable"),
    ("unexpected_eof", "provider_unavailable"),
    ("eof occurred", "provider_unavailable"),
    ("name or service not known", "provider_unavailable"),
    ("nodename nor servname", "provider_unavailable"),
    ("remote end closed", "provider_unavailable"),
)


def extract_provider_error_code(exc: Exception | str) -> str | None:
    explicit_code = getattr(exc, "error_code", None)
    if explicit_code:
        return str(explicit_code)

    message = str(exc)
    for code in PAUSABLE_PROVIDER_ERROR_CODES:
        if code and code in message:
            return code

    code_match = re.search(r"\b([A-Za-z]+(?:\.[A-Za-z]+)+|[A-Za-z_]*Quota[A-Za-z_.]*|InvalidApiKey|Arrearage)\b", message)
    return code_match.group(1) if code_match else None


def classify_provider_error(exc: Exception | str, provider: str) -> ProviderErrorInfo | None:
    code = extract_provider_error_code(exc)
    if code in PAUSABLE_PROVIDER_ERROR_CODES:
        return ProviderErrorInfo(
            provider=provider,
            reason_code=PAUSABLE_PROVIDER_ERROR_CODES[code],
            provider_error_code=code,
        )

    message = str(exc).lower()
    for marker, reason_code in PAUSABLE_MESSAGE_MARKERS:
        if marker in message:
            return ProviderErrorInfo(
                provider=provider,
                reason_code=reason_code,
                provider_error_code=code,
            )

    return None


def pause_for_provider_error(
    exc: Exception,
    *,
    provider: str,
    stage: TaskStage,
    prefix: str,
    include_transient: bool = True,
) -> TaskPausedError | None:
    """Return a TaskPausedError if ``exc`` is a pausable provider problem, else None.

    Set ``include_transient=False`` inside retry loops so transient connectivity errors
    (``provider_unavailable``) keep retrying; the caller should pause for them only after
    retries are exhausted (i.e. call again with the default ``include_transient=True``).
    """
    info = classify_provider_error(exc, provider)
    if info is None:
        return None
    if not include_transient and info.reason_code == "provider_unavailable":
        return None
    return TaskPausedError(
        f"{prefix}: {exc}",
        provider=info.provider,
        reason_code=info.reason_code,
        provider_error_code=info.provider_error_code,
        stage=stage,
    )
