from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

load_dotenv(
    PROJECT_ROOT / ".env"
)


def _resolve_data_root() -> Path:
    raw = Path(
        os.getenv(
            "C3_DATA_ROOT",
            "data/component3",
        )
    )

    if raw.is_absolute():
        return raw

    return PROJECT_ROOT / raw


DATA_ROOT = _resolve_data_root()

RAW_ROOT = (
    DATA_ROOT
    / "raw"
)

PROCESSED_ROOT = (
    DATA_ROOT
    / "processed"
)

MANIFEST_ROOT = (
    DATA_ROOT
    / "manifests"
)

EVALUATION_ROOT = (
    DATA_ROOT
    / "evaluation"
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

REVALIDATION_INPUT_PATH = (
    RAW_ROOT
    / "revalidation"
    / "change_cases.json"
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


REVALIDATION_ROOT = (
    PROCESSED_ROOT
    / "revalidation"
)

REVALIDATION_RESULTS_PATH = (
    REVALIDATION_ROOT
    / "revalidation_results.json"
)


EVALUATION_GOLD_PATH = (
    EVALUATION_ROOT
    / "gold_labels.json"
)

EVALUATION_RESULTS_ROOT = (
    PROCESSED_ROOT
    / "evaluation"
)

EVALUATION_RESULTS_PATH = (
    EVALUATION_RESULTS_ROOT
    / "evaluation_results.json"
)


USKG_ROOT = (
    PROCESSED_ROOT
    / "uskg"
)

USKG_EXPORT_PATH = (
    USKG_ROOT
    / "c3_uskg.json"
)


RELEASE_ROOT = (
    PROCESSED_ROOT
    / "release"
)

RELEASE_VALIDATION_PATH = (
    RELEASE_ROOT
    / "release_validation.json"
)


DATASET_MANIFEST_PATH = (
    MANIFEST_ROOT
    / "dataset_manifest.json"
)

NFR_SUPPORT_MATRIX_PATH = (
    MANIFEST_ROOT
    / "nfr_support_matrix.json"
)

REPRODUCIBILITY_MANIFEST_PATH = (
    MANIFEST_ROOT
    / "reproducibility_manifest.json"
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

PETCLINIC_COMMIT = os.getenv(
    "PETCLINIC_COMMIT",
    (
        "500158f732419217507c7656904b8e6aa1bcc0d6"
    ),
)


def ensure_directories() -> None:
    paths = [
        RAW_ROOT,
        PROCESSED_ROOT,
        MANIFEST_ROOT,
        EVALUATION_ROOT,

        REQUIREMENTS_PATH.parent,
        MANUAL_TESTS_PATH.parent,
        MANUAL_EXECUTIONS_PATH.parent,
        JUNIT_ROOT,
        SUREFIRE_ROOT,
        PERFORMANCE_PATH.parent,
        REVALIDATION_INPUT_PATH.parent,

        RVUS_PATH.parent,
        EVIDENCE_PROFILES_PATH.parent,
        NORMALIZED_EVIDENCE_PATH.parent,
        RETRIEVAL_ROOT,

        ADEQUACY_ROOT,
        VALIDATION_ROOT,
        GAPS_ROOT,
        REVALIDATION_ROOT,

        EVALUATION_RESULTS_ROOT,
        USKG_ROOT,
        RELEASE_ROOT,
    ]

    for path in paths:
        path.mkdir(
            parents=True,
            exist_ok=True,
        )