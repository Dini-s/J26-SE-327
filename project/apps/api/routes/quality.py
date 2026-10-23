from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from agents.quality_agent import config

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


def _load_json(
    path: Path,
    default,
):
    if not path.exists():
        return default

    return (
        agent.dataset_service
        .load_json(path)
    )


def _ensure_outputs() -> None:
    if (
        not config.RVUS_PATH.exists()
        or not config
        .EVIDENCE_PROFILES_PATH
        .exists()
    ):
        agent.process_requirements()

    if not (
        config
        .NORMALIZED_EVIDENCE_PATH
        .exists()
    ):
        agent.normalize_evidence()

    required_outputs = [
        config
        .ADEQUACY_ASSESSMENTS_PATH,

        config
        .RVU_ADEQUACY_PATH,

        config
        .RVU_VALIDATION_PATH,

        config
        .REQUIREMENT_INTELLIGENCE_PATH,

        config.GAPS_PATH,

        config
        .RECOMMENDATIONS_PATH,

        config.ANALYTICS_PATH,
    ]

    if any(
        not path.exists()
        for path
        in required_outputs
    ):
        agent.analyze_quality()

    if (
        config
        .REVALIDATION_INPUT_PATH
        .exists()
        and not config
        .REVALIDATION_RESULTS_PATH
        .exists()
    ):
        agent.run_revalidation()


def _assertion_strength(
    value: float | None,
) -> str:
    if value is None:
        return "NOT_AVAILABLE"

    if value >= 0.75:
        return "STRONG"

    if value >= 0.50:
        return "MODERATE"

    return "WEAK"


# ============================================================
# Bootstrap / health-supporting component state
# ============================================================

@router.post(
    "/bootstrap"
)
def bootstrap():
    _ensure_outputs()

    requirements = (
        agent.dataset_service
        .load_requirements(
            config.REQUIREMENTS_PATH
        )
    )

    return {
        "status": "ready",

        "requirements": len(
            requirements
        ),

        "rvus": len(
            _load_json(
                config.RVUS_PATH,
                [],
            )
        ),

        "evidence_items": len(
            _load_json(
                config
                .NORMALIZED_EVIDENCE_PATH,
                [],
            )
        ),

        "requirement_intelligence": len(
            _load_json(
                config
                .REQUIREMENT_INTELLIGENCE_PATH,
                [],
            )
        ),

        "revalidation_cases": len(
            _load_json(
                config
                .REVALIDATION_RESULTS_PATH,
                [],
            )
        ),

        "analytics_ready": (
            config
            .ANALYTICS_PATH
            .exists()
        ),
    }


@router.get(
    "/debug/status"
)
def debug_status():
    requirements = []

    if (
        config
        .REQUIREMENTS_PATH
        .exists()
    ):
        requirements = (
            agent.dataset_service
            .load_requirements(
                config
                .REQUIREMENTS_PATH
            )
        )

    return {
        "requirements_exists": (
            config
            .REQUIREMENTS_PATH
            .exists()
        ),

        "requirements": len(
            requirements
        ),

        "rvus_exists": (
            config
            .RVUS_PATH
            .exists()
        ),

        "rvus": len(
            _load_json(
                config.RVUS_PATH,
                [],
            )
        ),

        "profiles_exists": (
            config
            .EVIDENCE_PROFILES_PATH
            .exists()
        ),

        "normalized_evidence_exists": (
            config
            .NORMALIZED_EVIDENCE_PATH
            .exists()
        ),

        "intelligence_exists": (
            config
            .REQUIREMENT_INTELLIGENCE_PATH
            .exists()
        ),

        "analytics_exists": (
            config
            .ANALYTICS_PATH
            .exists()
        ),

        "revalidation_exists": (
            config
            .REVALIDATION_RESULTS_PATH
            .exists()
        ),
    }


# ============================================================
# Raw dataset / processing endpoints
# ============================================================

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
        agent.process_requirements()
    )

    return {
        "requirements": len(
            result["requirements"]
        ),

        "rvus": len(
            result["rvus"]
        ),

        "expected_profiles": len(
            result["profiles"]
        ),
    }


@router.post(
    "/evidence/normalize"
)
def normalize_evidence():
    evidence = (
        agent.normalize_evidence()
    )

    return {
        "evidence_items": len(
            evidence
        )
    }


@router.get(
    "/evidence"
)
def get_evidence():
    _ensure_outputs()

    return _load_json(
        config
        .NORMALIZED_EVIDENCE_PATH,
        [],
    )


# ============================================================
# Raw requirements API
# ============================================================

