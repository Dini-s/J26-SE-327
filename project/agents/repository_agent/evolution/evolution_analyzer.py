import argparse
import csv
import subprocess
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "data" / "evolution"


def run_git_command(repo_path, command):
    """Execute a Git command inside a repository."""
    result = subprocess.run(
        ["git", "-C", str(repo_path)] + command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    return result.stdout.strip()


def get_commit_count(repo_path):
    output = run_git_command(repo_path, ["rev-list", "--count", "HEAD"])
    return int(output)


def get_contributor_count(repo_path):
    output = run_git_command(repo_path, ["shortlog", "-sne", "--all"])
    return len(output.splitlines()) if output else 0


def get_repository_change_statistics(repo_path):
    """Calculate repository-wide historical change statistics."""
    output = run_git_command(repo_path, ["log", "--numstat", "--format="])

    files_changed = 0
    insertions = 0
    deletions = 0

    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue

        added, deleted, _ = parts

        # Git uses '-' for binary files.
        if added == "-" or deleted == "-":
            continue

        try:
            added = int(added)
            deleted = int(deleted)
        except ValueError:
            continue

        files_changed += 1
        insertions += added
        deletions += deleted

    return files_changed, insertions, deletions


def get_file_evolution_statistics(repo_path):
    """
    Calculate per-file historical changes.

    File paths are repository-relative paths. Renames are recorded using
    Git's default history path behavior; this initial implementation
    does not attempt to merge renamed paths into one identity.
    """
    output = run_git_command(
        repo_path,
        [
            "log",
            "--all",
            "--numstat",
            "--format=tformat:--EVOLUTION-COMMIT--",
            "--no-renames",
        ],
    )

    stats = defaultdict(
        lambda: {
            "change_records": 0,
            "commit_count": 0,
            "insertions": 0,
            "deletions": 0,
        }
    )

    seen_files_in_commit = set()

    for line in output.splitlines():
        if line == "--EVOLUTION-COMMIT--":
            seen_files_in_commit = set()
            continue

        parts = line.split("\t")
        if len(parts) != 3:
            continue

        added, deleted, file_path = parts

        # Skip binary-file line counts but retain no numeric churn for them.
        if added == "-" or deleted == "-":
            continue

        try:
            added = int(added)
            deleted = int(deleted)
        except ValueError:
            continue

        item = stats[file_path]
        item["change_records"] += 1
        item["insertions"] += added
        item["deletions"] += deleted

        if file_path not in seen_files_in_commit:
            item["commit_count"] += 1
            seen_files_in_commit.add(file_path)

    rows = []

    for file_path, values in sorted(stats.items()):
        rows.append(
            {
                "file_path": file_path,
                "change_records": values["change_records"],
                "commit_count": values["commit_count"],
                "total_insertions": values["insertions"],
                "total_deletions": values["deletions"],
                "total_churn": (values["insertions"] + values["deletions"]),
            }
        )

    return rows


def save_repository_results(repo_name, results):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{repo_name}_evolution.csv"

    fields = [
        "repository",
        "commit_count",
        "contributor_count",
        "files_changed",
        "total_insertions",
        "total_deletions",
        "total_churn",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"repository": repo_name, **results})

    return output_file


def save_file_results(repo_name, rows):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{repo_name}_file_evolution.csv"

    fields = [
        "repository",
        "file_path",
        "change_records",
        "commit_count",
        "total_insertions",
        "total_deletions",
        "total_churn",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for row in rows:
            writer.writerow({"repository": repo_name, **row})

    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Analyze repository-level and file-level Git evolution"
    )
    parser.add_argument("repo_path", help="Path to the Git repository")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()

    if not repo_path.is_dir():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    if not (repo_path / ".git").exists():
        raise ValueError(f"Not a Git repository: {repo_path}")

    repo_name = repo_path.name

    print(f"Repository: {repo_name}")
    print("Analyzing Git history...")

    commit_count = get_commit_count(repo_path)
    contributor_count = get_contributor_count(repo_path)
    files_changed, insertions, deletions = get_repository_change_statistics(repo_path)

    repository_results = {
        "commit_count": commit_count,
        "contributor_count": contributor_count,
        "files_changed": files_changed,
        "total_insertions": insertions,
        "total_deletions": deletions,
        "total_churn": insertions + deletions,
    }

    file_rows = get_file_evolution_statistics(repo_path)

    repository_file = save_repository_results(repo_name, repository_results)
    file_output = save_file_results(repo_name, file_rows)

    print(f"Commits: {commit_count}")
    print(f"Contributors: {contributor_count}")
    print(f"Repository change records: {files_changed}")
    print(f"Repository churn: {insertions + deletions}")
    print(f"Files with numeric change history: {len(file_rows)}")
    print(f"Repository summary saved to: {repository_file}")
    print(f"File evolution saved to: {file_output}")
    print("Evolution analysis completed.")


if __name__ == "__main__":
    main()
