"""Demo-only controls for showing the whole flow without C1/C2/C3.

In the real system C1 writes ``Requirement`` nodes and C2 writes ``CodeEntity`` nodes and keeps
them in sync with GitHub. For a demo (or a viva) these helpers stand in for them:

* ``modify`` - edit a CodeEntity's text, i.e. what C2 would do when a commit changes a file,
* ``add_requirement`` - a new requirement typed into the dashboard (what C1 would create),
* ``reset``  - delete C4's own results (VERIFIED_TRACE, DecayFlag), the dashboard-created requirements, and undo ``modify``.

Safety: only enabled for a local Neo4j (localhost / 127.0.0.1) and only touches nodes that carry a
``dataset`` property (set by scripts/load_to_neo4j.ipynb), never anything a teammate created.
Set DASHBOARD_ALLOW_DEMO=0 to disable.
"""

import os
import re
from typing import Any, Optional
from urllib.parse import urlparse

from apps.api.sources import _neo4j_driver

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class DemoError(ValueError):
    """The requested demo action cannot be performed."""


def allowed() -> dict[str, Any]:
    """Whether demo writes are enabled, and why not if they are not."""
    if os.getenv("DASHBOARD_ALLOW_DEMO", "1") == "0":
        return {"allowed": False, "reason": "disabled (DASHBOARD_ALLOW_DEMO=0)"}
    host = urlparse(os.getenv("NEO4J_URI", "bolt://localhost:7687")).hostname
    if host not in LOCAL_HOSTS:
        return {"allowed": False, "reason": f"Neo4j host {host!r} is not local; demo writes only run against a local database"}
    return {"allowed": True, "reason": ""}


def _require_allowed() -> None:
    state = allowed()
    if not state["allowed"]:
        raise DemoError(state["reason"])


def mutation_functions() -> dict[str, Any]:
    """Name -> function for each text edit the demo can apply."""
    from agents.traceability_agent.decay_injection import BREAKING_MUTATIONS, CONTROL_MUTATION

    return {**BREAKING_MUTATIONS, CONTROL_MUTATION[0]: CONTROL_MUTATION[1]}


def linked_code_entities(limit: int = 150, project: Optional[str] = None) -> list[dict[str, Any]]:
    """Demo code entities that currently have a VERIFIED_TRACE (the ones worth editing)."""
    with _neo4j_driver() as driver:
        records, _, _ = driver.execute_query(
            """MATCH (r:Requirement)-[v:VERIFIED_TRACE]->(c:CodeEntity)
               WHERE c.dataset IS NOT NULL AND ($project IS NULL OR coalesce(c.project, c.repo, c.dataset) = $project)
               RETURN c.id AS id, collect(DISTINCT r.id) AS requirements, max(v.status) AS status,
                      c.original_text IS NOT NULL AS modified, left(coalesce(c.text,''), 140) AS preview
               ORDER BY id LIMIT $n""", n=limit, project=project)
    return [dict(r) for r in records]


NEW_DATASET = "demo-new"  # marks requirements typed into the dashboard, so they can be told apart and removed
_ID = re.compile(r"[A-Za-z0-9._-]{1,40}")


def add_requirement(text: str, requirement_id: str = "", project: Optional[str] = None) -> dict[str, Any]:
    """Create a new ``Requirement`` node from text typed into the dashboard (stands in for C1).

    It joins ``project`` (so it is linked against that project's code only); without one it gets the
    generic ``demo-new`` dataset. Either way it carries ``demo_added`` so a reset can remove it.

    Raises:
        DemoError: If the text is too short/long, the id is malformed, or the id already exists.
    """
    _require_allowed()
    text = " ".join(text.split())
    if not 15 <= len(text) <= 2000:
        raise DemoError("Write the requirement as a full sentence (15 to 2000 characters).")
    requirement_id = requirement_id.strip()
    if requirement_id and not _ID.fullmatch(requirement_id):
        raise DemoError("The id may only contain letters, digits, '.', '_' and '-' (max 40 characters).")
    with _neo4j_driver() as driver:
        if not requirement_id:
            records, _, _ = driver.execute_query("MATCH (r:Requirement) WHERE r.id STARTS WITH 'NEW-' RETURN r.id AS id")
            used = {int(m.group(1)) for r in records if (m := re.fullmatch(r"NEW-(\d+)", r["id"]))}
            requirement_id = f"NEW-{next(i for i in range(1, 10_000) if i not in used):03d}"
        exists, _, _ = driver.execute_query("MATCH (r:Requirement {id: $id}) RETURN r.id AS id", id=requirement_id)
        if exists:
            raise DemoError(f"A requirement with id {requirement_id!r} already exists.")
        driver.execute_query("CREATE (:Requirement {id: $id, text: $text, dataset: $ds, demo_added: true})",
                             id=requirement_id, text=text, ds=project or NEW_DATASET)
    return {"id": requirement_id, "text": text, "project": project}


