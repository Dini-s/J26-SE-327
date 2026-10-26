import argparse
import csv
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

COMMIT_MARKER = "@@PACKAGE_EVOLUTION_COMMIT@@"


def run_git(repo_path: Path, *args: str) -> str:
    """Run Git and return standard output."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Git command failed")

    return result.stdout


def parse_datetime(value: str) -> datetime:
    """Parse an ISO datetime and normalize it to UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def is_production_java(file_path: str) -> bool:
    """Filter likely production Java files."""
    normalized = file_path.replace("\\", "/")
    parts = [part.lower() for part in normalized.split("/")]

    if not normalized.lower().endswith(".java"):
        return False

    excluded_dirs = {
        "test",
        "tests",
        "testing",
        "testfixtures",
        "test-fixtures",
        "generated",
        "target",
        "build",
        "out",
        ".mvn",
    }

    if any(part in excluded_dirs for part in parts):
        return False

    # Exclude common Java test class names.
    filename = parts[-1]

    if (
        filename.startswith("test")
        or filename.endswith("test.java")
        or filename.endswith("tests.java")
        or filename.endswith("testcase.java")
    ):
        return False

    return True


def get_package_from_path(file_path: str) -> str:
    """
    Infer package from a conventional Java source path.

    This is an approximation, not a substitute for reading
    the historical Java package declaration.
    """
    parts = file_path.replace("\\", "/").split("/")
    lower_parts = [part.lower() for part in parts]

    # Standard Maven/Gradle layout:
    # src/main/java/org/example/Class.java
    if "java" in lower_parts:
        index = len(lower_parts) - 1 - lower_parts[::-1].index("java")
        package_parts = parts[index + 1 : -1]

        if package_parts:
            package_name = ".".join(package_parts)

            # Do not mistake temporary directory names for packages.
            if package_name.lower() in {"pending", "temp", "temporary"}:
                return "(path-unresolved)"

            return package_name

        return "(default)"

    # Older layouts such as src/org/example/Class.java.
    # Only infer when the path contains a plausible package hierarchy.
    for root in ("source", "src"):
        if root in lower_parts:
            index = len(lower_parts) - 1 - lower_parts[::-1].index(root)
            remainder = parts[index + 1 : -1]

            remainder = [
                part for part in remainder if part.lower() not in {"main", "java"}
            ]

            if not remainder:
                return "(default)"

            # A single folder like src/pending/Class.java is ambiguous.
            if len(remainder) == 1 and remainder[0].lower() in {
                "pending",
                "temp",
                "temporary",
            }:
                return "(path-unresolved)"

            return ".".join(remainder)

    return "(path-unresolved)"


def analyze_package_evolution(
    repo_path: Path,
    since: str,
    until: str,
) -> list[dict]:
    """Aggregate package evolution using one batched Git history command."""
    repo_path = repo_path.resolve()

    if not (repo_path / ".git").exists() and not (repo_path / ".git").is_file():
        raise ValueError(f"Not a Git repository: {repo_path}")

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

    current_commit = None
    current_author = None
    commits_processed = 0

    for line in output.splitlines():
        if line.startswith(COMMIT_MARKER):
            fields = line[len(COMMIT_MARKER) :].split("\t", 2)

            if len(fields) != 3:
                current_commit = None
                current_author = None
                continue

            commit_id, timestamp_text, current_author = fields

            try:
                commit_time = datetime.fromtimestamp(int(timestamp_text), timezone.utc)
            except (ValueError, OverflowError):
                current_commit = None
                current_author = None
                continue

            if not start_time <= commit_time < end_time:
                current_commit = None
                current_author = None
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
            added = int(added_text)
            deleted = int(deleted_text)
        except ValueError:
            # Ignore files whose line counts cannot be measured.
            continue

        package_name = get_package_from_path(file_path)
        item = stats[package_name]

        item["files"].add(file_path)
        item["insertions"] += added
        item["deletions"] += deleted
        item["commit_ids"].add(current_commit)
        item["contributors"].add(current_author)

    rows = []

    for package_name, item in sorted(stats.items()):
        rows.append(
            {
                "repository": repo_path.name,
                "package_path": package_name,
                "period_start": since,
                "period_end": until,
                "commit_count": len(item["commit_ids"]),
                "contributor_count": len(item["contributors"]),
                "files_changed": len(item["files"]),
                "total_insertions": item["insertions"],
                "total_deletions": item["deletions"],
                "total_churn": (item["insertions"] + item["deletions"]),
            }
        )

    print(f"Commits processed in period (excluding merges): {commits_processed}")
    print(f"Packages/buckets with production Java changes: {len(rows)}")
    print(
        "Warning: package names are inferred from paths. "
        "Historical package declarations are not verified."
    )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fast package-level production Java evolution analyzer"
    )

    parser.add_argument("repo_path", help="Path to a Git repository")
    parser.add_argument("--since", required=True, help="Start ISO datetime")
    parser.add_argument("--until", required=True, help="End ISO datetime")
    parser.add_argument(
        "--output",
        default="data/evolution/package_evolution.csv",
        help="Output CSV path",
    )

    args = parser.parse_args()

    rows = analyze_package_evolution(
        Path(args.repo_path),
        args.since,
        args.until,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "repository",
        "package_path",
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
