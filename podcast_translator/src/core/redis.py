import json
import logging
from datetime import datetime
from typing import Any

import redis
import redis.asyncio as redis_async

from src.config import settings

logger = logging.getLogger(__name__)

_sync_client: redis.Redis | None = None
_async_client: redis_async.Redis | None = None


def get_redis_sync() -> redis.Redis | None:
    global _sync_client
    if _sync_client is not None:
        return _sync_client

    try:
        _sync_client = redis.from_url(str(settings.PCT_REDIS_URL), decode_responses=True)
        _sync_client.ping()
        return _sync_client
    except Exception as exc:
        logger.warning("Redis sync client unavailable: %s", exc)
        _sync_client = None
        return None


def get_redis_async() -> redis_async.Redis | None:
    global _async_client
    if _async_client is not None:
        return _async_client

    try:
        _async_client = redis_async.from_url(str(settings.PCT_REDIS_URL), decode_responses=True)
        return _async_client
    except Exception as exc:
        logger.warning("Redis async client unavailable: %s", exc)
        _async_client = None
        return None


def get_task_progress_channel(task_id: str) -> str:
    return f"task:{task_id}:progress"


def get_task_pause_request_key(task_id: str) -> str:
    """Cooperative-pause flag: the API sets it; the running pipeline checks it at stage and
    chunk boundaries and pauses itself gracefully (keeping checkpoints for later resume)."""
    return f"task:{task_id}:pause-requested"


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def build_task_progress_payload(
    *,
    task_id: str,
    stage: str | None,
    progress_percent: int,
    status: str,
    error_message: str | None = None,
    pause_reason_code: str | None = None,
    provider_error_code: str | None = None,
    output_audio_url: str | None = None,
    audio_duration: float | None = None,
    processed_seconds: float | None = None,
    total_seconds: float | None = None,
    chunk_index: int | None = None,
    chunk_count: int | None = None,
    stage_progress_percent: int | None = None,
    eta_seconds: float | None = None,
    finished_at: datetime | str | None = None,
    event: str | None = None,
) -> dict[str, Any]:
    payload = {
        "task_id": task_id,
        "stage": stage,
        "progress_percent": progress_percent,
        "status": status,
        "error_message": error_message,
        "pause_reason_code": pause_reason_code,
        "provider_error_code": provider_error_code,
        "output_audio_url": output_audio_url,
        "audio_duration": audio_duration,
        "processed_seconds": processed_seconds,
        "total_seconds": total_seconds,
        "chunk_index": chunk_index,
        "chunk_count": chunk_count,
        "stage_progress_percent": stage_progress_percent,
        "eta_seconds": eta_seconds,
        "finished_at": _normalize_value(finished_at),
    }
    if event:
        payload["event"] = event
    return payload


def publish_task_progress_message(**payload: Any) -> None:
    client = get_redis_sync()
    if client is None:
        return

    task_id = payload["task_id"]
    try:
        client.publish(get_task_progress_channel(task_id), json.dumps(payload))
    except Exception as exc:
        logger.warning("Failed to publish task progress for %s: %s", task_id, exc)
