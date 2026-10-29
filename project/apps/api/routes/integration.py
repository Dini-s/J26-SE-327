from fastapi import (
    APIRouter,
)

from agents.quality_agent.integration.contracts import (
    C1RequirementPayload,
    C2RepositoryArtifactReference,
    C4ChangeContext,
    USKG_OWNERSHIP,
)


router = APIRouter(
    prefix=(
        "/api/quality/integration"
    ),

    tags=[
        (
            "Quality Integration "
            "Contracts"
        )
    ],
)


@router.post(
    "/c1/validate"
)
def validate_c1_requirement(
    payload:
    C1RequirementPayload,
):
    return {
        "valid":
            True,

        "contract":
            "C1_TO_C3",

        "normalized":
            payload.model_dump(
                mode="json"
            ),
    }


@router.post(
    "/c2/validate"
)
def validate_c2_artifact(
    payload:
    C2RepositoryArtifactReference,
):
    return {
        "valid":
            True,

        "contract":
            "C2_TO_C3",

        "normalized":
            payload.model_dump(
                mode="json"
            ),
    }


@router.post(
    "/c4/validate"
)
def validate_c4_change(
    payload:
    C4ChangeContext,
):
    return {
        "valid":
            True,

        "contract":
            "C4_TO_C3",

        "normalized":
            payload.model_dump(
                mode="json"
            ),
    }


@router.get(
    "/ownership"
)
def get_uskg_ownership():
    return (
        USKG_OWNERSHIP
    )