"""Queries and serialisation behind the endpoints (no web code here)."""
import csv
import io

from .. import generation as gen
from . import analysis, planning, risk, suggest, vague
from .db import DEFAULT_PROJECT_KEY, dumps, loads, now, unique_key
from .errors import ApiError
from .gen_worker import failure_reason
from .explain import build_explanation

FILTER_TYPES = ("all", "ambiguity", "conflict", "duplicate", "security")
DECISIONS = ("accepted", "edited", "rejected")
SCHEMA_VERSION = "c1.clarified_requirements.v1"
HEURISTIC_NOTE = ("Ambiguity and classification labels, risk levels and candidate conflicts are automatic hints from baseline models and an unvalidated heuristic; "
                  "generated drafts are model output. Only the decision field records a human choice.")


# ------------------------------------------------------------------------------------------------------------------- projects
def project_or_404(db, pid):
    p = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    if not p:
        raise ApiError(404, "project_not_found", f"Project {pid} does not exist.")
    return p


def decision_counts(db, pid):
    """Requirements of the project by decision status; `pending` = no decision yet."""
    rows = db.all("SELECT d.decision s, COUNT(*) n FROM requirements r LEFT JOIN decisions d ON d.uid=r.uid WHERE r.project_id=? GROUP BY d.decision", (pid,))
    c = {r["s"] or "pending": r["n"] for r in rows}
    return {k: c.get(k, 0) for k in ("accepted", "edited", "rejected", "pending")}


def last_analysis_at(db, pid):
    row = db.one("SELECT updated_at FROM jobs WHERE project_id=? AND part_a_done=1 ORDER BY updated_at DESC LIMIT 1", (pid,))
    return row["updated_at"] if row else None


def project_out(db, p, publish=None):
    """`publish` = {"last_published_at", "out_of_date"} from the graph store (it needs the bundle hash, which lives there)."""
    publish = publish or {}
    return {"id": p["id"], "project_key": p["project_key"], "name": p["name"], "archived": bool(p["archived"]), "created_at": p["created_at"],
            "sources": db.one("SELECT COUNT(*) n FROM sources WHERE project_id=?", (p["id"],))["n"],
            "requirements": db.one("SELECT COUNT(*) n FROM requirements WHERE project_id=?", (p["id"],))["n"],
            "decisions": decision_counts(db, p["id"]), "last_analysis_at": last_analysis_at(db, p["id"]),
            "last_published_at": publish.get("last_published_at"), "out_of_date": publish.get("out_of_date", True)}


def _clean_name(name):
    name = " ".join((name or "").split())
    if not 2 <= len(name) <= 80:
        raise ApiError(422, "validation_error", "name: use 2 to 80 characters.")
    return name


def _check_name_free(db, name, except_id=None):
    for other in db.all("SELECT id, name FROM projects WHERE archived=0"):
        if other["id"] != except_id and other["name"].casefold() == name.casefold():
            raise ApiError(409, "project_name_taken", f"A project named '{other['name']}' already exists. Choose another name.")


def create_project(db, name):
    name = _clean_name(name)
    _check_name_free(db, name)
    key = unique_key({r["project_key"] for r in db.all("SELECT project_key FROM projects")}, name)
    pid = db.run("INSERT INTO projects (name, created_at, project_key, archived) VALUES (?,?,?,0)", (name, now(), key))
    db.ensure_planning(pid)  # every project starts with "Sprint 1" as its current sprint
    return project_or_404(db, pid)


def rename_project(db, pid, name):
    p = project_or_404(db, pid)
    name = _clean_name(name)
    if not p["archived"]:
        _check_name_free(db, name, pid)
    db.run("UPDATE projects SET name=? WHERE id=?", (name, pid))  # the key never changes
    return project_or_404(db, pid)


def set_archived(db, pid, archived):
    p = project_or_404(db, pid)
    if not archived and p["archived"]:
        _check_name_free(db, p["name"], pid)  # another active project may have taken the name meanwhile
    db.run("UPDATE projects SET archived=? WHERE id=?", (1 if archived else 0, pid))
    return project_or_404(db, pid)


