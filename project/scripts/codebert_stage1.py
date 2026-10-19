"""Does a pre-trained CodeBERT (no fine-tuning) help stage 1 as a third similarity signal?

Stage 1 today fuses TF-IDF and MiniLM (z-score). This adds CodeBERT's mean-pooled embeddings as a third signal and
measures recall@k against the gold links of iTrust, eTour and CM-1. TF-IDF and MiniLM matrices come from the cache
written by agents/traceability_agent/ranker.py, so only CodeBERT is computed here. Nothing is trained.

    python scripts/codebert_stage1.py            # CPU is fine for these three datasets, slower than a GPU
"""

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.traceability_agent.config import CHUNK_WORDS  # noqa: E402
from agents.traceability_agent.preprocess import retrieval_text  # noqa: E402
from agents.traceability_agent.ranker import load_project, recall_at  # noqa: E402
from agents.traceability_agent.retrieval import _best_chunk, _chunk_targets, cosine_matrix, zscore_fuse  # noqa: E402

DATASETS = ["itrust", "etour", "cm1"]
CACHE = ROOT / "data" / "cache" / "stage1"
OUT = ROOT / "data" / "results" / "codebert_stage1.json"
MODEL = "microsoft/codebert-base"
MAX_TOKENS = 256


class CodeBert:
    """Mean-pooled CodeBERT vectors; same ``embed_batch`` interface as the MiniLM embedder."""

    def __init__(self) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(MODEL)
        self.model = AutoModel.from_pretrained(MODEL).eval()

    def embed_batch(self, texts: list[str], batch: int = 16) -> np.ndarray:
        out = []
        with self.torch.no_grad():
            for i in range(0, len(texts), batch):
                enc = self.tok(texts[i : i + batch], truncation=True, max_length=MAX_TOKENS, padding=True, return_tensors="pt")
                hidden = self.model(**enc).last_hidden_state
                mask = enc["attention_mask"].unsqueeze(-1).float()
                out.append(((hidden * mask).sum(1) / mask.sum(1)).numpy())
        return np.vstack(out)


def codebert_matrix(reqs: list, code: list, embedder: Any) -> np.ndarray:
    """Cosine similarity, requirement x code, using each code file's best 60-word chunk (as stage 1 does for MiniLM)."""
    chunks, starts = _chunk_targets(code, retrieval_text, CHUNK_WORDS)
    q = embedder.embed_batch([retrieval_text(r) for r in reqs])
    c = embedder.embed_batch(chunks)
    return _best_chunk(cosine_matrix(q, c), starts)


def scores_by_req(matrix: np.ndarray) -> dict[int, list[tuple[float, int]]]:
    return {i: [(float(matrix[i, j]), j) for j in range(matrix.shape[1])] for i in range(matrix.shape[0])}


def main() -> None:
    embedder = None
    rows: dict[str, Any] = {}
    for name in DATASETS:
        reqs, code, gold = load_project(name)
        cached = np.load(CACHE / f"{name}.npz")
        tfidf, emb = cached["tfidf"], cached["emb"]
        cb_path = CACHE / f"{name}_codebert.npy"
        if cb_path.exists():
            cb = np.load(cb_path)
        else:
            if embedder is None:
                embedder = CodeBert()
            cb = codebert_matrix(reqs, code, embedder)
            np.save(cb_path, cb)
        combos = {
            "hybrid (current)": zscore_fuse([tfidf, emb]),
            "codebert alone": cb,
            "hybrid + codebert": zscore_fuse([tfidf, emb, cb]),
        }
        rows[name] = {}
        for label, m in combos.items():
            s = scores_by_req(m)
            rows[name][label] = {str(k): round(recall_at(s, gold, k), 3) for k in (5, 10, 20)}
        print(name, json.dumps(rows[name]), flush=True)
    macro = {label: {str(k): round(float(np.mean([rows[d][label][str(k)] for d in DATASETS])), 3) for k in (5, 10, 20)}
             for label in rows[DATASETS[0]]}
    OUT.write_text(json.dumps({"model": MODEL, "per_dataset": rows, "macro": macro}, indent=1), encoding="utf-8")
    print("macro recall", json.dumps(macro, indent=1))


if __name__ == "__main__":
    main()
