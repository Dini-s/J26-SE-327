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
from . import conflicts, explain, risk
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


def _segment_sources(sources):
    """Candidate requirement rows of every source, in source order, each with its source reference."""
    rows = []
    for s in sources:
        extracted = loads(s["extracted"])
        seg, _, _ = segment_document(s["filename"].rsplit(".", 1)[0], extracted["text"], s["ext"].lstrip("."), line_map_dict(extracted["line_map"]))
        for r in seg:
            rows.append({"source_id": s["id"], "source_file": s["filename"], "page": r["page"], "paragraph": r["paragraph"],
                         "position": r["position"], "clause_label": r["clause_label"], "text": r["cleaned_text"], "word_count": r["word_count"]})
    return rows


def run_part_a(db, project_id, models_dir=None, on_stage=None):
    """Rebuild the requirement records of a project. Returns {"requirements": n, "uids": [...]}. Decisions and generation state of
    requirements whose text and source are unchanged are kept (the id is matched by source, text hash and the occurrence number of that text in that source). Everything else derived from the project is replaced, so analysing twice never duplicates requirements."""
    models = get_models(models_dir)
    sources = db.all("SELECT * FROM sources WHERE project_id=? ORDER BY id", (project_id,))
    if not sources:
        raise ApiError(400, "no_sources", "Upload at least one source file before analysing.")
    if on_stage:
        on_stage("identify")
    rows = _segment_sources(sources)
    if on_stage:
        on_stage("analyse")

    old = {(r["source_id"], r["text_hash"], r["occurrence"]): r for r in db.all("SELECT uid, rid, seq, source_id, text_hash, occurrence FROM requirements WHERE project_id=?", (project_id,))}
    next_seq = max([r["seq"] for r in old.values()] + [0]) + 1
    seen, recs = {}, []
    for r in rows:
        h = text_hash(r["text"])
        seen[(r["source_id"], h)] = seen.get((r["source_id"], h), 0) + 1
        key = (r["source_id"], h, seen[(r["source_id"], h)])
        if key in old:
            uid, rid, seq = old[key]["uid"], old[key]["rid"], old[key]["seq"]
        else:
            seq, next_seq = next_seq, next_seq + 1
            rid = f"REQ-{seq:03d}"
            uid = f"p{project_id}-{rid}"
        recs.append(dict(r, uid=uid, rid=rid, seq=seq, text_hash=h, occurrence=seen[(r["source_id"], h)]))

    texts = [r["text"] for r in recs]
    detected, emb = detect(texts, models) if texts else ([], None)
    for r, d in zip(recs, detected):
        r.update(d)
        r.update(duplicate_matches=[], conflict_matches=[], duplicate_threshold=models["duplicate_threshold"])
    conflict_rows = []
    if texts:
        threshold = models["duplicate_threshold"]
        for i, j, c in zip(*dup.similarity_pairs(emb, threshold)):
            c = round(float(c), 4)
            recs[i]["duplicate_matches"].append({"id": recs[j]["rid"], "uid": recs[j]["uid"], "similarity": c})
            recs[j]["duplicate_matches"].append({"id": recs[i]["rid"], "uid": recs[i]["uid"], "similarity": c})
        i_, j_, c_ = dup.similarity_pairs(emb, conflicts.MIN_COSINE)
        for hit in conflicts.find_conflicts(texts, zip(i_, j_, c_)):
            a, b = recs[hit["i"]], recs[hit["j"]]
            a["conflict_matches"].append({"id": b["rid"], "uid": b["uid"], "similarity": hit["cosine"], "kind": hit["kind"], "reason": hit["reason"]})
            b["conflict_matches"].append({"id": a["rid"], "uid": a["uid"], "similarity": hit["cosine"], "kind": hit["kind"], "reason": hit["reason"]})
            conflict_rows.append((project_id, a["uid"], b["uid"], hit["cosine"], hit["kind"], hit["reason"]))
    for r in recs:
        r["risk_score"], r["risk_level"] = risk.assess(r["ambiguity_label"] == "defect", len(r["weak_words"]), r["is_security"],
                                                       bool(r["duplicate_matches"]), bool(r["conflict_matches"]))
        r["findings"] = explain.build_findings(r)

    keep = {r["uid"] for r in recs}
    stamp = now()
    with db.connect() as con:
        gone = [r["uid"] for r in con.execute("SELECT uid FROM requirements WHERE project_id=?", (project_id,)).fetchall() if r["uid"] not in keep]
        for uid in gone:
            for table in ("generation", "decisions", "decision_history"):
                con.execute(f"DELETE FROM {table} WHERE uid=?", (uid,))
        con.execute("DELETE FROM requirements WHERE project_id=?", (project_id,))
        con.execute("DELETE FROM conflicts WHERE project_id=?", (project_id,))
        for r in recs:
            con.execute(
                "INSERT INTO requirements (uid, project_id, rid, seq, source_id, source_file, page, paragraph, position, clause_label, text, text_hash, occurrence,"
                " word_count, fr_nfr, nfr_probability, is_security, security_cue_words, ambiguity_label, ambiguity_probability, weak_words, duplicate_group,"
                " duplicate_matches, conflict_matches, risk_score, risk_level, findings, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["uid"], project_id, r["rid"], r["seq"], r["source_id"], r["source_file"], r["page"], r["paragraph"], r["position"], r["clause_label"],
                 r["text"], r["text_hash"], r["occurrence"], r["word_count"], r["fr_nfr"], r["nfr_probability"], int(r["is_security"]),
                 dumps(r["security_cue_words"]), r["ambiguity_label"], r["ambiguity_probability"], dumps(r["weak_words"]), r["duplicate_group"],
                 dumps(r["duplicate_matches"]), dumps(r["conflict_matches"]), r["risk_score"], r["risk_level"], dumps(r["findings"]), stamp))
        con.executemany("INSERT INTO conflicts (project_id, a_uid, b_uid, cosine, kind, reason) VALUES (?,?,?,?,?,?)", conflict_rows)
    return {"requirements": len(recs), "uids": [r["uid"] for r in recs]}
