"""Tree-based models (XGBoost, LightGBM, RandomForest, ExtraTrees) on the same Component 1 tasks, splits and metrics as `run_baselines`.

    python -m evaluation.tree_models_eval --task fr_nfr|security|ambiguity|all [--quick]

Why: the baselines (majority, rules, TF-IDF/embeddings + logistic regression or SVM) never included tree boosting, and it is sometimes claimed to be "the best algorithm".
This script answers that for our text tasks with the same protocol: every model is fitted on the train split only and tuned on the validation split only (macro-F1,
seed 327); FR/NFR also gets grouped / stratified cross-validation and PROMISE leave-one-project-out on train+val. The frozen test split is read once per task in
`final()`, through `data_access.load_test_for_final_evaluation` (SHA-256 verified), and no choice is made from it.
Models are NOT saved and nothing under models/ or agents/ is touched. Output: evaluation/component1/results/tree_models_{metrics,tuning}.csv and tree_models_notes.txt.
Needs the optional packages in requirements-experiments.txt (xgboost, lightgbm).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier

from agents.requirement_agent.classifier import security_cue_words
from agents.requirement_agent.features import SEED, embed, make_tfidf
from evaluation import data_access as da
from evaluation import metrics as M
from evaluation.run_baselines import DEFAULT_OUT, FILES, GROUPED_CV, METRIC_COLS, MIN_CV_ROWS, SECURITY_SOURCE, STRATIFIED_CV, TEXT, Results, _security_filter, basis_family

FAMILIES = ("xgboost", "lightgbm", "random_forest", "extra_trees")
FEATURES = ("tfidf", "emb", "tfidf_emb", "emb_hand")
QUICK_FEATURES = ("emb", "tfidf_emb")

# small grids on purpose (validation macro-F1 picks one per family and feature set); `--full` doubles them
GRIDS = {
    "xgboost": [{"max_depth": 4, "n_estimators": 300}, {"max_depth": 6, "n_estimators": 300}],
    "lightgbm": [{"num_leaves": 15, "n_estimators": 300}, {"num_leaves": 31, "n_estimators": 300}],
    "random_forest": [{"n_estimators": 300, "max_depth": None}, {"n_estimators": 300, "max_depth": 40}],
    "extra_trees": [{"n_estimators": 300, "max_depth": None}, {"n_estimators": 300, "max_depth": 40}],
}
FULL_EXTRA = {
    "xgboost": [{"max_depth": 4, "n_estimators": 600}, {"max_depth": 6, "n_estimators": 600}],
    "lightgbm": [{"num_leaves": 15, "n_estimators": 600}, {"num_leaves": 31, "n_estimators": 600}],
    "random_forest": [{"n_estimators": 600, "max_depth": None}, {"n_estimators": 600, "max_depth": 40}],
    "extra_trees": [{"n_estimators": 600, "max_depth": None}, {"n_estimators": 600, "max_depth": 40}],
}

_NEGATION = ("not", "no", "never", "without", "cannot")
_MODAL = ("may", "might", "could", "can", "should", "would", "possibly", "optionally")


def hand_features(texts):
    """A few transparent numbers per text (no fitting, so nothing can leak): length, digits, security cue words, vague terms, shall/must, negation, soft modals."""
    from agents.requirement_agent.api.vague import vague_term_spans
    rows = []
    for t in texts:
        low = str(t).lower()
        words = low.split()
        rows.append([len(words), len(low), sum(ch.isdigit() for ch in low), len(security_cue_words(low)), len(vague_term_spans(low)),
                     int(any(w in ("shall", "must") for w in words)), sum(w in _NEGATION for w in words), sum(w in _MODAL for w in words), low.count(",") + low.count(";")])
    return np.asarray(rows, dtype=np.float32)


def _estimator(family, params, n_pos, n_neg):
    if family == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(learning_rate=0.1, subsample=0.8, colsample_bytree=0.5, tree_method="hist", eval_metric="logloss", random_state=SEED,
                             scale_pos_weight=(n_neg / max(n_pos, 1)), n_jobs=-1, **params)
    if family == "lightgbm":
        from lightgbm import LGBMClassifier
        return LGBMClassifier(learning_rate=0.1, subsample=0.8, subsample_freq=1, colsample_bytree=0.5, min_child_samples=10, class_weight="balanced",
                              random_state=SEED, n_jobs=-1, verbose=-1, **params)
    cls = RandomForestClassifier if family == "random_forest" else ExtraTreesClassifier
    return cls(class_weight="balanced_subsample" if family == "random_forest" else "balanced", random_state=SEED, n_jobs=-1, **params)


class TreeText(BaseEstimator, ClassifierMixin):
    """Texts -> features -> a tree model. `fit(texts, y)` / `predict(texts)` like the baselines; labels may be strings. Binary tasks only (all of ours are)."""

    def __init__(self, family="xgboost", features="emb", params=None):
        self.family, self.features, self.params = family, features, params

    def _x(self, texts, fit=False):
        texts = [str(t) for t in texts]
        parts = []
        if "tfidf" in self.features:
            if fit:
                self.tfidf_ = make_tfidf().fit(texts)  # fitted on the training texts only
            parts.append(sp.csr_matrix(self.tfidf_.transform(texts), dtype=np.float32))
        if "emb" in self.features:
            parts.append(sp.csr_matrix(embed(texts)))
        if self.features.endswith("hand"):
            parts.append(sp.csr_matrix(hand_features(texts)))
        return sp.hstack(parts, format="csr") if len(parts) > 1 else parts[0]

    def fit(self, X, y):
        y = np.asarray(y)
        self.classes_ = np.array(sorted(set(y)), dtype=object)
        if len(self.classes_) != 2:
            raise ValueError("binary tasks only")
        codes = (y == self.classes_[1]).astype(int)
        self.model_ = _estimator(self.family, dict(self.params or {}), int(codes.sum()), int(len(codes) - codes.sum()))
        self.model_.fit(self._x(X, fit=True), codes)
        return self

    def predict_proba(self, X):
        return self.model_.predict_proba(self._x(X))

    def predict(self, X):
        return self.classes_[self.model_.predict(self._x(X)).astype(int)]


class Task:
    """One task: how to pick its rows, its label, the labels' order and the test slices (the same definitions as run_baselines)."""

    def __init__(self, name, file, subtask, labels, filt, y_fn, slices, cv=False):
        self.name, self.file, self.subtask, self.labels, self.filt, self.y_fn, self.slices, self.cv = name, file, subtask, labels, filt, y_fn, slices, cv

    def prep(self, df):
        df = df[self.filt(df)].reset_index(drop=True)
        return df.assign(y=self.y_fn(df))


