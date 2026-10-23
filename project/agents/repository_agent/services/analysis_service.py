import csv
import subprocess
import sys
from pathlib import Path

from agents.repository_agent.services.technology_detector import (
    detect_repository_technology,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = PROJECT_ROOT / "data" / "user_repositories"

STRUCTURE_SCRIPT = (
    PROJECT_ROOT / "agents" / "repository_agent" / "analysis" / "structure_analyzer.py"
)
DEPENDENCY_SCRIPT = (
    PROJECT_ROOT
    / "agents"
    / "repository_agent"
    / "dependency"
    / "dependency_analyzer.py"
)
ARCHITECTURE_SCRIPT = (
    PROJECT_ROOT
    / "agents"
    / "repository_agent"
    / "architecture"
    / "architecture_analyzer.py"
)
EVOLUTION_SCRIPT = (
    PROJECT_ROOT / "agents" / "repository_agent" / "evolution" / "evolution_analyzer.py"
)


def _run_script(*args: str) -> str:
    """Run an existing analyzer and return its console output."""
    result = subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )

    if result.returncode != 0:
        # Keep detailed diagnostics in the server terminal.
        print(f"Analyzer failed: {args[0]}")
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError(
            f"Analysis stage failed: {Path(args[0]).name}. "
            "Check the API server terminal for details."
        )

    return result.stdout


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        raise RuntimeError(f"Expected analysis output was not created: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def analyze_registered_repository(repository_id: str) -> dict:
    """Run structure, dependency, architecture and evolution analysis."""

    # IDs are UUIDs; validate before building filesystem paths.
    if not repository_id or any(
        char not in "0123456789abcdef-" for char in repository_id.lower()
    ):
        raise ValueError("Invalid repository ID.")

    repo_path = (REPOSITORY_ROOT / repository_id).resolve()

    if repo_path.parent != REPOSITORY_ROOT.resolve():
        raise ValueError("Invalid repository path.")

    if not repo_path.is_dir() or not (repo_path / ".git").exists():
        raise FileNotFoundError("Clone the repository before analyzing it.")

    # Each registered repository gets its own output files.
    structure_file = (
        PROJECT_ROOT / "data" / "structural" / f"{repository_id}_structure.csv"
    )
    dependency_file = (
        PROJECT_ROOT / "data" / "dependencies" / f"{repository_id}_dependencies.csv"
    )
    architecture_file = (
        PROJECT_ROOT / "data" / "architecture" / f"{repository_id}_architecture.csv"
    )
    evolution_file = (
        PROJECT_ROOT / "data" / "evolution" / f"{repository_id}_evolution.csv"
    )
    file_evolution_file = (
        PROJECT_ROOT / "data" / "evolution" / f"{repository_id}_file_evolution.csv"
    )
    findings_file = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "architecture_violations"
        / f"{repository_id}_findings.csv"
    )

    # 1. Structure analysis
    _run_script(str(STRUCTURE_SCRIPT), str(repo_path))
    structure_rows = _read_csv(structure_file)

    # 2. Dependency analysis
    _run_script(
        str(DEPENDENCY_SCRIPT),
        str(repo_path),
        "--output-dir",
        str(PROJECT_ROOT / "data" / "dependencies"),
    )
    dependency_rows = _read_csv(dependency_file)

    # 3. Architecture analysis: consumes the two CSVs above
    _run_script(str(ARCHITECTURE_SCRIPT), str(repo_path))
    architecture_rows = _read_csv(architecture_file)
    # The analyzer always writes this file; an empty CSV means no candidates.
    findings_rows = _read_csv(findings_file) if findings_file.is_file() else []

    # 4. Git evolution analysis
    _run_script(str(EVOLUTION_SCRIPT), str(repo_path))
    evolution_rows = _read_csv(evolution_file)
    file_evolution_rows = _read_csv(file_evolution_file)
    evolution_summary = dict(evolution_rows[0]) if evolution_rows else {}
    for field in (
        "commit_count", "contributor_count", "files_changed",
        "total_insertions", "total_deletions", "total_churn",
    ):
        try:
            value = evolution_summary.get(field)
            evolution_summary[field] = int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            evolution_summary[field] = None
    technology_info = detect_repository_technology(repo_path)

    return {
        "repository_id": repository_id,
        "status": "Analysis Complete",
        "language": technology_info["language"],
        "technology": technology_info["technology"],
        "summary": {
            "packages": len(structure_rows),
            "dependency_edges": len(dependency_rows),
            "architecture_packages": len(architecture_rows),
            "files_with_evolution": len(file_evolution_rows),
        },
        "structure": structure_rows,
        "dependencies": dependency_rows,
        "architecture": architecture_rows,
        "architecture_findings": findings_rows,
        "architecture_findings_summary": {
            "total_candidates": len(findings_rows),
            "confirmed": sum(
                1
                for row in findings_rows
                if row.get("status", "").lower() == "confirmed"
            ),
            "candidate": sum(
                1
                for row in findings_rows
                if row.get("status", "").lower() == "candidate"
            ),
            "by_type": {
                finding_type: sum(
                    1
                    for row in findings_rows
                    if row.get("finding_type") == finding_type
                )
                for finding_type in sorted(
                    {row.get("finding_type", "UNKNOWN") for row in findings_rows}
                )
            },
        },
        "evolution": evolution_rows,  # retained for backward compatibility
        "evolution_summary": evolution_summary,
        "file_evolution": file_evolution_rows,
        "file_evolution_count": len(file_evolution_rows),
    }
