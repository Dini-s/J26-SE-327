import argparse
import csv
import re
import subprocess
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

SNAPSHOTS = [
    {
        "date": "2015-12-22",
        "commit": "a768e877efa9d22c9b6a3173a9a92a3b3af8aa3d",
    },
    {
        "date": "2018-12-17",
        "commit": "ab567242851166983e5f0140ab7593fd04c7d365",
    },
    {
        "date": "2021-12-23",
        "commit": "778161f0183d44df8f58b6eaee64fc085b64b69c",
    },
    {
        "date": "2024-12-15",
        "commit": "6148ddd9671ccab86a3f0ae2dfa77d833b713ee8",
    },
]

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
        raise RuntimeError(result.stderr.strip())
    return result.stdout


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

    paths = git(repo, "ls-tree", "-r", "--name-only", commit).splitlines()

    package_files = defaultdict(list)
    package_imports = defaultdict(set)
    package_loc = defaultdict(int)
    skipped = 0

    for path in paths:
        if not is_production_java(path):
            continue

        source = git(repo, "show", f"{commit}:{path}")

        package_match = PACKAGE_RE.search(source)
        if not package_match:
            skipped += 1
            continue

        package = package_match.group(1)
        package_files[package].append(path)

        # A reproducible proxy: count non-empty source lines.
        # This is not a full Java LOC parser.
        package_loc[package] += sum(1 for line in source.splitlines() if line.strip())

        for imported in IMPORT_RE.findall(source):
            imported = imported.removeprefix("static ")

            # Resolve the import to a known internal package below.
            package_imports[package].add(imported)

    packages = set(package_files)
    edges = set()

    for source_package, imports in package_imports.items():
        for imported in imports:
            # Resolve to the longest known package prefix.
            candidates = [
                package
                for package in packages
                if imported == package or imported.startswith(package + ".")
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
        f"{snapshot['date']}: "
        f"packages={len(packages)}, "
        f"Java files={sum(len(v) for v in package_files.values())}, "
        f"internal edges={len(edges)}, "
        f"unparsed Java files={skipped}"
    )

    return metrics, edge_rows


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        default="data/raw/R01_spring_petclinic",
        help="Path to the Git repository",
    )
    args = parser.parse_args()

    repo = Path(args.repo)
    if not repo.is_absolute():
        repo = PROJECT_ROOT / repo
    repo = repo.resolve()

    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        raise ValueError(f"Not a Git repository: {repo}")

    output_dir = PROJECT_ROOT / "data" / "historical" / repo.name

    all_metrics = []
    all_edges = []

    for snapshot in SNAPSHOTS:
        # Confirm the selected commit exists.
        git(repo, "cat-file", "-e", f"{snapshot['commit']}^{{commit}}")

        metrics, edges = read_snapshot(repo, snapshot)
        all_metrics.extend(metrics)
        all_edges.extend(edges)

        date = snapshot["date"]
        write_csv(
            output_dir / f"{date}_architecture.csv",
            metrics,
            [
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
            ],
        )
        write_csv(
            output_dir / f"{date}_dependencies.csv",
            edges,
            [
                "repository",
                "snapshot_date",
                "commit_hash",
                "source_package",
                "target_package",
            ],
        )

    write_csv(
        output_dir / "all_snapshots_architecture.csv",
        all_metrics,
        [
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
        ],
    )

    print(f"\nOutput directory: {output_dir}")
    print(f"Total package-snapshot records: {len(all_metrics)}")
    print(f"Total package dependency edges: {len(all_edges)}")


if __name__ == "__main__":
    main()
