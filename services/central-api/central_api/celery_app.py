"""Celery application for the DEV-55 submission-only Redis task queue."""

import os

from celery import Celery
from kombu import Queue

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0").strip()

celery_app = Celery(
    "trackflow",
    broker=redis_url,
    backend=redis_url,
    include=["central_api.domains.tasks.celery_tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=86_400,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 1_200},
    task_soft_time_limit=840,
    task_time_limit=900,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_queues=(Queue("rfp"), Queue("dev55"), Queue("dead_letter")),
    task_routes={
        "trackflow.rfp.process": {"queue": "rfp"},
        "trackflow.dev55.failure": {"queue": "dev55"},
        "trackflow.dead_letter.record": {"queue": "dead_letter"},
    },
)
