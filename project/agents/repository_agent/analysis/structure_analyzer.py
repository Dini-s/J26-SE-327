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
    """Discover Java source roots in different project layouts."""

    source_roots = set()
    ignored_dirs = {
        ".git",
        "build",
        "target",
        "out",
        "bin",
        "node_modules",
        "__pycache__",
    }

    for java_file in repo_path.rglob("*.java"):
        relative = java_file.relative_to(repo_path)

        if any(part.startswith(".") or part in ignored_dirs for part in relative.parts):
            continue

        parts = relative.parts

        # Standard Maven/Gradle source layout:
        # module/src/main/java/org/example/Class.java
        for i in range(len(parts) - 2):
            if parts[i : i + 3] == ("src", "main", "java"):
                source_roots.add(repo_path.joinpath(*parts[: i + 3]))
                break
        else:
            # Legacy layout:
            # module/src/org/example/Class.java
            for i, part in enumerate(parts[:-1]):
                if part == "src":
                    source_root = repo_path.joinpath(*parts[: i + 1])
                    source_roots.add(source_root)
                    break

    return sorted(source_roots)


def analyze_discovered_structure(repo_path: Path, source_roots: list[Path]):
    """Analyze packages across automatically discovered Java source roots."""

    packages = {}

    ignored_dirs = {
        ".git",
        "build",
        "target",
        "out",
        "bin",
        "node_modules",
        "__pycache__",
    }

    for source_root in source_roots:
        for java_file in source_root.rglob("*.java"):
            relative = java_file.relative_to(source_root)

            if any(
                part.startswith(".") or part in ignored_dirs for part in relative.parts
            ):
                continue

            try:
                with java_file.open("r", encoding="utf-8", errors="replace") as f:
                    total_lines = sum(1 for _ in f)
            except OSError as exc:
                print(f"Skipping {java_file}: {exc}")
                continue

            package_path = ".".join(java_file.parent.relative_to(source_root).parts)

            if not package_path:
                package_path = "(default package)"

            # Keep packages from different modules distinguishable.
            module_name = source_root.parent.name
            package_key = (module_name, package_path)

            if package_key not in packages:
                packages[package_key] = {
                    "package_path": f"{module_name}:{package_path}",
                    "java_files": 0,
                    "lines_of_code": 0,
                }

            packages[package_key]["java_files"] += 1
            packages[package_key]["lines_of_code"] += total_lines

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
