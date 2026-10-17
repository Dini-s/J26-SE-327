"""Confidence calibration and abstain mode for LLM verdicts.

The LLM's "confidence 0.8" is not a probability: a link it calls 0.8 may be right far less (or more) often. This
module learns, from verdicts that have a known answer (gold links), how often each confidence level is really
correct (isotonic regression), then offers an *abstain* policy: accept a link only when its calibrated
probability is high, drop it when it is low, and send the middle band to a human ("needs review") instead of
guessing. Everything is measured with cross-validation so the numbers are not fitted-and-tested on the same links.

    python -m agents.traceability_agent.calibration --out data/results/calibration.json
"""

import argparse
import glob
import json
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ("itrust", "etour", "cm1")


def raw_score(is_linked: bool, confidence: float) -> float:
    """One number per verdict: the LLM's confidence if it said "linked", else 0."""
    return float(confidence) if is_linked else 0.0


def load_labelled_verdicts(runs: str = str(ROOT / "data" / "runs"), processed: Path = ROOT / "data" / "processed") -> list[dict[str, Any]]:
    """LLM verdicts from stored runs whose requirement belongs to a gold-labelled dataset (last verdict per pair wins)."""
    gold: dict[str, set[tuple[str, str]]] = {}
    reqs: dict[str, set[str]] = {}
    for d in DATASETS:
        gold[d] = {(t["source_id"], t["target_id"]) for t in json.loads((processed / d / "traces.json").read_text(encoding="utf-8"))}
        arts = json.loads((processed / d / "artifacts.json").read_text(encoding="utf-8"))
        reqs[d] = {a["id"] for a in arts if a["type"] == "requirement"}
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in sorted(glob.glob(f"{runs}/2026*/events.jsonl")):
        for line in open(path, encoding="utf-8"):
            e = json.loads(line)
            if e.get("type") != "verdict":
                continue
            for d in DATASETS:
                if e["source_id"] in reqs[d]:
                    out[(d, e["source_id"], e["target_id"])] = {
                        "dataset": d, "score": raw_score(e["is_linked"], e["confidence"]),
                        "label": int((e["source_id"], e["target_id"]) in gold[d]),
                    }
                    break
    return list(out.values())


def ece(scores: np.ndarray, labels: np.ndarray, bins: int = 5) -> float:
    """Expected calibration error: average gap between stated probability and real hit rate (lower is better)."""
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (scores >= lo) & ((scores < hi) if hi < 1 else (scores <= hi))
        if m.any():
            total += m.mean() * abs(scores[m].mean() - labels[m].mean())
    return float(total)


def abstain(prob: float, low: float, high: float) -> str:
    """accept / reject / review for one calibrated probability."""
    return "accept" if prob >= high else "reject" if prob < low else "review"


def cross_validated(rows: Sequence[dict[str, Any]], folds: int = 5, seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Out-of-fold calibrated probabilities: ``(raw, calibrated, label)``."""
    s = np.array([r["score"] for r in rows])
    y = np.array([r["label"] for r in rows])
    cal = np.zeros(len(rows))
    idx = np.random.default_rng(seed).permutation(len(rows))
    for k in range(folds):
        test = idx[k::folds]
        train = np.setdiff1d(idx, test)
        cal[test] = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(s[train], y[train]).predict(s[test])
    return s, cal, y


def policy_table(cal: np.ndarray, y: np.ndarray, highs: Sequence[float] = (0.5, 0.6, 0.7, 0.8)) -> list[dict[str, Any]]:
    """For each accept-threshold: how many links are accepted, their precision, and how many true links are kept."""
    rows = []
    for h in highs:
        keep = cal >= h
        n = int(keep.sum())
        tp = int(y[keep].sum())
        rows.append({"accept_if_calibrated>=": h, "accepted": n, "precision": round(tp / n, 3) if n else None,
                     "recall": round(tp / y.sum(), 3) if y.sum() else None})
    return rows


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="data/results/calibration.json")
    args = parser.parse_args(argv)
    rows = load_labelled_verdicts()
    s, cal, y = cross_validated(rows)
    raw_table = policy_table(s, y, (0.5, 0.7, 0.8, 0.9))
    res = {
        "n_verdicts": len(rows), "n_true": int(y.sum()),
        "ece_raw": round(ece(s, y), 3), "ece_calibrated": round(ece(cal, y), 3),
        "raw_confidence_threshold": raw_table,
        "calibrated_threshold": policy_table(cal, y),
        "reliability_raw": [{"conf": c, "n": int((s == c).sum()), "correct": round(float(y[s == c].mean()), 3)} for c in sorted(set(s)) if (s == c).sum() >= 5],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
