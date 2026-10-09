import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


DATA_ROOT = (
    PROJECT_ROOT
    / os.getenv(
        "C3_DATA_ROOT",
        "data/component3",
    )
)


RAW_ROOT = DATA_ROOT / "raw"
PROCESSED_ROOT = DATA_ROOT / "processed"


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
    "sentence-transformers/all-MiniLM-L6-v2",
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


def ensure_directories() -> None:
    paths = [
        RAW_ROOT,
        PROCESSED_ROOT,
        RVUS_PATH.parent,
        EVIDENCE_PROFILES_PATH.parent,
        NORMALIZED_EVIDENCE_PATH.parent,
        RETRIEVAL_ROOT,
    ]

    for path in paths:
        path.mkdir(
            parents=True,
            exist_ok=True,
        )