def _tasks():
    def fr_slices(d):
        return {"pooled": np.ones(len(d), bool), "source=PROMISE": (d.source_dataset == "PROMISE").values, "source=FR_NFR": (d.source_dataset == "FR_NFR").values}

    def sec_slices(d):
        src = d.label_scheme.map(SECURITY_SOURCE)
        s = {"pooled": np.ones(len(d), bool)}
        s.update({f"source={v}": (src == v).values for v in ("PURE", "security_requirements", "PROMISE")})
        return s

    def amb_slices(d):
        fam = d.ambiguity_label_basis.map(basis_family)
        s = {"pooled": np.ones(len(d), bool), "basis=QuRE": (fam == "QuRE").values, "basis=ARTA_pooled": (fam == "ARTA").values}
        for ds in ("DS1", "DS2", "DS3", "DS4"):
            s[f"basis=ARTA_{ds}"] = d.ambiguity_label_basis.str.contains(f"_{ds}_").values
        return s

    return {
        "fr_nfr": Task("fr_nfr", FILES["fr_nfr"], "fr_nfr", ["FR", "NFR"], lambda d: d.requirement_type.isin(["FR", "NFR"]), lambda d: d.requirement_type.values, fr_slices, cv=True),
        "security": Task("nfr_subtype", FILES["nfr_subtype"], "security_binary", ["0", "1"], _security_filter, lambda d: d.security_label.values, sec_slices),
        "ambiguity": Task("ambiguity", FILES["ambiguity"], "ambiguity", ["defect", "ok"], lambda d: np.ones(len(d), bool), lambda d: d.ambiguity_label.values, amb_slices),
    }


def grid_for(family, full):
    return GRIDS[family] + (FULL_EXTRA[family] if full else [])


def develop(task, res, train, val, n_boot, families, features, full):
    """Tune on val only. Returns {(family, features): (fitted model, params, val macro-F1)}."""
    train, val = task.prep(train), task.prep(val)
    best = {}
    for family in families:
        for feat in features:
            top = None
            for params in grid_for(family, full):
                model = TreeText(family, feat, params).fit(list(train[TEXT]), train.y.values)
                score = M.classification_metrics(val.y, model.predict(list(val[TEXT])), task.labels)["macro_f1"]
                res.tuning.append({"subtask": task.subtask, "model": f"{family}+{feat}", "C": str(params), "val_score": round(float(score), 6)})
                if top is None or score > top[0] + 1e-12:  # ties keep the earlier (smaller) setting
                    top = (score, params, model)
            name = f"{family}+{feat}"
            best[(family, feat)] = (top[2], top[1], top[0])
            res.emit(task.subtask, "val", "pooled", name, val.y, top[2].predict(list(val[TEXT])), task.labels, n_boot, ci=False)
            print(f"   {task.subtask} {name}: val macro-F1 {top[0]:.4f} {top[1]}", flush=True)
    pick = max(best, key=lambda k: best[k][2])
    res.notes.append(f"[{task.subtask}] best tree model by validation macro-F1: {pick[0]}+{pick[1]} ({best[pick][2]:.4f})")
    return train, val, best