def project_key(db, p):
    """The immutable key (also the Neo4j project id). Rows made without one (older code paths) get it here, once."""
    if p.get("project_key"):
        return p["project_key"]
    key = unique_key({r["project_key"] for r in db.all("SELECT project_key FROM projects") if r["project_key"]},
                     DEFAULT_PROJECT_KEY if p["id"] == 1 else p["name"], f"project-{p['id']}")
    db.run("UPDATE projects SET project_key=? WHERE id=? AND project_key IS NULL", (key, p["id"]))
    return db.one("SELECT project_key FROM projects WHERE id=?", (p["id"],))["project_key"]


def with_key(db, p):
    return dict(p, project_key=project_key(db, p))


def source_stats(db, pid):
    """Per-document numbers of a project in three queries: ({sid: requirements, ambiguities}, {sid: {draft state: n}}, {sid: [{sprint_id, count}]})."""
    reqs = {r["sid"]: r for r in db.all("SELECT source_id sid, COUNT(*) n, SUM(ambiguity_label='defect') amb FROM requirements WHERE project_id=? GROUP BY source_id", (pid,))}
    drafts = {}
    for r in db.all("SELECT r.source_id sid, g.state st, COUNT(*) n FROM requirements r JOIN generation g ON g.uid=r.uid WHERE r.project_id=? GROUP BY r.source_id, g.state", (pid,)):
        drafts.setdefault(r["sid"], {})[r["st"]] = r["n"]
    sprints = {}
    for r in db.all(f"SELECT r.source_id sid, {planning.EFFECTIVE_SPRINT} spr, COUNT(*) n FROM requirements r JOIN sources s ON s.id=r.source_id "
                    f"WHERE r.project_id=? GROUP BY r.source_id, spr ORDER BY spr", (pid,)):
        sprints.setdefault(r["sid"], []).append({"sprint_id": r["spr"], "count": r["n"]})
    return reqs, drafts, sprints


def source_out(s, stats=None):
    reqs, drafts, sprints = stats or ({}, {}, {})
    n, d = reqs.get(s["id"]) or {"n": 0, "amb": 0}, drafts.get(s["id"], {})
    return {"id": s["id"], "filename": s["filename"], "ext": s["ext"], "size_bytes": s["size_bytes"], "pages": s["pages"],
            "warnings": loads(s["warnings"], []), "created_at": s["created_at"], "uploaded_at": s["created_at"], "source_type": s.get("source_type") or "srs",
            "default_sprint_id": s.get("default_sprint_id"), "analysis_state": s.get("analysis_state") or "not_analyzed", "analyzed_at": s.get("analyzed_at"),
            "requirements": n["n"], "ambiguities": int(n["amb"] or 0),
            "drafts": {"ready": d.get("done", 0), "needs_clarification": d.get("needs_clarification", 0), "failed": d.get("failed", 0)},
            "sprints": sprints.get(s["id"], [])}


def sources_out(db, pid, rows=None):
    """The documents of a project (all, or `rows`) with their stats."""
    stats = source_stats(db, pid)
    rows = db.all("SELECT * FROM sources WHERE project_id=? ORDER BY id", (pid,)) if rows is None else rows
    return [source_out(s, stats) for s in rows]


# ------------------------------------------------------------------------------------------------------------------- generation block
def generation_block(g, text=None):
    base = {"state": "not_requested", "message": "", "status": None, "user_story": "", "technical_task": "", "acceptance_criteria": [], "rationale": "",
            "clarification_questions": [], "attempts": 0, "manual_review": False, "raw_output": "", "updated_at": None,
            "backend": "", "model": "", "numbers_not_in_source": [], "generated_from": "",
            "generated_on": "", "endpoint_host": None, "failure_reason": None}
    if not g:
        return base
    res = loads(g["result"], None) or {}
    base.update(state=g["state"], message=g["message"], attempts=g["attempts"], manual_review=bool(g["manual_review"]), updated_at=g["updated_at"],
                failure_reason=failure_reason(g["message"]) if g["state"] == "failed" else None)
    if res:
        base.update(status=res.get("status"), user_story=res.get("user_story", ""), technical_task=res.get("technical_task", ""),
                    acceptance_criteria=res.get("acceptance_criteria", []), rationale=res.get("rationale", ""),
                    clarification_questions=res.get("clarification_questions", []), raw_output=res.get("raw_output", ""),
                    backend=res.get("backend", ""), model=res.get("model", ""), generated_from=res.get("generated_from", "original"),
                    generated_on=res.get("generated_on", "device"), endpoint_host=res.get("endpoint_host"))
        if text is not None and g["state"] in ("done", "needs_clarification"):
            base["numbers_not_in_source"] = gen.numbers_not_in_source(res.get("source_text") or text, res)  # the text the model really saw
    return base


