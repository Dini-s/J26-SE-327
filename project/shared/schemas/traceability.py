"""Pydantic models shared by every agent that reads or writes traceability data."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ArtifactType = Literal["requirement", "code", "test", "design"]
LinkStatus = Literal["verified", "decayed"]


class Artifact(BaseModel):
    """A single software artifact (requirement, code unit, test, design doc).

    In the USKG, requirements are ``Requirement`` nodes (owned by C1) and every
    other type is a ``CodeEntity`` node (owned by C2) distinguished by ``kind``.

    Attributes:
        id: Unique identifier of the artifact in the USKG.
        type: Kind of artifact.
        text: The textual content used for embedding and LLM verification.
        metadata: Any extra properties stored on the graph node.
    """

    id: str
    type: ArtifactType
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceabilityLink(BaseModel):
    """A directed trace from a source artifact to a target artifact.

    Maps onto a ``VERIFIED_TRACE`` edge (Requirement -> CodeEntity) in the USKG.

    Attributes:
        source_id: Id of the source artifact (the requirement).
        target_id: Id of the target artifact.
        link_type: Label such as ``"requirement_to_code"``.
        confidence: Verifier confidence in ``[0, 1]``.
        justification: Plain-language explanation of the verdict.
        status: ``verified`` or ``decayed``.
        text_hash: Hash of both texts at verification time (for change detection).
        verified_at: When the link was first verified.
        last_checked_at: When it was last (re-)verified.
    """

    source_id: str
    target_id: str
    link_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str
    status: LinkStatus = "verified"
    text_hash: Optional[str] = None
    verified_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None


class TraceabilityRequest(BaseModel):
    """Input to the traceability agent: which artifacts to relate."""

    source_artifacts: list[Artifact]
    target_artifacts: list[Artifact]


class TraceabilityResponse(BaseModel):
    """Output of the traceability agent: the confirmed links."""

    links: list[TraceabilityLink]


class CompletenessResult(BaseModel):
    """Traceability completeness of one requirement.

    Attributes:
        requirement_id: The requirement scored.
        score: 0-100, how trustworthy its traceability currently is.
        is_orphan: True if it has no verified trace link at all.
        trace_confidence: Mean confidence of its verified links (None if orphan).
        evidence_coverage: C3 evidence coverage in ``[0, 1]`` (None if unavailable).
    """

    requirement_id: str
    score: float = Field(ge=0.0, le=100.0)
    is_orphan: bool
    trace_confidence: Optional[float] = None
    evidence_coverage: Optional[float] = None
