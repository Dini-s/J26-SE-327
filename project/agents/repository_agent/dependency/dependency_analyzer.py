import csv
import re
from pathlib import Path
import argparse

JAVA_PACKAGE_PATTERN = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)

JAVA_IMPORT_PATTERN = re.compile(r"^\s*import\s+(?!static\s)([\w.]+)\s*;", re.MULTILINE)


def read_java_file(java_file: Path):
    """Read a Java source file safely."""

    try:
        return java_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def get_java_files(source_path: Path):
    """Return all Java source files"""
    return list(source_path.rglob("*.java"))


def extract_package(content: str):
    """Extract the package declaration from a Java file."""

    match = JAVA_PACKAGE_PATTERN.search(content)

    if match:
        return match.group(1)

    return None


def extract_imports(content: str):
    """Extract non-static Java imports"""
    return JAVA_IMPORT_PATTERN.findall(content)


def analyze_dependencies(repo_path: str):
    path = Path(repo_path)

    if not path.exists():
        raise FileNotFoundError(f"Repository not found :{repo_path}")

    source_path = path / "src" / "main" / "java"

    if not source_path.exists():
        raise FileNotFoundError(f"Java source directory not found : {source_path}")

    java_files = list(source_path.rglob("*.java"))

    print(f"java files discovered : {len(java_files)}")

    # discover all packages in the repository

    repository_packages = set()
    java_file_data = []

    for java_file in java_files:
        content = read_java_file(java_file)

        if content is None:
            continue

        package_name = extract_package(content)
        imports = extract_imports(content)

        if imports:
            print(f"\nFile: {java_file.name}")
            print(f"Package: {package_name}")

            for imported in imports:
                print(f"  Import: {imported}")

        if package_name:
            repository_packages.add(package_name)

        java_file_data.append(
            {"file": java_file, "package": package_name, "imports": imports}
        )

    print(f"Packages discovered: {len(repository_packages)}")

    for package in sorted(repository_packages):
        print(f"  - {package}")

    # create dependency relationships
    dependencies = set()

    for file_data in java_file_data:
        source_package = file_data["package"]

        if not source_package:
            continue

        for imported_class in file_data["imports"]:
            imported_parts = imported_class.split(".")

            if len(imported_parts) < 2:
                continue

            imported_package = ".".join(imported_parts[:-1])

            target_package = None

            for repository_package in repository_packages:
                if (
                    imported_package == repository_package
                    or imported_package.startswith(repository_package + ".")
                ):
                    target_package = repository_package
                    break

            if not target_package:
                continue

            # ignore self dependencies
            if source_package == target_package:
                continue

            dependencies.add((source_package, target_package))

    return sorted(dependencies), len(java_files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Analyze Java package dependenciesdynamically")
    )

    parser.add_argument("repo_path", help="Path to the Git Repository")

    args = parser.parse_args()

    repo_path = Path(args.repo_path)

    dependencies, java_file_count = analyze_dependencies(repo_path)

    # output
    output_dir = Path("data/dependencies")
    output_dir.mkdir(parents=True, exist_ok=True)

    repo_name = repo_path.name

    output_path = output_dir / f"{repo_name}_dependencies.csv"

    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["source_package", "target_package"])

        writer.writeheader()

        for source, target in dependencies:
            writer.writerow({"source_package": source, "target_package": target})

    print("\nDependency analysis completed.")
    print(f"Repository: {repo_name}")
    print(f"Java files analyzed: {java_file_count}")
    print(f"Dependencies found: {len(dependencies)}")
    print(f"Output saved to: {output_path}")
