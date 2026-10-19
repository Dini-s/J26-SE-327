"""Phases and sprints of a project, and which sprint each requirement belongs to.

    effective sprint of a requirement = requirement.sprint_id (an override) if set, else the default sprint of its document

A document may cover several sprints (page ranges or single requirements are overridden) and a sprint may hold several documents.
Nothing here ever starts an analysis: planning is only labelling.
"""
import re
import sqlite3
from datetime import date

from .db import now
from .errors import ApiError

NAME_MAX = 80
ORIGINS = ("manual", "detected", "jira")
EFFECTIVE_SPRINT = "COALESCE(r.sprint_id, s.default_sprint_id)"  # r = requirements, s = sources (joined on r.source_id = s.id)

_DETECT = re.compile(r"(?<![A-Za-z])(sprint|iteration)[\s_\-#:]*(\d{1,3})(?!\d)", re.IGNORECASE)
FIRST_PAGE_CHARS = 2000


def _name(value, what):
    value = " ".join((value or "").split())
    if not 1 <= len(value) <= NAME_MAX:
        raise ApiError(422, "validation_error", f"name: use 1 to {NAME_MAX} characters.")
    return value


def _date(value, field):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise ApiError(422, "validation_error", f"{field}: use a date like 2026-10-31.") from None


def _taken(error):
    return isinstance(error, sqlite3.IntegrityError)


def project_or_404(db, pid):
    p = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    if not p:
        raise ApiError(404, "project_not_found", f"Project {pid} does not exist.")
    db.ensure_planning(pid)
    return db.one("SELECT * FROM projects WHERE id=?", (pid,))


def current_sprint_id(db, pid):
    return project_or_404(db, pid)["current_sprint_id"]


# ------------------------------------------------------------------------------------------------------------------- phases
def phase_row(db, pid, phase_id):
    row = db.one("SELECT * FROM phases WHERE id=? AND project_id=?", (phase_id, pid))
    if not row:
        raise ApiError(404, "phase_not_found", f"Phase {phase_id} does not exist in project {pid}.")
    return row


def phase_out(db, row):
    return {"id": row["id"], "project_id": row["project_id"], "name": row["name"], "position": row["position"],
            "sprints": db.one("SELECT COUNT(*) n FROM sprints WHERE phase_id=?", (row["id"],))["n"]}


def list_phases(db, pid):
    project_or_404(db, pid)
    return [phase_out(db, r) for r in db.all("SELECT * FROM phases WHERE project_id=? ORDER BY position, id", (pid,))]


def create_phase(db, pid, name):
    project_or_404(db, pid)
    name = _name(name, "phase")
    pos = (db.one("SELECT MAX(position) m FROM phases WHERE project_id=?", (pid,))["m"] or 0) + 1
    try:
        new = db.run("INSERT INTO phases (project_id, name, position, created_at) VALUES (?,?,?,?)", (pid, name, pos, now()))
    except sqlite3.IntegrityError:
        raise ApiError(409, "phase_name_taken", f"A phase named '{name}' already exists.") from None
    return phase_out(db, phase_row(db, pid, new))


def update_phase(db, pid, phase_id, fields):
    row = phase_row(db, pid, phase_id)
    name = _name(fields["name"], "phase") if fields.get("name") is not None else row["name"]
    position = fields["position"] if fields.get("position") is not None else row["position"]
    try:
        db.run("UPDATE phases SET name=?, position=? WHERE id=?", (name, position, phase_id))
    except sqlite3.IntegrityError:
        raise ApiError(409, "phase_name_taken", f"A phase named '{name}' already exists.") from None
    return phase_out(db, phase_row(db, pid, phase_id))


def delete_phase(db, pid, phase_id):
    """Its sprints stay and lose the phase."""
    phase_row(db, pid, phase_id)
    with db.connect() as con:
        con.execute("UPDATE sprints SET phase_id=NULL WHERE phase_id=?", (phase_id,))
        con.execute("DELETE FROM phases WHERE id=?", (phase_id,))