def generation_counts(db, pid):
    rows = db.all("SELECT g.state s, COUNT(*) n FROM requirements r LEFT JOIN generation g ON g.uid=r.uid WHERE r.project_id=? GROUP BY g.state", (pid,))
    c = {(r["s"] or "not_requested"): r["n"] for r in rows}
    total = sum(c.values())
    done = c.get("done", 0) + c.get("needs_clarification", 0) + c.get("manual_review", 0)
    return {"total": total, "done": done, "failed": c.get("failed", 0), "queued": c.get("queued", 0) + c.get("running", 0),
            "running": c.get("running", 0)}


# ------------------------------------------------------------------------------------------------------------------- summary
def _task_drafts(rows, manager):
    c = {}
    for r in rows:
        c[r["gstate"] or "not_requested"] = c.get(r["gstate"] or "not_requested", 0) + 1
    queued, running = c.get("queued", 0), c.get("running", 0)
    eta, samples = manager.eta(queued + running) if manager else (None, 0)
    return {"generated": c.get("done", 0), "total": len(rows), "needs_clarification": c.get("needs_clarification", 0),
            "manual_review": c.get("manual_review", 0), "failed": c.get("failed", 0), "not_generated": c.get("not_requested", 0),
            "in_progress": queued + running, "queued": queued, "running": running, "paused": bool(manager and manager.paused),
            "paused_reason": manager.paused_reason if manager else None,
            "eta_seconds": eta, "latency_samples": samples}


def summary(db, pid, manager=None):
    project_or_404(db, pid)
    rows = db.all("SELECT r.uid, r.risk_level, r.ambiguity_label, r.is_security, r.duplicate_matches, r.conflict_matches, r.duplicate_group, r.findings, "
                  "g.state gstate, d.decision FROM requirements r LEFT JOIN generation g ON g.uid=r.uid LEFT JOIN decisions d ON d.uid=r.uid "
                  "WHERE r.project_id=?", (pid,))
    amb = [r for r in rows if r["ambiguity_label"] == "defect"]
    dup_ends = sum(len(loads(r["duplicate_matches"], [])) for r in rows)
    levels = {lvl: sum(1 for r in rows if r["risk_level"] == lvl) for lvl in risk.LEVELS}
    return {
        "requirements": len(rows),
        "ambiguities": {"count": len(amb), "high_risk": sum(1 for r in amb if r["risk_level"] == "HIGH"),
                        "asked_by_ai": sum(1 for r in rows if r["ambiguity_label"] != "defect" and r["gstate"] == "needs_clarification")},
        "conflicts": db.one("SELECT COUNT(*) n FROM conflicts WHERE project_id=?", (pid,))["n"],
        "duplicates": dup_ends // 2,
        "duplicate_groups": len({r["duplicate_group"] for r in rows if r["duplicate_group"]}),
        "security": sum(1 for r in rows if r["is_security"]),
        "risk_counts": levels,
        "task_drafts": _task_drafts(rows, manager),
        "open_findings": sum(len(loads(r["findings"], [])) for r in rows if not r["decision"]),
        "decided": sum(1 for r in rows if r["decision"]),
    }


# ------------------------------------------------------------------------------------------------------------------- overview
def _percent(done, total):
    return round(100.0 * done / total, 1) if total else 0.0


