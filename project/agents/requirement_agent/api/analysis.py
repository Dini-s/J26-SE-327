"""Part A for a whole project: segment the uploaded sources with the existing segmenter, run the saved Part A models, find duplicates and
candidate conflicts, and store one record per requirement. Nothing here trains or re-implements a model: it calls the objects returned by
`agent.load_models()` the same way `agent.run` does.
"""
import hashlib
import re
import threading

from .. import agent as agent_mod
from .. import duplicates as dup
from ..classifier import security_cue_words
from ..features import embed, normalize_for_models
from ..segmenter import segment_document
from . import conflicts, explain, jira, risk
from .db import dumps, loads, now
from .errors import ApiError
from .ingest import line_map_dict

_LOCK = threading.Lock()
_MODELS = {"value": None, "dir": None}


def get_models(models_dir=None):
    """Load the Part A models once per process (the same files the command-line agent loads)."""
    with _LOCK:
        if _MODELS["value"] is None or _MODELS["dir"] != models_dir:
            try:
                _MODELS["value"], _MODELS["dir"] = agent_mod.load_models(models_dir), models_dir
            except agent_mod.ModelMissing as exc:
                raise ApiError(503, "models_missing", str(exc)) from exc
        return _MODELS["value"]


def part_a_loaded(models_dir=None):
    try:
        get_models(models_dir)
        return True
    except ApiError:
        return False


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def weak_word_spans(text, words):
    spans = []
    for w in words:
        for m in re.finditer(r"(?<![A-Za-z0-9])" + re.escape(w) + r"(?![A-Za-z0-9])", text, re.IGNORECASE):
            spans.append({"word": w, "start": m.start(), "end": m.end()})
    return sorted(spans, key=lambda s: s["start"])


def detect(texts, models):
    """Per-text detector output plus the embeddings; the calls are the ones agent.run makes."""
    X = [normalize_for_models(t) for t in texts]
    types = models["type"].predict(X)
    nfr = agent_mod._probability(models["type"], X, "NFR")
    security = models["security"].predict(X)
    amb_label = models["ambiguity"].predict(X)
    amb_prob = agent_mod._probability(models["ambiguity"], X, "defect")
    emb = embed(texts)
    groups = dup.group_ids(dup.cluster_labels(emb, models["duplicate_threshold"]))
    rows = []
    for i, x in enumerate(X):
        rows.append({
            "fr_nfr": str(types[i]), "nfr_probability": round(float(nfr[i]), 4),
            "is_security": str(security[i]) == "1", "security_cue_words": security_cue_words(x),
            "ambiguity_label": str(amb_label[i]), "ambiguity_probability": round(float(amb_prob[i]), 4),
            "weak_words": sorted(set(models["weak_words"].matches(x))), "duplicate_group": groups[i],
        })
    return rows, emb


def _jira_rows(db, s):
    """A Jira document has no file: one row per imported issue (also the ones Jira no longer returned, so their requirements are kept). The issue key is the clause
    label and its number the paragraph, so an issue keeps its place when the others change; the sprint of the issue travels with the row."""
    rows = []
    issues = db.all("SELECT * FROM jira_issues WHERE source_id=?", (s["id"],))
    for i, ji in enumerate(sorted(issues, key=lambda x: (jira.issue_number(x["issue_key"]) or 0, x["issue_key"])), start=1):
        rows.append({"source_id": s["id"], "source_file": s["filename"], "page": None, "paragraph": jira.issue_number(ji["issue_key"]), "position": i,
                     "clause_label": ji["issue_key"], "text": ji["text"], "word_count": len(ji["text"].split()), "sprint_id": ji["sprint_id"]})
    return rows


def _segment_sources(db, sources):
    """Candidate requirement rows of every source, in source order, each with its source reference."""
    rows = []
    for s in sources:
        if s.get("source_type") == "jira":
            rows.extend(_jira_rows(db, s))
            continue
        extracted = loads(s["extracted"])
        seg, _, _ = segment_document(s["filename"].rsplit(".", 1)[0], extracted["text"], s["ext"].lstrip("."), line_map_dict(extracted["line_map"]))
        for r in seg:
            rows.append({"source_id": s["id"], "source_file": s["filename"], "page": r["page"], "paragraph": r["paragraph"],
                         "position": r["position"], "clause_label": r["clause_label"], "text": r["cleaned_text"], "word_count": r["word_count"]})
    return rows


def sources_to_analyse(db, project_id, only=None, force=False):
    """Documents that still need the analysis: not analysed yet, failed, or changed since they were analysed (content hash). Analysed ones are skipped completely."""
    out = []
    for s in db.all("SELECT * FROM sources WHERE project_id=? ORDER BY id", (project_id,)):
        if only is not None and s["id"] not in only:
            continue
        changed = bool(s.get("analyzed_hash") and s.get("sha256") and s["analyzed_hash"] != s["sha256"])
        if force or (s.get("analysis_state") or "not_analyzed") in ("not_analyzed", "failed") or changed:
            out.append(s)
    return out