# ------------------------------------------------------------------------------------------------------------------- sprints
def sprint_row(db, pid, sprint_id):
    row = db.one("SELECT * FROM sprints WHERE id=? AND project_id=?", (sprint_id, pid)) if sprint_id is not None else None
    if not row:
        raise ApiError(404, "sprint_not_found", f"Sprint {sprint_id} does not exist in project {pid}.")
    return row


def decision_counts_by_sprint(db, pid):
    """{sprint_id: {"total", "accepted", "edited", "rejected", "pending"}} over the effective sprint of every requirement."""
    rows = db.all(f"SELECT {EFFECTIVE_SPRINT} sid, d.decision dec, COUNT(*) n FROM requirements r JOIN sources s ON s.id=r.source_id "
                  f"LEFT JOIN decisions d ON d.uid=r.uid WHERE r.project_id=? GROUP BY sid, dec", (pid,))
    out = {}
    for r in rows:
        c = out.setdefault(r["sid"], {"total": 0, "accepted": 0, "edited": 0, "rejected": 0, "pending": 0})
        c[r["dec"] or "pending"] += r["n"]
        c["total"] += r["n"]
    return out


def sprint_out(row, current_id, counts, documents):
    c = counts or {"total": 0, "accepted": 0, "edited": 0, "rejected": 0, "pending": 0}
    return {"id": row["id"], "project_id": row["project_id"], "phase_id": row["phase_id"], "name": row["name"], "start_date": row["start_date"],
            "end_date": row["end_date"], "goal": row["goal"], "origin": row["origin"], "confirmed": bool(row["confirmed"]), "external_id": row["external_id"],
            "position": row["position"], "is_current": row["id"] == current_id, "requirements": c["total"], "pending": c["pending"], "documents": documents}


def sprint_view(db, pid, sprint_id):
    return next(s for s in list_sprints(db, pid) if s["id"] == sprint_id)


def list_sprints(db, pid):
    p = project_or_404(db, pid)
    counts = decision_counts_by_sprint(db, pid)
    docs = {r["sid"]: r["n"] for r in db.all("SELECT default_sprint_id sid, COUNT(*) n FROM sources WHERE project_id=? GROUP BY default_sprint_id", (pid,))}
    return [sprint_out(r, p["current_sprint_id"], counts.get(r["id"]), docs.get(r["id"], 0))
            for r in db.all("SELECT * FROM sprints WHERE project_id=? ORDER BY position, id", (pid,))]


def _check_phase(db, pid, phase_id):
    if phase_id is not None:
        phase_row(db, pid, phase_id)