def planning_overview(db, pid):
    """current_sprint, current_phase, by_sprint and by_phase. "pending" is what still needs a decision (needs review)."""
    sprints = planning.list_sprints(db, pid)
    counts = planning.decision_counts_by_sprint(db, pid)
    zero = {"total": 0, "accepted": 0, "edited": 0, "rejected": 0, "pending": 0}
    by_sprint = [dict(counts.get(s["id"], zero), sprint_id=s["id"], name=s["name"], phase_id=s["phase_id"], is_current=s["is_current"]) for s in sprints]
    by_phase = []
    for ph in planning.list_phases(db, pid) + [None]:
        members = [b for b in by_sprint if b["phase_id"] == (ph["id"] if ph else None)]
        if ph is None and not members:
            continue
        agg = {k: sum(b[k] for b in members) for k in zero}
        by_phase.append(dict(agg, phase_id=ph["id"] if ph else None, name=ph["name"] if ph else None, sprints=len(members)))
    current = next((s for s in sprints if s["is_current"]), None)
    cur_sprint = cur_phase = None
    if current:
        c = counts.get(current["id"], zero)
        decided = c["total"] - c["pending"]
        cur_sprint = {"id": current["id"], "name": current["name"], "phase_id": current["phase_id"], "start_date": current["start_date"], "end_date": current["end_date"],
                      "goal": current["goal"], "requirements": c["total"], "pending": c["pending"], "decided": decided, "percent_decided": _percent(decided, c["total"])}
        ph = next((x for x in by_phase if x["phase_id"] is not None and x["phase_id"] == current["phase_id"]), None)
        if ph:
            cur_phase = {"id": ph["phase_id"], "name": ph["name"], "sprints": ph["sprints"], "requirements": ph["total"], "pending": ph["pending"],
                         "decided": ph["total"] - ph["pending"], "percent_decided": _percent(ph["total"] - ph["pending"], ph["total"])}
    return cur_sprint, cur_phase, by_sprint, by_phase


def pipeline(docs, total, decided, td, sync):
    """The five stages of the project and the numbers behind each. `docs` = the analysis state of every document, `total` = requirements, `decided` = requirements with a
    decision, `td` = the task-draft counts, `sync` = the auto-sync status."""
    n = len(docs)
    analysed, analysing, failed = (sum(1 for d in docs if d == x) for x in ("analyzed", "analyzing", "failed"))
    drafts = {"ready": td["generated"], "needs_clarification": td["needs_clarification"], "failed": td["failed"], "waiting": td["in_progress"]}
    written = drafts["ready"] + drafts["needs_clarification"]
    if analysing:
        identify = analyse = "active"
    else:
        identify = "done" if total else ("failed" if failed else "waiting")
        analyse = "failed" if failed else ("done" if n and analysed == n else "waiting")
    if drafts["waiting"]:
        improve = "active"
    elif drafts["failed"]:
        improve = "failed" if written == 0 else "attention"  # `failed` only when every draft failed; otherwise the rest still works and the failed ones can be retried
    elif total and decided == total:
        improve = "done"
    else:
        improve = "active" if decided or written else "waiting"
    share = {"synced": "done", "syncing": "active", "unreachable": "failed"}.get(sync["state"], "waiting")
    if not total and share == "done":
        share = "waiting"
    return {"collect": {"state": "done" if n else "waiting", "documents": n},
            "identify": {"state": identify, "documents": n, "requirements": total},
            "analyse": {"state": analyse, "analysed": analysed, "total": n, "failed": failed},
            "improve": {"state": improve, "requirements": total, "decided": decided, "drafts_written": written, "drafts": drafts},
            "share": {"state": share, "sync_state": sync["state"], "last_synced_at": sync["last_synced_at"]}}


