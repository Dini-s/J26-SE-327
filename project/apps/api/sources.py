"""Data access and aggregation for the dashboard (no web framework in here, so it is testable).

Two data sources are combined:
* run logs written by the pipeline (``data/runs/<run>/events.jsonl``), for live progress,
* Neo4j (the USKG), when reachable, for the persisted graph.
Processed datasets (``data/processed/<name>/``) supply artifact text and ground truth.
"""

import json
import os
import time
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = Path(os.getenv("DASHBOARD_RUNS_DIR", PROJECT_ROOT / "data" / "runs"))
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


# ---------------------------------------------------------------- run logs
def latest_run_dir(runs_dir: Path = RUNS_DIR, kind: str = "pipeline") -> Optional[Path]:
    """Newest run directory with an events file (names start with a timestamp).

    Args:
        runs_dir: Where runs are stored.
        kind: ``pipeline`` (link/evaluate runs), ``monitor`` (decay passes) or ``any``.
    """
    if not runs_dir.exists():
        return None
    runs = sorted(
        d
        for d in runs_dir.iterdir()
        if (d / "events.jsonl").exists()
        and (kind == "any" or d.name.endswith("-monitor") == (kind == "monitor"))
    )
    return runs[-1] if runs else None


def read_events(run_dir: Path) -> list[dict[str, Any]]:
    """All parseable events of a run (a half-written last line is ignored)."""
    events: list[dict[str, Any]] = []
    with open(run_dir / "events.jsonl", encoding="utf-8") as fh:
        for line in fh:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                break
    return events


@lru_cache(maxsize=4)
def load_dataset(name: str) -> dict[str, Any]:
    """Artifacts (by id) and ground-truth pairs of a processed dataset ({} if missing)."""
    base = PROCESSED_DIR / name
    if not (base / "artifacts.json").exists():
        return {"artifacts": {}, "truth": set()}
    artifacts = {a["id"]: a for a in json.loads((base / "artifacts.json").read_text(encoding="utf-8"))}
    truth = {(t["source_id"], t["target_id"]) for t in json.loads((base / "traces.json").read_text(encoding="utf-8"))}
    return {"artifacts": artifacts, "truth": truth}


def summarize_run(events: list[dict[str, Any]], truth: set[tuple[str, str]]) -> dict[str, Any]:
    """Progress and live precision/recall of a run, computed from its events.

    Recall is measured against the ground-truth links of the run's own requirements,
    and is only final once the run has finished. ``shortlisted_true`` is how many true
    links stage 1 shortlisted, which is the ceiling for recall.
    """
    start = next((e for e in events if e["type"] == "run_start"), None)
    end = next((e for e in events if e["type"] == "run_end"), None)
    if start is None:
        return {"state": "none"}
    sources = set(start.get("sources", []))
    run_truth = {p for p in truth if p[0] in sources}
    shortlist = {(e["source_id"], t["id"]) for e in events if e["type"] == "shortlist" for t in e["targets"]}
    verdicts = [e for e in events if e["type"] == "verdict"]
    verify_start = next((e for e in events if e["type"] == "verify_start"), None)
    kept = {(v["source_id"], v["target_id"]) for v in verdicts if v["kept"]}
    tp, fp = len(kept & run_truth), len(kept - run_truth)
    fn = len(run_truth - kept)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / len(run_truth) if run_truth else 0.0
    latencies = sorted(v["latency"] for v in verdicts)
    return {
        "state": "finished" if end else ("verifying" if verify_start else "shortlisting"),
        "dataset": start.get("dataset"),
        "retrieval": start.get("retrieval"),
        "top_k": start.get("top_k"),
        "sources": len(sources),
        "targets": start.get("n_targets"),
        "true_links": len(run_truth),
        "shortlisted": len(shortlist),
        "shortlisted_true": len(shortlist & run_truth),
        "total": verify_start["total"] if verify_start else None,
        "done": len(verdicts),
        "malformed": sum(1 for e in events if e["type"] == "malformed"),
        "kept": len(kept),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "mean_latency": sum(latencies) / len(latencies) if latencies else None,
        "p95_latency": latencies[int(0.95 * (len(latencies) - 1))] if latencies else None,
        "started": start["ts"],
        "finished": end["ts"] if end else None,
    }


