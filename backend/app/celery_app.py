import json
import os

from celery import Celery
from celery.signals import worker_ready

from app.config import settings

redis_url = os.environ.get("REDIS_URL", settings.redis_url)


def _channel(job_id: str) -> str:
    return f"job:{job_id}:events"


def publish_event(job_id: str, payload: dict) -> None:
    from redis import Redis

    r = Redis.from_url(redis_url, decode_responses=True)
    line = json.dumps(payload)
    r.publish(_channel(job_id), line)
    r.lpush(f"job:{job_id}:log", line)
    r.ltrim(f"job:{job_id}:log", 0, 199)


celery_app = Celery("agents", broker=redis_url, backend=redis_url)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
# Load tasks after celery_app and publish_event exist (avoids circular import).
celery_app.conf.imports = ("app.tasks",)


@worker_ready.connect
def _start_metrics_http(**_kwargs):
    """Expose Prometheus metrics from the worker process (where job counters are updated)."""
    import app.tasks  # noqa: F401 — ensure metrics registry is populated

    try:
        from prometheus_client import start_http_server

        start_http_server(9100)
    except OSError:
        pass
