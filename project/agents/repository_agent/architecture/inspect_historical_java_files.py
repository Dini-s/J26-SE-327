import re
import subprocess
from pathlib import Path

# Project root: J26-SE-327/project
PROJECT_ROOT = Path(__file__).resolve().parents[3]

REPO = PROJECT_ROOT / "data" / "raw" / "R01_spring_petclinic"

SNAPSHOTS = {
    "2015-12-22": "a768e877efa9d22c9b6a3173a9a92a3b3af8aa3d",
    "2021-12-23": "778161f0183d44df8f58b6eaee64fc085b64b69c",
}

PACKAGE_RE = re.compile(
    r"^\s*package\s+([\w.]+)\s*;",
    re.MULTILINE,
)

EXCLUDED_DIRS = {
    "test",
    "tests",
    "testing",
    "testfixtures",
    "test-fixtures",
    "generated",
    "target",
    "build",
    "out",
}


def git(*args):
    """Run Git commands against the Spring PetClinic repository."""
    result = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Git command failed:\n{result.stderr.strip()}")

    return result.stdout


def is_production_java(file_path):
    """Apply the current path-based production Java filter."""
    parts = file_path.replace("\\", "/").split("/")
    lower_parts = [part.lower() for part in parts]
    filename = lower_parts[-1]

    if not filename.endswith(".java"):
        return False

    if any(part in EXCLUDED_DIRS for part in lower_parts):
        return False

    if (
        filename.startswith("test")
        or filename.endswith("test.java")
        or filename.endswith("tests.java")
        or filename.endswith("testcase.java")
    ):
        return False

    return True


def inspect_snapshot(date, commit):
    """Inspect Java-file filtering and package declarations."""
    print(f"\n{'=' * 60}")
    print(f"Snapshot: {date}")
    print(f"Commit: {commit}")

    # Verify that the commit exists.
    git("cat-file", "-e", f"{commit}^{{commit}}")

    # List every tracked file in this historical commit.
    paths = git(
        "ls-tree",
        "-r",
        "--name-only",
        commit,
    ).splitlines()

    java_paths = [path for path in paths if path.lower().endswith(".java")]

    filtered_paths = [path for path in java_paths if not is_production_java(path)]

    eligible_paths = [path for path in java_paths if is_production_java(path)]

    unparsed_paths = []
    package_counts = {}

    for path in eligible_paths:
        source = git("show", f"{commit}:{path}")

        package_match = PACKAGE_RE.search(source)

        if not package_match:
            unparsed_paths.append(path)
            continue

        package_name = package_match.group(1)
        package_counts[package_name] = package_counts.get(package_name, 0) + 1

    analyzed_files = len(eligible_paths) - len(unparsed_paths)

    print(f"Tracked files: {len(paths)}")
    print(f"Tracked Java files: {len(java_paths)}")
    print(f"Filtered Java files: {len(filtered_paths)}")
    print(f"Eligible Java files: {len(eligible_paths)}")
    print(f"Files without recognized package declarations: {len(unparsed_paths)}")
    print(f"Files with recognized package declarations: {analyzed_files}")
    print(f"Distinct declared packages: {len(package_counts)}")

    if filtered_paths:
        print("\nFiltered Java files:")
        for path in filtered_paths:
            print(f"  {path}")

    if unparsed_paths:
        print("\nJava files without recognized package declarations:")
        for path in unparsed_paths:
            print(f"  {path}")

    if package_counts:
        print("\nPackage file counts:")
        for package_name, count in sorted(package_counts.items()):
            print(f"  {package_name}: {count} Java file(s)")


def main():
    """Inspect the selected historical snapshots."""
    if not REPO.is_dir():
        raise FileNotFoundError(f"Repository directory not found: {REPO}")

    if not (REPO / ".git").exists() and not (REPO / ".git").is_file():
        raise ValueError(f"Not a Git repository: {REPO}")

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Repository: {REPO}")

    for date, commit in SNAPSHOTS.items():
        inspect_snapshot(date, commit)

    print("\nInspection completed.")


if __name__ == "__main__":
    main()
