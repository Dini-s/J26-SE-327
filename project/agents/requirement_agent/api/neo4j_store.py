"""Publishing the clarified requirements of a workspace project to a Neo4j graph that Components 2-4 read.

The sqlite workspace stays C1's working store and is never read back from Neo4j. Publishing is one-way and idempotent: every node is MERGEd by its id and
its properties are set again, so publishing twice creates no duplicates. Nothing is hard-deleted: what is no longer in the workspace gets active = false.

Sections: (1) build the bundle (what would be sent) from sqlite, (2) its content hash (the "out of date" check), (3) Cypher built from neo4j_schema,
(4) the store: connection with short timeouts, status, schema, publish, and calm errors (503 with a code; no password, no address, no stack trace).
"""
import copy
import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import neo4j_config, service, vague
from . import neo4j_schema as S
from .db import dumps, loads, now
from .errors import ApiError

log = logging.getLogger("c1.neo4j")

CONNECT_TIMEOUT = 5.0  # seconds, for connecting and for acquiring a connection
BATCH = 500  # rows per UNWIND

MSG = {
    "neo4j_unconfigured": "Neo4j is not configured. Set NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD (or the C1_NEO4J_* names) in the environment or in the shared .env file, then try again.",
    "neo4j_driver_missing": "The Neo4j Python driver is not installed. Install it with: pip install neo4j (it is listed in project/requirements.txt).",
    "neo4j_auth_failed": "Neo4j refused the user name or password. Check NEO4J_USERNAME and NEO4J_PASSWORD.",
    "neo4j_unreachable": "Could not reach Neo4j within 5 seconds. Check that the database is running and that the address is right.",
    "neo4j_publish_failed": "Neo4j reported an error while publishing. The workspace is unchanged and it is safe to publish again; see the server log for the error type.",
}


def _fail(code, extra=""):
    return ApiError(503, code, MSG[code] + extra)


# ------------------------------------------------------------------------------------------------------------------- (1) the bundle
@dataclass
class SourceBundle:
    source_id: str
    props: dict
    requirements: list = field(default_factory=list)  # {"id", "props"}
    issues: list = field(default_factory=list)  # {"id", "req_id", "props"}
    drafts: list = field(default_factory=list)  # {"id", "req_id", "props"}


