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

from apps.api import demo, runner, sources  # noqa: E402

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
        "redis": sources.redis_status(),
        "run": {"id": run_dir.name if run_dir else None, **_summary(events, truth)},
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
        {**e, "truth": ((e["source_id"], e["target_id"]) in dataset["truth"]) if dataset["truth"] else None}
        for e in events[after:]
        if e["type"] in ("verdict", "malformed")
    ]
    return {"id": run_dir.name, "summary": _summary(events, dataset["truth"]),
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


@app.get("/api/completeness")
def completeness(project: Optional[str] = None) -> dict[str, Any]:
    """Traceability completeness and orphan requirements (needs Neo4j)."""
    if not sources.neo4j_status()["connected"]:
        raise HTTPException(503, "Neo4j is not connected")
    return sources.neo4j_completeness(project=project or None)


@app.get("/api/runs")
def runs() -> list[str]:
    """Names of all recorded runs, newest last."""
    if not sources.RUNS_DIR.exists():
        return []
    return sorted(d.name for d in sources.RUNS_DIR.iterdir() if (d / "events.jsonl").exists())


def _idle() -> bool:
    """No pipeline process is running, so a run without a run_end event was interrupted."""
    return runner.status()["state"] == "idle"


def _summary(events: list[dict[str, Any]], truth: Any) -> dict[str, Any]:
    summary = sources.summarize_run(events, truth)
    if summary["state"] not in ("finished", "none") and _idle():
        summary["state"] = "interrupted"
    return summary


def _events(kind: str) -> list[dict[str, Any]]:
    run_dir = sources.latest_run_dir(kind=kind)
    return sources.read_events(run_dir) if run_dir else []


@app.get("/api/pipeline")
def pipeline() -> dict[str, Any]:
    """The pipeline stages, each with a state and a one-line detail, from the latest run and monitor pass."""
    return {"stages": sources.pipeline_stages(_events("pipeline"), _events("monitor"), sources.neo4j_status(), interrupted=_idle())}


@app.get("/api/projects")
def projects() -> list[dict[str, Any]]:
    """Projects (repositories) in the USKG with their node and link counts."""
    if not sources.neo4j_status()["connected"]:
        return []
    return sources.neo4j_projects()


@app.get("/api/uskg")
def uskg(source: str = "neo4j", dataset: str = "cm1", project: Optional[str] = None) -> dict[str, Any]:
    """The USKG graph: ``neo4j`` (live) or ``files`` (offline preview from a processed dataset)."""
    if source == "files":
        return sources.file_graph(dataset)
    if not sources.neo4j_status()["connected"]:
        raise HTTPException(503, "Neo4j is not connected")
    return {**sources.neo4j_uskg_graph(project=project or None), "counts": sources.neo4j_status().get("counts", {})}


@app.get("/api/uskg/requirement/{requirement_id}")
def uskg_requirement(requirement_id: str) -> dict[str, Any]:
    """One requirement with its linked code, justifications, completeness score and decay history."""
    if not sources.neo4j_status()["connected"]:
        raise HTTPException(503, "Neo4j is not connected")
    detail = sources.neo4j_requirement_detail(requirement_id)
    if not detail:
        raise HTTPException(404, "Unknown requirement")
    return detail


@app.get("/api/decay")
def decay(project: Optional[str] = None) -> dict[str, Any]:
    """Decayed links, DecayFlag history, and the event stream of the latest decay-monitor pass."""
    events = _events("monitor")
    out: dict[str, Any] = {
        "neo4j": sources.neo4j_status()["connected"],
        "events": [e for e in events if e["type"] in ("recheck", "decay_event", "run_start", "run_end")][-80:],
        "decayed": [], "flags": [],
    }
    if out["neo4j"]:
        out.update(sources.neo4j_decay(project=project or None))
    return out


@app.get("/api/results")
def results() -> dict[str, Any]:
    """Measured evaluation results (static file) plus a decay-injection report if one was saved."""
    return sources.load_results()


@app.get("/api/runs/summary")
def runs_summary() -> list[dict[str, Any]]:
    """One summary row per recorded run (pipeline runs with metrics, monitor passes with counts)."""
    return sources.runs_summary(idle=_idle())


def _demo_guard() -> None:
    state = demo.allowed()
    if not state["allowed"]:
        raise HTTPException(403, state["reason"])


@app.get("/api/demo")
def demo_state(project: Optional[str] = None) -> dict[str, Any]:
    """Whether demo controls are available, loadable datasets, edit types and linked code entities."""
    state = demo.allowed()
    out: dict[str, Any] = {**state, "datasets": demo.datasets(), "mutations": list(demo.mutation_functions()), "code_entities": []}
    if state["allowed"] and sources.neo4j_status()["connected"]:
        out["code_entities"] = demo.linked_code_entities(project=project or None)
    return out


@app.post("/api/demo/load", dependencies=[Depends(require_local_action)])
def demo_load(params: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Load a processed dataset into Neo4j as demo Requirement / CodeEntity nodes."""
    _demo_guard()
    try:
        result = demo.load(str(params.get("dataset", "")))
    except demo.DemoError as exc:
        raise HTTPException(400, str(exc))
    sources._neo_cache.update(at=0.0, value=None)
    return result


@app.post("/api/demo/modify", dependencies=[Depends(require_local_action)])
def demo_modify(params: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Edit a demo code entity's text, as C2 would after a commit (original kept for reset)."""
    _demo_guard()
    try:
        return demo.modify(str(params.get("code_id", "")), str(params.get("mutation", "")))
    except demo.DemoError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/requirements/link", dependencies=[Depends(require_local_action)])
def link_new_requirement(params: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Add a new requirement (stands in for C1) and start linking just that requirement to code."""
    _demo_guard()
    if not sources.neo4j_status()["connected"]:
        raise HTTPException(503, "Neo4j is not connected")
    if runner.status()["state"] != "idle":
        raise HTTPException(409, "A run is already in progress; wait for it to finish.")
    try:
        top_k = int(params.get("top_k", 3))
        project = str(params.get("project") or "") or None
        added = demo.add_requirement(str(params.get("text", "")), str(params.get("id", "")), project)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    sources._neo_cache.update(at=0.0, value=None)
    try:
        started = runner.start({"kind": "link", "requirement_ids": [added["id"]], "top_k": top_k, "retrieval": "hybrid", "project": project})
    except runner.RunnerError as exc:
        raise HTTPException(409 if "already" in str(exc) else 400, str(exc))
    return {**added, **started}


@app.post("/api/demo/commit", dependencies=[Depends(require_local_action)])
def demo_commit(params: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Stand in for C2: edit a code file as a commit would, then tell C4 which file changed.

    C4 re-checks only the links that depend on that file (the ``changed`` command).
    """
    _demo_guard()
    if runner.status()["state"] != "idle":
        raise HTTPException(409, "A run is already in progress; wait for it to finish.")
    project = str(params.get("project") or "") or None
    code_id = str(params.get("code_id", ""))
    try:
        edit = demo.modify(code_id, str(params.get("mutation", "")))
        started = runner.start({"kind": "changed", "project": project, "code_changed": [code_id]})
    except demo.DemoError as exc:
        raise HTTPException(400, str(exc))
    except runner.RunnerError as exc:
        raise HTTPException(409 if "already" in str(exc) else 400, str(exc))
    sources._neo_cache.update(at=0.0, value=None)
    return {**edit, **started}


@app.post("/api/demo/undo", dependencies=[Depends(require_local_action)])
def demo_undo(params: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Undo demo code edits and un-decay the links that decayed because of them."""
    _demo_guard()
    try:
        return demo.undo_changes(str(params.get("project") or "") or None)
    except demo.DemoError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/demo/reset", dependencies=[Depends(require_local_action)])
def demo_reset(params: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Delete C4's results (VERIFIED_TRACE, DecayFlag) and undo demo code edits (one project, or all)."""
    _demo_guard()
    try:
        result = demo.reset(str(params.get("project") or "") or None)
    except demo.DemoError as exc:
        raise HTTPException(400, str(exc))
    sources._neo_cache.update(at=0.0, value=None)
    return result


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


# Register C3 routes before the static fallback.
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from apps.api.routes import integration, quality

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(quality.router)
app.include_router(integration.router)

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "component": "quality-testing-intelligence", "component_id": "C3"}

@app.get("/", include_in_schema=False)
@app.get("/traceability", include_in_schema=False)
def traceability_dashboard():
    return FileResponse(Path(__file__).resolve().parents[1] / "web" / "traceability.html")

app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "web", html=True), name="web")
