"""Cooperative user-initiated pause for the running pipeline.

The API sets a Redis flag (see ``get_task_pause_request_key``); the pipeline calls
``raise_if_user_paused`` at stage and chunk boundaries. When the flag is set it clears it and
raises ``TaskPausedError`` with reason ``user_paused`` — which the worker already handles by
marking the task ``paused`` (quota preserved, resumable from the current stage)."""

import logging

from src.core.provider_errors import TaskPausedError
from src.core.redis import get_redis_sync, get_task_pause_request_key
from src.pipeline.context import TaskStage

logger = logging.getLogger(__name__)

USER_PAUSE_REASON_CODE = "user_paused"


def raise_if_user_paused(task_id: str, stage: TaskStage | None = None) -> None:
    client = get_redis_sync()
    if client is None:
        return
    key = get_task_pause_request_key(task_id)
    try:
        requested = client.get(key)
    except Exception:
        logger.warning("Failed to read pause flag for task %s", task_id, exc_info=True)
        return
    if not requested:
        return
    try:
        client.delete(key)
    except Exception:
        logger.warning("Failed to clear pause flag for task %s", task_id, exc_info=True)
    logger.info("Task %s: user-requested pause taking effect at stage %s.", task_id, getattr(stage, "value", stage))
    raise TaskPausedError(
        "任务已被手动暂停，可从当前阶段继续或删除。",
        provider="user",
        reason_code=USER_PAUSE_REASON_CODE,
        stage=stage,
    )
