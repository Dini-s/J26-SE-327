"""Neo4j (USKG) access shared by all agents.

Graph model (system spec):
    (:Requirement {id, text})                         written by C1 - read only here
    (:CodeEntity {id, text, kind?})                   written by C2 - read only here
    (:Requirement)-[:VERIFIED_TRACE {confidence, justification, status,
                    verifiedAt, lastCheckedAt, ...}]->(:CodeEntity)    written by C4
    (:Requirement)-[:HAS_DECAY]->(:DecayFlag {...})                    written by C4

Assumptions to confirm with C1/C2: the text property names (the queries try
``text`` first, then common alternatives), and that ``CodeEntity.kind`` (default
``code``) distinguishes code from test/design entities.

Write ownership: the only write statements in this module create/update
``VERIFIED_TRACE`` edges and ``DecayFlag`` nodes; every other node type is only
ever matched, never created, modified or deleted.
"""

import logging
import os
import re
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

from shared.schemas.traceability import Artifact, TraceabilityLink

# The read queries try several property names for an entity's text (text, source, code, ...), because
# C1/C2's exact names are not confirmed. Neo4j warns about every name that does not exist yet; silence that.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

_CORE_PROPERTIES = {"id", "type", "text"}

# A "project" is one repository / dataset. It is read from whichever property the producing component sets
# (project, repo, or the demo loader's dataset), so one graph can hold many projects without a schema change.
_REQUIREMENTS_QUERY = """
MATCH (n:Requirement)
WHERE $project IS NULL OR coalesce(n.project, n.repo, n.dataset) = $project
RETURN n.id AS id, 'requirement' AS type,
       coalesce(n.text, n.description, n.title, '') AS text, properties(n) AS props
"""

_CODE_ENTITIES_QUERY = """
MATCH (n:CodeEntity)
WHERE coalesce(n.kind, 'code') = $type
  AND ($project IS NULL OR coalesce(n.project, n.repo, n.dataset) = $project)
RETURN n.id AS id, coalesce(n.kind, 'code') AS type,
       coalesce(n.text, n.source, n.code, n.signature, '') AS text, properties(n) AS props
"""

_PROJECTS_QUERY = """
MATCH (n) WHERE (n:Requirement OR n:CodeEntity) AND coalesce(n.project, n.repo, n.dataset) IS NOT NULL
WITH coalesce(n.project, n.repo, n.dataset) AS project,
     sum(CASE WHEN n:Requirement THEN 1 ELSE 0 END) AS requirements,
     sum(CASE WHEN n:CodeEntity THEN 1 ELSE 0 END) AS code_entities
OPTIONAL MATCH (r:Requirement)-[v:VERIFIED_TRACE]->()
WHERE coalesce(r.project, r.repo, r.dataset) = project
RETURN project, requirements, code_entities, count(v) AS links,
       sum(CASE WHEN v.status = 'decayed' THEN 1 ELSE 0 END) AS decayed
ORDER BY project
"""

_GET_TRACES_QUERY = """
MATCH (r:Requirement)-[v:VERIFIED_TRACE]->(c:CodeEntity)
WHERE ($status IS NULL OR v.status = $status)
  AND ($project IS NULL OR coalesce(r.project, r.repo, r.dataset) = $project)
RETURN r.id AS source_id, c.id AS target_id, properties(v) AS props
"""

# MERGE on the (requirement, code entity) pair makes the write idempotent: re-running
# updates the existing edge, never duplicates it. verifiedAt is only set on creation.
_WRITE_LINK_QUERY = """
MATCH (r:Requirement {id: $source_id}), (c:CodeEntity {id: $target_id})
MERGE (r)-[v:VERIFIED_TRACE]->(c)
ON CREATE SET v.verifiedAt = datetime()
SET v.confidence = $confidence, v.justification = $justification, v.status = $status,
    v.linkType = $link_type, v.textHash = $text_hash, v.lastCheckedAt = datetime()
RETURN count(v) AS written
"""

