import json
import os
import time

import httpx
import streamlit as st

API = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Multi-Agent Research", layout="wide")
st.title("Multi-Agent Research & Automation")
st.caption("Goal → orchestrator → researcher / analyst / writer → structured output")

goal = st.text_area(
    "Goal",
    value="Research competitors in AI observability and outline a one-page market summary.",
    height=100,
)

if st.button("Run agents", type="primary"):
    with httpx.Client(timeout=120.0) as client:
        r = client.post(f"{API}/jobs", json={"goal": goal})
        r.raise_for_status()
        data = r.json()
        st.session_state["job_id"] = data["job_id"]
        st.success(f"Job started: `{data['job_id']}`")

job_id = st.session_state.get("job_id")
if job_id:
    st.subheader("Agent activity")
    log_box = st.empty()
    status = st.status("Running…", state="running")
    lines: list[str] = []
    done = False
    for _ in range(180):
        with httpx.Client(timeout=30.0) as client:
            ev = client.get(f"{API}/jobs/{job_id}/events").json().get("events", [])
        lines = []
        for obj in ev:
            lines.append(
                f"**{obj.get('agent', '?')}** — `{obj.get('step')}`: {obj.get('detail', '')}"
            )
            if obj.get("step") in ("done", "error"):
                done = True
        log_box.markdown("\n\n".join(lines[-25:]) if lines else "_Waiting for worker…_")
        if done:
            status.update(label="Finished", state="complete")
            break
        time.sleep(1)
    else:
        status.update(label="Timed out waiting", state="error")

    if st.button("Load result"):
        with httpx.Client(timeout=60.0) as client:
            rr = client.get(f"{API}/jobs/{job_id}/result")
            if rr.status_code == 404:
                st.info("Result not ready — run again in a few seconds.")
            else:
                rr.raise_for_status()
                out = rr.json()
                st.subheader("Markdown report")
                st.markdown(out.get("markdown", ""))
                st.subheader("JSON payload")
                st.json(out.get("json", {}))
                st.subheader("Citations")
                st.json(out.get("citations", []))

st.divider()
st.markdown(f"API: `{API}` · [Swagger]({API}/docs)")
