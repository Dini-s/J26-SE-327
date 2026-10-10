import re
import csv
from pathlib import Path
import argparse


def anlyze_structure(repo_path: str):
    "Analyze the java package structure of a reposiotry"

    path = Path(repo_path)

    if not path.exists():
        raise FileNotFoundError(f"Repository not found :{repo_path}")

    source_path = path / "src" / "main" / "java"

    if not source_path.exists():
        raise FileNotFoundError(f"Java source directory not found: {source_path}")

    packages = []

    for directory in source_path.rglob("*"):
        if directory.is_dir():
            java_files = list(directory.glob("*.java"))

            if java_files:
                relative_path = directory.relative_to(source_path)

                total_lines = 0

                for java_file in java_files:
                    try:
                        with open(java_file, "r", encoding="utf-8") as f:
                            total_lines += sum(1 for _ in f)

                    except UnicodeDecodeError:
                        print(f"Skipping unreadable file :{java_file}")

                packages.append(
                    {
                        "package_path": ".".join(relative_path.parts),
                        "java_files": len(java_files),
                        "lines_of_code": total_lines,
                    }
                )

    return packages


def analyze_multimodule_structure(repo_path: str):
    """Analyze Java packages across multiple repository modules."""

    path = Path(repo_path)

    if not path.is_dir():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    source_paths = set()

    # Discover nested src/main/java directories.
    for java_file in path.rglob("*.java"):
        relative_parts = java_file.relative_to(path).parts

        # Ignore hidden folders and generated build output.
        if any(part.startswith(".") for part in relative_parts):
            continue

        if any(part in {"build", "target"} for part in relative_parts):
            continue

        for i in range(len(relative_parts) - 2):
            if relative_parts[i : i + 3] == ("src", "main", "java"):
                source_paths.add(path.joinpath(*relative_parts[: i + 3]))
                break

    if not source_paths:
        raise FileNotFoundError(f"No Java source directories found in {path}")

    packages = {}

    for source_path in sorted(source_paths):
        for java_file in source_path.rglob("*.java"):
            try:
                with java_file.open("r", encoding="utf-8", errors="strict") as f:
                    total_lines = sum(1 for _ in f)
            except (UnicodeDecodeError, OSError) as exc:
                print(f"Skipping {java_file}: {exc}")
                continue

            relative_path = java_file.parent.relative_to(source_path)
            package_path = ".".join(relative_path.parts)

            if not package_path:
                package_path = "(default package)"

            if package_path not in packages:
                packages[package_path] = {
                    "package_path": package_path,
                    "java_files": 0,
                    "lines_of_code": 0,
                }

            packages[package_path]["java_files"] += 1
            packages[package_path]["lines_of_code"] += total_lines

    return list(packages.values())


def discover_java_source_roots(repo_path: Path):
    """Discover production Java source roots across repository modules."""

    source_roots = set()
    ignored_dirs = {
        ".git",
        ".idea",
        ".vscode",
        "build",
        "target",
        "out",
        "bin",
        "node_modules",
        "__pycache__",
    }
    test_dirs = {
        "test",
        "tests",
        "testing",
        "testfixtures",
        "integration-test",
    }

    for java_file in repo_path.rglob("*.java"):
        relative = java_file.relative_to(repo_path)
        parts = relative.parts

        if any(part.startswith(".") or part.lower() in ignored_dirs for part in parts):
            continue

        lower_parts = tuple(part.lower() for part in parts)

        # Standard Maven/Gradle production layout.
        found_standard_root = False

        for i in range(len(parts) - 2):
            if lower_parts[i : i + 3] == ("src", "main", "java"):
                source_roots.add(repo_path.joinpath(*parts[: i + 3]))
                found_standard_root = True
                break

        if found_standard_root:
            continue

        # Exclude test code from the production dataset.
        if any(part in test_dirs for part in lower_parts):
            continue

        # Support legacy layouts such as src/org/example/Class.java.
        for i, part in enumerate(lower_parts[:-1]):
            if part == "src":
                source_roots.add(repo_path.joinpath(*parts[: i + 1]))
                break

    return sorted(source_roots)


def analyze_discovered_structure(repo_path: Path, source_roots: list[Path]):
    """Aggregate Java metrics by declared package across source roots."""

    packages = {}
    processed_files = set()

    ignored_dirs = {
        ".git",
        ".idea",
        ".vscode",
        "build",
        "target",
        "out",
        "bin",
        "node_modules",
        "__pycache__",
    }
    test_dirs = {
        "test",
        "tests",
        "testing",
        "testfixtures",
        "integration-test",
    }

    package_pattern = re.compile(
        r"^\s*package\s+([\w.]+)\s*;",
        re.MULTILINE,
    )

    for source_root in source_roots:
        for java_file in source_root.rglob("*.java"):
            resolved_file = java_file.resolve()

            if resolved_file in processed_files:
                continue

            relative = java_file.relative_to(source_root)
            parts = relative.parts
            lower_parts = tuple(part.lower() for part in parts)

            if any(part.startswith(".") or part in ignored_dirs for part in parts):
                continue

            if any(part in test_dirs for part in lower_parts):
                continue

            # A legacy src root can also contain src/main/java.
            # Do not count those files a second time.
            if len(lower_parts) >= 2 and lower_parts[:2] == ("main", "java"):
                continue

            try:
                content = java_file.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError as exc:
                print(f"Skipping {java_file}: {exc}")
                continue

            processed_files.add(resolved_file)

            match = package_pattern.search(content)

            if match:
                package_path = match.group(1)
            else:
                package_path = "(default package)"

            if package_path not in packages:
                packages[package_path] = {
                    "package_path": package_path,
                    "java_files": 0,
                    "lines_of_code": 0,
                }

            packages[package_path]["java_files"] += 1
            packages[package_path]["lines_of_code"] += content.count("\n") + (
                1 if content else 0
            )

    return list(packages.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze the Java package structure of a repository"
    )

    parser.add_argument("repo_path", help="Path to the Git repository")

    args = parser.parse_args()

    repo_path = Path(args.repo_path)

    repo_path = repo_path.resolve()

    source_roots = discover_java_source_roots(repo_path)

    if not source_roots:
        raise FileNotFoundError(f"No Java source roots found in {repo_path}")

    packages = analyze_discovered_structure(repo_path, source_roots)

    repo_name = repo_path.name
    # output file create
    output_dir = Path("data/structural")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{repo_name}_structure.csv"

    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file, fieldnames=["package_path", "java_files", "lines_of_code"]
        )

        writer.writeheader()
        writer.writerows(packages)

    print("\nStructure analysis completed.")
    print(f"Packages found: {len(packages)}")
    print(f"Output saved to: {output_path}")
