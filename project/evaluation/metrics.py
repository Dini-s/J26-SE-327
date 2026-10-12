"""Evaluation metrics for the Component 1 baselines (no data access, no model code).

Precision / recall / F1 (macro and per class), confusion matrix, 95 % percentile-bootstrap confidence intervals, and
cross-validation helpers that group by `group_id`. All randomness uses an explicit seed.
"""
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

SEED = 327
N_BOOT = 1000


def _encode(y, labels):
    index = {l: i for i, l in enumerate(labels)}
    return np.array([index[v] for v in y], dtype=int)


def _confusion_from_codes(yt, yp, k):
    return np.bincount(yt * k + yp, minlength=k * k).reshape(k, k)  # rows = true, cols = predicted


def confusion_matrix(y_true, y_pred, labels):
    return _confusion_from_codes(_encode(y_true, labels), _encode(y_pred, labels), len(labels))


def _prf(cm):
    tp = np.diag(cm).astype(float)
    pred, true = cm.sum(axis=0).astype(float), cm.sum(axis=1).astype(float)
    p = np.divide(tp, pred, out=np.zeros_like(tp), where=pred > 0)
    r = np.divide(tp, true, out=np.zeros_like(tp), where=true > 0)
    f = np.divide(2 * p * r, p + r, out=np.zeros_like(tp), where=(p + r) > 0)
    return p, r, f, true


def _summary(cm, present_only=True):
    p, r, f, support = _prf(cm)
    keep = support > 0 if present_only else np.ones_like(support, bool)
    acc = float(np.diag(cm).sum() / cm.sum()) if cm.sum() else 0.0
    return {"accuracy": acc, "macro_precision": float(p[keep].mean()), "macro_recall": float(r[keep].mean()), "macro_f1": float(f[keep].mean()),
            "per_class": {"precision": p, "recall": r, "f1": f, "support": support}}


def classification_metrics(y_true, y_pred, labels):
    """Point estimates. Macro averages use classes that occur in y_true. Returns a flat dict plus per-class entries."""
    cm = confusion_matrix(y_true, y_pred, labels)
    s = _summary(cm)
    out = {k: s[k] for k in ("accuracy", "macro_precision", "macro_recall", "macro_f1")}
    for i, l in enumerate(labels):
        for m in ("precision", "recall", "f1"):
            out[f"{m}[{l}]"] = float(s["per_class"][m][i])
        out[f"support[{l}]"] = int(s["per_class"]["support"][i])
    return out


def bootstrap_ci(y_true, y_pred, labels, n_boot=N_BOOT, seed=SEED, alpha=0.05):
    """Percentile bootstrap over rows. Returns {metric: (low, high)} for the same keys as classification_metrics (support excluded)."""
    yt, yp, k = _encode(y_true, labels), _encode(y_pred, labels), len(labels)
    n = len(yt)
    rng = np.random.default_rng(seed)
    draws = {}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        s = _summary(_confusion_from_codes(yt[idx], yp[idx], k))
        for key in ("accuracy", "macro_precision", "macro_recall", "macro_f1"):
            draws.setdefault(key, []).append(s[key])
        sup = s["per_class"]["support"]
        for i, l in enumerate(labels):
            for m in ("precision", "recall", "f1"):
                draws.setdefault(f"{m}[{l}]", []).append(s["per_class"][m][i] if sup[i] > 0 else np.nan)
    lo, hi = 100 * alpha / 2, 100 * (1 - alpha / 2)
    out = {}
    for key, vals in draws.items():
        vals = np.asarray(vals, dtype=float)
        vals = vals[~np.isnan(vals)]
        out[key] = (float(np.percentile(vals, lo)), float(np.percentile(vals, hi))) if len(vals) else (float("nan"), float("nan"))
    return out


