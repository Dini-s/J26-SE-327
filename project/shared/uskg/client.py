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

import os
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

from shared.schemas.traceability import Artifact, TraceabilityLink

_CORE_PROPERTIES = {"id", "type", "text"}

_REQUIREMENTS_QUERY = """
MATCH (n:Requirement)
RETURN n.id AS id, 'requirement' AS type,
       coalesce(n.text, n.description, n.title, '') AS text, properties(n) AS props
"""

_CODE_ENTITIES_QUERY = """
MATCH (n:CodeEntity)
WHERE coalesce(n.kind, 'code') = $type
RETURN n.id AS id, coalesce(n.kind, 'code') AS type,
       coalesce(n.text, n.source, n.code, n.signature, '') AS text, properties(n) AS props
"""

_GET_TRACES_QUERY = """
MATCH (r:Requirement)-[v:VERIFIED_TRACE]->(c:CodeEntity)
WHERE $status IS NULL OR v.status = $status
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
SET v.status = 'decayed', v.confidence = $new_confidence, v.lastCheckedAt = datetime()
CREATE (r)-[:HAS_DECAY]->(d:DecayFlag {
    codeEntityId: $target_id, flaggedAt: datetime(),
    previousConfidence: previous, reason: $reason})
RETURN count(d) AS flagged
"""


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
        def work(tx: Any) -> int:
            record = tx.run(query, **params).single()
            return int(record[key]) if record else 0

        with self._driver.session() as session:
            return session.execute_write(work)

    def get_artifacts(self, artifact_type: str) -> list[Artifact]:
        """Fetch all artifacts of one type (read-only).

        Args:
            artifact_type: ``requirement`` reads ``Requirement`` nodes; any other
                type reads ``CodeEntity`` nodes whose ``kind`` matches.

        Returns:
            The matching artifacts; extra node properties land in ``metadata``.
        """
        if artifact_type == "requirement":
            rows = self._read(_REQUIREMENTS_QUERY)
        else:
            rows = self._read(_CODE_ENTITIES_QUERY, type=artifact_type)
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

    def get_traces(self, status: Optional[str] = None) -> list[TraceabilityLink]:
        """Fetch existing ``VERIFIED_TRACE`` edges.

        Args:
            status: Only return edges with this status (``verified``/``decayed``).

        Returns:
            The edges as links.
        """
        links = []
        for row in self._read(_GET_TRACES_QUERY, status=status):
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

    def mark_decayed(self, link: TraceabilityLink, new_confidence: float, reason: str) -> bool:
        """Mark an edge decayed and attach a ``DecayFlag``, without deleting the edge.

        Args:
            link: The link that decayed (identifies the edge).
            new_confidence: Confidence from the failed re-verification.
            reason: Why it decayed (the verifier's justification).

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
            )
            > 0
        )
