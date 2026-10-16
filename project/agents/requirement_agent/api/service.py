"""Queries and serialisation behind the endpoints (no web code here)."""
import csv
import io

from .. import generation as gen
from . import analysis, risk, vague
from .db import dumps, loads, now
from .errors import ApiError
from .explain import build_explanation

FILTER_TYPES = ("all", "ambiguity", "conflict", "duplicate", "security")
DECISIONS = ("accepted", "edited", "rejected")
SCHEMA_VERSION = "c1.clarified_requirements.v1"
HEURISTIC_NOTE = ("Part A labels, risk levels and candidate conflicts are automatic hints from baseline models and an unvalidated heuristic; "
                  "generated drafts are model output. Only the decision field records a human choice.")


# ------------------------------------------------------------------------------------------------------------------- projects
def project_or_404(db, pid):
    p = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    if not p:
        raise ApiError(404, "project_not_found", f"Project {pid} does not exist.")
    return p


def project_out(db, p):
    return {"id": p["id"], "name": p["name"], "created_at": p["created_at"],
            "sources": db.one("SELECT COUNT(*) n FROM sources WHERE project_id=?", (p["id"],))["n"],
            "requirements": db.one("SELECT COUNT(*) n FROM requirements WHERE project_id=?", (p["id"],))["n"]}


def source_out(s):
    return {"id": s["id"], "filename": s["filename"], "ext": s["ext"], "size_bytes": s["size_bytes"], "pages": s["pages"],
            "warnings": loads(s["warnings"], []), "created_at": s["created_at"], "source_type": s.get("source_type") or "srs"}


# ------------------------------------------------------------------------------------------------------------------- generation block
def generation_block(g, text=None):
    base = {"state": "not_requested", "message": "", "status": None, "user_story": "", "technical_task": "", "acceptance_criteria": [], "rationale": "",
            "clarification_questions": [], "attempts": 0, "manual_review": False, "raw_output": "", "updated_at": None,
            "backend": "", "model": "", "numbers_not_in_source": [], "generated_from": "",
            "generated_on": "", "endpoint_host": None}
    if not g:
        return base
    res = loads(g["result"], None) or {}
    base.update(state=g["state"], message=g["message"], attempts=g["attempts"], manual_review=bool(g["manual_review"]), updated_at=g["updated_at"])
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


# ------------------------------------------------------------------------------------------------------------------- list
def _row(r):
    return {"uid": r["uid"], "id": r["rid"], "text": r["text"], "source_file": r["source_file"], "page": r["page"], "paragraph": r["paragraph"],
            "fr_nfr": r["fr_nfr"], "risk_level": r["risk_level"], "risk_score": r["risk_score"],
            "flags": {"ambiguity": r["ambiguity_label"] == "defect", "conflict": r["conflict_matches"] != "[]",
                      "duplicate": r["duplicate_matches"] != "[]", "security": bool(r["is_security"])},
            "generation_state": r["gstate"] or "not_requested", "decision": r["decision"]}


def list_requirements(db, pid, risk_filter=None, type_filter="all", q=None, limit=50, offset=0):
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
    if q and q.strip():
        like = "%" + q.strip().lower().replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(LOWER(r.text) LIKE ? ESCAPE '\\' OR LOWER(r.rid) LIKE ? ESCAPE '\\' OR LOWER(r.source_file) LIKE ? ESCAPE '\\')")
        args += [like, like, like]
    clause = " AND ".join(where)
    total = db.one(f"SELECT COUNT(*) n FROM requirements r WHERE {clause}", args)["n"]
    rows = db.all(f"SELECT r.*, g.state gstate, d.decision FROM requirements r LEFT JOIN generation g ON g.uid=r.uid LEFT JOIN decisions d ON d.uid=r.uid "
                  f"WHERE {clause} ORDER BY r.seq LIMIT ? OFFSET ?", args + [limit, offset])
    return {"total": total, "limit": limit, "offset": offset, "items": [_row(r) for r in rows]}


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
    d = db.one("SELECT * FROM decisions WHERE uid=?", (uid,))
    history = db.all("SELECT decision, edited_text, note, created_at FROM decision_history WHERE uid=? ORDER BY id", (uid,))
    return ({"decision": d["decision"], "edited_text": d["edited_text"], "note": d["note"], "updated_at": d["updated_at"]} if d else None), history


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
    current, history = decision_block(db, uid)
    return {
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
        "generation": generation_block(db.one("SELECT * FROM generation WHERE uid=?", (uid,)), r["text"]),
        "decision": current, "decision_history": history,
    }


def set_decision(db, rid, decision, edited_text, note):
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
    stamp = now()
    db.run("INSERT INTO decisions (uid, decision, edited_text, note, updated_at) VALUES (?,?,?,?,?) "
           "ON CONFLICT(uid) DO UPDATE SET decision=excluded.decision, edited_text=excluded.edited_text, note=excluded.note, updated_at=excluded.updated_at",
           (uid, decision, edited, note, stamp))
    db.run("INSERT INTO decision_history (uid, decision, edited_text, note, created_at) VALUES (?,?,?,?,?)", (uid, decision, edited, note, stamp))
    current, history = decision_block(db, uid)
    return dict(current, uid=uid, history=history)


# ------------------------------------------------------------------------------------------------------------------- export
def _export_records(db, pid):
    reqs = db.all("SELECT * FROM requirements WHERE project_id=? ORDER BY seq", (pid,))
    out = []
    for r in reqs:
        current, _ = decision_block(db, r["uid"])
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
