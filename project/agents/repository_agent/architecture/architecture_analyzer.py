import argparse
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def read_csv(file_path):
    """Read a csv file and return its rows"""

    if not file_path.exists():
        raise FileNotFoundError(f"Required input file not found : {file_path}")

    with file_path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def calculate_architecture_metrics(repo_name):
    """Calculate package-level architecture metrics"""

    structural_file = (
        PROJECT_ROOT / "data" / "structural" / f"{repo_name}_structure.csv"
    )

    dependency_file = (
        PROJECT_ROOT / "data" / "dependencies" / f"{repo_name}_dependencies.csv"
    )

    structural_rows = read_csv(structural_file)
    dependency_rows = read_csv(dependency_file)

    # create one record per package
    packages = {}

    for row in structural_rows:
        package = row.get("package_path", "").strip()

        if not package:
            continue

        packages[package] = {
            "repository": repo_name,
            "package_path": package,
            "java_files": int(row.get("java_files") or 0),
            "lines_of_code": int(row.get("lines_of_code") or 0),
            "fan_in": 0,
            "fan_out": 0,
        }

    edges = set()

    for row in dependency_rows:
        source = row.get("source_package", "").strip()
        target = row.get("target_package", "").strip()

        if not source or not target:
            continue

        if source == target:
            continue

        edges.add((source, target))

        # include dependency package if the structural aalyzer did not include them
        for package in (source, target):
            if package not in packages:
                packages[package] = {
                    "repository": repo_name,
                    "package_path": package,
                    "java_files": 0,
                    "lines_of_code": 0,
                    "fan_in": 0,
                    "fan_out": 0,
                }

    # calculate incloming ad outgoing dependencies
    for source, target in edges:
        packages[source]["fan_out"] += 1
        packages[target]["fan_in"] += 1

    # calculate coupling and instability
    for package_data in packages.values():
        fan_in = package_data["fan_in"]
        fan_out = package_data["fan_out"]

        package_data["total_coupling"] = fan_in + fan_out

        denominator = fan_in + fan_out

        package_data["instability"] = fan_out / denominator if denominator else 0.0

    return list(packages.values())


def save_metrics(repo_name, metrics):
    output_dir = PROJECT_ROOT / "data" / "architecture"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{repo_name}_architecture.csv"

    fieldnames = [
        "repository",
        "package_path",
        "java_files",
        "lines_of_code",
        "fan_in",
        "fan_out",
        "total_coupling",
        "instability",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(metrics)

    return output_file


def main():

    parser = argparse.ArgumentParser(
        description="Calculate reposiotry architecture metrics"
    )

    parser.add_argument("repo_path", help="Path to the repository being analyzed")

    args = parser.parse_args()
    repo_path = Path(args.repo_path)

    if not repo_path.is_absolute():
        repo_path = Path.cwd() / repo_path

    if not repo_path.is_absolute():
        repo_path = Path.cwd() / repo_path

    if not repo_path.is_dir():
        raise FileNotFoundError(f"Repository directory not found:{repo_path}")

    repo_name = repo_path.name

    print(f"Repository: {repo_name}")
    print("Calculating architecture metrics...")

    metrics = calculate_architecture_metrics(repo_name)

    output_file = save_metrics(repo_name, metrics)

    print(f"Packages analyzed:{len(metrics)}")
    print(f"Dependency edges:{sum(row['fan_out'] for row in metrics)}")
    print(f"Output saved to : {output_file}")
    print("Architecture analysis completed")


if __name__ == "__main__":
    main()
