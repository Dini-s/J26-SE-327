"""Validate the generated SFT pairs (Component 1). No model is called except the MiniLM embedder used for the near-duplicate check.

    python validate_sft_pairs.py [--quiet]

Reads processed/llm_sft/synthetic_batches/{batch_NNN,retry_NNN}.jsonl (first attempt / second attempt), the 550 original pairs
(processed/llm_sft/synthetic_pairs_all_550.jsonl) and the batch-3 seeds. Writes (rewriting its own derived files on every run):
  processed/llm_sft/validated_new.jsonl   passing rows, review_status="auto_validated"
  processed/llm_sft/rejects.jsonl         failing rows with attempt (1 = batch file, 2 = retry file) and the reasons
  processed/llm_sft/qa_sample_100.jsonl   100 random passing rows (seed 327) for a human spot check

Rules (a row fails with every reason that applies):
  schema          exact key set, types, synthetic == true, ids/source/requirement_text identical to the seed file, id unique
  status ok       user_story matches ^As an? .+, I want .+, so that .+\\.$ ; technical_task non-empty ; 2-6 acceptance criteria each matching
                  ^Given .+, when .+, then .+ ; rationale non-empty ; no clarification_questions ; no empty strings anywhere
  status needs_clarification   user_story and technical_task null, acceptance_criteria [], clarification_questions: 1-5 non-empty strings, rationale non-empty
  numbers         every number written in an output field must also appear in the requirement text
  copied          user_story / technical_task must not be a copy of the requirement (difflib ratio >= 0.92 or story containing the full requirement)
  near_duplicate  MiniLM cosine > 0.95 to an earlier accepted output of the same status (the 550 originals come first, then batches in order)
"""
import argparse
import difflib
import json
import random
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents.requirement_agent.features import SEED, embed, normalize_for_models  # noqa: E402

PROJECT = Path(__file__).resolve().parents[2]
SFT = PROJECT / "data" / "component1" / "processed" / "llm_sft"
BATCH_DIR = SFT / "synthetic_batches"
SEED_FILE = PROJECT / "data" / "component1" / "processed" / "tasks" / "synthetic_seed_inputs_batch3.csv"
ORIGINAL = SFT / "synthetic_pairs_all_550.jsonl"
OUT_VALID, OUT_REJECTS, OUT_QA = SFT / "validated_new.jsonl", SFT / "rejects.jsonl", SFT / "qa_sample_100.jsonl"

STORY = re.compile(r"^As an? .+, I want .+, so that .+\.$")
GWT = re.compile(r"^Given .+, when .+, then .+")
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
BASE_KEYS = {"id", "source", "requirement_text", "synthetic", "generator", "review_status", "status", "user_story", "technical_task",
             "acceptance_criteria", "rationale", "reviewer_note"}
OPTIONAL_KEYS = {"requirement_text_raw", "clarification_questions"}
COPY_RATIO = 0.92
DUP_COSINE = 0.95


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def numbers_in(text):
    return {n.rstrip(".,").replace(",", "") for n in NUMBER.findall(str(text))}


def output_strings(row):
    out = [row.get("rationale") or ""]
    if row.get("user_story"):
        out.append(row["user_story"])
    if row.get("technical_task"):
        out.append(row["technical_task"])
    out += list(row.get("acceptance_criteria") or [])
    out += list(row.get("clarification_questions") or [])
    return [s for s in out if isinstance(s, str)]


def output_text(row):
    """The text used for the near-duplicate check."""
    if row.get("status") == "ok":
        return f"{row['user_story']} {row['technical_task']}"
    return " ".join(row.get("clarification_questions") or []) + " " + (row.get("rationale") or "")


