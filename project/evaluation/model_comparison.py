"""One table of every Component 1 Part A model: accuracy and macro-F1 on the frozen test split, which model is best, and which one the agent loads.

    python -m evaluation.model_comparison

Reads only the result files that already exist (fr_nfr / nfr_subtype / ambiguity _metrics.csv from `run_baselines`, and tree_models_metrics.csv from
`tree_models_eval`); it trains and evaluates nothing. Writes MODEL_COMPARISON.md, model_comparison.csv and model_comparison.xlsx next to them.

"Best" is chosen by VALIDATION macro-F1, never by the test numbers. Accuracy is shown because it was asked for, next to macro-F1, because accuracy alone misleads on
imbalanced tasks (security: always answering "not security" is already 95 % accurate).
"""
import sys
from pathlib import Path

import pandas as pd

from evaluation.run_baselines import DEFAULT_OUT

TASKS = (  # (title, metrics file, subtask, label for the table)
    ("FR vs NFR", "fr_nfr_metrics.csv", "fr_nfr"),
    ("Security flag", "nfr_subtype_metrics.csv", "security_binary"),
    ("Ambiguity (ok / defect)", "ambiguity_metrics.csv", "ambiguity"),
)
AGENT = {"FR vs NFR": {"emb_lr"}, "Security flag": {"rules"}, "Ambiguity (ok / defect)": {"tfidf_lr", "qure_weak_word_rule"}}
FEATURES = {"majority": "none (most common class)", "rules": "hand-written keyword rules", "qure_weak_word_rule": "QuRE weak-word list", "tfidf_lr": "TF-IDF",
            "tfidf_svm": "TF-IDF", "emb_lr": "MiniLM embeddings"}
NAMES = {"majority": "Majority class", "rules": "Keyword rules", "qure_weak_word_rule": "QuRE weak-word rule", "tfidf_lr": "Logistic Regression", "tfidf_svm": "Linear SVM",
         "emb_lr": "Logistic Regression"}
FAMILY = {"xgboost": "XGBoost", "lightgbm": "LightGBM", "random_forest": "Random Forest", "extra_trees": "Extra Trees"}
FEAT = {"tfidf": "TF-IDF", "emb": "MiniLM embeddings", "tfidf_emb": "TF-IDF + MiniLM embeddings", "emb_hand": "MiniLM embeddings + hand features"}
ORDER = ["majority", "rules", "qure_weak_word_rule", "tfidf_lr", "tfidf_svm", "emb_lr"]
COLUMNS = ["Task", "Model", "Features", "Accuracy", "Accuracy 95% CI", "Macro-F1", "Macro-F1 95% CI", "Validation macro-F1", "PROMISE leave-one-project-out macro-F1", "Test rows",
           "Used by the agent", "Best (by validation)"]


def describe(model):
    """(algorithm, features) in words for a model id such as `tfidf_lr` or `xgboost+tfidf_emb`."""
    if "+" in model:
        fam, feat = model.split("+", 1)
        return FAMILY.get(fam, fam), FEAT.get(feat, feat)
    return NAMES.get(model, model), FEATURES.get(model, "")


def _metric(df, model, metric, evaluation, slice_):
    r = df[(df.model == model) & (df.evaluation == evaluation) & (df.slice == slice_) & (df.metric == metric) & (df.cls == "")]
    return r.iloc[0] if len(r) else None


def _ci(r):
    return f"[{float(r.ci_low):.3f}, {float(r.ci_high):.3f}]" if r is not None and r.ci_low != "" else ""


def load(path):
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False) if Path(path).exists() else pd.DataFrame()


def collect(out_dir):
    """Rows of the comparison (a list of dicts keyed by COLUMNS), best by validation macro-F1 marked per task."""
    out_dir = Path(out_dir)
    trees = load(out_dir / "tree_models_metrics.csv")
    rows = []
    for title, file, sub in TASKS:
        base = load(out_dir / file)
        if base.empty:
            continue
        frames = [base[base.subtask == sub]]
        if not trees.empty:
            frames.append(trees[trees.subtask == sub])
        df = pd.concat(frames, ignore_index=True)
        models = [m for m in ORDER if m in set(df.model)] + sorted({m for m in df.model if "+" in m}, key=lambda m: (list(FAMILY).index(m.split("+")[0]) if m.split("+")[0] in FAMILY else 9, m))
        task_rows = []
        for m in models:
            acc, f1 = _metric(df, m, "accuracy", "test", "pooled"), _metric(df, m, "macro_f1", "test", "pooled")
            if acc is None:
                continue
            val, lopo = _metric(df, m, "macro_f1", "val", "pooled"), _metric(df, m, "macro_f1", "lopo", "PROMISE_only_leave_one_project_out")
            algo, feat = describe(m)
            task_rows.append({"Task": title, "Model": algo, "Features": feat, "Accuracy": float(acc.value), "Accuracy 95% CI": _ci(acc), "Macro-F1": float(f1.value), "Macro-F1 95% CI": _ci(f1),
                              "Validation macro-F1": float(val.value) if val is not None else None, "PROMISE leave-one-project-out macro-F1": float(lopo.value) if lopo is not None else None,
                              "Test rows": int(acc.n_rows), "Used by the agent": "yes" if m in AGENT[title] else "", "Best (by validation)": "", "_id": m})
        scored = [r for r in task_rows if r["Validation macro-F1"] is not None and r["_id"] != "majority"]
        if scored:
            max(scored, key=lambda r: r["Validation macro-F1"])["Best (by validation)"] = "BEST"
        rows += task_rows
    return rows


