from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import time
from collections.abc import Callable
from typing import Any

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config import settings
from app.metrics import agent_steps, tool_failures
from app.rag.memory import ingest_text, retrieve_context


EmitFn = Callable[[dict[str, Any]], None]


def _emit(emit: EmitFn | None, payload: dict[str, Any]) -> None:
    if emit:
        emit(payload)


def _web_search(query: str) -> str:
    if settings.serpapi_api_key:
        try:
            r = httpx.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": settings.serpapi_api_key, "engine": "google"},
                timeout=30.0,
            )
            r.raise_for_status()
            data = r.json()
            bits = []
            for o in data.get("organic_results", [])[:5]:
                bits.append(f"- {o.get('title')}: {o.get('snippet', '')}")
            return "\n".join(bits) if bits else str(data)[:2000]
        except Exception:
            tool_failures.labels(tool="serpapi").inc()
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            rows = list(ddgs.text(query, max_results=5))
        return "\n".join(f"- {x.get('title')}: {x.get('body', '')}" for x in rows)
    except Exception:
        tool_failures.labels(tool="duckduckgo").inc()
        return f"(search unavailable) query: {query}"


def _sql_demo(query: str) -> str:
    try:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE sales (region TEXT, amount REAL)")
        conn.executemany(
            "INSERT INTO sales VALUES (?, ?)",
            [("NA", 100), ("EU", 80), ("APAC", 120)],
        )
        conn.commit()
        cur = conn.execute(query)
        rows = cur.fetchall()
        conn.close()
        os.unlink(path)
        return json.dumps(rows)
    except Exception as e:
        tool_failures.labels(tool="sql").inc()
        return f"SQL error: {e}"


def _safe_python(expr: str) -> str:
    if not re.match(r"^[0-9+\-*/().\s]+$", expr):
        return "Only numeric expressions allowed."
    try:
        return str(eval(expr, {"__builtins__": {}}, {}))
    except Exception as e:
        tool_failures.labels(tool="python_repl").inc()
        return str(e)


# Keeps sleep/lifestyle/education goals from being framed as "market reports" unless the user asked for business analysis.
_TONE_GUIDANCE = (
    "Tone: Match the user's goal. Use executive or market-style language only when the goal is "
    "clearly about markets, competitors, industry, investing, revenue, or corporate strategy. "
    "For health, sleep, wellness, lifestyle, education, how-to, or general life topics, write "
    "clear practical guidance with sensible ## headings—do not title or frame the answer as a "
    "'market report' or business memo. For technical or factual questions, explain directly. "
    "The sql_demo field is synthetic demo data for tooling illustration only—never treat it as "
    "real market, sales, or medical evidence unless the user explicitly asks about that demo data."
)


def _live_llm_configured() -> bool:
    if settings.demo_mode:
        return False
    p = (settings.llm_provider or "openai").lower()
    if p == "gemini":
        return bool(settings.google_api_key)
    return bool(settings.openai_api_key)


def _chat_llm():
    p = (settings.llm_provider or "openai").lower()
    if p == "gemini":
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key or "")
        return ChatGoogleGenerativeAI(model=settings.gemini_model, temperature=0.2)
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key or "")
    return ChatOpenAI(model=settings.openai_model, temperature=0.2)