def check_row(row, seed=None):
    """List of reason codes for one row (empty list = passes the row-level checks)."""
    reasons = []
    keys = set(row)
    if not BASE_KEYS <= keys or not keys <= BASE_KEYS | OPTIONAL_KEYS:
        reasons.append(f"schema_keys(missing={sorted(BASE_KEYS - keys)}, extra={sorted(keys - BASE_KEYS - OPTIONAL_KEYS)})")
        return reasons
    if row["synthetic"] is not True:
        reasons.append("schema_synthetic_not_true")
    for k in ("id", "source", "requirement_text", "generator", "review_status", "rationale"):
        if not isinstance(row[k], str) or not row[k].strip():
            reasons.append(f"empty_or_non_string:{k}")
    if seed is not None:
        if row["source"] != seed["source"] or row["requirement_text"] != seed["requirement_text"]:
            reasons.append("seed_mismatch")
    status = row["status"]
    req = str(row["requirement_text"])
    if status == "ok":
        story, task, crit = row["user_story"], row["technical_task"], row["acceptance_criteria"]
        if not isinstance(story, str) or not STORY.match(story.strip()):
            reasons.append("story_pattern")
        if not isinstance(task, str) or not task.strip():
            reasons.append("empty_technical_task")
        if not isinstance(crit, list) or not 2 <= len(crit) <= 6:
            reasons.append(f"criteria_count({len(crit) if isinstance(crit, list) else 'not_list'})")
        else:
            for i, c in enumerate(crit, 1):
                if not isinstance(c, str) or not c.strip():
                    reasons.append(f"empty_criterion_{i}")
                elif not GWT.match(c.strip()):
                    reasons.append(f"criterion_pattern_{i}")
            if len({norm(c) for c in crit if isinstance(c, str)}) < len(crit):
                reasons.append("duplicate_criteria")
        if row.get("clarification_questions"):
            reasons.append("ok_row_has_clarification_questions")
        if isinstance(story, str) and isinstance(task, str):
            if norm(req) and (norm(req) in norm(story) or difflib.SequenceMatcher(None, norm(story), norm(req)).ratio() >= COPY_RATIO):
                reasons.append("copied_story")
            if difflib.SequenceMatcher(None, norm(task), norm(req)).ratio() >= COPY_RATIO:
                reasons.append("copied_technical_task")
    elif status == "needs_clarification":
        if row["user_story"] is not None or row["technical_task"] is not None:
            reasons.append("nc_story_or_task_not_null")
        if row["acceptance_criteria"] != []:
            reasons.append("nc_criteria_not_empty")
        q = row.get("clarification_questions")
        if not isinstance(q, list) or not 1 <= len(q) <= 5 or not all(isinstance(x, str) and x.strip() for x in q):
            reasons.append("nc_clarification_questions")
    else:
        reasons.append(f"schema_status({status!r})")
        return reasons
    allowed = numbers_in(req) | numbers_in(row.get("requirement_text_raw", ""))
    extra = sorted({n for s in output_strings(row) for n in numbers_in(s)} - allowed)
    if extra:
        reasons.append(f"numbers_not_in_requirement({','.join(extra)})")
    return reasons


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_all(seeds, originals, batch_files):
    """Returns (passed rows, rejected dicts). Row order: batches by file name, rows in file order."""
    seed_by_id = {r.id: {"source": r.source, "requirement_text": r.requirement_text} for r in seeds.itertuples()}
    rows = []
    for path in batch_files:
        attempt = 2 if path.name.startswith("retry_") else 1
        for i, row in enumerate(load_jsonl(path), 1):
            rows.append((attempt, path.name, i, row))
    rejected, candidates = [], []
    for attempt, fname, i, row in rows:
        reasons = check_row(row, seed_by_id.get(row.get("id")))
        rid = row.get("id")
        if rid not in seed_by_id:
            reasons.append("id_not_in_seed_file")
        (rejected if reasons else candidates).append(
            {"id": rid, "attempt": attempt, "file": fname, "line": i, "reasons": reasons, "row": row} if reasons else (attempt, fname, i, row))
    # near-duplicate outputs: originals first, then candidates in order
    accepted_vec = {"ok": [], "needs_clarification": []}
    for r in originals:
        accepted_vec[r["status"]].append(r)
    orig_vec = {s: embed([normalize_for_models(output_text(r)) for r in accepted_vec[s]]) if accepted_vec[s] else np.zeros((0, 384), np.float32) for s in accepted_vec}
    cand_vec = embed([normalize_for_models(output_text(c[3])) for c in candidates]) if candidates else np.zeros((0, 384), np.float32)
    pools = {s: [v for v in orig_vec[s]] for s in orig_vec}
    passed, passed_ids = [], set()
    for idx, (attempt, fname, i, row) in enumerate(candidates):
        if row["id"] in passed_ids:  # a seed already passed in an earlier file (a retry never replaces a pass)
            rejected.append({"id": row["id"], "attempt": attempt, "file": fname, "line": i, "reasons": ["duplicate_id_in_batches"], "row": row})
            continue
        pool = pools[row["status"]]
        v = cand_vec[idx]
        top = float(np.max(np.stack(pool) @ v)) if pool else 0.0
        if top > DUP_COSINE:
            rejected.append({"id": row["id"], "attempt": attempt, "file": fname, "line": i, "reasons": [f"near_duplicate_output({top:.3f})"], "row": row})
            continue
        pool.append(v)
        passed_ids.add(row["id"])
        passed.append(dict(row, review_status="auto_validated", _attempt=attempt))
    return passed, rejected


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    seeds = pd.read_csv(SEED_FILE, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    originals = load_jsonl(ORIGINAL)
    files = sorted(BATCH_DIR.glob("batch_*.jsonl")) + sorted(BATCH_DIR.glob("retry_*.jsonl"))
    passed, rejected = validate_all(seeds, originals, files)
    # a seed that passed on the retry is no longer "rejected"; keep its attempt-1 reject in the file for the record
    for r in passed:
        r.pop("_attempt", None)
    write_jsonl(OUT_VALID, passed)
    write_jsonl(OUT_REJECTS, sorted(rejected, key=lambda r: (r["attempt"], r["file"], r["line"])))
    rng = random.Random(SEED)
    pool = sorted(passed, key=lambda r: r["id"])
    write_jsonl(OUT_QA, rng.sample(pool, min(100, len(pool))))
    n_in = len(passed) + len(rejected)
    final_rejected = {r["id"] for r in rejected} - {r["id"] for r in passed}
    nc = sum(r["status"] == "needs_clarification" for r in passed)
    reasons = {}
    for r in rejected:
        for x in r["reasons"]:
            k = re.sub(r"\(.*\)", "", x)
            reasons[k] = reasons.get(k, 0) + 1
    print(f"[validate] files={len(files)} rows={n_in} passed={len(passed)} rejected_rows={len(rejected)} still_failing_seeds={len(final_rejected)} "
          f"reject_rate={len(rejected) / max(n_in, 1):.1%} nc_share={nc / max(len(passed), 1):.1%} top_reasons={dict(sorted(reasons.items(), key=lambda kv: -kv[1])[:4])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
