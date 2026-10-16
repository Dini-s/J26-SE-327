"""Learning curve: does a reranker trained on MORE PROJECTS do better on unseen projects? (standalone; run it on Colab)

Question behind it: before collecting more training data, is there any sign that more (and more varied) projects help?
The reranker is trained on 1, 2, 3 and 4 of the training projects (added one by one, in two different orders to see how
much the order matters) and every model is tested on the same unseen projects (LibEST, CM-1, EBT).

    python learning_curve.py --data data/reranker --base cross-encoder/ms-marco-MiniLM-L-6-v2 --out curve_minilm
    python learning_curve.py --data data/reranker --base microsoft/codebert-base --out curve_codebert

Each finished run is saved in ``<out>/curve.json``; if the session stops, run the same command again and it continues.

Reading the result: the columns show, pooled over the 115 unseen requirements, (a) the MRR of the reranker alone and
(b) how many more true links per requirement land in the top 5 when it is fused with stage 1 (mean and 95% interval,
``train.py`` / ``evaluate.py`` use the same definitions as the main analysis). If these numbers rise as projects are
added, more data is likely to help; if they stay flat or noisy, it will not.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import evaluate as ev
import train as T

ORDERS = {
    "A": ["iTrust", "eTour", "SMOS", "eANCI"],   # large and diverse first
    "B": ["eANCI", "SMOS", "eTour", "iTrust"],   # the reverse order
}


def run_one(name: str, datasets: list[str], args: argparse.Namespace, meta: dict[str, Any]) -> dict[str, Any]:
    out = Path(args.out) / name
    T.train(argparse.Namespace(data=args.data, base=args.base, out=str(out), epochs=args.epochs, batch=args.batch, lr=args.lr,
                               max_length=args.max_length, max_steps=args.max_steps, seed=args.seed, train_datasets=",".join(datasets)))
    T.predict(argparse.Namespace(data=args.data, model=str(out), out=None, max_length=args.max_length))
    rows = ev.load(out / "test_scores.jsonl")
    for r in rows:
        r["stage1"] = r["stage1_score"]
    ev.add_fusion(rows, (args.w,))
    key = f"fuse_{args.w}"
    alone = ev.per_requirement(rows, "score")
    mrr_alone = sum(v[0] for v in alone.values()) / len(alone)
    boot = ev.bootstrap(rows, "stage1", key)["ALL"]
    per_ds = {}
    for ds in sorted({r["dataset"] for r in rows}):
        sub = [r for r in rows if r["dataset"] == ds]
        a = ev.per_requirement(sub, "score")
        per_ds[ds] = {"mrr_alone": round(sum(v[0] for v in a.values()) / len(a), 3),
                      "hits5_fused_minus_stage1": round(ev.bootstrap(sub, "stage1", key)["ALL"]["hits@5"][0], 3)}
    train_info = json.loads((out / "training.json").read_text(encoding="utf-8"))
    return {"run": name, "datasets": datasets, "n_projects": len(datasets), "best_valid_auc": train_info["best_valid_auc"],
            "mrr_alone": round(mrr_alone, 3), "fused_hits5": [round(x, 3) for x in boot["hits@5"]],
            "fused_mrr": [round(x, 3) for x in boot["MRR"]], "per_dataset": per_ds}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default="data/reranker")
    parser.add_argument("--base", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--out", required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--max-steps", type=int, default=0, help="smoke test only")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--w", type=float, default=0.5, help="fusion weight")
    parser.add_argument("--orders", default="A,B", help="which orders to run (A, B)")
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "curve.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"base": args.base, "w": args.w, "runs": {}}
    meta = json.loads((Path(args.data) / "meta.json").read_text(encoding="utf-8"))

    plan = {}
    for o in args.orders.split(","):
        for k in range(1, 5):
            datasets = ORDERS[o][:k]
            if k == 4 and "4_all" in plan:       # the full training set is identical in both orders
                continue
            plan[f"{o}{k}" if k < 4 else "4_all"] = datasets
    for name, datasets in plan.items():
        if name in state["runs"]:
            print("already done:", name)
            continue
        print(f"\n=== run {name}: train on {datasets}", flush=True)
        state["runs"][name] = run_one(name, datasets, args, meta)
        state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")

    print(f"\nLearning curve ({args.base}), tested on LibEST + CM-1 + EBT, fusion w={args.w}")
    print(f"{'run':6} {'projects':>8}  {'trained on':34} {'valid AUC':>9} {'MRR alone':>9}  {'fused: more true links in top-5 (95% interval)':>46}")
    for name, r in sorted(state["runs"].items(), key=lambda kv: (kv[1]["n_projects"], kv[0])):
        m, lo, hi = r["fused_hits5"]
        print(f"{name:6} {r['n_projects']:>8}  {'+'.join(r['datasets']):34} {r['best_valid_auc']:>9.3f} {r['mrr_alone']:>9.3f}  {m:+.3f} [{lo:+.3f}, {hi:+.3f}]{' *' if lo > 0 or hi < 0 else ''}")
    print("(* = interval excludes 0; stage-1 alone has MRR 0.7 to 0.9 on these datasets; see docs for the main analysis)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
