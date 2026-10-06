"""Dashboard API (FastAPI). Run from the project root:

    uvicorn apps.api.main:app --port 8000

then open http://127.0.0.1:8000. Binds to localhost by default; credentials in .env
are used server-side only and never returned to the browser.
"""

from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import os  # noqa: E402

from apps.api import runner, sources  # noqa: E402

app = FastAPI(title="Traceability dashboard")


def require_local_action(request: Request) -> None:
    """Guard for endpoints that start or stop work.

    Browsers let any web page POST to localhost, so require a custom header (which a
    cross-site page cannot send without a CORS preflight we don't allow) and, when the
    browser sends an Origin, that it matches this server. Set ``DASHBOARD_ALLOW_RUN=0``
    to disable starting runs entirely (e.g. when sharing the dashboard read-only).
    """
    if os.getenv("DASHBOARD_ALLOW_RUN", "1") == "0":
        raise HTTPException(403, "Starting runs is disabled on this dashboard")
    if request.headers.get("x-requested-with") != "dashboard":
        raise HTTPException(403, "Missing X-Requested-With header")
    origin = request.headers.get("origin")
    if origin and origin.split("://", 1)[-1] != request.headers.get("host"):
        raise HTTPException(403, "Cross-origin request refused")


def _current_run() -> tuple[Optional[Path], list[dict[str, Any]]]:
    run_dir = sources.latest_run_dir()
    return run_dir, (sources.read_events(run_dir) if run_dir else [])


@app.get("/api/status")
def status() -> dict[str, Any]:
    """Health of Neo4j and the LLM server, plus a summary of the latest run."""
    run_dir, events = _current_run()
    start = next((e for e in events if e["type"] == "run_start"), None)
    truth = sources.load_dataset(start["dataset"])["truth"] if start else set()
    return {
        "neo4j": sources.neo4j_status(),
        "llm": sources.llm_status(),
        "run": {"id": run_dir.name if run_dir else None, **sources.summarize_run(events, truth)},
    }


@app.get("/api/run")
def run(after: int = 0) -> dict[str, Any]:
    """Run summary plus the verdict/malformed events after index ``after`` (for the live feed)."""
    run_dir, events = _current_run()
    if run_dir is None:
        return {"id": None, "summary": {"state": "none"}, "feed": [], "next": 0}
    start = next((e for e in events if e["type"] == "run_start"), None)
    dataset = sources.load_dataset(start["dataset"]) if start else {"truth": set(), "artifacts": {}}
    feed = [
        {**e, "truth": (e["source_id"], e["target_id"]) in dataset["truth"]}
        for e in events[after:]
        if e["type"] in ("verdict", "malformed")
    ]
    return {"id": run_dir.name, "summary": sources.summarize_run(events, dataset["truth"]),
            "feed": feed, "next": len(events)}


@app.get("/api/graph")
def graph(source: str = "run") -> dict[str, Any]:
    """Graph for the dashboard: ``run`` (latest pipeline run) or ``neo4j`` (persisted USKG)."""
    if source == "neo4j":
        if not sources.neo4j_status()["connected"]:
            raise HTTPException(503, "Neo4j is not connected")
        return {"source": "neo4j", **sources.neo4j_graph()}
    run_dir, events = _current_run()
    start = next((e for e in events if e["type"] == "run_start"), None)
    if start is None:
        return {"source": "run", "nodes": [], "edges": []}
    dataset = sources.load_dataset(start["dataset"])
    return {"source": "run", **sources.build_run_graph(events, dataset["artifacts"], dataset["truth"])}


@app.get("/api/runs")
def runs() -> list[str]:
    """Names of all recorded runs, newest last."""
    if not sources.RUNS_DIR.exists():
        return []
    return sorted(d.name for d in sources.RUNS_DIR.iterdir() if (d / "events.jsonl").exists())


@app.get("/api/runner")
def runner_state() -> dict[str, Any]:
    """Whether a run is active, available datasets, defaults, and the recent console output."""
    return {
        **runner.status(),
        "datasets": runner.list_datasets(),
        "retrievals": list(runner.RETRIEVALS),
        "seconds_per_call": runner.SECONDS_PER_CALL,
        "allowed": os.getenv("DASHBOARD_ALLOW_RUN", "1") != "0",
        "log": runner.log_tail(),
    }


@app.post("/api/runner/estimate")
def runner_estimate(params: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Expected calls and minutes for the given parameters."""
    try:
        return runner.estimate(runner.validate(params))
    except runner.RunnerError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/runner/start", dependencies=[Depends(require_local_action)])
def runner_start(params: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Start a pipeline run (one at a time)."""
    try:
        return runner.start(params)
    except runner.RunnerError as exc:
        raise HTTPException(409 if "already" in str(exc) else 400, str(exc))


@app.post("/api/runner/stop", dependencies=[Depends(require_local_action)])
def runner_stop() -> dict[str, Any]:
    """Stop the run started from this dashboard."""
    try:
        return runner.stop()
    except runner.RunnerError as exc:
        raise HTTPException(409, str(exc))


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "web", html=True), name="web")
