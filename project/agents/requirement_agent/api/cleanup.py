"""Deleting uploaded sources and everything derived from them.

Cascade for one source (all in one database transaction, then the file is removed):
    requirements of that source -> their generation results, decisions, decision audit rows and candidate conflicts.
The shared generation cache (keyed by text, backend and model) is kept: it holds no project data and only saves work.
Requirements of the other sources stay with their ids and decisions. Partner links that pointed at a deleted requirement (duplicates, conflicts,
and the findings that mention them) are removed from the remaining requirements and their risk level is recomputed from what is left; the other
detector results do not depend on other requirements and are unchanged.
Clearing all sources removes every requirement, finding, generation result, decision and conflict of the project.
Refused with 409 while Part A is running for the project or any draft is queued or running.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import risk
from .db import dumps, loads
from .errors import ApiError

BUSY_MESSAGE = "An analysis or draft generation is still running for this project. Wait for it to finish, then try again."
JOB_STALE_AFTER = timedelta(minutes=15)  # a job row that never finished (a crashed request) stops blocking after this long


def project_busy(db, pid):
    paused = (db.one("SELECT value FROM settings WHERE key='gen_paused'") or {}).get("value") == "1"
    states = "'running'" if paused else "'queued','running'"  # a paused queue does not run, so waiting items do not block a delete
    queued = db.one(f"SELECT COUNT(*) n FROM generation g JOIN requirements r ON r.uid=g.uid WHERE r.project_id=? AND g.state IN ({states})", (pid,))["n"]
    cutoff = (datetime.now(timezone.utc) - JOB_STALE_AFTER).isoformat(timespec="seconds")
    running = db.one("SELECT COUNT(*) n FROM jobs WHERE project_id=? AND part_a_done=0 AND error IS NULL AND updated_at>=?", (pid, cutoff))["n"]
    return queued > 0 or running > 0


def remove_upload(workspace, stored_path):
    """Delete an uploaded file only if it really is inside <workspace>/uploads. Returns True when the file is gone."""
    root = (Path(workspace) / "uploads").resolve()
    try:
        path = Path(stored_path).resolve()
    except (OSError, ValueError):
        return False
    if root not in path.parents:
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        return False
    try:
        path.parent.rmdir()  # the project folder, when it is empty now
    except OSError:
        pass
    return True


def _prune_partners(con, pid, gone_uids, gone_rids):
    """Remove links to deleted requirements from the remaining ones and recompute their risk."""
    rows = con.execute(
        "SELECT uid, ambiguity_label, is_security, weak_words, duplicate_group, duplicate_matches, conflict_matches, findings FROM requirements WHERE project_id=?", (pid,)
    ).fetchall()
    for r in rows:
        dups, confs = loads(r["duplicate_matches"], []), loads(r["conflict_matches"], [])
        keep_d = [m for m in dups if m["uid"] not in gone_uids]
        keep_c = [m for m in confs if m["uid"] not in gone_uids]
        if len(keep_d) == len(dups) and len(keep_c) == len(confs):
            continue
        findings = [f for f in loads(r["findings"], []) if not set(f.get("related", [])) & gone_rids]
        score, level = risk.assess(r["ambiguity_label"] == "defect", len(loads(r["weak_words"], [])), bool(r["is_security"]), bool(keep_d), bool(keep_c))
        con.execute(
            "UPDATE requirements SET duplicate_matches=?, conflict_matches=?, findings=?, risk_score=?, risk_level=?, duplicate_group=? WHERE uid=?",
            (dumps(keep_d), dumps(keep_c), dumps(findings), score, level, r["duplicate_group"] if keep_d else "", r["uid"]))


def delete_sources(db, workspace, pid, source_id=None):
    """Delete one source (source_id) or all sources of the project, with everything derived from them. Raises ApiError 404 or 409."""
    if not db.one("SELECT id FROM projects WHERE id=?", (pid,)):
        raise ApiError(404, "project_not_found", f"Project {pid} does not exist.")
    if source_id is None:
        sources = db.all("SELECT id, stored_path FROM sources WHERE project_id=?", (pid,))
    else:
        row = db.one("SELECT id, stored_path FROM sources WHERE id=? AND project_id=?", (source_id, pid))
        if not row:
            raise ApiError(404, "source_not_found", f"Source {source_id} does not exist in project {pid}.")
        sources = [row]
    if project_busy(db, pid):
        raise ApiError(409, "project_busy", BUSY_MESSAGE)

    with db.connect() as con:
        if source_id is None:
            reqs = con.execute("SELECT uid, rid FROM requirements WHERE project_id=?", (pid,)).fetchall()
        else:
            reqs = con.execute("SELECT uid, rid FROM requirements WHERE project_id=? AND source_id=?", (pid, source_id)).fetchall()
        gone_uids, gone_rids = {r["uid"] for r in reqs}, {r["rid"] for r in reqs}
        for uid in gone_uids:
            for table in ("generation", "decisions", "decision_audit"):
                con.execute(f"DELETE FROM {table} WHERE uid=?", (uid,))
            con.execute("DELETE FROM conflicts WHERE a_uid=? OR b_uid=?", (uid, uid))
            con.execute("DELETE FROM requirements WHERE uid=?", (uid,))
        if source_id is None:
            con.execute("DELETE FROM sources WHERE project_id=?", (pid,))
            con.execute("DELETE FROM jira_issues WHERE project_id=?", (pid,))  # the issue map goes with its documents (the connection stays)
            con.execute("DELETE FROM jobs WHERE project_id=?", (pid,))
        else:
            con.execute("DELETE FROM sources WHERE id=?", (source_id,))
            con.execute("DELETE FROM jira_issues WHERE source_id=?", (source_id,))
            _prune_partners(con, pid, gone_uids, gone_rids)
    for s in sources:
        remove_upload(workspace, s["stored_path"])
    return {"sources": len(sources), "requirements": len(gone_uids)}
