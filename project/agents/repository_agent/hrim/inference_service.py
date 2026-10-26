import csv
import json
from pathlib import Path

import joblib
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = PROJECT_ROOT / "data" / "evaluation" / "hrim_baseline"
MODEL_PATH = MODEL_DIR / "xgboost_structural_proxy.joblib"
SCHEMA_PATH = MODEL_DIR / "feature_schema.json"

with SCHEMA_PATH.open("r", encoding="utf-8") as file:
    FEATURE_SCHEMA = json.load(file)

FEATURES = FEATURE_SCHEMA["features"]
TARGET = FEATURE_SCHEMA["target"]


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Required analysis output not found: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def _count_nonempty_lines(repo_path: Path, package_path: str) -> int:
    """Count non-empty lines using the historical training definition."""
    package_parts = package_path.split(".")
    source_root = repo_path

    # Locate Java files by package declaration rather than assuming
    # a particular Maven source-directory layout.
    count = 0
    for java_file in source_root.rglob("*.java"):
        if any(
            part in {".git", ".venv", "target", "build", "out", "node_modules"}
            for part in java_file.parts
        ):
            continue

        try:
            source = java_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        package_name = ""
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("package ") and stripped.endswith(";"):
                package_name = stripped[len("package ") : -1].strip()
                break

        if package_name == package_path:
            count += sum(1 for line in source.splitlines() if line.strip())

    return count


def predict_package_proxy_scores(
    repository_id: str,
    architecture_csv: Path,
    repo_path: Path,
) -> list[dict]:
    """Predict exploratory architecture-change proxy scores per package."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Saved baseline model not found: {MODEL_PATH}")

    model = joblib.load(MODEL_PATH)
    architecture_rows = _read_csv(architecture_csv)

    feature_rows = []
    package_paths = []

    for row in architecture_rows:
        package_path = row["package_path"]

        fan_in = int(float(row["fan_in"]))
        fan_out = int(float(row["fan_out"]))
        coupling = int(float(row["total_coupling"]))

        feature_row = {
            "java_files": int(float(row["java_files"])),
            "nonempty_lines": _count_nonempty_lines(repo_path, package_path),
            "fan_in": fan_in,
            "fan_out": fan_out,
            "total_coupling": coupling,
            "instability": float(row["instability"]),
            "outgoing_dependency_count": fan_out,
            "incoming_dependency_count": fan_in,
        }

        feature_rows.append(feature_row)
        package_paths.append(package_path)

    X = pd.DataFrame(feature_rows, columns=FEATURES)

    probabilities = model.predict_proba(X)
    classes = list(model.classes_)

    # The positive class is the proxy label 1, not verified drift.
    if 1 not in classes:
        raise ValueError("The saved model does not contain proxy class 1.")

    positive_index = classes.index(1)
    results = []

    for package_path, probability, predicted_class in zip(
        package_paths, probabilities, model.predict(X)
    ):
        results.append(
            {
                "package_path": package_path,
                "proxy_probability": round(float(probability[positive_index]), 4),
                "predicted_proxy_label": int(predicted_class),
                "target": TARGET,
                "interpretation": (
                    "Exploratory architecture-change proxy prediction; "
                    "not validated architecture-drift detection."
                ),
            }
        )

    return results
