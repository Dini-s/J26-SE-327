from agents.quality_agent.integration.contracts import (
    C1RequirementPayload,
    C2RepositoryArtifactReference,
    C4ChangeContext,
    USKG_OWNERSHIP,
)


def test_c1_contract_accepts_camel_case():
    payload = (
        C1RequirementPayload
        .model_validate(
            {
                "requirementId":
                    "REQ-001",

                "title":
                    "Example",

                "text":
                    "Example requirement",

                "type":
                    "FUNCTIONAL",

                "subtype":
                    "SEARCH",

                "risk":
                    "MEDIUM",

                "version":
                    1,

                "source":
                    "C1",

                "acceptanceCriteria":
                    [
                        {
                            "acId":
                                "AC-001",

                            "text":
                                (
                                    "The system shall "
                                    "return a result."
                                ),
                        }
                    ],
            }
        )
    )

    assert (
        payload
        .requirement_id
        == "REQ-001"
    )

    assert (
        payload
        .acceptance_criteria[
            0
        ]
        .ac_id
        == "AC-001"
    )


def test_c2_contract_preserves_commit():
    payload = (
        C2RepositoryArtifactReference
        .model_validate(
            {
                "repositoryId":
                    "REPO-001",

                "repositoryName":
                    "Spring PetClinic",

                "commitSha":
                    "abc123",

                "artifactId":
                    "TEST-001",

                "artifactType":
                    "AUTOMATED_TEST",

                "sourcePath":
                    (
                        "src/test/"
                        "ExampleTest.java"
                    ),

                "className":
                    "ExampleTest",

                "methodName":
                    "shouldWork",
            }
        )
    )

    assert (
        payload.commit_sha
        == "abc123"
    )


def test_c4_contract_accepts_affected_rvus():
    payload = (
        C4ChangeContext
        .model_validate(
            {
                "changeId":
                    "CHG-001",

                "requirementId":
                    "REQ-001",

                "affectedRvuIds":
                    [
                        "REQ-001-RVU-01"
                    ],

                "changeType":
                    (
                        "ACCEPTANCE_"
                        "CRITERION_UPDATE"
                    ),

                "previousText":
                    "Old rule",

                "currentText":
                    "New rule",
            }
        )
    )

    assert (
        payload
        .affected_rvu_ids
        ==
        [
            "REQ-001-RVU-01"
        ]
    )


def test_c3_does_not_own_trace_edges():
    forbidden = set(
        USKG_OWNERSHIP[
            "FORBIDDEN_C3_WRITES"
        ]
    )

    assert (
        "VERIFIED_TRACE"
        in forbidden
    )

    assert (
        "REQUIREMENT_TO_CODE"
        in forbidden
    )