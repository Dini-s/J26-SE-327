import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HISTORICAL_DIR = ROOT / "data" / "historical"
OUTPUT = ROOT / "data" / "processed" / "historical_architecture_changes.csv"


def load_dependency_edges(repo_dir):
    """Load dependency edges separately for each historical snapshot."""
    edges_by_date = {}

    for file in repo_dir.glob("*_dependencies.csv"):
        date = file.name.removesuffix("_dependencies.csv")

        try:
            df = pd.read_csv(file)
        except pd.errors.EmptyDataError:
            edges_by_date[date] = set()
            continue

        required = {"source_package", "target_package"}
        if not required.issubset(df.columns):
            print(f"Warning: Skipping invalid dependency file: {file}")
            continue

        edges_by_date[date] = set(
            zip(
                df["source_package"].dropna(),
                df["target_package"].dropna(),
            )
        )

    return edges_by_date


def compare_repository(repo_dir):
    combined_file = repo_dir / "all_snapshots_architecture.csv"

    if not combined_file.exists():
        print(f"Skipping {repo_dir.name}: combined architecture CSV missing.")
        return []

    try:
        architecture = pd.read_csv(combined_file)
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        print(f"Skipping {repo_dir.name}: cannot read architecture CSV ({exc}).")
        return []

    required = {"snapshot_date", "package_path", "total_coupling"}
    if not required.issubset(architecture.columns):
        print(f"Skipping {repo_dir.name}: required columns missing.")
        return []

    architecture["snapshot_date"] = pd.to_datetime(
        architecture["snapshot_date"], errors="coerce"
    )
    architecture = architecture.dropna(subset=["snapshot_date", "package_path"])

    edges_by_date = load_dependency_edges(repo_dir)

    dates = sorted(architecture["snapshot_date"].dt.strftime("%Y-%m-%d").unique())

    rows = []

    for previous_date, current_date in zip(dates, dates[1:]):
        previous = architecture[
            architecture["snapshot_date"].dt.strftime("%Y-%m-%d") == previous_date
        ].set_index("package_path")

        current = architecture[
            architecture["snapshot_date"].dt.strftime("%Y-%m-%d") == current_date
        ].set_index("package_path")

        # Avoid silently comparing ambiguous duplicate package records.
        if previous.index.has_duplicates or current.index.has_duplicates:
            print(
                f"Warning: {repo_dir.name}: duplicate package paths "
                f"between {previous_date} and {current_date}; skipping interval."
            )
            continue

        previous_packages = set(previous.index)
        current_packages = set(current.index)

        previous_edges = edges_by_date.get(previous_date, set())
        current_edges = edges_by_date.get(current_date, set())

        common = previous_packages & current_packages
        package_union = previous_packages | current_packages
        edge_union = previous_edges | current_edges

        package_similarity = (
            len(previous_packages & current_packages) / len(package_union)
            if package_union
            else 1.0
        )
        edge_similarity = (
            len(previous_edges & current_edges) / len(edge_union) if edge_union else 1.0
        )

        coupling_changes = sum(
            pd.notna(previous.loc[p, "total_coupling"])
            and pd.notna(current.loc[p, "total_coupling"])
            and previous.loc[p, "total_coupling"] != current.loc[p, "total_coupling"]
            for p in common
        )

        rows.append(
            {
                "repository": repo_dir.name,
                "previous_snapshot": previous_date,
                "current_snapshot": current_date,
                "previous_package_count": len(previous_packages),
                "current_package_count": len(current_packages),
                "packages_added": len(current_packages - previous_packages),
                "packages_removed": len(previous_packages - current_packages),
                "previous_dependency_edges": len(previous_edges),
                "current_dependency_edges": len(current_edges),
                "dependency_edges_added": len(current_edges - previous_edges),
                "dependency_edges_removed": len(previous_edges - current_edges),
                "common_packages": len(common),
                "common_packages_with_coupling_change": coupling_changes,
                "package_jaccard_similarity": package_similarity,
                "dependency_jaccard_similarity": edge_similarity,
                "architecture_change_score": (
                    (1 - package_similarity) + (1 - edge_similarity)
                )
                / 2,
                "change_score_interpretation": "structural_change_proxy_not_ground_truth",
            }
        )

    return rows


def main():
    all_rows = []

    if not HISTORICAL_DIR.exists():
        raise FileNotFoundError(
            f"Historical data directory not found: {HISTORICAL_DIR}"
        )

    repo_dirs = sorted(folder for folder in HISTORICAL_DIR.iterdir() if folder.is_dir())

    for repo_dir in repo_dirs:
        rows = compare_repository(repo_dir)
        all_rows.extend(rows)
        print(f"{repo_dir.name}: {len(rows)} snapshot intervals compared.")

    result = pd.DataFrame(all_rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT, index=False)

    print(
        f"\nRepositories processed: {result['repository'].nunique() if not result.empty else 0}"
    )
    print(f"Historical intervals: {len(result)}")

    if not result.empty:
        print("\nStructural change summary:")
        print(
            result[
                [
                    "repository",
                    "previous_snapshot",
                    "current_snapshot",
                    "package_jaccard_similarity",
                    "dependency_jaccard_similarity",
                    "architecture_change_score",
                ]
            ].to_string(index=False)
        )

    print(f"\nSaved: {OUTPUT}")
    print(
        "Interpretation: higher scores indicate more observed structural change. "
        "This is a proxy, not a validated architecture-drift label."
    )


if __name__ == "__main__":
    main()
