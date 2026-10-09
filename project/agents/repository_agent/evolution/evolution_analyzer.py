import argparse
import csv
import subprocess
from pathlib import Path


def run_git_command(repo_path, command):
    """
    Execue a Git command inside the repository
    """
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
    """
    Total number of commits in the repository
    """
    output = run_git_command(repo_path, ["rev-list", "--count", "HEAD"])

    return int(output)


def get_contributor_count(repo_path):
    """
    Number of unique contributors
    """
    output = run_git_command(repo_path, ["shortlog", "-sne", "--all"])

    if not output:
        return 0

    return len(output.splitlines())


def get_file_change_statistics(repo_path):
    """
    Calculate total files changed, insertions and deletions from Git hisory
    """

    output = run_git_command(repo_path, ["log", "--numstat", "--format="])

    total_files_changed = 0
    total_insertions = 0
    total_deletions = 0

    for line in output.splitlines():
        if not line.strip():
            continue

        parts = line.split("\t")

        if len(parts) != 3:
            continue

        additions, deletions, _ = parts

        # Binary files are represented by "-"
        if additions == "-" or deletions == "-":
            continue

        try:
            additions = int(additions)
            deletions = int(deletions)

        except ValueError:
            continue

        total_files_changed += 1
        total_insertions += additions
        total_deletions += deletions

    return (total_files_changed, total_insertions, total_deletions)


def get_repository_evolution(repo_path):

    commit_count = get_commit_count(repo_path)
    contributor_count = get_contributor_count(repo_path)

    (files_changed, insertions, deletions) = get_file_change_statistics(repo_path)

    total_churn = insertions + deletions

    return {
        "commit_count": commit_count,
        "contributor_count": contributor_count,
        "files_changed": files_changed,
        "total_insertions": insertions,
        "total_deletions": deletions,
        "total_churn": total_churn,
    }


def save_results(repo_name, results):

    output_dir = Path("data/evolution")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{repo_name}_evolution.csv"

    fieldnames = [
        "repository",
        "commit_count",
        "contributor_count",
        "files_changed",
        "total_insertions",
        "total_deletions",
        "total_churn",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()

        writer.writerow({"repository": repo_name, **results})

    return output_file


def main():

    parser = argparse.ArgumentParser(description="Analyze Git repository evolution")

    parser.add_argument("repo_path", help="Path to the Git repository")

    args = parser.parse_args()

    repo_path = Path(args.repo_path)

    if not repo_path.exists():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    git_folder = repo_path / ".git"

    if not git_folder.exists():
        raise ValueError(f"Not a Git repository: {repo_path}")

    repo_name = repo_path.name

    print(f"Repository:{repo_name}")
    print("Analyzing Git history ...")

    results = get_repository_evolution(repo_path)

    print(f"Commits: {results['commit_count']}")
    print(f"Contributors :{results['contributor_count']}")
    print(f"Files changed: {results['files_changed']}")
    print(f"Insertions: {results['total_insertions']}")
    print(f"Deletions: {results['total_deletions']}")
    print(f"Total churn: {results['total_churn']}")

    output_file = save_results(repo_name, results)

    print()
    print("Evolution analysis completed")
    print(f"Output saved to: {output_file}")


if __name__ == "__main__":
    main()