def overview(db, pid, manager, engine, graph, sync=None):
    """Everything a project dashboard needs, in one call. The graph part never fails the call. `sync` = the auto-sync status of the project."""
    p = project_or_404(db, pid)
    db.ensure_planning(pid)
    s = summary(db, pid, manager)
    td = s["task_drafts"]
    dec = decision_counts(db, pid)
    decided = dec["accepted"] + dec["edited"] + dec["rejected"]
    total = s["requirements"]
    srcs = db.all("SELECT size_bytes, source_type, created_at FROM sources WHERE project_id=?", (pid,))
    by_type = {}
    for x in srcs:
        by_type[x["source_type"] or "srs"] = by_type.get(x["source_type"] or "srs", 0) + 1
    try:
        g = graph.status(pid)
    except Exception:  # noqa: BLE001 - the dashboard must load even when the graph part breaks
        g = {"configured": False, "reachable": False, "project_id": project_key(db, p), "last_published_at": None, "out_of_date": True,
             "error": "neo4j_status_failed", "message": "The graph status could not be read."}
    sync = sync or {"state": "pending", "enabled": False, "last_synced_at": None, "counts": None, "next_attempt_at": None, "error": None}
    docs = [x["a"] for x in db.all("SELECT analysis_state a FROM sources WHERE project_id=?", (pid,))]
    state = "paused" if td["paused"] else ("running" if td["in_progress"] else "idle")
    cur_sprint, cur_phase, by_sprint, by_phase = planning_overview(db, pid)
    return {
        "project": {"id": p["id"], "project_key": project_key(db, p), "name": p["name"], "archived": bool(p["archived"])},
        "counts": {"requirements": total,
                   "ambiguities": {"total": s["ambiguities"]["count"] + s["ambiguities"]["asked_by_ai"], "detected": s["ambiguities"]["count"],
                                   "asked_by_ai": s["ambiguities"]["asked_by_ai"]},
                   "conflicts": s["conflicts"], "duplicates": s["duplicates"],
                   "drafts": {"total": td["total"], "done": td["generated"], "ready": td["generated"], "needs_clarification": td["needs_clarification"], "waiting": td["in_progress"],
                              "failed": td["failed"], "not_generated": td["not_generated"], "manual_review": td["manual_review"]}},
        "decisions": dict(dec, decided=decided, percent_decided=round(100.0 * decided / total, 1) if total else 0.0),
        "sources": {"count": len(srcs), "by_type": by_type, "total_size_bytes": sum(x["size_bytes"] for x in srcs),
                    "latest_upload_at": max((x["created_at"] for x in srcs), default=None)},
        "last_analysis_at": last_analysis_at(db, pid),
        "generation": {"state": state, "target": engine.target(), "in_progress": td["in_progress"], "paused_reason": td["paused_reason"], "eta_seconds": td["eta_seconds"]},
        "neo4j": {k: g.get(k) for k in ("configured", "reachable", "project_id", "last_published_at", "out_of_date", "error", "message")},
        "current_sprint": cur_sprint, "current_phase": cur_phase, "by_sprint": by_sprint, "by_phase": by_phase,
        "findings_by_type": {"ambiguity": s["ambiguities"]["count"], "conflict": s["conflicts"], "duplicate": s["duplicates"], "security": s["security"]},
        "latest_uploads": sources_out(db, pid, db.all("SELECT * FROM sources WHERE project_id=? ORDER BY created_at DESC, id DESC LIMIT 5", (pid,))),
        "analysis": {"ready": sum(1 for a in docs if a == "analyzed"), "total": len(srcs)},
        "sync": sync,
        "pipeline": pipeline(docs, total, decided, td, sync),
    }


# ------------------------------------------------------------------------------------------------------------------- list
def _questions(gresult):
    """How many follow-up questions the draft step asked (0 while it has not been asked)."""
    res = loads(gresult, None) if gresult else None
    return len((res or {}).get("clarification_questions") or [])


def _order(db, pid):
    """{uid: (position, display id)} of the project's requirements, to tell which item of a duplicate pair comes first."""
    return {x["uid"]: (x["seq"], x["rid"]) for x in db.all("SELECT uid, seq, rid FROM requirements WHERE project_id=?", (pid,))}


def suggestion(r, gresult, order):
    """The rule-based suggested decision of one requirement row (computed on every call; never stored, exported or published)."""
    partners = sorted(order[m["uid"]] for m in loads(r["duplicate_matches"], []) if m["uid"] in order)
    return suggest.suggest(r, [rid for seq, rid in partners if seq < r["seq"]], [rid for seq, rid in partners if seq > r["seq"]], _questions(gresult))


def jira_ref(key, kind, status, url):
    return {"key": key, "type": kind or "", "status": status or "", "url": url or ""} if key else None


def _row(r, order):
    return {"sprint_id": r["sprint_eff"], "uid": r["uid"], "id": r["rid"], "text": r["text"], "source_file": r["source_file"], "page": r["page"], "paragraph": r["paragraph"],
            "fr_nfr": r["fr_nfr"], "risk_level": r["risk_level"], "risk_score": r["risk_score"],
            "flags": {"ambiguity": r["ambiguity_label"] == "defect", "conflict": r["conflict_matches"] != "[]",
                      "duplicate": r["duplicate_matches"] != "[]", "security": bool(r["is_security"])},
            "jira": jira_ref(r.get("jkey"), r.get("jtype"), r.get("jstatus"), r.get("jurl")),
            "generation_state": r["gstate"] or "not_requested", "failure_reason": failure_reason(r["gmessage"]) if r["gstate"] == "failed" else None, "decision": r["decision"],
            "suggestion": suggestion(r, r["gresult"], order)}


EFF = "COALESCE(r.sprint_id, (SELECT default_sprint_id FROM sources WHERE id=r.source_id))"  # the effective sprint of a requirement row `r`


