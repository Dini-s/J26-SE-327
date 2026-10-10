import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = PROJECT_ROOT / "data"
STRUCTURAL_DIR = DATA_DIR / "structural"
DEPENDENCY_DIR = DATA_DIR / "dependencies"
EVOLUTION_DIR = DATA_DIR / "evolution"
ARCHITECTURE_DIR = DATA_DIR / "architecture"
OUTPUT_DIR = DATA_DIR / "processed"


def read_csv(path):
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_dataset():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    package_rows = []
    dependency_rows = []
    validation_rows = []

    architecture_files = sorted(ARCHITECTURE_DIR.glob("*_architecture.csv"))

    if not architecture_files:
        raise FileNotFoundError(
            f"No architecture CSV files found in {ARCHITECTURE_DIR}"
        )

    package_fields = [
        "repository",
        "package_path",
        "package_origin",
        "java_files",
        "lines_of_code",
        "fan_in",
        "fan_out",
        "total_coupling",
        "instability",
        "commit_count",
        "contributor_count",
        "files_changed",
        "total_insertions",
        "total_deletions",
        "total_churn",
    ]

    for architecture_file in architecture_files:
        repository_id = architecture_file.name.removesuffix("_architecture.csv")

        structural_file = STRUCTURAL_DIR / f"{repository_id}_structure.csv"
        dependency_file = DEPENDENCY_DIR / f"{repository_id}_dependencies.csv"
        evolution_file = EVOLUTION_DIR / f"{repository_id}_evolution.csv"

        required_files = [
            structural_file,
            dependency_file,
            evolution_file,
        ]

        missing_files = [
            str(path.relative_to(PROJECT_ROOT))
            for path in required_files
            if not path.exists()
        ]

        if missing_files:
            validation_rows.append(
                {
                    "repository": repository_id,
                    "status": "INCOMPLETE",
                    "details": "Missing: " + "; ".join(missing_files),
                }
            )
            continue

        structural_data = read_csv(structural_file)
        architecture_data = read_csv(architecture_file)
        dependency_data = read_csv(dependency_file)
        evolution_data = read_csv(evolution_file)

        if len(evolution_data) != 1:
            validation_rows.append(
                {
                    "repository": repository_id,
                    "status": "INVALID",
                    "details": (
                        "Expected one repository-level evolution row; "
                        f"found {len(evolution_data)}"
                    ),
                }
            )
            continue

        evolution = evolution_data[0]

        if evolution.get("repository") != repository_id:
            validation_rows.append(
                {
                    "repository": repository_id,
                    "status": "INVALID",
                    "details": "Evolution repository ID does not match filename",
                }
            )
            continue

        # Index structural features by package.
        structural_by_package = {}
        duplicate_structural_packages = []

        for row in structural_data:
            package = row["package_path"]

            if package in structural_by_package:
                duplicate_structural_packages.append(package)
                continue

            structural_by_package[package] = row

        if duplicate_structural_packages:
            validation_rows.append(
                {
                    "repository": repository_id,
                    "status": "INVALID",
                    "details": (
                        "Duplicate structural packages: "
                        + "; ".join(duplicate_structural_packages[:5])
                    ),
                }
            )
            continue

        architecture_packages = set()
        duplicate_architecture_packages = []
        missing_structural_packages = []
        repository_package_rows = []

        for architecture in architecture_data:
            package = architecture["package_path"]

            if package in architecture_packages:
                duplicate_architecture_packages.append(package)
                continue

            architecture_packages.add(package)
            structure = structural_by_package.get(package)

            if structure is None:
                missing_structural_packages.append(package)

            package_origin = (
                "structural" if structure is not None else "dependency_only"
            )

            # Keep the package even if structural metrics are unavailable.
            # Empty strings indicate missing values, not measured zeros.
            repository_package_rows.append(
                {
                    "repository": repository_id,
                    "package_path": package,
                    "package_origin": package_origin,
                    "java_files": (structure["java_files"] if structure else ""),
                    "lines_of_code": (structure["lines_of_code"] if structure else ""),
                    "fan_in": architecture["fan_in"],
                    "fan_out": architecture["fan_out"],
                    "total_coupling": architecture["total_coupling"],
                    "instability": architecture["instability"],
                    "commit_count": evolution["commit_count"],
                    "contributor_count": evolution["contributor_count"],
                    "files_changed": evolution["files_changed"],
                    "total_insertions": evolution["total_insertions"],
                    "total_deletions": evolution["total_deletions"],
                    "total_churn": evolution["total_churn"],
                }
            )

        if duplicate_architecture_packages:
            validation_rows.append(
                {
                    "repository": repository_id,
                    "status": "INVALID",
                    "details": (
                        "Duplicate architecture packages: "
                        + "; ".join(duplicate_architecture_packages[:5])
                    ),
                }
            )
            continue

        # Preserve dependency relationships as a separate edge dataset.
        seen_edges = set()
        repository_edges = []

        for edge in dependency_data:
            source = edge["source_package"]
            target = edge["target_package"]
            edge_key = (source, target)

            if edge_key in seen_edges:
                continue

            seen_edges.add(edge_key)

            repository_edges.append(
                {
                    "repository": repository_id,
                    "source_package": source,
                    "target_package": target,
                }
            )

        package_rows.extend(repository_package_rows)
        dependency_rows.extend(repository_edges)

        if missing_structural_packages:
            validation_rows.append(
                {
                    "repository": repository_id,
                    "status": "WARNING",
                    "details": (
                        f"{len(missing_structural_packages)} architecture "
                        "packages missing from structural CSV. "
                        "Their structural values were left blank. Examples: "
                        + "; ".join(missing_structural_packages[:3])
                    ),
                }
            )
        else:
            validation_rows.append(
                {
                    "repository": repository_id,
                    "status": "OK",
                    "details": (
                        f"{len(repository_package_rows)} packages matched; "
                        f"{len(repository_edges)} unique dependency edges"
                    ),
                }
            )

    write_csv(
        OUTPUT_DIR / "hrim_package_features.csv",
        package_rows,
        package_fields,
    )

    write_csv(
        OUTPUT_DIR / "dependency_edges.csv",
        dependency_rows,
        ["repository", "source_package", "target_package"],
    )

    write_csv(
        OUTPUT_DIR / "dataset_validation_report.csv",
        validation_rows,
        ["repository", "status", "details"],
    )

    print(f"Repositories discovered: {len(architecture_files)}")
    print(f"Validation entries: {len(validation_rows)}")
    print(f"Package samples created: {len(package_rows)}")
    print(f"Dependency edges exported: {len(dependency_rows)}")
    print(f"Package dataset: {OUTPUT_DIR / 'hrim_package_features.csv'}")
    print(f"Dependency dataset: {OUTPUT_DIR / 'dependency_edges.csv'}")
    print(f"Validation report: {OUTPUT_DIR / 'dataset_validation_report.csv'}")
    print("Dataset preparation completed.")


if __name__ == "__main__":
    build_dataset()
