from celery import Celery

from src.config import settings

celery_app = Celery(
    "podcast_translator",
    broker=str(settings.PCT_REDIS_URL),
    backend=str(settings.PCT_REDIS_URL),
    include=["src.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=settings.PCT_PIPELINE_TASK_TIME_LIMIT_SECONDS,
    task_soft_time_limit=settings.PCT_PIPELINE_TASK_SOFT_TIME_LIMIT_SECONDS,
)

def build_beat_schedule() -> dict:
    schedule = {}
    if settings.PCT_VOICE_CLONE_CLEANUP_INTERVAL_HOURS > 0:
        schedule["cleanup-expired-voices"] = {
            "task": "tasks.cleanup_expired_voices",
            "schedule": settings.PCT_VOICE_CLONE_CLEANUP_INTERVAL_HOURS * 3600,
        }
    if settings.PCT_ENABLE_STALL_RECONCILER:
        schedule["reconcile-stalled-tasks"] = {
            "task": "tasks.reconcile_stalled_tasks",
            "schedule": max(15, settings.PCT_TASK_STALL_SCAN_INTERVAL_SECONDS),
        }
    return schedule


celery_app.conf.beat_schedule = build_beat_schedule()