def cross_validate(task, res, train, val, best, n_boot):
    """FR/NFR only: the same CV slices and PROMISE leave-one-project-out as the baselines, for the chosen setting of each model."""
    both = pd.concat([train, val], ignore_index=True)
    real = (~both.group_id.str.endswith(":ungrouped") & ~both.group_id.str.endswith("_unknown")).values
    parts = {GROUPED_CV: both[real].reset_index(drop=True), STRATIFIED_CV: both[~real].reset_index(drop=True)}
    promise = both[(both.source_dataset == "PROMISE") & both.group_id.str.match(r"^PROMISE_P\d+$")].reset_index(drop=True)
    for (family, feat), (_, params, _) in best.items():
        name = f"{family}+{feat}"
        fp = lambda Xtr, ytr, Xte, family=family, feat=feat, params=params: TreeText(family, feat, params).fit(list(Xtr), ytr).predict(list(Xte))  # noqa: E731
        for cv_name, part in parts.items():
            if len(part) < MIN_CV_ROWS or part.y.nunique() < 2:
                continue
            pred = (M.grouped_cv_predictions(fp, part[TEXT], part.y, part.group_id.values) if cv_name == GROUPED_CV else M.stratified_cv_predictions(fp, part[TEXT], part.y))
            res.emit(task.subtask, "cv", cv_name, name, part.y, pred, task.labels, n_boot)
        out = M.leave_one_group_out(fp, promise[TEXT], promise.y, promise.group_id)
        res.emit(task.subtask, "lopo", "PROMISE_only_leave_one_project_out", name, np.concatenate([v[0] for v in out.values()]), np.concatenate([v[1] for v in out.values()]), task.labels, n_boot)


def final(task, res, best, n_boot):
    """The only place that reads the frozen test split (verified first). Every tree model is scored; none is chosen from it."""
    test = task.prep(da.load_test_for_final_evaluation(task.file))
    for (family, feat), (model, _, _) in best.items():
        pred = np.asarray(model.predict(list(test[TEXT])), dtype=object)
        for slice_name, mask in task.slices(test).items():
            mask = np.asarray(mask)
            res.emit(task.subtask, "test", slice_name, f"{family}+{feat}", test.y[mask], pred[mask], task.labels, n_boot)


def run_task(key, out, n_boot, families, features, full):
    task = _tasks()[key]
    res = Results(task.name)
    print(f"== {key}: development (train/val only)", flush=True)
    train, val, best = develop(task, res, da.load_task(task.file, ("train",)), da.load_task(task.file, ("val",)), n_boot, families, features, full)
    if task.cv:
        print(f"== {key}: cross-validation and leave-one-project-out (train+val)", flush=True)
        cross_validate(task, res, train, val, best, n_boot)
    print(f"== {key}: frozen test evaluation", flush=True)
    final(task, res, best, n_boot)
    return res


def write(results, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [r for res in results for r in res.metrics]
    df = pd.DataFrame(rows, columns=METRIC_COLS)
    df["value"] = pd.to_numeric(df["value"]).round(6)
    for c in ("ci_low", "ci_high"):
        df[c] = df[c].map(lambda v: "" if v == "" else round(float(v), 6))
    df.to_csv(out_dir / "tree_models_metrics.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    pd.DataFrame([r for res in results for r in res.tuning]).to_csv(out_dir / "tree_models_tuning.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    (out_dir / "tree_models_notes.txt").write_text("\n".join(n for res in results for n in res.notes) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--task", required=True, choices=["fr_nfr", "security", "ambiguity", "all"])
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--n-boot", type=int, default=M.N_BOOT)
    ap.add_argument("--quick", action="store_true", help="two feature sets and the first grid entries only (a fast look)")
    ap.add_argument("--full", action="store_true", help="the larger grid (600 trees too)")
    ap.add_argument("--families", default=",".join(FAMILIES))
    a = ap.parse_args(argv)
    families = tuple(f for f in a.families.split(",") if f in FAMILIES)
    features = QUICK_FEATURES if a.quick else FEATURES
    keys = ["fr_nfr", "security", "ambiguity"] if a.task == "all" else [a.task]
    results = [run_task(k, Path(a.out_dir), a.n_boot, families, features, a.full) for k in keys]
    write(results, Path(a.out_dir))
    print(f"wrote {Path(a.out_dir) / 'tree_models_metrics.csv'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
