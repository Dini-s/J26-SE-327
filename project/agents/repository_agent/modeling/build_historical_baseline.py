from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
HISTORICAL_DIR = ROOT / "data" / "historical"
PROCESSED_DIR = ROOT / "data" / "processed"

QUALITY_FILE = PROCESSED_DIR / "historical_architecture_changes_quality.csv"
OUTPUT_FILE = PROCESSED_DIR / "historical_baseline_dataset.csv"
REPORT_FILE = PROCESSED_DIR / "historical_baseline_report.csv"

METRICS = [
    "java_files",
    "nonempty_lines",
    "fan_in",
    "fan_out",
    "total_coupling",
    "instability",
]

# A package-level structural-change proxy threshold.
# This is an experimental threshold, not a validated drift definition.
CHANGE_THRESHOLD = 0.30


def load_interval_quality():
    if not QUALITY_FILE.exists():
        raise FileNotFoundError(f"Missing quality report: {QUALITY_FILE}")

    quality = pd.read_csv(QUALITY_FILE).fillna("")
    required = {
        "repository",
        "previous_snapshot",
        "current_snapshot",
        "interval_quality",
        "low_coverage_endpoint",
    }

    if not required.issubset(quality.columns):
        raise ValueError(
            f"Quality report is missing columns: {required - set(quality.columns)}"
        )

    result = {}

    for _, row in quality.iterrows():
        key = (
            row["repository"],
            row["previous_snapshot"],
            row["current_snapshot"],
        )
        result[key] = row.to_dict()

    return result


def load_edges(repo_dir):
    edges = {}

    for file in repo_dir.glob("*_dependencies.csv"):
        snapshot = file.name.removesuffix("_dependencies.csv")

        try:
            df = pd.read_csv(file)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            edges[snapshot] = set()
            continue

        required = {"source_package", "target_package"}

        if required.issubset(df.columns):
            edges[snapshot] = set(
                zip(
                    df["source_package"].dropna().astype(str),
                    df["target_package"].dropna().astype(str),
                )
            )

    return edges


def safe_relative_change(old, new):
    """Symmetric relative change, bounded between 0 and 2."""
    if pd.isna(old) or pd.isna(new):
        return np.nan

    old = float(old)
    new = float(new)
    denominator = abs(old) + abs(new)

    if denominator == 0:
        return 0.0

    return abs(new - old) / denominator


