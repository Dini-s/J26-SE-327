import argparse
import csv
import re
from pathlib import Path

TEST_MODULE_DIRS = {
    "test",
    "tests",
    "testing",
    "testsuite",
    "testframework",
    "testfixtures",
    "test-fixtures",
    "integration-test",
    "integration-tests",
}

IGNORED_DIRS = {
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


def anlyze_structure(repo_path: str):
    """Analyze a single src/main/java tree."""
    path = Path(repo_path)
    if not path.exists():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    source_path = path / "src" / "main" / "java"
    if not source_path.exists():
        raise FileNotFoundError(f"Java source directory not found: {source_path}")

    packages = []
    for directory in source_path.rglob("*"):
        if not directory.is_dir():
            continue

        java_files = list(directory.glob("*.java"))
        if not java_files:
            continue

        relative_path = directory.relative_to(source_path)
        total_lines = 0
        readable_files = 0

        for java_file in java_files:
            try:
                with java_file.open("r", encoding="utf-8") as file:
                    total_lines += sum(1 for _ in file)
                readable_files += 1
            except (UnicodeDecodeError, OSError) as exc:
                print(f"Skipping unreadable file {java_file}: {exc}")

        if readable_files:
            packages.append(
                {
                    "package_path": ".".join(relative_path.parts),
                    "java_files": readable_files,
                    "lines_of_code": total_lines,
                }
            )

    return packages


def analyze_multimodule_structure(repo_path: str):
    """Analyze Java packages across standard src/main/java module roots."""
    path = Path(repo_path)
    if not path.is_dir():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    source_paths = set()
    for java_file in path.rglob("*.java"):
        relative_parts = java_file.relative_to(path).parts
        lower_parts = tuple(part.lower() for part in relative_parts)

        if any(
            part.startswith(".") or part.lower() in IGNORED_DIRS
            for part in relative_parts
        ):
            continue

        for i in range(len(relative_parts) - 2):
            if lower_parts[i : i + 3] != ("src", "main", "java"):
                continue

            if any(part.lower() in TEST_MODULE_DIRS for part in relative_parts[:i]):
                break

            if any(
                lower_parts[j : j + 3] == ("src", "test", "resources") for j in range(i)
            ):
                break

            source_paths.add(path.joinpath(*relative_parts[: i + 3]))
            break

    if not source_paths:
        raise FileNotFoundError(f"No eligible Java source directories found in {path}")

    packages = {}
    for source_path in sorted(source_paths):
        for java_file in source_path.rglob("*.java"):
            try:
                content = java_file.read_text(encoding="utf-8", errors="strict")
            except (UnicodeDecodeError, OSError) as exc:
                print(f"Skipping {java_file}: {exc}")
                continue

            package_path = ".".join(java_file.relative_to(source_path).parent.parts)
            if not package_path:
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


def discover_java_source_roots(repo_path: Path):
    """Discover production-oriented Java source roots across repository modules.

    Standard Maven/Gradle roots are preferred; legacy src roots are supported
    as a fallback. Known test-module directory names are excluded consistently.
    """
    repo_path = repo_path.resolve()
    source_roots = set()

    for java_file in repo_path.rglob("*.java"):
        try:
            relative = java_file.relative_to(repo_path)
        except ValueError:
            continue

        parts = relative.parts
        lower_parts = tuple(part.lower() for part in parts)

        if any(part.startswith(".") or part.lower() in IGNORED_DIRS for part in parts):
            continue

        found_standard_root = False
        for i in range(len(parts) - 2):
            if lower_parts[i : i + 3] != ("src", "main", "java"):
                continue

            # Do not accept src/main/java nested inside known test modules.
            if any(part.lower() in TEST_MODULE_DIRS for part in parts[:i]):
                break

            # Exclude roots nested under src/test/resources.
            if any(
                lower_parts[j : j + 3] == ("src", "test", "resources") for j in range(i)
            ):
                break

            source_roots.add(repo_path.joinpath(*parts[: i + 3]))
            found_standard_root = True
            break

        if found_standard_root:
            continue

        # Legacy layouts: src/org/example/Class.java
        if any(part.lower() in TEST_MODULE_DIRS for part in parts):
            continue

        for i, part in enumerate(lower_parts[:-1]):
            if part == "src":
                source_roots.add(repo_path.joinpath(*parts[: i + 1]))
                break

    return sorted(source_roots)


def analyze_discovered_structure(repo_path: Path, source_roots: list[Path]):
    """Aggregate metrics by declared Java package across discovered roots."""
    repo_path = repo_path.resolve()
    packages = {}
    processed_files = set()

    package_pattern = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)

    for source_root in source_roots:
        for java_file in source_root.rglob("*.java"):
            try:
                resolved_file = java_file.resolve()
                relative_to_repo = java_file.relative_to(repo_path)
            except (OSError, ValueError):
                continue

            if resolved_file in processed_files:
                continue

            repo_parts = relative_to_repo.parts

            if any(
                part.startswith(".") or part.lower() in IGNORED_DIRS
                for part in repo_parts
            ):
                continue

            # Apply the same test-module filter using the full repository path.
            if any(part.lower() in TEST_MODULE_DIRS for part in repo_parts):
                continue

            relative_to_root = java_file.relative_to(source_root)
            root_parts = tuple(part.lower() for part in relative_to_root.parts)

            # Prevent legacy src roots from recounting files under main/java.
            if len(root_parts) >= 2 and root_parts[:2] == ("main", "java"):
                continue

            try:
                content = java_file.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"Skipping {java_file}: {exc}")
                continue

            processed_files.add(resolved_file)
            match = package_pattern.search(content)
            package_path = match.group(1) if match else "(default package)"

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

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.is_dir():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    source_roots = discover_java_source_roots(repo_path)
    if not source_roots:
        raise FileNotFoundError(f"No Java source roots found in {repo_path}")

    packages = analyze_discovered_structure(repo_path, source_roots)

    output_dir = Path("data/structural")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{repo_path.name}_structure.csv"

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["package_path", "java_files", "lines_of_code"],
        )
        writer.writeheader()
        writer.writerows(packages)

    print("\nStructure analysis completed.")
    print(f"Source roots found: {len(source_roots)}")
    print(f"Packages found: {len(packages)}")
    print(f"Output saved to: {output_path}")