def run_pipeline(goal: str, session_id: str, emit: EmitFn | None = None) -> dict[str, Any]:
    t0 = time.perf_counter()
    citations: list[dict[str, str]] = []

    if not _live_llm_configured():
        _emit(emit, {"agent": "Orchestrator", "step": "plan", "detail": "Decomposed goal into research, analysis, writing"})
        agent_steps.labels(agent="orchestrator").inc()
        time.sleep(0.2)
        _emit(emit, {"agent": "Researcher", "step": "search", "detail": "DuckDuckGo / SerpAPI (demo)"})
        agent_steps.labels(agent="researcher").inc()
        _emit(emit, {"agent": "Analyst", "step": "synthesize", "detail": "Merged findings (demo)"})
        agent_steps.labels(agent="analyst").inc()
        _emit(emit, {"agent": "Writer", "step": "draft", "detail": "Structured report (demo)"})
        agent_steps.labels(agent="writer").inc()
        body = f"## Demo report\n\nGoal: **{goal}**\n\nThis run used **DEMO_MODE** (no OpenAI key). Enable `OPENAI_API_KEY` for live agents."
        result = {
            "goal": goal,
            "markdown": body,
            "json": {"summary": "Demo mode output", "goal": goal},
            "citations": [{"source": "demo", "note": "No live retrieval"}],
        }
        return result

    llm = _chat_llm()

    _emit(emit, {"agent": "Orchestrator", "step": "plan", "detail": "Planning subtasks"})
    agent_steps.labels(agent="orchestrator").inc()

    rag_ctx = ""
    if not settings.simple_mode:
        ingest_text(session_id, goal, "goal")
        rag_ctx = retrieve_context(session_id, goal)
    else:
        _emit(
            emit,
            {
                "agent": "Orchestrator",
                "step": "simple_mode",
                "detail": "Skipping RAG/embeddings (SIMPLE_MODE) — one LLM call only",
            },
        )

    _emit(emit, {"agent": "Researcher", "step": "search", "detail": f"Query: {goal[:120]}..."})
    agent_steps.labels(agent="researcher").inc()
    search_hits = _web_search(goal[:200])
    citations.append({"source": "web_search", "excerpt": search_hits[:500]})

    _emit(emit, {"agent": "Researcher", "step": "sql_sample", "detail": "Running demo aggregation on SQLite"})
    agent_steps.labels(agent="researcher").inc()
    sql_out = _sql_demo("SELECT region, SUM(amount) FROM sales GROUP BY region")

    _emit(emit, {"agent": "Analyst", "step": "compute", "detail": "Numeric check"})
    agent_steps.labels(agent="analyst").inc()
    calc = _safe_python("100 * 0.12")

    if settings.simple_mode:
        _emit(
            emit,
            {"agent": "Writer", "step": "report", "detail": "Single pass (simple mode): report + JSON"},
        )
        agent_steps.labels(agent="writer").inc()
        simple_msgs = [
            SystemMessage(
                content=(
                    "You are a research assistant. Using the goal, optional RAG notes, web snippets, "
                    "SQL demo output, and numeric check, write a helpful Markdown report with ## sections. "
                    + _TONE_GUIDANCE
                    + " End with a JSON code block ONLY containing keys: summary (string), "
                    "recommendations (array of strings), risks (array of strings). "
                    "Use risks for caveats or limitations (e.g. individual variation), not only financial risk."
                )
            ),
            HumanMessage(
                content=json.dumps(
                    {
                        "goal": goal,
                        "rag": rag_ctx[:2000],
                        "web": search_hits[:4000],
                        "sql_demo": sql_out,
                        "calc": calc,
                    }
                )
            ),
        ]
        report = llm.invoke(simple_msgs).content
    else:
        analyst_msgs = [
            SystemMessage(
                content=(
                    "You are a senior analyst. Given user goal, RAG context, web snippets, "
                    "and SQL aggregate output, produce 5 bullet findings with explicit uncertainty. "
                    + _TONE_GUIDANCE
                )
            ),
            HumanMessage(
                content=json.dumps(
                    {
                        "goal": goal,
                        "rag": rag_ctx[:2000],
                        "web": search_hits[:4000],
                        "sql_demo": sql_out,
                        "calc": calc,
                    }
                )
            ),
        ]
        analysis = llm.invoke(analyst_msgs).content

        _emit(emit, {"agent": "Writer", "step": "report", "detail": "Generating structured deliverable"})
        agent_steps.labels(agent="writer").inc()
        writer_msgs = [
            SystemMessage(
                content=(
                    "Write a concise Markdown deliverable with ## sections. "
                    + _TONE_GUIDANCE
                    + " End with a JSON code block ONLY containing keys: summary (string), "
                    "recommendations (array of strings), risks (array of strings). "
                    "Use risks for caveats relevant to the topic (health variance, uncertainty, tradeoffs)."
                )
            ),
            HumanMessage(content=f"Goal:\n{goal}\n\nAnalysis:\n{analysis}"),
        ]
        report = llm.invoke(writer_msgs).content

    json_part = {}
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", report)
    if m:
        try:
            json_part = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            json_part = {"summary": report[:500], "parse_error": True}

    result = {
        "goal": goal,
        "markdown": report,
        "json": json_part or {"summary": report[:800]},
        "citations": citations,
        "elapsed_sec": round(time.perf_counter() - t0, 3),
    }
    return result
