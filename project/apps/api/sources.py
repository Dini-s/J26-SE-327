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


def neo4j_unlinked(project: Optional[str]) -> dict[str, Any]:
    """Requirements of a project that no VERIFIED_TRACE starts from yet, plus how many requirements / code files it has."""
    with _neo4j_driver() as driver:
        rows, _, _ = driver.execute_query(
            """MATCH (r:Requirement) WHERE coalesce(r.project, r.repo, r.dataset) = $project
               RETURN r.id AS id, EXISTS { (r)-[:VERIFIED_TRACE]->() } AS linked ORDER BY r.id""", project=project)
        code, _, _ = driver.execute_query(
            """MATCH (c:CodeEntity) WHERE coalesce(c.kind,'code') = 'code' AND coalesce(c.project, c.repo, c.dataset) = $project
               RETURN count(c) AS n""", project=project)
        links, _, _ = driver.execute_query(
            """MATCH (r:Requirement)-[v:VERIFIED_TRACE]->() WHERE coalesce(r.project, r.repo, r.dataset) = $project
               RETURN count(v) AS n""", project=project)
    unlinked = [r["id"] for r in rows if not r["linked"]]
    return {"requirements": len(rows), "unlinked": len(unlinked), "ids": unlinked[:200], "codeFiles": code[0]["n"], "links": links[0]["n"]}


# ---------------------------------------------------------------- USKG graph (Neo4j)
def _trim(text: Any, n: int = 1200) -> str:
    return (text or "")[:n]


GRAPH_MODES = ("links", "code", "requirements", "all")
# kind shown in the dashboard for each label a component may write (first match wins); everything is read-only here
_KIND_BY_LABEL = [("Repository", "repository"), ("Package", "package"), ("CodeFile", "code"), ("CodeEntity", "code"),
                  ("EvolutionFeature", "evolution"), ("Finding", "finding"), ("Document", "document"), ("UserStory", "story"),
                  ("AcceptanceCriterion", "criterion"), ("TechnicalTask", "task"), ("AnalysisFinding", "analysis"),
                  ("Risk", "risk"), ("Requirement", "requirement")]
_CODE_LABELS = ["Repository", "Package", "CodeEntity", "EvolutionFeature", "Finding"]
_REQ_LABELS = ["Requirement", "Document", "UserStory", "AcceptanceCriterion", "TechnicalTask", "AnalysisFinding", "Risk"]
_STRUCTURE_RELS = "CONTAINS|DEPENDS_ON|HAS_EVOLUTION|INVOLVES_PACKAGE|FROM_DOCUMENT|HAS_STORY|HAS_CRITERION|HAS_TASK|HAS_FINDING|HAS_RISK|SIMILAR_TO"


def _prop_view(props: dict[str, Any]) -> dict[str, Any]:
    """Short, JSON-safe copy of node properties for the inspector (long text is left to the dedicated text field)."""
    out: dict[str, Any] = {}
    for key, value in props.items():
        if key in ("id", "text", "source", "dataset", "repo", "project"):
            continue
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value)
        out[key] = value if isinstance(value, (int, float, bool)) or value is None else str(value)[:300]
    return out


def _structure(driver: Any, project: Optional[str], labels: list[str], nodes: dict[str, dict], edges: list[dict]) -> None:
    """Add the nodes C1 / C2 wrote for a project (repository, packages, files, requirement details ...) and their relationships."""
    records, _, _ = driver.execute_query(
        """MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels)
             AND ($project IS NULL OR coalesce(n.project, n.repo, n.dataset) = $project)
           RETURN n.id AS id, labels(n) AS labels, properties(n) AS props LIMIT 1500""", labels=labels, project=project)
    key: dict[str, str] = {}
    for r in records:
        kind = next((k for l, k in _KIND_BY_LABEL if l in r["labels"]), None)
        if kind is None or r["id"] is None:
            continue
        gid = f"{'r' if kind == 'requirement' else 'c' if kind == 'code' else 's'}:{r['id']}"
        key[r["id"]] = gid
        props = r["props"]
        label = (r["id"] if kind in ("code", "requirement") else props.get("name") or props.get("cycle_id") or props.get("text") or r["id"])
        if kind == "package":
            label = str(label).rsplit(".", 1)[-1] if not str(label).startswith("templates") else str(label)
        node = nodes.setdefault(gid, {"id": gid, "label": str(label), "kind": kind, "text": _trim(props.get("text"))})
        node["props"] = _prop_view(props)
        if kind == "code":
            node["codeKind"] = props.get("kind", "code")
        if kind == "requirement" and "orphan" in node:
            node.pop("orphan")
    if not key:
        return
    rels, _, _ = driver.execute_query(
        f"""MATCH (a)-[r:{_STRUCTURE_RELS}]->(b) WHERE a.id IN $ids AND b.id IN $ids
            RETURN a.id AS a, type(r) AS rel, b.id AS b, properties(r) AS props""", ids=list(key))
    for r in rels:
        edges.append({"from": key[r["a"]], "to": key[r["b"]], "category": "rel", "rel": r["rel"],
                      "confidence": (r["props"] or {}).get("similarity")})


def neo4j_uskg_graph(max_traces: int = 400, max_orphans: int = 40, project: Optional[str] = None, mode: str = "links") -> dict[str, Any]:
    """The USKG as the dashboard shows it.

    ``links`` (default): requirements, linked code entities, VERIFIED_TRACE edges (verified or decayed), DecayFlag nodes
    with HAS_DECAY edges, plus some orphan requirements. ``code``: the structure C2 wrote (repository, packages, files,
    dependencies, evolution, findings). ``requirements``: the requirements with the C1 details around them. ``all``: everything.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    if mode not in GRAPH_MODES:
        mode = "links"
    if mode in ("code", "requirements"):
        with _neo4j_driver() as driver:
            _structure(driver, project, _CODE_LABELS if mode == "code" else _REQ_LABELS, nodes, edges)
        return {"source": "neo4j", "mode": mode, "nodes": list(nodes.values()), "edges": edges}

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
    if mode == "all":
        with _neo4j_driver() as driver:
            _structure(driver, project, _CODE_LABELS + _REQ_LABELS, nodes, edges)
    return {"source": "neo4j", "mode": mode, "nodes": list(nodes.values()), "edges": edges}


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
