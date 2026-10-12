"""Merge the 550 original SFT pairs with the validated new pairs and split train/val (Component 1). No model is called.

    python build_sft_dataset.py

Reads (never modifies):
  processed/llm_sft/synthetic_pairs_all_550.jsonl   the 550 original pairs (their review_status is kept)
  processed/llm_sft/validated_new.jsonl             new pairs that passed validate_sft_pairs.py (review_status="auto_validated")
  processed/llm_sft/sft_train_550.jsonl             only to copy the system prompt and to prove the formatter reproduces the old chat rows
  processed/tasks/{frozen_test_ids,generation_eval_ids,generation_eval_inputs}.csv   test data that must never appear
Writes (an existing file with different content is never overwritten):
  processed/llm_sft/synthetic_pairs_all.jsonl       merged, deduplicated by requirement_text (originals first)
  processed/llm_sft/sft_train.jsonl, sft_val.jsonl  chat format {id, review_status, messages:[system,user,assistant]}, stratified 90/10 by
                                                    (source, status), seed 327
"""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[2]
PROCESSED = PROJECT / "data" / "component1" / "processed"
TASKS = PROCESSED / "tasks"
SFT = PROCESSED / "llm_sft"
SEED = 327
VAL_SHARE = 0.10


def h(*parts):
    return hashlib.sha256("|".join(str(p) for p in (SEED,) + parts).encode("utf-8")).hexdigest()


def key(text):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s+", " ", str(text).lower()))


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def dump_jsonl(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def write_safe(path, text):
    path = Path(path)
    if path.exists():
        if path.read_text(encoding="utf-8") == text:
            return "unchanged"
        raise SystemExit(f"{path} exists with different content; delete it first if you want to rebuild")
    path.write_text(text, encoding="utf-8", newline="\n")
    return "written"


def assistant_json(row):
    """The assistant message: the model answers with this JSON object only (same key order as the 550 originals)."""
    if row["status"] == "ok":
        out = {"status": "ok", "user_story": row["user_story"], "technical_task": row["technical_task"],
               "acceptance_criteria": row["acceptance_criteria"], "rationale": row["rationale"]}
    else:
        out = {"status": "needs_clarification", "clarification_questions": row["clarification_questions"], "rationale": row["rationale"]}
    return json.dumps(out, ensure_ascii=False)


def chat_row(row, system_prompt):
    return {"id": row["id"], "review_status": row["review_status"],
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": f"Requirement: {row['requirement_text']}"},
                         {"role": "assistant", "content": assistant_json(row)}]}


def merge(originals, new):
    """Originals first, then new rows; a row whose normalized requirement_text was already taken is dropped."""
    seen, merged, dropped = set(), [], []
    for r in originals + new:
        k = key(r["requirement_text"])
        if k in seen:
            dropped.append(r["id"])
            continue
        seen.add(k)
        merged.append(r)
    return merged, dropped


def split(rows):
    """Stratified by (source, status): in each stratum the rows are ordered by sha256(seed|id) and the first round(10%) go to val."""
    strata = defaultdict(list)
    for r in rows:
        strata[(r["source"], r["status"])].append(r)
    train, val = [], []
    for k in sorted(strata):
        ordered = sorted(strata[k], key=lambda r: h("split", r["id"]))
        n_val = round(len(ordered) * VAL_SHARE)
        val += ordered[:n_val]
        train += ordered[n_val:]
    order = {r["id"]: i for i, r in enumerate(rows)}
    return sorted(train, key=lambda r: order[r["id"]]), sorted(val, key=lambda r: order[r["id"]])


def forbidden():
    frozen = set(pd.read_csv(TASKS / "frozen_test_ids.csv", encoding="utf-8-sig", dtype=str).record_id)
    ev_ids = set(pd.read_csv(TASKS / "generation_eval_ids.csv", encoding="utf-8-sig", dtype=str).id)
    ev_texts = {key(t) for t in pd.read_csv(TASKS / "generation_eval_inputs.csv", encoding="utf-8-sig", dtype=str).requirement_text}
    return frozen | ev_ids, ev_texts


def main():
    originals = load_jsonl(SFT / "synthetic_pairs_all_550.jsonl")
    new = load_jsonl(SFT / "validated_new.jsonl")
    old_train = load_jsonl(SFT / "sft_train_550.jsonl")
    old_val = load_jsonl(SFT / "sft_val_550.jsonl")
    system_prompt = old_train[0]["messages"][0]["content"]
    assert all(m["messages"][0]["content"] == system_prompt for m in old_train + old_val), "the 550 chat files use more than one system prompt"

    # the formatter must reproduce the existing chat rows byte for byte
    by_id = {r["id"]: r for r in originals}
    for old in old_train + old_val:
        assert chat_row(by_id[old["id"]], system_prompt) == old, f"formatter does not reproduce {old['id']}"

    bad_ids, bad_texts = forbidden()
    merged, dropped = merge(originals, new)
    leaks = [r["id"] for r in merged if r["id"] in bad_ids or key(r["requirement_text"]) in bad_texts]
    if leaks:
        raise SystemExit(f"{len(leaks)} merged rows are test/eval data, e.g. {leaks[:3]}")
    train, val = split(merged)
    assert {r["id"] for r in train}.isdisjoint({r["id"] for r in val})

    print("pairs.jsonl:", write_safe(SFT / "synthetic_pairs_all.jsonl", dump_jsonl(merged)))
    print("sft_train.jsonl:", write_safe(SFT / "sft_train.jsonl", dump_jsonl([chat_row(r, system_prompt) for r in train])))
    print("sft_val.jsonl:", write_safe(SFT / "sft_val.jsonl", dump_jsonl([chat_row(r, system_prompt) for r in val])))
    print(f"[build] originals={len(originals)} new={len(new)} merged={len(merged)} dropped_duplicates={len(dropped)} train={len(train)} val={len(val)}")
    print("[build] status:", dict(Counter(r["status"] for r in merged)), "| review_status:", dict(Counter(r["review_status"] for r in merged)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
