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


def stream_notifications(handler: BaseHTTPRequestHandler) -> None:
    """Stream Redis trace notifications to connected dashboard clients."""
    try:
        import redis
        from agents.traceability_agent.config import CHANGE_CHANNEL, DECAY_CHANNEL

        client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(DECAY_CHANNEL, CHANGE_CHANNEL)
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("X-Accel-Buffering", "no")
        handler.end_headers()
        handler.wfile.write(b": connected\n\n")
        handler.wfile.flush()
        while True:
            message = pubsub.get_message(timeout=15)
            if message and message.get("data"):
                payload = message["data"]
                try:
                    json.loads(payload)
                except (TypeError, ValueError):
                    payload = json.dumps({"event": message["channel"], "message": str(payload)})
                handler.wfile.write(f"event: {message['channel']}\ndata: {payload}\n\n".encode("utf-8"))
            else:
                handler.wfile.write(b": ping\n\n")
            handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return
    except Exception:
        return
    finally:
        try:
            pubsub.close()
            client.close()
        except (UnboundLocalError, AttributeError):
            pass


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


def get_notifications(q: dict) -> list[dict[str, Any]]:
    try:
        limit = int(q.get("limit", 40))
    except (TypeError, ValueError):
        limit = 40
    return history.notifications(limit)


def get_unlinked(q: dict) -> dict:
    """How many requirements of the project have no trace link yet (what "Create trace links" would work on)."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    info = sources.neo4j_unlinked(project)
    ids = info.get("ids") or []
    info["texts"] = {rid: text[:200] for rid, text in _texts(ids[:400]).items()}
    return info


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


def get_review_queue(q: dict) -> dict:
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    try:
        page, page_size = int(q.get("page", 1)), int(q.get("page_size", 40))
    except ValueError:
        raise ApiError(400, "page and page_size must be integers.")
    try:
        return sources.neo4j_review_queue(project, q.get("state", "needs_review"), page, page_size,
                                          q.get("requirement"), q.get("code"))
    except ValueError as exc:
        raise ApiError(400, str(exc)) from exc


def get_analytics(q: dict) -> dict:
    """Distributions, change hotspots, weakest links and a timeline for the project's trace links."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    from apps.api import analytics

    return _cached(f"analytics:{project}", 3, lambda: analytics.build(sources.neo4j_links(project)))


def get_labeling(q: dict) -> dict:
    """A fixed random sample of the project's verified links, the saved hand labels, and the precision they give."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()
    from apps.api import labeling

    try:
        n = min(200, max(5, int(q.get("n", 40))))
    except ValueError:
        n = 40
    links = sources.neo4j_links(project)["links"]
    sample = labeling.sample_links(links, n)
    requested = next((link for link in links if link["requirement"] == q.get("requirement")
                      and link["code"] == q.get("code") and link.get("status") != "decayed"), None)
    if requested is not None and requested not in sample:
        sample = sample[:max(0, n - 1)] + [requested]
    labels = {f"{l['requirement']}||{l['code']}": {"label": l["review"]}
              for l in sample if l.get("review") and l.get("reviewedHash") == l.get("textHash")}
    items = [{**l, "label": labels.get(f"{l['requirement']}||{l['code']}", {}).get("label")} for l in sample]
    return {"project": project, "items": items, "total": sum(link.get("status") != "decayed" for link in links),
            "stats": labeling.stats(sample, labels)}


def get_code_text(q: dict) -> dict:
    """The stored text of a code entity."""
    code = str(q.get("code", ""))
    if not code or len(code) > 500:
        raise ApiError(400, "code is required.")
    _need_neo4j()
    return {"code": code, "text": sources.neo4j_code_text(code, limit=None) if q.get("full") == "1" else sources.neo4j_code_text(code)}


def post_label(body: dict) -> dict:
    """Apply a versioned human decision to the graph; preserve the AI confidence."""
    project = _project(body.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    requirement, code, label = str(body.get("requirement", "")), str(body.get("code", "")), body.get("label")
    if not requirement or not code or len(requirement) > 200 or len(code) > 500:
        raise ApiError(400, "requirement and code are required.")
    _need_neo4j()
    from shared.uskg.client import USKGClient
    with runner.RUN_LOCK:
        _need_idle()
        try:
            with USKGClient() as uskg:
                result = uskg.review_link(project, requirement, code, label, str(body.get("text_hash", "")))
        except ValueError as exc:
            raise ApiError(409, str(exc)) from exc
    _forget()
    return result


def get_c3(q: dict) -> dict:
    """What Component 3 stores about validation for this project's requirements (read-only): RVUs and tests."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()

    def compute() -> dict:
        from agents.traceability_agent.c3 import coverage_from_rows
        from shared.uskg.client import USKGClient

        with USKGClient() as uskg:
            info = coverage_from_rows(uskg.get_c3_evidence(project))
        return {"project": project, "available": bool(info), "requirements": info}

    return _cached(f"c3:{project}", 3, compute)


