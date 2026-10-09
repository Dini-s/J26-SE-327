from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class AcceptanceCriterion(BaseModel):
    ac_id: str
    text: str


class RequirementRecord(BaseModel):
    requirement_id: str
    title: str
    text: str

    type: str
    subtype: str
    risk: str

    version: int = 1
    source: str

    acceptance_criteria: list[AcceptanceCriterion] = Field(
        default_factory=list
    )


class SourceSpan(BaseModel):
    start: int
    end: int


class RequirementValidationUnit(BaseModel):
    rvu_id: str

    requirement_id: str
    ac_id: str

    atomic_text: str
    behavior_type: str

    source_text: str
    source_fragment: str
    source_span: SourceSpan

    constraints: list[str] = Field(
        default_factory=list
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    requires_review: bool = False
    review_reason: str | None = None

    version: int = 1

    extraction_method: str


class ExpectedEvidenceProfile(BaseModel):
    profile_id: str

    rvu_id: str
    requirement_id: str
    ac_id: str

    requirement_type: str
    requirement_subtype: str

    evidence_type: str

    required_scenarios: list[str] = Field(
        default_factory=list
    )

    preconditions: list[str] = Field(
        default_factory=list
    )

    inputs: list[str] = Field(
        default_factory=list
    )

    expected_outcomes: list[str] = Field(
        default_factory=list
    )

    required_assertions: list[str] = Field(
        default_factory=list
    )

    metric: str | None = None
    percentile: str | None = None
    operator: str | None = None
    threshold: float | None = None
    unit: str | None = None

    load: int | None = None
    duration_seconds: int | None = None
    scope: str | None = None

    support_status: str = "SUPPORTED"
    support_reason: str | None = None

    generation_method: str = (
        "DETERMINISTIC_EXPECTED_EVIDENCE_V2"
    )


class TestArtifact(BaseModel):
    artifact_id: str
    artifact_type: str

    title: str
    description: str = ""

    source_path: str
    source_tool: str
    source_version: str | None = None

    class_name: str | None = None
    method_name: str | None = None

    annotations: list[str] = Field(
        default_factory=list
    )

    assertions: list[str] = Field(
        default_factory=list
    )

    raw_reference: str | None = None


class ExecutionResult(BaseModel):
    execution_id: str

    artifact_id: str | None = None

    class_name: str | None = None
    method_name: str | None = None

    status: str

    duration_ms: float | None = None

    source_path: str
    source_tool: str

    run_id: str | None = None

    error_message: str | None = None


class ValidationEvidence(BaseModel):
    evidence_id: str
    evidence_type: str

    title: str
    description: str = ""

    preconditions: list[str] = Field(
        default_factory=list
    )

    inputs: list[str] = Field(
        default_factory=list
    )

    steps: list[str] = Field(
        default_factory=list
    )

    expected_result: str | None = None

    assertions: list[str] = Field(
        default_factory=list
    )

    class_name: str | None = None
    method_name: str | None = None

    execution_status: str | None = None
    execution_duration_ms: float | None = None
    execution_run_id: str | None = None

    metric: str | None = None
    measured_value: float | None = None
    threshold: float | None = None
    percentile: str | None = None

    load: int | None = None
    duration_seconds: int | None = None
    scope: str | None = None
    unit: str | None = None

    source_path: str
    source_tool: str
    source_version: str | None = None

    raw_reference: str | None = None

    synthetic: bool = False

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )


class CandidateEvidenceMatch(BaseModel):
    rvu_id: str

    evidence_id: str
    evidence_title: str
    evidence_type: str

    retrieval_method: str

    similarity_score: float
    rank: int

    model_name: str
    model_version: str | None = None

    source_path: str
    source_tool: str

    execution_status: str | None = None

    synthetic: bool = False

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )


class OverviewStats(BaseModel):
    requirements: int
    acceptance_criteria: int

    functional_requirements: int
    non_functional_requirements: int

    rvus: int
    expected_profiles: int
    evidence_items: int

    automated_tests: int
    manual_tests: int
    performance_evidence: int

    