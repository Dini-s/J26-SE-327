from pathlib import Path

import pandas as pd


# Project root: project/
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LABEL_DIR = PROJECT_ROOT / "data" / "labels"

TRAINING_FILE = LABEL_DIR / "hrim_historical_training_table_v1.csv"
EVIDENCE_FILE = LABEL_DIR / "hrim_historical_label_evidence_v1.csv"

REPORT_DIR = PROJECT_ROOT / "data" / "evaluation"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 65)
    print("HRIM HISTORICAL LABEL VALIDATION")
    print("=" * 65)

    if not TRAINING_FILE.exists():
        raise FileNotFoundError(f"Missing file: {TRAINING_FILE}")

    if not EVIDENCE_FILE.exists():
        raise FileNotFoundError(f"Missing file: {EVIDENCE_FILE}")

    df = pd.read_csv(TRAINING_FILE)
    evidence = pd.read_csv(EVIDENCE_FILE)

    required = {
        "sample_id",
        "repository",
        "package_path",
        "feature_snapshot_date",
        "label_observation_snapshot_date",
        "architecture_change_proxy_label",
    }

    missing_columns = required - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    target = "architecture_change_proxy_label"

    print(f"\nDataset shape: {df.shape}")
    print(f"Repositories: {df['repository'].nunique()}")
    print(f"Duplicate sample IDs: {df['sample_id'].duplicated().sum()}")

    # 1. Target validation
    print("\n--- Label distribution ---")
    print(df[target].value_counts(dropna=False).sort_index())

    print("\nLabel percentages:")
    print((df[target].value_counts(normalize=True, dropna=False) * 100).round(2))

    print("\nMissing target values:", df[target].isna().sum())
    print(
        "Unexpected target values:",
        (~df[target].isin([0, 1]) & df[target].notna()).sum(),
    )

    # 2. Repository coverage and class distribution
    repository_summary = (
        df.groupby("repository")
        .agg(
            samples=("sample_id", "size"),
            positive_labels=(target, "sum"),
            unique_packages=("package_path", "nunique"),
            feature_snapshots=("feature_snapshot_date", "nunique"),
        )
        .reset_index()
    )

    repository_summary["positive_rate_percent"] = (
        repository_summary["positive_labels"] / repository_summary["samples"] * 100
    ).round(2)

    print("\n--- Per-repository summary ---")
    print(repository_summary.to_string(index=False))

    # 3. Check that labels have corresponding evidence
    if "sample_id" not in evidence.columns:
        raise ValueError("Evidence CSV does not contain sample_id.")

    if "label_evidence_reasons" in evidence.columns:
        print("\n--- Label evidence reasons ---")
        reasons = (
            evidence["label_evidence_reasons"]
            .fillna("missing")
            .str.split(";")
            .explode()
            .value_counts()
        )
        print(reasons.to_string())

    unmatched = set(df["sample_id"]) - set(evidence["sample_id"])
    print("\nTraining rows without evidence:", len(unmatched))

    # 4. Check temporal ordering
    feature_dates = pd.to_datetime(df["feature_snapshot_date"], errors="coerce")
    observation_dates = pd.to_datetime(
        df["label_observation_snapshot_date"], errors="coerce"
    )

    invalid_dates = (
        feature_dates.isna()
        | observation_dates.isna()
        | (observation_dates <= feature_dates)
    )

    print("Invalid snapshot date pairs:", int(invalid_dates.sum()))

    # 5. Save audit reports
    repository_summary.to_csv(
        REPORT_DIR / "historical_label_repository_summary.csv",
        index=False,
    )

    label_counts = (
        df[target]
        .value_counts(dropna=False)
        .rename_axis("label")
        .reset_index(name="samples")
    )
    label_counts.to_csv(
        REPORT_DIR / "historical_label_distribution.csv",
        index=False,
    )

    checks = {
        "rows": len(df),
        "repositories": df["repository"].nunique(),
        "duplicate_sample_ids": int(df["sample_id"].duplicated().sum()),
        "missing_targets": int(df[target].isna().sum()),
        "unexpected_targets": int(
            (~df[target].isin([0, 1]) & df[target].notna()).sum()
        ),
        "unmatched_evidence_rows": len(unmatched),
        "invalid_date_pairs": int(invalid_dates.sum()),
    }

    pd.DataFrame(list(checks.items()), columns=["check", "value"]).to_csv(
        REPORT_DIR / "historical_label_validation_checks.csv",
        index=False,
    )

    print("\n--- Validation checks ---")
    for name, value in checks.items():
        print(f"{name}: {value}")

    print(f"\nReports saved to: {REPORT_DIR}")
    print(
        "\nIMPORTANT: These are structural-change proxy labels, "
        "not yet validated architecture-drift ground truth."
    )


if __name__ == "__main__":
    main()
