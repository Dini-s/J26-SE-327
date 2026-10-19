"""Merge and clean the Gemini batch CSVs into one training file.

Input : data/synthetic/gemini/*.csv  (columns: requirement_id,requirement_text,code_text,label,kind)
Output: data/synthetic/final/synthetic_all.csv + clean_report.json

Checks, in order (a bad item is dropped as a whole, never half-kept):
  1. header and column count
  2. label in {0,1}, kind in {pos,hard}, and each item has exactly 1 pos + 2 hard rows
  3. no empty field; requirement and code are real text
  4. no forbidden word in the code (shortcut words such as "wrong", "alternative")
  5. code has balanced braces/parentheses (a cut-off class is dropped)
  6. the same requirement text is kept only once (first occurrence)
  7. the same code text is kept only once

    python scripts/clean_synthetic.py                       # reads data/synthetic/gemini/
    python scripts/clean_synthetic.py --input ~/Downloads   # reads the CSVs you downloaded
"""

import csv
import glob
import json
import re
import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN_DIR = ROOT / "data" / "synthetic" / "gemini"
OUT_DIR = ROOT / "data" / "synthetic" / "final"
COLUMNS = ["requirement_id", "requirement_text", "code_text", "label", "kind"]
FORBIDDEN = re.compile(r"\b(correct|wrong|fake|alternative|negative|decoy|variant|sample|test|dummy)\b", re.IGNORECASE)
csv.field_size_limit(sys.maxsize)


def balanced(code: str) -> bool:
    pairs = {")": "(", "}": "{", "]": "["}
    stack = []
    in_str = False
    prev = ""
    for ch in code:
        if ch == '"' and prev != "\\":
            in_str = not in_str
        elif not in_str:
            if ch in "({[":
                stack.append(ch)
            elif ch in pairs:
                if not stack or stack.pop() != pairs[ch]:
                    return False
        prev = ch
    return not stack and not in_str


def read_rows(path: Path, report: Counter) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None or [h.strip() for h in header] != COLUMNS:
            report["bad_header_files"] += 1
            print(f"SKIP {path.name}: header is {header}", file=sys.stderr)
            return []
        rows = []
        for raw in reader:
            if not any(cell.strip() for cell in raw):
                continue
            if len(raw) != len(COLUMNS):
                report["bad_column_count_rows"] += 1
                continue
            rows.append(dict(zip(COLUMNS, [c.strip() for c in raw])))
        return rows


def check_item(rows: list[dict[str, str]], report: Counter) -> bool:
    kinds = Counter(r["kind"] for r in rows)
    labels_ok = all(r["label"] in ("0", "1") for r in rows)
    if len(rows) != 3 or kinds != Counter({"pos": 1, "hard": 2}) or not labels_ok:
        report["incomplete_or_bad_label_items"] += 1
        return False
    for r in rows:
        if not all(r[c] for c in COLUMNS):
            report["empty_field_items"] += 1
            return False
        if (r["kind"] == "pos") != (r["label"] == "1"):
            report["label_kind_mismatch_items"] += 1
            return False
        if FORBIDDEN.search(r["code_text"]) or FORBIDDEN.search(r["requirement_text"]):
            report["forbidden_word_items"] += 1
            return False
        code = r["code_text"].replace("\\n", "\n").replace('\\"', '"')
        if not balanced(code):
            report["unbalanced_code_items"] += 1
            return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", default=str(IN_DIR), help="folder with the downloaded Gemini CSV files")
    args = ap.parse_args()
    report: Counter = Counter()
    files = sorted(glob.glob(str(Path(args.input).expanduser() / "*.csv")))
    if not files:
        print(f"No CSV files in {args.input}.")
        return
    items: dict[str, list[dict[str, str]]] = {}
    for f in files:
        for r in read_rows(Path(f), report):
            items.setdefault(r["requirement_id"], []).append(r)
        report["files_read"] += 1

    seen_req, seen_code = set(), set()
    kept: list[dict[str, str]] = []
    for rid in sorted(items):
        rows = items[rid]
        report["items_read"] += 1
        if not check_item(rows, report):
            continue
        req_key = rows[0]["requirement_text"].lower()
        code_keys = [r["code_text"] for r in rows]
        if req_key in seen_req:
            report["duplicate_requirement_items"] += 1
            continue
        if any(c in seen_code for c in code_keys):
            report["duplicate_code_items"] += 1
            continue
        seen_req.add(req_key)
        seen_code.update(code_keys)
        kept.extend(rows)
        report["items_kept"] += 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "synthetic_all.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(kept)
    summary = {
        "files_read": report["files_read"],
        "items_read": report["items_read"],
        "items_kept": report["items_kept"],
        "rows_kept": len(kept),
        "dropped": {k: v for k, v in report.items() if k not in ("files_read", "items_read", "items_kept")},
        "kept_kinds": dict(Counter(r["kind"] for r in kept)),
    }
    (OUT_DIR / "clean_report.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
