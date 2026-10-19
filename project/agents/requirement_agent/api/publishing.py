"""Publishing by document: the user decides which analysed documents are shared with the other components.

Only published documents are sent to the graph (neo4j_store.build_bundle); unpublishing switches them off there (active = false, never deleted). The rules are here, the
sync itself stays in neo4j_store / autosync. Everything is read and written in the workspace only.
"""
from . import planning, service
from .db import dumps, loads, now
from .errors import ApiError

REASONS = {
    "not_found": "This document is not in the project.",
    "not_analyzed": "Analyse the document first.",
    "analyzing": "The document is being analysed. Publish it when that has finished.",
    "failed": "The analysis of this document failed. Analyse it again first.",
    "no_requirements": "No requirements were found in this document.",
    "already_published": "Already published.",
    "not_published": "Not published.",
}

# the sync state of the project, in the words of one document
_DOC_STATE = {"synced": "published", "not_configured": "published", "syncing": "syncing", "pending": "syncing", "retrying": "sync_error", "unreachable": "sync_error"}


def _documents(db, pid):
    return {s["id"]: s for s in db.all("SELECT * FROM sources WHERE project_id=? ORDER BY id", (pid,))}


def sprint_document_ids(db, pid, sprint_id):
    """The documents of a sprint: the ones that follow it by default, and the ones with at least one requirement in it."""
    planning.sprint_row(db, pid, sprint_id)
    rows = db.all(f"SELECT DISTINCT s.id FROM sources s LEFT JOIN requirements r ON r.source_id=s.id WHERE s.project_id=? AND (s.default_sprint_id=? OR {planning.EFFECTIVE_SPRINT}=?) ORDER BY s.id",
                  (pid, sprint_id, sprint_id))
    return [r["id"] for r in rows]


def _skip_reason(s, publishing):
    if s is None:
        return "not_found"
    state = s.get("analysis_state") or "not_analyzed"
    if publishing:
        if state != "analyzed":
            return {"analyzing": "analyzing", "failed": "failed"}.get(state, "not_analyzed")
        if not db_has_requirements(s):
            return "no_requirements"
        return "already_published" if s.get("published") else None
    return None if s.get("published") else "not_published"


def db_has_requirements(s):
    return bool(s.get("_requirements"))


def change(db, pid, document_ids, sprint_id, publishing):
    """Publish (or unpublish) the given documents and/or every document of a sprint. Returns {"changed": [...], "skipped": [...]} and writes the audit row.
    Documents that cannot be published are skipped with a reason; nothing else is touched."""
    service.project_or_404(db, pid)
    ids = list(dict.fromkeys(document_ids or []))
    if sprint_id is not None:
        ids += [i for i in sprint_document_ids(db, pid, sprint_id) if i not in ids]
    if not ids:
        raise ApiError(400, "invalid_parameter", "Give document_ids or a sprint_id that has documents.")
    docs = _documents(db, pid)
    counts = {r["source_id"]: r["n"] for r in db.all("SELECT source_id, COUNT(*) n FROM requirements WHERE project_id=? GROUP BY source_id", (pid,))}
    changed, skipped, stamp = [], [], now()
    for i in ids:
        s = docs.get(i)
        if s is not None:
            s = dict(s, _requirements=counts.get(i, 0))
        reason = _skip_reason(s, publishing)
        name = s["filename"] if s else str(i)
        if reason:
            skipped.append({"document_id": i, "name": name, "reason": reason, "message": REASONS[reason]})
            continue
        db.run("UPDATE sources SET published=?, published_at=? WHERE id=? AND project_id=?", (1 if publishing else 0, stamp if publishing else None, i, pid))
        changed.append({"document_id": i, "name": name})
    db.run("INSERT INTO publish_audit (project_id, action, scope, sprint_id, document_ids, skipped, at) VALUES (?,?,?,?,?,?,?)",
           (pid, "publish" if publishing else "unpublish", "sprint" if sprint_id is not None and not document_ids else "documents", sprint_id,
            dumps([c["document_id"] for c in changed]), dumps([{"document_id": k["document_id"], "reason": k["reason"]} for k in skipped]), stamp))
    return {"action": "publish" if publishing else "unpublish", "changed": changed, "skipped": skipped}


