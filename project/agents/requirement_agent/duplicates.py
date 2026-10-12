"""Near-duplicate detection for requirement texts: MiniLM embeddings, cosine threshold, then DBSCAN grouping.

Two requirements are linked when their cosine similarity is at least `threshold`; DBSCAN (cosine distance, eps = 1 - threshold,
min_samples = 2) turns the links into groups, so a group can chain A~B~C even if A and C are a little below the threshold.
The threshold is not hard-coded: `evaluation/duplicates_eval.py` chooses it on a seeded development subset (train split only) and
writes `models/component1/part_a_active/duplicates_config.json`, which the agent loads. No LLM calls.
"""
import json
import re
from pathlib import Path

import numpy as np
from sklearn.cluster import DBSCAN

from .features import embed

CONFIG_PATH = Path(__file__).resolve().parents[2] / "models" / "component1" / "part_a_active" / "duplicates_config.json"


def exact_key(text):
    """Normalisation used to recognise exact-text matches (lower case, alphanumerics only)."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def load_threshold(path=None):
    path = Path(path) if path else CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Duplicate-detection config not found: {path}. Create it with: python -m evaluation.duplicates_eval --task seeded")
    return float(json.loads(path.read_text(encoding="utf-8"))["threshold"])


def similarity_pairs(embeddings, low, high=None, block=1000):
    """All index pairs i < j with low <= cosine < high (high=None: no upper bound). Embeddings must be L2-normalised.
    Returns three arrays (i, j, cosine), sorted by (i, j)."""
    emb = np.asarray(embeddings, dtype=np.float32)
    n = len(emb)
    ii, jj, ss = [], [], []
    for start in range(0, n, block):
        sims = emb[start:start + block] @ emb.T
        rows, cols = np.nonzero(sims >= low - 1e-7)
        keep = cols > rows + start
        rows, cols = rows[keep] + start, cols[keep]
        vals = sims[rows - start, cols]
        if high is not None:
            ok = vals < high
            rows, cols, vals = rows[ok], cols[ok], vals[ok]
        ii.append(rows)
        jj.append(cols)
        ss.append(vals)
    if not ii:
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0, np.float32)
    return np.concatenate(ii), np.concatenate(jj), np.concatenate(ss)


def cluster_labels(embeddings, threshold):
    """DBSCAN cluster label per row (-1 = not part of any duplicate group)."""
    emb = np.asarray(embeddings, dtype=np.float32)
    if len(emb) < 2:
        return np.full(len(emb), -1)
    model = DBSCAN(eps=1.0 - float(threshold) + 1e-6, min_samples=2, metric="cosine", algorithm="brute")
    return model.fit(emb).labels_


def group_ids(labels):
    """Stable group ids ('DUP0001', ...) numbered by the first row of each group; rows in no group get ''."""
    names, out = {}, []
    for lab in labels:
        if lab < 0:
            out.append("")
            continue
        if lab not in names:
            names[lab] = f"DUP{len(names) + 1:04d}"
        out.append(names[lab])
    return out


def find_duplicate_groups(texts, threshold, embeddings=None):
    """Group id per text ('' when the text has no near-duplicate). Embeds the texts unless `embeddings` is given."""
    texts = list(texts)
    emb = embed(texts) if embeddings is None else embeddings
    return group_ids(cluster_labels(emb, threshold))
