from __future__ import annotations

from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
)


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class C1AcceptanceCriterion(
    ContractModel
):
    ac_id: str = Field(
        validation_alias=AliasChoices(
            "ac_id",
            "acId",
        )
    )

    text: str


class C1RequirementPayload(
    ContractModel
):
    requirement_id: str = Field(
        validation_alias=AliasChoices(
            "requirement_id",
            "requirementId",
        )
    )

    title: str

    text: str

    type: str

    subtype: str

    risk: str

    version: int = 1

    source: str

    acceptance_criteria: list[
        C1AcceptanceCriterion
    ] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "acceptance_criteria",
            "acceptanceCriteria",
        ),
    )


class C2RepositoryArtifactReference(
    ContractModel
):
    repository_id: str = Field(
        validation_alias=AliasChoices(
            "repository_id",
            "repositoryId",
        )
    )

    repository_name: str = Field(
        default="Spring PetClinic",
        validation_alias=AliasChoices(
            "repository_name",
            "repositoryName",
        ),
    )

    commit_sha: str = Field(
        validation_alias=AliasChoices(
            "commit_sha",
            "commitSha",
            "commitId",
        )
    )

    artifact_id: str = Field(
        validation_alias=AliasChoices(
            "artifact_id",
            "artifactId",
        )
    )

    artifact_type: str = Field(
        validation_alias=AliasChoices(
            "artifact_type",
            "artifactType",
        )
    )

    source_path: str = Field(
        validation_alias=AliasChoices(
            "source_path",
            "sourcePath",
        )
    )

    language: str | None = None

    class_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "class_name",
            "className",
        ),
    )

    method_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "method_name",
            "methodName",
        ),
    )

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class C4ChangeContext(
    ContractModel
):
    change_id: str = Field(
        validation_alias=AliasChoices(
            "change_id",
            "changeId",
            "event_id",
            "eventId",
        )
    )

    requirement_id: str = Field(
        validation_alias=AliasChoices(
            "requirement_id",
            "requirementId",
        )
    )

    affected_rvu_ids: list[
        str
    ] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "affected_rvu_ids",
            "affectedRvuIds",
        ),
    )

    change_type: str = Field(
        validation_alias=AliasChoices(
            "change_type",
            "changeType",
        )
    )

    previous_text: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "previous_text",
            "previousText",
        ),
    )

    current_text: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "current_text",
            "currentText",
        ),
    )

    verified_trace_ids: list[
        str
    ] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "verified_trace_ids",
            "verifiedTraceIds",
        ),
    )

    decay_status: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "decay_status",
            "decayStatus",
        ),
    )

    source: str = "C4"


class C3RVUPublication(
    ContractModel
):
    rvu_id: str

    requirement_id: str

    ac_id: str

    atomic_text: str

    behavior_type: str

    version: int = 1

    adequacy_status: str | None = None

    validation_status: str | None = None


class C3EvidencePublication(
    ContractModel
):
    evidence_id: str

    rvu_id: str

    evidence_type: str

    relevance_score: float

    adequacy_status: str

    adequacy_score: float

    execution_status: str | None = None

    source_path: str

    source_tool: str


USKG_OWNERSHIP = {
    "C1_OWNED_READ_ONLY": [
        "Requirement",
        "AcceptanceCriterion",
        "RequirementRisk",
        "RequirementVersion",
    ],

    "C2_OWNED_READ_ONLY": [
        "Repository",
        "Package",
        "CodeFile",
        "TestArtifact",
        "RepositoryArtifactReference",
    ],

    "C4_OWNED_READ_ONLY": [
        "VerifiedTrace",
        "DecayFlag",
        "ChangeImpact",
    ],

    "C3_OWNED": [
        "RequirementValidationUnit",
        "ExpectedEvidenceProfile",
        "ValidationEvidence",
        "EvidenceAdequacyAssessment",
        "RVUAdequacySummary",
        "RVUValidationResult",
        "RequirementIntelligence",
        "QAGap",
        "Recommendation",
        "RevalidationReport",
    ],

    "C3_RELATIONSHIPS": [
        "HAS_RVU",
        "DERIVED_FROM_AC",
        "EXPECTS_EVIDENCE",
        "MATCHED_BY",
        "SUMMARIZED_AS",
        "HAS_VALIDATION",
        "HAS_GAP",
        "RECOMMENDS",
        "IMPACTED_BY",
        "AFFECTS_RVU",
    ],

    "FORBIDDEN_C3_WRITES": [
        "VERIFIED_TRACE",
        "DECAY_FLAG",
        "REQUIREMENT_TO_CODE",
        "CODE_TO_TEST_TRACE",
    ],
}


def parse_c1_requirement(
    payload: dict[str, Any],
) -> C1RequirementPayload:
    return (
        C1RequirementPayload
        .model_validate(
            payload
        )
    )


def parse_c2_artifact(
    payload: dict[str, Any],
) -> C2RepositoryArtifactReference:
    return (
        C2RepositoryArtifactReference
        .model_validate(
            payload
        )
    )


def parse_c4_change(
    payload: dict[str, Any],
) -> C4ChangeContext:
    return (
        C4ChangeContext
        .model_validate(
            payload
        )
    )