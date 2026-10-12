"""Evaluate and calibrate the duplicate detector, and prepare the manual review file.

    python -m evaluation.duplicates_eval --task seeded     # calibrate the threshold on a dev subset, evaluate on a held-out subset
    python -m evaluation.duplicates_eval --task review     # top-50 flagged real pairs for manual review
    python -m evaluation.duplicates_eval --task all

Seeded evaluation. There are no human-labelled duplicate pairs, so the evaluation uses rule-made pairs, **clearly labelled
`seeded_eval_only`**. They are never written to `processed/tasks/`, never used to train anything, and never include the frozen test split:
  - development set: requirement texts of the *train* split (used only to choose the cosine threshold);
  - evaluation set:  requirement texts of the *val* split (used only to report numbers).
Positives are one rule-based edit of a real requirement (modal swap, dropped modifier, clause reorder, case/punctuation change, trailing
clause added or removed). Negatives are easy (two random different requirements) or hard (same template, different object: the last two
words of a requirement replaced by those of another requirement with the same first three words, high word overlap, not duplicates).
Precision is reported with and without the hard negatives. This measures rule-style paraphrase only; real-world recall is unknown.

Review file. The top-50 flagged real pairs over `srs_requirements_extracted.csv`: 25 with the highest cosine and 25 drawn (seeded hash
order) from the 0.80-0.90 band, exact-text matches excluded; `is_duplicate` and `reviewer_note` are left empty for the reviewer.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from agents.requirement_agent import duplicates as D
from agents.requirement_agent.features import EMBEDDING_MODEL, SEED, embed
from evaluation import data_access as da
from evaluation import metrics as M

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "evaluation" / "component1" / "results"
SRS_FILE = da.DATA / "processed" / "srs_requirements_extracted.csv"
TCS_DOCUMENT = "1999 - tcs"
N_DEV, N_EVAL = 1000, 500            # pairs per kind
MODAL_SWAP = {"shall": "must", "must": "shall", "should": "shall", "will": "shall"}
MODIFIERS = {"all", "also", "new", "existing", "relevant", "appropriate", "various", "additional", "current", "specific", "each", "any", "every"}
NOT_ADVERBS = {"only", "early", "family", "daily", "weekly", "monthly", "yearly", "apply", "supply", "reply", "assembly", "italy", "anomaly", "friendly"}
TRAILING_ADD = ", as described in this document"
TRAILING_CLAUSE = re.compile(r",\s+(?:as|where|unless|if|when|so that|according to)\s+[^,]{3,60}$", re.I)
CONDITION = re.compile(r"^(if|when|where|after|before|upon|during|once)\b", re.I)


def h(*parts):
    return hashlib.sha256("|".join(str(p) for p in (SEED,) + parts).encode("utf-8")).hexdigest()


def clean(text):
    return re.sub(r"\s+", " ", str(text)).strip().strip("'\"").strip()


def _words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def jaccard(a, b):
    sa, sb = set(_words(a)), set(_words(b))
    return len(sa & sb) / max(len(sa | sb), 1)


# --------------------------------------------------------------------------------------------------- seeded edits (positives)
def edit_modal_swap(text):
    m = re.search(r"\b(shall|must|should|will)\b", text, re.I)
    if not m:
        return None
    new = MODAL_SWAP[m.group(1).lower()]
    new = new.capitalize() if m.group(1)[0].isupper() else new
    return text[:m.start()] + new + text[m.end():]


def edit_drop_modifier(text):
    words = text.split()
    cands = [i for i, w in enumerate(words) if i > 0 and (re.sub(r"\W", "", w.lower()) in MODIFIERS or
                                                            (re.sub(r"\W", "", w.lower()).endswith("ly") and len(w) > 5 and re.sub(r"\W", "", w.lower()) not in NOT_ADVERBS))]
    if not cands or len(words) < 8:
        return None
    i = cands[int(h("drop", text), 16) % len(cands)]
    return " ".join(words[:i] + words[i + 1:])


def edit_clause_reorder(text):
    body = text.rstrip()
    end = body[-1] if body and body[-1] in ".;" else ""
    body = body[:-1] if end else body
    if "," not in body or len(body.split()) < 8:
        return None
    first, rest = body.split(",", 1)
    rest = rest.strip()
    if CONDITION.match(first) and rest:
        return rest[:1].upper() + rest[1:] + " " + first[:1].lower() + first[1:] + end
    parts = [p.strip() for p in body.split(",")]
    if len(parts) < 2 or len(parts[0].split()) < 3 or len(parts[1].split()) < 3:
        return None
    parts[0], parts[1] = parts[1][:1].upper() + parts[1][1:], parts[0][:1].lower() + parts[0][1:]
    return ", ".join(parts) + end


def edit_case_punct(text):
    new = text.lower().rstrip(".") if text.rstrip().endswith(".") or text != text.lower() else None
    return new if new and new != text else None


def edit_trailing_clause(text):
    stripped = text.rstrip()
    if TRAILING_CLAUSE.search(stripped):
        cut = TRAILING_CLAUSE.sub("", stripped).rstrip()
        return (cut + ".") if stripped.endswith(".") and not cut.endswith(".") and len(cut.split()) >= 6 else (cut if len(cut.split()) >= 6 else None)
    if stripped.endswith("."):
        return stripped[:-1] + TRAILING_ADD + "."
    return stripped + TRAILING_ADD


EDITS = {"modal_swap": edit_modal_swap, "drop_modifier": edit_drop_modifier, "clause_reorder": edit_clause_reorder,
         "case_punctuation": edit_case_punct, "trailing_clause": edit_trailing_clause}


def make_positive(text):
    """One deterministic rule-based edit of `text`, or None when no edit applies. Returns (edited, edit_name)."""
    options = [(name, fn(text)) for name, fn in EDITS.items()]
    options = [(n, t) for n, t in options if t and t != text and len(t.split()) >= 4]
    if not options:
        return None
    name, new = options[int(h("edit", text), 16) % len(options)]
    return new, name


# --------------------------------------------------------------------------------------------------- negatives
def make_hard_negative(text, donors_by_prefix):
    """Same template, different object: replace the last two words (before the final punctuation) by those of another requirement with the
    same first three words. Returns the new text or None."""
    words = text.split()
    if len(words) < 8:
        return None
    end = words[-1][-1] if words[-1][-1] in ".;" else ""
    core = [w.rstrip(".;") if i == len(words) - 1 else w for i, w in enumerate(words)]
    prefix = " ".join(w.lower() for w in core[:3])
    pool = [d for d in donors_by_prefix.get(prefix, []) if d != text]
    if not pool:
        return None
    pool = sorted(pool, key=lambda d: h("donor", text, d))
    for donor in pool[:10]:
        dw = [w.rstrip(".;") for w in donor.split()]
        if len(dw) < 4 or dw[-2:] == core[-2:]:
            continue
        new = " ".join(core[:-2] + dw[-2:]) + end
        if new != text and jaccard(text, new) >= 0.6 and jaccard(text, donor) < 0.95:
            return new
    return None


def build_pairs(texts, n, tag):
    """Disjoint-base seeded pairs: n positives, n hard negatives, n easy negatives, from `texts` (list of cleaned requirement strings)."""
    texts = sorted({t for t in texts if len(t.split()) >= 6}, key=lambda t: h(tag, "order", t))
    prefix = {}
    for t in texts:
        prefix.setdefault(" ".join(w.lower() for w in t.split()[:3]), []).append(t)
    used, rows = set(), []

    def add(kind, label, a, b, extra=""):
        rows.append({"set": tag, "kind": kind, "label": label, "text_a": a, "text_b": b, "edit_or_note": extra})

    for t in texts:
        if sum(r["kind"] == "positive" for r in rows) >= n:
            break
        made = make_positive(t)
        if made:
            add("positive", "duplicate", t, made[0], made[1])
            used.add(t)
    for t in texts:
        if t in used:
            continue
        if sum(r["kind"] == "hard_negative" for r in rows) >= n:
            break
        new = make_hard_negative(t, prefix)
        if new:
            add("hard_negative", "not_duplicate", t, new, "template_object_swap")
            used.add(t)
    rest = [t for t in texts if t not in used]
    i = 0
    easy = 0
    while easy < n and i + 1 < len(rest):
        a, b = rest[i], rest[i + 1]
        i += 2
        if jaccard(a, b) < 0.5:
            add("easy_negative", "not_duplicate", a, b, "random_pair")
            easy += 1
    df = pd.DataFrame(rows)
    df.insert(0, "pair_id", [f"{tag}:{k:04d}" for k in range(len(df))])
    df["seeded_eval_only"] = True
    return df


def score_pairs(df):
    uniq = sorted(set(df.text_a) | set(df.text_b))
    emb = dict(zip(uniq, embed(uniq)))
    df = df.copy()
    df["cosine"] = [float(np.dot(emb[a], emb[b])) for a, b in zip(df.text_a, df.text_b)]
    return df


# --------------------------------------------------------------------------------------------------- metrics
def prf(labels_true, flagged, n_boot):
    yt = np.where(np.asarray(labels_true) == "duplicate", "dup", "not")
    yp = np.where(np.asarray(flagged), "dup", "not")
    m = M.classification_metrics(list(yt), list(yp), ["dup", "not"])
    ci = M.bootstrap_ci(list(yt), list(yp), ["dup", "not"], n_boot=n_boot)
    return {k: (m[f"{k}[dup]"], *ci[f"{k}[dup]"]) for k in ("precision", "recall", "f1")}


def sweep(df, grid):
    y = (df.label == "duplicate").values
    rows = []
    for t in grid:
        flagged = df.cosine.values >= t
        tp, fp, fn = int((flagged & y).sum()), int((flagged & ~y).sum()), int((~flagged & y).sum())
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        rows.append({"threshold": round(float(t), 3), "precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0})
    return pd.DataFrame(rows)


def requirement_texts(split):
    d = da.load_task("generation_inputs", (split,))
    return [clean(t) for t in d[d.record_type == "requirement_text"].requirement_text_original]


def run_seeded(out_dir, models_dir, n_boot):
    out = Path(out_dir) / "duplicates_eval"
    out.mkdir(parents=True, exist_ok=True)
    dev = score_pairs(build_pairs(requirement_texts("train"), N_DEV, "dev"))
    ev = score_pairs(build_pairs(requirement_texts("val"), N_EVAL, "eval"))
    grid = np.round(np.arange(0.60, 0.9951, 0.005), 3)
    sw = sweep(dev, grid)
    best = sw.sort_values(["f1", "threshold"], ascending=[False, False]).iloc[0]
    t = float(best.threshold)
    dev["flagged"], ev["flagged"] = dev.cosine >= t, ev.cosine >= t

    rows = []
    for name, sub in (("all_negatives", ev), ("easy_negatives_only", ev[ev.kind != "hard_negative"]), ("hard_negatives_only", ev[ev.kind != "easy_negative"])):
        res = prf(sub.label.values, sub.flagged.values, n_boot)
        for metric, (v, lo, hi) in res.items():
            rows.append({"set": "eval(val)", "negatives": name, "metric": metric, "value": v, "ci_low": lo, "ci_high": hi, "n_pairs": len(sub)})
    dres = prf(dev.label.values, dev.flagged.values, n_boot)
    for metric, (v, lo, hi) in dres.items():
        rows.append({"set": "dev(train)", "negatives": "all_negatives", "metric": metric, "value": v, "ci_low": lo, "ci_high": hi, "n_pairs": len(dev)})
    for kind in ("positive",):
        for edit, sub in ev[ev.kind == kind].groupby("edit_or_note"):
            rows.append({"set": "eval(val)", "negatives": "recall_by_edit:" + edit, "metric": "recall", "value": float(sub.flagged.mean()), "ci_low": "", "ci_high": "", "n_pairs": len(sub)})
    for kind, sub in ev[ev.kind != "positive"].groupby("kind"):
        rows.append({"set": "eval(val)", "negatives": "false_positive_rate:" + kind, "metric": "flag_rate", "value": float(sub.flagged.mean()), "ci_low": "", "ci_high": "", "n_pairs": len(sub)})

    # DBSCAN grouping on the evaluation texts: a pair counts as a duplicate when both texts land in the same group
    texts = sorted(set(ev.text_a) | set(ev.text_b))
    index = {x: i for i, x in enumerate(texts)}
    labels = D.cluster_labels(embed(texts), t)
    same = np.array([labels[index[a]] >= 0 and labels[index[a]] == labels[index[b]] for a, b in zip(ev.text_a, ev.text_b)])
    for name, sub in (("all_negatives", ev.assign(g=same)), ("easy_negatives_only", ev.assign(g=same)[ev.kind != "hard_negative"])):
        res = prf(sub.label.values, sub.g.values, n_boot)
        for metric, (v, lo, hi) in res.items():
            rows.append({"set": "eval(val) DBSCAN groups", "negatives": name, "metric": metric, "value": v, "ci_low": lo, "ci_high": hi, "n_pairs": len(sub)})

    metrics = pd.DataFrame(rows)
    for c in ("value", "ci_low", "ci_high"):
        metrics[c] = metrics[c].map(lambda v: "" if v == "" else round(float(v), 4))
    metrics.to_csv(out / "duplicates_eval_metrics.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    sw.round(4).to_csv(out / "threshold_sweep_dev.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    keep = ["pair_id", "set", "kind", "label", "edit_or_note", "cosine", "flagged", "seeded_eval_only", "text_a", "text_b"]
    dev[keep].round({"cosine": 4}).to_csv(out / "seeded_pairs_dev.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    ev[keep].round({"cosine": 4}).to_csv(out / "seeded_pairs_eval.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    config = {"threshold": t, "dbscan_eps": round(1 - t, 4), "dbscan_min_samples": 2, "embedding_model": EMBEDDING_MODEL, "seed": SEED,
              "chosen_on": "seeded development pairs from the train split (max F1; ties to the higher threshold)", "dev_f1": round(float(best.f1), 4),
              "note": "seeded rule-made pairs only; real-world recall is unknown"}
    Path(models_dir).mkdir(parents=True, exist_ok=True)
    (Path(models_dir) / "duplicates_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    write_eval_md(out, metrics, ev, dev, t, best)
    print(f"threshold chosen on dev: {t} (dev F1 {best.f1:.3f})")
    return t


def write_eval_md(out, metrics, ev, dev, t, best):
    def row(set_, neg, metric):
        r = metrics[(metrics.set == set_) & (metrics.negatives == neg) & (metrics.metric == metric)].iloc[0]
        return f"{r.value:.3f} [{r.ci_low:.3f}, {r.ci_high:.3f}]"
    L = ["# Duplicate detector: seeded evaluation", "",
         "**All pairs here are rule-made (`seeded_eval_only`); they are not human-labelled duplicates, are never training data, and the frozen test split is not used.** "
         f"Threshold {t} was chosen on {len(dev)} development pairs from the train split (max F1 {best.f1:.3f}); numbers below are on {len(ev)} held-out pairs from the val split "
         f"({int((ev.kind == 'positive').sum())} positives, {int((ev.kind == 'hard_negative').sum())} hard negatives, {int((ev.kind == 'easy_negative').sum())} easy negatives). "
         "95 % bootstrap CIs in brackets.", "",
         "| negatives used | precision | recall | F1 |", "|---|---|---|---|"]
    for name, label in (("all_negatives", "easy + hard negatives"), ("easy_negatives_only", "easy negatives only (without hard negatives)")):
        L.append(f"| {label} | {row('eval(val)', name, 'precision')} | {row('eval(val)', name, 'recall')} | {row('eval(val)', name, 'f1')} |")
    L += ["", "Pair-level classification by cosine >= threshold. With DBSCAN grouping (a pair is a duplicate when both texts fall in the same group):", "",
          "| negatives used | precision | recall | F1 |", "|---|---|---|---|"]
    for name, label in (("all_negatives", "easy + hard negatives"), ("easy_negatives_only", "easy negatives only")):
        L.append(f"| {label} | {row('eval(val) DBSCAN groups', name, 'precision')} | {row('eval(val) DBSCAN groups', name, 'recall')} | {row('eval(val) DBSCAN groups', name, 'f1')} |")
    L += ["", "Recall by edit type and flag rate of the negatives (eval set):", "", "| item | value | pairs |", "|---|---|---|"]
    for r in metrics[metrics.negatives.str.startswith(("recall_by_edit", "false_positive_rate"))].itertuples():
        L.append(f"| {r.negatives} | {r.value:.3f} | {r.n_pairs} |")
    L += ["", "Limits: positives are simple rule edits, so recall says nothing about free paraphrase; hard negatives are constructed by swapping the last two "
          "words, so they may be easier or harder than real near-misses; no human labels were used."]
    (out / "DUPLICATES_EVAL.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------------------- manual review file
def run_review(out_dir):
    srs = pd.read_csv(SRS_FILE, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    texts = list(srs.cleaned_text)
    emb = embed(texts)
    i, j, s = D.similarity_pairs(emb, 0.80)
    keys = np.array([D.exact_key(t) for t in texts], dtype=object)
    exact = keys[i] == keys[j]
    n_pairs, n_exact = len(i), int(exact.sum())
    i, j, s = i[~exact], j[~exact], s[~exact]
    pairs = pd.DataFrame({"i": i, "j": j, "cosine": s.astype(float)})
    pairs["pid"] = [f"{srs.srs_record_id[a]}|{srs.srs_record_id[b]}" for a, b in zip(i, j)]
    top = pairs.sort_values(["cosine", "pid"], ascending=[False, True]).head(25).assign(band="top25_highest_cosine")
    band = pairs[(pairs.cosine >= 0.80) & (pairs.cosine < 0.90) & ~pairs.pid.isin(top.pid)]
    band = band.assign(_o=band.pid.map(lambda x: h("review_band", x))).sort_values("_o").head(25).drop(columns="_o").assign(band="band_0.80_0.90_sampled")
    sel = pd.concat([top, band]).reset_index(drop=True)
    rows = []
    for n, r in enumerate(sel.itertuples(), start=1):
        a, b = srs.iloc[r.i], srs.iloc[r.j]
        flag = "tcs_hold" if TCS_DOCUMENT in (a.source_document, b.source_document) else ""
        rows.append({"pair_no": n, "selection": r.band, "cosine": round(r.cosine, 4), "scope": "within_document" if a.source_document == b.source_document else "across_documents",
                     "tcs_flag": flag, "record_id_a": a.srs_record_id, "document_a": a.source_document, "text_a": a.cleaned_text,
                     "record_id_b": b.srs_record_id, "document_b": b.source_document, "text_b": b.cleaned_text, "is_duplicate": "", "reviewer_note": ""})
    df = pd.DataFrame(rows)
    path = Path(out_dir) / "duplicates_review_top50.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig", lineterminator="\n")
    note = (f"{len(srs)} SRS rows; {n_pairs} pairs at cosine >= 0.80, of which {n_exact} are exact-text matches (excluded); "
            f"{len(pairs)} pairs remain; band 0.80-0.90 holds {int(((pairs.cosine >= 0.8) & (pairs.cosine < 0.9)).sum())}.")
    (Path(out_dir) / "duplicates_review_notes.txt").write_text(note + "\n", encoding="utf-8")
    print(note)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--task", required=True, choices=["seeded", "review", "all"])
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--models-dir", default=str(D.CONFIG_PATH.parent))
    ap.add_argument("--n-boot", type=int, default=M.N_BOOT)
    a = ap.parse_args(argv)
    if a.task in ("seeded", "all"):
        run_seeded(a.out_dir, a.models_dir, a.n_boot)
    if a.task in ("review", "all"):
        run_review(a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