def _mark(db, ids, state, stamp=None):
    with db.connect() as con:
        for sid in ids:
            if state == "analyzed":
                con.execute("UPDATE sources SET analysis_state=?, analyzed_at=?, analyzed_hash=sha256 WHERE id=?", (state, stamp, sid))
            else:
                con.execute("UPDATE sources SET analysis_state=? WHERE id=?", (state, sid))


def run_part_a(db, project_id, models_dir=None, on_stage=None, only=None, force=False):
    """Analyse the documents of a project that still need it (`only` = a set of source ids, `force` = even if analysed: a re-analysis).
    Analysed documents are skipped completely: their requirements, results, decisions and drafts are not touched, and no draft is queued for them.
    The only project-wide step is the comparison between requirements (duplicates and candidate conflicts, from cached embeddings), because a new
    document can repeat or contradict an old one; the detectors themselves run on the requirements of the analysed documents only.
    Returns {"requirements": total, "uids": all, "new_uids": added, "kept", "changed", "removed", "added", "processed_sources", "skipped_sources"}."""
    models = get_models(models_dir)
    sources = db.all("SELECT * FROM sources WHERE project_id=? ORDER BY id", (project_id,))
    if not sources:
        raise ApiError(400, "no_sources", "Upload at least one source file before analysing.")
    if any((s.get("analysis_state") or "") == "analyzing" for s in sources):
        raise ApiError(409, "analysis_running", "An analysis is already running for this project. Wait for it to finish.")
    todo = sources_to_analyse(db, project_id, only, force)
    if not todo:
        uids = [r["uid"] for r in db.all("SELECT uid FROM requirements WHERE project_id=? ORDER BY seq", (project_id,))]
        return {"requirements": len(uids), "uids": uids, "new_uids": [], "kept": 0, "changed": 0, "removed": 0, "added": 0, "processed_sources": [], "skipped_sources": len(sources)}
    ids = [s["id"] for s in todo]
    _mark(db, ids, "analyzing")
    try:
        result = _analyse(db, project_id, models, todo, on_stage)
    except BaseException:
        _mark(db, ids, "failed")
        raise
    _mark(db, ids, "analyzed", now())
    return dict(result, processed_sources=ids, skipped_sources=len(sources) - len(ids))


def _stored_record(row):
    """A requirement row of an analysed document, in the shape the pair step and the findings builder read."""
    return dict(row, is_security=bool(row["is_security"]), security_cue_words=loads(row["security_cue_words"], []), weak_words=loads(row["weak_words"], []))


