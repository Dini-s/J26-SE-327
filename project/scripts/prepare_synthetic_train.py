"""Clean generated (synthetic) traceability items and write train / valid files for the reranker.

Inputs (both are read if present):
  data/synthetic/gemini/*.csv            columns: requirement_id,requirement_text,code_text,label,kind
  data/synthetic/{user_domains,deepseek,claude}/*.json
                                          list of {"requirement", "code", "hard_negatives": [...]}
Output:
  data/synthetic_clean/train.jsonl, valid.jsonl   (reranker format: dataset, source_id, target_id, query, doc, label, kind)
  data/synthetic_clean/clean_report.json

Cleaning, per item (a bad item is dropped whole):
  1. code: package / import / licence header removed with the pipeline's strip_boilerplate
  2. every code (positive and negative) must still have text after cleaning, and balanced braces
  3. no forbidden word (wrong, alternative, test, ...) in any code or requirement
  4. each negative must differ from the positive after cleaning (identical text = not a negative)
  5. duplicate requirement text or duplicate code is kept once
Split: whole source files go to valid (about 10 %), so validation contains unseen domains.

    python scripts/prepare_synthetic_train.py
"""

import csv
import glob
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.traceability_agent.preprocess import strip_boilerplate  # noqa: E402
from shared.schemas.traceability import Artifact  # noqa: E402

SYN = ROOT / "data" / "synthetic"
OUT = ROOT / "data" / "synthetic_clean"
FORBIDDEN = re.compile(r"\b(correct|wrong|fake|alternative|negative|decoy|variant|sample|test|dummy)\b", re.IGNORECASE)
# requirements may legitimately say "negative balance", so only the shortcut-revealing words are checked there
FORBIDDEN_REQ = re.compile(r"\b(correct|wrong|fake|alternative|decoy|variant|dummy)\b", re.IGNORECASE)
JSON_FOLDERS = ("user_domains", "deepseek", "claude")
VALID_FRACTION = 0.10
SEED = 33
csv.field_size_limit(sys.maxsize)


CLASS_NAME = re.compile(r"\bclass\s+(\w+)")


def label_revealing_name(code: str) -> bool:
    """True if the declared class name itself says right/wrong (the shortcut we removed earlier).

    Words such as "test" inside JSP attributes (<c:when test=...>) or "negative balance" in logic are legitimate
    and are not checked.
    """
    return any(FORBIDDEN.search(name) for name in CLASS_NAME.findall(code))


def balanced(code: str) -> bool:
    pairs, stack, in_str, prev = {")": "(", "}": "{", "]": "["}, [], False, ""
    for ch in code:
        if ch == '"' and prev != "\\":
            in_str = not in_str
        elif not in_str:
            if ch in "({[":
                stack.append(ch)
            elif ch in pairs and (not stack or stack.pop() != pairs[ch]):
                return False
        prev = ch
    return not stack and not in_str


def clean_code(raw: str) -> str:
    cleaned = strip_boilerplate(Artifact(id="x", type="code", text=raw))
    return " ".join(cleaned.split())


def load_json_items(report: Counter) -> list[dict]:
    items = []
    for f in sorted(p for folder in JSON_FOLDERS for p in glob.glob(str(SYN / folder / "*.json"))):
        group = f"{Path(f).parent.name}/{Path(f).stem}"
        for i, x in enumerate(json.loads(Path(f).read_text(encoding="utf-8"))):
            if not isinstance(x, dict) or not x.get("requirement") or not x.get("code"):
                report["bad_json_item"] += 1
                continue
            items.append({"group": group, "id": f"{group}#{i}", "requirement": x["requirement"],
                          "code": x["code"], "hard": list(x.get("hard_negatives") or [])})
    return items


def load_csv_items(report: Counter) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for f in sorted(glob.glob(str(SYN / "gemini" / "*.csv"))):
        with open(f, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                grouped.setdefault(row.get("requirement_id", ""), []).append(row)
    items = []
    for rid, rows in grouped.items():
        pos = [r for r in rows if r.get("kind") == "pos" and r.get("label") == "1"]
        hard = [r for r in rows if r.get("kind") == "hard" and r.get("label") == "0"]
        if len(pos) != 1 or len(hard) != 2:
            report["csv_incomplete_item"] += 1
            continue
        items.append({"group": "gemini", "id": rid, "requirement": pos[0]["requirement_text"],
                      "code": pos[0]["code_text"], "hard": [h["code_text"] for h in hard]})
    return items


def main() -> None:
    report: Counter = Counter()
    items = load_json_items(report) + load_csv_items(report)
    report["items_read"] = len(items)

    kept, seen_req, seen_code = [], set(), set()
    for it in items:
        ok = True
        req = " ".join(it["requirement"].split())
        if FORBIDDEN_REQ.search(req):
            report["forbidden_requirement"] += 1
            continue
        pos_code = clean_code(it["code"])
        negs = [clean_code(h) for h in it["hard"]]
        if not pos_code or not balanced(pos_code):
            report["bad_positive_code"] += 1
            continue
        for n in negs:
            if not n or not balanced(n) or label_revealing_name(n) or n == pos_code:
                ok = False
                break
        if label_revealing_name(pos_code) or not ok:
            report["bad_negative_or_forbidden_code"] += 1
            continue
        if req.lower() in seen_req:
            report["duplicate_requirement"] += 1
            continue
        if pos_code in seen_code:
            report["duplicate_positive_code"] += 1
            continue
        seen_req.add(req.lower())
        seen_code.add(pos_code)
        kept.append({"group": it["group"], "id": it["id"], "req": req, "pos": pos_code, "negs": negs})
    report["items_kept"] = len(kept)

    groups = sorted({k["group"] for k in kept})
    rng = random.Random(SEED)
    valid_groups = set(rng.sample(groups, max(1, round(len(groups) * VALID_FRACTION)))) if groups else set()
    OUT.mkdir(parents=True, exist_ok=True)
    counts = {"train": Counter(), "valid": Counter()}
    files = {name: (OUT / f"{name}.jsonl").open("w", encoding="utf-8") for name in ("train", "valid")}
    try:
        for k in kept:
            split = "valid" if k["group"] in valid_groups else "train"
            fh = files[split]
            rows = [(f"{k['id']}-pos", k["pos"], 1, "pos")] + [
                (f"{k['id']}-hard{j}", n, 0, "hard") for j, n in enumerate(k["negs"])]
            for target_id, doc, label, kind in rows:
                fh.write(json.dumps({"dataset": "synthetic", "source_id": k["id"], "target_id": target_id,
                                     "query": k["req"], "doc": doc, "label": label, "kind": kind},
                                    ensure_ascii=False) + "\n")
                counts[split][kind] += 1
    finally:
        for fh in files.values():
            fh.close()
    report["groups"] = len(groups)
    report["valid_groups"] = sorted(valid_groups)
    report["rows"] = {s: dict(c) for s, c in counts.items()}
    (OUT / "clean_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
