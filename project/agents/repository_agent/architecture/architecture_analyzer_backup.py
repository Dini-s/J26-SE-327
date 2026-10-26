import argparse
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def read_csv(file_path):
    """Read a CSV file and return its rows."""
    if not file_path.exists():
        raise FileNotFoundError(f"Required input file not found: {file_path}")

    with file_path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def calculate_architecture_metrics(repo_name):
    """Calculate architecture metrics for structurally analyzed packages only."""

    structural_file = (
        PROJECT_ROOT / "data" / "structural" / f"{repo_name}_structure.csv"
    )
    dependency_file = (
        PROJECT_ROOT / "data" / "dependencies" / f"{repo_name}_dependencies.csv"
    )

    structural_rows = read_csv(structural_file)
    dependency_rows = read_csv(dependency_file)

    # The structural CSV is the authoritative package list for this analysis.
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

    structural_package_names = set(packages)
    edges = set()
    excluded_edges = set()
    blank_edges = 0
    self_edges = 0

    for row in dependency_rows:
        source = row.get("source_package", "").strip()
        target = row.get("target_package", "").strip()

        if not source or not target:
            blank_edges += 1
            continue

        if source == target:
            self_edges += 1
            continue

        # Keep an edge in architecture metrics only if both endpoints
        # have structural measurements in the accepted package scope.
        if (
            source not in structural_package_names
            or target not in structural_package_names
        ):
            excluded_edges.add((source, target))
            continue

        edges.add((source, target))

    # Calculate incoming and outgoing dependencies for accepted packages.
    for source, target in edges:
        packages[source]["fan_out"] += 1
        packages[target]["fan_in"] += 1

    # Coupling and instability are calculated from the filtered edge set.
    for package_data in packages.values():
        fan_in = package_data["fan_in"]
        fan_out = package_data["fan_out"]
        package_data["total_coupling"] = fan_in + fan_out
        denominator = fan_in + fan_out
        package_data["instability"] = fan_out / denominator if denominator else 0.0

    metrics = list(packages.values())

    audit = {
        "repository": repo_name,
        "structural_packages": len(structural_package_names),
        "accepted_dependency_edges": len(edges),
        "excluded_dependency_edges": len(excluded_edges),
        "blank_dependency_rows": blank_edges,
        "self_dependency_rows": self_edges,
    }

    return metrics, audit


def save_metrics(repo_name, metrics):
    """Save architecture metrics."""
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
        description=(
            "Calculate architecture metrics for structurally analyzed "
            "Java packages in a repository"
        )
    )
    parser.add_argument("repo_path", help="Path to the repository being analyzed")
    args = parser.parse_args()

    repo_path = Path(args.repo_path)
    if not repo_path.is_absolute():
        repo_path = (Path.cwd() / repo_path).resolve()

    if not repo_path.is_dir():
        raise FileNotFoundError(f"Repository directory not found: {repo_path}")

    repo_name = repo_path.name
    print(f"Repository: {repo_name}")
    print("Calculating architecture metrics using structural package scope...")

    metrics, audit = calculate_architecture_metrics(repo_name)
    output_file = save_metrics(repo_name, metrics)

    # Write a per-repository audit so excluded edges are visible and reproducible.
    audit_dir = PROJECT_ROOT / "data" / "processed" / "architecture_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / f"{repo_name}_architecture_scope_audit.csv"

    with audit_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(audit.keys()))
        writer.writeheader()
        writer.writerow(audit)

    print(f"Structural packages analyzed: {len(metrics)}")
    print(f"Accepted dependency edges: {audit['accepted_dependency_edges']}")
    print(f"Excluded dependency edges: {audit['excluded_dependency_edges']}")
    print(f"Blank dependency rows skipped: {audit['blank_dependency_rows']}")
    print(f"Self-dependency rows skipped: {audit['self_dependency_rows']}")
    print(f"Architecture output saved to: {output_file}")
    print(f"Scope audit saved to: {audit_file}")
    print("Architecture analysis completed.")


if __name__ == "__main__":
    main()
