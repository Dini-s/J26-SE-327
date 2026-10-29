from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from typing import Any

from pydantic import (
    BaseModel,
    Field,
)


class AcceptanceCriterion(
    BaseModel
):
    ac_id: str
    text: str


class RequirementRecord(
    BaseModel
):
    requirement_id: str

    title: str
    text: str

    type: str
    subtype: str
    risk: str

    version: int = 1

    source: str

    acceptance_criteria: list[
        AcceptanceCriterion
    ] = Field(
        default_factory=list
    )


class SourceSpan(
    BaseModel
):
    start: int
    end: int


class RequirementValidationUnit(
    BaseModel
):
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


class ExpectedEvidenceProfile(
    BaseModel
):
    profile_id: str

    rvu_id: str
    requirement_id: str
    ac_id: str

    requirement_type: str
    requirement_subtype: str

    evidence_type: str

    required_scenarios: list[
        str
    ] = Field(
        default_factory=list
    )

    preconditions: list[
        str
    ] = Field(
        default_factory=list
    )

    inputs: list[
        str
    ] = Field(
        default_factory=list
    )

    expected_outcomes: list[
        str
    ] = Field(
        default_factory=list
    )

    required_assertions: list[
        str
    ] = Field(
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

    support_status: str = (
        "SUPPORTED"
    )

    support_reason: str | None = None

    generation_method: str = (
        "DETERMINISTIC_"
        "EXPECTED_EVIDENCE_V2"
    )


class TestArtifact(
    BaseModel
):
    artifact_id: str
    artifact_type: str

    title: str
    description: str = ""

    source_path: str
    source_tool: str

    source_version: str | None = None

    class_name: str | None = None
    method_name: str | None = None

    annotations: list[
        str
    ] = Field(
        default_factory=list
    )

    assertions: list[
        str
    ] = Field(
        default_factory=list
    )

    raw_reference: str | None = None


class ExecutionResult(
    BaseModel
):
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


class ValidationEvidence(
    BaseModel
):
    evidence_id: str
    evidence_type: str

    title: str

    description: str = ""

    preconditions: list[
        str
    ] = Field(
        default_factory=list
    )

    inputs: list[
        str
    ] = Field(
        default_factory=list
    )

    steps: list[
        str
    ] = Field(
        default_factory=list
    )

    expected_result: str | None = None

    assertions: list[
        str
    ] = Field(
        default_factory=list
    )

    class_name: str | None = None
    method_name: str | None = None

    execution_status: str | None = None

    execution_duration_ms: (
        float | None
    ) = None

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

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    timestamp: datetime = Field(
        default_factory=lambda:
        datetime.now(
            timezone.utc
        )
    )


class CandidateEvidenceMatch(
    BaseModel
):
    rvu_id: str

    evidence_id: str
    evidence_title: str
    evidence_type: str

    retrieval_method: str

    similarity_score: float
    rank: int

    model_name: str

    model_version: (
        str | None
    ) = None

    source_path: str
    source_tool: str

    execution_status: (
        str | None
    ) = None

    synthetic: bool = False

    created_at: datetime = Field(
        default_factory=lambda:
        datetime.now(
            timezone.utc
        )
    )


class OverviewStats(
    BaseModel
):
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


class EvidenceAdequacyAssessment(
    BaseModel
):
    assessment_id: str

    profile_id: str

    rvu_id: str
    requirement_id: str

    evidence_id: str

    requirement_type: str

    requirement_subtype: str

    retrieval_method: str

    retrieval_rank: int | None = None

    relevance_status: str

    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    adequacy_status: str

    adequacy_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    factor_scores: dict[
        str,
        float,
    ] = Field(
        default_factory=dict
    )

    reason_codes: list[
        str
    ] = Field(
        default_factory=list
    )

    execution_status: (
        str | None
    ) = None

    source_path: str
    source_tool: str

    synthetic: bool = False

    rule_version: str = (
        "c3-adequacy-v2"
    )


class RVUAdequacySummary(
    BaseModel
):
    rvu_id: str
    requirement_id: str

    support_status: str

    evidence_found: bool

    adequacy_status: str

    best_evidence_id: (
        str | None
    ) = None

    best_relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    best_adequacy_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    adequate_evidence_ids: list[
        str
    ] = Field(
        default_factory=list
    )

    partial_evidence_ids: list[
        str
    ] = Field(
        default_factory=list
    )

    contributing_evidence_ids: list[
        str
    ] = Field(
        default_factory=list
    )

    reason_codes: list[
        str
    ] = Field(
        default_factory=list
    )


class RVUValidationResult(
    BaseModel
):
    rvu_id: str
    requirement_id: str

    evidence_found: bool

    adequacy_status: str

    execution_satisfied: bool

    validation_status: str

    best_evidence_id: (
        str | None
    ) = None

    reason_codes: list[
        str
    ] = Field(
        default_factory=list
    )


class RequirementIntelligence(
    BaseModel
):
    requirement_id: str

    total_rvus: int

    supported_rvus: int

    not_assessed_rvus: int = 0

    evidence_found_rvus: int

    adequate_rvus: int

    validated_rvus: int

    evidence_found_percent: float

    adequacy_coverage_percent: float

    rvc_percent: float

    assessable_adequacy_percent: float = 0.0

    execution_confirmed_percent: float = 0.0

    validation_status: str

    rves: float

    rves_factors: dict[
        str,
        float,
    ] = Field(
        default_factory=dict
    )

    rves_experimental: bool = True


class QAGap(
    BaseModel
):
    gap_id: str

    requirement_id: str
    rvu_id: str

    gap_type: str
    severity: str

    description: str

    reason_codes: list[
        str
    ] = Field(
        default_factory=list
    )

    evidence_id: (
        str | None
    ) = None


class Recommendation(
    BaseModel
):
    recommendation_id: str

    gap_id: str

    requirement_id: str
    rvu_id: str

    action_type: str

    recommendation: str

    grounded_in: list[
        str
    ] = Field(
        default_factory=list
    )


class RevalidationEvidenceInput(
    BaseModel
):
    evidence_id: (
        str | None
    ) = None

    evidence_name: str

    evidence_text: str

    previous_validation_purpose: str

    current_validation_purpose: str


class RevalidationChangeCase(
    BaseModel
):
    change_id: str

    source: str

    requirement_id: str

    requirement_type: str

    requirement_subtype: str

    affected_rvu_ids: list[
        str
    ] = Field(
        min_length=1
    )

    change_type: str

    previous_text: str
    current_text: str

    change_description: str

    evidence_cases: list[
        RevalidationEvidenceInput
    ] = Field(
        default_factory=list
    )


class RevalidationEvidenceDecision(
    BaseModel
):
    evidence_id: (
        str | None
    ) = None

    evidence_name: str

    previous_validation_purpose: str

    current_validation_purpose: str

    classification: str

    reason: str
    action: str


class RevalidationReport(
    BaseModel
):
    change_id: str

    source: str

    requirement_id: str

    requirement_type: str

    requirement_subtype: str

    affected_rvu_ids: list[
        str
    ]

    change_type: str

    previous_text: str
    current_text: str

    reusable_count: int

    modification_required_count: int

    outdated_count: int

    new_evidence_required_count: int

    decisions: list[
        RevalidationEvidenceDecision
    ] = Field(
        default_factory=list
    )

    summary: list[
        str
    ] = Field(
        default_factory=list
    )

    recommended_actions: list[
        str
    ] = Field(
        default_factory=list
    )