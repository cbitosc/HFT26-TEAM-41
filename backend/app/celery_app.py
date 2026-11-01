from celery import Celery

from app.config import get_settings

AUTO_SUBMIT_INTERVAL_S = 30.0

settings = get_settings()

celery_app = Celery("app", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    # Lets GET /jobs/{id} tell "queued" from "running".
    task_track_started=True,
    beat_schedule={
        "auto-submit-expired": {
            "task": "auto_submit_expired",
            "schedule": AUTO_SUBMIT_INTERVAL_S,
        },
    },
)
