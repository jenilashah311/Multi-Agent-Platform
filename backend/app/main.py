import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from redis import Redis
from sse_starlette.sse import EventSourceResponse

from app.celery_app import celery_app, redis_url
from app.config import settings
from app.metrics import metrics_response
from app.tasks import run_goal_task


def get_redis() -> Redis:
    return Redis.from_url(os.environ.get("REDIS_URL", redis_url), decode_responses=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Multi-Agent Research Platform", lifespan=lifespan)


class GoalRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=4000)
    session_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "demo_mode": settings.demo_mode}


@app.get("/metrics")
def metrics():
    body, headers = metrics_response()
    return Response(content=body, media_type=headers["Content-Type"])


@app.post("/jobs")
def start_job(req: GoalRequest):
    job_id = str(uuid.uuid4())
    session_id = req.session_id or str(uuid.uuid4())
    run_goal_task.delay(job_id, req.goal, session_id)
    return {"job_id": job_id, "session_id": session_id}


@app.get("/jobs/{job_id}/events")
def job_events(job_id: str):
    r = get_redis()
    items = r.lrange(f"job:{job_id}:log", 0, -1)
    return {"events": [json.loads(x) for x in reversed(items)] if items else []}


@app.get("/jobs/{job_id}/result")
def job_result(job_id: str):
    r = get_redis()
    raw = r.get(f"job:{job_id}:result")
    if not raw:
        raise HTTPException(status_code=404, detail="Result not ready or unknown job")
    return JSONResponse(json.loads(raw))


@app.get("/jobs/{job_id}/stream")
async def job_stream(job_id: str):
    r = get_redis()
    pubsub = r.pubsub()
    channel = f"job:{job_id}:events"
    pubsub.subscribe(channel)

    async def gen():
        try:
            while True:
                msg = await asyncio.to_thread(pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message" and msg.get("data"):
                    yield {"event": "agent", "data": msg["data"]}
                    data = json.loads(msg["data"])
                    if data.get("step") in ("done", "error"):
                        break
                await asyncio.sleep(0.05)
        finally:
            try:
                pubsub.unsubscribe(channel)
                pubsub.close()
            except Exception:
                pass

    return EventSourceResponse(gen())


@app.get("/")
def root():
    return {"service": "multi-agent-platform", "docs": "/docs"}
