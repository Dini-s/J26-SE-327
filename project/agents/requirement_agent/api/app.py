"""FastAPI app for Component 1 (Requirement Intelligence).

    uvicorn agents.requirement_agent.api.app:app --port 8000        (binds 127.0.0.1)

Storage: SQLite file and uploads under outputs/c1_workspace/ (C1_WORKSPACE overrides). Generation backend: C1_GENERATION_BACKEND = replay | ollama | mock
(default replay). Contract: docs/c1_api_contract.md.
"""
import hashlib
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Body, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..generation import BackendError
from . import analysis, autosync, cleanup, ingest, jira, planning, priority, publishing, schemas, service, settings
from .db import DEFAULT_PROJECT_KEY, Database, dumps, now
from . import engine as engine_mod
from .engine import EngineStore
from .errors import ApiError
from .gen_worker import GenerationManager, make_backend
from .neo4j_schema import DEFAULT_SOURCE_TYPE, UPLOAD_SOURCE_TYPES
from .neo4j_store import Neo4jStore

log = logging.getLogger("c1.api")


def _error(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(workspace=None, backend=None, backend_name=None, model_name=None, replay_file=None, models_dir=None, neo4j_store_=None, jira_http=None, jira_config=None):
    ws = settings.workspace_dir(workspace)
    (ws / "uploads").mkdir(parents=True, exist_ok=True)
    settings.configure_embedding_cache(ws)
    db = Database(ws / "c1.db")
    if not db.one("SELECT id FROM projects LIMIT 1"):
        db.ensure_planning(db.run("INSERT INTO projects (name, created_at, project_key, archived) VALUES (?,?,?,0)", (settings.DEFAULT_PROJECT_NAME, now(), DEFAULT_PROJECT_KEY)))

    name = settings.generation_backend_name(backend_name)
    init_error = None
    if backend is None:
        try:
            backend, model = make_backend(name, replay_file)
        except BackendError as exc:
            backend, model, init_error = None, name, str(exc)
    else:
        model = model_name or name
    if model_name:
        model = model_name
    engine = EngineStore(db, name, model, backend)
    manager = GenerationManager(db, backend, name, model, init_error, engine)
    manager.resume_pending()  # queued/running drafts of the last run go back in the queue (the queue itself is only in memory)
    manager.start()

    neo4j_store = neo4j_store_ if neo4j_store_ is not None else Neo4jStore(db)
    sync = autosync.AutoSync(db, neo4j_store, enabled=autosync.enabled_from_env(os.environ))  # C1_AUTO_SYNC=0 switches it off
    manager.on_draft = sync.notify_uid
    jira_svc = jira.JiraService(db, http=jira_http, config_loader=jira_config)  # tests pass a fake HTTP client; nothing else ever reaches Atlassian

    @asynccontextmanager
    async def lifespan(app):
        sync.start()
        yield
        sync.stop()
        manager.stop()

    app = FastAPI(title="Component 1 - Requirement Intelligence API", version="1.0.0", lifespan=lifespan)
    app.state.db, app.state.manager, app.state.workspace, app.state.engine, app.state.neo4j, app.state.sync = db, manager, ws, engine, neo4j_store, sync
    app.state.jira = jira_svc
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins(), allow_methods=["*"], allow_headers=["*"])

    # ------------------------------------------------------------------------------------------------ errors
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=exc.body())

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return _error(422, "validation_error", f"{where}: {first.get('msg', 'invalid request')}".strip(": "))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        codes = {404: "not_found", 405: "method_not_allowed"}
        return _error(exc.status_code, codes.get(exc.status_code, "http_error"), str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.exception("unhandled error")
        return _error(500, "internal_error", "Unexpected server error; see the server log.")

    # ------------------------------------------------------------------------------------------------ helpers
    def job_out(job_id):
        j = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not j:
            raise ApiError(404, "job_not_found", f"Job {job_id} does not exist.")
        counts = service.generation_counts(db, j["project_id"])
        stage = j["stage"]
        if j["part_a_done"]:
            stage = "improve" if counts["queued"] > 0 and not manager.paused else "share"
        return {"job_id": j["id"], "project_id": j["project_id"], "stage": stage, "part_a_done": bool(j["part_a_done"]),
                "generation": counts, "requirements": counts["total"], "error": j["error"], "policy": j["policy"]}

    def set_job(job_id, **fields):
        cols = ", ".join(f"{k}=?" for k in fields)
        db.run(f"UPDATE jobs SET {cols}, updated_at=? WHERE id=?", (*fields.values(), now(), job_id))

    # ------------------------------------------------------------------------------------------------ endpoints
    @app.get("/api/health", response_model=schemas.Health)
    def health():
        loaded = analysis.part_a_loaded(models_dir)
        return {"status": "ok" if loaded else "degraded", "part_a_loaded": loaded, "generation_backend": name,
                "generation_reachable": manager.reachable(), "model": manager.active_model(), "generation_target": engine.target()}

    @app.get("/api/engine", response_model=schemas.EngineOut)
    def get_engine():
        return engine.public(manager.device_reachable())

    @app.put("/api/engine", response_model=schemas.EngineOut)
    def put_engine(body: schemas.EngineUpdate):
        before = engine.target()
        engine.update(body.model_dump(exclude_unset=True))
        if engine.target() != before:
            manager.on_target_changed()
        return engine.public(manager.device_reachable())

    @app.post("/api/engine/test", response_model=schemas.EngineTestOut)
    def test_engine(body: schemas.EngineTestIn):
        if body.target == engine_mod.DEVICE:
            started = time.monotonic()
            ok = manager.device_reachable()
            detail = "Connected; the on-device writing model is ready." if ok else "The on-device writing model does not answer. Check that it is running."
            return {"ok": ok, "detail": detail, "latency_ms": int(round((time.monotonic() - started) * 1000))}
        if engine.disabled_reason:
            raise ApiError(409, "cloud_disabled", engine.disabled_reason)
        if not engine.cloud_url():
            raise ApiError(409, "cloud_not_configured", "Set the cloud address first.")
        result = engine_mod.probe(engine.cloud_url(), engine.cloud_key(), engine.cloud_model())
        engine.record_test(result)
        return result

    def project_view(p):
        try:
            publish = neo4j_store.publish_info(p["id"])
        except Exception:  # noqa: BLE001 - counts must load even if the publish check cannot
            publish = None
        return service.project_out(db, p, publish)

    @app.get("/api/projects", response_model=list[schemas.ProjectOut])
    def list_projects(include_archived: bool = Query(False, description="also list archived projects")):
        where = "" if include_archived else "WHERE archived=0"
        return [project_view(service.with_key(db, p)) for p in db.all(f"SELECT * FROM projects {where} ORDER BY id")]

    @app.post("/api/projects", response_model=schemas.ProjectOut, status_code=201, responses={409: {"model": schemas.ErrorResponse}})
    def create_project(body: schemas.ProjectCreate):
        return project_view(service.create_project(db, body.name))

    @app.patch("/api/projects/{pid}", response_model=schemas.ProjectOut, responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def rename_project(pid: int, body: schemas.ProjectRename):
        out = project_view(service.with_key(db, service.rename_project(db, pid, body.name)))
        sync.notify(pid)  # the new name reaches the graph
        return out

    @app.post("/api/projects/{pid}/archive", response_model=schemas.ProjectOut, responses={404: {"model": schemas.ErrorResponse}})
    def archive_project(pid: int):
        return project_view(service.with_key(db, service.set_archived(db, pid, True)))

    @app.post("/api/projects/{pid}/unarchive", response_model=schemas.ProjectOut, responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def unarchive_project(pid: int):
        return project_view(service.with_key(db, service.set_archived(db, pid, False)))

    @app.get("/api/projects/{pid}/overview", response_model=schemas.Overview, responses={404: {"model": schemas.ErrorResponse}})
    def project_overview(pid: int):
        return service.overview(db, pid, manager, engine, neo4j_store, sync.status(pid))

    @app.post("/api/projects/{pid}/sources", response_model=schemas.UploadResult, status_code=201,
              responses={400: {"model": schemas.ErrorResponse}, 413: {"model": schemas.ErrorResponse}})
    def upload_sources(pid: int, files: list[UploadFile] = File(...), source_type: str = Form(DEFAULT_SOURCE_TYPE),
                       phase_id: Optional[int] = Form(None), sprint_id: Optional[int] = Form(None)):
        service.project_or_404(db, pid)
        target = planning.upload_target(db, pid, phase_id, sprint_id)  # a bad phase or sprint is refused before anything is stored
        chosen = phase_id is not None or sprint_id is not None
        source_type = (source_type or DEFAULT_SOURCE_TYPE).strip().lower()
        if source_type not in UPLOAD_SOURCE_TYPES:
            raise ApiError(400, "invalid_parameter", f"source_type must be one of {list(UPLOAD_SOURCE_TYPES)}.")
        root = (ws / "uploads").resolve()
        accepted, rejected, detected, first_error = [], [], [], None
        for f in files:
            shown = ingest.safe_filename(f.filename)
            try:
                ext = ingest.check_extension(shown)
                chunks, size = [], 0
                while True:
                    chunk = f.file.read(1 << 20)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > settings.MAX_UPLOAD_BYTES:
                        raise ApiError(413, "file_too_large", f"{shown}: larger than the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
                    chunks.append(chunk)
                raw = b"".join(chunks)
                if not raw:
                    raise ApiError(400, "empty_file", f"{shown}: the file is empty.")
                extracted = ingest.extract(raw, ext)
                folder = (root / str(pid)).resolve()
                folder.mkdir(parents=True, exist_ok=True)
                stored = (folder / f"{uuid.uuid4().hex}{ext}").resolve()
                if folder not in stored.parents:
                    raise ApiError(400, "bad_filename", "The file name is not allowed.")
                stored.write_bytes(raw)
                sprint_for = target
                name = None if chosen else planning.detect_sprint(shown, extracted["text"])
                if name:  # the file names a sprint: use it (proposed, not confirmed, when it did not exist yet)
                    found, _ = planning.find_or_propose(db, pid, name)
                    sprint_for = found["id"]
                    detected.append({"filename": shown, "sprint_id": found["id"], "name": found["name"], "confirmed": bool(found["confirmed"])})
                sid = db.run("INSERT INTO sources (project_id, filename, stored_path, ext, size_bytes, pages, warnings, extracted, created_at, source_type, sha256, default_sprint_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                             (pid, shown, str(stored), ext, size, extracted["pages"], dumps(extracted["warnings"]),
                              dumps({"text": extracted["text"], "line_map": extracted["line_map"]}), now(), source_type, hashlib.sha256(raw).hexdigest(), sprint_for))
                accepted.append(service.source_out(db.one("SELECT * FROM sources WHERE id=?", (sid,))))
            except ApiError as exc:
                first_error = first_error or exc
                rejected.append({"filename": shown, "code": exc.code, "message": exc.message})
        if not accepted and first_error:
            raise first_error
        return {"accepted": accepted, "rejected": rejected, "sprint_detected": bool(detected), "detected": detected}

    @app.get("/api/projects/{pid}/sources", response_model=list[schemas.SourceOut])
    def list_sources(pid: int):
        service.project_or_404(db, pid)
        return service.sources_out(db, pid)

    @app.delete("/api/projects/{pid}/sources/{source_id}", status_code=204, response_class=Response,
                responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def delete_source(pid: int, source_id: int):
        cleanup.delete_sources(db, ws, pid, source_id)
        sync.notify(pid)
        return Response(status_code=204)

    @app.delete("/api/projects/{pid}/sources", status_code=204, response_class=Response,
                responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def clear_sources(pid: int):
        cleanup.delete_sources(db, ws, pid, None)
        sync.notify(pid)
        return Response(status_code=204)

    def run_analysis(pid, policy, only=None, force=False):
        """The analysis of the documents that need it (all of them with `force`, only `only` otherwise). Returns (job id, result, drafts queued)."""
        service.project_or_404(db, pid)
        policy = policy.strip().lower()
        if policy not in priority.POLICIES:
            raise ApiError(400, "invalid_parameter", f"policy must be one of {list(priority.POLICIES)}.")
        job_id = uuid.uuid4().hex[:12]
        db.run("INSERT INTO jobs (id, project_id, stage, part_a_done, created_at, updated_at, policy) VALUES (?,?,?,?,?,?,?)", (job_id, pid, "collect", 0, now(), now(), policy))
        try:
            result = analysis.run_part_a(db, pid, models_dir, on_stage=lambda s: set_job(job_id, stage=s), only=only, force=force)
        except ApiError as exc:
            set_job(job_id, error=exc.message)
            raise
        except Exception as exc:
            set_job(job_id, error=f"{exc.__class__.__name__}: {exc}")
            raise
        set_job(job_id, stage="improve", part_a_done=1)
        queued = manager.plan(pid, policy, only=set(result["new_uids"]))  # drafts only for requirements that are new in this run
        if result["processed_sources"]:
            sync.notify(pid)
        return job_id, result, queued

    @app.post("/api/projects/{pid}/analyze", response_model=schemas.Job, status_code=202)
    def analyze(pid: int, policy: str = Query(priority.DEFAULT_POLICY, description="smart | all | manual: which drafts are queued automatically")):
        """Analyses only the documents that are not analysed yet (or failed, or changed); analysed documents are skipped completely."""
        job_id, _, _ = run_analysis(pid, policy)
        return job_out(job_id)

    @app.post("/api/projects/{pid}/sources/{source_id}/reanalyze", response_model=schemas.ReanalyzeOut, status_code=202,
              responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def reanalyze_source(pid: int, source_id: int, policy: str = Query(priority.DEFAULT_POLICY)):
        """Analyse one document again. Requirements whose text is unchanged keep their decision and draft; changed or removed ones go to the audit trail."""
        service.project_or_404(db, pid)
        if not db.one("SELECT id FROM sources WHERE id=? AND project_id=?", (source_id, pid)):
            raise ApiError(404, "source_not_found", f"Source {source_id} does not exist in project {pid}.")
        if cleanup.project_busy(db, pid):
            raise ApiError(409, "project_busy", cleanup.BUSY_MESSAGE)
        job_id, result, queued = run_analysis(pid, policy, only={source_id}, force=True)
        return {"source_id": source_id, "kept": result["kept"], "changed": result["changed"], "removed": result["removed"], "added": result["added"],
                "queued": queued, "job": job_out(job_id)}

    @app.get("/api/jobs/{job_id}", response_model=schemas.Job)
    def get_job(job_id: str):
        return job_out(job_id)

    @app.get("/api/projects/{pid}/summary", response_model=schemas.Summary)
    def project_summary(pid: int):
        return service.summary(db, pid, manager)

    @app.get("/api/projects/{pid}/requirements", response_model=schemas.RequirementList)
    def project_requirements(pid: int, risk: Optional[str] = None, type: str = "all", q: Optional[str] = None,
                             limit: int = Query(50), offset: int = Query(0), sprint_id: Optional[int] = Query(None, description="only requirements of this (effective) sprint")):
        return service.list_requirements(db, pid, risk, type, q, limit, offset, sprint_id)

    @app.get("/api/requirements/{rid}", response_model=schemas.RequirementDetail)
    def requirement_detail(rid: str):
        return service.detail(db, rid)

    @app.post("/api/requirements/{rid}/generate", response_model=schemas.GenerateOut, status_code=202)
    def regenerate(rid: str):
        uid = service.resolve_uid(db, rid)
        return {"uid": uid, "generation_state": manager.request(uid)}

    @app.post("/api/projects/{pid}/generate", response_model=schemas.GenerateAllOut, status_code=202)
    def generate_remaining(pid: int):
        service.project_or_404(db, pid)
        return {"queued": manager.enqueue_remaining(pid)}

    # ------------------------------------------------------------------------------------------------ jira (read-only)
    JIRA = "/api/projects/{pid}/integrations/jira"
    JIRA_ERRORS = {404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}, 502: {"model": schemas.ErrorResponse}}

    @app.get(JIRA, response_model=schemas.JiraStatus, responses={404: {"model": schemas.ErrorResponse}})
    def jira_status(pid: int):
        service.project_or_404(db, pid)
        return jira_svc.status(pid)

    @app.post(JIRA + "/connect", response_model=schemas.JiraConnectOut, responses=JIRA_ERRORS)
    def jira_connect(pid: int):
        service.project_or_404(db, pid)
        return jira_svc.connect(pid)

    @app.delete(JIRA, status_code=204, response_class=Response, responses={404: {"model": schemas.ErrorResponse}})
    def jira_disconnect(pid: int):
        service.project_or_404(db, pid)
        jira_svc.disconnect(pid)
        return Response(status_code=204)

    @app.get(JIRA + "/projects", response_model=list[schemas.JiraProject], responses=JIRA_ERRORS)
    def jira_projects(pid: int):
        service.project_or_404(db, pid)
        return jira_svc.projects(pid)

    @app.get(JIRA + "/boards", response_model=list[schemas.JiraBoard], responses=JIRA_ERRORS)
    def jira_boards(pid: int, project_key: str = Query(..., description="the Jira project key")):
        service.project_or_404(db, pid)
        return jira_svc.boards(pid, project_key)

    @app.get(JIRA + "/sprints", response_model=list[schemas.JiraSprintOut], responses=JIRA_ERRORS)
    def jira_sprints(pid: int, board_id: int = Query(...), states: str = Query("active,future", description="active, future and/or closed, comma separated")):
        service.project_or_404(db, pid)
        return jira_svc.sprints(pid, board_id, [s for s in states.split(",") if s.strip()])

    @app.post(JIRA + "/import", response_model=schemas.JiraImportOut, responses=JIRA_ERRORS)
    def jira_import(pid: int, body: schemas.JiraImportIn):
        service.project_or_404(db, pid)
        policy = body.policy.strip().lower()
        if policy not in priority.POLICIES:
            raise ApiError(400, "invalid_parameter", f"policy must be one of {list(priority.POLICIES)}.")
        if cleanup.project_busy(db, pid):
            raise ApiError(409, "project_busy", cleanup.BUSY_MESSAGE)
        result = jira_svc.import_issues(pid, body.project_key, body.board_id, body.sprint_states, body.issue_types, body.set_current, body.target_sprint_id)
        source_ids = result.pop("source_ids")
        queued, job_id, analysis_error = 0, None, None
        if body.analyze and source_ids:  # the normal analysis of the new or changed documents, then the drafts the policy asks for
            try:
                job_id, _, queued = run_analysis(pid, policy, only=set(source_ids))
            except ApiError as exc:
                analysis_error = exc.code
            except Exception as exc:  # noqa: BLE001 - the import itself worked and stays
                log.warning("analysis after a Jira import failed: %s", exc.__class__.__name__)
                analysis_error = "analysis_failed"
        sync.notify(pid)
        return dict(result, queued=queued, job_id=job_id, analysis_error=analysis_error)

    @app.get("/api/integrations/jira/callback", status_code=302, response_class=Response, summary="OAuth redirect target: finishes the connection and sends the browser back to the module")
    def jira_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
        return RedirectResponse(jira_svc.callback(code, state, error), status_code=302)

    @app.post("/api/projects/{pid}/drafts/retry-failed", response_model=schemas.GenerateAllOut, status_code=202, responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def retry_failed_drafts(pid: int):
        service.project_or_404(db, pid)
        if service.generation_counts(db, pid)["queued"] > 0:
            raise ApiError(409, "generation_running", "Drafts are being written right now. Retry the failed ones when it has finished.")
        return {"queued": manager.retry_failed(pid)}

    @app.post("/api/projects/{pid}/generation/pause", response_model=schemas.PausedOut)
    def pause_generation(pid: int):
        service.project_or_404(db, pid)
        manager.set_paused(True)
        return {"paused": True}

    @app.post("/api/projects/{pid}/generation/resume", response_model=schemas.PausedOut)
    def resume_generation(pid: int):
        service.project_or_404(db, pid)
        manager.set_paused(False)
        return {"paused": False}

    def sync_draft(uid, before):
        """The draft follows the effective text (the edited text while the decision is `edited`, else the original). Never fails the decision itself."""
        try:
            manager.sync_draft(uid, before)
        except Exception:  # noqa: BLE001
            log.exception("draft could not follow the decision")

    def decided(rid, body):
        before = manager.source_text(service.resolve_uid(db, rid))[0]
        out = service.set_decision(db, rid, body.decision, body.edited_text, body.note)
        sync_draft(out["uid"], before)
        sync.notify_uid(out["uid"])
        return out

    @app.get("/api/requirements/{rid}/decision", response_model=schemas.DecisionState)
    def get_decision(rid: str):
        return service.get_decision(db, rid)

    @app.put("/api/requirements/{rid}/decision", response_model=schemas.DecisionOut, responses={400: {"model": schemas.ErrorResponse}})
    def put_decision(rid: str, body: schemas.DecisionIn = Body(...)):
        """The one current decision of the requirement: creates it or replaces the earlier one."""
        return decided(rid, body)

    @app.delete("/api/requirements/{rid}/decision", status_code=204, response_class=Response)
    def delete_decision(rid: str):
        """Back to pending."""
        uid = service.resolve_uid(db, rid)
        before = manager.source_text(uid)[0]
        service.clear_decision(db, rid)
        sync_draft(uid, before)
        sync.notify_uid(uid)
        return Response(status_code=204)

    @app.post("/api/requirements/{rid}/decision", response_model=schemas.DecisionOut, deprecated=True, responses={400: {"model": schemas.ErrorResponse}})
    def decide(rid: str, body: schemas.DecisionIn = Body(...)):
        """Deprecated alias of PUT: it also replaces the current decision instead of adding one."""
        return decided(rid, body)

    @app.post("/api/projects/{pid}/publish/neo4j", response_model=schemas.PublishOut,
              responses={503: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def publish_neo4j(pid: int, body: Optional[schemas.PublishIn] = Body(None)):
        """"Sync now": the same idempotent publish the background sync uses."""
        body = body or schemas.PublishIn()
        out = neo4j_store.publish(pid, body.project_id, body.project_name)
        sync.record_manual(pid, out)
        return out

    def publish_change(pid, body, publishing_on):
        out = publishing.change(db, pid, body.document_ids, body.sprint_id, publishing_on)
        state, error = "synced", None
        if out["changed"]:
            sync.notify(pid)  # the background sync keeps trying if the first attempt below does not work
            try:
                sync.record_manual(pid, neo4j_store.publish(pid))
            except ApiError as exc:
                state, error = ("not_configured" if exc.code == "neo4j_unconfigured" else "retrying"), exc.code
        published, total = publishing.counts(db, pid)
        return dict(out, published_documents=published, total_documents=total, sync={"state": state, "error": error})

    @app.post("/api/projects/{pid}/publish", response_model=schemas.PublishDocsOut, responses={400: {"model": schemas.ErrorResponse}, 404: {"model": schemas.ErrorResponse}})
    def publish_documents(pid: int, body: schemas.PublishDocsIn):
        """Publish documents (a list, or every analysed document of a sprint) and sync now. Documents that cannot be published are skipped with a reason."""
        return publish_change(pid, body, True)

    @app.post("/api/projects/{pid}/unpublish", response_model=schemas.PublishDocsOut, responses={400: {"model": schemas.ErrorResponse}, 404: {"model": schemas.ErrorResponse}})
    def unpublish_documents(pid: int, body: schemas.PublishDocsIn):
        """Take documents back: they become inactive for the other components (nothing is deleted) and can be published again."""
        return publish_change(pid, body, False)

    @app.get("/api/projects/{pid}/sprints/{sprint_id}/summary", response_model=schemas.SprintSummary, responses={404: {"model": schemas.ErrorResponse}})
    def sprint_summary(pid: int, sprint_id: int):
        """Totals of one sprint and one row per document (numbers, decisions, findings, publish state)."""
        service.project_or_404(db, pid)
        return publishing.sprint_summary(db, pid, sprint_id, sync.status(pid)["state"])

    @app.get("/api/projects/{pid}/sync", response_model=schemas.SyncStatus, responses={404: {"model": schemas.ErrorResponse}})
    def sync_status(pid: int):
        """State of the background sync (reads the workspace only; the graph database is not contacted)."""
        service.project_or_404(db, pid)
        return sync.status(pid)

    # ------------------------------------------------------------------------------------------------ phases and sprints
    @app.get("/api/projects/{pid}/phases", response_model=list[schemas.PhaseOut], responses={404: {"model": schemas.ErrorResponse}})
    def list_phases(pid: int):
        return planning.list_phases(db, pid)

    @app.post("/api/projects/{pid}/phases", response_model=schemas.PhaseOut, status_code=201, responses={409: {"model": schemas.ErrorResponse}})
    def create_phase(pid: int, body: schemas.PhaseIn):
        out = planning.create_phase(db, pid, body.name)
        sync.notify(pid)
        return out

    @app.patch("/api/projects/{pid}/phases/{phase_id}", response_model=schemas.PhaseOut, responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def update_phase(pid: int, phase_id: int, body: schemas.PhaseUpdate):
        out = planning.update_phase(db, pid, phase_id, body.model_dump(exclude_unset=True))
        sync.notify(pid)
        return out

    @app.delete("/api/projects/{pid}/phases/{phase_id}", status_code=204, response_class=Response, responses={404: {"model": schemas.ErrorResponse}})
    def delete_phase(pid: int, phase_id: int):
        """Its sprints stay and lose the phase."""
        planning.delete_phase(db, pid, phase_id)
        sync.notify(pid)
        return Response(status_code=204)

    @app.get("/api/projects/{pid}/sprints", response_model=list[schemas.SprintOut], responses={404: {"model": schemas.ErrorResponse}})
    def list_sprints(pid: int):
        return planning.list_sprints(db, pid)

    @app.post("/api/projects/{pid}/sprints", response_model=schemas.SprintOut, status_code=201, responses={409: {"model": schemas.ErrorResponse}})
    def create_sprint(pid: int, body: schemas.SprintIn):
        out = planning.create_sprint(db, pid, body.model_dump())
        sync.notify(pid)
        return out

    @app.patch("/api/projects/{pid}/sprints/{sprint_id}", response_model=schemas.SprintOut, responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def update_sprint(pid: int, sprint_id: int, body: schemas.SprintUpdate):
        out = planning.update_sprint(db, pid, sprint_id, body.model_dump(exclude_unset=True))
        sync.notify(pid)
        return out

    @app.delete("/api/projects/{pid}/sprints/{sprint_id}", response_model=schemas.SprintDeleted, responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def delete_sprint(pid: int, sprint_id: int, reassign_to: Optional[int] = Query(None, description="required when the sprint holds requirements or documents or is the current one")):
        out = planning.delete_sprint(db, pid, sprint_id, reassign_to)
        sync.notify(pid)
        return out

    @app.put("/api/projects/{pid}/current-sprint", response_model=schemas.SprintOut, responses={404: {"model": schemas.ErrorResponse}})
    def put_current_sprint(pid: int, body: schemas.CurrentSprintIn):
        out = planning.set_current(db, pid, body.sprint_id)
        sync.notify(pid)
        return out

    @app.put("/api/projects/{pid}/sources/{source_id}/sprint", response_model=schemas.SourceOut, responses={404: {"model": schemas.ErrorResponse}})
    def put_source_sprint(pid: int, source_id: int, body: schemas.SourceSprintIn):
        """The document's default sprint. Never starts an analysis."""
        planning.set_source_sprint(db, pid, source_id, body.sprint_id)
        sync.notify(pid)
        return next(s for s in service.sources_out(db, pid) if s["id"] == source_id)

    @app.post("/api/projects/{pid}/sources/{source_id}/assign-ranges", response_model=schemas.AssignRangesOut, responses={404: {"model": schemas.ErrorResponse}})
    def assign_ranges(pid: int, source_id: int, body: schemas.AssignRangesIn):
        """Sets the sprint of the requirements of this document by page range (each requirement gets its own sprint; later ranges win)."""
        out = planning.assign_ranges(db, pid, source_id, [r.model_dump() for r in body.ranges])
        sync.notify(pid)
        return out

    @app.post("/api/projects/{pid}/requirements/assign", response_model=schemas.AssignOut, responses={404: {"model": schemas.ErrorResponse}})
    def assign_requirements(pid: int, body: schemas.AssignIn):
        """Bulk assign requirements to a sprint (null = follow the document's default again)."""
        out = planning.assign_requirements(db, pid, body.requirement_ids, body.sprint_id)
        sync.notify(pid)
        return out

    @app.get("/api/projects/{pid}/publish/neo4j", response_model=schemas.PublishStatus)
    def publish_neo4j_status(pid: int, project_id: Optional[str] = Query(None, pattern=r"^[A-Za-z0-9_.:-]{1,100}$")):
        return neo4j_store.status(pid, project_id)

    @app.get("/api/projects/{pid}/export")
    def export(pid: int, format: str = "json"):
        fmt = format.lower()
        if fmt == "csv":
            body = service.export_csv(db, pid)
            return Response(content=body.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="c1_project_{pid}_requirements.csv"'})
        if fmt == "json":
            return JSONResponse(service.export_json(db, pid))
        raise ApiError(400, "invalid_parameter", "format must be csv or json.")

    return app


_APP = None


def __getattr__(attribute):
    """`uvicorn agents.requirement_agent.api.app:app` finds `app` here; importing this module (for tests) does not create the workspace."""
    global _APP
    if attribute == "app":
        if _APP is None:
            _APP = create_app()
        return _APP
    raise AttributeError(attribute)


if __name__ == "__main__":  # python -m agents.requirement_agent.api.app
    import uvicorn
    uvicorn.run(__getattr__("app"), host="127.0.0.1", port=8000)