@dataclass
class Bundle:
    project_id: str
    project_props: dict
    sources: list
    duplicates: list  # {"id", "a", "b", "score"}

    def as_dict(self):
        return {
            "schema": S.SCHEMA_VERSION, "project_id": self.project_id, "project": self.project_props,
            "sources": [{"source_id": s.source_id, "props": s.props, "requirements": s.requirements, "issues": s.issues, "drafts": s.drafts} for s in self.sources],
            "duplicates": self.duplicates,
        }

    def digest(self):
        """sha256 of everything a publish would send (no publish time in it): changes exactly when the published graph would change."""
        return hashlib.sha256(json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()

    def counts(self):
        return {S.Label.PROJECT: 1, S.Label.SOURCE: len(self.sources), S.Label.REQUIREMENT: sum(len(s.requirements) for s in self.sources),
                S.Label.ISSUE: sum(len(s.issues) for s in self.sources), S.Label.DRAFT: sum(len(s.drafts) for s in self.sources),
                S.Rel.DUPLICATE_OF: len(self.duplicates)}


def source_graph_id(project_id, source_id):
    return f"{project_id}:src{source_id}"


def requirement_graph_id(project_id, source_id, rid):
    """req_id = <project_id>:src<workspace source id>:<workspace requirement id>, e.g. demo-project:src3:REQ-012 (docs/c1_neo4j_contract.md)."""
    return f"{source_graph_id(project_id, source_id)}:{rid}"


def _common(project_id):
    return {S.Common.PROJECT_ID: project_id, S.Common.PRODUCED_BY: S.PRODUCED_BY, S.Common.SCHEMA_VERSION: S.SCHEMA_VERSION}


def _file_sha256(db, s):
    """Hash of the uploaded file (stored when it was uploaded; older rows are filled in here, once). The file bytes themselves are never published."""
    if s.get("sha256"):
        return s["sha256"]
    try:
        digest = hashlib.sha256(Path(s["stored_path"]).read_bytes()).hexdigest()
    except OSError:
        digest = hashlib.sha256((s.get("extracted") or "").encode("utf-8")).hexdigest()  # the file is gone: hash what was extracted from it
    db.run("UPDATE sources SET sha256=? WHERE id=?", (digest, s["id"]))
    return digest


def _issues(req_id, project_id, r, block, text):
    """Part A ambiguity, rule-based vague terms, security cue words, the heuristic risk, and an AI request for clarification."""
    common = _common(project_id)

    def issue(kind, raised_by, detail, key=None):
        return {"id": f"{req_id}:{kind}:{key or raised_by}", "req_id": req_id,
                "props": dict(common, **{S.IssueP.TYPE: kind, S.IssueP.DETAIL: detail, S.IssueP.RAISED_BY: raised_by, S.IssueP.ACTIVE: True})}

    out = []
    if r["ambiguity_label"] == "defect":
        weak = loads(r["weak_words"], [])
        p = r["ambiguity_probability"]
        detail = "Part A ambiguity model: defect" + (f" (probability {p:.2f})" if p is not None else "") + (f"; weak words: {', '.join(weak)}" if weak else "")
        out.append(issue("ambiguity", "part_a", detail))
    for term in sorted({t["term"].lower() for t in vague.vague_term_spans(text)}):
        out.append(issue("vague", "rule", f"Vague term (rule-based word list): {term}", key=term))
    if r["is_security"]:
        cues = loads(r["security_cue_words"], [])
        out.append(issue("security", "part_a", "Security-related" + (f": keyword rule matched {', '.join(cues)}" if cues else "")))
    if r["risk_level"] and r["risk_level"] != "NONE":
        out.append(issue("risk", "rule", f"Risk {r['risk_level']} (score {r['risk_score']}), unvalidated heuristic"))
    if block["state"] == "needs_clarification":
        questions = block["clarification_questions"]
        out.append(issue("ambiguity", "ai", "AI asked for clarification" + (": " + " | ".join(questions) if questions else "")))
    return out


def build_bundle(db, pid, project_id, project_name):
    """Everything a publish sends, read from the workspace. Needs no Neo4j."""
    service.project_or_404(db, pid)
    export = {rec["uid"]: rec for rec in service.export_json(db, pid)["requirements"]}
    decisions = {d["uid"]: d for d in db.all("SELECT * FROM decisions WHERE uid IN (SELECT uid FROM requirements WHERE project_id=?)", (pid,))}
    gens = {g["uid"]: g for g in db.all("SELECT * FROM generation WHERE uid IN (SELECT uid FROM requirements WHERE project_id=?)", (pid,))}
    reqs = db.all("SELECT * FROM requirements WHERE project_id=? ORDER BY seq", (pid,))
    req_by_uid = {r["uid"]: r for r in reqs}
    common = _common(project_id)

    by_source = {}
    sources = []
    for s in db.all("SELECT * FROM sources WHERE project_id=? ORDER BY id", (pid,)):
        sb = SourceBundle(source_graph_id(project_id, s["id"]), dict(common, **{
            S.SourceP.FILENAME: s["filename"], S.SourceP.SOURCE_TYPE: s.get("source_type") or S.DEFAULT_SOURCE_TYPE, S.SourceP.SHA256: _file_sha256(db, s),
            S.SourceP.UPLOADED_AT: s["created_at"], S.SourceP.ACTIVE: True}))
        by_source[s["id"]] = (sb, s)
        sources.append(sb)

    duplicates = {}
    for r in reqs:
        if r["source_id"] not in by_source:
            continue  # cannot happen in a consistent workspace (deleting a source deletes its requirements)
        sb, s = by_source[r["source_id"]]
        req_id = requirement_graph_id(project_id, r["source_id"], r["rid"])
        dec = decisions.get(r["uid"])
        status = dec["decision"] if dec else "pending"
        final = dec["edited_text"] if dec and dec["decision"] == "edited" else r["text"]
        block = service.generation_block(gens.get(r["uid"]))

        rec = copy.deepcopy(export[r["uid"]])
        rec["source"].update(source_id=sb.source_id, source_type=sb.props[S.SourceP.SOURCE_TYPE])
        rec["status"] = status
        if rec["draft"] is not None:
            rec["draft"]["provenance"] = {"model": block["model"], "backend": block["backend"], "generated_on": block["generated_on"], "endpoint_host": block["endpoint_host"]}
        payload = {"schema_version": S.PAYLOAD_SCHEMA_VERSION, "project": {"id": project_id, "name": project_name}, "requirement": rec}

        sb.requirements.append({"id": req_id, "props": dict(common, **{
            S.RequirementP.TEXT: r["text"], S.RequirementP.KIND: (r["fr_nfr"] or "").upper() or None, S.RequirementP.STATUS: status, S.RequirementP.FINAL_TEXT: final,
            S.RequirementP.SECURITY_FLAG: bool(r["is_security"]), S.RequirementP.ACTIVE: True,
            S.RequirementP.PAYLOAD_JSON: json.dumps(payload, sort_keys=True, ensure_ascii=False)})})
        sb.issues.extend(_issues(req_id, project_id, r, block, r["text"]))
        if block["state"] in ("done", "needs_clarification"):
            sb.drafts.append({"id": f"{req_id}:draft", "req_id": req_id, "props": dict(common, **{
                S.DraftP.USER_STORY: block["user_story"], S.DraftP.TECHNICAL_TASK: block["technical_task"],
                S.DraftP.ACCEPTANCE_CRITERIA: [str(c) for c in block["acceptance_criteria"]], S.DraftP.RATIONALE: block["rationale"],
                S.DraftP.NEEDS_CLARIFICATION: block["state"] == "needs_clarification",
                S.DraftP.CLARIFICATION_QUESTIONS: [str(q) for q in block["clarification_questions"]],
                S.DraftP.GENERATED_BY: block["model"], S.DraftP.GENERATED_ON: block["generated_on"], S.DraftP.ENDPOINT_HOST: block["endpoint_host"],
                S.DraftP.ACTIVE: True})})
        for m in loads(r["duplicate_matches"], []):  # each pair is listed on both ends: keep one link, from the later requirement to the earlier one
            other = req_by_uid.get(m["uid"])
            if other is None or other["source_id"] not in by_source or other["seq"] >= r["seq"]:
                continue
            a, b = req_id, requirement_graph_id(project_id, other["source_id"], other["rid"])
            duplicates[f"{a}|{b}"] = {"id": f"{a}|{b}", "a": a, "b": b, "score": m.get("similarity")}
    return Bundle(project_id, dict(common, **{S.ProjectP.NAME: project_name}), sources, [duplicates[k] for k in sorted(duplicates)])


# ------------------------------------------------------------------------------------------------------------------- (3) Cypher
L, R, C = S.Label, S.Rel, S.Common

Q_PROJECT = (f"MERGE (p:{L.PROJECT} {{{S.ProjectP.ID}: $project_id}}) ON CREATE SET p += $props "
             f"ON MATCH SET p.{S.ProjectP.NAME} = coalesce(p.{S.ProjectP.NAME}, $name)")
Q_SOURCE = (f"MATCH (p:{L.PROJECT} {{{S.ProjectP.ID}: $project_id}}) MERGE (s:{L.SOURCE} {{{S.SourceP.ID}: $source_id}}) SET s += $props "
            f"MERGE (p)-[:{R.HAS_SOURCE}]->(s)")
Q_REQUIREMENTS = (f"UNWIND $rows AS row MATCH (s:{L.SOURCE} {{{S.SourceP.ID}: $source_id}}) MERGE (r:{L.REQUIREMENT} {{{S.RequirementP.ID}: row.id}}) "
                  f"SET r += row.props MERGE (s)-[:{R.CONTAINS}]->(r)")
Q_ISSUES = (f"UNWIND $rows AS row MATCH (r:{L.REQUIREMENT} {{{S.RequirementP.ID}: row.req_id}}) MERGE (i:{L.ISSUE} {{{S.IssueP.ID}: row.id}}) "
            f"SET i += row.props MERGE (r)-[:{R.HAS_ISSUE}]->(i)")
Q_DRAFTS = (f"UNWIND $rows AS row MATCH (r:{L.REQUIREMENT} {{{S.RequirementP.ID}: row.req_id}}) MERGE (d:{L.DRAFT} {{{S.DraftP.ID}: row.id}}) "
            f"SET d += row.props MERGE (r)-[:{R.HAS_DRAFT}]->(d)")
Q_DUPLICATES = (f"UNWIND $rows AS row MATCH (a:{L.REQUIREMENT} {{{S.RequirementP.ID}: row.a}}) MATCH (b:{L.REQUIREMENT} {{{S.RequirementP.ID}: row.b}}) "
                f"MERGE (a)-[d:{R.DUPLICATE_OF} {{{S.DuplicateP.ID}: row.id}}]->(b) SET d.{S.DuplicateP.SCORE} = row.score, d.{S.DuplicateP.ACTIVE} = true, d.{C.PROJECT_ID} = $project_id")


def _deactivate(label, id_prop):
    return (f"MATCH (n:{label} {{{C.PROJECT_ID}: $project_id}}) WHERE NOT n.{id_prop} IN $ids AND coalesce(n.active, true) = true "
            f"SET n.active = false RETURN count(n) AS n")


Q_DEACTIVATE = {
    L.SOURCE: _deactivate(L.SOURCE, S.SourceP.ID), L.REQUIREMENT: _deactivate(L.REQUIREMENT, S.RequirementP.ID),
    L.ISSUE: _deactivate(L.ISSUE, S.IssueP.ID), L.DRAFT: _deactivate(L.DRAFT, S.DraftP.ID),
    R.DUPLICATE_OF: (f"MATCH (:{L.REQUIREMENT} {{{C.PROJECT_ID}: $project_id}})-[d:{R.DUPLICATE_OF}]->() WHERE NOT d.{S.DuplicateP.ID} IN $ids "
                     f"AND coalesce(d.active, true) = true SET d.active = false RETURN count(d) AS n"),
}


def schema_statements():
    """Constraints and indexes, all `IF NOT EXISTS`: running them again changes nothing."""
    out = [f"CREATE CONSTRAINT c1_{label.lower()}_{prop} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE" for label, prop in S.UNIQUE_IDS]
    out += [f"CREATE INDEX c1_{label.lower()}_{prop} IF NOT EXISTS FOR (n:{label}) ON (n.{prop})" for label, prop in S.INDEXES]
    return out


def ensure_schema(session):
    for statement in schema_statements():
        session.run(statement).consume()


def _chunks(rows):
    for i in range(0, len(rows), BATCH):
        yield rows[i:i + BATCH]


def _with_stamp(rows, stamp):
    return [{"id": r["id"], "props": dict(r["props"], **{S.RequirementP.PUBLISHED_AT: stamp})} for r in rows]


def write_source(tx, bundle, src, stamp):
    """One transaction per source: the project node, the source, then its requirements, issues and drafts in UNWIND batches."""
    pid = bundle.project_id
    tx.run(Q_PROJECT, project_id=pid, props=bundle.project_props, name=bundle.project_props[S.ProjectP.NAME])
    tx.run(Q_SOURCE, project_id=pid, source_id=src.source_id, props=src.props)
    for rows in _chunks(src.requirements):
        tx.run(Q_REQUIREMENTS, source_id=src.source_id, rows=_with_stamp(rows, stamp))
    for rows in _chunks(src.issues):
        tx.run(Q_ISSUES, rows=rows)
    for rows in _chunks(src.drafts):
        tx.run(Q_DRAFTS, rows=rows)


def finish(tx, bundle):
    """Duplicate links (they can join two sources), then soft-deactivate everything of this project that is no longer in the workspace."""
    pid = bundle.project_id
    tx.run(Q_PROJECT, project_id=pid, props=bundle.project_props, name=bundle.project_props[S.ProjectP.NAME])
    for rows in _chunks(bundle.duplicates):
        tx.run(Q_DUPLICATES, project_id=pid, rows=rows)
    current = {
        L.SOURCE: [s.source_id for s in bundle.sources],
        L.REQUIREMENT: [r["id"] for s in bundle.sources for r in s.requirements],
        L.ISSUE: [i["id"] for s in bundle.sources for i in s.issues],
        L.DRAFT: [d["id"] for s in bundle.sources for d in s.drafts],
        R.DUPLICATE_OF: [d["id"] for d in bundle.duplicates],
    }
    out = {}
    for key, query in Q_DEACTIVATE.items():
        record = tx.run(query, project_id=pid, ids=current[key]).single()
        out[key] = int(record["n"]) if record is not None else 0
    return out


# ------------------------------------------------------------------------------------------------------------------- (4) the store
def translate(exc):
    """Map a driver error to a calm ApiError. Only the error TYPE is logged and nothing of the exception text is sent to the client."""
    if isinstance(exc, ApiError):
        return exc
    name, code = type(exc).__name__, str(getattr(exc, "code", "") or "")
    log.warning("neo4j call failed: %s %s", name, code)
    if name in ("AuthError", "AuthConfigurationError") or code.startswith("Neo.ClientError.Security"):
        return _fail("neo4j_auth_failed")
    if isinstance(exc, (OSError, TimeoutError, ValueError)) or name in ("ServiceUnavailable", "SessionExpired", "ConfigurationError", "DriverError", "ConnectionAcquisitionTimeoutError"):
        return _fail("neo4j_unreachable")
    return _fail("neo4j_publish_failed")


def server_version(driver):
    try:
        agent = str(getattr(driver.get_server_info(), "agent", "") or "")
    except Exception:  # noqa: BLE001 - the version is a nice-to-have
        return None
    return agent.split("/", 1)[-1] or None


class Neo4jStore:
    def __init__(self, db, config_loader=None, project_loader=None, driver_factory=None):
        self.db = db
        self._load_config = config_loader or neo4j_config.load_config
        self._load_project = project_loader or neo4j_config.project_stub
        self._driver_factory = driver_factory
        self._publishing = threading.Lock()

    # -- helpers
    def config(self):
        return self._load_config()

    def project(self, pid, project_id=None, name=None):
        """(platform project id, name). The stub id uses the stub name; another id keeps the name it was last published with (or an explicit one)."""
        stub_id, stub_name = self._load_project()
        gp = project_id or stub_id
        if name:
            return gp, name
        if gp == stub_id:
            return gp, stub_name
        last = self.last_publish(pid, gp)
        return gp, (last["graph_project_name"] if last and last["graph_project_name"] else gp)

    def open(self, cfg):
        """A verified driver, or an ApiError (503) with a plain message."""
        if not cfg.configured:
            raise _fail("neo4j_unconfigured")
        factory = self._driver_factory
        if factory is None:
            try:
                import neo4j
            except ImportError:
                raise _fail("neo4j_driver_missing") from None

            def factory(c):
                return neo4j.GraphDatabase.driver(c.uri, auth=(c.user, c.password), connection_timeout=CONNECT_TIMEOUT,
                                                  connection_acquisition_timeout=CONNECT_TIMEOUT, max_transaction_retry_time=CONNECT_TIMEOUT)
        driver = None
        try:
            driver = factory(cfg)
            driver.verify_connectivity()
            return driver
        except Exception as exc:  # noqa: BLE001
            if driver is not None:
                try:
                    driver.close()
                except Exception:  # noqa: BLE001
                    pass
            raise translate(exc) from None

    def last_publish(self, pid, graph_project_id):
        row = self.db.one("SELECT * FROM publish_log WHERE project_id=? AND graph_project_id=? ORDER BY id DESC LIMIT 1", (pid, graph_project_id))
        return row

    # -- status
    def status(self, pid, project_id=None):
        service.project_or_404(self.db, pid)
        gp, gname = self.project(pid, project_id)
        cfg = self.config()
        last = self.last_publish(pid, gp)
        digest = build_bundle(self.db, pid, gp, gname).digest()
        out = {"configured": cfg.configured, "reachable": False, "project_id": gp, "host": cfg.host or None, "database": cfg.database if cfg.configured else None,
               "server_version": None, "last_published_at": last["published_at"] if last else None,
               "last_counts": loads(last["counts"], None) if last else None, "out_of_date": last is None or last["content_hash"] != digest,
               "error": None, "message": None}
        try:
            driver = self.open(cfg)
        except ApiError as exc:
            out.update(error=exc.code, message=exc.message)
            return out
        try:
            out.update(reachable=True, server_version=server_version(driver))
        finally:
            driver.close()
        return out

    def check(self):
        """For scripts/check_c1_neo4j.py: connect, read the version, run RETURN 1, create the constraints. Publishes nothing."""
        cfg = self.config()
        driver = self.open(cfg)
        try:
            with driver.session(database=cfg.database) as session:
                one = session.run("RETURN 1 AS one").single()["one"]
                ensure_schema(session)
            return {"host": cfg.host, "database": cfg.database, "server_version": server_version(driver), "return_one": one, "statements": len(schema_statements())}
        except Exception as exc:  # noqa: BLE001
            raise translate(exc) from None
        finally:
            driver.close()

    # -- publish
    def publish(self, pid, project_id=None, project_name=None):
        service.project_or_404(self.db, pid)
        gp, gname = self.project(pid, project_id, project_name)
        cfg = self.config()
        if not cfg.configured:
            raise _fail("neo4j_unconfigured")
        if not self._publishing.acquire(blocking=False):
            raise ApiError(409, "publish_in_progress", "A publish is already running; wait for it to finish.")
        try:
            bundle = build_bundle(self.db, pid, gp, gname)
            digest = bundle.digest()
            driver = self.open(cfg)
            started, stamp = time.monotonic(), now()
            try:
                with driver.session(database=cfg.database) as session:
                    ensure_schema(session)
                    for src in bundle.sources:
                        session.execute_write(write_source, bundle, src, stamp)
                    deactivated = session.execute_write(finish, bundle)
            except Exception as exc:  # noqa: BLE001
                raise translate(exc) from None
            finally:
                driver.close()
            seconds = round(time.monotonic() - started, 3)
            counts = bundle.counts()
            self.db.run("INSERT INTO publish_log (project_id, graph_project_id, graph_project_name, content_hash, published_at, seconds, counts) VALUES (?,?,?,?,?,?,?)",
                        (pid, gp, gname, digest, stamp, seconds, dumps(counts)))
            return {"project_id": gp, "published_at": stamp, "seconds": seconds, "counts": counts, "deactivated": deactivated, "content_hash": digest}
        finally:
            self._publishing.release()