# The edge is kept (history is preserved); it is only marked decayed. A relationship
# cannot itself be the endpoint of another relationship in Neo4j, so the DecayFlag hangs
# off the requirement via HAS_DECAY and records which code entity it concerns.
_MARK_DECAYED_QUERY = """
MATCH (r:Requirement {id: $source_id})-[v:VERIFIED_TRACE]->(c:CodeEntity {id: $target_id})
WITH r, v, v.confidence AS previous
SET v.status = 'decayed', v.confidence = $new_confidence, v.lastCheckedAt = datetime(),
    v.textHash = coalesce($text_hash, v.textHash)
CREATE (r)-[:HAS_DECAY]->(d:DecayFlag {
    codeEntityId: $target_id, flaggedAt: datetime(),
    previousConfidence: previous, reason: $reason})
RETURN count(d) AS flagged
"""


_WRITE_QUERIES = frozenset({_WRITE_LINK_QUERY, _MARK_DECAYED_QUERY})

# --- write ownership -------------------------------------------------------------------
# C4 may only create/modify VERIFIED_TRACE edges, DecayFlag nodes and HAS_DECAY edges.
# Every write goes through USKGClient._write_count, which only runs statements from this
# registry after checking them, so a future edit cannot quietly write C1/C2/C3 types.
# (This is a code-level guard; Neo4j Community has no role-based access control.)
OWNED_WRITE_TYPES = frozenset({"VERIFIED_TRACE", "DecayFlag", "HAS_DECAY"})
_FORBIDDEN_WRITE_KEYWORDS = re.compile(r"\b(DELETE|DETACH|REMOVE|DROP)\b", re.IGNORECASE)
_PATTERN_TYPES = re.compile(r"[(\[]\s*\w*\s*:\s*(\w+)")  # labels and rel types: (x:Label) / [x:TYPE]


def validate_write_query(query: str) -> None:
    """Reject a write statement that could touch types C4 does not own.

    Every MERGE/CREATE may only mention owned labels/relationship types, and
    DELETE/REMOVE/DROP are never allowed.

    Raises:
        PermissionError: If the statement violates the ownership rules.
    """
    if _FORBIDDEN_WRITE_KEYWORDS.search(query):
        raise PermissionError("C4 write layer: DELETE/REMOVE/DROP statements are not allowed")
    for line in query.splitlines():
        if re.match(r"\s*(MERGE|CREATE)\b", line, re.IGNORECASE) or re.search(r"\bCREATE\b|\bMERGE\b", line):
            for name in _PATTERN_TYPES.findall(line):
                if name not in OWNED_WRITE_TYPES:
                    raise PermissionError(f"C4 write layer: {name!r} is owned by another component")


# Plain (non-unique) indexes: they make the id lookups in write_link / get_traces O(log n)
# instead of a full scan, without constraining how C1/C2 create their nodes.
SCHEMA_STATEMENTS = [
    "CREATE INDEX requirement_id IF NOT EXISTS FOR (n:Requirement) ON (n.id)",
    "CREATE INDEX codeentity_id IF NOT EXISTS FOR (n:CodeEntity) ON (n.id)",
    "CREATE INDEX codeentity_kind IF NOT EXISTS FOR (n:CodeEntity) ON (n.kind)",
    "CREATE INDEX verified_trace_status IF NOT EXISTS FOR ()-[v:VERIFIED_TRACE]-() ON (v.status)",
    "CREATE INDEX decayflag_code IF NOT EXISTS FOR (d:DecayFlag) ON (d.codeEntityId)",
]


def _to_datetime(value: Any) -> Optional[datetime]:
    """Convert a neo4j temporal value (or None) to a native datetime."""
    if value is None:
        return None
    return value.to_native() if hasattr(value, "to_native") else value


