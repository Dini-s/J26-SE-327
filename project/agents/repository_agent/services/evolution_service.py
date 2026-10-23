"""Read repository-level and file-level Git evolution outputs."""

import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVOLUTION_DIR = PROJECT_ROOT / "data" / "evolution"
NUMERIC_SUMMARY_FIELDS = (
    "commit_count",
    "contributor_count",
    "files_changed",
    "total_insertions",
    "total_deletions",
    "total_churn",
)


def _validate_repository_id(repository_id: str) -> str:
    if not repository_id or any(
        c not in "0123456789abcdef-" for c in repository_id.lower()
    ):
        raise ValueError("Invalid repository ID.")
    return repository_id


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Evolution output not found: {path.name}")
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def _to_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_evolution_summary(repository_id: str) -> dict:
    """Return repository-wide metrics from the analyzer's summary CSV."""
    repository_id = _validate_repository_id(repository_id)
    rows = _read_csv(EVOLUTION_DIR / f"{repository_id}_evolution.csv")
    if not rows:
        raise RuntimeError("Evolution summary CSV contains no data rows.")
    row = rows[0]
    result = {key: _to_int(row.get(key)) for key in NUMERIC_SUMMARY_FIELDS}
    result["repository"] = row.get("repository") or repository_id
    result["status"] = "available"
    return result


def get_file_evolution(repository_id: str, limit: int = 500) -> dict:
    """Return per-file evolution metrics, with a bounded response size."""
    repository_id = _validate_repository_id(repository_id)
    if limit < 1 or limit > 5000:
        raise ValueError("limit must be between 1 and 5000.")
    rows = _read_csv(EVOLUTION_DIR / f"{repository_id}_file_evolution.csv")
    numeric_fields = (
        "change_records",
        "commit_count",
        "total_insertions",
        "total_deletions",
        "total_churn",
    )
    normalized = []
    for row in rows:
        item = dict(row)
        for field in numeric_fields:
            item[field] = _to_int(item.get(field))
        normalized.append(item)
    return {
        "repository_id": repository_id,
        "total_files": len(normalized),
        "returned_files": min(len(normalized), limit),
        "limit": limit,
        "files": normalized[:limit],
    }