def list_requirements(db, pid, risk_filter=None, type_filter="all", q=None, limit=50, offset=0, sprint_id=None):
    project_or_404(db, pid)
    if risk_filter:
        risk_filter = risk_filter.upper()
        if risk_filter not in risk.LEVELS:
            raise ApiError(400, "invalid_parameter", f"risk must be one of {list(risk.LEVELS)}.")
    type_filter = (type_filter or "all").lower()
    if type_filter not in FILTER_TYPES:
        raise ApiError(400, "invalid_parameter", f"type must be one of {list(FILTER_TYPES)}.")
    if not 1 <= limit <= 500 or offset < 0:
        raise ApiError(400, "invalid_parameter", "limit must be 1-500 and offset >= 0.")
    where, args = ["r.project_id=?"], [pid]
    if risk_filter:
        where.append("r.risk_level=?")
        args.append(risk_filter)
    where.append({"all": "1=1", "ambiguity": "r.ambiguity_label='defect'", "conflict": "r.conflict_matches<>'[]'",
                  "duplicate": "r.duplicate_matches<>'[]'", "security": "r.is_security=1"}[type_filter])
    if sprint_id is not None:
        where.append(f"{EFF}=?")
        args.append(sprint_id)
    if q and q.strip():
        like = "%" + q.strip().lower().replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(LOWER(r.text) LIKE ? ESCAPE '\\' OR LOWER(r.rid) LIKE ? ESCAPE '\\' OR LOWER(r.source_file) LIKE ? ESCAPE '\\')")
        args += [like, like, like]
    clause = " AND ".join(where)
    total = db.one(f"SELECT COUNT(*) n FROM requirements r WHERE {clause}", args)["n"]
    order = _order(db, pid)
    rows = db.all(f"SELECT r.*, {EFF} sprint_eff, g.state gstate, g.message gmessage, g.result gresult, d.decision, ji.issue_key jkey, ji.issue_type jtype, ji.status jstatus, ji.url jurl FROM requirements r LEFT JOIN generation g ON g.uid=r.uid LEFT JOIN decisions d ON d.uid=r.uid "
                  f"LEFT JOIN jira_issues ji ON ji.project_id=r.project_id AND ji.source_id=r.source_id AND ji.issue_key=r.clause_label "
                  f"WHERE {clause} ORDER BY r.seq LIMIT ? OFFSET ?", args + [limit, offset])
    return {"total": total, "limit": limit, "offset": offset, "items": [_row(r, order) for r in rows]}


# ------------------------------------------------------------------------------------------------------------------- one requirement
def resolve_uid(db, rid):
    """Accept the unique id (`p1-REQ-001`) or, when only one project has it, the display id (`REQ-001`)."""
    row = db.one("SELECT uid FROM requirements WHERE uid=?", (rid,))
    if row:
        return row["uid"]
    rows = db.all("SELECT uid FROM requirements WHERE rid=?", (rid,))
    if len(rows) == 1:
        return rows[0]["uid"]
    if len(rows) > 1:
        raise ApiError(409, "ambiguous_requirement_id", f"{rid} exists in several projects; use one of: " + ", ".join(r["uid"] for r in rows))
    raise ApiError(404, "requirement_not_found", f"Requirement {rid} does not exist.")


def decision_block(db, uid):
    """The one current decision of a requirement, or None while it is pending."""
    d = db.one("SELECT * FROM decisions WHERE uid=?", (uid,))
    return {"decision": d["decision"], "edited_text": d["edited_text"], "note": d["note"], "updated_at": d["updated_at"]} if d else None


def legacy_history(current):
    """Deprecated `history` / `decision_history` fields: only the current decision (older ones live in the internal audit table and are not returned)."""
    return [{"decision": current["decision"], "edited_text": current["edited_text"], "note": current["note"], "created_at": current["updated_at"]}] if current else []


def _partners(db, matches):
    out = []
    for m in matches:
        p = db.one("SELECT text, source_file, page, paragraph FROM requirements WHERE uid=?", (m["uid"],)) or {}
        out.append(dict(m, text=p.get("text", ""), source_file=p.get("source_file", ""), page=p.get("page"), paragraph=p.get("paragraph")))
    return out


