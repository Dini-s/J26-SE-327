"""Merge the downloaded gold datasets into one clean CSV.

Input : data/processed/<dataset>/artifacts.json  (requirements and code, with text)
        data/processed/<dataset>/gold.json       ([requirement_id, code_id, is_true_link] per labelled pair)
Output: data/final/all_projects.csv + clean_report.json

Only the pairs that gold.json labels are written (true and false), so every row has a real answer.
The project folder is the project field, so candidates are never matched across projects.

    python scripts/clean_gold_datasets.py
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data" / "final"
COLUMNS = ["project", "requirement_id", "requirement_text", "code_id", "code_text", "gold"]
csv.field_size_limit(sys.maxsize)


def clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def main() -> None:
    report: dict = {"projects": {}, "dropped": Counter()}
    rows: list[list] = []
    seen: set[tuple] = set()
    for folder in sorted(p for p in PROCESSED.iterdir() if p.is_dir()):
        art_path, gold_path = folder / "artifacts.json", folder / "gold.json"
        if not (art_path.exists() and gold_path.exists()):
            report["dropped"]["folder_without_gold"] += 1
            continue
        artifacts = {a["id"]: a for a in json.loads(art_path.read_text(encoding="utf-8"))}
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        project = folder.name
        counts = Counter()
        for req_id, code_id, is_true in gold:
            req, code = artifacts.get(req_id), artifacts.get(code_id)
            if req is None or code is None:
                report["dropped"]["missing_artifact"] += 1
                continue
            req_text, code_text = clean_text(req.get("text")), clean_text(code.get("text"))
            if not req_text or not code_text:
                report["dropped"]["empty_text"] += 1
                continue
            key = (project, req_id, code_id)
            if key in seen:
                report["dropped"]["duplicate_pair"] += 1
                continue
            seen.add(key)
            label = 1 if is_true else 0
            counts["pairs"] += 1
            counts["positives"] += label
            rows.append([project, req_id, req_text, code_id, code_text, label])
        report["projects"][project] = dict(counts)

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "all_projects.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    report["total_pairs"] = len(rows)
    report["total_positives"] = sum(r[5] for r in rows)
    report["dropped"] = dict(report["dropped"])
    (OUT / "clean_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
