from pathlib import Path

# Project root: .../project
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
HISTORICAL_DIR = DATA_DIR / "historical"

HRIM_FEATURES_FILE = PROCESSED_DIR / "hrim_fused_features.csv"
HRIM_SEMANTIC_FEATURES_FILE = (
    PROCESSED_DIR / "hrim_semantic_fused_features.csv"
)
FEATURE_AVAILABILITY_FILE = (
    PROCESSED_DIR / "hrim_feature_availability.csv"
)
ARCHITECTURE_RISK_FILE = (
    PROCESSED_DIR / "architecture_risk_baseline.csv"
)
HISTORICAL_CHANGES_FILE = (
    PROCESSED_DIR / "R01_petclinic_architecture_changes.csv"
)

API_TITLE = "Repository Intelligence Agent API"
API_VERSION = "1.0.0"


def validate_required_files() -> list[str]:
    """Return required data files that do not exist."""
    required_files = [
        HRIM_FEATURES_FILE,
        HRIM_SEMANTIC_FEATURES_FILE,
        FEATURE_AVAILABILITY_FILE,
        ARCHITECTURE_RISK_FILE,
    ]
    return [str(path) for path in required_files if not path.is_file()]