def detail(db, rid):
    uid = resolve_uid(db, rid)
    r = db.one("SELECT * FROM requirements WHERE uid=?", (uid,))
    weak = loads(r["weak_words"], [])
    rec = {"fr_nfr": r["fr_nfr"], "nfr_probability": r["nfr_probability"], "findings": loads(r["findings"], []),
           "conflict_matches": loads(r["conflict_matches"], []), "risk_level": r["risk_level"], "risk_score": r["risk_score"]}
    current = decision_block(db, uid)
    g = db.one("SELECT * FROM generation WHERE uid=?", (uid,))
    ji = db.one("SELECT issue_key, issue_type, status, url FROM jira_issues WHERE project_id=? AND source_id=? AND issue_key=?", (r["project_id"], r["source_id"], r["clause_label"] or ""))
    return {
        "jira": jira_ref(*(ji[k] for k in ("issue_key", "issue_type", "status", "url"))) if ji else None,
        "sprint_id": db.one(f"SELECT {EFF} s FROM requirements r WHERE r.uid=?", (uid,))["s"],
        "uid": uid, "id": r["rid"], "project_id": r["project_id"], "text": r["text"], "original_text": r["text"],
        "source": {"file": r["source_file"], "page": r["page"], "paragraph": r["paragraph"], "position": r["position"], "clause_label": r["clause_label"]},
        "classification": {"fr_nfr": r["fr_nfr"], "nfr_probability": r["nfr_probability"]},
        "ambiguity": {"label": r["ambiguity_label"], "probability_defect": r["ambiguity_probability"], "weak_words": weak,
                      "weak_word_spans": analysis.weak_word_spans(r["text"], weak)},
        "security": {"is_security": bool(r["is_security"]), "cue_words": loads(r["security_cue_words"], [])},
        "duplicates": _partners(db, loads(r["duplicate_matches"], [])), "duplicate_group": r["duplicate_group"],
        "conflicts": _partners(db, rec["conflict_matches"]),
        "risk": {"level": r["risk_level"], "score": r["risk_score"], "note": "unvalidated heuristic, not a trained model"},
        "findings": rec["findings"], "explanation": build_explanation(rec),
        "vague_terms": vague.vague_term_spans(r["text"]),
        "generation": generation_block(g, r["text"]), "suggestion": suggestion(r, g["result"] if g else None, _order(db, r["project_id"])),
        "decision": current, "decision_history": legacy_history(current),
    }


def get_decision(db, rid):
    uid = resolve_uid(db, rid)
    current = decision_block(db, uid)
    if not current:
        return {"uid": uid, "decision": "pending", "edited_text": None, "note": None, "updated_at": None}
    return dict(current, uid=uid)


def _audit(con, uid, old, reason):
    """Copy a decision that is being replaced or removed to the internal audit table (append-only; never returned by any endpoint)."""
    con.execute("INSERT INTO decision_audit (uid, decision, edited_text, note, decided_at, superseded_at, reason) VALUES (?,?,?,?,?,?,?)",
                (uid, old["decision"], old["edited_text"], old["note"], old["updated_at"], now(), reason))


def set_decision(db, rid, decision, edited_text, note):
    """Upsert: a requirement has ONE current decision. The decision it replaces goes to the audit table."""
    uid = resolve_uid(db, rid)
    if decision not in DECISIONS:
        raise ApiError(400, "invalid_decision", f"decision must be one of {list(DECISIONS)}.")
    if decision == "edited" and not (edited_text and edited_text.strip()):
        raise ApiError(400, "edited_text_required", "An edited decision needs edited_text.")
    if decision == "edited":
        original = db.one("SELECT text FROM requirements WHERE uid=?", (uid,))["text"]
        if " ".join(edited_text.split()) == " ".join(original.split()):
            raise ApiError(400, "edited_text_unchanged", "The edited text is the same as the original. Change the text, or accept the requirement as it is.")
    edited = edited_text.strip() if decision == "edited" else None
    with db.connect() as con:
        old = con.execute("SELECT * FROM decisions WHERE uid=?", (uid,)).fetchone()
        if old is not None:
            _audit(con, uid, old, "replaced")
        con.execute("INSERT INTO decisions (uid, decision, edited_text, note, updated_at) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(uid) DO UPDATE SET decision=excluded.decision, edited_text=excluded.edited_text, note=excluded.note, updated_at=excluded.updated_at",
                    (uid, decision, edited, note, now()))
    current = decision_block(db, uid)
    return dict(current, uid=uid, history=legacy_history(current))


