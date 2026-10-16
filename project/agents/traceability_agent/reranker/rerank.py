"""Optional stage 1.5: a cross-encoder re-orders the stage-1 candidates before the LLM sees them.

Stage 1 (TF-IDF + embeddings) ranks cheaply; the cross-encoder reads each (requirement, code) pair together and gives a
second opinion. The two are combined per requirement as ``z(stage-1 score) + weight * z(cross-encoder score)`` (z-scored over
that requirement's candidate pool) and only the best ``keep`` go on to the LLM.

On the held-out datasets (LibEST, CM-1, EBT) this put on average about 0.14-0.16 more true links into the top 5 per requirement
than stage 1 alone (95% interval above zero for the pooled data, see reranker/evaluate.py --bootstrap). It does NOT
improve the order of the top 1-3 reliably, and it has not been measured end to end with the LLM.
"""

from collections import OrderedDict
from typing import Any, Callable, Optional, Sequence

import numpy as np

from agents.traceability_agent.reranker.data import Focus
from agents.traceability_agent.retrieval import Candidate

PairScorer = Callable[[Sequence[tuple[str, str]]], Sequence[float]]


def _z(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    std = arr.std()
    return (arr - arr.mean()) / (std if std > 0 else 1.0)


class CrossEncoderReranker:
    """Re-orders candidates with a cross-encoder fused with the stage-1 score."""

    def __init__(self, model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", weight: float = 0.5, max_length: int = 512,
                 scorer: Optional[PairScorer] = None, batch: int = 32) -> None:
        """Args:
            model: A saved model folder or a Hugging Face name (loaded on first use; needs torch and transformers).
            weight: Weight of the cross-encoder z-score against the stage-1 z-score (0 = stage 1 only).
            max_length: Token limit of the pair.
            scorer: Replaces the model (tests): maps a list of (query, doc) to scores.
            batch: Pairs per forward pass.
        """
        self.model_name, self.weight, self.max_length, self.batch = model, weight, max_length, batch
        self._scorer = scorer
        self._loaded: Optional[tuple[Any, Any, str]] = None

    def _score(self, pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
        if self._scorer is not None:
            return self._scorer(pairs)
        from agents.traceability_agent.reranker.train import encode, pick_device

        if self._loaded is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            device = pick_device()
            tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            model = AutoModelForSequenceClassification.from_pretrained(self.model_name).to(device).eval()
            self._loaded = (tokenizer, model, device)
        tokenizer, model, device = self._loaded
        import torch

        out: list[float] = []
        rows = [{"query": q, "doc": d} for q, d in pairs]
        with torch.no_grad():
            for i in range(0, len(rows), self.batch):
                enc = {k: v.to(device) for k, v in encode(tokenizer, rows[i : i + self.batch], self.max_length).items()}
                out.extend(model(**enc).logits.squeeze(-1).float().cpu().tolist())
        return out

    def select(self, candidates: list[Candidate], keep: int) -> list[Candidate]:
        """Keep the ``keep`` best candidates per source, best first; the Candidate.similarity stays the stage-1 score."""
        if not candidates:
            return []
        by_source: "OrderedDict[str, list[Candidate]]" = OrderedDict()
        for c in candidates:
            by_source.setdefault(c.source.id, []).append(c)
        reqs = [group[0].source for group in by_source.values()]
        code = list({c.target.id: c.target for c in candidates}.values())
        focus = Focus(reqs, code)
        pairs = [(c.source.text, focus.text(c.source.id, c.target.id)) for group in by_source.values() for c in group]
        scores = iter(self._score(pairs))
        chosen: list[Candidate] = []
        for group in by_source.values():
            rerank = [next(scores) for _ in group]
            fused = _z([c.similarity for c in group]) + self.weight * _z(rerank)
            order = np.argsort(-fused, kind="stable")[:keep]
            chosen.extend(group[i] for i in order)
        return chosen
