"""Requirement Intelligence Agent (Component 1): document in, one analysed row per candidate requirement out. No LLM calls.

    python -m agents.requirement_agent.agent <document> --out out.csv

Pipeline: ingest (txt, html, pdf, docx, rtf) -> segment into candidate requirements -> for every candidate:
  * FR/NFR type            embeddings + logistic regression (best under PROMISE leave-one-project-out)
  * security flag          keyword rules, with the matched cue words as the explanation
  * ambiguity score        TF-IDF + logistic regression (probability of `defect`), plus the matched QuRE weak words as the explanation
  * duplicate group id     MiniLM cosine threshold + DBSCAN grouping within the document (threshold from models/component1/duplicates_config.json)
Models are the ones saved by `python -m evaluation.run_baselines` and `python -m evaluation.duplicates_eval --task seeded`; if one is
missing the agent stops with a message that names the file and the command that creates it. Rows are unverified candidates
(`boundary_status=auto_unverified`): the baselines are weak models, so treat the columns as triage hints, not decisions.
"""
import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd

from . import duplicates as dup
from .classifier import security_cue_words
from .features import normalize_for_models
from .ingestion import UnsupportedFormat, load_document
from .segmenter import segment_document

MODELS_DIR = Path(__file__).resolve().parents[2] / "models" / "component1"
MODEL_FILES = {
    "type": "fr_nfr_fr_nfr_emb_lr.joblib",
    "security": "nfr_subtype_security_binary_rules.joblib",
    "ambiguity": "ambiguity_ambiguity_tfidf_lr.joblib",
    "weak_words": "ambiguity_ambiguity_qure_weak_word_rule.joblib",
}
HOW_TO_CREATE = {
    "type": "python -m evaluation.run_baselines --task fr_nfr",
    "security": "python -m evaluation.run_baselines --task nfr_subtype",
    "ambiguity": "python -m evaluation.run_baselines --task ambiguity",
    "weak_words": "python -m evaluation.run_baselines --task ambiguity",
    "duplicates": "python -m evaluation.duplicates_eval --task seeded",
}
COLUMNS = ["requirement_id", "source_document", "source_format", "position", "line_start", "clause_label", "text", "word_count", "rule_type_hint",
           "requirement_type", "nfr_probability", "is_security", "security_cue_words", "ambiguity_label", "ambiguity_score", "weak_words_matched",
           "duplicate_group_id", "boundary_status", "document_warnings"]


class ModelMissing(Exception):
    """A saved model file is missing."""


def load_models(models_dir=None):
    models_dir = Path(models_dir) if models_dir else MODELS_DIR
    loaded = {}
    for key, name in MODEL_FILES.items():
        path = models_dir / name
        if not path.exists():
            raise ModelMissing(f"Saved model missing: {path}\nCreate it with: {HOW_TO_CREATE[key]}")
        loaded[key] = joblib.load(path)["model"]
    config = models_dir / "duplicates_config.json"
    if not config.exists():
        raise ModelMissing(f"Duplicate-detection config missing: {config}\nCreate it with: {HOW_TO_CREATE['duplicates']}")
    loaded["duplicate_threshold"] = dup.load_threshold(config)
    return loaded


def _probability(model, X, positive):
    index = list(model.classes_).index(positive)
    return model.predict_proba(X)[:, index]


def run(document_path, models_dir=None):
    """Analyse one document and return a DataFrame with the COLUMNS above (empty frame, same columns, if nothing was extracted)."""
    models = load_models(models_dir)
    text, fmt, warnings = load_document(document_path)
    name = Path(document_path).stem
    rows, _, _ = segment_document(name, text, fmt)
    if not rows:
        empty = pd.DataFrame(columns=COLUMNS)
        empty.attrs["warnings"] = warnings + ["no candidate requirements were extracted"]
        return empty
    df = pd.DataFrame(rows)
    shown = list(df.cleaned_text)
    X = [normalize_for_models(t) for t in shown]
    out = pd.DataFrame({
        "requirement_id": df.srs_record_id, "source_document": df.source_document, "source_format": df.source_format, "position": df.position,
        "line_start": df.line_start, "clause_label": df.clause_label, "text": shown, "word_count": df.word_count, "rule_type_hint": df.candidate_type})
    out["requirement_type"] = models["type"].predict(X)
    out["nfr_probability"] = _probability(models["type"], X, "NFR").round(4)
    out["is_security"] = [p == "1" for p in models["security"].predict(X)]
    out["security_cue_words"] = [";".join(security_cue_words(x)) for x in X]
    out["ambiguity_label"] = models["ambiguity"].predict(X)
    out["ambiguity_score"] = _probability(models["ambiguity"], X, "defect").round(4)
    out["weak_words_matched"] = [";".join(sorted(set(models["weak_words"].matches(x)))) for x in X]
    out["duplicate_group_id"] = dup.find_duplicate_groups(shown, models["duplicate_threshold"])
    out["boundary_status"] = "auto_unverified"
    out["document_warnings"] = "; ".join(warnings)
    out = out[COLUMNS]
    out.attrs["warnings"] = warnings
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agents.requirement_agent.agent", description="Analyse the requirements in a document (no LLM).")
    ap.add_argument("document", help=".txt, .html, .pdf, .docx or .rtf file")
    ap.add_argument("--out", required=True, help="output CSV path")
    ap.add_argument("--models-dir", default=None, help="directory with the saved models (default: models/component1)")
    a = ap.parse_args(argv)
    try:
        result = run(a.document, a.models_dir)
    except (ModelMissing, UnsupportedFormat, FileNotFoundError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(a.out, index=False, encoding="utf-8-sig", lineterminator="\n")
    n = len(result)
    print(f"{n} candidate requirements -> {a.out}")
    for w in result.attrs.get("warnings", []):
        print(f"  warning: {w}")
    if n:
        print(f"  NFR: {int((result.requirement_type == 'NFR').sum())}, security-flagged: {int(result.is_security.sum())}, "
              f"ambiguity=defect: {int((result.ambiguity_label == 'defect').sum())}, in duplicate groups: {int((result.duplicate_group_id != '').sum())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
