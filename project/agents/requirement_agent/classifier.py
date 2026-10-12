"""Baseline text classifiers for Component 1 (FR/NFR, security, NFR subtype, and the shared model factory).

The five baselines, in order: majority class, keyword/regex rules, TF-IDF + logistic regression, TF-IDF + linear SVM,
sentence embeddings + logistic regression. These functions only receive arrays of texts and labels: they never read files,
so the frozen test split cannot reach them. Hyper-parameters are tuned on the validation arrays only.
"""
import re

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from .features import SEED, Embedder, make_tfidf

MODEL_KINDS = ("majority", "rules", "tfidf_lr", "tfidf_svm", "emb_lr")
C_GRID = {"tfidf_lr": [0.1, 1, 10, 100, 1000], "tfidf_svm": [0.01, 0.1, 1, 10], "emb_lr": [0.1, 1, 10, 100, 1000]}

# --- keyword rules, written from general requirements-engineering vocabulary (not tuned on any data) ------------------------
SUBTYPE_CUES = {
    "A": r"\b(availab\w*|uptime|24\s*/\s*7|24 hours|downtime|operational at all times)\b",
    "FT": r"\b(fault[- ]toleran\w*|recover\w*|fail(s|ure|ures|over)?|crash\w*|backup\w*|redundan\w*|resum\w*|graceful\w*)\b",
    "L": r"\b(comply|compliance|complies|legal\w*|law|laws|regulat\w*|statut\w*|hipaa|iso ?\d*|gdpr|standards?|certif\w*|policy|policies)\b",
    "LF": r"\b(look and feel|colou?rs?|fonts?|layout|appearance|icons?|logo\w*|style|visual\w*|screen design|theme|graphics?)\b",
    "MN": r"\b(maintain\w*|maintenance|modif\w*|upgrad\w*|updat\w*|extensib\w*|configurab\w*|changes? to the)\b",
    "O": r"\b(operat\w*|runs? on|deploy\w*|install\w*|environment|hardware|network|interface with|server)\b",
    "PE": r"\b(response time|within \d+|seconds?|milliseconds?|throughput|latency|performance|fast\w*|speed|per second|concurrent\w*|simultaneous\w*|load)\b",
    "PO": r"\b(portab\w*|platforms?|cross-platform|windows|linux|unix|mac ?os|browsers?|compatib\w*|operating systems?|android|ios)\b",
    "SC": r"\b(scal\w*|growth|grow|increase in (users|volume|load)|expan\w*|up to \d[\d,]* (users|records|transactions))\b",
    "SE": r"\b(secur\w*|authenticat\w*|authoriz\w*|authoris\w*|encrypt\w*|passwords?|confidential\w*|privacy|private|access control|"
          r"permissions?|audit\w*|login|log in|credentials?|integrity|unauthori[sz]ed|protect\w*|malicious|attack\w*)\b",
    "US": r"\b(usab\w*|user[- ]friendly|easy to (use|learn|understand)|ease of use|learn\w*|intuitive|accessib\w*|help\b|training|"
          r"understand\w*|novice|menus?)\b",
}
_SUBTYPE_RE = {k: re.compile(v, re.I) for k, v in SUBTYPE_CUES.items()}
_ANY_NFR_RE = re.compile("|".join(f"(?:{v})" for v in SUBTYPE_CUES.values()) + r"|\d+\s?%", re.I)


def rule_fr_nfr(text):
    """NFR if any non-functional cue (any subtype cue or a percentage) appears, otherwise FR."""
    return "NFR" if _ANY_NFR_RE.search(text) else "FR"


def rule_security(text):
    return "1" if _SUBTYPE_RE["SE"].search(text) else "0"


def security_cue_words(text):
    """The security cue words the keyword rule matched in `text` (explanation for a security flag)."""
    return sorted({m.group(0).lower() for m in _SUBTYPE_RE["SE"].finditer(text)})


def rule_subtype_labels(text):
    return {k for k, rx in _SUBTYPE_RE.items() if rx.search(text)}