class USKGClient:
    """Reads the shared graph and writes this component's trace links and decay flags."""

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        driver: Optional[Driver] = None,
    ) -> None:
        """Connect to Neo4j.

        Args:
            uri: Bolt URI; defaults to ``NEO4J_URI``.
            username: Defaults to ``NEO4J_USERNAME``.
            password: Defaults to ``NEO4J_PASSWORD``.
            driver: Pre-built driver, mainly for tests (skips creating a real one).
        """
        load_dotenv()
        if driver is None:
            driver = GraphDatabase.driver(
                uri or os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                auth=(
                    username or os.getenv("NEO4J_USERNAME", "neo4j"),
                    password or os.getenv("NEO4J_PASSWORD", ""),
                ),
            )
        self._driver = driver

    def close(self) -> None:
        """Close the underlying driver."""
        self._driver.close()

    def __enter__(self) -> "USKGClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def _read(self, query: str, **params: Any) -> list[dict[str, Any]]:
        def work(tx: Any) -> list[dict[str, Any]]:
            return [record.data() for record in tx.run(query, **params)]

        with self._driver.session() as session:
            return session.execute_read(work)

    def _write_count(self, query: str, key: str, **params: Any) -> int:
        if query not in _WRITE_QUERIES:
            raise PermissionError("C4 write layer: only the vetted write statements may run")
        validate_write_query(query)

        def work(tx: Any) -> int:
            record = tx.run(query, **params).single()
            return int(record[key]) if record else 0

        with self._driver.session() as session:
            return session.execute_write(work)

    def ensure_schema(self) -> list[str]:
        """Create the indexes the trace queries rely on (idempotent).

        Returns:
            The statements that were run.
        """
        for statement in SCHEMA_STATEMENTS:
            self._driver.execute_query(statement)
        return list(SCHEMA_STATEMENTS)

    def list_projects(self) -> list[dict[str, Any]]:
        """Projects (repositories) in the graph with their node and link counts (read-only)."""
        return self._read(_PROJECTS_QUERY)

    def get_artifacts(self, artifact_type: str, project: Optional[str] = None) -> list[Artifact]:
        """Fetch all artifacts of one type (read-only).

        Args:
            artifact_type: ``requirement`` reads ``Requirement`` nodes; any other
                type reads ``CodeEntity`` nodes whose ``kind`` matches.
            project: Only artifacts of this project / repository; ``None`` reads all.

        Returns:
            The matching artifacts; extra node properties land in ``metadata``.
        """
        if artifact_type == "requirement":
            rows = self._read(_REQUIREMENTS_QUERY, project=project)
        else:
            rows = self._read(_CODE_ENTITIES_QUERY, type=artifact_type, project=project)
        return [
            Artifact(
                id=str(row["id"]),
                type=row["type"],
                text=row["text"] or "",
                metadata={k: v for k, v in row["props"].items() if k not in _CORE_PROPERTIES},
            )
            for row in rows
            if row["id"] is not None
        ]

    def get_traces(self, status: Optional[str] = None, project: Optional[str] = None) -> list[TraceabilityLink]:
        """Fetch existing ``VERIFIED_TRACE`` edges.

        Args:
            status: Only return edges with this status (``verified``/``decayed``).
            project: Only edges whose requirement belongs to this project; ``None`` reads all.

        Returns:
            The edges as links.
        """
        links = []
        for row in self._read(_GET_TRACES_QUERY, status=status, project=project):
            p = row["props"]
            links.append(
                TraceabilityLink(
                    source_id=row["source_id"],
                    target_id=row["target_id"],
                    link_type=p.get("linkType", "requirement_to_code"),
                    confidence=p.get("confidence", 0.0),
                    justification=p.get("justification", ""),
                    status=p.get("status", "verified"),
                    text_hash=p.get("textHash"),
                    verified_at=_to_datetime(p.get("verifiedAt")),
                    last_checked_at=_to_datetime(p.get("lastCheckedAt")),
                )
            )
        return links

    def write_link(self, link: TraceabilityLink) -> bool:
        """Create or update a ``VERIFIED_TRACE`` edge, idempotently.

        Returns:
            True if written; False if either endpoint node does not exist.
        """
        return (
            self._write_count(
                _WRITE_LINK_QUERY,
                "written",
                source_id=link.source_id,
                target_id=link.target_id,
                confidence=link.confidence,
                justification=link.justification,
                status=link.status,
                link_type=link.link_type,
                text_hash=link.text_hash,
            )
            > 0
        )

    def mark_decayed(self, link: TraceabilityLink, new_confidence: float, reason: str, text_hash: Optional[str] = None) -> bool:
        """Mark an edge decayed and attach a ``DecayFlag``, without deleting the edge.

        Args:
            link: The link that decayed (identifies the edge).
            new_confidence: Confidence from the failed re-verification.
            reason: Why it decayed (the verifier's justification).
            text_hash: Hash of the text that was just checked; stored so the monitor re-checks a decayed
                link only when its text changes again (e.g. after a revert), not on every pass.

        Returns:
            True if the edge existed and was flagged.
        """
        return (
            self._write_count(
                _MARK_DECAYED_QUERY,
                "flagged",
                source_id=link.source_id,
                target_id=link.target_id,
                new_confidence=new_confidence,
                reason=reason,
                text_hash=text_hash,
            )
            > 0
        )
