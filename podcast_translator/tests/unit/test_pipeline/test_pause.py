import pytest

from src.core.provider_errors import TaskPausedError
from src.pipeline import pause as pause_mod
from src.pipeline.context import TaskStage


class FakeRedis:
    def __init__(self, value=None):
        self.store = {"task:t1:pause-requested": value} if value else {}

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)


def test_raise_if_user_paused_raises_and_clears_flag(monkeypatch):
    fake = FakeRedis(value="1")
    monkeypatch.setattr(pause_mod, "get_redis_sync", lambda: fake)

    with pytest.raises(TaskPausedError) as exc:
        pause_mod.raise_if_user_paused("t1", TaskStage.SEPARATING)

    assert exc.value.reason_code == "user_paused"
    assert exc.value.stage == TaskStage.SEPARATING
    # flag cleared so a resumed run doesn't immediately re-pause
    assert "task:t1:pause-requested" not in fake.store


def test_raise_if_user_paused_noop_when_flag_absent(monkeypatch):
    monkeypatch.setattr(pause_mod, "get_redis_sync", lambda: FakeRedis())
    pause_mod.raise_if_user_paused("t1", TaskStage.SEPARATING)  # must not raise


def test_raise_if_user_paused_noop_without_redis(monkeypatch):
    monkeypatch.setattr(pause_mod, "get_redis_sync", lambda: None)
    pause_mod.raise_if_user_paused("t1")  # must not raise
