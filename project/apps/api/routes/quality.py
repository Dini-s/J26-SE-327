from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from agents.quality_agent import (
    config,
)

from agents.quality_agent.agent import (
    QualityAgent,
)


router = APIRouter(
    prefix="/api/quality",
    tags=[
        "Quality & Testing Intelligence"
    ],
)


agent = QualityAgent()


@router.get(
    "/overview"
)
def get_overview():
    return agent.overview()


@router.post(
    "/process-requirements"
)
def process_requirements():

    result = (
        agent
        .process_requirements()
    )

    return {
        "requirements":
        len(
            result[
                "requirements"
            ]
        ),

        "rvus":
        len(
            result[
                "rvus"
            ]
        ),

        "expected_profiles":
        len(
            result[
                "profiles"
            ]
        ),
    }


@router.post(
    "/evidence/normalize"
)
def normalize_evidence():

    evidence = (
        agent
        .normalize_evidence()
    )

    return {
        "evidence_items":
        len(evidence)
    }


@router.get(
    "/evidence"
)
def get_evidence():

    if not (
        config
        .NORMALIZED_EVIDENCE_PATH
        .exists()
    ):
        return []

    return (
        agent
        .dataset_service
        .load_json(
            config
            .NORMALIZED_EVIDENCE_PATH
        )
    )


@router.get(
    "/requirements"
)
def get_requirements():

    requirements = (
        agent
        .dataset_service
        .load_requirements(
            config.REQUIREMENTS_PATH
        )
    )

    rvus = (
        agent
        .dataset_service
        .load_json(
            config.RVUS_PATH
        )
        if (
            config
            .RVUS_PATH
            .exists()
        )
        else []
    )

    response = []

    for requirement in (
        requirements
    ):
        requirement_rvus = [
            item
            for item
            in rvus
            if (
                item[
                    "requirement_id"
                ]
                == requirement
                .requirement_id
            )
        ]

        response.append(
            {
                **requirement
                .model_dump(),

                "ac_count":
                len(
                    requirement
                    .acceptance_criteria
                ),

                "rvu_count":
                len(
                    requirement_rvus
                ),
            }
        )

    return response


@router.get(
    "/requirements/{requirement_id}"
)
def get_requirement_details(
    requirement_id: str,
):

    requirements = (
        agent
        .dataset_service
        .load_requirements(
            config.REQUIREMENTS_PATH
        )
    )

    requirement = next(
        (
            item
            for item
            in requirements
            if (
                item
                .requirement_id
                == requirement_id
            )
        ),
        None,
    )

    if requirement is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Requirement not found"
            ),
        )

    rvus = []

    if (
        config
        .RVUS_PATH
        .exists()
    ):
        rvus = [
            item
            for item
            in (
                agent
                .dataset_service
                .load_json(
                    config.RVUS_PATH
                )
            )
            if (
                item[
                    "requirement_id"
                ]
                == requirement_id
            )
        ]

    profiles = []

    if (
        config
        .EVIDENCE_PROFILES_PATH
        .exists()
    ):
        profiles = [
            item
            for item
            in (
                agent
                .dataset_service
                .load_json(
                    config
                    .EVIDENCE_PROFILES_PATH
                )
            )
            if (
                item[
                    "requirement_id"
                ]
                == requirement_id
            )
        ]

    return {
        "requirement":
        requirement.model_dump(),

        "rvus":
        rvus,

        "profiles":
        profiles,
    }


@router.post(
    "/rvus/{rvu_id}/retrieve"
)
def retrieve_evidence(
    rvu_id: str,

    method: str = Query(
        default="semantic",
        pattern=(
            "^(keyword|tfidf|semantic)$"
        ),
    ),

    top_k: int = Query(
        default=5,
        ge=1,
        le=25,
    ),
):
    try:
        return agent.retrieve(
            rvu_id=rvu_id,
            method=method,
            top_k=top_k,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error