def _analyse(db, project_id, models, todo, on_stage):
    if on_stage:
        on_stage("identify")
    rows = _segment_sources(db, todo)
    if on_stage:
        on_stage("analyse")
    proc = {s["id"] for s in todo}
    existing = db.all("SELECT * FROM requirements WHERE project_id=? ORDER BY seq", (project_id,))
    old = {(r["source_id"], r["text_hash"], r["occurrence"]): r for r in existing if r["source_id"] in proc}
    next_seq = max([r["seq"] for r in existing] + [0]) + 1
    seen, recs, kept_keys = {}, [], set()
    for r in rows:
        h = text_hash(r["text"])
        seen[(r["source_id"], h)] = seen.get((r["source_id"], h), 0) + 1
        key = (r["source_id"], h, seen[(r["source_id"], h)])
        if key in old:
            uid, rid, seq = old[key]["uid"], old[key]["rid"], old[key]["seq"]
            kept_keys.add(key)
        else:
            seq, next_seq = next_seq, next_seq + 1
            rid = f"REQ-{seq:03d}"
            uid = f"p{project_id}-{rid}"
        recs.append(dict(r, uid=uid, rid=rid, seq=seq, text_hash=h, occurrence=seen[(r["source_id"], h)], is_kept=key in old))

    detected, _ = detect([r["text"] for r in recs], models) if recs else ([], None)
    for r, d in zip(recs, detected):
        r.update(d)
    gone = [o for k, o in old.items() if k not in kept_keys]
    fresh = [r for r in recs if not r["is_kept"]]
    pool = {}
    for o in gone:
        pool.setdefault((o["source_id"], o["page"], o["paragraph"]), []).append(o["uid"])
    changed_uids = set()
    for a in fresh:  # a removed requirement and a new one at the same place in the document count as one that changed
        waiting = pool.get((a["source_id"], a["page"], a["paragraph"]))
        if waiting:
            changed_uids.add(waiting.pop(0))

    # every requirement of the project, in document order, for the comparison between requirements
    everyone = sorted([_stored_record(r) for r in existing if r["source_id"] not in proc] + recs, key=lambda r: r["seq"])
    texts = [r["text"] for r in everyone]
    threshold = models["duplicate_threshold"]
    emb = embed(texts) if texts else None
    groups = dup.group_ids(dup.cluster_labels(emb, threshold)) if texts else []
    for r, g in zip(everyone, groups):
        r.update(duplicate_group=g, duplicate_matches=[], conflict_matches=[], duplicate_threshold=threshold)
    conflict_rows = []
    if texts:
        for i, j, c in zip(*dup.similarity_pairs(emb, threshold)):
            c = round(float(c), 4)
            everyone[i]["duplicate_matches"].append({"id": everyone[j]["rid"], "uid": everyone[j]["uid"], "similarity": c})
            everyone[j]["duplicate_matches"].append({"id": everyone[i]["rid"], "uid": everyone[i]["uid"], "similarity": c})
        i_, j_, c_ = dup.similarity_pairs(emb, conflicts.MIN_COSINE)
        for hit in conflicts.find_conflicts(texts, zip(i_, j_, c_)):
            a, b = everyone[hit["i"]], everyone[hit["j"]]
            a["conflict_matches"].append({"id": b["rid"], "uid": b["uid"], "similarity": hit["cosine"], "kind": hit["kind"], "reason": hit["reason"]})
            b["conflict_matches"].append({"id": a["rid"], "uid": a["uid"], "similarity": hit["cosine"], "kind": hit["kind"], "reason": hit["reason"]})
            conflict_rows.append((project_id, a["uid"], b["uid"], hit["cosine"], hit["kind"], hit["reason"]))
    for r in everyone:
        r["risk_score"], r["risk_level"] = risk.assess(r["ambiguity_label"] == "defect", len(r["weak_words"]), r["is_security"],
                                                       bool(r["duplicate_matches"]), bool(r["conflict_matches"]))
        r["findings"] = explain.build_findings(r)

    stamp = now()
    with db.connect() as con:
        for o in gone:
            decision = con.execute("SELECT * FROM decisions WHERE uid=?", (o["uid"],)).fetchone()
            if decision is not None:  # the decision is not lost: it goes to the audit table with the reason
                con.execute("INSERT INTO decision_audit (uid, decision, edited_text, note, decided_at, superseded_at, reason) VALUES (?,?,?,?,?,?,?)",
                            (o["uid"], decision["decision"], decision["edited_text"], decision["note"], decision["updated_at"], stamp,
                             "reanalysis_changed" if o["uid"] in changed_uids else "reanalysis_removed"))
            for table in ("generation", "decisions"):
                con.execute(f"DELETE FROM {table} WHERE uid=?", (o["uid"],))
            con.execute("DELETE FROM requirements WHERE uid=?", (o["uid"],))
        con.execute("DELETE FROM conflicts WHERE project_id=?", (project_id,))
        for r in everyone:
            pair = (dumps(r["duplicate_matches"]), dumps(r["conflict_matches"]), r["duplicate_group"], r["risk_score"], r["risk_level"], dumps(r["findings"]))
            if "is_kept" not in r:  # a document that was not analysed: only the comparison between requirements can have changed
                con.execute("UPDATE requirements SET duplicate_matches=?, conflict_matches=?, duplicate_group=?, risk_score=?, risk_level=?, findings=? WHERE uid=?", pair + (r["uid"],))
            elif r["is_kept"]:
                con.execute(
                    "UPDATE requirements SET source_file=?, page=?, paragraph=?, position=?, clause_label=?, word_count=?, fr_nfr=?, nfr_probability=?, is_security=?,"
                    " security_cue_words=?, ambiguity_label=?, ambiguity_probability=?, weak_words=?, duplicate_matches=?, conflict_matches=?, duplicate_group=?,"
                    " risk_score=?, risk_level=?, findings=? WHERE uid=?",
                    (r["source_file"], r["page"], r["paragraph"], r["position"], r["clause_label"], r["word_count"], r["fr_nfr"], r["nfr_probability"], int(r["is_security"]),
                     dumps(r["security_cue_words"]), r["ambiguity_label"], r["ambiguity_probability"], dumps(r["weak_words"]), *pair, r["uid"]))
            else:
                con.execute(
                    "INSERT INTO requirements (uid, project_id, rid, seq, source_id, source_file, page, paragraph, position, clause_label, text, text_hash, occurrence,"
                    " word_count, fr_nfr, nfr_probability, is_security, security_cue_words, ambiguity_label, ambiguity_probability, weak_words, duplicate_group,"
                    " duplicate_matches, conflict_matches, risk_score, risk_level, findings, created_at, sprint_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["uid"], project_id, r["rid"], r["seq"], r["source_id"], r["source_file"], r["page"], r["paragraph"], r["position"], r["clause_label"],
                     r["text"], r["text_hash"], r["occurrence"], r["word_count"], r["fr_nfr"], r["nfr_probability"], int(r["is_security"]),
                     dumps(r["security_cue_words"]), r["ambiguity_label"], r["ambiguity_probability"], dumps(r["weak_words"]), r["duplicate_group"],
                     dumps(r["duplicate_matches"]), dumps(r["conflict_matches"]), r["risk_score"], r["risk_level"], dumps(r["findings"]), stamp, r.get("sprint_id")))
        con.executemany("INSERT INTO conflicts (project_id, a_uid, b_uid, cosine, kind, reason) VALUES (?,?,?,?,?,?)", conflict_rows)
    return {"requirements": len(everyone), "uids": [r["uid"] for r in everyone], "new_uids": [r["uid"] for r in fresh],
            "kept": len(kept_keys), "changed": len(changed_uids), "removed": len(gone) - len(changed_uids), "added": len(fresh) - len(changed_uids)}
