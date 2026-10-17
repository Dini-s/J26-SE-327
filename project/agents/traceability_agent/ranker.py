"""Learned Link Ranker: a small model trained on past projects to rank code for a requirement.

Stage 1 fuses TF-IDF and MiniLM with a fixed formula (z-score sum). This module replaces that formula with a
gradient-boosting model that sees several signals per (requirement, code) pair and learns how much to trust each.
It needs no LLM; it is trained and measured on the ground-truth links of the public datasets.

Honest test: leave-one-project-out. For every dataset the model is trained on the OTHER projects only and
then ranks the held-out project, which it has never seen.

    python -m agents.traceability_agent.ranker --out data/results/ranker.json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from agents.traceability_agent.config import CHUNK_WORDS
from agents.traceability_agent.preprocess import retrieval_text, split_identifiers
from agents.traceability_agent.retrieval import embedding_matrix, tfidf_matrix, zscore_fuse
from shared.schemas.traceability import Artifact

PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"
DATASETS = ["libest", "cm1", "ebt", "eanci", "smos", "etour", "itrust"]
POOL = 50  # candidates per requirement handed to the ranker (best by the stage-1 hybrid)
KS = (5, 10, 20)
FEATURES = [
    "tfidf", "emb", "hybrid",
    "tfidf_z", "emb_z", "hybrid_z",
    "tfidf_rank", "emb_rank", "hybrid_rank",
    "hybrid_gap_top", "hybrid_col_z", "hybrid_rev_rank",
    "name_overlap", "rare_overlap", "log_code_len", "log_req_len",
]

_TOKEN = re.compile(r"[a-z][a-z0-9]{2,}")


def _z_rows(m: np.ndarray) -> np.ndarray:
    return (m - m.mean(axis=1, keepdims=True)) / (m.std(axis=1, keepdims=True) + 1e-9)


def _ranks(m: np.ndarray) -> np.ndarray:
    """Rank of each cell within its row (0 = best)."""
    order = np.argsort(-m, axis=1, kind="stable")
    ranks = np.empty_like(order)
    rows = np.arange(m.shape[0])[:, None]
    ranks[rows, order] = np.arange(m.shape[1])[None, :]
    return ranks


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(split_identifiers(text).lower()))


def build_features(
    tfidf: np.ndarray, emb: np.ndarray, req_texts: Sequence[str], code_names: Sequence[str], code_texts: Sequence[str],
    pool: int = POOL,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Feature rows for the top-``pool`` hybrid candidates of every requirement.

    Args:
        tfidf: TF-IDF similarity matrix (requirements x code).
        emb: Embedding similarity matrix, same shape.
        req_texts: Requirement texts.
        code_names: Code ids / file names (their identifiers are matched against the requirement words).
        code_texts: Prepared code texts (used for rare-word overlap and length).
        pool: Candidates per requirement.

    Returns:
        ``(X, req_index, code_index)``: the feature matrix and, per row, which requirement and code it is.
    """
    n_req, n_code = tfidf.shape
    pool = min(pool, n_code)
    hybrid = zscore_fuse([tfidf, emb])
    tf_z, em_z, hy_z = _z_rows(tfidf), _z_rows(emb), _z_rows(hybrid)
    tf_r, em_r, hy_r = _ranks(tfidf), _ranks(emb), _ranks(hybrid)
    col_z = (hybrid - hybrid.mean(axis=0, keepdims=True)) / (hybrid.std(axis=0, keepdims=True) + 1e-9)
    rev_rank = _ranks(hybrid.T).T  # rank of this requirement among all requirements for the code
    top1 = hybrid.max(axis=1, keepdims=True)

    req_tok = [_tokens(t) for t in req_texts]
    name_tok = [_tokens(n) for n in code_names]
    code_tok = [_tokens(t) for t in code_texts]
    doc_freq: dict[str, int] = {}
    for toks in code_tok:
        for w in toks:
            doc_freq[w] = doc_freq.get(w, 0) + 1
    rare = {w for w, c in doc_freq.items() if c <= max(2, n_code // 50)}  # words that occur in few code files
    code_len = np.log1p([len(t) for t in code_texts])
    req_len = np.log1p([len(t) for t in req_texts])

    rows: list[list[float]] = []
    ri: list[int] = []
    ci: list[int] = []
    for i in range(n_req):
        for j in np.argsort(-hybrid[i], kind="stable")[:pool]:
            shared_name = req_tok[i] & name_tok[j]
            rows.append([
                tfidf[i, j], emb[i, j], hybrid[i, j],
                tf_z[i, j], em_z[i, j], hy_z[i, j],
                tf_r[i, j], em_r[i, j], hy_r[i, j],
                top1[i, 0] - hybrid[i, j], col_z[i, j], rev_rank[i, j],
                len(shared_name) / (len(name_tok[j]) or 1),
                len(req_tok[i] & code_tok[j] & rare),
                code_len[j], req_len[i],
            ])
            ri.append(i)
            ci.append(int(j))
    return np.asarray(rows, dtype=float), np.asarray(ri), np.asarray(ci)


def recall_at(scores_by_req: dict[int, list[tuple[float, int]]], gold: dict[int, set[int]], k: int) -> float:
    """Share of true links found in each requirement's top-k (pooled over all true links)."""
    hit = total = 0
    for i, truth in gold.items():
        ranked = [c for _, c in sorted(scores_by_req.get(i, []), key=lambda x: -x[0])[:k]]
        hit += len(truth & set(ranked))
        total += len(truth)
    return hit / total if total else 0.0


def load_project(name: str) -> tuple[list[Artifact], list[Artifact], dict[int, set[int]]]:
    arts = [Artifact(**a) for a in json.loads((PROCESSED / name / "artifacts.json").read_text(encoding="utf-8"))]
    traces = json.loads((PROCESSED / name / "traces.json").read_text(encoding="utf-8"))
    reqs = [a for a in arts if a.type == "requirement"]
    code = [a for a in arts if a.type != "requirement"]
    r_idx = {a.id: i for i, a in enumerate(reqs)}
    c_idx = {a.id: i for i, a in enumerate(code)}
    gold: dict[int, set[int]] = {}
    for t in traces:
        if t["source_id"] in r_idx and t["target_id"] in c_idx:
            gold.setdefault(r_idx[t["source_id"]], set()).add(c_idx[t["target_id"]])
    return reqs, code, gold


def project_matrices(name: str, cache: Path, embedder: Any) -> tuple[np.ndarray, np.ndarray]:
    """TF-IDF and embedding similarity matrices for a project (cached on disk, MiniLM is the slow part)."""
    path = cache / f"{name}.npz"
    if path.exists():
        data = np.load(path)
        return data["tfidf"], data["emb"]
    reqs, code, _ = load_project(name)
    tfidf = tfidf_matrix(reqs, code, retrieval_text, CHUNK_WORDS)
    emb = embedding_matrix(reqs, code, embedder, retrieval_text, CHUNK_WORDS)
    cache.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, tfidf=tfidf, emb=emb)
    return tfidf, emb


def make_model(seed: int = 0) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_depth=4, learning_rate=0.08, max_iter=150, l2_regularization=1.0,
                                          class_weight="balanced", random_state=seed)


