"""Print the verifier-LLM comparison as one terminal table (for a screenshot / the viva).

Reads the saved answers in data/results (llm_compare.json = eTour+iTrust+CM-1, llm_compare_petclinic.json = PetClinic),
prints precision / recall / F1 per test set and pooled over all pairs, and names the model with the best pooled F1.

    .venv/bin/python scripts/show_llm_results.py
"""
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[1] / "data" / "results"
SETS = {"eTour + iTrust + CM-1": "llm_compare.json", "PetClinic": "llm_compare_petclinic.json"}


def prf(rows):
    linked = lambda r: bool(r.get("linked"))  # noqa: E731  (no usable answer counts as "not linked")
    tp = sum(r["label"] == 1 and linked(r) for r in rows)
    fp = sum(r["label"] == 0 and linked(r) for r in rows)
    fn = sum(r["label"] == 1 and not linked(r) for r in rows)
    p, rc = tp / max(1, tp + fp), tp / max(1, tp + fn)
    secs = [r["seconds"] for r in rows if r.get("seconds") is not None]
    return {"n": len(rows), "tp": tp, "fp": fp, "fn": fn, "P": p, "R": rc, "F1": 2 * p * rc / max(1e-9, p + rc),
            "sec": sum(secs) / len(secs) if secs else 0, "none": sum(r.get("linked") is None for r in rows)}


def line(name, m):
    return (f"  {name:16s} P={m['P']:.2f}  R={m['R']:.2f}  F1={m['F1']:.2f}   TP={m['tp']:2d} FP={m['fp']:2d} FN={m['fn']:2d}"
            f"   {m['sec']:3.0f}s/answer   no-answer={m['none']}")


def main():
    pooled = {}
    for title, file in SETS.items():
        path = RESULTS / file
        if not path.exists():
            continue
        models = json.loads(path.read_text(encoding="utf-8"))["models"]
        print(f"\n{title}  ({len(next(iter(models.values())))} pairs: half true links, half not)")
        for name, rows in models.items():
            short = name.split(":")[0].replace("-8k", "")
            print(line(short, prf(rows)))
            pooled.setdefault(short, []).extend(rows)
    print(f"\nALL TEST SETS POOLED  ({len(next(iter(pooled.values())))} pairs)")
    table = {k: prf(v) for k, v in pooled.items()}
    for k, m in table.items():
        print(line(k, m))
    best = max(table, key=lambda k: table[k]["F1"])
    print(f"\nBest pooled F1: {best} ({table[best]['F1']:.2f}).  Targets: precision >= 0.90, recall >= 0.80.")


if __name__ == "__main__":
    main()