def get_selfcheck(q: dict) -> dict:
    """C4's own consistency checks for the project (read-only, no LLM)."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()

    def compute() -> dict:
        from agents.traceability_agent.selfcheck import selfcheck_project
        from shared.uskg.client import USKGClient

        with USKGClient() as uskg:
            return selfcheck_project(uskg, project)

    return _cached(f"selfcheck:{project}", 3, compute)


def get_pr_curve(q: dict) -> dict:
    """Precision / recall of the stored links per confidence threshold, for projects that have ground truth."""
    project = _project(q.get("project"))
    if not project:
        raise ApiError(400, "Choose a project first.")
    _need_neo4j()

    def compute() -> dict:
        from agents.traceability_agent.pr_curve import pr_curve_project
        from shared.uskg.client import USKGClient

        with USKGClient() as uskg:
            return pr_curve_project(uskg, project) or {"project": project, "rows": [], "operating_point": None, "no_ground_truth": True}

    return _cached(f"prcurve:{project}", 3, compute)


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
            from agents.traceability_agent.c3 import evidence_coverage

            reqs = uskg.get_artifacts("requirement", project=project)
            evidence = evidence_coverage(uskg.get_c3_evidence(project))
            results = completeness_scores(reqs, uskg.get_traces(project=project), evidence)
        rows = [r.model_dump() for r in sorted(results, key=lambda r: r.score)]
        mean = sum(r["score"] for r in rows) / len(rows) if rows else 0.0
        return {"project": project, "mean": round(mean, 1), "c3Requirements": len(evidence), "orphans": sum(1 for r in rows if r["is_orphan"] and not r["is_broken"]), "broken": sum(1 for r in rows if r["is_broken"]), "requirements": rows}

    return _cached(f"completeness:{project}", 3, compute)


def get_analysis(_: dict) -> dict:
    """Stored analysis results of the reranker / stage-1 experiments (data/results/*.json), if present."""
    results = PROJECT_ROOT / "data" / "results"

    def read(name: str) -> Any:
        path = results / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    from apps.api import evidence

    expansion = read("query_expansion_itrust.json")
    return {"reranker": read("reranker.json"), "stage1Embeddings": read("stage1_embeddings.json"),
            "queryExpansion": {"model": expansion.get("model"), "requirements": len(expansion.get("answers", {}))} if expansion else None,
            "evidence": evidence.build(results)}


def get_results(_: dict) -> dict:
    return sources.load_results()


# ------------------------------------------------------------------ POST handlers
def post_delete_project(body: dict) -> dict:
    from apps.api import project_admin
    _need_neo4j()
    try:
        result = project_admin.delete_project(body.get('project'), body.get('confirmation'))
    except (project_admin.ProjectError, project_admin.rc.ConnectorError) as exc:
        raise ApiError(400, str(exc)) from exc
    finally:
        _forget()
    return result


def post_github(body: dict) -> dict:
    from apps.api import github_app
    try:
        action = body.get('action', 'status')
        if action == 'repositories':
            return github_app.repositories()
        if action == 'connect':
            return github_app.connect(_project(body.get('project')))
        if action == 'status':
            return github_app.configuration()
        raise ApiError(400, 'Unknown GitHub action.')
    except github_app.GitHubError as exc:
        raise ApiError(400, str(exc)) from exc


def get_repo_sync(q: dict) -> dict:
    from apps.api import repo_sync
    return repo_sync.status(_project(q.get("project")))


def post_browse_folders(body: dict) -> dict:
    from apps.api import repo_import

    try:
        return repo_import.browse_folders(body.get("path"))
    except repo_import.ImportError_ as exc:
        raise ApiError(400, str(exc)) from exc


def post_import(body: dict) -> dict:
    """Add a project: a public GitHub URL, or a folder inside the home folder. Reads the graph, writes CodeEntity nodes."""
    from apps.api import repo_import

    _need_neo4j()
    _need_idle()
    state = demo.allowed()
    if not state["allowed"]:
        raise ApiError(403, f"Adding projects is switched off: {state['reason']}")
    name = body.get("name") if isinstance(body.get("name"), str) else None
    try:
        if body.get("kind") == "folder":
            result = repo_import.import_folder(body.get("path"), name)
        else:
            branch = body.get("branch") if isinstance(body.get("branch"), str) else None
            result = repo_import.import_github(body.get("url"), name, branch, use_app=body.get("useApp") is True)
    except repo_import.ImportError_ as exc:
        raise ApiError(400, str(exc)) from exc
    _forget()
    return result


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
        ids = body.get("requirement_ids")
        if ids is not None and (not isinstance(ids, list) or not ids or len(ids) > 20
                                or not all(isinstance(rid, str) and rid in info["ids"] for rid in ids)):
            raise ApiError(400, "Select 1–20 unlinked requirements from this project.")
        params = {"kind": "link", "project": project, "top_k": top_k, "retrieval": "hybrid",
                  "limit_sources": 0}
        params.update({"requirement_ids": list(dict.fromkeys(ids))} if ids is not None else {"only_unlinked": True})
        started = runner.start(params)
    except (runner.RunnerError, ValueError, TypeError) as exc:
        raise ApiError(400, str(exc)) from exc
    _forget()
    count = len(set(ids)) if ids is not None else info["unlinked"]
    calls = count * top_k
    return {"requirements": count, "calls": calls, "minutes": round(calls * runner.SECONDS_PER_CALL / 60), "pid": started["pid"]}


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
    "/api/repo-sync": get_repo_sync, "/api/health": get_health, "/api/projects": get_projects, "/api/activity": get_activity,
    "/api/link-runs": get_link_runs, "/api/change-runs": get_change_runs, "/api/notifications/recent": get_notifications, "/api/files": get_files,
    "/api/graph": get_graph, "/api/unlinked": get_unlinked, "/api/results": get_results,
    "/api/links": get_links, "/api/review-queue": get_review_queue, "/api/completeness": get_completeness, "/api/analysis": get_analysis, "/api/export": get_export, "/api/analytics": get_analytics, "/api/c3": get_c3, "/api/selfcheck": get_selfcheck, "/api/pr-curve": get_pr_curve, "/api/labeling": get_labeling, "/api/code-text": get_code_text,
}
POST_ROUTES: dict[str, Callable[[dict], Any]] = {
    "/api/projects/delete": post_delete_project, "/api/github": post_github, "/api/folders": post_browse_folders, "/api/import": post_import, "/api/link": post_link, "/api/link-existing": post_link_existing, "/api/scan": post_scan, "/api/commit": post_commit, "/api/undo": post_undo, "/api/reset": post_reset, "/api/label": post_label,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "C4Web"
    protocol_version = "HTTP/1.1"

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
        if url.path == "/api/notifications":
            stream_notifications(self)
        elif url.path in ("/", "/index.html", "/legacy"):
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
    from apps.api import repo_sync
    from apps.api import github_app
    receiver = github_app.start_receiver() if os.getenv("GITHUB_WEBHOOK_SECRET") else None
    try:
        from shared.uskg.client import USKGClient
        with USKGClient() as graph:
            from apps.api.approval import migrate_reviews
            migrate_reviews(graph)
            graph.migrate_approval_policy()
    except Exception as exc:
        print(f"Approval policy migration deferred: {type(exc).__name__}", flush=True)
    watcher = repo_sync.start()
    print(f"C4 web app: http://{HOST}:{port}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        watcher.set()
        if receiver:
            receiver.shutdown()
            receiver.server_close()
        server.server_close()


if __name__ == "__main__":
    main()