def counts(db, pid):
    """(published, total) documents of the project."""
    row = db.one("SELECT COUNT(*) total, COALESCE(SUM(published), 0) published FROM sources WHERE project_id=?", (pid,))
    return int(row["published"]), int(row["total"])


def sprint_summary(db, pid, sprint_id, sync_state="synced"):
    """Totals of the sprint and one row per document, counting the requirements that are in this sprint."""
    sprint = planning.sprint_row(db, pid, sprint_id)
    ids = sprint_document_ids(db, pid, sprint_id)
    docs = _documents(db, pid)
    jira = {r["source_id"] for r in db.all("SELECT DISTINCT source_id FROM jira_issues WHERE project_id=?", (pid,))}
    rows = db.all(f"SELECT r.uid, r.source_id, r.fr_nfr, r.ambiguity_label, r.is_security, r.duplicate_matches, r.conflict_matches, g.state gstate, d.decision "
                  f"FROM requirements r JOIN sources s ON s.id=r.source_id LEFT JOIN generation g ON g.uid=r.uid LEFT JOIN decisions d ON d.uid=r.uid "
                  f"WHERE r.project_id=? AND {planning.EFFECTIVE_SPRINT}=?", (pid, sprint_id))
    by_doc = {}
    for r in rows:
        by_doc.setdefault(r["source_id"], []).append(r)
    out = []
    for i in ids:
        s, rs = docs[i], by_doc.get(i, [])
        fr = sum(1 for r in rs if (r["fr_nfr"] or "").upper() == "FR")
        nfr = sum(1 for r in rs if (r["fr_nfr"] or "").upper() == "NFR")
        draft = lambda *states: sum(1 for r in rs if (r["gstate"] or "not_requested") in states)  # noqa: E731
        decided = {k: sum(1 for r in rs if r["decision"] == k) for k in ("accepted", "edited", "rejected")}
        decided["pending"] = sum(1 for r in rs if not r["decision"])
        published = bool(s.get("published"))
        out.append({
            "document_id": i, "name": s["filename"], "source": "jira" if i in jira else "file", "requirements": len(rs), "fr": fr, "nfr": nfr, "unclassified": len(rs) - fr - nfr,
            "ready": draft("done"), "needs_clarification": draft("needs_clarification"), "failed": draft("failed", "manual_review"),
            "not_written": draft("not_requested", "queued", "running"), "decided": decided,
            "findings": {"ambiguity": sum(1 for r in rs if r["ambiguity_label"] == "defect"), "conflict": sum(1 for r in rs if loads(r["conflict_matches"], [])),
                         "duplicate": sum(1 for r in rs if loads(r["duplicate_matches"], [])), "security": sum(1 for r in rs if r["is_security"])},
            "analysis_state": s.get("analysis_state") or "not_analyzed",
            "publish_state": _DOC_STATE.get(sync_state, "published") if published else "not_published", "published_at": s.get("published_at") if published else None})
    total = lambda key: sum(d[key] for d in out)  # noqa: E731
    return {"sprint_id": sprint["id"], "name": sprint["name"], "is_current": sprint["id"] == planning.current_sprint_id(db, pid), "documents": len(out),
            "published": sum(1 for d in out if d["publish_state"] != "not_published"), "requirements": total("requirements"), "fr": total("fr"), "nfr": total("nfr"),
            "ready": total("ready"), "needs_clarification": total("needs_clarification"), "failed": total("failed"), "not_written": total("not_written"),
            "decided": {k: sum(d["decided"][k] for d in out) for k in ("accepted", "edited", "rejected", "pending")}, "rows": out}
