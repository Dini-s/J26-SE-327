from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]

INPUT_FILE = PROJECT_ROOT / "data" / "processed" / "hrim_package_features.csv"

OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "hrim_labeled_features.csv"
VIOLATION_COLUMNS = [
    "architecture_violation_count",
    "unexpected_dependency_count",
    "circular_dependency_count",
]

HIGH_RISK_THRESHOLD = 1


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Feature CSV not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)

    print("Dataset shape:", df.shape)
    print("Available columns:")
    print(df.columns.tolist())

    # Use only architectural indicators that really exist.
    available = [col for col in VIOLATION_COLUMNS if col in df.columns]

    if not available:
        raise ValueError(
            "No architectural violation columns were found. "
            "Inspect the CSV columns and update "
            "VIOLATION_COLUMNS. Do not create labels from "
            "unrelated features without a justified rule."
        )

    # Missing measurements must not silently become zero.
    values = df[available].apply(pd.to_numeric, errors="coerce")

    # A package can be labeled only if all selected
    # violation measurements are available.
    valid = values.notna().all(axis=1)

    if (values[valid] < 0).any().any():
        raise ValueError("Violation counts cannot be negative.")

    # Combine the confirmed violation indicators.
    df["architecture_violation_score"] = values.sum(axis=1, min_count=len(available))

    # 1 = high risk, 0 = low risk, missing = unlabeled.
    df["architecture_drift_label"] = pd.Series(pd.NA, index=df.index, dtype="Int64")

    df.loc[valid, "architecture_drift_label"] = (
        df.loc[valid, "architecture_violation_score"]
        .ge(HIGH_RISK_THRESHOLD)
        .astype(int)
    )

    df["labeling_method"] = "Rule-based architectural violation proxy"

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print("\nLabeling completed.")
    print("Indicators used:", available)
    print("Labeled packages:", int(valid.sum()))
    print("Unlabeled packages:", int((~valid).sum()))
    print(
        "Label distribution:\n",
        df["architecture_drift_label"].value_counts(dropna=False).sort_index(),
    )
    print("Output:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