def undo_changes(project: Optional[str] = None) -> dict[str, Any]:
    """Restore demo code texts edited with ``modify`` and un-decay the links that decayed because of them.

    Only touches nodes with a ``dataset`` property and C4's own DecayFlag / VERIFIED_TRACE data.
    """
    _require_allowed()
    with _neo4j_driver() as driver:
        _, s1, _ = driver.execute_query(
            "MATCH (c:CodeEntity) WHERE c.dataset IS NOT NULL AND c.original_text IS NOT NULL "
            "AND ($project IS NULL OR coalesce(c.project, c.repo, c.dataset) = $project) "
            "SET c.text = c.original_text REMOVE c.original_text", project=project)
        _, s2, _ = driver.execute_query(
            """MATCH (r:Requirement)-[:HAS_DECAY]->(f:DecayFlag), (r)-[v:VERIFIED_TRACE]->(c:CodeEntity {id: f.codeEntityId})
               WHERE $project IS NULL OR coalesce(r.project, r.repo, r.dataset) = $project
               SET v.status = 'verified', v.confidence = f.previousConfidence
               WITH DISTINCT f DETACH DELETE f""", project=project)
    return {"restored_texts": s1.counters.properties_set // 2 if s1.counters.properties_set else 0, "flags_removed": s2.counters.nodes_deleted}


def modify(code_id: str, mutation: str) -> dict[str, Any]:
    """Edit a demo CodeEntity's text the way a commit would; the original is kept for ``reset``."""
    _require_allowed()
    funcs = mutation_functions()
    if mutation not in funcs:
        raise DemoError(f"Unknown mutation {mutation!r}")
    with _neo4j_driver() as driver:
        records, _, _ = driver.execute_query(
            "MATCH (c:CodeEntity {id: $id}) WHERE c.dataset IS NOT NULL RETURN c.text AS text", id=code_id)
        if not records:
            raise DemoError(f"{code_id!r} is not a demo code entity (no dataset property)")
        before = records[0]["text"] or ""
        after = funcs[mutation](before)
        if after == before:
            raise DemoError(f"'{mutation}' changes nothing in this text; try another edit")
        driver.execute_query(
            "MATCH (c:CodeEntity {id: $id}) SET c.original_text = coalesce(c.original_text, c.text), c.text = $new",
            id=code_id, new=after)
    return {"code_id": code_id, "mutation": mutation, "before": before[:500], "after": after[:500]}


def reset(project: Optional[str] = None) -> dict[str, Any]:
    """Delete C4's own results (VERIFIED_TRACE edges, DecayFlag nodes) and restore edited demo texts.

    With ``project`` only that project is reset; the others keep their results.
    """
    _require_allowed()
    with _neo4j_driver() as driver:
        _, s1, _ = driver.execute_query(
            "MATCH (r:Requirement)-[v:VERIFIED_TRACE]->() WHERE $project IS NULL OR coalesce(r.project, r.repo, r.dataset) = $project DELETE v", project=project)
        _, s2, _ = driver.execute_query(
            "MATCH (r:Requirement)-[:HAS_DECAY]->(d:DecayFlag) WHERE $project IS NULL OR coalesce(r.project, r.repo, r.dataset) = $project DETACH DELETE d",
            project=project)
        _, s3, _ = driver.execute_query(
            "MATCH (c:CodeEntity) WHERE c.dataset IS NOT NULL AND c.original_text IS NOT NULL "
            "AND ($project IS NULL OR coalesce(c.project, c.repo, c.dataset) = $project) "
            "SET c.text = c.original_text REMOVE c.original_text", project=project)
        driver.execute_query(
            "MATCH (r:Requirement) WHERE (r.dataset = $ds OR r.demo_added = true) "
            "AND ($project IS NULL OR coalesce(r.project, r.repo, r.dataset) = $project OR r.dataset = $ds) DETACH DELETE r", ds=NEW_DATASET, project=project)
    return {"deleted_links": s1.counters.relationships_deleted, "deleted_flags": s2.counters.nodes_deleted,
            "restored_texts": s3.counters.properties_set // 2 if s3.counters.properties_set else 0}
