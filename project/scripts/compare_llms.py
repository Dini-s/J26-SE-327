"""Compare LLMs as the link verifier on the SAME labelled pairs, prompt and settings.

The pairs come from the gold-labelled datasets (iTrust, eTour, CM-1): per dataset N true links and N false pairs
that stage 1 really shortlisted (hard negatives, not random). Every model gets the evidence prompt at temperature 0.
Results are written after every call, so a stopped run resumes.

    python scripts/compare_llms.py --models llama3.1-8k:latest,qwen2.5-coder-8k:latest --per-dataset 10
    python scripts/compare_llms.py --summary            # print the table from the saved results
"""

import argparse
import glob
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "results" / "llm_compare.json"
PAIRS = ROOT / "data" / "results" / "llm_compare_pairs.json"
DATASETS = ("itrust", "etour", "cm1")


def build_pairs(per_dataset: int, seed: int = 7) -> list[dict]:
    """Balanced, reproducible sample: shortlisted pairs seen in earlier runs, half true and half false."""
    rng = random.Random(seed)
    pairs = []
    for d in DATASETS:
        base = ROOT / "data" / "processed" / d
        gold = {(t["source_id"], t["target_id"]) for t in json.loads((base / "traces.json").read_text())}
        reqs = {a["id"] for a in json.loads((base / "artifacts.json").read_text()) if a["type"] == "requirement"}
        seen = set()
        for path in sorted(glob.glob(str(ROOT / "data" / "runs" / "2026*" / "events.jsonl"))):
            for line in open(path, encoding="utf-8"):
                e = json.loads(line)
                if e.get("type") == "verdict" and e["source_id"] in reqs:
                    seen.add((e["source_id"], e["target_id"]))
        pos = sorted(p for p in seen if p in gold)
        neg = sorted(p for p in seen if p not in gold)
        for label, pool in ((1, pos), (0, neg)):
            for s, t in rng.sample(pool, min(per_dataset, len(pool))):
                pairs.append({"dataset": d, "source": s, "target": t, "label": label})
    rng.shuffle(pairs)
    return pairs


def metrics(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("linked") is not None]
    tp = sum(1 for r in ok if r["linked"] and r["label"])
    fp = sum(1 for r in ok if r["linked"] and not r["label"])
    fn = sum(1 for r in ok if not r["linked"] and r["label"])
    p = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    secs = sorted(r["seconds"] for r in ok)
    return {"n": len(ok), "errors": len(rows) - len(ok), "tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 3), "recall": round(rec, 3), "f1": round(2 * p * rec / (p + rec), 3) if p + rec else 0.0,
            "median_seconds": secs[len(secs) // 2] if secs else None}


def bootstrap_f1(rows: list[dict], n: int = 1000, seed: int = 1) -> list[float]:
    rng = random.Random(seed)
    ok = [r for r in rows if r.get("linked") is not None]
    vals = sorted(metrics([rng.choice(ok) for _ in ok])["f1"] for _ in range(n)) if ok else [0, 0]
    return [vals[int(0.025 * n)], vals[int(0.975 * n) - 1]]


def summary(data: dict) -> None:
    print(f"{'model':32} {'n':>3} {'err':>3} {'prec':>6} {'recall':>6} {'F1':>6} {'F1 95% CI':>14} {'sec':>6}")
    for model, rows in data["models"].items():
        m = metrics(rows)
        lo, hi = bootstrap_f1(rows)
        print(f"{model:32} {m['n']:>3} {m['errors']:>3} {m['precision']:>6} {m['recall']:>6} {m['f1']:>6} {f'{lo}-{hi}':>14} {m['median_seconds']:>6}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--models", default="")
    ap.add_argument("--per-dataset", type=int, default=10)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--limit", type=int, help="only the first N pairs (smoke test)")
    args = ap.parse_args()
    data = json.loads(OUT.read_text()) if OUT.exists() else {"models": {}}
    if args.summary:
        return summary(data)

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from agents.traceability_agent import prompts
    from agents.traceability_agent.preprocess import llm_text
    from shared.llm.client import LLMClient
    from shared.schemas.traceability import Artifact

    if PAIRS.exists():
        pairs = json.loads(PAIRS.read_text())
    else:
        pairs = build_pairs(args.per_dataset)
        PAIRS.write_text(json.dumps(pairs, indent=1))
    arts: dict[str, dict[str, Artifact]] = {}
    for d in DATASETS:
        arts[d] = {a["id"]: Artifact(**a) for a in json.loads((ROOT / "data" / "processed" / d / "artifacts.json").read_text())}
    if args.limit:
        pairs = pairs[: args.limit]

    for model in [m for m in args.models.split(",") if m]:
        rows = data["models"].setdefault(model, [])
        done = {(r["dataset"], r["source"], r["target"]) for r in rows}
        llm = LLMClient(model=model, system_prompt=prompts.EVIDENCE_SYSTEM_PROMPT, response_mode="evidence")
        for n, p in enumerate(pairs, 1):
            if (p["dataset"], p["source"], p["target"]) in done:
                continue
            req, tgt = arts[p["dataset"]][p["source"]], arts[p["dataset"]][p["target"]]
            t0 = time.time()
            try:
                v = llm.verify_link(req.model_copy(update={"text": llm_text(req)}), tgt.model_copy(update={"text": llm_text(tgt)}))
                row = {"linked": bool(v["is_linked"]) and float(v["confidence"]) >= 0.5, "confidence": v["confidence"]}
            except Exception as exc:
                row = {"linked": None, "error": f"{type(exc).__name__}: {exc}"[:200]}
            rows.append({**p, **row, "seconds": round(time.time() - t0, 1)})
            OUT.write_text(json.dumps(data, indent=1))
            print(f"{model} {n}/{len(pairs)} label={p['label']} linked={row['linked']} ({rows[-1]['seconds']} s)", flush=True)
    summary(data)


if __name__ == "__main__":
    main()
