import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = PROJECT_ROOT / "data"
STRUCTURAL_DIR = DATA_DIR / "structural"
DEPENDENCY_DIR = DATA_DIR / "dependencies"
EVOLUTION_DIR = DATA_DIR / "evolution"
ARCHITECTURE_DIR = DATA_DIR / "architecture"
OUTPUT_DIR = DATA_DIR / "processed"

AMBIGUOUS_PACKAGES = {
    "",
    "(default)",
    "(default package)",
    "(path-unresolved)",
    "(package-unresolved)",
    "pending",
}


def read_csv(path):
    """Read a CSV file and return its rows as dictionaries."""
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fieldnames):
    """Write rows to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def find_package_evolution_file(repository_id):
    """
    Find the best available package-level evolution CSV.

    Prefer a full-history file when available, then the fast analyzer output.
    Repository-level metrics are never substituted for package-level metrics.
    """
    candidates = [
        EVOLUTION_DIR / f"{repository_id}_package_evolution_historical_test.csv",
        EVOLUTION_DIR / f"{repository_id}_package_evolution_all_history.csv",
        EVOLUTION_DIR / f"{repository_id}_package_evolution_diagnostic.csv",
        EVOLUTION_DIR / f"{repository_id}_package_evolution_fast.csv",
        EVOLUTION_DIR / f"{repository_id}_package_evolution.csv",
        EVOLUTION_DIR / f"{repository_id}_package_evolution_v2.csv",
        EVOLUTION_DIR / f"{repository_id}_package_evolution_2025.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def load_package_evolution(path, repository_id):
    """Load exact package records and report ambiguous or duplicate entries."""
    if path is None:
        return {}, {
            "source": "not available",
            "rows_read": 0,
            "ambiguous_rows": 0,
            "duplicate_packages": [],
        }

    rows = read_csv(path)
    indexed = {}
    ambiguous_rows = 0
    duplicate_packages = []

    for row in rows:
        row_repository = row.get("repository", "").strip()
        if row_repository and row_repository != repository_id:
            continue

        package = row.get("package_path", "").strip()
        if package in AMBIGUOUS_PACKAGES:
            ambiguous_rows += 1
            continue

        if package in indexed:
            duplicate_packages.append(package)
            # Do not silently replace the first record with a duplicate.
            continue

        indexed[package] = row

    return indexed, {
        "source": path.name,
        "rows_read": len(rows),
        "ambiguous_rows": ambiguous_rows,
        "duplicate_packages": sorted(set(duplicate_packages)),
    }


def index_packages(rows, source_name):
    """Create a package index and return duplicate package names."""
    indexed = {}
    duplicates = []

    for row in rows:
        package = row.get("package_path", "").strip()
        if not package:
            continue
        if package in indexed:
            duplicates.append(package)
            continue
        indexed[package] = row

    if duplicates:
        raise ValueError(
            f"Duplicate package names in {source_name}: "
            + ", ".join(sorted(set(duplicates))[:10])
        )

    return indexed


def build_dataset():
    """
    Build package features and dependency edges.

    Package rows are created from the UNION of structural and architecture
    packages, so a structural package is not dropped just because it is absent
    from the architecture CSV. Missing metrics remain blank; they are not
    imputed as zero.
    """
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
        "evolution_status",
        "evolution_activity_status",
    ]

    for architecture_file in architecture_files:
        repository_id = architecture_file.name.removesuffix("_architecture.csv")
        structural_file = STRUCTURAL_DIR / f"{repository_id}_structure.csv"
        dependency_file = DEPENDENCY_DIR / f"{repository_id}_dependencies.csv"

        missing_files = [
            str(path.relative_to(PROJECT_ROOT))
            for path in (structural_file, dependency_file)
            if not path.exists()
        ]
        if missing_files:
            validation_rows.append(
                {
                    "repository": repository_id,
                    "status": "INCOMPLETE",
                    "details": "Missing required files: " + "; ".join(missing_files),
                }
            )
            continue

        structural_data = read_csv(structural_file)
        architecture_data = read_csv(architecture_file)
        dependency_data = read_csv(dependency_file)

        try:
            structural_by_package = index_packages(
                structural_data, structural_file.name
            )
            architecture_by_package = index_packages(
                architecture_data, architecture_file.name
            )
        except ValueError as exc:
            validation_rows.append(
                {
                    "repository": repository_id,
                    "status": "INVALID",
                    "details": str(exc),
                }
            )
            continue

        package_evolution_file = find_package_evolution_file(repository_id)
        evolution_by_package, evolution_info = load_package_evolution(
            package_evolution_file, repository_id
        )

        # Exclude unresolved package placeholders consistently.
        valid_structural_packages = {
            package
            for package in structural_by_package
            if package not in AMBIGUOUS_PACKAGES
        }

        valid_architecture_packages = {
            package
            for package in architecture_by_package
            if package not in AMBIGUOUS_PACKAGES
        }

        # Preserve valid packages from either source.
        all_packages = sorted(valid_structural_packages | valid_architecture_packages)

        repository_package_rows = []
        evolution_matches = 0
        evolution_missing = 0
        structural_only_count = 0
        architecture_only_count = 0

        for package in all_packages:
            structure = structural_by_package.get(package)
            architecture = architecture_by_package.get(package)
            evolution = evolution_by_package.get(package)

            if structure is not None and architecture is not None:
                package_origin = "structural"
            elif structure is not None:
                package_origin = "structural_only"
                structural_only_count += 1
            else:
                package_origin = "dependency_only"
                architecture_only_count += 1

            if evolution is not None:
                evolution_matches += 1
                evolution_status = "exact_package_match"
            else:
                evolution_missing += 1
                evolution_status = (
                    "no_evolution_file"
                    if package_evolution_file is None
                    else "missing_evolution_record"
                )

            # Empty strings mean unavailable/unmatched metrics, not zero activity.
            repository_package_rows.append(
                {
                    "repository": repository_id,
                    "package_path": package,
                    "package_origin": package_origin,
                    "java_files": structure.get("java_files", "") if structure else "",
                    "lines_of_code": structure.get("lines_of_code", "")
                    if structure
                    else "",
                    "fan_in": architecture.get("fan_in", "") if architecture else "",
                    "fan_out": architecture.get("fan_out", "") if architecture else "",
                    "total_coupling": architecture.get("total_coupling", "")
                    if architecture
                    else "",
                    "instability": architecture.get("instability", "")
                    if architecture
                    else "",
                    "commit_count": evolution.get("commit_count", "")
                    if evolution
                    else "",
                    "contributor_count": evolution.get("contributor_count", "")
                    if evolution
                    else "",
                    "files_changed": evolution.get("files_changed", "")
                    if evolution
                    else "",
                    "total_insertions": evolution.get("total_insertions", "")
                    if evolution
                    else "",
                    "total_deletions": evolution.get("total_deletions", "")
                    if evolution
                    else "",
                    "total_churn": evolution.get("total_churn", "")
                    if evolution
                    else "",
                    "evolution_status": evolution_status,
                    "evolution_activity_status": (
                        evolution.get("activity_status") or "unknown"
                        if evolution
                        else "unknown"
                    ),
                }
            )

        # Preserve unique dependency relationships separately.
        seen_edges = set()
        repository_edges = []
        for edge in dependency_data:
            source = edge.get("source_package", "").strip()
            target = edge.get("target_package", "").strip()
            if not source or not target:
                continue

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

        status = "OK"
        messages = []

        if package_evolution_file is None:
            status = "WARNING"
            messages.append("No package-level evolution CSV available.")
        elif evolution_info["duplicate_packages"]:
            status = "WARNING"
            messages.append(
                "Duplicate evolution records detected: "
                + ", ".join(evolution_info["duplicate_packages"][:5])
            )

        if evolution_missing:
            status = "WARNING"
            messages.append(
                f"{evolution_missing} packages lack exact evolution records; "
                f"{evolution_matches} matched."
            )
        if structural_only_count:
            status = "WARNING"
            messages.append(
                f"{structural_only_count} structural packages lack architecture records "
                "and were retained with blank architecture features."
            )
        if architecture_only_count:
            messages.append(
                f"{architecture_only_count} architecture packages lack structural records."
            )
        if evolution_info["ambiguous_rows"]:
            messages.append(
                f"{evolution_info['ambiguous_rows']} ambiguous evolution rows excluded."
            )

        details = (
            f"Packages: {len(repository_package_rows)}; "
            f"unique dependency edges: {len(repository_edges)}; "
            f"evolution source: {evolution_info['source']}; "
            f"evolution matches: {evolution_matches}; "
            f"evolution missing: {evolution_missing}; "
            f"structural-only packages retained: {structural_only_count}; "
            f"architecture-only packages: {architecture_only_count}. "
            + " ".join(messages)
        )

        validation_rows.append(
            {
                "repository": repository_id,
                "status": status,
                "details": details,
            }
        )

        print(
            f"{repository_id}: packages={len(repository_package_rows)}, "
            f"evolution matches={evolution_matches}, "
            f"evolution missing={evolution_missing}, "
            f"structural-only={structural_only_count}, "
            f"architecture-only={architecture_only_count}, "
            f"edges={len(repository_edges)}"
        )

    # Write the outputs using the established filenames and package schema.
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

    print("\n=== HRIM Dataset Summary ===")
    print(f"Repositories discovered: {len(architecture_files)}")
    print(f"Validation entries: {len(validation_rows)}")
    print(f"Package samples created: {len(package_rows)}")
    print(f"Dependency edges exported: {len(dependency_rows)}")
    print(f"Package feature dataset: {OUTPUT_DIR / 'hrim_package_features.csv'}")
    print(f"Dependency dataset: {OUTPUT_DIR / 'dependency_edges.csv'}")
    print(f"Validation report: {OUTPUT_DIR / 'dataset_validation_report.csv'}")
    print("Dataset preparation completed.")


if __name__ == "__main__":
    build_dataset()
