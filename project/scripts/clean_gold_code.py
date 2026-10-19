"""Clean the code text of the merged gold CSV with the project's own preprocessing.

Why it starts from the raw artifacts: the merged CSV has every line joined into one line, so the
line-based boilerplate rules (import / package / licence header) cannot run on it. This script re-reads
data/processed/<project>/artifacts.json, applies the same rules the pipeline uses (llm_text, the
prompt view), and writes a new CSV. Requirement text is only whitespace-cleaned.

Output: data/final/all_projects_clean.csv   (same columns as all_projects.csv, plus code_lines_removed)
        data/final/clean_code_report.json

    python scripts/clean_gold_code.py
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.traceability_agent.preprocess import strip_boilerplate  # noqa: E402
from shared.schemas.traceability import Artifact  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
SRC = ROOT / "data" / "final" / "all_projects.csv"
OUT = ROOT / "data" / "final" / "all_projects_clean.csv"
REPORT = ROOT / "data" / "final" / "clean_code_report.json"
COLUMNS = ["project", "requirement_id", "requirement_text", "code_id", "code_text", "gold", "code_lines_removed"]
csv.field_size_limit(sys.maxsize)


def clean_inline(value: str) -> str:
    return " ".join(value.split())


def main() -> None:
    cache: dict[str, dict[str, Artifact]] = {}
    removed_total = 0
    stats: Counter = Counter()
    with SRC.open(encoding="utf-8", newline="") as src, OUT.open("w", encoding="utf-8", newline="") as out:
        reader = csv.DictReader(src)
        writer = csv.DictWriter(out, fieldnames=COLUMNS)
        writer.writeheader()
        for row in reader:
            project = row["project"]
            if project not in cache:
                cache[project] = {a["id"]: Artifact(**a) for a in json.loads((PROCESSED / project / "artifacts.json").read_text(encoding="utf-8"))}
            code = cache[project][row["code_id"]]
            before = code.text.count("\n") + 1
            cleaned = strip_boilerplate(code)
            removed = max(0, before - (cleaned.count("\n") + 1))
            removed_total += removed
            stats["rows"] += 1
            if not cleaned.strip():
                # nothing left to judge (only imports / licence): drop the pair instead of keeping a trivial negative
                stats["dropped_code_empty_after_cleaning"] += 1
                stats[f"dropped_gold_{row['gold']}"] += 1
                continue
            writer.writerow({
                "project": project,
                "requirement_id": row["requirement_id"],
                "requirement_text": clean_inline(row["requirement_text"]),
                "code_id": row["code_id"],
                "code_text": clean_inline(cleaned),
                "gold": row["gold"],
                "code_lines_removed": removed,
            })
    report = {"rows_read": stats["rows"], "code_lines_removed_total": removed_total,
              "rows_dropped_code_empty": stats["dropped_code_empty_after_cleaning"],
              "dropped_gold_0": stats["dropped_gold_0"], "dropped_gold_1": stats["dropped_gold_1"],
              "rows_written": stats["rows"] - stats["dropped_code_empty_after_cleaning"]}
    REPORT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