def build_run_graph(
    events: list[dict[str, Any]], artifacts: dict[str, dict], truth: set[tuple[str, str]]
) -> dict[str, Any]:
    """Graph of one run: shortlisted pairs coloured by what the LLM decided, plus missed true links.

    Edge categories:
        verified_correct  LLM accepted, and the link is in the ground truth
        verified_wrong    LLM accepted, but not in the ground truth (false positive)
        rejected_true     LLM rejected a true link (false negative at stage 2)
        rejected          LLM rejected, correctly
        pending           shortlisted, not yet verified
        missed            true link that stage 1 never shortlisted (false negative at stage 1)
    """
    start = next((e for e in events if e["type"] == "run_start"), None)
    if start is None:
        return {"nodes": [], "edges": []}
    sources = list(start.get("sources", []))
    source_set = set(sources)
    verdicts = {(e["source_id"], e["target_id"]): e for e in events if e["type"] == "verdict"}
    shortlist: dict[tuple[str, str], float] = {}
    for e in events:
        if e["type"] == "shortlist":
            for t in e["targets"]:
                shortlist[(e["source_id"], t["id"])] = t["score"]

    edges: list[dict[str, Any]] = []
    for (s, t), score in shortlist.items():
        v = verdicts.get((s, t))
        is_true = (s, t) in truth
        if v is None:
            category = "pending"
        elif not truth:  # no gold labels (e.g. a run on Neo4j data): no correct / wrong judgement
            category = "verified" if v["kept"] else "rejected"
        elif v["kept"]:
            category = "verified_correct" if is_true else "verified_wrong"
        else:
            category = "rejected_true" if is_true else "rejected"
        edges.append(
            {"from": f"r:{s}", "to": f"c:{t}", "category": category, "truth": is_true if truth else None, "similarity": score,
             "confidence": v["confidence"] if v else None, "reasoning": v["reasoning"] if v else None}
        )
    for s, t in sorted(truth):
        if s in source_set and (s, t) not in shortlist:
            edges.append({"from": f"r:{s}", "to": f"c:{t}", "category": "missed", "truth": True,
                          "similarity": None, "confidence": None, "reasoning": None})

    node_ids = {e["from"] for e in edges} | {e["to"] for e in edges} | {f"r:{s}" for s in sources}
    nodes = []
    for nid in node_ids:
        kind = "requirement" if nid.startswith("r:") else "code"
        art = artifacts.get(nid[2:], {})
        nodes.append({"id": nid, "label": nid[2:], "kind": kind, "text": (art.get("text") or "")[:1500]})
    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------- Neo4j
_neo_cache: dict[str, Any] = {"at": 0.0, "value": None}


def _neo4j_driver() -> Any:
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
        connection_timeout=2,
        max_transaction_retry_time=1,
    )


def neo4j_status(ttl: float = 5.0) -> dict[str, Any]:
    """Connectivity and node/edge counts, cached briefly so polling never hammers the DB."""
    if _neo_cache["value"] is not None and time.time() - _neo_cache["at"] < ttl:
        return _neo_cache["value"]
    result: dict[str, Any] = {"connected": False, "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687")}
    try:
        with _neo4j_driver() as driver:
            driver.verify_connectivity()
            counts = {}
            for key, query in {
                "requirements": "MATCH (n:Requirement) RETURN count(n) AS c",
                "code_entities": "MATCH (n:CodeEntity) RETURN count(n) AS c",
                "verified_traces": "MATCH ()-[v:VERIFIED_TRACE]->() RETURN count(v) AS c",
                "decayed": "MATCH ()-[v:VERIFIED_TRACE {status:'decayed'}]->() RETURN count(v) AS c",
                "decay_flags": "MATCH (d:DecayFlag) RETURN count(d) AS c",
            }.items():
                records, _, _ = driver.execute_query(query)
                counts[key] = records[0]["c"]
            result.update(connected=True, counts=counts)
    except Exception as exc:  # any failure (refused, auth, missing driver) just means "not connected"
        result["error"] = f"{type(exc).__name__}: {exc}"[:200]
    _neo_cache.update(at=time.time(), value=result)
    return result


