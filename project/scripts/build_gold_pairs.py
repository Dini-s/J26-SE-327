"""Build data/final/all_projects_clean.csv from the prepared real datasets (one command, two steps).

Where the input comes from (the whole chain, in order):
  1. data/raw/<project>/                 the downloaded datasets (requirements, code, answer keys)
  2. scripts/load_dataset.ipynb          -> data/processed/<project>/{artifacts,gold,traces}.json
  3. THIS script
       step A  every labelled (requirement, code) pair of every project in data/processed/
               -> data/final/all_projects.csv          (gold 1 = true link, 0 = not a link)
       step B  the code text is cleaned with the same rules the pipeline uses at retrieval time
               (package / import / licence header removed, whitespace collapsed); pairs whose code
               is empty after cleaning are dropped; pairs whose target is not code (CM-1 design
               documents, iTrust manifests) are dropped
               -> data/final/all_projects_clean.csv    (the file used for the evaluation tables)
               -> data/final/clean_code_report.json   (how many rows each rule removed)

Only the labelled pairs of gold.json are used, so every row has a real answer. Candidates are never
matched across projects (the project folder is the project field).

    .venv/bin/python scripts/build_gold_pairs.py
    .venv/bin/python scripts/build_gold_pairs.py --check     # build to a temporary folder and compare with the current file
"""

import argparse
import csv
import filecmp
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.traceability_agent.preprocess import strip_boilerplate  # noqa: E402
from shared.schemas.traceability import Artifact  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
FINAL = ROOT / "data" / "final"
COLUMNS_STEP_A = ["project", "requirement_id", "requirement_text", "code_id", "code_text", "gold"]
COLUMNS = COLUMNS_STEP_A + ["code_lines_removed"]
# a code target must look like source code (CM-1 targets are design documents, some iTrust targets are manifests)
CODE_LIKE = re.compile(r"[{};]|\bdef \b|\bpublic\b|\bclass\b|\bfunction\b|#include")
csv.field_size_limit(sys.maxsize)


def clean_text(value: object) -> str:
    """One line of text: every run of whitespace (including newlines) becomes one space."""
    return " ".join(str(value or "").split())


def is_code(artifact: Artifact) -> bool:
    return artifact.type == "code" and bool(CODE_LIKE.search(artifact.text))


def step_a(out_dir: Path) -> tuple[Path, dict]:
    """Every labelled pair of every project in data/processed -> all_projects.csv."""
    report: dict = {"projects": {}, "dropped": Counter()}
    rows, seen = [], set()
    for folder in sorted(p for p in PROCESSED.iterdir() if p.is_dir()):
        art_path, gold_path = folder / "artifacts.json", folder / "gold.json"
        if not (art_path.exists() and gold_path.exists()):
            report["dropped"]["folder_without_gold"] += 1
            continue
        artifacts = {a["id"]: a for a in json.loads(art_path.read_text(encoding="utf-8"))}
        counts = Counter()
        for req_id, code_id, is_true in json.loads(gold_path.read_text(encoding="utf-8")):
            req, code = artifacts.get(req_id), artifacts.get(code_id)
            if req is None or code is None:
                report["dropped"]["missing_artifact"] += 1
                continue
            req_text, code_text = clean_text(req.get("text")), clean_text(code.get("text"))
            if not req_text or not code_text:
                report["dropped"]["empty_text"] += 1
                continue
            key = (folder.name, req_id, code_id)
            if key in seen:
                report["dropped"]["duplicate_pair"] += 1
                continue
            seen.add(key)
            label = 1 if is_true else 0
            counts["pairs"] += 1
            counts["positives"] += label
            rows.append([folder.name, req_id, req_text, code_id, code_text, label])
        report["projects"][folder.name] = dict(counts)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "all_projects.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS_STEP_A)
        writer.writerows(rows)
    report["total_pairs"] = len(rows)
    report["total_positives"] = sum(r[5] for r in rows)
    report["dropped"] = dict(report["dropped"])
    return path, report


def step_b(source: Path, out_dir: Path) -> tuple[Path, dict]:
    """Clean the code text with the pipeline's own boilerplate rules -> all_projects_clean.csv."""
    cache: dict[str, dict[str, Artifact]] = {}
    removed_total = 0
    stats: Counter = Counter()
    path = out_dir / "all_projects_clean.csv"
    with source.open(encoding="utf-8", newline="") as src, path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=COLUMNS)
        writer.writeheader()
        for row in csv.DictReader(src):
            project = row["project"]
            if project not in cache:
                cache[project] = {a["id"]: Artifact(**a) for a in json.loads((PROCESSED / project / "artifacts.json").read_text(encoding="utf-8"))}
            code = cache[project][row["code_id"]]
            if not is_code(code):
                stats["dropped_not_code_target"] += 1
                stats[f"dropped_not_code_gold_{row['gold']}"] += 1
                stats[f"not_code_{project}"] += 1
                continue
            before = code.text.count("\n") + 1
            cleaned = strip_boilerplate(code)
            removed = max(0, before - (cleaned.count("\n") + 1))
            removed_total += removed
            stats["rows"] += 1
            if not cleaned.strip():                      # only imports / licence left: nothing to judge, drop the pair
                stats["dropped_code_empty_after_cleaning"] += 1
                stats[f"dropped_gold_{row['gold']}"] += 1
                continue
            writer.writerow({"project": project, "requirement_id": row["requirement_id"], "requirement_text": clean_text(row["requirement_text"]),
                             "code_id": row["code_id"], "code_text": clean_text(cleaned), "gold": row["gold"], "code_lines_removed": removed})
    report = {"rows_read": stats["rows"], "code_lines_removed_total": removed_total,
              "rows_dropped_not_code_target": stats["dropped_not_code_target"],
              "dropped_not_code_gold_1": stats["dropped_not_code_gold_1"], "dropped_not_code_gold_0": stats["dropped_not_code_gold_0"],
              "dropped_not_code_by_project": {k[len("not_code_"):]: v for k, v in stats.items() if k.startswith("not_code_")},
              "rows_dropped_code_empty": stats["dropped_code_empty_after_cleaning"],
              "dropped_gold_0": stats["dropped_gold_0"], "dropped_gold_1": stats["dropped_gold_1"],
              "rows_written": stats["rows"] - stats["dropped_code_empty_after_cleaning"]}
    return path, report


def build(out_dir: Path) -> dict:
    a_path, report_a = step_a(out_dir)
    _, report_b = step_b(a_path, out_dir)
    (out_dir / "clean_code_report.json").write_text(json.dumps(report_b, indent=1), encoding="utf-8")
    return {"step_a": report_a, "step_b": report_b}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="build into a temporary folder and compare with data/final")
    args = ap.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            report = build(Path(tmp))
            same = filecmp.cmp(Path(tmp) / "all_projects_clean.csv", FINAL / "all_projects_clean.csv", shallow=False) if (FINAL / "all_projects_clean.csv").exists() else None
            print(json.dumps(report["step_b"], indent=1))
            print("compared with data/final/all_projects_clean.csv:", "IDENTICAL" if same else "DIFFERENT" if same is False else "no file to compare with")
        return 0
    report = build(FINAL)
    print(json.dumps(report, indent=1))
    print(f"written: {FINAL / 'all_projects_clean.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
