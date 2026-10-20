import argparse
import csv
import re
import subprocess
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_REPOSITORIES_DIR = PROJECT_ROOT / "data" / "raw"
SNAPSHOT_COUNT = 4

PACKAGE_RE = re.compile(
    r"^\s*package\s+([\w.]+)\s*;",
    re.MULTILINE,
)

IMPORT_RE = re.compile(
    r"^\s*import\s+(?:static\s+)?([\w.*]+)\s*;",
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

ARCHITECTURE_COLUMNS = [
    "repository",
    "snapshot_date",
    "commit_hash",
    "package_path",
    "java_files",
    "nonempty_lines",
    "fan_in",
    "fan_out",
    "total_coupling",
    "instability",
]

DEPENDENCY_COLUMNS = [
    "repository",
    "snapshot_date",
    "commit_hash",
    "source_package",
    "target_package",
]


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Git command failed.")

    return result.stdout


def is_git_repository(path):
    return path.is_dir() and ((path / ".git").exists() or (path / ".git").is_file())


def discover_repositories():
    if not RAW_REPOSITORIES_DIR.exists():
        raise FileNotFoundError(
            f"Raw repositories directory not found: {RAW_REPOSITORIES_DIR}"
        )

    return [
        path.resolve()
        for path in sorted(RAW_REPOSITORIES_DIR.iterdir())
        if is_git_repository(path)
    ]


def snapshot_has_packages(repo, commit):
    """Check whether a commit contains production Java package declarations."""

    pattern = (
        r"^[[:space:]]*package[[:space:]]+"
        r"[[:alnum:]_.]+[[:space:]]*;"
    )

    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "grep",
            "-I",
            "-l",
            "-E",
            pattern,
            commit,
            "--",
            "*.java",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or "Git grep failed.")

    for line in result.stdout.splitlines():
        path = line.split(":", 1)[-1]

        if is_production_java(path):
            return True

    return False


def select_snapshots(repo, snapshot_count=SNAPSHOT_COUNT):
    """
    Select up to four evenly distributed historical commits
    that contain recognizable production Java packages.
    """

    output = git(
        repo,
        "log",
        "--first-parent",
        "--reverse",
        "--format=%H%x09%cs",
        "HEAD",
    )

    history = []

    for line in output.splitlines():
        parts = line.split("\t", maxsplit=1)

        if len(parts) == 2:
            history.append(
                {
                    "commit": parts[0],
                    "date": parts[1],
                }
            )

    if not history:
        print(f"WARNING: No commits found for {repo.name}; skipping.")
        return []

    # Locate the first commit containing recognizable production
    # Java packages without checking every historical commit.
    first_valid = None
    probe = 0

    while probe < len(history):
        if snapshot_has_packages(repo, history[probe]["commit"]):
            first_valid = probe
            break

        probe = 1 if probe == 0 else probe * 2

    if first_valid is None:
        print(f"WARNING: No production Java packages found in {repo.name}; skipping.")
        return []

    # Refine the first eligible commit using binary search.
    # This assumes package-bearing Java code remains present
    # after it first appears in the repository history.
    low = max(0, probe // 2)
    high = probe

    while low < high:
        middle = (low + high) // 2

        if snapshot_has_packages(repo, history[middle]["commit"]):
            high = middle
        else:
            low = middle + 1

    first_valid = low
    eligible_history = history[first_valid:]

    count = min(snapshot_count, len(eligible_history))

    if count == 1:
        indices = [len(eligible_history) - 1]
    else:
        indices = [
            round(i * (len(eligible_history) - 1) / (count - 1)) for i in range(count)
        ]

    snapshots = []
    seen_dates = set()

    for index in indices:
        snapshot = eligible_history[index]

        # Confirm eligibility in case the repository's structure changed.
        if not snapshot_has_packages(repo, snapshot["commit"]):
            print(
                f"WARNING: Skipping {snapshot['date']}: "
                "no recognizable production Java packages."
            )
            continue

        if snapshot["date"] in seen_dates:
            continue

        snapshots.append(snapshot)
        seen_dates.add(snapshot["date"])

    print(
        f"{repo.name}: {len(history)} total commits; "
        f"{len(eligible_history)} commits from the first "
        f"Java-bearing commit onward; "
        f"selected {len(snapshots)} snapshots."
    )

    return snapshots


def is_production_java(path):
    parts = path.replace("\\", "/").split("/")
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


def read_snapshot(repo, snapshot):
    commit = snapshot["commit"]

    paths = git(
        repo,
        "ls-tree",
        "-r",
        "--name-only",
        commit,
    ).splitlines()

    package_files = defaultdict(list)
    package_imports = defaultdict(set)
    package_loc = defaultdict(int)
    skipped = 0

    for path in paths:
        if not is_production_java(path):
            continue

        try:
            source = git(repo, "show", f"{commit}:{path}")
        except RuntimeError:
            skipped += 1
            continue

        package_match = PACKAGE_RE.search(source)

        if not package_match:
            skipped += 1
            continue

        package = package_match.group(1)
        package_files[package].append(path)

        # Count non-empty source lines.
        # This is a reproducible proxy, not a full Java LOC parser.
        package_loc[package] += sum(1 for line in source.splitlines() if line.strip())

        for imported in IMPORT_RE.findall(source):
            package_imports[package].add(imported)

    packages = set(package_files)
    edges = set()

    for source_package, imports in package_imports.items():
        for imported in imports:
            # Resolve imports to the longest known internal package.
            candidates = [
                package
                for package in packages
                if (imported == package or imported.startswith(package + "."))
            ]

            if not candidates:
                continue

            target_package = max(candidates, key=len)

            if source_package != target_package:
                edges.add((source_package, target_package))

    fan_in = defaultdict(int)
    fan_out = defaultdict(int)

    for source, target in edges:
        fan_out[source] += 1
        fan_in[target] += 1

    metrics = []

    for package in sorted(packages):
        incoming = fan_in[package]
        outgoing = fan_out[package]
        coupling = incoming + outgoing

        metrics.append(
            {
                "repository": repo.name,
                "snapshot_date": snapshot["date"],
                "commit_hash": commit,
                "package_path": package,
                "java_files": len(package_files[package]),
                "nonempty_lines": package_loc[package],
                "fan_in": incoming,
                "fan_out": outgoing,
                "total_coupling": coupling,
                "instability": (outgoing / coupling if coupling else 0.0),
            }
        )

    edge_rows = [
        {
            "repository": repo.name,
            "snapshot_date": snapshot["date"],
            "commit_hash": commit,
            "source_package": source,
            "target_package": target,
        }
        for source, target in sorted(edges)
    ]

    print(
        f"  {snapshot['date']} ({commit[:10]}): "
        f"packages={len(packages)}, "
        f"Java files={sum(len(v) for v in package_files.values())}, "
        f"internal edges={len(edges)}, "
        f"unparsed Java files={skipped}"
    )

    return metrics, edge_rows


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
        )
        writer.writeheader()
        writer.writerows(rows)