def create_sprint(db, pid, fields):
    project_or_404(db, pid)
    name = _name(fields.get("name"), "sprint")
    start, end = _date(fields.get("start_date"), "start_date"), _date(fields.get("end_date"), "end_date")
    if start and end and end < start:
        raise ApiError(422, "validation_error", "end_date: must not be before start_date.")
    _check_phase(db, pid, fields.get("phase_id"))
    origin = fields.get("origin") or "manual"
    if origin not in ORIGINS:
        raise ApiError(422, "validation_error", f"origin: use one of {list(ORIGINS)}.")
    pos = (db.one("SELECT MAX(position) m FROM sprints WHERE project_id=?", (pid,))["m"] or 0) + 1
    try:
        new = db.run("INSERT INTO sprints (project_id, phase_id, name, start_date, end_date, goal, origin, confirmed, external_id, position, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (pid, fields.get("phase_id"), name, start, end, fields.get("goal"), origin, 0 if origin == "detected" else 1, fields.get("external_id"), pos, now()))
    except sqlite3.IntegrityError:
        raise ApiError(409, "sprint_name_taken", f"A sprint named '{name}' already exists.") from None
    return sprint_view(db, pid, new)


def update_sprint(db, pid, sprint_id, fields):
    """`fields` holds only what the request set (so phase_id may be set to null)."""
    row = sprint_row(db, pid, sprint_id)
    new = dict(row)
    if "name" in fields and fields["name"] is not None:
        new["name"] = _name(fields["name"], "sprint")
    for key in ("start_date", "end_date"):
        if key in fields:
            new[key] = _date(fields[key], key)
    if new["start_date"] and new["end_date"] and new["end_date"] < new["start_date"]:
        raise ApiError(422, "validation_error", "end_date: must not be before start_date.")
    if "phase_id" in fields:
        _check_phase(db, pid, fields["phase_id"])
        new["phase_id"] = fields["phase_id"]
    for key in ("goal", "position"):
        if key in fields and (fields[key] is not None or key == "goal"):
            new[key] = fields[key]
    if fields.get("confirmed") is not None:
        new["confirmed"] = 1 if fields["confirmed"] else 0
    try:
        db.run("UPDATE sprints SET name=?, phase_id=?, start_date=?, end_date=?, goal=?, position=?, confirmed=? WHERE id=?",
               (new["name"], new["phase_id"], new["start_date"], new["end_date"], new["goal"], new["position"], new["confirmed"], sprint_id))
    except sqlite3.IntegrityError:
        raise ApiError(409, "sprint_name_taken", f"A sprint named '{new['name']}' already exists.") from None
    return sprint_view(db, pid, sprint_id)


def delete_sprint(db, pid, sprint_id, reassign_to=None):
    """A sprint that holds requirements or documents (or is the current one) needs `reassign_to`: they move there. The last sprint cannot be deleted."""
    p = project_or_404(db, pid)
    sprint_row(db, pid, sprint_id)
    if db.one("SELECT COUNT(*) n FROM sprints WHERE project_id=?", (pid,))["n"] <= 1:
        raise ApiError(409, "last_sprint", "A project needs at least one sprint. Rename this one instead.")
    held = db.one(f"SELECT COUNT(*) n FROM requirements r JOIN sources s ON s.id=r.source_id WHERE r.project_id=? AND {EFFECTIVE_SPRINT}=?", (pid, sprint_id))["n"]
    docs = db.one("SELECT COUNT(*) n FROM sources WHERE project_id=? AND default_sprint_id=?", (pid, sprint_id))["n"]
    overrides = db.one("SELECT COUNT(*) n FROM requirements WHERE project_id=? AND sprint_id=?", (pid, sprint_id))["n"]
    if reassign_to is not None:
        if reassign_to == sprint_id:
            raise ApiError(422, "validation_error", "reassign_to: choose a different sprint.")
        sprint_row(db, pid, reassign_to)
    elif held or docs or overrides or p["current_sprint_id"] == sprint_id:
        raise ApiError(409, "reassign_required", "This sprint holds requirements, documents or is the current sprint. Choose where they go (reassign_to).")
    with db.connect() as con:
        if reassign_to is not None:
            con.execute("UPDATE requirements SET sprint_id=? WHERE project_id=? AND sprint_id=?", (reassign_to, pid, sprint_id))
            con.execute("UPDATE sources SET default_sprint_id=? WHERE project_id=? AND default_sprint_id=?", (reassign_to, pid, sprint_id))
            con.execute("UPDATE projects SET current_sprint_id=? WHERE id=? AND current_sprint_id=?", (reassign_to, pid, sprint_id))
        con.execute("DELETE FROM sprints WHERE id=?", (sprint_id,))
    return {"deleted": sprint_id, "reassigned_to": reassign_to, "requirements_moved": held}


def set_current(db, pid, sprint_id):
    sprint_row(db, pid, sprint_id)
    db.run("UPDATE projects SET current_sprint_id=? WHERE id=?", (sprint_id, pid))
    return sprint_view(db, pid, sprint_id)


# ------------------------------------------------------------------------------------------------------------------- assignment
def set_source_sprint(db, pid, source_id, sprint_id):
    if not db.one("SELECT id FROM sources WHERE id=? AND project_id=?", (source_id, pid)):
        raise ApiError(404, "source_not_found", f"Source {source_id} does not exist in project {pid}.")
    sprint_row(db, pid, sprint_id)
    db.run("UPDATE sources SET default_sprint_id=? WHERE id=?", (sprint_id, source_id))


def assign_ranges(db, pid, source_id, ranges):
    """Set the sprint override of the requirements of one document by page range. Documents without pages (txt, docx) cannot be split this way."""
    if not db.one("SELECT id FROM sources WHERE id=? AND project_id=?", (source_id, pid)):
        raise ApiError(404, "source_not_found", f"Source {source_id} does not exist in project {pid}.")
    if not ranges:
        raise ApiError(422, "validation_error", "ranges: give at least one range.")
    for r in ranges:
        sprint_row(db, pid, r["sprint_id"])
        if r["from_page"] < 1 or r["to_page"] < r["from_page"]:
            raise ApiError(422, "validation_error", "ranges: use from_page >= 1 and to_page >= from_page.")
    assigned = 0
    with db.connect() as con:
        for r in ranges:  # later ranges win where they overlap
            assigned += con.execute("UPDATE requirements SET sprint_id=? WHERE project_id=? AND source_id=? AND page BETWEEN ? AND ?",
                                    (r["sprint_id"], pid, source_id, r["from_page"], r["to_page"])).rowcount
    total = db.one("SELECT COUNT(*) n FROM requirements WHERE project_id=? AND source_id=?", (pid, source_id))["n"]
    without_page = db.one("SELECT COUNT(*) n FROM requirements WHERE project_id=? AND source_id=? AND page IS NULL", (pid, source_id))["n"]
    return {"assigned": assigned, "requirements": total, "without_page": without_page}


def assign_requirements(db, pid, ids, sprint_id):
    """Bulk assign (uid or display id of this project). sprint_id null removes the override: the requirement follows its document again."""
    project_or_404(db, pid)
    if sprint_id is not None:
        sprint_row(db, pid, sprint_id)
    if not ids:
        raise ApiError(422, "validation_error", "requirement_ids: give at least one requirement.")
    uids, missing = [], []
    for rid in ids:
        row = db.one("SELECT uid FROM requirements WHERE project_id=? AND (uid=? OR rid=?)", (pid, rid, rid))
        (uids if row else missing).append(row["uid"] if row else rid)
    if missing:
        raise ApiError(404, "requirement_not_found", "Not in this project: " + ", ".join(missing[:10]))
    with db.connect() as con:
        con.executemany("UPDATE requirements SET sprint_id=? WHERE uid=?", [(sprint_id, u) for u in uids])
    return {"assigned": len(uids), "sprint_id": sprint_id}


# ------------------------------------------------------------------------------------------------------------------- upload
def detect_sprint(filename, text=""):
    """Minimal detection: "Sprint 3" or "Iteration 2" in the file name, else on the first page. Returns the proposed name or None."""
    for source in (filename or "", (text or "")[:FIRST_PAGE_CHARS]):
        m = _DETECT.search(source)
        if m:
            return f"{m.group(1).capitalize()} {int(m.group(2))}"
    return None


def upload_target(db, pid, phase_id=None, sprint_id=None):
    """The sprint a new document starts in: the one asked for, else the first sprint of the asked phase, else the current sprint."""
    p = project_or_404(db, pid)
    if sprint_id is not None:
        row = sprint_row(db, pid, sprint_id)
        if phase_id is not None and row["phase_id"] != phase_id:
            raise ApiError(422, "validation_error", "sprint_id: this sprint is not in the chosen phase.")
        return row["id"]
    if phase_id is not None:
        phase_row(db, pid, phase_id)
        first = db.one("SELECT id FROM sprints WHERE project_id=? AND phase_id=? ORDER BY position, id LIMIT 1", (pid, phase_id))
        if not first:
            raise ApiError(422, "validation_error", "phase_id: this phase has no sprint yet. Add one or choose a sprint.")
        return first["id"]
    return p["current_sprint_id"]


def find_or_propose(db, pid, name):
    """The sprint with this name, or a new one proposed (origin detected, not confirmed). Returns (sprint row, created)."""
    row = db.one("SELECT * FROM sprints WHERE project_id=? AND name=? COLLATE NOCASE", (pid, name))
    if row:
        return row, False
    created = create_sprint(db, pid, {"name": name, "origin": "detected"})
    return sprint_row(db, pid, created["id"]), True
