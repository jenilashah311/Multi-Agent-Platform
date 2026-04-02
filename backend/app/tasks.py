import json
import time

from redis import Redis

from app.celery_app import celery_app, redis_url, publish_event
from app.metrics import job_duration, jobs_completed
from app.orchestration.agents import run_pipeline


def _result_key(job_id: str) -> str:
    return f"job:{job_id}:result"


@celery_app.task(name="agents.run_goal")
def run_goal_task(job_id: str, goal: str, session_id: str) -> dict:
    t0 = time.perf_counter()

    def emit(p):
        publish_event(job_id, p)

    try:
        out = run_pipeline(goal, session_id, emit=emit)
        publish_event(job_id, {"agent": "System", "step": "done", "detail": "Complete"})
        r = Redis.from_url(redis_url, decode_responses=True)
        r.set(_result_key(job_id), json.dumps(out), ex=86400)
        jobs_completed.labels(status="success").inc()
        return out
    except Exception as e:
        publish_event(job_id, {"agent": "System", "step": "error", "detail": str(e)})
        jobs_completed.labels(status="error").inc()
        raise
    finally:
        job_duration.observe(time.perf_counter() - t0)
