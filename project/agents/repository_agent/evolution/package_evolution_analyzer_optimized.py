import argparse
import csv
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

COMMIT_MARKER = "@@PACKAGE_EVOLUTION_COMMIT@@"
PACKAGE_PATTERN = re.compile(rb"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)


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

    in_main_source = any(
        parts[i : i + 2] == ["src", "main"] for i in range(len(parts) - 1)
    )

    if not in_main_source and (
        filename.lower().startswith("test")
        or filename.lower().endswith("test.java")
        or filename.lower().endswith("tests.java")
        or filename.lower().endswith("testcase.java")
    ):
        return False

    return True


def git_cat_file_batch(repo_path: Path, specs: list[str]) -> dict[str, bytes | None]:
    """
    Retrieve many Git objects in one process using `git cat-file --batch`.
    Returns spec -> raw blob bytes, or None if the object cannot be resolved.
    """
    if not specs:
        return {}

    # Keep requests unique while preserving order.
    unique_specs = list(dict.fromkeys(specs))
    request = ("\n".join(unique_specs) + "\n").encode("utf-8", errors="surrogateescape")
    result = subprocess.run(
        ["git", "-C", str(repo_path), "cat-file", "--batch"],
        input=request,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.decode("utf-8", errors="replace").strip()
            or "git cat-file --batch failed"
        )

    data = result.stdout
    offset = 0
    objects: dict[str, bytes | None] = {}

    for requested_spec in unique_specs:
        newline = data.find(b"\n", offset)
        if newline < 0:
            raise RuntimeError("Unexpected truncated output from git cat-file --batch")

        header = data[offset:newline].decode("utf-8", errors="replace")
        offset = newline + 1
        header_parts = header.split()

        if len(header_parts) >= 2 and header_parts[1] == "missing":
            objects[requested_spec] = None
            continue

        if len(header_parts) != 3:
            objects[requested_spec] = None
            continue

        object_type = header_parts[1]
        try:
            object_size = int(header_parts[2])
        except ValueError:
            objects[requested_spec] = None
            continue

        blob = data[offset : offset + object_size]
        offset += object_size

        # cat-file emits one separator newline after each object body.
        if offset < len(data) and data[offset : offset + 1] == b"\n":
            offset += 1

        objects[requested_spec] = blob if object_type == "blob" else None

    return objects


def package_name_from_blob(content: bytes | None) -> str | None:
    if content is None:
        return None
    match = PACKAGE_PATTERN.search(content)
    return (
        match.group(1).decode("utf-8", errors="replace")
        if match
        else "(package-unresolved)"
    )


def current_production_packages(repo_path: Path) -> set[str]:
    """Return package declarations for tracked production Java files at HEAD."""
    tracked = run_git(repo_path, "ls-files", "-z", "--", "*.java")
    files = [item for item in tracked.split("\0") if item and is_production_java(item)]
    specs = [f"HEAD:{file_path}" for file_path in files]
    blobs = git_cat_file_batch(repo_path, specs)

    package_names = set()
    for file_path, spec in zip(files, specs):
        package_name = package_name_from_blob(blobs.get(spec))
        if package_name and package_name != "(package-unresolved)":
            package_names.add(package_name)
    return package_names


def analyze_package_evolution(repo_path: Path, since: str, until: str) -> list[dict]:
    """Aggregate package evolution, retrieving historical blobs in batches."""
    repo_path = repo_path.resolve()
    if not (repo_path / ".git").exists() and not (repo_path / ".git").is_file():
        raise ValueError(f"Not a Git repository: {repo_path}")

    start_time = parse_datetime(since)
    end_time = parse_datetime(until)
    if start_time >= end_time:
        raise ValueError("--since must be earlier than --until")

    current_packages = current_production_packages(repo_path)

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

    # Store candidate events first. We then fetch all historical blobs in batches
    # instead of launching one `git show` subprocess per file event.
    events = []
    current_commit = None
    current_author = None
    commits_processed = 0

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
            # Binary or otherwise non-numeric numstat records are not Java text events.
            continue

        events.append(
            {
                "commit_id": current_commit,
                "author": current_author,
                "file_path": file_path,
                "insertions": added,
                "deletions": deleted,
                "primary_spec": f"{current_commit}:{file_path}",
                "fallback_spec": None,
            }
        )

    primary_specs = list(dict.fromkeys(event["primary_spec"] for event in events))
    primary_blobs = git_cat_file_batch(repo_path, primary_specs)

    # Deleted paths may not exist at the commit itself; use the first parent,
    # matching the original analyzer's fallback behavior.
    fallback_specs = []
    for event in events:
        if primary_blobs.get(event["primary_spec"]) is None:
            event["fallback_spec"] = f"{event['commit_id']}^:{event['file_path']}"
            fallback_specs.append(event["fallback_spec"])

    fallback_blobs = git_cat_file_batch(repo_path, fallback_specs)
    package_cache: dict[str, str] = {}
    unresolved_events = 0

    for event in events:
        spec = event["primary_spec"]
        content = primary_blobs.get(spec)
        if content is None and event["fallback_spec"]:
            content = fallback_blobs.get(event["fallback_spec"])

        package_name = package_cache.get(spec)
        if package_name is None:
            resolved_name = package_name_from_blob(content)
            package_name = resolved_name or "(package-unresolved)"
            package_cache[spec] = package_name

        if package_name == "(package-unresolved)":
            unresolved_events += 1

        item = stats[package_name]
        item["files"].add(event["file_path"])
        item["insertions"] += event["insertions"]
        item["deletions"] += event["deletions"]
        item["commit_ids"].add(event["commit_id"])
        item["contributors"].add(event["author"])

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

    print(f"Commits processed in period (excluding merges): {commits_processed}")
    print(f"Production Java change events selected: {len(events)}")
    print(f"Unique primary Git objects requested: {len(primary_specs)}")
    print(f"Fallback parent objects requested: {len(set(fallback_specs))}")
    print(f"Events with unresolved package declarations: {unresolved_events}")
    print(f"Packages in output (changed + current): {len(rows)}")
    print(f"Current production packages at HEAD: {len(current_packages)}")
    print(
        "Current packages with no qualifying changes: "
        f"{sum(1 for name in current_packages if not stats[name]['commit_ids'])}"
    )
    print(
        "Package names are read from historical Java declarations where available; "
        "deleted files use their first parent."
    )
    print("Optimized analyzer retrieves Git objects in batches.")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Optimized historical-declaration package evolution analyzer"
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
