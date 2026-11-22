from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "policyrag",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.indexing_tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    beat_schedule={
        "recover-stale-index-tasks": {
            "task": "policyrag.recover_stale_tasks",
            "schedule": 15.0,
        }
    },
)
