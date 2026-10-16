"""FastAPI app for Component 1 (Requirement Intelligence).

    uvicorn agents.requirement_agent.api.app:app --port 8000        (binds 127.0.0.1)

Storage: SQLite file and uploads under outputs/c1_workspace/ (C1_WORKSPACE overrides). Generation backend: C1_GENERATION_BACKEND = replay | ollama | mock
(default replay). Contract: docs/c1_api_contract.md.
"""
import hashlib
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Body, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..generation import BackendError
from . import analysis, cleanup, ingest, priority, schemas, service, settings
from .db import Database, dumps, now
from . import engine as engine_mod
from .engine import EngineStore
from .errors import ApiError
from .gen_worker import GenerationManager, make_backend
from .neo4j_schema import DEFAULT_SOURCE_TYPE, SOURCE_TYPES
from .neo4j_store import Neo4jStore

log = logging.getLogger("c1.api")


def _error(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(workspace=None, backend=None, backend_name=None, model_name=None, replay_file=None, models_dir=None, neo4j_store_=None):
    ws = settings.workspace_dir(workspace)
    (ws / "uploads").mkdir(parents=True, exist_ok=True)
    settings.configure_embedding_cache(ws)
    db = Database(ws / "c1.db")
    if not db.one("SELECT id FROM projects LIMIT 1"):
        db.run("INSERT INTO projects (name, created_at) VALUES (?,?)", (settings.DEFAULT_PROJECT_NAME, now()))

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

    @asynccontextmanager
    async def lifespan(app):
        yield
        manager.stop()

    neo4j_store = neo4j_store_ if neo4j_store_ is not None else Neo4jStore(db)
    app = FastAPI(title="Component 1 - Requirement Intelligence API", version="1.0.0", lifespan=lifespan)
    app.state.db, app.state.manager, app.state.workspace, app.state.engine, app.state.neo4j = db, manager, ws, engine, neo4j_store
    app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

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
            detail = (f"Connected; model '{model}' is served." if name == "ollama" else f"The {name} backend is ready.") if ok else \
                (f"The local model server does not answer or does not serve '{model}'." if name == "ollama" else f"The {name} backend is not ready.")
            return {"ok": ok, "detail": detail, "latency_ms": int(round((time.monotonic() - started) * 1000))}
        if engine.disabled_reason:
            raise ApiError(409, "cloud_disabled", engine.disabled_reason)
        if not engine.cloud_url():
            raise ApiError(409, "cloud_not_configured", "Set the cloud address first.")
        result = engine_mod.probe(engine.cloud_url(), engine.cloud_key(), engine.cloud_model())
        engine.record_test(result)
        return result

    @app.get("/api/projects", response_model=list[schemas.ProjectOut])
    def list_projects():
        return [service.project_out(db, p) for p in db.all("SELECT * FROM projects ORDER BY id")]

    @app.post("/api/projects", response_model=schemas.ProjectOut, status_code=201)
    def create_project(body: schemas.ProjectCreate):
        pid = db.run("INSERT INTO projects (name, created_at) VALUES (?,?)", (body.name.strip(), now()))
        return service.project_out(db, service.project_or_404(db, pid))

    @app.post("/api/projects/{pid}/sources", response_model=schemas.UploadResult, status_code=201,
              responses={400: {"model": schemas.ErrorResponse}, 413: {"model": schemas.ErrorResponse}})
    def upload_sources(pid: int, files: list[UploadFile] = File(...), source_type: str = Form(DEFAULT_SOURCE_TYPE)):
        service.project_or_404(db, pid)
        source_type = (source_type or DEFAULT_SOURCE_TYPE).strip().lower()
        if source_type not in SOURCE_TYPES:
            raise ApiError(400, "invalid_parameter", f"source_type must be one of {list(SOURCE_TYPES)}.")
        root = (ws / "uploads").resolve()
        accepted, rejected, first_error = [], [], None
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
                sid = db.run("INSERT INTO sources (project_id, filename, stored_path, ext, size_bytes, pages, warnings, extracted, created_at, source_type, sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (pid, shown, str(stored), ext, size, extracted["pages"], dumps(extracted["warnings"]),
                              dumps({"text": extracted["text"], "line_map": extracted["line_map"]}), now(), source_type, hashlib.sha256(raw).hexdigest()))
                accepted.append(service.source_out(db.one("SELECT * FROM sources WHERE id=?", (sid,))))
            except ApiError as exc:
                first_error = first_error or exc
                rejected.append({"filename": shown, "code": exc.code, "message": exc.message})
        if not accepted and first_error:
            raise first_error
        return {"accepted": accepted, "rejected": rejected}

    @app.get("/api/projects/{pid}/sources", response_model=list[schemas.SourceOut])
    def list_sources(pid: int):
        service.project_or_404(db, pid)
        return [service.source_out(s) for s in db.all("SELECT * FROM sources WHERE project_id=? ORDER BY id", (pid,))]

    @app.delete("/api/projects/{pid}/sources/{source_id}", status_code=204, response_class=Response,
                responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def delete_source(pid: int, source_id: int):
        cleanup.delete_sources(db, ws, pid, source_id)
        return Response(status_code=204)

    @app.delete("/api/projects/{pid}/sources", status_code=204, response_class=Response,
                responses={404: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def clear_sources(pid: int):
        cleanup.delete_sources(db, ws, pid, None)
        return Response(status_code=204)

    @app.post("/api/projects/{pid}/analyze", response_model=schemas.Job, status_code=202)
    def analyze(pid: int, policy: str = Query(priority.DEFAULT_POLICY, description="smart | all | manual: which drafts are queued automatically")):
        service.project_or_404(db, pid)
        policy = policy.strip().lower()
        if policy not in priority.POLICIES:
            raise ApiError(400, "invalid_parameter", f"policy must be one of {list(priority.POLICIES)}.")
        job_id = uuid.uuid4().hex[:12]
        db.run("INSERT INTO jobs (id, project_id, stage, part_a_done, created_at, updated_at, policy) VALUES (?,?,?,?,?,?,?)", (job_id, pid, "collect", 0, now(), now(), policy))
        try:
            result = analysis.run_part_a(db, pid, models_dir, on_stage=lambda s: set_job(job_id, stage=s))
        except ApiError as exc:
            set_job(job_id, error=exc.message)
            raise
        except Exception as exc:
            set_job(job_id, error=f"{exc.__class__.__name__}: {exc}")
            raise
        set_job(job_id, stage="improve", part_a_done=1)
        manager.plan(pid, policy)
        return job_out(job_id)

    @app.get("/api/jobs/{job_id}", response_model=schemas.Job)
    def get_job(job_id: str):
        return job_out(job_id)

    @app.get("/api/projects/{pid}/summary", response_model=schemas.Summary)
    def project_summary(pid: int):
        return service.summary(db, pid, manager)

    @app.get("/api/projects/{pid}/requirements", response_model=schemas.RequirementList)
    def project_requirements(pid: int, risk: Optional[str] = None, type: str = "all", q: Optional[str] = None,
                             limit: int = Query(50), offset: int = Query(0)):
        return service.list_requirements(db, pid, risk, type, q, limit, offset)

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

    @app.post("/api/requirements/{rid}/decision", response_model=schemas.DecisionOut)
    def decide(rid: str, body: schemas.DecisionIn = Body(...)):
        return service.set_decision(db, rid, body.decision, body.edited_text, body.note)

    @app.post("/api/projects/{pid}/publish/neo4j", response_model=schemas.PublishOut,
              responses={503: {"model": schemas.ErrorResponse}, 409: {"model": schemas.ErrorResponse}})
    def publish_neo4j(pid: int, body: Optional[schemas.PublishIn] = Body(None)):
        body = body or schemas.PublishIn()
        return neo4j_store.publish(pid, body.project_id, body.project_name)

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
