"""Local web server for the C4 demo: serves the legacy single-page demo (apps/web_legacy/index.html) and the JSON API.

The new React dashboard (apps/web, Vite) does not need this page: in development its dev server proxies /api to this server.

Standard library only (no web framework). Run from the project root:

    .venv/bin/python -m apps.api.server            # then open http://127.0.0.1:8000

It listens on this machine only. Requests that change data (POST) must carry the header
``X-Requested-With: c4-web`` and, when the browser sends an Origin, come from this server's own
page, so another web site cannot trigger them.
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

from apps.api import demo, history, runner, sources  # noqa: E402

WEB_DIR = PROJECT_ROOT / "apps" / "web_legacy"   # the old demo page; the React app lives in apps/web
HOST = "127.0.0.1"
MAX_BODY = 20_000
_cache: dict[str, tuple[float, Any]] = {}


class ApiError(Exception):
    """An error with an HTTP status and a message for the user."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _cached(key: str, ttl: float, fn: Callable[[], Any]) -> Any:
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    value = fn()
    _cache[key] = (time.time(), value)
    return value


def _forget() -> None:
    """Drop cached graph data after a write, so the next read is fresh."""
    for key in [k for k in _cache if not k.startswith("llm")]:
        _cache.pop(key, None)
    sources._neo_cache.update(at=0.0, value=None)


def _busy() -> bool:
    return runner.status()["state"] != "idle"


def _need_neo4j() -> None:
    if not sources.neo4j_status()["connected"]:
        raise ApiError(503, "The knowledge graph (Neo4j) is not reachable. Start Neo4j Desktop.")


def _need_idle() -> None:
    if _busy():
        raise ApiError(409, "Something is already running. Wait for it to finish.")


def _project(value: Any) -> Optional[str]:
    return str(value) if value else None


# ------------------------------------------------------------------ GET handlers
def get_health(_: dict) -> dict:
    neo = sources.neo4j_status()
    llm = _cached("llm", 15, sources.llm_status)
    return {"neo4j": {"connected": neo["connected"], "counts": neo.get("counts", {})},
            "llm": {"reachable": bool(llm.get("reachable")), "model": llm.get("model")},
            "redis": sources.redis_status(), "demo": demo.allowed()}


def get_projects(_: dict) -> list:
    if not sources.neo4j_status()["connected"]:
        return []
    return _cached("projects", 5, sources.neo4j_projects)


def get_activity(_: dict) -> dict:
    state = runner.status()
    out: dict[str, Any] = {"state": state["state"]}
    if state["state"] == "idle":
        return out
    link = next((r for r in history.link_runs(busy=True) if r["state"] == "running"), None)
    change = next((r for r in history.change_runs(busy=True) if r["state"] == "running"), None)
    if link:
        out.update(kind="link", project=link["project"], requirements=link["requirements"][:5],
                   done=link["done"], total=link["total"], started=link["started"])
    elif change:
        out.update(kind="change", trigger=change["trigger"], project=change["project"], files=change["files"],
                   checked=len(change["rechecks"]), started=change["started"])
    return out


def get_unlinked(q: dict) -> dict:
    """How many requirements of the project have no trace link yet (what "Create trace links" would work on)."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    return sources.neo4j_unlinked(project)


def _texts(ids: list[str]) -> dict[str, str]:
    if not ids or not sources.neo4j_status()["connected"]:
        return {}
    with sources._neo4j_driver() as driver:
        records, _, _ = driver.execute_query(
            "MATCH (r:Requirement) WHERE r.id IN $ids RETURN r.id AS id, coalesce(r.text,'') AS text", ids=ids)
    return {r["id"]: r["text"] for r in records}


def get_link_runs(q: dict) -> dict:
    runs = [r for r in history.link_runs(_project(q.get("project")), busy=_busy()) if r["candidates"] or r["state"] == "running"]
    runs = runs[:60]
    ids = sorted({rid for r in runs for rid in r["requirements"][:20]})
    return {"runs": runs, "texts": _texts(ids[:400])}


def get_change_runs(q: dict) -> dict:
    return {"runs": history.change_runs(_project(q.get("project")), busy=_busy())[:60]}


def get_files(q: dict) -> list:
    project = _project(q.get("project"))
    if not project or not sources.neo4j_status()["connected"]:
        return []
    return demo.linked_code_entities(project=project)


def get_graph(q: dict) -> dict:
    _need_neo4j()
    project = _project(q.get("project"))
    mode = q.get("mode") if q.get("mode") in sources.GRAPH_MODES else "links"
    return _cached(f"graph:{project}:{mode}", 3, lambda: sources.neo4j_uskg_graph(max_traces=300, max_orphans=60, project=project, mode=mode))


def get_links(q: dict) -> dict:
    """All trace links of the project, with reasons, decay flags and orphan requirements (for the React dashboard)."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    return _cached(f"links:{project}", 3, lambda: sources.neo4j_links(project))


