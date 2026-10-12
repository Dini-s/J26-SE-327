"""Run the Component 1 baselines: FR/NFR, NFR subtype (security + PROMISE multi-label) and ambiguity.

    python -m evaluation.run_baselines --task fr_nfr|nfr_subtype|ambiguity|all

Two phases per task. `develop_*` loads train/val rows only (through `data_access.load_task`, which refuses the test split), tunes on val,
runs grouped cross-validation and leave-one-project-out. `final_*` is the only code that loads the frozen test rows, and only after
`data_access` has verified frozen_test_ids.csv / the task file against manifest.json. No LLM calls, no synthetic data, seed 327.
Models are saved to models/component1/part_a_experiments/<fr_nfr|security_and_subtype|ambiguity>/ (override with --models-dir).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from agents.requirement_agent.ambiguity import RULE_NAME, WeakWordRuleModel, weak_words_from_evidence
from agents.requirement_agent.classifier import MODEL_KINDS, build_model, tune_and_fit
from agents.requirement_agent.features import SEED
from evaluation import data_access as da
from evaluation import metrics as M

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "evaluation" / "component1" / "results"
# Models are saved under part_a_experiments/<group>/. The four models the agent loads live in models/component1/part_a_active/; copy them
# there by hand after a run (the agent never reads part_a_experiments/).
DEFAULT_MODELS = PROJECT_ROOT / "models" / "component1" / "part_a_experiments"
MODEL_GROUPS = (("fr_nfr_", "fr_nfr"), ("nfr_subtype_", "security_and_subtype"), ("ambiguity_", "ambiguity"))
SUBTYPES = ["A", "FT", "L", "LF", "MN", "O", "PE", "PO", "SC", "SE", "US"]
FILES = {"fr_nfr": "classification_fr_nfr", "nfr_subtype": "classification_nfr_subtype", "ambiguity": "ambiguity"}
METRIC_COLS = ["task", "subtask", "evaluation", "slice", "model", "metric", "cls", "value", "ci_low", "ci_high", "n_rows"]
TEXT = "requirement_text_normalized"
GROUPED_CV = "grouped_cv:rows_with_real_groups"
STRATIFIED_CV = "stratified_cv:rows_without_groups"
MIN_CV_ROWS = 50
SECURITY_SOURCE = {"PURE_security_reliability": "PURE", "SECURITY_BINARY": "security_requirements", "PROMISE_NICE_11": "PROMISE"}


def order_key(record_id):
    return hashlib.sha256(f"{SEED}|{record_id}".encode()).hexdigest()


def effective_groups(df):
    """group_id, except ungrouped rows (one shared dummy group) become one group per row so cross-validation stays usable."""
    return np.where(df.group_id.str.endswith(":ungrouped") | df.group_id.str.endswith("_unknown"), "row:" + df.record_id, df.group_id).astype(object)


def describe(text):
    """Short pattern flags for the error files (descriptive only; never used to tune anything)."""
    n = len(text.split())
    flags = ["very short (<10 words)" if n < 10 else "long (>40 words)" if n > 40 else f"{n} words"]
    low = text.lower()
    flags.append("has shall/must" if any(w in low.split() or f"{w} " in low for w in ("shall", "must")) else "no shall/must")
    if any(ch.isdigit() for ch in text):
        flags.append("contains digits")
    if " and " in low or ";" in low:
        flags.append("compound")
    if any(w in low for w in (" not ", " no ", "n't ")):
        flags.append("negation")
    return "; ".join(flags)


class Results:
    def __init__(self, task):
        self.task, self.metrics, self.confusion, self.tuning, self.errors, self.notes = task, [], [], [], [], []

    def emit(self, subtask, evaluation, slice_, model, y_true, y_pred, labels, n_boot, ci=True):
        y_true, y_pred = list(y_true), list(y_pred)
        if not y_true:
            return
        m = M.classification_metrics(y_true, y_pred, labels)
        bounds = M.bootstrap_ci(y_true, y_pred, labels, n_boot=n_boot) if ci else {}
        base = dict(task=self.task, subtask=subtask, evaluation=evaluation, slice=slice_, model=model, n_rows=len(y_true))
        for k in ("accuracy", "macro_precision", "macro_recall", "macro_f1"):
            lo, hi = bounds.get(k, ("", ""))
            self.metrics.append({**base, "metric": k, "cls": "", "value": m[k], "ci_low": lo, "ci_high": hi})
        for l in labels:
            for k in ("precision", "recall", "f1"):
                lo, hi = bounds.get(f"{k}[{l}]", ("", ""))
                self.metrics.append({**base, "metric": k, "cls": l, "value": m[f"{k}[{l}]"], "ci_low": lo, "ci_high": hi})
            self.metrics.append({**base, "metric": "support", "cls": l, "value": m[f"support[{l}]"], "ci_low": "", "ci_high": ""})
        if evaluation in ("test", "cross_source"):
            cm = M.confusion_matrix(y_true, y_pred, labels)
            for i, a in enumerate(labels):
                for j, b in enumerate(labels):
                    self.confusion.append({"subtask": subtask, "evaluation": evaluation, "slice": slice_, "model": model, "cls": "", "true": a, "predicted": b, "count": int(cm[i, j])})

    def emit_multilabel(self, subtask, evaluation, slice_, model, Y_true, Y_pred, classes, n_boot, ci=True):
        m = M.multilabel_metrics(Y_true, Y_pred, classes)
        bounds = M.multilabel_bootstrap_ci(Y_true, Y_pred, classes, n_boot=n_boot) if ci else {}
        base = dict(task=self.task, subtask=subtask, evaluation=evaluation, slice=slice_, model=model, n_rows=len(Y_true))
        if evaluation == "test":  # one 2x2 table per class (true 1/0 x predicted 1/0)
            Yt, Yp = np.asarray(Y_true), np.asarray(Y_pred)
            for j, c in enumerate(classes):
                for a in (1, 0):
                    for b in (1, 0):
                        self.confusion.append({"subtask": subtask, "evaluation": evaluation, "slice": slice_, "model": model, "cls": c, "true": str(a), "predicted": str(b),
                                               "count": int(((Yt[:, j] == a) & (Yp[:, j] == b)).sum())})
        for k, v in m.items():
            metric, _, cls = k.partition("[")
            lo, hi = bounds.get(k, ("", ""))
            self.metrics.append({**base, "metric": metric, "cls": cls.rstrip("]"), "value": v, "ci_low": lo, "ci_high": hi})

    def write(self, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        def dump(rows, name, cols=None):
            df = pd.DataFrame(rows, columns=cols) if cols else pd.DataFrame(rows)
            if "value" in df:
                df["value"] = pd.to_numeric(df["value"]).round(6)
            for c in ("ci_low", "ci_high"):
                if c in df:
                    df[c] = df[c].map(lambda v: "" if v == "" else round(float(v), 6))
            df.to_csv(out_dir / name, index=False, encoding="utf-8-sig", lineterminator="\n")
        dump(self.metrics, f"{self.task}_metrics.csv", METRIC_COLS)
        dump(self.confusion, f"{self.task}_confusion.csv")
        dump(self.tuning, f"{self.task}_tuning.csv")
        dump(self.errors, f"{self.task}_errors.csv")
        (out_dir / f"{self.task}_notes.txt").write_text("\n".join(self.notes) + "\n", encoding="utf-8")


def model_group(name):
    """Subfolder of the models directory for a model file name (fr_nfr, security_and_subtype or ambiguity)."""
    for prefix, group in MODEL_GROUPS:
        if name.startswith(prefix):
            return group
    raise ValueError(f"no model group for {name!r}")


def save_model(models_dir, name, payload):
    target = models_dir / model_group(name)
    target.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, target / f"{name}.joblib")


# ---------------------------------------------------------------------------------------------------------------------------
# single-label experiments (FR/NFR, security, ambiguity)
# ---------------------------------------------------------------------------------------------------------------------------
class SingleLabel:
    """Develop on train/val; evaluate on test later. `slices(df)` maps a slice name to a boolean mask over df rows."""

    def __init__(self, res, subtask, labels, kinds, filt, y_fn, rule, slices, rule_factory=None, rule_kind="rules"):
        self.res, self.subtask, self.labels, self.kinds = res, subtask, labels, kinds
        self.filt, self.y_fn, self.rule, self.slices, self.rule_factory = filt, y_fn, rule, slices, rule_factory
        self.rule_kind = rule_kind
        self.models, self.C, self.val_score = {}, {}, {}

    def prep(self, df):
        df = df[self.filt(df)].reset_index(drop=True)
        return df.assign(y=self.y_fn(df))

    def make(self, kind, C):
        if self.rule_factory and kind == self.rule_kind:
            return self.rule_factory()
        return build_model(kind, C if C is not None else 1.0, rule=self.rule)

    def develop(self, train, val, n_boot):
        train, val = self.prep(train), self.prep(val)
        self.train, self.val = train, val
        for kind in self.kinds:
            if self.rule_factory and kind == self.rule_kind:
                model = self.rule_factory().fit(list(train[TEXT]), train.y)
                C, rows = None, [{"model": kind, "C": "", "val_score": ""}]
            else:
                model, C, rows = tune_and_fit(kind, train[TEXT], train.y, val[TEXT], val.y, rule=self.rule)
            pred = model.predict(list(val[TEXT]))
            self.models[kind], self.C[kind] = model, C
            self.val_score[kind] = M.classification_metrics(val.y, pred, self.labels)["macro_f1"]
            self.res.tuning += [{"subtask": self.subtask, **r} for r in rows]
            self.res.emit(self.subtask, "val", "pooled", kind, val.y, pred, self.labels, n_boot, ci=False)
        self.best = max(self.kinds, key=lambda k: (self.val_score[k], -self.kinds.index(k)))
        self.res.notes.append(f"[{self.subtask}] best model by validation macro-F1: {self.best} ({self.val_score[self.best]:.4f})")

    def fit_predict(self, kind):
        C = self.C[kind]
        def fp(Xtr, ytr, Xte):
            if self.rule_factory and kind == self.rule_kind:
                return self.rule_factory().fit(list(Xtr), ytr).predict(list(Xte))
            return self.make(kind, C).fit(list(Xtr), ytr).predict(list(Xte))
        return fp

    def cross_validate(self, n_boot, lopo_filter=None):
        """5-fold CV on train+val, reported as two separate slices: grouped CV on rows with real project/document groups, and plain stratified
        CV on rows without groups. The held-out test split is never involved."""
        both = pd.concat([self.train, self.val], ignore_index=True)
        real = (~both.group_id.str.endswith(":ungrouped") & ~both.group_id.str.endswith("_unknown")).values
        parts = {GROUPED_CV: both[real].reset_index(drop=True), STRATIFIED_CV: both[~real].reset_index(drop=True)}
        for kind in self.kinds:
            if kind in ("rules", self.rule_kind):
                continue
            for name, part in parts.items():
                if len(part) < MIN_CV_ROWS or part.y.nunique() < 2:
                    continue
                if name == GROUPED_CV:
                    pred = M.grouped_cv_predictions(self.fit_predict(kind), part[TEXT], part.y, part.group_id.values)
                else:
                    pred = M.stratified_cv_predictions(self.fit_predict(kind), part[TEXT], part.y)
                self.res.emit(self.subtask, "cv", name, kind, part.y, pred, self.labels, n_boot)
        for name, part in parts.items():
            if len(part) < MIN_CV_ROWS or part.y.nunique() < 2:
                self.res.notes.append(f"[{self.subtask}] {name} not run: only {len(part)} rows of that kind in train+val.")
        if lopo_filter is not None:
            sub = both[lopo_filter(both)].reset_index(drop=True)
            for kind in self.kinds:
                if kind in ("rules", self.rule_kind):
                    continue
                out = M.leave_one_group_out(self.fit_predict(kind), sub[TEXT], sub.y, sub.group_id)
                yt = np.concatenate([v[0] for v in out.values()])
                yp = np.concatenate([v[1] for v in out.values()])
                self.res.emit(self.subtask, "lopo", "PROMISE_only_leave_one_project_out", kind, yt, yp, self.labels, n_boot)
                for g, (a, b) in out.items():
                    self.res.emit(self.subtask, "lopo", f"held_out={g}", kind, a, b, self.labels, n_boot, ci=False)

    def final(self, test, n_boot, models_dir, save):
        test = self.prep(test)
        self.test = test
        preds = {}
        for kind in self.kinds:
            pred = self.models[kind].predict(list(test[TEXT]))
            preds[kind] = pred
            for name, mask in self.slices(test).items():
                mask = np.asarray(mask)
                self.res.emit(self.subtask, "test", name, kind, test.y[mask], np.asarray(pred, dtype=object)[mask], self.labels, n_boot)
        self.preds = preds
        wrong = test[np.asarray(preds[self.best], dtype=object) != test.y.values]
        picked = wrong.assign(_o=wrong.record_id.map(order_key)).sort_values("_o", kind="stable").head(30)
        for r in picked.itertuples():
            self.res.errors.append({"subtask": self.subtask, "model": self.best, "record_id": r.record_id, "source_dataset": r.source_dataset, "group_id": r.group_id,
                                    "text": getattr(r, "requirement_text_original", "")[:400].strip(), "true": r.y,
                                    "predicted": preds[self.best][list(test.record_id).index(r.record_id)], "pattern_note": describe(r.requirement_text_normalized)})
        self.res.notes.append(f"[{self.subtask}] {len(wrong)} of {len(test)} test rows misclassified by {self.best}; 30 sampled in errors file")
        if save:
            for kind in self.kinds:
                payload = {"model": self.models[kind], "kind": kind, "C": self.C[kind], "labels": self.labels, "seed": SEED, "fitted_on": "train split only"}
                save_model(models_dir, f"{self.res.task}_{self.subtask}_{kind}", payload)


def run_fr_nfr(out, models_dir, n_boot, save):
    res = Results("fr_nfr")
    exp = SingleLabel(res, "fr_nfr", ["FR", "NFR"], list(MODEL_KINDS), lambda d: d.requirement_type.isin(["FR", "NFR"]), lambda d: d.requirement_type.values, "fr_nfr",
                      lambda d: {"pooled": np.ones(len(d), bool), "source=PROMISE": (d.source_dataset == "PROMISE").values,
                                 "source=FR_NFR": (d.source_dataset == "FR_NFR").values})
    exp.develop(da.load_task(FILES["fr_nfr"], ("train",)), da.load_task(FILES["fr_nfr"], ("val",)), n_boot)
    exp.cross_validate(n_boot, lopo_filter=lambda d: (d.source_dataset == "PROMISE") & d.group_id.str.match(r"^PROMISE_P\d+$"))
    res.notes.append("[fr_nfr] cross-validation is reported in two slices: grouped CV on PROMISE rows (grouped by project) and stratified CV on FR_NFR rows (no project information). "
                     "PROMISE-only leave-one-project-out (train on the other PROMISE projects only) is the domain-shift estimate. Per-project macro-F1 averages only the classes present in that project, so single-class projects (P11-P13) score a trivial 1.0 and should be ignored; use the pooled LOPO row.")
    return res, exp


def final_fr_nfr(res, exp, out, models_dir, n_boot, save):
    exp.final(da.load_test_for_final_evaluation(FILES["fr_nfr"]), n_boot, models_dir, save)


def _security_filter(d):
    return d.security_label.isin(["0", "1"]) & d.label_scheme.isin(list(SECURITY_SOURCE))


def run_security(out, models_dir, n_boot, save):
    res = Results("nfr_subtype")
    def slices(d):
        src = d.label_scheme.map(SECURITY_SOURCE)
        s = {"pooled": np.ones(len(d), bool)}
        s.update({f"source={v}": (src == v).values for v in ("PURE", "security_requirements", "PROMISE")})
        return s
    exp = SingleLabel(res, "security_binary", ["0", "1"], list(MODEL_KINDS), _security_filter, lambda d: d.security_label.values, "security", slices)
    exp.develop(da.load_task(FILES["nfr_subtype"], ("train",)), da.load_task(FILES["nfr_subtype"], ("val",)), n_boot)
    exp.cross_validate(n_boot)
    res.notes.append("[security_binary] trained on all three label sources pooled; reported per source and pooled. PURE dominates the pooled number; "
                     "PURE validation is a single document (HIPAA) and PURE test has only 32 security positives, so read the CIs.")
    return res, exp


# ---------------------------------------------------------------------------------------------------------------------------
# multi-label PROMISE subtypes
# ---------------------------------------------------------------------------------------------------------------------------
class MultiLabel:
    def __init__(self, res):
        self.res, self.classes, self.subtask = res, SUBTYPES, "promise_subtype_multilabel"
        self.models, self.C, self.val_score = {}, {}, {}

    def prep(self, df):
        df = df[(df.label_scheme == "PROMISE_NICE_11") & (df.nfr_subtype != "")].reset_index(drop=True)
        Y = np.array([[1 if c in set(v.split("|")) else 0 for c in self.classes] for v in df.nfr_subtype], dtype=int)
        return df, Y

    def develop(self, train, val, n_boot):
        (self.train, self.Ytr), (self.val, self.Yva) = self.prep(train), self.prep(val)
        for kind in MODEL_KINDS:
            model, C, rows = tune_and_fit(kind, self.train[TEXT], self.Ytr, self.val[TEXT], self.Yva, multilabel_classes=self.classes)
            self.models[kind], self.C[kind] = model, C
            pred = np.asarray(model.predict(list(self.val[TEXT])))
            self.val_score[kind] = M.multilabel_metrics(self.Yva, pred, self.classes)["micro_f1"]
            self.res.tuning += [{"subtask": self.subtask, **r} for r in rows]
            self.res.emit_multilabel(self.subtask, "val", "pooled", kind, self.Yva, pred, self.classes, n_boot, ci=False)
        self.best = max(MODEL_KINDS, key=lambda k: (self.val_score[k], -MODEL_KINDS.index(k)))
        self.res.notes.append(f"[{self.subtask}] best model by validation micro-F1: {self.best} ({self.val_score[self.best]:.4f}); "
                              f"{len(self.train)} train / {len(self.val)} val rows with a non-empty subtype label (rows with an empty subtype are excluded, not treated as all-zero)")

    def cross_validate(self, n_boot):
        both = pd.concat([self.train, self.val], ignore_index=True)
        Y = np.vstack([self.Ytr, self.Yva])
        real = (~both.group_id.str.endswith(":ungrouped") & ~both.group_id.str.endswith("_unknown")).values
        if (~real).sum() >= MIN_CV_ROWS:
            raise RuntimeError("ungrouped PROMISE rows are numerous enough to need a stratified CV slice; extend cross_validate")
        self.res.notes.append(f"[{self.subtask}] grouped CV uses the {int(real.sum())} rows with a real project group; {int((~real).sum())} ungrouped rows are left out of CV "
                              "(too few for a separate stratified slice).")
        both, Y = both[real].reset_index(drop=True), Y[real]
        groups = both.group_id.values
        strat = np.array([c.split("|")[0] if c else "" for c in both.nfr_subtype], dtype=object)
        for kind in MODEL_KINDS:
            if kind == "rules":
                continue
            pred = np.zeros_like(Y)
            for tr, te in M.grouped_folds(strat, groups):
                model = build_model(kind, self.C[kind] or 1.0, multilabel_classes=self.classes).fit(list(both[TEXT].values[tr]), Y[tr])
                pred[te] = model.predict(list(both[TEXT].values[te]))
            self.res.emit_multilabel(self.subtask, "cv", GROUPED_CV, kind, Y, pred, self.classes, n_boot)

    def final(self, test, n_boot, models_dir, save):
        test, Yte = self.prep(test)
        counts = Yte.sum(axis=0)
        self.res.notes.append(f"[{self.subtask}] WARNING: test has only {len(test)} rows; per-class test support = {dict(zip(self.classes, counts.tolist()))}. "
                              "Classes with support < 5 are unreliable; treat the cross-validation rows as the main evidence.")
        preds = {}
        for kind in MODEL_KINDS:
            pred = np.asarray(self.models[kind].predict(list(test[TEXT])))
            preds[kind] = pred
            self.res.emit_multilabel(self.subtask, "test", "pooled", kind, Yte, pred, self.classes, n_boot)
        P = preds[self.best]
        wrong = np.where((P != Yte).any(axis=1))[0]
        order = sorted(wrong, key=lambda i: order_key(test.record_id[i]))[:30]
        for i in order:
            self.res.errors.append({"subtask": self.subtask, "model": self.best, "record_id": test.record_id[i], "source_dataset": test.source_dataset[i], "group_id": test.group_id[i],
                                    "text": test.requirement_text_original[i][:400].strip(), "true": "|".join(c for c, v in zip(self.classes, Yte[i]) if v),
                                    "predicted": "|".join(c for c, v in zip(self.classes, P[i]) if v), "pattern_note": describe(test[TEXT][i])})
        self.res.notes.append(f"[{self.subtask}] {len(wrong)} of {len(test)} test rows have at least one wrong label under {self.best}")
        if save:
            for kind in MODEL_KINDS:
                save_model(models_dir, f"nfr_subtype_{self.subtask}_{kind}", {"model": self.models[kind], "kind": kind, "C": self.C[kind], "classes": self.classes, "seed": SEED, "fitted_on": "train split only"})


# ---------------------------------------------------------------------------------------------------------------------------
# ambiguity
# ---------------------------------------------------------------------------------------------------------------------------
def basis_family(basis):
    return "QuRE" if basis.startswith("QuRE") else "ARTA"


def run_ambiguity(out, models_dir, n_boot, save):
    res = Results("ambiguity")
    train, val = da.load_task(FILES["ambiguity"], ("train",)), da.load_task(FILES["ambiguity"], ("val",))
    kinds = ["majority", RULE_NAME, "tfidf_lr", "emb_lr"]
    weak = weak_words_from_evidence(train[train.ambiguity_label_basis.str.startswith("QuRE")].smell_evidence)
    res.notes.append(f"[ambiguity] {RULE_NAME}: defect if the text contains any of the {len(weak)} QuRE weak words (collected from QuRE train rows only).")
    factory = lambda: WeakWordRuleModel(weak_words=weak)  # noqa: E731

    def slices(d):
        fam = d.ambiguity_label_basis.map(basis_family)
        s = {"pooled": np.ones(len(d), bool), "basis=QuRE": (fam == "QuRE").values, "basis=ARTA_pooled": (fam == "ARTA").values}
        for ds in ("DS1", "DS2", "DS3", "DS4"):
            s[f"basis=ARTA_{ds}"] = d.ambiguity_label_basis.str.contains(f"_{ds}_").values
        return s

    exp = SingleLabel(res, "ambiguity", ["defect", "ok"], kinds, lambda d: np.ones(len(d), bool), lambda d: d.ambiguity_label.values, "none", slices, rule_factory=factory, rule_kind=RULE_NAME)
    exp.develop(train, val, n_boot)
    exp.cross_validate(n_boot)
    # cross-source models: trained on one family's train rows, tuned on that family's val rows
    cross = {}
    for src in ("QuRE", "ARTA"):
        tr = train[train.ambiguity_label_basis.map(basis_family) == src]
        va = val[val.ambiguity_label_basis.map(basis_family) == src]
        for kind in ("majority", "tfidf_lr", "emb_lr"):
            model, C, rows = tune_and_fit(kind, tr[TEXT], tr.ambiguity_label.values, va[TEXT], va.ambiguity_label.values)
            cross[(src, kind)] = model
            res.tuning += [{"subtask": f"cross_source_train_{src}", **r} for r in rows]
    exp.cross = cross
    res.notes.append("[ambiguity] CAUTION: ARTA labels are derived from smell-term columns and QuRE labels are human 'defect' judgements; the label definitions differ, "
                     "so cross-source numbers measure transfer between two definitions, not only domain shift. ARTA labels come from smell-term columns, which the QuRE weak-word rule does not use.")
    return res, exp


def final_ambiguity(res, exp, out, models_dir, n_boot, save):
    test = da.load_test_for_final_evaluation(FILES["ambiguity"])
    exp.final(test, n_boot, models_dir, save)
    t = exp.prep(test)
    fam = t.ambiguity_label_basis.map(basis_family)
    for (src, kind), model in sorted(exp.cross.items()):
        for tgt in ("QuRE", "ARTA"):
            sub = t[fam == tgt]
            pred = model.predict(list(sub[TEXT]))
            res.emit("ambiguity_cross_source", "cross_source", f"train={src}->test={tgt}", kind, sub.y, pred, ["defect", "ok"], n_boot)
    if save:
        for (src, kind), model in sorted(exp.cross.items()):
            save_model(models_dir, f"ambiguity_cross_train_{src}_{kind}", {"model": model, "kind": kind, "trained_on_family": src, "seed": SEED, "fitted_on": "train split only"})


# ---------------------------------------------------------------------------------------------------------------------------
NL = chr(10)
SUMMARY_METRICS = ["macro_f1", "micro_f1", "macro_precision", "macro_recall", "accuracy", "micro_precision", "micro_recall"]


def _ci(r):
    return f"[{float(r.ci_low):.3f}, {float(r.ci_high):.3f}]" if r.ci_low != "" else ""


def build_summary(out_dir):
    """RESULTS.md, built only from the saved CSVs: summary tables per evaluation type (test, cross-source, grouped CV, stratified CV,
    leave-one-project-out, val), then per-class results and confusion matrices on the frozen test split."""
    lines = ["# Component 1 baseline results", "",
             "Generated by `python -m evaluation.run_baselines`. Seed 327. Test numbers are on the frozen test split (SHA-256 verified); "
             "95 % bootstrap CIs (1000 resamples) in brackets; `n` is the number of rows scored. Models were fitted on the train split only and tuned on val. "
             "Frozen-test, grouped-CV, stratified-CV and leave-one-project-out results are in separate tables and must not be compared as if they were the same estimate.", ""]
    rerun = out_dir / "rerun_note.md"
    if rerun.exists():
        lines += [rerun.read_text(encoding="utf-8").strip(), ""]
    for task in ("fr_nfr", "nfr_subtype", "ambiguity"):
        path = out_dir / f"{task}_metrics.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        conf = pd.read_csv(out_dir / f"{task}_confusion.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
        if "cls" not in conf.columns:
            conf["cls"] = ""
        notes = (out_dir / f"{task}_notes.txt").read_text(encoding="utf-8") if (out_dir / f"{task}_notes.txt").exists() else ""
        lines += [f"## {task}", "", "```", notes.strip(), "```", ""]
        for sub in sorted(df.subtask.unique()):
            d = df[(df.subtask == sub) & (df.cls == "") & df.metric.isin(SUMMARY_METRICS)]
            titles = {"test": "frozen test", "cross_source": "cross-source (frozen test)", "lopo": "PROMISE-only leave-one-project-out (train+val)", "val": "validation (used for tuning)"}
            blocks = [(ev, titles[ev], d[d.evaluation == ev]) for ev in ("test", "cross_source")]
            cv = d[d.evaluation == "cv"]
            blocks += [("cv", f"{sl.split(':')[0].replace('_', ' ')} on train+val - {sl.split(':')[1].replace('_', ' ')}", cv[cv.slice == sl]) for sl in sorted(cv.slice.unique())]
            blocks += [(ev, titles[ev], d[d.evaluation == ev]) for ev in ("lopo", "val")]
            for ev, title, e in blocks:
                e = e[~e.slice.str.startswith("held_out")] if ev == "lopo" else e
                if e.empty:
                    continue
                lines += [f"### {sub} - {title}", "", "| slice | model | metric | value | 95% CI | n |", "|---|---|---|---|---|---|"]
                lines += [f"| {r.slice} | {r.model} | {r.metric} | {float(r.value):.3f} | {_ci(r)} | {r.n_rows} |" for r in e.itertuples()]
                lines.append("")
            # per-class results on the frozen test split
            pc = df[(df.subtask == sub) & (df.evaluation == "test") & (df.cls != "") & df.metric.isin(["precision", "recall", "f1", "support"])]
            if not pc.empty:
                lines += [f"### {sub} - per-class results (frozen test)", "", "| slice | model | class | precision | recall | F1 | support |", "|---|---|---|---|---|---|---|"]
                for (sl, mod, cl), g in pc.groupby(["slice", "model", "cls"], sort=False):
                    g = g.set_index("metric")
                    cells = [f"{float(g.loc[m].value):.3f} {_ci(g.loc[m])}".strip() for m in ("precision", "recall", "f1")]
                    lines.append(f"| {sl} | {mod} | {cl} | {cells[0]} | {cells[1]} | {cells[2]} | {int(float(g.loc['support'].value))} |")
                lines.append("")
            cf = conf[(conf.subtask == sub) & (conf.evaluation == "test")]
            if not cf.empty and (cf.cls == "").all():
                lines += [f"### {sub} - confusion matrices (frozen test; rows = true class, columns = predicted)", ""]
                for sl, g in cf.groupby("slice", sort=False):
                    labs = list(dict.fromkeys(g.true))
                    head = "| model | " + " | ".join(f"{a}->{b}" for a in labs for b in labs) + " |"
                    lines += [f"slice `{sl}`", "", head, "|" + "---|" * (1 + len(labs) ** 2)]
                    for mod, gm in g.groupby("model", sort=False):
                        cnt = {(r.true, r.predicted): r.count for r in gm.itertuples()}
                        lines.append(f"| {mod} | " + " | ".join(cnt[(a, b)] for a in labs for b in labs) + " |")
                    lines.append("")
            elif not cf.empty:
                lines += [f"### {sub} - per-class 2x2 counts (frozen test; positive = label present)", "", "| model | class | TP | FN | FP | TN |", "|---|---|---|---|---|---|"]
                for (mod, cl), g in cf.groupby(["model", "cls"], sort=False):
                    c = {(r.true, r.predicted): r.count for r in g.itertuples()}
                    lines.append(f"| {mod} | {cl} | {c[('1', '1')]} | {c[('1', '0')]} | {c[('0', '1')]} | {c[('0', '0')]} |")
                lines.append("")
    (out_dir / "RESULTS.md").write_text(NL.join(lines) + NL, encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--task", required=True, choices=["fr_nfr", "nfr_subtype", "ambiguity", "all"])
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--models-dir", default=str(DEFAULT_MODELS))
    ap.add_argument("--no-save-models", action="store_true")
    ap.add_argument("--n-boot", type=int, default=M.N_BOOT)
    a = ap.parse_args(argv)
    out, models_dir, save = Path(a.out_dir), Path(a.models_dir), not a.no_save_models
    tasks = ["fr_nfr", "nfr_subtype", "ambiguity"] if a.task == "all" else [a.task]

    for task in tasks:
        print(f"== {task}: development (train/val only)", flush=True)
        if task == "fr_nfr":
            res, exp = run_fr_nfr(out, models_dir, a.n_boot, save)
            print("== frozen test evaluation", flush=True)
            final_fr_nfr(res, exp, out, models_dir, a.n_boot, save)
        elif task == "nfr_subtype":
            res, exp = run_security(out, models_dir, a.n_boot, save)
            ml = MultiLabel(res)
            ml.develop(da.load_task(FILES["nfr_subtype"], ("train",)), da.load_task(FILES["nfr_subtype"], ("val",)), a.n_boot)
            ml.cross_validate(a.n_boot)
            print("== frozen test evaluation", flush=True)
            test = da.load_test_for_final_evaluation(FILES["nfr_subtype"])
            exp.final(test, a.n_boot, models_dir, save)
            ml.final(test, a.n_boot, models_dir, save)
            reliability_pos = {s: int((da.load_task(FILES["nfr_subtype"], (s,)).reliability_label == "1").sum()) for s in ("train", "val")}
            res.notes.append(f"[reliability] too sparse to evaluate: no metric reported (positives in train/val: {reliability_pos}; test count not examined).")
        else:
            res, exp = run_ambiguity(out, models_dir, a.n_boot, save)
            print("== frozen test evaluation", flush=True)
            final_ambiguity(res, exp, out, models_dir, a.n_boot, save)
        res.write(out)
        print(f"   wrote {out / (task + '_metrics.csv')}", flush=True)
    build_summary(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