def neo4j_graph(limit: int = 500) -> dict[str, Any]:
    """The persisted USKG trace graph: VERIFIED_TRACE edges with their endpoints."""
    query = """
    MATCH (r:Requirement)-[v:VERIFIED_TRACE]->(c:CodeEntity)
    RETURN r.id AS s, coalesce(r.text,'') AS rtext, c.id AS t, coalesce(c.text,'') AS ctext,
           v.status AS status, v.confidence AS confidence, v.justification AS reasoning
    LIMIT $limit
    """
    nodes: dict[str, dict] = {}
    edges = []
    with _neo4j_driver() as driver:
        records, _, _ = driver.execute_query(query, limit=limit)
    for r in records:
        nodes.setdefault(f"r:{r['s']}", {"id": f"r:{r['s']}", "label": r["s"], "kind": "requirement", "text": r["rtext"][:1500]})
        nodes.setdefault(f"c:{r['t']}", {"id": f"c:{r['t']}", "label": r["t"], "kind": "code", "text": r["ctext"][:1500]})
        edges.append({"from": f"r:{r['s']}", "to": f"c:{r['t']}",
                      "category": "decayed" if r["status"] == "decayed" else "verified",
                      "truth": None, "similarity": None, "confidence": r["confidence"], "reasoning": r["reasoning"]})
    return {"nodes": list(nodes.values()), "edges": edges}


# ---------------------------------------------------------------- LLM server
def llm_status() -> dict[str, Any]:
    """Whether the configured OpenAI-compatible server answers (the API key is never returned)."""
    base = (os.getenv("LLM_BASE_URL") or "").rstrip("/")
    if not base:
        return {"configured": False}
    url = base[:-3] if base.endswith("/v1") else base
    request = urllib.request.Request(url + "/api/version")
    if os.getenv("LLM_API_KEY"):
        request.add_header("Authorization", f"Bearer {os.getenv('LLM_API_KEY')}")
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return {"configured": True, "reachable": True, "model": os.getenv("LLM_MODEL"),
                    "info": json.loads(response.read().decode())}
    except Exception as exc:
        return {"configured": True, "reachable": False, "model": os.getenv("LLM_MODEL"),
                "error": f"{type(exc).__name__}"}


def neo4j_projects() -> list[dict[str, Any]]:
    """Projects (repositories) in the graph with node / link counts, for the project selector."""
    from shared.uskg.client import _PROJECTS_QUERY

    with _neo4j_driver() as driver:
        records, _, _ = driver.execute_query(_PROJECTS_QUERY)
    return [dict(r) for r in records]


def neo4j_completeness(project: Optional[str] = None) -> dict[str, Any]:
    """Completeness score per requirement and the orphan list, from the live USKG."""
    from agents.traceability_agent.completeness import completeness_scores
    from shared.uskg.client import USKGClient

    scope = {"project": project} if project else {}
    with USKGClient() as uskg:
        results = completeness_scores(uskg.get_artifacts("requirement", **scope), uskg.get_traces(**scope))
    rows = sorted((r.model_dump() for r in results), key=lambda r: r["score"])
    orphans = [r["requirement_id"] for r in rows if r["is_orphan"]]
    return {
        "requirements": len(rows),
        "orphans": orphans,
        "mean_score": sum(r["score"] for r in rows) / len(rows) if rows else 0.0,
        "rows": rows,
    }


# ---------------------------------------------------------------- USKG graph (Neo4j)
def _trim(text: Any, n: int = 1200) -> str:
    return (text or "")[:n]


