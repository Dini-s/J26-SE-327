"""In-memory stand-in for USKGClient (same interface), for offline evaluation and tests."""

from datetime import datetime, timezone
from typing import Iterable, Optional

from shared.schemas.traceability import Artifact, TraceabilityLink


class InMemoryUSKG:
    """Holds artifacts and traces in dicts; no Neo4j needed."""

    def __init__(
        self,
        artifacts: Iterable[Artifact] = (),
        traces: Iterable[TraceabilityLink] = (),
    ) -> None:
        """Create the store.

        Args:
            artifacts: Initial artifacts.
            traces: Initial ``VERIFIED_TRACE`` links.
        """
        self.artifacts: dict[str, Artifact] = {a.id: a for a in artifacts}
        self.traces: dict[tuple[str, str], TraceabilityLink] = {
            (t.source_id, t.target_id): t for t in traces
        }
        self.decay_flags: list[dict] = []

    @staticmethod
    def _project_of(artifact: Artifact) -> Optional[str]:
        meta = artifact.metadata
        return meta.get("project") or meta.get("repo") or meta.get("dataset")

    def get_artifacts(self, artifact_type: str, project: Optional[str] = None) -> list[Artifact]:
        """Artifacts of one type, optionally only those of one project."""
        return [
            a for a in self.artifacts.values()
            if a.type == artifact_type and (project is None or self._project_of(a) == project)
        ]

    def get_traces(self, status: Optional[str] = None, project: Optional[str] = None) -> list[TraceabilityLink]:
        """Stored links, optionally filtered by status and by the project of the requirement."""
        return [
            t for t in self.traces.values()
            if (status is None or t.status == status)
            and (project is None or (t.source_id in self.artifacts and self._project_of(self.artifacts[t.source_id]) == project))
        ]

    def write_link(self, link: TraceabilityLink) -> bool:
        """Upsert a link keyed by (source, target); preserves the original verified_at."""
        now = datetime.now(timezone.utc)
        existing = self.traces.get((link.source_id, link.target_id))
        self.traces[(link.source_id, link.target_id)] = link.model_copy(
            update={
                "verified_at": existing.verified_at if existing and existing.verified_at else now,
                "last_checked_at": now,
            }
        )
        return True

    def resolve_decay(self, link: TraceabilityLink) -> int:
        """Mark the open flags of a link resolved; returns how many were closed."""
        n = 0
        for flag in self.decay_flags:
            if flag["source_id"] == link.source_id and flag["target_id"] == link.target_id and not flag.get("resolved"):
                flag["resolved"] = True
                n += 1
        return n

    def mark_decayed(self, link: TraceabilityLink, new_confidence: float, reason: str, text_hash: Optional[str] = None) -> bool:
        """Mark a stored link decayed and record a flag (the link is kept)."""
        key = (link.source_id, link.target_id)
        current = self.traces.get(key)
        if current is None:
            return False
        self.decay_flags.append(
            {
                "source_id": link.source_id,
                "target_id": link.target_id,
                "previous_confidence": current.confidence,
                "reason": reason,
            }
        )
        self.traces[key] = current.model_copy(
            update={
                "status": "decayed",
                "confidence": new_confidence,
                "text_hash": text_hash or current.text_hash,
                "last_checked_at": datetime.now(timezone.utc),
            }
        )
        return True
