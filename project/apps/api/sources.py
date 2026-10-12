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


# ---------------------------------------------------------------- pipeline stages and run summaries
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
