from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"

INPUT_FILE = PROCESSED / "historical_baseline_dataset.csv"
QUALITY_FILE = PROCESSED / "historical_interval_quality_review.csv"

OUTPUT_FILE = PROCESSED / "hrim_historical_training_baseline.csv"
REPORT_FILE = PROCESSED / "hrim_historical_training_report.csv"

TARGET = "structural_change_proxy"

# Initial baseline: information available at the previous snapshot.
FEATURES = [
    "previous_java_files",
    "previous_nonempty_lines",
    "previous_fan_in",
    "previous_fan_out",
    "previous_total_coupling",
    "previous_instability",
]

JOIN_KEYS = ["repository", "previous_snapshot", "current_snapshot"]

MIN_RETENTION = 0.50
MIN_RETAINED_PACKAGES = 20


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input dataset: {INPUT_FILE}")

    if not QUALITY_FILE.exists():
        raise FileNotFoundError(f"Missing quality report: {QUALITY_FILE}")

    data = pd.read_csv(INPUT_FILE)
    quality = pd.read_csv(QUALITY_FILE)

    required_data = set(JOIN_KEYS + FEATURES + [TARGET])
    required_quality = set(JOIN_KEYS + ["retained", "retention_rate", "low_coverage"])

    if not required_data.issubset(data.columns):
        raise ValueError(
            f"Missing dataset columns: {required_data - set(data.columns)}"
        )

    if not required_quality.issubset(quality.columns):
        raise ValueError(
            f"Missing quality columns: {required_quality - set(quality.columns)}"
        )

    if quality.duplicated(JOIN_KEYS).any():
        raise ValueError("Duplicate historical interval keys in quality report.")

    # Join quality information without using it as a model feature.
    merged = data.merge(
        quality[JOIN_KEYS + ["retained", "retention_rate", "low_coverage"]],
        on=JOIN_KEYS,
        how="left",
        validate="many_to_one",
        indicator=True,
    )

    if not merged["_merge"].eq("both").all():
        missing = merged.loc[merged["_merge"] != "both", JOIN_KEYS]
        raise ValueError(
            "Some examples have no matching quality record:\n"
            + missing.head(10).to_string(index=False)
        )

    merged = merged.drop(columns="_merge")

    # Explicitly parse boolean values from CSV.
    low_coverage = (
        merged["low_coverage"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )

    eligible = (
        ~low_coverage
        & (merged["retention_rate"] >= MIN_RETENTION)
        & (merged["retained"] >= MIN_RETAINED_PACKAGES)
    )

    selected = merged.loc[eligible].copy()

    # Require valid binary labels and finite predictor values.
    selected[TARGET] = pd.to_numeric(selected[TARGET], errors="coerce")
    for feature in FEATURES:
        selected[feature] = pd.to_numeric(selected[feature], errors="coerce")

    selected = selected.dropna(subset=FEATURES + [TARGET])

    valid_labels = selected[TARGET].isin([0, 1])
    selected = selected.loc[valid_labels].copy()
    selected[TARGET] = selected[TARGET].astype(int)

    for feature in FEATURES:
        selected = selected.loc[
            selected[feature].map(
                lambda value: pd.notna(value) and abs(value) != float("inf")
            )
        ]

    if selected.empty:
        raise RuntimeError("No valid training examples remain after filtering.")

    # Keep identifiers for group-aware evaluation, but not as predictors.
    output_columns = JOIN_KEYS + ["package_path"] + FEATURES + [TARGET]
    training = selected[output_columns].copy()

    if training.duplicated(["repository", "package_path", "current_snapshot"]).any():
        raise ValueError(
            "Duplicate repository/package/current-snapshot examples detected."
        )

    if training[FEATURES + [TARGET]].isna().any().any():
        raise ValueError("Missing values remain in the final training dataset.")

    if not training[TARGET].isin([0, 1]).all():
        raise ValueError("Target must contain only binary labels 0 and 1.")

    PROCESSED.mkdir(parents=True, exist_ok=True)
    training.to_csv(OUTPUT_FILE, index=False)

    report = (
        training.groupby("repository")
        .agg(
            examples=(TARGET, "size"),
            positive_examples=(TARGET, "sum"),
        )
        .reset_index()
    )
    report["negative_examples"] = report["examples"] - report["positive_examples"]
    report.to_csv(REPORT_FILE, index=False)

    print("Historical training baseline prepared.")
    print("Examples:", len(training))
    print("Repositories:", training["repository"].nunique())
    print("Features:", FEATURES)
    print("\nTarget distribution:")
    print(training[TARGET].value_counts().sort_index().to_string())
    print("\nMissing values:", int(training.isna().sum().sum()))
    print("Duplicate rows:", int(training.duplicated().sum()))
    print("\nRepository report:")
    print(report.to_string(index=False))
    print("\nSaved training dataset:", OUTPUT_FILE)
    print("Saved report:", REPORT_FILE)
    print(
        "\nIMPORTANT: This is a historical structural-change-proxy baseline, "
        "not a validated architecture-drift model."
    )


if __name__ == "__main__":
    main()