def neo4j_uskg_graph(max_traces: int = 400, max_orphans: int = 40, project: Optional[str] = None) -> dict[str, Any]:
    """The USKG as the dashboard shows it: requirements, code entities, VERIFIED_TRACE edges
    (verified or decayed), DecayFlag nodes with HAS_DECAY edges, plus some orphan requirements."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def req(rid: str, text: Any = "", **extra: Any) -> str:
        nid = f"r:{rid}"
        nodes.setdefault(nid, {"id": nid, "label": rid, "kind": "requirement", "text": _trim(text), **extra})
        return nid

    with _neo4j_driver() as driver:
        traces, _, _ = driver.execute_query(
            """MATCH (r:Requirement)-[v:VERIFIED_TRACE]->(c:CodeEntity)
               WHERE $project IS NULL OR coalesce(r.project, r.repo, r.dataset) = $project
               RETURN r.id AS s, coalesce(r.text,'') AS rtext, c.id AS t, coalesce(c.text,'') AS ctext,
                      coalesce(c.kind,'code') AS ckind, v.status AS status, v.confidence AS confidence,
                      v.justification AS reasoning, toString(v.lastCheckedAt) AS checked
               LIMIT $n""", n=max_traces, project=project)
        flags, _, _ = driver.execute_query(
            """MATCH (r:Requirement)-[:HAS_DECAY]->(d:DecayFlag)
               WHERE $project IS NULL OR coalesce(r.project, r.repo, r.dataset) = $project
               RETURN r.id AS rid, coalesce(r.text,'') AS rtext, toString(id(d)) AS did, d.codeEntityId AS cid,
                      d.previousConfidence AS prev, d.reason AS reason, toString(d.flaggedAt) AS at
               LIMIT 200""", project=project)
        orphans, _, _ = driver.execute_query(
            """MATCH (r:Requirement)
               WHERE NOT (r)-[:VERIFIED_TRACE]->()
                 AND ($project IS NULL OR coalesce(r.project, r.repo, r.dataset) = $project)
               RETURN r.id AS rid, coalesce(r.text,'') AS rtext LIMIT $n""", n=max_orphans, project=project)

    for t in traces:
        rn = req(t["s"], t["rtext"])
        cn = f"c:{t['t']}"
        nodes.setdefault(cn, {"id": cn, "label": t["t"], "kind": "code", "codeKind": t["ckind"], "text": _trim(t["ctext"])})
        edges.append({"from": rn, "to": cn, "category": "decayed" if t["status"] == "decayed" else "verified",
                      "confidence": t["confidence"], "reasoning": t["reasoning"], "checked": t["checked"]})
    for f in flags:
        rn = req(f["rid"], f["rtext"])
        dn = f"d:{f['did']}"
        nodes[dn] = {"id": dn, "label": "DecayFlag", "kind": "decayflag", "text": f["reason"] or "",
                     "codeEntityId": f["cid"], "previousConfidence": f["prev"], "flaggedAt": f["at"]}
        edges.append({"from": rn, "to": dn, "category": "has_decay", "confidence": f["prev"], "reasoning": f["reason"], "checked": f["at"]})
    for o in orphans:
        req(o["rid"], o["rtext"], orphan=True)
    return {"source": "neo4j", "nodes": list(nodes.values()), "edges": edges}


def neo4j_requirement_detail(requirement_id: str) -> dict[str, Any]:
    """One requirement: its text, every linked code entity with the LLM justification, and its score."""
    with _neo4j_driver() as driver:
        req, _, _ = driver.execute_query(
            "MATCH (r:Requirement {id: $id}) RETURN r.id AS id, coalesce(r.text,'') AS text", id=requirement_id)
        if not req:
            return {}
        links, _, _ = driver.execute_query(
            """MATCH (r:Requirement {id: $id})-[v:VERIFIED_TRACE]->(c:CodeEntity)
               RETURN c.id AS code_id, coalesce(c.text,'') AS code_text, v.status AS status, v.confidence AS confidence,
                      v.justification AS justification, toString(v.verifiedAt) AS verified_at, toString(v.lastCheckedAt) AS last_checked
               ORDER BY v.confidence DESC""", id=requirement_id)
        flags, _, _ = driver.execute_query(
            """MATCH (r:Requirement {id: $id})-[:HAS_DECAY]->(d:DecayFlag)
               RETURN d.codeEntityId AS code_id, d.previousConfidence AS previous, d.reason AS reason, toString(d.flaggedAt) AS at
               ORDER BY d.flaggedAt DESC""", id=requirement_id)
    from agents.traceability_agent.completeness import completeness_scores
    from shared.schemas.traceability import Artifact, TraceabilityLink

    traces = [
        TraceabilityLink(source_id=requirement_id, target_id=l["code_id"], link_type="requirement_to_code",
                         confidence=l["confidence"] or 0.0, justification=l["justification"] or "", status=l["status"] or "verified")
        for l in links
    ]
    score = completeness_scores([Artifact(id=requirement_id, type="requirement", text=req[0]["text"])], traces)[0]
    return {
        "id": requirement_id,
        "text": req[0]["text"],
        "score": score.model_dump(),
        "links": [{**dict(l), "code_text": _trim(l["code_text"], 600)} for l in links],
        "decay_history": [dict(f) for f in flags],
    }


def neo4j_decay(project: Optional[str] = None) -> dict[str, Any]:
    """Decayed links and the DecayFlag history."""
    with _neo4j_driver() as driver:
        decayed, _, _ = driver.execute_query(
            """MATCH (r:Requirement)-[v:VERIFIED_TRACE {status:'decayed'}]->(c:CodeEntity)
               WHERE $project IS NULL OR coalesce(r.project, r.repo, r.dataset) = $project
               RETURN r.id AS requirement, c.id AS code, v.confidence AS confidence, v.justification AS reasoning,
                      toString(v.lastCheckedAt) AS checked""", project=project)
        flags, _, _ = driver.execute_query(
            """MATCH (r:Requirement)-[:HAS_DECAY]->(d:DecayFlag)
               WHERE $project IS NULL OR coalesce(r.project, r.repo, r.dataset) = $project
               RETURN r.id AS requirement, d.codeEntityId AS code, d.previousConfidence AS previous,
                      d.reason AS reason, toString(d.flaggedAt) AS at ORDER BY d.flaggedAt DESC LIMIT 100""", project=project)
    return {"decayed": [dict(r) for r in decayed], "flags": [dict(r) for r in flags]}


def file_graph(dataset: str, max_requirements: int = 40) -> dict[str, Any]:
    """Offline preview built from a processed dataset (ground-truth links), used when Neo4j is down."""
    data = load_dataset(dataset)
    reqs = [a for a in data["artifacts"].values() if a["type"] == "requirement"][:max_requirements]
    keep = {a["id"] for a in reqs}
    nodes: dict[str, dict] = {f"r:{a['id']}": {"id": f"r:{a['id']}", "label": a["id"], "kind": "requirement", "text": _trim(a["text"])} for a in reqs}
    edges = []
    for s, t in sorted(data["truth"]):
        if s in keep and t in data["artifacts"]:
            a = data["artifacts"][t]
            nodes.setdefault(f"c:{t}", {"id": f"c:{t}", "label": t, "kind": "code", "codeKind": a["type"], "text": _trim(a["text"])})
            edges.append({"from": f"r:{s}", "to": f"c:{t}", "category": "truth", "confidence": None, "reasoning": "ground-truth link from the dataset", "checked": None})
    return {"source": "files", "nodes": list(nodes.values()), "edges": edges}


# ---------------------------------------------------------------- pipeline stages and run summaries
def pipeline_stages(
    pipeline_events: list[dict[str, Any]],
    monitor_events: list[dict[str, Any]],
    neo4j: dict[str, Any],
    interrupted: bool = False,
) -> list[dict[str, Any]]:
    """The seven pipeline stages with a state (pending / active / done / skipped / interrupted).

    ``interrupted`` means no process is running, so a stage that was ``active`` was cut off (crash, stop).
    """
    start = next((e for e in pipeline_events if e["type"] == "run_start"), None)
    end = next((e for e in pipeline_events if e["type"] == "run_end"), None)
    shortlist = [e for e in pipeline_events if e["type"] == "shortlist"]
    verify = next((e for e in pipeline_events if e["type"] == "verify_start"), None)
    verdicts = [e for e in pipeline_events if e["type"] == "verdict"]
    kept = sum(1 for v in verdicts if v["kept"])
    stages: list[dict[str, Any]] = []

    def add(key: str, title: str, state: str, detail: str) -> None:
        stages.append({"key": key, "title": title, "state": state, "detail": detail})

    n_src = len(start.get("sources", [])) if start else 0
    add("load", "Load artifacts", "done" if start else "pending",
        f"{n_src} requirements x {start.get('n_targets')} code entities from {start.get('dataset')}" if start else "waiting for a run")
    clean_done = bool(shortlist)
    add("clean", "Clean and chunk text", "done" if clean_done else ("active" if start else "pending"),
        "imports stripped, identifiers split, 60-word chunks")
    s1_done = bool(start) and len(shortlist) >= n_src > 0
    cands = sum(len(e["targets"]) for e in shortlist)
    add("stage1", "Stage 1: shortlist", "done" if s1_done else ("active" if clean_done else "pending"),
        f"{cands} candidates, top-{start.get('top_k')} per requirement ({start.get('retrieval')})" if start else "TF-IDF + embeddings")
    total = verify["total"] if verify else None
    llm_done = bool(end) or (total is not None and len(verdicts) >= total)
    lat = [v["latency"] for v in verdicts]
    add("llm", "Stage 2: LLM verification", "done" if llm_done else ("active" if verify else "pending"),
        f"{len(verdicts)}/{total if total is not None else '?'} verdicts, {kept} kept" + (f", mean {sum(lat) / len(lat):.0f}s each" if lat else ""))
    method = (start or {}).get("method")
    if method == "full":
        add("save", "Save VERIFIED_TRACE to USKG", "skipped", "evaluation run: nothing is written to the graph")
    else:
        add("save", "Save VERIFIED_TRACE to USKG", "done" if (end and end.get("written")) else ("active" if verify and not end else "pending"),
            f"{kept} links written as they are confirmed" if start else "edges written with confidence and justification")
    mstart = next((e for e in monitor_events if e["type"] == "run_start"), None)
    mend = next((e for e in monitor_events if e["type"] == "run_end"), None)
    rechecks = [e for e in monitor_events if e["type"] == "recheck"]
    add("monitor", "Monitor decay", "done" if mend else ("active" if mstart else "pending"),
        f"{len(rechecks)} re-checked, {sum(1 for r in rechecks if r['decayed'])} decayed" if mstart else "no monitor pass yet")
    if interrupted:
        for st in stages:
            if st["state"] == "active":
                st["state"] = "interrupted"
    counts = neo4j.get("counts") or {}
    add("score", "Completeness and orphans", "done" if counts.get("verified_traces") else "pending",
        f"{counts.get('verified_traces', 0)} links in the USKG" if neo4j.get("connected") else "needs Neo4j")
    return stages


def runs_summary(idle: bool = False) -> list[dict[str, Any]]:
    """One summary row per recorded run, newest first.

    Args:
        idle: True when no process is running, so any run without a ``run_end`` was interrupted.
    """
    rows = []
    if not RUNS_DIR.exists():
        return rows
    live_slot = not idle  # one process runs at a time: only the newest unfinished run can be it
    for d in sorted((d for d in RUNS_DIR.iterdir() if (d / "events.jsonl").exists()), reverse=True):
        events = read_events(d)
        start = next((e for e in events if e["type"] == "run_start"), None)
        if start is None:
            continue
        end = next((e for e in events if e["type"] == "run_end"), None)
        if d.name.endswith("-monitor"):
            rechecks = [e for e in events if e["type"] == "recheck"]
            state = "finished"
            if not end:
                state = "running" if live_slot else "interrupted"
                live_slot = False
            rows.append({"id": d.name, "kind": "monitor", "state": state, "started": start["ts"],
                         "rechecked": len(rechecks), "decayed": sum(1 for r in rechecks if r["decayed"])})
            continue
        truth = load_dataset(start["dataset"])["truth"] if start.get("dataset") in {p.name for p in PROCESSED_DIR.iterdir()} else set()
        summary = summarize_run(events, truth)
        if summary["state"] != "finished":
            if not live_slot:
                summary["state"] = "interrupted"
            live_slot = False
        rows.append({"id": d.name, "kind": start.get("method"), "dataset": start.get("dataset"), "retrieval": start.get("retrieval"),
                     "prompt": start.get("prompt"), "top_k": start.get("top_k"), "state": summary["state"], "started": start["ts"],
                     "done": summary.get("done"), "total": summary.get("total"), "kept": summary.get("kept"),
                     "precision": summary.get("precision"), "recall": summary.get("recall"), "f1": summary.get("f1"),
                     "mean_latency": summary.get("mean_latency"), "scored": bool(truth)})
    return rows


RESULTS_FILE = PROJECT_ROOT / "data" / "results" / "summary.json"


def load_results() -> dict[str, Any]:
    """Measured evaluation results recorded in data/results/summary.json (plus any saved decay-injection report)."""
    data = json.loads(RESULTS_FILE.read_text(encoding="utf-8")) if RESULTS_FILE.exists() else {}
    decay_files = sorted((RESULTS_FILE.parent).glob("decay_injection_*.json"))
    data["decay_injection"] = json.loads(decay_files[-1].read_text(encoding="utf-8")) if decay_files else None
    return data


def redis_status() -> dict[str, Any]:
    """Whether the redis package is installed and a server answers (decay events need both)."""
    try:
        import redis
    except ImportError:
        return {"installed": False, "reachable": False}
    try:
        redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=1).ping()
        return {"installed": True, "reachable": True}
    except Exception:
        return {"installed": True, "reachable": False}