def get_analytics(q: dict) -> dict:
    """Distributions, change hotspots, weakest links and a timeline for the project's trace links."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    from apps.api import analytics

    return _cached(f"analytics:{project}", 3, lambda: analytics.build(sources.neo4j_links(project)))


def get_completeness(q: dict) -> dict:
    """Traceability completeness per requirement (0-100) and orphan requirements; no C3 evidence figure is available yet."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()

    def compute() -> dict:
        from agents.traceability_agent.completeness import completeness_scores
        from shared.uskg.client import USKGClient

        with USKGClient() as uskg:
            reqs = uskg.get_artifacts("requirement", project=project)
            results = completeness_scores(reqs, uskg.get_traces(project=project))
        rows = [r.model_dump() for r in sorted(results, key=lambda r: r.score)]
        mean = sum(r["score"] for r in rows) / len(rows) if rows else 0.0
        return {"project": project, "mean": round(mean, 1), "orphans": sum(1 for r in rows if r["is_orphan"] and not r["is_broken"]), "broken": sum(1 for r in rows if r["is_broken"]), "requirements": rows}

    return _cached(f"completeness:{project}", 3, compute)


def get_analysis(_: dict) -> dict:
    """Stored analysis results of the reranker / stage-1 experiments (data/results/*.json), if present."""
    results = PROJECT_ROOT / "data" / "results"

    def read(name: str) -> Any:
        path = results / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    expansion = read("query_expansion_itrust.json")
    return {"reranker": read("reranker.json"), "stage1Embeddings": read("stage1_embeddings.json"),
            "queryExpansion": {"model": expansion.get("model"), "requirements": len(expansion.get("answers", {}))} if expansion else None}


def get_results(_: dict) -> dict:
    return sources.load_results()


