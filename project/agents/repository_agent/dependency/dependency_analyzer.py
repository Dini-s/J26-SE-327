import argparse
import csv
import re
from pathlib import Path


JAVA_PACKAGE_PATTERN = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)

JAVA_IMPORT_PATTERN = re.compile(r"^\s*import\s+(?!static\s)([\w.]+)\s*;", re.MULTILINE)

TYPE_PATTERN = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)\b")

EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "target",
    "build",
    "out",
    "dist",
    ".gradle",
    ".mvn",
    "vendor",
}


def read_java_file(java_file: Path):
    """Read a Java source file safely."""

    try:
        return java_file.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def discover_java_files(repo_path: Path):
    """Discover Java files across common source layouts"""

    java_files = set()

    # common source roots
    source_roots = [
        "src/main/java",
        "src/test/java",
        "src/java",
        "src",
        "source",
        "java",
    ]

    for relative_root in source_roots:
        source_root = repo_path / relative_root

        if not source_root.is_dir():
            continue

        for java_file in source_root.rglob("*.java"):
            if any(part in EXCLUDED_DIRS for part in java_file.parts):
                continue

            java_files.add(java_file.resolve())

    for java_file in repo_path.rglob("*java"):
        if any(part in EXCLUDED_DIRS for part in java_file.parts):
            continue

        java_files.add(java_file.resolve())

    return sorted(java_files)


def get_java_files(source_path: Path):
    """Return all Java source files"""
    return list(source_path.rglob("*.java"))


def extract_package(content: str):
    """Extract the package declaration from a Java file."""

    match = JAVA_PACKAGE_PATTERN.search(content)

    return match.group(1) if match else ""


def extract_imports(content: str):
    """Extract non-static Java imports"""
    return JAVA_IMPORT_PATTERN.findall(content)


def extract_declared_types(content: str):
    """Extract basic class, interface, enum, and record names."""
    return set(TYPE_PATTERN.findall(content))


def analyze_dependencies(repo_path: Path):

    repo_path = repo_path.resolve()

    if not repo_path.is_dir():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    java_files = discover_java_files(repo_path)

    if not java_files:
        raise FileNotFoundError(f"No Java files found in :{repo_path}")

    repository_packages = set()
    class_to_package = {}
    file_records = []
    unreadable_files = 0

    # discover packages and declared types
    for java_file in java_files:
        content = read_java_file(java_file)

        if content is None:
            unreadable_files += 1
            continue

        package_name = extract_package(content)
        imports = extract_imports(content)
        declared_types = extract_declared_types(content)

        if package_name:
            repository_packages.add(package_name)

        for type_name in declared_types:
            qualified_name = (
                f"{package_name}.{type_name}" if package_name else type_name
            )
            class_to_package[qualified_name] = package_name

        file_records.append(
            {"file": java_file, "package": package_name, "imports": imports}
        )

    # resolve imports against discovered repository classes
    dependencies = set()
    unresolved_imports = 0

    for record in file_records:
        source_package = record["package"]

        if not source_package:
            continue

        for imported_name in record["imports"]:
            if imported_name.endswith(".*"):
                target_package = imported_name[:-2]

                if target_package not in repository_packages:
                    continue

            else:
                target_package = class_to_package.get(imported_name)

                if target_package is None:
                    unresolved_imports += 1
                    continue

            if not target_package:
                continue

            if source_package == target_package:
                continue

            dependencies.add((source_package, target_package))

    return {
        "java_files_discovered": len(java_files),
        "java_files_analyzed": len(file_records),
        "unreadable_files": unreadable_files,
        "package_count": len(repository_packages),
        "declared_types": len(class_to_package),
        "unresolved_imports": unresolved_imports,
        "dependencies": sorted(dependencies),
    }


def save_dependencies(output_path: Path, dependencies):
    """Write dependency edges to a CSV file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "source_package",
                "target_package",
            ],
        )
        writer.writeheader()

        for source, target in dependencies:
            writer.writerow({"source_package": source, "target_package": target})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Analyze Java package dependenciesdynamically")
    )

    parser.add_argument("repo_path", help="Path to the Git Repository")

    parser.add_argument(
        "--output-dir",
        default="data/dependencies",
        help="Directory for generated dependency CSV files",
    )

    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()

    if not repo_path.is_dir():
        raise FileNotFoundError(f"Repository direcory not found: {repo_path}")

    result = analyze_dependencies(repo_path)

    repo_name = repo_path.name
    output_dir = Path(args.output_dir)

    if not output_dir.is_absolute():
        output_dir = Path.cwd() / output_dir

    output_path = output_dir / f"{repo_name}_dependencies.csv"

    save_dependencies(
        output_path,
        result["dependencies"],
    )

    print(f"Repository: {repo_name}")
    print(f"Java files discovered: {result['java_files_discovered']}")
    print(f"Java files analyzed: {result['java_files_analyzed']}")
    print(f"Packages discovered: {result['package_count']}")
    print(f"Declared types mapped: {result['declared_types']}")
    print(f"Unique internal dependency edges: {len(result['dependencies'])}")
    print(f"Unresolved imports: {result['unresolved_imports']}")
    print(f"Unreadable files skipped: {result['unreadable_files']}")
    print(f"Output saved to: {output_path}")

    if result["dependencies"]:
        print("\nDetected dependencies:")

        for source, target in result["dependencies"]:
            print(f"{source}->{target}")

    else:
        print(
            "\nNo internal dependencies resolved. "
            "Review source discovery and import resolution."
        )