def evaluate(cache: Path, datasets: Sequence[str] = DATASETS, seed: int = 0) -> dict[str, Any]:
    """Leave-one-project-out: train on the other projects, rank the held-out one, compare with plain hybrid."""
    embedder = None
    if any(not (cache / f"{d}.npz").exists() for d in datasets):
        from shared.embeddings.embedder import Embedder

        embedder = Embedder()
    built: dict[str, dict[str, Any]] = {}
    for d in datasets:
        reqs, code, gold = load_project(d)
        tfidf, emb = project_matrices(d, cache, embedder)
        X, ri, ci = build_features(tfidf, emb, [r.text for r in reqs], [c.id for c in code], [retrieval_text(c) for c in code])
        y = np.array([int(c in gold.get(r, ())) for r, c in zip(ri, ci)])
        built[d] = {"X": X, "ri": ri, "ci": ci, "y": y, "gold": gold, "hybrid": zscore_fuse([tfidf, emb]), "n_req": len(reqs)}
        print(f"features {d}: {len(X)} rows, {int(y.sum())} positives in pool", file=sys.stderr)

    results: dict[str, Any] = {}
    importances: list[np.ndarray] = []
    for held in datasets:
        train = [d for d in datasets if d != held]
        X = np.vstack([built[d]["X"] for d in train])
        y = np.concatenate([built[d]["y"] for d in train])
        model = make_model(seed).fit(X, y)
        b = built[held]
        proba = model.predict_proba(b["X"])[:, 1]
        learned: dict[int, list[tuple[float, int]]] = {}
        plain: dict[int, list[tuple[float, int]]] = {}
        for p, r, c in zip(proba, b["ri"], b["ci"]):
            learned.setdefault(int(r), []).append((float(p), int(c)))
        for i in b["gold"]:
            plain[i] = [(float(b["hybrid"][i, j]), int(j)) for j in range(b["hybrid"].shape[1])]
        gold = b["gold"]
        total = sum(len(v) for v in gold.values())
        in_pool = int(b["y"].sum())
        results[held] = {
            "true_links": total, "pool_recall": round(in_pool / total, 3) if total else None,
            "hybrid": {str(k): round(recall_at(plain, gold, k), 3) for k in KS},
            "learned": {str(k): round(recall_at(learned, gold, k), 3) for k in KS},
        }
        importances.append(_permutation_importance(model, b["X"], b["y"]))
        h, l = results[held]["hybrid"], results[held]["learned"]
        print(f"{held}: hybrid@10 {h['10']} -> learned@10 {l['10']}", file=sys.stderr)

    results["_macro"] = {s: {str(k): round(float(np.mean([results[d][s][str(k)] for d in datasets])), 3) for k in KS} for s in ("hybrid", "learned")}
    imp = np.mean(importances, axis=0)
    results["_feature_importance"] = dict(sorted(zip(FEATURES, (round(float(v), 4) for v in imp)), key=lambda kv: -kv[1]))
    return results


def _permutation_importance(model: Any, X: np.ndarray, y: np.ndarray, seed: int = 0) -> np.ndarray:
    """Drop in average precision when one feature is shuffled (bigger = the model leans on it more)."""
    from sklearn.metrics import average_precision_score

    if y.sum() == 0:
        return np.zeros(X.shape[1])
    rng = np.random.default_rng(seed)
    base = average_precision_score(y, model.predict_proba(X)[:, 1])
    out = np.zeros(X.shape[1])
    for f in range(X.shape[1]):
        Xp = X.copy()
        Xp[:, f] = rng.permutation(Xp[:, f])
        out[f] = base - average_precision_score(y, model.predict_proba(Xp)[:, 1])
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", default=str(PROCESSED.parent / "cache" / "stage1"))
    parser.add_argument("--out", default="data/results/ranker.json")
    parser.add_argument("--datasets", default=",".join(DATASETS))
    args = parser.parse_args(argv)
    res = evaluate(Path(args.cache), [d for d in args.datasets.split(",") if d])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res["_macro"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