def multilabel_metrics(Y_true, Y_pred, classes):
    """Per-class binary P/R/F1 plus micro and macro F1 (macro over classes with at least one true positive row)."""
    Y_true, Y_pred = np.asarray(Y_true), np.asarray(Y_pred)
    out = {}
    f_list = []
    for j, c in enumerate(classes):
        tp = int(((Y_true[:, j] == 1) & (Y_pred[:, j] == 1)).sum())
        fp = int(((Y_true[:, j] == 0) & (Y_pred[:, j] == 1)).sum())
        fn = int(((Y_true[:, j] == 1) & (Y_pred[:, j] == 0)).sum())
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        out[f"precision[{c}]"], out[f"recall[{c}]"], out[f"f1[{c}]"], out[f"support[{c}]"] = p, r, f, int(Y_true[:, j].sum())
        if Y_true[:, j].sum() > 0:
            f_list.append(f)
    tp = int(((Y_true == 1) & (Y_pred == 1)).sum())
    fp = int(((Y_true == 0) & (Y_pred == 1)).sum())
    fn = int(((Y_true == 1) & (Y_pred == 0)).sum())
    mp = tp / (tp + fp) if tp + fp else 0.0
    mr = tp / (tp + fn) if tp + fn else 0.0
    out["micro_precision"], out["micro_recall"] = mp, mr
    out["micro_f1"] = 2 * mp * mr / (mp + mr) if mp + mr else 0.0
    out["macro_f1"] = float(np.mean(f_list)) if f_list else 0.0
    return out


def multilabel_bootstrap_ci(Y_true, Y_pred, classes, n_boot=N_BOOT, seed=SEED, alpha=0.05):
    Y_true, Y_pred = np.asarray(Y_true), np.asarray(Y_pred)
    rng = np.random.default_rng(seed)
    n = len(Y_true)
    draws = {}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        m = multilabel_metrics(Y_true[idx], Y_pred[idx], classes)
        for key, v in m.items():
            if not key.startswith("support"):
                draws.setdefault(key, []).append(v if not (key.startswith(("precision[", "recall[", "f1[")) and m[f"support[{key[key.index('[') + 1:-1]}]"] == 0) else np.nan)
    lo, hi = 100 * alpha / 2, 100 * (1 - alpha / 2)
    out = {}
    for key, vals in draws.items():
        vals = np.asarray(vals, dtype=float)
        vals = vals[~np.isnan(vals)]
        out[key] = (float(np.percentile(vals, lo)), float(np.percentile(vals, hi))) if len(vals) else (float("nan"), float("nan"))
    return out


def grouped_folds(y, groups, n_splits=5, seed=SEED):
    """Stratified group k-fold index pairs. Rows sharing a group never cross folds. `y` may be a label vector."""
    y = np.asarray(y)
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return list(splitter.split(np.zeros(len(y)), y, groups=np.asarray(groups)))


def grouped_cv_predictions(fit_predict, X, y, groups, n_splits=5, seed=SEED):
    """Out-of-fold predictions. `fit_predict(X_train, y_train, X_test) -> y_pred`. Returns an object array aligned with `y`."""
    X, y = np.asarray(X, dtype=object), np.asarray(y)
    pred = np.empty(len(y), dtype=object)
    for tr, te in grouped_folds(y, groups, n_splits, seed):
        pred[te] = fit_predict(X[tr], y[tr], X[te])
    return pred


def stratified_cv_predictions(fit_predict, X, y, n_splits=5, seed=SEED):
    """Out-of-fold predictions with plain stratified k-fold (for rows that have no groups)."""
    X, y = np.asarray(X, dtype=object), np.asarray(y)
    pred = np.empty(len(y), dtype=object)
    for tr, te in StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(np.zeros(len(y)), y):
        pred[te] = fit_predict(X[tr], y[tr], X[te])
    return pred


def leave_one_group_out(fit_predict, X, y, groups):
    """Train on all other groups, predict the held-out group. Returns {group: (y_true, y_pred)} in sorted group order."""
    X, y, groups = np.asarray(X, dtype=object), np.asarray(y), np.asarray(groups)
    out = {}
    for g in sorted(set(groups)):
        te = groups == g
        out[g] = (y[te], np.asarray(fit_predict(X[~te], y[~te], X[te]), dtype=object))
    return out