def clear_decision(db, rid):
    """Back to pending. Removing a requirement that has no decision is not an error (the result is the same)."""
    uid = resolve_uid(db, rid)
    with db.connect() as con:
        old = con.execute("SELECT * FROM decisions WHERE uid=?", (uid,)).fetchone()
        if old is not None:
            _audit(con, uid, old, "removed")
            con.execute("DELETE FROM decisions WHERE uid=?", (uid,))


# ------------------------------------------------------------------------------------------------------------------- export
def _export_records(db, pid):
    reqs = db.all("SELECT * FROM requirements WHERE project_id=? ORDER BY seq", (pid,))
    out = []
    for r in reqs:
        current = decision_block(db, r["uid"])
        g = generation_block(db.one("SELECT * FROM generation WHERE uid=?", (r["uid"],)))
        final = current["edited_text"] if current and current["decision"] == "edited" else r["text"]
        out.append((r, current, g, final))
    return out


def export_json(db, pid):
    p = project_or_404(db, pid)
    records = []
    for r, current, g, final in _export_records(db, pid):
        records.append({
            "id": r["rid"], "uid": r["uid"],
            "source": {"file": r["source_file"], "page": r["page"], "paragraph": r["paragraph"]},
            "original_text": r["text"], "final_text": final,
            "decision": ({"status": current["decision"], "edited_text": current["edited_text"], "note": current["note"], "decided_at": current["updated_at"]}
                         if current else None),
            "classification": {"type": r["fr_nfr"], "nfr_probability": r["nfr_probability"]},
            "quality": {"ambiguity_label": r["ambiguity_label"], "ambiguity_probability": r["ambiguity_probability"],
                        "weak_words": loads(r["weak_words"], []), "security_related": bool(r["is_security"]),
                        "risk_level": r["risk_level"], "risk_score": r["risk_score"],
                        "duplicates": [m["id"] for m in loads(r["duplicate_matches"], [])],
                        "conflict_candidates": [{"id": m["id"], "reason": m["reason"]} for m in loads(r["conflict_matches"], [])]},
            "draft": ({"status": g["status"], "user_story": g["user_story"], "technical_task": g["technical_task"],
                       "acceptance_criteria": g["acceptance_criteria"], "rationale": g["rationale"],
                       "clarification_questions": g["clarification_questions"], "manual_review": g["manual_review"]}
                      if g["state"] in ("done", "needs_clarification", "manual_review") else None),
        })
    return {"schema_version": SCHEMA_VERSION, "generated_at": now(), "project": {"id": p["id"], "name": p["name"]},
            "source_files": [s["filename"] for s in db.all("SELECT filename FROM sources WHERE project_id=? ORDER BY id", (pid,))],
            "note": HEURISTIC_NOTE, "requirements": records}


CSV_COLUMNS = ["id", "uid", "source_file", "page", "paragraph", "original_text", "final_text", "decision", "decision_note", "type", "nfr_probability",
               "risk_level", "risk_score", "ambiguity_label", "ambiguity_probability", "weak_words", "security_related", "duplicate_of",
               "conflict_candidates", "generation_state", "user_story", "technical_task", "acceptance_criteria", "rationale", "clarification_questions"]


def _cell(value):
    """Text that starts with = + - @ would be run as a formula by spreadsheet programs; prefix a quote."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", chr(9), chr(13)):
        return "'" + value
    return value


def export_csv(db, pid):
    project_or_404(db, pid)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for r, current, g, final in _export_records(db, pid):
        w.writerow([_cell(c) for c in [r["rid"], r["uid"], r["source_file"], r["page"] if r["page"] is not None else "", r["paragraph"] if r["paragraph"] is not None else "",
                    r["text"], final, current["decision"] if current else "", (current["note"] or "") if current else "", r["fr_nfr"], r["nfr_probability"],
                    r["risk_level"], r["risk_score"], r["ambiguity_label"], r["ambiguity_probability"], ";".join(loads(r["weak_words"], [])),
                    bool(r["is_security"]), ";".join(m["id"] for m in loads(r["duplicate_matches"], [])),
                    ";".join(m["id"] for m in loads(r["conflict_matches"], [])), g["state"], g["user_story"], g["technical_task"],
                    dumps(g["acceptance_criteria"]), g["rationale"], dumps(g["clarification_questions"])]])
    return buf.getvalue()