# ------------------------------------------------------------------ POST handlers
def post_link(body: dict) -> dict:
    project = _project(body.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    _need_idle()
    try:
        top_k = int(body.get("top_k", 3))
        added = demo.add_requirement(str(body.get("text", "")), str(body.get("id", "")), project)
        started = runner.start({"kind": "link", "requirement_ids": [added["id"]], "top_k": top_k,
                                "retrieval": "hybrid", "project": project})
    except (demo.DemoError, runner.RunnerError, ValueError, TypeError) as exc:
        raise ApiError(400, str(exc)) from exc
    _forget()
    return {**added, "minutes": started.get("minutes")}


def post_link_existing(body: dict) -> dict:
    """Create trace links for the requirements already in the graph (written by C1) that have none yet."""
    project = _project(body.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    _need_idle()
    info = sources.neo4j_unlinked(project)
    if not info["requirements"]:
        raise ApiError(400, "This project has no requirements yet.")
    if not info["codeFiles"]:
        raise ApiError(400, "This project has no code files yet.")
    if not info["unlinked"]:
        raise ApiError(400, "Every requirement of this project already has a trace link.")
    try:
        top_k = int(body.get("top_k", 3))
        started = runner.start({"kind": "link", "project": project, "top_k": top_k, "retrieval": "hybrid",
                                "limit_sources": 0, "only_unlinked": True})
    except (runner.RunnerError, ValueError, TypeError) as exc:
        raise ApiError(400, str(exc)) from exc
    _forget()
    calls = info["unlinked"] * top_k
    return {"requirements": info["unlinked"], "calls": calls, "minutes": round(calls * runner.SECONDS_PER_CALL / 60), "pid": started["pid"]}


def post_scan(body: dict) -> dict:
    """Drift detection: re-check the project's trace links whose requirement or code text has changed."""
    project = _project(body.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    _need_idle()
    info = sources.neo4j_unlinked(project)
    if not info["links"]:
        raise ApiError(400, "This project has no trace links to scan yet. Create trace links first.")
    try:
        runner.start({"kind": "monitor", "project": project, "force": bool(body.get("force"))})
    except runner.RunnerError as exc:
        raise ApiError(400, str(exc)) from exc
    _forget()
    return {"links": info["links"]}


def post_commit(body: dict) -> dict:
    project = _project(body.get("project"))
    _need_neo4j()
    _need_idle()
    code_id = str(body.get("code_id", ""))
    try:
        edit = demo.modify(code_id, str(body.get("mutation", "")))
        runner.start({"kind": "changed", "project": project, "code_changed": [code_id]})
    except (demo.DemoError, runner.RunnerError) as exc:
        raise ApiError(400, str(exc)) from exc
    _forget()
    return edit


def post_undo(body: dict) -> dict:
    _need_neo4j()
    try:
        result = demo.undo_changes(_project(body.get("project")))
    except demo.DemoError as exc:
        raise ApiError(400, str(exc)) from exc
    _forget()
    return result


def post_reset(body: dict) -> dict:
    project = _project(body.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    _need_idle()
    try:
        result = demo.reset(project)
    except demo.DemoError as exc:
        raise ApiError(400, str(exc)) from exc
    _forget()
    return result


class Download:
    """A file the browser should save instead of a JSON answer."""

    def __init__(self, body: str, content_type: str, filename: str) -> None:
        self.body, self.content_type, self.filename = body.encode("utf-8"), content_type, filename


def get_export(q: dict) -> Download:
    """CSV / JSON exports of the traceability state: ``kind`` = matrix | links | report."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    kind = q.get("kind", "matrix")
    if kind not in ("matrix", "links", "report"):
        raise ApiError(400, "kind must be matrix, links or report.")
    _need_neo4j()
    from agents.traceability_agent import report as rep
    from shared.uskg.client import USKGClient

    with USKGClient() as uskg:
        reqs = uskg.get_artifacts("requirement", project=project)
        traces = uskg.get_traces(project=project)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in project)
    if kind == "report":
        return Download(json.dumps(rep.report(reqs, traces), indent=1), "application/json; charset=utf-8", f"{safe}_trace_report.json")
    body = rep.matrix_csv(reqs, traces) if kind == "matrix" else rep.links_csv(reqs, traces)
    return Download(body, "text/csv; charset=utf-8", f"{safe}_trace_{kind}.csv")


GET_ROUTES: dict[str, Callable[[dict], Any]] = {
    "/api/health": get_health, "/api/projects": get_projects, "/api/activity": get_activity,
    "/api/link-runs": get_link_runs, "/api/change-runs": get_change_runs, "/api/files": get_files,
    "/api/graph": get_graph, "/api/unlinked": get_unlinked, "/api/results": get_results,
    "/api/links": get_links, "/api/completeness": get_completeness, "/api/analysis": get_analysis, "/api/export": get_export, "/api/analytics": get_analytics,
}
POST_ROUTES: dict[str, Callable[[dict], Any]] = {
    "/api/link": post_link, "/api/link-existing": post_link_existing, "/api/scan": post_scan, "/api/commit": post_commit, "/api/undo": post_undo, "/api/reset": post_reset,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "C4Web"

    def log_message(self, *args: Any) -> None:  # keep the console quiet; errors are returned as JSON
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: Any) -> None:
        self._send(status, json.dumps(data, default=str).encode("utf-8"), "application/json; charset=utf-8")

    def _run(self, fn: Callable[[dict], Any], arg: dict) -> None:
        try:
            result = fn(arg)
            if isinstance(result, Download):
                self.send_response(200)
                self.send_header("Content-Type", result.content_type)
                self.send_header("Content-Length", str(len(result.body)))
                self.send_header("Content-Disposition", f'attachment; filename="{result.filename}"')
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(result.body)
                return
            self._json(200, result)
        except ApiError as exc:
            self._json(exc.status, {"detail": str(exc)})
        except Exception as exc:  # never crash the server; tell the page what went wrong
            self._json(500, {"detail": f"{type(exc).__name__}: {exc}"[:300]})

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        if url.path in ("/", "/index.html", "/legacy"):
            self._send(200, (WEB_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif url.path in GET_ROUTES:
            self._run(GET_ROUTES[url.path], {k: v[0] for k, v in parse_qs(url.query).items()})
        elif url.path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
        else:
            self._json(404, {"detail": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        if url.path not in POST_ROUTES:
            return self._json(404, {"detail": "Not found"})
        origin = self.headers.get("Origin")
        if self.headers.get("X-Requested-With") != "c4-web" or (origin and origin.split("://", 1)[-1] != self.headers.get("Host")):
            return self._json(403, {"detail": "Refused: requests must come from this page."})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._json(413, {"detail": "Request too large."})
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"detail": "Body must be JSON."})
        self._run(POST_ROUTES[url.path], body if isinstance(body, dict) else {})


def main() -> None:
    port = int(os.getenv("C4_WEB_PORT", "8000"))
    server = ThreadingHTTPServer((HOST, port), Handler)
    print(f"C4 web app: http://{HOST}:{port}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
