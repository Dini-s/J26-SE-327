import os

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

load_dotenv(
    PROJECT_ROOT
    / ".env"
)


DATA_ROOT = (
    PROJECT_ROOT
    / os.getenv(
        "C3_DATA_ROOT",
        "data/component3",
    )
)


RAW_ROOT = (
    DATA_ROOT
    / "raw"
)

PROCESSED_ROOT = (
    DATA_ROOT
    / "processed"
)


REQUIREMENTS_PATH = (
    RAW_ROOT
    / "requirements"
    / "requirements.json"
)


MANUAL_TESTS_PATH = (
    RAW_ROOT
    / "manual_tests"
    / "manual_tests.json"
)


MANUAL_EXECUTIONS_PATH = (
    RAW_ROOT
    / "manual_execution"
    / "manual_execution_results.json"
)


JUNIT_ROOT = (
    RAW_ROOT
    / "junit"
    / "petclinic"
)


SUREFIRE_ROOT = (
    RAW_ROOT
    / "surefire"
    / "petclinic"
)


PERFORMANCE_PATH = (
    RAW_ROOT
    / "performance"
    / "performance_evidence.json"
)


RVUS_PATH = (
    PROCESSED_ROOT
    / "rvus"
    / "rvus.json"
)


EVIDENCE_PROFILES_PATH = (
    PROCESSED_ROOT
    / "evidence_profiles"
    / "evidence_profiles.json"
)


NORMALIZED_EVIDENCE_PATH = (
    PROCESSED_ROOT
    / "normalized_evidence"
    / "evidence.json"
)


RETRIEVAL_ROOT = (
    PROCESSED_ROOT
    / "retrieval"
)


EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    (
        "sentence-transformers/"
        "all-MiniLM-L6-v2"
    ),
)


TOP_K = int(
    os.getenv(
        "TOP_K",
        "5",
    )
)


SEMANTIC_THRESHOLD = float(
    os.getenv(
        "SEMANTIC_THRESHOLD",
        "0.35",
    )
)


ADEQUACY_ROOT = (
    PROCESSED_ROOT
    / "adequacy"
)


ADEQUACY_ASSESSMENTS_PATH = (
    ADEQUACY_ROOT
    / "evidence_assessments.json"
)


RVU_ADEQUACY_PATH = (
    ADEQUACY_ROOT
    / "rvu_adequacy.json"
)


VALIDATION_ROOT = (
    PROCESSED_ROOT
    / "validation"
)


RVU_VALIDATION_PATH = (
    VALIDATION_ROOT
    / "rvu_validation.json"
)


REQUIREMENT_INTELLIGENCE_PATH = (
    VALIDATION_ROOT
    / "requirement_intelligence.json"
)


ANALYTICS_PATH = (
    VALIDATION_ROOT
    / "analytics.json"
)


ANALYSIS_HISTORY_PATH = (
    VALIDATION_ROOT
    / "analysis_history.json"
)


GAPS_ROOT = (
    PROCESSED_ROOT
    / "gaps"
)


GAPS_PATH = (
    GAPS_ROOT
    / "gaps.json"
)


RECOMMENDATIONS_PATH = (
    GAPS_ROOT
    / "recommendations.json"
)


REVALIDATION_INPUT_PATH = (
    RAW_ROOT
    / "revalidation"
    / "change_cases.json"
)


REVALIDATION_ROOT = (
    PROCESSED_ROOT
    / "revalidation"
)


REVALIDATION_RESULTS_PATH = (
    REVALIDATION_ROOT
    / "revalidation_results.json"
)


def ensure_directories() -> None:
    paths = [
        RAW_ROOT,
        PROCESSED_ROOT,

        REQUIREMENTS_PATH.parent,

        MANUAL_TESTS_PATH.parent,

        MANUAL_EXECUTIONS_PATH.parent,

        RVUS_PATH.parent,

        EVIDENCE_PROFILES_PATH.parent,

        NORMALIZED_EVIDENCE_PATH.parent,

        RETRIEVAL_ROOT,

        ADEQUACY_ROOT,

        VALIDATION_ROOT,

        GAPS_ROOT,

        REVALIDATION_ROOT,
    ]

    for path in paths:
        path.mkdir(
            parents=True,
            exist_ok=True,
        )