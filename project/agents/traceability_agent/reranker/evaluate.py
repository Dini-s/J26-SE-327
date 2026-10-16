"""Does the reranker help? Precision / recall / F1 / MRR at top-k per test dataset (standalone: numpy only).

    # stage-1 retrieval alone
    python evaluate.py --data data/reranker
    # stage-1 versus a trained reranker (scores written by train.py predict)
    python evaluate.py --data data/reranker --scores data/reranker/model_codebert/test_scores.jsonl

For every requirement the candidates are the stage-1 top-K (see meta.json). "Top-k" then means: the k candidates
the method ranks highest, which is what would be sent to the LLM. Recall is measured against ALL true links of the
dataset, so a true link that stage 1 never found counts as missed by every method.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

KS = (1, 3, 5, 10)


def load(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def metrics(rows: list[dict[str, Any]], total_true: int, key: str, ks: tuple[int, ...] = KS) -> dict[str, float]:
    """Top-k precision / recall / F1 and MRR; ``key`` is the row field to rank by (higher is better)."""
    by_req: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_req[r["source_id"]].append(r)
    out: dict[str, float] = {}
    ranked = {s: sorted(v, key=lambda r: (-r[key], r["stage1_rank"])) for s, v in by_req.items()}
    for k in ks:
        picked = [r for v in ranked.values() for r in v[:k]]
        tp = sum(r["label"] for r in picked)
        precision = tp / len(picked) if picked else 0.0
        recall = tp / total_true if total_true else 0.0
        out[f"P@{k}"], out[f"R@{k}"] = precision, recall
        out[f"F1@{k}"] = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    rr = []
    for v in ranked.values():
        if any(r["label"] for r in v):
            rr.append(next(1 / i for i, r in enumerate(v, start=1) if r["label"]))
    out["MRR"] = sum(rr) / len(rr) if rr else 0.0
    return out


def add_fusion(rows: list[dict[str, Any]], weights: tuple[float, ...]) -> None:
    """Add ``fuse_<w>`` = z(stage-1 score) + w * z(reranker score), z-scored over each requirement's candidates.

    Tests whether the reranker adds information on top of stage 1 even when it is worse on its own.
    """
    by_req: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_req[(r["dataset"], r["source_id"])].append(r)

    def z(values: list[float]) -> list[float]:
        mean = sum(values) / len(values)
        std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5 or 1.0
        return [(v - mean) / std for v in values]

    for group in by_req.values():
        zs, zr = z([r["stage1_score"] for r in group]), z([r["score"] for r in group])
        for r, a, b in zip(group, zs, zr):
            for w in weights:
                r[f"fuse_{w}"] = a + w * b


def per_requirement(rows: list[dict[str, Any]], key: str) -> dict[tuple[str, str], tuple[float, float, float]]:
    """For each requirement: (reciprocal rank of the first true link, true links in top-3, true links in top-5)."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[(r["dataset"], r["source_id"])].append(r)
    out = {}
    for g, v in groups.items():
        v = sorted(v, key=lambda r: (-r[key], r["stage1_rank"]))
        rr = next((1 / i for i, r in enumerate(v, start=1) if r["label"]), 0.0)
        out[g] = (rr, float(sum(r["label"] for r in v[:3])), float(sum(r["label"] for r in v[:5])))
    return out


