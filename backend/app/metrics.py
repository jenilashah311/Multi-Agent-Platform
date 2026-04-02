from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

jobs_completed = Counter(
    "agent_jobs_completed_total",
    "Completed agent orchestration jobs",
    ["status"],
)
job_duration = Histogram(
    "agent_job_duration_seconds",
    "Wall time for full job",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)
agent_steps = Counter(
    "agent_steps_total",
    "Steps emitted per logical agent role",
    ["agent"],
)
tool_failures = Counter(
    "agent_tool_failures_total",
    "Tool invocation failures",
    ["tool"],
)


def metrics_response():
    return generate_latest(), {"Content-Type": CONTENT_TYPE_LATEST}