def compare_repository(repo_dir, quality_lookup):
    architecture_file = repo_dir / "all_snapshots_architecture.csv"

    if not architecture_file.exists():
        print(f"Skipping {repo_dir.name}: architecture file missing.")
        return []

    architecture = pd.read_csv(architecture_file)

    required = {
        "repository",
        "snapshot_date",
        "commit_hash",
        "package_path",
        *METRICS,
    }

    if not required.issubset(architecture.columns):
        print(f"Skipping {repo_dir.name}: required columns missing.")
        return []

    architecture["snapshot_date"] = pd.to_datetime(
        architecture["snapshot_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    architecture = architecture.dropna(subset=["snapshot_date", "package_path"])

    edge_map = load_edges(repo_dir)
    dates = sorted(architecture["snapshot_date"].unique())
    rows = []

    for previous_date, current_date in zip(dates, dates[1:]):
        interval_key = (
            repo_dir.name,
            previous_date,
            current_date,
        )
        quality = quality_lookup.get(interval_key, {})

        quality_status = str(quality.get("interval_quality", "quality_record_missing"))
        low_coverage = str(
            quality.get("low_coverage_endpoint", "")
        ).strip().lower() in {"true", "1", "yes"}

        # Exclude flagged or unassessed intervals from the primary dataset.
        # They remain visible in the report.
        eligible = quality_status == "no_initial_flag" and not low_coverage

        previous = architecture[
            architecture["snapshot_date"] == previous_date
        ].set_index("package_path")

        current = architecture[architecture["snapshot_date"] == current_date].set_index(
            "package_path"
        )

        if previous.index.has_duplicates or current.index.has_duplicates:
            print(
                f"Skipping duplicate package keys: {repo_dir.name} "
                f"{previous_date} -> {current_date}"
            )
            continue

        previous_packages = set(previous.index)
        current_packages = set(current.index)
        common_packages = previous_packages & current_packages

        previous_edges = edge_map.get(previous_date, set())
        current_edges = edge_map.get(current_date, set())

        edge_union = previous_edges | current_edges
        edge_similarity = (
            len(previous_edges & current_edges) / len(edge_union) if edge_union else 1.0
        )
        edge_change = 1.0 - edge_similarity

        for package in sorted(common_packages):
            row = {
                "repository": repo_dir.name,
                "package_path": package,
                "previous_snapshot": previous_date,
                "current_snapshot": current_date,
                "previous_commit": previous.loc[package, "commit_hash"],
                "current_commit": current.loc[package, "commit_hash"],
                "interval_quality": quality_status,
                "low_coverage_endpoint": low_coverage,
                "eligible_for_primary_experiment": eligible,
            }

            changes = []

            for metric in METRICS:
                old = previous.loc[package, metric]
                new = current.loc[package, metric]

                row[f"previous_{metric}"] = old
                row[f"current_{metric}"] = new

                change = safe_relative_change(old, new)
                row[f"{metric}_relative_change"] = change

                if pd.notna(change):
                    changes.append(change)

            row["mean_structural_metric_change"] = (
                float(np.mean(changes)) if changes else np.nan
            )

            # Descriptive future outcome; not a verified drift label.
            row["structural_change_proxy"] = (
                int(row["mean_structural_metric_change"] >= CHANGE_THRESHOLD)
                if pd.notna(row["mean_structural_metric_change"])
                else np.nan
            )

            row["threshold"] = CHANGE_THRESHOLD
            row["dependency_edge_change_score"] = edge_change
            row["target_interpretation"] = (
                "future_structural_change_proxy_not_verified_architecture_drift"
            )

            rows.append(row)

    return rows


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    quality_lookup = load_interval_quality()
    all_rows = []

    for repo_dir in sorted(
        folder for folder in HISTORICAL_DIR.iterdir() if folder.is_dir()
    ):
        rows = compare_repository(repo_dir, quality_lookup)
        all_rows.extend(rows)
        print(f"{repo_dir.name}: {len(rows)} retained-package examples")

    result = pd.DataFrame(all_rows)

    if result.empty:
        raise RuntimeError("No historical baseline examples were generated.")

    result.to_csv(OUTPUT_FILE, index=False)

    report = (
        result.groupby(
            [
                "repository",
                "previous_snapshot",
                "current_snapshot",
                "interval_quality",
                "eligible_for_primary_experiment",
            ],
            dropna=False,
        )
        .agg(
            examples=("package_path", "size"),
            positive_proxy=("structural_change_proxy", "sum"),
            negative_proxy=("structural_change_proxy", lambda s: (s == 0).sum()),
            mean_change=("mean_structural_metric_change", "mean"),
        )
        .reset_index()
    )

    report.to_csv(REPORT_FILE, index=False)

    primary = result[result["eligible_for_primary_experiment"]]

    print(f"\nAll retained-package examples: {len(result)}")
    print(f"Primary eligible examples: {len(primary)}")
    print(f"Excluded examples: {len(result) - len(primary)}")
    print(f"Output dataset: {OUTPUT_FILE}")
    print(f"Interval report: {REPORT_FILE}")

    if not primary.empty:
        print("\nPrimary proxy distribution:")
        print(
            primary["structural_change_proxy"]
            .value_counts(dropna=False)
            .sort_index()
            .to_string()
        )

    print(
        "\nWARNING: the target is a threshold-based structural-change proxy, "
        "not an independently verified architecture-drift label. "
        "This output is for baseline exploration, not a validated model claim."
    )


if __name__ == "__main__":
    main()
