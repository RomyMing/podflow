from unittest.mock import patch

from src.workers.celery_app import build_beat_schedule


def test_beat_schedule_merges_cleanup_and_stall_scanner():
    with patch("src.workers.celery_app.settings.PCT_ENABLE_STALL_RECONCILER", True):
        with patch("src.workers.celery_app.settings.PCT_VOICE_CLONE_CLEANUP_INTERVAL_HOURS", 24):
            schedule = build_beat_schedule()

    assert schedule["cleanup-expired-voices"]["task"] == "tasks.cleanup_expired_voices"
    assert schedule["reconcile-stalled-tasks"]["task"] == "tasks.reconcile_stalled_tasks"


def test_stall_scanner_is_disabled_during_first_rollout_phase():
    with patch("src.workers.celery_app.settings.PCT_ENABLE_STALL_RECONCILER", False):
        schedule = build_beat_schedule()

    assert "reconcile-stalled-tasks" not in schedule