def verdict(rows):
    """One sentence per task: the agent's model, the best model by validation, and the best tree model against the agent's model (test accuracy and macro-F1)."""
    lines = []
    for title, _, _ in TASKS:
        t = [r for r in rows if r["Task"] == title]
        if not t:
            continue
        agent = next((r for r in t if r["Used by the agent"] and r["_id"] != "qure_weak_word_rule"), None)
        best = next((r for r in t if r["Best (by validation)"]), None)
        trees = [r for r in t if "+" in r["_id"] and r["Validation macro-F1"] is not None]
        tbest = max(trees, key=lambda r: r["Validation macro-F1"]) if trees else None
        s = f"- **{title}**: "
        if agent:
            s += f"the agent uses {agent['Model']} ({agent['Features']}) (accuracy {agent['Accuracy']:.3f}, macro-F1 {agent['Macro-F1']:.3f}). "
        if best:
            s += f"Best by validation: {best['Model']} ({best['Features']}) (accuracy {best['Accuracy']:.3f}, macro-F1 {best['Macro-F1']:.3f}). "
        if tbest and agent:
            d_acc, d_f1 = tbest["Accuracy"] - agent["Accuracy"], tbest["Macro-F1"] - agent["Macro-F1"]
            s += (f"Best tree model by validation: {tbest['Model']} ({tbest['Features']}) (accuracy {tbest['Accuracy']:.3f}, macro-F1 {tbest['Macro-F1']:.3f}); "
                  f"against the agent's model that is {d_acc:+.3f} accuracy and {d_f1:+.3f} macro-F1 on test (check the CIs before calling it a difference).")
        lines.append(s)
    return lines


def markdown(rows):
    out = ["# Component 1 Part A: every model on the frozen test split", "",
           "Generated by `python -m evaluation.model_comparison` from the saved result files (nothing is re-trained here). Seed 327. Models were fitted on the train split and tuned on "
           "the validation split only; the frozen test split was read once per task. CIs are 95 % bootstrap intervals (1000 resamples).", "",
           "**Read accuracy with care.** Accuracy is shown next to macro-F1 because both were asked for, but on an imbalanced task accuracy flatters a model that predicts the common "
           "class: for the security flag, always answering \"not security\" scores about 0.95 accuracy. Macro-F1 averages the classes equally and is the fairer number there.", "",
           "**Best** is the model with the highest validation macro-F1 (the majority baseline is excluded); it is never chosen from the test numbers.", ""]
    for line in verdict(rows):
        out.append(line)
    out.append("")
    for title, _, _ in TASKS:
        t = [r for r in rows if r["Task"] == title]
        if not t:
            continue
        out += [f"## {title}", "", "| Model | Features | Accuracy [95% CI] | Macro-F1 [95% CI] | Validation macro-F1 | Leave-one-project-out macro-F1 | Test rows | Used by the agent | Best |",
                "|---|---|---|---|---|---|---|---|---|"]
        for r in t:
            val = "" if r["Validation macro-F1"] is None else f"{r['Validation macro-F1']:.3f}"
            lopo = "" if r["PROMISE leave-one-project-out macro-F1"] is None else f"{r['PROMISE leave-one-project-out macro-F1']:.3f}"
            name = f"**{r['Model']}**" if r["Best (by validation)"] else r["Model"]
            out.append(f"| {name} | {r['Features']} | {r['Accuracy']:.3f} {r['Accuracy 95% CI']} | {r['Macro-F1']:.3f} {r['Macro-F1 95% CI']} | {val} | {lopo} | {r['Test rows']} | "
                       f"{r['Used by the agent']} | {r['Best (by validation)']} |")
        out.append("")
    out += ["## Not in the table", "",
            "- **Duplicate detection** (MiniLM cosine >= 0.955 + DBSCAN): there are no human-labelled duplicate pairs, so there is no accuracy to report. Its only score is F1 0.853 on 3,000 rule-made "
            "development pairs (0.812 on 1,500 held-out rule-made pairs); see `duplicates_eval/DUPLICATES_EVAL.md`.",
            "- **PROMISE NFR subtype** (multi-label): the test split has 43 rows, too few for a table of this kind; see `RESULTS.md`.",
            "- **Conflicts, risk score, draft priority**: hand-written rules, not trained models.", ""]
    return "\n".join(out)


def write(out_dir):
    out_dir = Path(out_dir)
    rows = collect(out_dir)
    if not rows:
        raise SystemExit(f"no result files found in {out_dir}")
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "_id"} for r in rows], columns=COLUMNS)
    df.to_csv(out_dir / "model_comparison.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    (out_dir / "MODEL_COMPARISON.md").write_text(markdown(rows) + "\n", encoding="utf-8")
    write_xlsx(df, out_dir / "model_comparison.xlsx")
    return df


def write_xlsx(df, path):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        df.to_excel(xl, index=False, sheet_name="All models")
        ws = xl.sheets["All models"]
        for c in ws[1]:
            c.font, c.fill, c.alignment = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E78"), Alignment(wrap_text=True, vertical="center")
        best = PatternFill("solid", fgColor="C6EFCE")
        for row in ws.iter_rows(min_row=2):
            if row[COLUMNS.index("Best (by validation)")].value == "BEST":
                for c in row:
                    c.fill, c.font = best, Font(bold=True)
            for name in ("Accuracy", "Macro-F1", "Validation macro-F1", "PROMISE leave-one-project-out macro-F1"):
                row[COLUMNS.index(name)].number_format = "0.000"
        for i, col in enumerate(COLUMNS, start=1):
            ws.column_dimensions[get_column_letter(i)].width = max(14, min(34, len(col) + 2))
        ws.freeze_panes = "C2"


def main(argv=None):
    out = Path(argv[0]) if argv else DEFAULT_OUT
    df = write(out)
    print(f"wrote {out / 'MODEL_COMPARISON.md'} ({len(df)} rows), model_comparison.csv, model_comparison.xlsx")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