def process_repository(repo):
    if not is_git_repository(repo):
        print(f"WARNING: Not a Git repository: {repo}; skipping.")
        return

    try:
        snapshots = select_snapshots(repo)
    except RuntimeError as error:
        print(f"WARNING: Could not read history for {repo.name}: {error}")
        return

    if not snapshots:
        return

    output_dir = PROJECT_ROOT / "data" / "historical" / repo.name

    all_metrics = []
    all_edges = []

    for snapshot in snapshots:
        try:
            metrics, edges = read_snapshot(repo, snapshot)
        except RuntimeError as error:
            print(
                f"WARNING: Failed snapshot {snapshot['date']} for {repo.name}: {error}"
            )
            continue

        all_metrics.extend(metrics)
        all_edges.extend(edges)

        date = snapshot["date"]

        write_csv(
            output_dir / f"{date}_architecture.csv",
            metrics,
            ARCHITECTURE_COLUMNS,
        )

        write_csv(
            output_dir / f"{date}_dependencies.csv",
            edges,
            DEPENDENCY_COLUMNS,
        )

    write_csv(
        output_dir / "all_snapshots_architecture.csv",
        all_metrics,
        ARCHITECTURE_COLUMNS,
    )

    print(f"  Output directory: {output_dir}")
    print(f"  Package-snapshot records: {len(all_metrics)}")
    print(f"  Package dependency edges: {len(all_edges)}")


def main():
    parser = argparse.ArgumentParser(
        description=("Extract historical architecture snapshots from Git repositories.")
    )

    parser.add_argument(
        "--repo",
        default=None,
        help=(
            "Optional path to one Git repository. "
            "Omit to process all repositories in data/raw."
        ),
    )

    args = parser.parse_args()

    if args.repo:
        repo = Path(args.repo)

        if not repo.is_absolute():
            repo = PROJECT_ROOT / repo

        repositories = [repo.resolve()]
    else:
        repositories = discover_repositories()

    if not repositories:
        print(f"No Git repositories found in {RAW_REPOSITORIES_DIR}")
        return

    print(f"Repositories to process: {len(repositories)}")

    for repo in repositories:
        print(f"\nProcessing repository: {repo.name}")

        try:
            process_repository(repo)
        except (OSError, ValueError, RuntimeError) as error:
            print(f"ERROR processing {repo.name}: {error}; continuing.")

    print("\nHistorical snapshot extraction finished.")


if __name__ == "__main__":
    main()