@router.get(
    "/requirements"
)
def get_requirements():
    _ensure_outputs()

    requirements = (
        agent.dataset_service
        .load_requirements(
            config.REQUIREMENTS_PATH
        )
    )

    rvus = _load_json(
        config.RVUS_PATH,
        [],
    )

    response = []

    for requirement in requirements:
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
                .model_dump(
                    mode="json"
                ),

                "ac_count": len(
                    requirement
                    .acceptance_criteria
                ),

                "rvu_count": len(
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
    _ensure_outputs()

    requirements = (
        agent.dataset_service
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
                item.requirement_id
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

    rvus = [
        item
        for item
        in _load_json(
            config.RVUS_PATH,
            [],
        )
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]

    profiles = [
        item
        for item
        in _load_json(
            config
            .EVIDENCE_PROFILES_PATH,
            [],
        )
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]

    return {
        "requirement": (
            requirement
            .model_dump(
                mode="json"
            )
        ),

        "rvus": rvus,

        "profiles": profiles,
    }


# ============================================================
# Evidence retrieval
# ============================================================

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


# ============================================================
# Complete quality analysis
# ============================================================

@router.post(
    "/analyze"
)
def analyze(
    top_k: int = Query(
        default=5,
        ge=1,
        le=25,
    ),
):
    result = (
        agent.analyze_quality(
            top_k=top_k
        )
    )

    return {
        "status": "completed",
        **result,
    }


# ============================================================
# Intelligence overview
# ============================================================

@router.get(
    "/intelligence/overview"
)
def intelligence_overview():
    _ensure_outputs()

    analytics = _load_json(
        config.ANALYTICS_PATH,
        {},
    )

    history = _load_json(
        config
        .ANALYSIS_HISTORY_PATH,
        [],
    )

    return {
        **analytics.get(
            "overview",
            {},
        ),

        "history": history,
    }


# ============================================================
# Intelligence requirements
# ============================================================

@router.get(
    "/intelligence/requirements"
)
def intelligence_requirements():
    _ensure_outputs()

    analytics = _load_json(
        config.ANALYTICS_PATH,
        {},
    )

    return analytics.get(
        "requirements",
        [],
    )


@router.get(
    "/intelligence/requirements/"
    "{requirement_id}"
)
def intelligence_requirement(
    requirement_id: str,
):
    _ensure_outputs()

    requirements = (
        agent.dataset_service
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
                item.requirement_id
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

    intelligence = next(
        (
            item
            for item
            in _load_json(
                config
                .REQUIREMENT_INTELLIGENCE_PATH,
                [],
            )
            if (
                item[
                    "requirement_id"
                ]
                == requirement_id
            )
        ),
        None,
    )

    rvus = [
        item
        for item
        in _load_json(
            config.RVUS_PATH,
            [],
        )
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]

    profiles = [
        item
        for item
        in _load_json(
            config
            .EVIDENCE_PROFILES_PATH,
            [],
        )
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]

    summaries = [
        item
        for item
        in _load_json(
            config
            .RVU_ADEQUACY_PATH,
            [],
        )
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]

    validations = [
        item
        for item
        in _load_json(
            config
            .RVU_VALIDATION_PATH,
            [],
        )
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]

    assessments = [
        item
        for item
        in _load_json(
            config
            .ADEQUACY_ASSESSMENTS_PATH,
            [],
        )
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]

    evidence = _load_json(
        config
        .NORMALIZED_EVIDENCE_PATH,
        [],
    )

    evidence_map = {
        item["evidence_id"]: item
        for item
        in evidence
    }

    profile_map = {
        item["rvu_id"]: item
        for item
        in profiles
    }

    summary_map = {
        item["rvu_id"]: item
        for item
        in summaries
    }

    validation_map = {
        item["rvu_id"]: item
        for item
        in validations
    }

    enriched_rvus = []

    for rvu in rvus:
        rvu_id = rvu[
            "rvu_id"
        ]

        current_assessments = []

        for assessment in assessments:
            if (
                assessment[
                    "rvu_id"
                ]
                != rvu_id
            ):
                continue

            evidence_item = (
                evidence_map.get(
                    assessment[
                        "evidence_id"
                    ]
                )
            )

            oracle_score = (
                assessment
                .get(
                    "factor_scores",
                    {},
                )
                .get(
                    "oracle_strength"
                )
            )

            current_assessments.append(
                {
                    **assessment,

                    "assertion_strength":
                        _assertion_strength(
                            oracle_score
                        ),

                    "evidence":
                        evidence_item,
                }
            )

        enriched_rvus.append(
            {
                "rvu": rvu,

                "profile":
                    profile_map.get(
                        rvu_id
                    ),

                "adequacy_summary":
                    summary_map.get(
                        rvu_id
                    ),

                "validation":
                    validation_map.get(
                        rvu_id
                    ),

                "evidence_assessments":
                    current_assessments,
            }
        )

    gaps = [
        item
        for item
        in _load_json(
            config.GAPS_PATH,
            [],
        )
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]

    recommendations = [
        item
        for item
        in _load_json(
            config
            .RECOMMENDATIONS_PATH,
            [],
        )
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]

    revalidation = [
        item
        for item
        in _load_json(
            config
            .REVALIDATION_RESULTS_PATH,
            [],
        )
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]

    return {
        "requirement": (
            requirement
            .model_dump(
                mode="json"
            )
        ),

        "intelligence":
            intelligence,

        "rvus":
            enriched_rvus,

        "gaps":
            gaps,

        "recommendations":
            recommendations,

        "revalidation":
            revalidation,
    }


# ============================================================
# Intelligence evidence / gaps / recommendations
# ============================================================

@router.get(
    "/intelligence/adequacy"
)
def get_adequacy(
    requirement_id: (
        str | None
    ) = None,
):
    _ensure_outputs()

    values = _load_json(
        config
        .ADEQUACY_ASSESSMENTS_PATH,
        [],
    )

    if requirement_id is None:
        return values

    return [
        item
        for item
        in values
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]


@router.get(
    "/intelligence/gaps"
)
def get_gaps(
    requirement_id: (
        str | None
    ) = None,
):
    _ensure_outputs()

    values = _load_json(
        config.GAPS_PATH,
        [],
    )

    if requirement_id is None:
        return values

    return [
        item
        for item
        in values
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]


@router.get(
    "/intelligence/recommendations"
)
def get_recommendations(
    requirement_id: (
        str | None
    ) = None,
):
    _ensure_outputs()

    values = _load_json(
        config
        .RECOMMENDATIONS_PATH,
        [],
    )

    if requirement_id is None:
        return values

    return [
        item
        for item
        in values
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]


# ============================================================
# Revalidation
# ============================================================

@router.post(
    "/revalidation/run"
)
def run_revalidation():
    reports = (
        agent.run_revalidation()
    )

    return {
        "change_cases": len(
            reports
        ),

        "reports": [
            item.model_dump(
                mode="json"
            )
            for item
            in reports
        ],
    }


@router.get(
    "/revalidation"
)
def get_revalidation(
    requirement_id: (
        str | None
    ) = None,
):
    _ensure_outputs()

    values = _load_json(
        config
        .REVALIDATION_RESULTS_PATH,
        [],
    )

    if requirement_id is None:
        return values

    return [
        item
        for item
        in values
        if (
            item[
                "requirement_id"
            ]
            == requirement_id
        )
    ]


# ============================================================
# Reports
# ============================================================

@router.get(
    "/intelligence/reports"
)
def reports():
    _ensure_outputs()

    analytics = _load_json(
        config.ANALYTICS_PATH,
        {},
    )

    revalidation = _load_json(
        config
        .REVALIDATION_RESULTS_PATH,
        [],
    )

    recommendations = _load_json(
        config
        .RECOMMENDATIONS_PATH,
        [],
    )

    gaps = _load_json(
        config.GAPS_PATH,
        [],
    )

    return {
        **analytics.get(
            "reports",
            {},
        ),

        "requirements":
            analytics.get(
                "requirements",
                [],
            ),

        "revalidation_cases":
            revalidation,

        "gaps":
            gaps,

        "recommendations":
            recommendations,

        "revalidation_summary": {
            "change_cases":
                len(revalidation),

            "reusable":
                sum(
                    item.get(
                        "reusable_count",
                        0,
                    )
                    for item
                    in revalidation
                ),

            "modification_required":
                sum(
                    item.get(
                        "modification_required_count",
                        0,
                    )
                    for item
                    in revalidation
                ),

            "outdated":
                sum(
                    item.get(
                        "outdated_count",
                        0,
                    )
                    for item
                    in revalidation
                ),

            "new_evidence_required":
                sum(
                    item.get(
                        "new_evidence_required_count",
                        0,
                    )
                    for item
                    in revalidation
                ),
        },
    }


# ============================================================
# Export
# ============================================================

@router.get(
    "/export/summary"
)
def export_summary():
    _ensure_outputs()

    analytics = _load_json(
        config.ANALYTICS_PATH,
        {},
    )

    revalidation = _load_json(
        config
        .REVALIDATION_RESULTS_PATH,
        [],
    )

    return {
        "component":
            "Quality & Testing Intelligence",

        "component_id":
            "C3",

        "analytics":
            analytics,

        "revalidation":
            revalidation,

        "methodology": {
            "rvc_definition": (
                "Adequate RVUs divided by "
                "total RVUs."
            ),

            "relevance_is_separate_from_adequacy":
                True,

            "adequacy_is_separate_from_execution":
                True,

            "execution_confirmed_validation_is_separate":
                True,

            "rves_is_experimental":
                True,

            "controlled_fixtures_are_explicit":
                True,

            "unsupported_nfrs_are_not_falsely_validated":
                True,
        },
    }