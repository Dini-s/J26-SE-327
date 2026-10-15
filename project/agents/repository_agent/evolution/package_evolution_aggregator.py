import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]

PACKAGE_PATTERN = re.compile(
    r"^\s*package\s+([\w.]+)\s*;",
    re.MULTILINE,
)

METRIC_COLUMNS = [
    "change_records",
    "commit_count",
    "total_insertions",
    "total_deletions",
    "total_churn",
]


def read_java_package(file_path):
    """Read the declared Java package from a source file."""
    try:
        source = file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        return None

    match = PACKAGE_PATTERN.search(source)
    return match.group(1) if match else None


def aggregate_by_package(repo_path, evolution_csv, architecture_csv):
    evolution = pd.read_csv(evolution_csv)
    architecture = pd.read_csv(architecture_csv)

    required_evolution = {"file_path", *METRIC_COLUMNS}
    required_architecture = {"repository", "package_path"}

    if not required_evolution.issubset(evolution.columns):
        raise ValueError(f"Evolution CSV must contain: {sorted(required_evolution)}")

    if not required_architecture.issubset(architecture.columns):
        raise ValueError(
            f"Architecture CSV must contain: {sorted(required_architecture)}"
        )

    # Keep only packages present in the architecture analyzer output.
    known_packages = set(architecture["package_path"].dropna().astype(str))

    stats = defaultdict(
        lambda: {
            "production_java_files": 0,
            "production_change_records": 0,
            "production_commit_count_sum": 0,
            "production_insertions": 0,
            "production_deletions": 0,
            "production_churn": 0,
            "test_java_files": 0,
            "test_change_records": 0,
            "test_commit_count_sum": 0,
            "test_insertions": 0,
            "test_deletions": 0,
            "test_churn": 0,
        }
    )

    matched_production_files = 0
    matched_test_files = 0
    unmatched_packages = set()

    for _, row in evolution.iterrows():
        relative_path = str(row["file_path"]).replace("\\", "/")
        path = Path(relative_path)

        if path.suffix.lower() != ".java":
            continue

        if relative_path.startswith("src/main/java/"):
            category = "production"
        elif relative_path.startswith("src/test/java/"):
            category = "test"
        else:
            continue

        java_file = repo_path / Path(relative_path)
        if not java_file.is_file():
            continue

        package = read_java_package(java_file)
        if not package:
            continue

        if package not in known_packages:
            unmatched_packages.add(package)
            continue

        prefix = f"{category}_"
        item = stats[package]

        item[prefix + "java_files"] += 1

        for metric in METRIC_COLUMNS:
            value = int(row[metric])
            if metric == "change_records":
                item[prefix + "change_records"] += value
            elif metric == "commit_count":
                item[prefix + "commit_count_sum"] += value
            elif metric == "total_insertions":
                item[prefix + "insertions"] += value
            elif metric == "total_deletions":
                item[prefix + "deletions"] += value
            elif metric == "total_churn":
                item[prefix + "churn"] += value

        if category == "production":
            matched_production_files += 1
        else:
            matched_test_files += 1

    output_rows = []

    for package in sorted(known_packages):
        values = stats[package]
        production_files = values["production_java_files"]
        test_files = values["test_java_files"]

        output_rows.append(
            {
                "repository": (
                    str(architecture["repository"].iloc[0])
                    if not architecture.empty
                    else repo_path.name
                ),
                "package_path": package,
                **values,
                "production_average_churn_per_file": (
                    values["production_churn"] / production_files
                    if production_files
                    else 0.0
                ),
                "test_average_churn_per_file": (
                    values["test_churn"] / test_files if test_files else 0.0
                ),
            }
        )

    return (
        pd.DataFrame(output_rows),
        matched_production_files,
        matched_test_files,
        unmatched_packages,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate file-level evolution metrics by Java package"
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--repo-id", required=True)
    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()
    if not repo_path.is_dir():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    evolution_csv = (
        PROJECT_ROOT / "data" / "evolution" / f"{args.repo_id}_file_evolution.csv"
    )
    architecture_csv = (
        PROJECT_ROOT / "data" / "architecture" / f"{args.repo_id}_architecture.csv"
    )

    if not evolution_csv.is_file():
        raise FileNotFoundError(f"Missing evolution CSV: {evolution_csv}")
    if not architecture_csv.is_file():
        raise FileNotFoundError(f"Missing architecture CSV: {architecture_csv}")

    result, production_count, test_count, unmatched = aggregate_by_package(
        repo_path,
        evolution_csv,
        architecture_csv,
    )

    output_dir = PROJECT_ROOT / "data" / "evolution"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{args.repo_id}_package_evolution.csv"
    result.to_csv(output_file, index=False)

    print(f"Repository: {args.repo_id}")
    print(f"Architecture packages: {len(result)}")
    print(f"Matched production Java files: {production_count}")
    print(f"Matched test Java files: {test_count}")
    print(f"Unmatched package names: {len(unmatched)}")
    if unmatched:
        print("Examples of unmatched packages:")
        for package in sorted(unmatched)[:10]:
            print(f"  {package}")
    print(f"Saved: {output_file}")
    print(result.head().to_string(index=False))


if __name__ == "__main__":
    main()
