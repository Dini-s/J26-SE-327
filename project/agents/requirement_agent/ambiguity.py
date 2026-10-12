"""Ambiguity-detection baselines for Component 1.

(a) the QuRE weak-word rule: a requirement is a `defect` if it contains a QuRE weak word;
(b) TF-IDF + logistic regression and (c) sentence embeddings + logistic regression (built by `classifier.build_model`).

No file is read here: task data is passed in as arrays, so the frozen test split cannot reach this module. QuRE weak words are
collected from *training* rows only.
"""
import re

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin

from .classifier import tune_and_fit  # noqa: F401  (re-exported: the same tuning routine serves the ambiguity models)

RULE_NAME = "qure_weak_word_rule"
LABELS = ("defect", "ok")


def weak_words_from_evidence(evidence):
    """QuRE weak words from `smell_evidence` strings such as 'defect=ok;weak_word=detail'."""
    words = set()
    for value in evidence:
        for part in str(value).split(";"):
            if part.startswith("weak_word="):
                w = part.split("=", 1)[1].strip().lower()
                if w:
                    words.add(w)
    return sorted(words)


def _regex(words):
    if not words:
        return None
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")(?![a-z0-9])", re.I)


class WeakWordRuleModel(BaseEstimator, ClassifierMixin):
    """`defect` if any QuRE weak word occurs as a whole word, else `ok`. No learning."""

    def __init__(self, weak_words=None):
        self.weak_words = weak_words

    def fit(self, X, y=None):
        self.classes_ = np.array(sorted(LABELS))
        self._rx = _regex(set(self.weak_words or []))
        return self

    def matches(self, text):
        return [m.group(0).lower() for m in self._rx.finditer(text)] if self._rx else []

    def predict(self, X):
        return np.array(["defect" if self._rx and self._rx.search(t) else "ok" for t in X], dtype=object)