def bootstrap(rows: list[dict[str, Any]], key_a: str, key_b: str, n: int = 2000, seed: int = 13) -> dict[str, dict[str, tuple[float, float, float]]]:
    """Paired bootstrap over requirements: mean difference (b - a) and 95% interval of MRR, hits@3 and hits@5 per requirement.

    "hits@k per requirement" is the number of true links in the top-k, i.e. recall@k up to a constant factor.
    An interval that contains 0 means the difference is not distinguishable from noise with this many requirements.
    """
    import random

    a, b = per_requirement(rows, key_a), per_requirement(rows, key_b)
    rng = random.Random(seed)
    result: dict[str, dict[str, tuple[float, float, float]]] = {}
    groups = {"ALL": list(a)} | {d: [g for g in a if g[0] == d] for d in sorted({g[0] for g in a})}
    for name, reqs in groups.items():
        diffs = [[], [], []]
        for _ in range(n):
            sample = [rng.choice(reqs) for _ in reqs]
            for i in range(3):
                diffs[i].append(sum(b[g][i] - a[g][i] for g in sample) / len(sample))
        result[name] = {}
        for label, d in zip(("MRR", "hits@3", "hits@5"), diffs):
            d.sort()
            result[name][label] = (sum(d) / n, d[int(0.025 * n)], d[int(0.975 * n)])
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default="data/reranker")
    parser.add_argument("--scores", help="test_scores.jsonl from train.py predict; omit to evaluate stage-1 only")
    parser.add_argument("--bootstrap", action="store_true", help="paired bootstrap of fused-vs-stage-1 differences over requirements")
    parser.add_argument("--versus", help="a second test_scores.jsonl; with --bootstrap, also tests (--scores model fused) minus (--versus model fused)")
    parser.add_argument("--fuse", default="0.5,1,2", help="weights w for fused = z(stage1) + w*z(reranker); empty to skip")
    args = parser.parse_args(argv)
    meta = json.loads((Path(args.data) / "meta.json").read_text(encoding="utf-8"))
    rows = load(Path(args.scores) if args.scores else Path(args.data) / "test_candidates.jsonl")
    for r in rows:
        r.setdefault("stage1", r["stage1_score"])
    weights = tuple(float(w) for w in args.fuse.split(",") if w.strip()) if args.scores else ()
    if weights:
        add_fusion(rows, weights)
    report: dict[str, Any] = {}
    for dataset in sorted({r["dataset"] for r in rows}):
        sub = [r for r in rows if r["dataset"] == dataset]
        total = meta["datasets"][dataset]["true_links"]
        report[dataset] = {"stage1": metrics(sub, total, "stage1")}
        if args.scores:
            report[dataset]["reranker"] = metrics(sub, total, "score")
            for w in weights:
                report[dataset][f"fuse_{w}"] = metrics(sub, total, f"fuse_{w}")
    header = f"{'dataset':8} {'method':9} " + " ".join(f"{m:>6}" for k in KS for m in (f"P@{k}", f"R@{k}", f"F1@{k}")) + "    MRR"
    print(header)
    for dataset, methods in report.items():
        for name, m in methods.items():
            print(f"{dataset:8} {name:9} " + " ".join(f"{m[f'{x}@{k}']:6.3f}" for k in KS for x in ("P", "R", "F1")) + f"  {m['MRR']:.3f}")
    if args.bootstrap and weights:
        print("\npaired bootstrap over requirements: difference (fused - stage1), mean [95% interval]; * = interval excludes 0")
        for w in weights:
            for name, stats in bootstrap(rows, "stage1", f"fuse_{w}").items():
                cells = "  ".join(f"{m} {v[0]:+.3f} [{v[1]:+.3f},{v[2]:+.3f}]{'*' if v[1] > 0 or v[2] < 0 else ' '}" for m, v in stats.items())
                print(f"fuse_{w:<4} {name:7} {cells}")
    if args.bootstrap and args.versus and weights:
        other = {(r["dataset"], r["source_id"], r["target_id"]): r["score"] for r in load(Path(args.versus))}
        twin = [{**r, "score": other[(r["dataset"], r["source_id"], r["target_id"])]} for r in rows]
        add_fusion(twin, weights)
        for r, t in zip(rows, twin):
            for w in weights:
                r[f"versus_{w}"] = t[f"fuse_{w}"]
        print(f"\npaired bootstrap: ({args.scores}) fused minus ({args.versus}) fused; * = interval excludes 0")
        for w in weights:
            for name, stats in bootstrap(rows, f"versus_{w}", f"fuse_{w}").items():
                cells = "  ".join(f"{m} {v[0]:+.3f} [{v[1]:+.3f},{v[2]:+.3f}]{'*' if v[1] > 0 or v[2] < 0 else ' '}" for m, v in stats.items())
                print(f"fuse_{w:<4} {name:7} {cells}")
    target = Path(args.scores).parent / "evaluation.json" if args.scores else Path(args.data) / "evaluation_stage1.json"
    target.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"saved {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
