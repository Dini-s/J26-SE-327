"""Batching helper for the Component 1 SFT dataset growth (Claude Code is the generator; no model is called here).

    python sft_batches.py plan                        # number of batches and which already exist
    python sft_batches.py show N                      # print the 50 seeds of batch N as `n | source | text`
    python sft_batches.py assemble N compact.jsonl    # compact generator output -> processed/llm_sft/synthetic_batches/batch_NNN.jsonl
    python sft_batches.py show-retry K                # print the seeds rejected once (from rejects.jsonl, attempt 1), batch K of 50
    python sft_batches.py assemble-retry K compact.jsonl

Seeds come from processed/tasks/synthetic_seed_inputs_batch3.csv in a fixed hash order (seed 327), 50 per batch. The generator writes one compact
JSON line per seed (`n` = position in the batch):
    {"n": 3, "s": "ok", "us": "As a ..., I want ..., so that ....", "tt": "...", "ac": ["Given ..., when ..., then ...", ...], "r": "..."}
    {"n": 4, "s": "nc", "q": ["question?", ...], "r": "..."}
`assemble` adds the seed metadata and writes the full record in the schema of synthetic_pairs_all_550.jsonl. An existing batch file is never overwritten.
"""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[2]
PROCESSED = PROJECT / "data" / "component1" / "processed"
TASKS = PROCESSED / "tasks"
SFT = PROCESSED / "llm_sft"
BATCH_DIR = SFT / "synthetic_batches"
SEED_FILE = TASKS / "synthetic_seed_inputs_batch3.csv"
RAW_FILE = TASKS / "synthetic_seed_inputs_batch3_raw.csv"
REJECTS = SFT / "rejects.jsonl"
GENERATOR = "claude-sonnet-5.5 (hand-written)"
BATCH_SIZE = 50
SEED = 327


def h(*parts):
    return hashlib.sha256("|".join(str(p) for p in (SEED,) + parts).encode("utf-8")).hexdigest()


def read(path):
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def ordered_seeds():
    seeds = read(SEED_FILE)
    raw = dict(zip(*[read(RAW_FILE)[c] for c in ("id", "requirement_text_raw")]))
    seeds = seeds.assign(_o=seeds.id.map(lambda i: h("sft_order", i))).sort_values("_o", kind="stable").drop(columns="_o").reset_index(drop=True)
    seeds["raw"] = seeds.id.map(lambda i: raw.get(i, ""))
    return seeds


def n_batches(seeds):
    return -(-len(seeds) // BATCH_SIZE)


def batch_rows(seeds, k):
    return seeds.iloc[(k - 1) * BATCH_SIZE:k * BATCH_SIZE].reset_index(drop=True)


def retry_seeds(seeds):
    """Seeds whose first attempt was rejected and that have not been retried yet."""
    if not REJECTS.exists():
        return seeds.iloc[0:0], set()
    rej = [json.loads(line) for line in REJECTS.read_text(encoding="utf-8").splitlines() if line.strip()]
    first = {r["id"] for r in rej if r.get("attempt") == 1}
    return seeds[seeds.id.isin(first)].reset_index(drop=True), {r["id"] for r in rej if r.get("attempt") == 2}


def full_record(seed, c):
    base = {"id": seed["id"], "source": seed["source"], "requirement_text": seed["requirement_text"]}
    if seed["raw"]:
        base["requirement_text_raw"] = seed["raw"]
    base.update({"synthetic": True, "generator": GENERATOR, "review_status": "unreviewed"})
    if c["s"] == "ok":
        base.update({"status": "ok", "user_story": c["us"], "technical_task": c["tt"], "acceptance_criteria": c["ac"], "rationale": c["r"]})
    elif c["s"] == "nc":
        base.update({"status": "needs_clarification", "user_story": None, "technical_task": None, "acceptance_criteria": [], "rationale": c["r"],
                     "clarification_questions": c["q"]})
    else:
        raise SystemExit(f"unknown status {c['s']!r} for n={c['n']}")
    base["reviewer_note"] = None
    return base


def assemble(rows, compact_path, out_path):
    out_path = Path(out_path)
    if out_path.exists():
        raise SystemExit(f"STOP: {out_path} already exists; batches are never overwritten.")
    compact = [json.loads(line) for line in Path(compact_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    by_n = {c["n"]: c for c in compact}
    if len(by_n) != len(compact) or sorted(by_n) != list(range(1, len(rows) + 1)):
        raise SystemExit(f"STOP: compact file must contain n=1..{len(rows)} exactly once (got {sorted(by_n)[:5]}... {len(compact)} lines)")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for i, seed in rows.iterrows():
            f.write(json.dumps(full_record(seed, by_n[i + 1]), ensure_ascii=False) + "\n")
    n_nc = sum(c["s"] == "nc" for c in compact)
    print(f"wrote {out_path.name}: {len(rows)} rows, {n_nc} needs_clarification")


def show(rows):
    for i, r in rows.iterrows():
        print(f"{i + 1} | {r['source']} | {r['requirement_text']}")


def main(argv):
    seeds = ordered_seeds()
    cmd = argv[1]
    if cmd == "plan":
        total = n_batches(seeds)
        existing = sorted(p.name for p in BATCH_DIR.glob("batch_*.jsonl")) if BATCH_DIR.exists() else []
        print(f"{len(seeds)} seeds -> {total} batches of {BATCH_SIZE}; existing: {len(existing)}; next missing: "
              f"{next((k for k in range(1, total + 1) if not (BATCH_DIR / f'batch_{k:03d}.jsonl').exists()), None)}")
    elif cmd == "show":
        show(batch_rows(seeds, int(argv[2])))
    elif cmd == "assemble":
        k = int(argv[2])
        assemble(batch_rows(seeds, k), argv[3], BATCH_DIR / f"batch_{k:03d}.jsonl")
    elif cmd in ("show-retry", "assemble-retry"):
        rs, _ = retry_seeds(seeds)
        k = int(argv[2])
        rows = rs.iloc[(k - 1) * BATCH_SIZE:k * BATCH_SIZE].reset_index(drop=True)
        if cmd == "show-retry":
            print(f"{len(rs)} seeds to retry; retry batch {k} has {len(rows)}")
            show(rows)
        else:
            assemble(rows, argv[3], BATCH_DIR / f"retry_{k:03d}.jsonl")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
