import json
import logging
import time

from src.core.redis import get_redis_sync

logger = logging.getLogger(__name__)


def task_lock_key(task_id: str) -> str:
    return f"task:{task_id}:worker-lock"


def task_heartbeat_key(task_id: str) -> str:
    return f"task:{task_id}:heartbeat"


def task_dispatch_guard_key(task_id: str) -> str:
    return f"task:{task_id}:dispatch-guard"


def build_owner_token(run_generation: int, celery_task_id: str) -> str:
    return f"{run_generation}:{celery_task_id}"


_REFRESH_LUA = """
if redis.call('get', KEYS[1]) ~= ARGV[1] then
  return 0
end
redis.call('expire', KEYS[1], tonumber(ARGV[2]))
redis.call('set', KEYS[2], ARGV[4], 'EX', tonumber(ARGV[3]))
return 1
"""

_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  redis.call('del', KEYS[1])
end
local heartbeat = redis.call('get', KEYS[2])
if heartbeat then
  local ok, payload = pcall(cjson.decode, heartbeat)
  if ok and payload['owner'] == ARGV[1] then
    redis.call('del', KEYS[2])
  end
end
return 1
"""


def acquire_task_ownership(task_id: str, owner: str, ttl_seconds: int) -> bool:
    client = get_redis_sync()
    if client is None:
        return True
    return bool(client.set(task_lock_key(task_id), owner, ex=ttl_seconds, nx=True))


def refresh_task_ownership(
    task_id: str,
    owner: str,
    lock_ttl: int,
    heartbeat_ttl: int,
) -> bool | None:
    """Return True when renewed, False when ownership is lost, and None on Redis errors."""
    client = get_redis_sync()
    if client is None:
        return None
    payload = json.dumps(
        {"owner": owner, "timestamp": time.time()},
        separators=(",", ":"),
    )
    try:
        return bool(
            client.eval(
                _REFRESH_LUA,
                2,
                task_lock_key(task_id),
                task_heartbeat_key(task_id),
                owner,
                lock_ttl,
                heartbeat_ttl,
                payload,
            )
        )
    except Exception:
        logger.warning("Failed to refresh ownership for task %s", task_id, exc_info=True)
        return None


def owns_task(task_id: str, owner: str) -> bool | None:
    client = get_redis_sync()
    if client is None:
        return None
    try:
        return client.get(task_lock_key(task_id)) == owner
    except Exception:
        logger.warning("Failed to verify ownership for task %s", task_id, exc_info=True)
        return None


def release_task_ownership(task_id: str, owner: str) -> None:
    client = get_redis_sync()
    if client is None:
        return
    try:
        client.eval(
            _RELEASE_LUA,
            2,
            task_lock_key(task_id),
            task_heartbeat_key(task_id),
            owner,
        )
    except Exception:
        logger.warning("Failed to release ownership for task %s", task_id, exc_info=True)

