"""Text features for the Component 1 baselines: TF-IDF and cached sentence embeddings.

Nothing here reads data files. Embeddings come from the CPU-only `all-MiniLM-L6-v2` model and are cached per text in
`models/component1/part_a_active/embedding_cache/` (git-ignored) so repeated runs are fast and byte-identical.
"""
import hashlib
import re
from pathlib import Path

import joblib
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer

SEED = 327
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "models" / "component1" / "part_a_active" / "embedding_cache"
CACHE_FILE = CACHE_DIR / "all-MiniLM-L6-v2.joblib"

_MODEL = None
_CACHE = None


def make_tfidf():
    """Word 1-2-gram TF-IDF with sublinear tf. Fitted on the training texts only (inside each Pipeline)."""
    return TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2, sublinear_tf=True)


def _text_id(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _load_cache():
    if CACHE_FILE.exists():
        try:
            return joblib.load(CACHE_FILE)
        except Exception:
            return {}
    return {}


def _get_model():
    global _MODEL
    if _MODEL is None:
        import torch
        from sentence_transformers import SentenceTransformer
        torch.manual_seed(SEED)
        _MODEL = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    return _MODEL


def embed(texts, use_cache=True):
    """Return an (n, 384) float32 array of sentence embeddings, in input order."""
    texts = [str(t) for t in texts]
    global _CACHE
    if use_cache:
        if _CACHE is None:
            _CACHE = _load_cache()
        cache = _CACHE
    else:
        cache = {}
    ids = [_text_id(t) for t in texts]
    missing = sorted({(i, t) for i, t in zip(ids, texts) if i not in cache})
    if missing:
        model = _get_model()
        vectors = model.encode([t for _, t in missing], batch_size=64, show_progress_bar=False, convert_to_numpy=True,
                               normalize_embeddings=True)
        for (i, _), v in zip(missing, vectors):
            cache[i] = v.astype(np.float32)
        if use_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            joblib.dump(cache, CACHE_FILE)
    return np.vstack([cache[i] for i in ids]) if ids else np.zeros((0, 384), dtype=np.float32)


class Embedder(BaseEstimator, TransformerMixin):
    """Sklearn transformer: texts -> MiniLM embeddings. Stateless; the transformer weights are never pickled."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return embed(list(X))


# --- text normalisation: the same recipe as `requirement_text_normalized` in the processed data (a parity test checks it) -------------------
_MOJIBAKE = re.compile("[\u00c3\u00c2\u00e2][\u0080-\u00bf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc"
                       "\u2013\u2014\u2018-\u201e\u2020-\u2022\u2026\u2030\u2039\u203a\u20ac\u2122]{1,2}")
_OUTER_QUOTES = re.compile(r"^([\'\"\u201c\u2018`]+)(.*?)([\'\"\u201d\u2019`]+)$", re.S)


def _collapse(value):
    return re.sub(r"\s+", " ", str(value).replace(" ", " ")).strip()


def _repair_mojibake(text):
    def fix(match):
        try:
            return match.group(0).encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return match.group(0)
    return _MOJIBAKE.sub(fix, text)


def normalize_for_models(value):
    """Lower-case, whitespace-collapsed text with matching outer quotes removed: the text the baselines were trained on."""
    text = _repair_mojibake(_collapse(value))
    match = _OUTER_QUOTES.match(text)
    if match:
        text = match.group(2).strip()
    return text.lower()