class MajorityModel(BaseEstimator, ClassifierMixin):
    def fit(self, X, y):
        values, counts = np.unique(np.asarray(y), return_counts=True)
        self.majority_ = values[np.argmax(counts)]
        self.classes_ = values
        return self

    def predict(self, X):
        return np.array([self.majority_] * len(X), dtype=object)


class RuleModel(BaseEstimator, ClassifierMixin):
    """Fixed keyword rules. `rule` is one of fr_nfr / security; fit() only records the classes."""

    def __init__(self, rule="fr_nfr"):
        self.rule = rule

    def fit(self, X, y):
        self.classes_ = np.unique(np.asarray(y))
        return self

    def predict(self, X):
        fn = {"fr_nfr": rule_fr_nfr, "security": rule_security}[self.rule]
        return np.array([fn(t) for t in X], dtype=object)


class SubtypeRuleModel(BaseEstimator):
    """Multi-label rules for the 11 PROMISE_NICE subtypes. Returns a 0/1 matrix in `classes` order."""

    def __init__(self, classes=None):
        self.classes = classes

    def fit(self, X, Y):
        self.classes_ = list(self.classes)
        return self

    def predict(self, X):
        return np.array([[1 if c in rule_subtype_labels(t) else 0 for c in self.classes_] for t in X], dtype=int)


def _estimator(kind, C):
    if kind == "tfidf_lr":
        return Pipeline([("f", make_tfidf()), ("c", LogisticRegression(C=C, class_weight="balanced", max_iter=3000, random_state=SEED))])
    if kind == "tfidf_svm":
        return Pipeline([("f", make_tfidf()), ("c", LinearSVC(C=C, class_weight="balanced", random_state=SEED, max_iter=20000))])
    if kind == "emb_lr":
        return Pipeline([("f", Embedder()), ("c", LogisticRegression(C=C, class_weight="balanced", max_iter=3000, random_state=SEED))])
    raise ValueError(kind)


def build_model(kind, C=1.0, rule="fr_nfr", multilabel_classes=None):
    """Return an unfitted model with fit(texts, y) / predict(texts). With `multilabel_classes`, y is a 0/1 matrix."""
    if multilabel_classes is not None:
        if kind == "majority":
            return OneVsRestClassifier(_MajorityBinary())
        if kind == "rules":
            return SubtypeRuleModel(classes=list(multilabel_classes))
        return OneVsRestClassifier(_estimator(kind, C))
    if kind == "majority":
        return MajorityModel()
    if kind == "rules":
        return RuleModel(rule=rule)
    return _estimator(kind, C)


class _MajorityBinary(BaseEstimator, ClassifierMixin):
    def fit(self, X, y):
        self.classes_ = np.unique(y)
        self.m_ = MajorityModel().fit(X, y).majority_
        return self

    def predict(self, X):
        return np.array([self.m_] * len(X))

    def predict_proba(self, X):
        out = np.zeros((len(X), 2))
        out[:, int(self.m_)] = 1.0
        return out


def _score(y_true, y_pred, multilabel):
    if multilabel:
        return f1_score(y_true, y_pred, average="micro", zero_division=0)
    return f1_score(y_true, y_pred, average="macro", zero_division=0)


def tune_and_fit(kind, X_train, y_train, X_val, y_val, rule="fr_nfr", multilabel_classes=None):
    """Tune C on the validation arrays, then refit on the training arrays only (val stays untouched for reporting).

    Returns (fitted_model, best_C, tuning_rows). Selection metric: macro-F1 (micro-F1 for multi-label). Ties go to the smaller C.
    """
    multilabel = multilabel_classes is not None
    grid = C_GRID.get(kind, [None])
    rows, best = [], None
    for C in grid:
        model = build_model(kind, C if C is not None else 1.0, rule, multilabel_classes).fit(list(X_train), y_train)
        score = _score(y_val, model.predict(list(X_val)), multilabel)
        rows.append({"model": kind, "C": "" if C is None else C, "val_score": round(float(score), 6)})
        if best is None or score > best[0] + 1e-12:
            best = (score, C, model)
    return best[2], best[1], rows
