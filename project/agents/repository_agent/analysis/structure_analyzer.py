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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze the Java package structure of a repository"
    )

    parser.add_argument("repo_path", help="Path to the Git repository")

    args = parser.parse_args()

    repo_path = Path(args.repo_path)

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
