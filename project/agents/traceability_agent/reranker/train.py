"""Fine-tune a cross-encoder reranker on the pair files from ``data.py`` (standalone: no project imports).

It runs on a laptop or on Google Colab (T4). Needs: torch, transformers, scikit-learn, numpy.

    # train (writes the best model to <out>), then score the test candidates
    python train.py train --data data/reranker --base microsoft/codebert-base --out data/reranker/model_codebert
    python train.py predict --data data/reranker --model data/reranker/model_codebert

    # the MiniLM comparison: same command with another base
    python train.py train --data data/reranker --base cross-encoder/ms-marco-MiniLM-L-6-v2 --out data/reranker/model_minilm

``predict`` writes ``<model>/test_scores.jsonl`` (test_candidates.jsonl rows with an added ``score``), which
``evaluate.py`` turns into precision / recall / F1 / MRR at top-k, next to the stage-1 baseline.
"""

import argparse
import functools
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

QUERY_MAX_TOKENS = 160  # long requirements are cut, so the code part always keeps room (max_length is 512 for CodeBERT)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def pick_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def encode(tokenizer: Any, rows: list[dict[str, Any]], max_length: int) -> dict[str, Any]:
    """Tokenise (query, doc) pairs; the query is cut to QUERY_MAX_TOKENS first, then the doc fills the rest."""
    queries = []
    for r in rows:
        ids = tokenizer(r["query"], add_special_tokens=False, truncation=True, max_length=QUERY_MAX_TOKENS)["input_ids"]
        queries.append(tokenizer.decode(ids))
    return tokenizer(queries, [r["doc"] for r in rows], truncation="only_second", max_length=max_length, padding=True, return_tensors="pt")


@functools.lru_cache(maxsize=None)
def _torch() -> Any:
    import torch

    return torch


def score_rows(model: Any, tokenizer: Any, rows: list[dict[str, Any]], device: str, max_length: int, batch: int = 32) -> np.ndarray:
    torch = _torch()
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(rows), batch):
            enc = {k: v.to(device) for k, v in encode(tokenizer, rows[i : i + batch], max_length).items()}
            out.append(model(**enc).logits.squeeze(-1).float().cpu().numpy())
    return np.concatenate(out) if out else np.array([])


def train(args: argparse.Namespace) -> None:
    from sklearn.metrics import roc_auc_score
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

    torch = _torch()
    random.seed(args.seed), np.random.seed(args.seed), torch.manual_seed(args.seed)
    data = Path(args.data)
    train_rows, valid_rows = read_jsonl(data / "train.jsonl"), read_jsonl(data / "valid.jsonl")
    device = pick_device()
    print(f"device={device}  base={args.base}  train={len(train_rows)} valid={len(valid_rows)}  positives={sum(r['label'] for r in train_rows)}")
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    model = AutoModelForSequenceClassification.from_pretrained(args.base, num_labels=1).to(device)
    optimiser = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    steps_per_epoch = (len(train_rows) + args.batch - 1) // args.batch
    total = steps_per_epoch * args.epochs if not args.max_steps else args.max_steps
    schedule = get_linear_schedule_with_warmup(optimiser, int(0.1 * total), total)
    loss_fn = torch.nn.BCEWithLogitsLoss()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    best, step, history = -1.0, 0, []
    for epoch in range(1, args.epochs + 1):
        model.train()
        random.shuffle(train_rows)
        started, running = time.time(), 0.0
        for i in range(0, len(train_rows), args.batch):
            chunk = train_rows[i : i + args.batch]
            enc = {k: v.to(device) for k, v in encode(tokenizer, chunk, args.max_length).items()}
            labels = torch.tensor([float(r["label"]) for r in chunk], device=device)
            loss = loss_fn(model(**enc).logits.squeeze(-1), labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimiser.step(), schedule.step(), optimiser.zero_grad()
            running += loss.item()
            step += 1
            if args.max_steps and step >= args.max_steps:
                break
        scores = score_rows(model, tokenizer, valid_rows, device, args.max_length)
        auc = float(roc_auc_score([r["label"] for r in valid_rows], scores)) if len({r["label"] for r in valid_rows}) > 1 else float("nan")
        history.append({"epoch": epoch, "train_loss": round(running / max(1, min(steps_per_epoch, step)), 4), "valid_auc": round(auc, 4), "seconds": round(time.time() - started)})
        print(history[-1])
        if auc > best:
            best = auc
            model.save_pretrained(out)
            tokenizer.save_pretrained(out)
        if args.max_steps and step >= args.max_steps:
            break
    (out / "training.json").write_text(json.dumps({"args": {k: v for k, v in vars(args).items() if k != "func"}, "history": history, "best_valid_auc": best}, indent=1), encoding="utf-8")
    print(f"best valid AUC {best:.4f}; model saved to {out}")


def predict(args: argparse.Namespace) -> None:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = pick_device()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(args.model).to(device)
    rows = read_jsonl(Path(args.data) / "test_candidates.jsonl")
    scores = score_rows(model, tokenizer, rows, device, args.max_length)
    target = Path(args.out) if args.out else Path(args.model) / "test_scores.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        for r, s in zip(rows, scores):
            fh.write(json.dumps({**r, "score": float(s)}, ensure_ascii=False) + "\n")
    print(f"scored {len(rows)} candidates -> {target}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("train")
    t.add_argument("--data", default="data/reranker")
    t.add_argument("--base", default="microsoft/codebert-base")
    t.add_argument("--out", required=True)
    t.add_argument("--epochs", type=int, default=3)
    t.add_argument("--batch", type=int, default=16)
    t.add_argument("--lr", type=float, default=2e-5)
    t.add_argument("--max-length", type=int, default=512)
    t.add_argument("--max-steps", type=int, default=0, help="stop after this many steps (smoke test)")
    t.add_argument("--seed", type=int, default=13)
    t.set_defaults(func=train)
    p = sub.add_parser("predict")
    p.add_argument("--data", default="data/reranker")
    p.add_argument("--model", required=True, help="a saved model folder, or a Hugging Face name (then pass --out)")
    p.add_argument("--out", help="where to write the scores (default: <model>/test_scores.jsonl)")
    p.add_argument("--max-length", type=int, default=512)
    p.set_defaults(func=predict)
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
