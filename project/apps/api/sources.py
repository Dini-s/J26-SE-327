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
def latest_run_dir(runs_dir: Path = RUNS_DIR) -> Optional[Path]:
    """Newest run directory that has an events file (names start with a timestamp)."""
    if not runs_dir.exists():
        return None
    runs = sorted(d for d in runs_dir.iterdir() if (d / "events.jsonl").exists())
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
        elif v["kept"]:
            category = "verified_correct" if is_true else "verified_wrong"
        else:
            category = "rejected_true" if is_true else "rejected"
        edges.append(
            {"from": f"r:{s}", "to": f"c:{t}", "category": category, "truth": is_true, "similarity": score,
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
