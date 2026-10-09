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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze the Java package structure of a repository"
    )

    parser.add_argument("repo_path", help="Path to the Git repository")

    args = parser.parse_args()

    repo_path = Path(args.repo_path)

    if repo_path.name == "R03_jabref":
        packages = analyze_multimodule_structure(repo_path)
    else:
        packages = anlyze_structure(repo_path)

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
