import argparse
import csv
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

COMMIT_MARKER = "@@PACKAGE_EVOLUTION_COMMIT@@"
PACKAGE_PATTERN = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)


def run_git(repo_path: Path, *args: str, check: bool = True) -> str:
    """Run Git and return standard output."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Git command failed")
    return result.stdout


def parse_datetime(value: str) -> datetime:
    """Parse an ISO datetime and normalize it to UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_production_java(file_path: str) -> bool:
    """Keep production Java files and exclude test fixtures."""
    normalized = file_path.replace("\\", "/")
    parts = [part.lower() for part in normalized.split("/")]

    if not normalized.lower().endswith(".java"):
        return False

    # Exclude test and generated directories.
    excluded_dirs = {
        "test",
        "tests",
        "testfixtures",
        "test-fixtures",
        "integration-test",
        "integration-tests",
        "generated",
        "target",
        "build",
        "out",
        ".mvn",
    }

    if any(part in excluded_dirs for part in parts):
        return False

    filename = parts[-1]

    if (
        filename.startswith("test")
        or filename.endswith("test.java")
        or filename.endswith("tests.java")
        or filename.endswith("testcase.java")
    ):
        return False

    return True


def package_from_historical_blob(
    repo_path: Path,
    commit_id: str,
    file_path: str,
    cache: dict[tuple[str, str], str],
) -> str:
    """Read the declaration at a commit; use first parent for deleted files."""
    key = (commit_id, file_path)
    if key in cache:
        return cache[key]

    content = run_git(repo_path, "show", f"{commit_id}:{file_path}", check=False)
    if not content:
        parent_line = (
            run_git(repo_path, "rev-list", "--parents", "-n", "1", commit_id)
            .strip()
            .split()
        )
        if len(parent_line) >= 2:
            content = run_git(
                repo_path, "show", f"{parent_line[1]}:{file_path}", check=False
            )

    match = PACKAGE_PATTERN.search(content)
    package_name = match.group(1) if match else "(package-unresolved)"
    cache[key] = package_name
    return package_name


def current_production_packages(repo_path: Path) -> set[str]:
    """Return package declarations for tracked production Java files at HEAD."""
    tracked = run_git(repo_path, "ls-files", "-z", "--", "*.java")
    package_names = set()
    for file_path in tracked.split("\0"):
        if not file_path or not is_production_java(file_path):
            continue
        content = run_git(repo_path, "show", f"HEAD:{file_path}", check=False)
        match = PACKAGE_PATTERN.search(content)
        if match:
            package_names.add(match.group(1))
    return package_names


def analyze_package_evolution(repo_path: Path, since: str, until: str) -> list[dict]:
    """Aggregate changes by package declaration found in each historical blob."""
    repo_path = repo_path.resolve()
    if not (repo_path / ".git").exists() and not (repo_path / ".git").is_file():
        raise ValueError(f"Not a Git repository: {repo_path}")

    # Include current production packages even when no qualifying changes were found.
    current_packages = current_production_packages(repo_path)

    start_time = parse_datetime(since)
    end_time = parse_datetime(until)
    if start_time >= end_time:
        raise ValueError("--since must be earlier than --until")

    output = run_git(
        repo_path,
        "log",
        "--all",
        "--no-merges",
        f"--since={since}",
        f"--until={until}",
        f"--format={COMMIT_MARKER}%H%x09%ct%x09%an <%ae>",
        "--numstat",
        "--no-renames",
    )

    stats = defaultdict(
        lambda: {
            "commit_ids": set(),
            "contributors": set(),
            "files": set(),
            "insertions": 0,
            "deletions": 0,
        }
    )
    package_cache: dict[tuple[str, str], str] = {}
    current_commit = None
    current_author = None
    commits_processed = 0
    java_file_events = 0

    for line in output.splitlines():
        if line.startswith(COMMIT_MARKER):
            fields = line[len(COMMIT_MARKER) :].split("\t", 2)
            if len(fields) != 3:
                current_commit = current_author = None
                continue
            commit_id, timestamp_text, current_author = fields
            try:
                commit_time = datetime.fromtimestamp(int(timestamp_text), timezone.utc)
            except (ValueError, OverflowError):
                current_commit = current_author = None
                continue
            if not start_time <= commit_time < end_time:
                current_commit = current_author = None
                continue
            current_commit = commit_id
            commits_processed += 1
            continue

        if current_commit is None:
            continue
        fields = line.split("\t", 2)
        if len(fields) != 3:
            continue
        added_text, deleted_text, file_path = fields
        file_path = file_path.replace("\\", "/")
        if not is_production_java(file_path):
            continue
        try:
            added, deleted = int(added_text), int(deleted_text)
        except ValueError:
            continue

        package_name = package_from_historical_blob(
            repo_path, current_commit, file_path, package_cache
        )
        item = stats[package_name]
        item["files"].add(file_path)
        item["insertions"] += added
        item["deletions"] += deleted
        item["commit_ids"].add(current_commit)
        item["contributors"].add(current_author)
        java_file_events += 1

    # defaultdict creates zero-valued metrics for current packages with no events.
    for package_name in current_packages:
        stats[package_name]

    rows = []
    for package_name, item in sorted(stats.items()):
        rows.append(
            {
                "repository": repo_path.name,
                "package_path": package_name,
                "activity_status": (
                    "changes_detected_in_period"
                    if item["commit_ids"]
                    else "no_qualifying_changes_detected_in_period"
                    if package_name in current_packages
                    else "historical_package_changes_not_current_at_HEAD"
                ),
                "period_start": since,
                "period_end": until,
                "commit_count": len(item["commit_ids"]),
                "contributor_count": len(item["contributors"]),
                "files_changed": len(item["files"]),
                "total_insertions": item["insertions"],
                "total_deletions": item["deletions"],
                "total_churn": item["insertions"] + item["deletions"],
            }
        )

    unresolved = sum(row["package_path"] == "(package-unresolved)" for row in rows)
    print(f"Commits processed in period (excluding merges): {commits_processed}")
    print(f"Production Java change events resolved: {java_file_events}")
    print(f"Packages in output (changed + current): {len(rows)}")
    print(f"Current production packages at HEAD: {len(current_packages)}")
    print(
        f"Current packages with no qualifying changes: {sum(1 for name in current_packages if not stats[name]['commit_ids'])}"
    )
    print(f"Unresolved package bucket rows: {unresolved}")
    print(
        "Package names are read from historical Java declarations where available; deleted files use their first parent."
    )
    print("Experimental analyzer may be slower than path-based inference.")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Experimental historical-declaration package evolution analyzer"
    )
    parser.add_argument("repo_path", help="Path to a Git repository")
    parser.add_argument("--since", required=True, help="Start ISO datetime")
    parser.add_argument("--until", required=True, help="End ISO datetime")
    parser.add_argument(
        "--output",
        default="data/evolution/package_evolution_historical_test.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()
    rows = analyze_package_evolution(Path(args.repo_path), args.since, args.until)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "repository",
        "package_path",
        "activity_status",
        "period_start",
        "period_end",
        "commit_count",
        "contributor_count",
        "files_changed",
        "total_insertions",
        "total_deletions",
        "total_churn",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved: {output_path.resolve()}")


if __name__ == "__main__":
    main()
