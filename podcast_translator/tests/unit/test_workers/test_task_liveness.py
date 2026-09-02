from unittest.mock import MagicMock, patch

from src.workers.task_liveness import (
    acquire_task_ownership,
    refresh_task_ownership,
    release_task_ownership,
)


def test_owner_can_acquire_and_refresh_atomically():
    redis = MagicMock()
    redis.set.return_value = True
    redis.eval.return_value = 1

    with patch("src.workers.task_liveness.get_redis_sync", return_value=redis):
        assert acquire_task_ownership("task-1", "0:celery-1", 300) is True
        assert refresh_task_ownership("task-1", "0:celery-1", 300, 900) is True

    redis.set.assert_called_once_with(
        "task:task-1:worker-lock",
        "0:celery-1",
        ex=300,
        nx=True,
    )


def test_wrong_owner_cannot_refresh_and_release_is_owner_conditional():
    redis = MagicMock()
    redis.eval.side_effect = [0, 1]

    with patch("src.workers.task_liveness.get_redis_sync", return_value=redis):
        assert refresh_task_ownership("task-1", "0:old", 300, 900) is False
        release_task_ownership("task-1", "0:old")

    assert redis.eval.call_count == 2
