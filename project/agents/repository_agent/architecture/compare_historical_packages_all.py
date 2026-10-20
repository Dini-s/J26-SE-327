import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HISTORICAL_DIR = ROOT / "data" / "historical"
PROCESSED_DIR = ROOT / "data" / "processed"

OUTPUT = PROCESSED_DIR / "historical_package_changes.csv"
QUALITY_FILE = PROCESSED_DIR / "historical_architecture_changes_quality.csv"

METRICS = [
    "java_files",
    "nonempty_lines",
    "fan_in",
    "fan_out",
    "total_coupling",
    "instability",
]


def load_edges(repo_dir):
    result = {}

    for file in repo_dir.glob("*_dependencies.csv"):
        snapshot = file.name.removesuffix("_dependencies.csv")

        try:
            df = pd.read_csv(file)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            result[snapshot] = set()
            continue

        required = {"source_package", "target_package"}
        if required.issubset(df.columns):
            result[snapshot] = set(
                zip(
                    df["source_package"].dropna(),
                    df["target_package"].dropna(),
                )
            )

    return result


def compare_repository(repo_dir, quality_lookup):
    file = repo_dir / "all_snapshots_architecture.csv"

    if not file.exists():
        print(f"Skipping {repo_dir.name}: architecture file missing.")
        return []

    try:
        df = pd.read_csv(file)
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        print(f"Skipping {repo_dir.name}: {exc}")
        return []

    required = {"snapshot_date", "package_path", *METRICS}
    if not required.issubset(df.columns):
        print(f"Skipping {repo_dir.name}: required columns missing.")
        return []

    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce")
    df = df.dropna(subset=["snapshot_date", "package_path"])
    df["snapshot_date"] = df["snapshot_date"].dt.strftime("%Y-%m-%d")

    edges = load_edges(repo_dir)
    dates = sorted(df["snapshot_date"].unique())
    rows = []

    for previous_date, current_date in zip(dates, dates[1:]):
        previous = df[df["snapshot_date"] == previous_date].set_index("package_path")
        current = df[df["snapshot_date"] == current_date].set_index("package_path")

        if previous.index.has_duplicates or current.index.has_duplicates:
            print(
                f"Skipping duplicate package keys: {repo_dir.name}, "
                f"{previous_date} -> {current_date}"
            )
            continue

        previous_packages = set(previous.index)
        current_packages = set(current.index)
        previous_edges = edges.get(previous_date, set())
        current_edges = edges.get(current_date, set())

        # An edge is incident to a package if it is its source or target.
        for package in sorted(previous_packages | current_packages):
            in_previous = package in previous_packages
            in_current = package in current_packages

            if in_previous and in_current:
                status = "retained"
            elif in_current:
                status = "added"
            else:
                status = "removed"

            row = {
                "repository": repo_dir.name,
                "previous_snapshot": previous_date,
                "current_snapshot": current_date,
                "package_path": package,
                "change_status": status,
            }

            for metric in METRICS:
                old = previous.loc[package, metric] if in_previous else None
                new = current.loc[package, metric] if in_current else None

                row[f"previous_{metric}"] = old
                row[f"current_{metric}"] = new

                # Deltas are meaningful only for packages present in both snapshots.
                if in_previous and in_current and pd.notna(old) and pd.notna(new):
                    row[f"{metric}_delta"] = new - old
                else:
                    row[f"{metric}_delta"] = None

            old_incident = {edge for edge in previous_edges if package in edge}
            new_incident = {edge for edge in current_edges if package in edge}

            row["previous_incident_edges"] = len(old_incident) if in_previous else None
            row["current_incident_edges"] = len(new_incident) if in_current else None
            row["incident_edges_added"] = (
                len(new_incident - old_incident) if in_previous and in_current else None
            )
            row["incident_edges_removed"] = (
                len(old_incident - new_incident) if in_previous and in_current else None
            )

            quality_key = (repo_dir.name, previous_date, current_date)
            quality = quality_lookup.get(quality_key, {})

            row["interval_quality"] = quality.get(
                "interval_quality", "quality_record_missing"
            )
            row["low_coverage_endpoint"] = quality.get("low_coverage_endpoint", "")

            # This is a descriptive proxy, not a verified drift label.
            row["change_status_is_drift_label"] = False
            row["target_interpretation"] = (
                "observed_package_structural_change_proxy_not_ground_truth"
            )

            rows.append(row)

    return rows


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    quality_lookup = {}
    if QUALITY_FILE.exists():
        quality_df = pd.read_csv(QUALITY_FILE).fillna("")
        required_quality = {
            "repository",
            "previous_snapshot",
            "current_snapshot",
        }

        if required_quality.issubset(quality_df.columns):
            for _, item in quality_df.iterrows():
                key = (
                    item["repository"],
                    item["previous_snapshot"],
                    item["current_snapshot"],
                )
                quality_lookup[key] = item.to_dict()

    all_rows = []

    for repo_dir in sorted(
        folder for folder in HISTORICAL_DIR.iterdir() if folder.is_dir()
    ):
        rows = compare_repository(repo_dir, quality_lookup)
        all_rows.extend(rows)
        print(f"{repo_dir.name}: {len(rows)} package-transition rows")

    result = pd.DataFrame(all_rows)
    result.to_csv(OUTPUT, index=False)

    print(
        f"\nRepositories: {result['repository'].nunique() if not result.empty else 0}"
    )
    print(f"Package-transition rows: {len(result)}")
    print(f"Saved: {OUTPUT}")

    if not result.empty:
        print("\nChange-status counts:")
        print(result["change_status"].value_counts().to_string())

        print("\nQuality flags:")
        print(result["interval_quality"].value_counts().to_string())

    print(
        "\nImportant: these records describe observed historical changes. "
        "They are not verified architecture-drift labels."
    )


if __name__ == "__main__":
    main()
