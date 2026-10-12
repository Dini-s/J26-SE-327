"""Requirement Intelligence Agent (Component 1): document in, one analysed row per candidate requirement out. No LLM calls.

    python -m agents.requirement_agent.agent <document> --out out.csv

Pipeline: ingest (txt, html, pdf, docx, rtf) -> segment into candidate requirements -> for every candidate:
  * FR/NFR type            embeddings + logistic regression (best under PROMISE leave-one-project-out)
  * security flag          keyword rules, with the matched cue words as the explanation
  * ambiguity score        TF-IDF + logistic regression (probability of `defect`), plus the matched QuRE weak words as the explanation
  * duplicate group id     MiniLM cosine threshold + DBSCAN grouping within the document (threshold from models/component1/part_a_active/duplicates_config.json)
Models are the ones in models/component1/part_a_active/: copies of files saved by `python -m evaluation.run_baselines` (which writes to
part_a_experiments/) and the config written by `python -m evaluation.duplicates_eval --task seeded`; if one is
missing the agent stops with a message that names the file and the command that creates it. Rows are unverified candidates
(`boundary_status=auto_unverified`): the baselines are weak models, so treat the columns as triage hints, not decisions.

Optional Part B (off by default): `--generate` adds, per requirement, a user story, technical task and acceptance criteria from a language
model (`--generation-backend replay|ollama`, `--replay-file PATH` for replay). The Part A columns and their order do not change; the
generation columns (generation.GENERATION_COLUMNS) are appended after them. See generation.py.
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

MODELS_DIR = Path(__file__).resolve().parents[2] / "models" / "component1" / "part_a_active"
MODEL_FILES = {
    "type": "fr_nfr_fr_nfr_emb_lr.joblib",
    "security": "nfr_subtype_security_binary_rules.joblib",
    "ambiguity": "ambiguity_ambiguity_tfidf_lr.joblib",
    "weak_words": "ambiguity_ambiguity_qure_weak_word_rule.joblib",
}
# run_baselines saves into models/component1/part_a_experiments/<group>/; the active copy in part_a_active/ is refreshed by hand
HOW_TO_CREATE = {
    "type": "python -m evaluation.run_baselines --task fr_nfr, then copy part_a_experiments/fr_nfr/fr_nfr_fr_nfr_emb_lr.joblib into models/component1/part_a_active/",
    "security": "python -m evaluation.run_baselines --task nfr_subtype, then copy part_a_experiments/security_and_subtype/nfr_subtype_security_binary_rules.joblib into models/component1/part_a_active/",
    "ambiguity": "python -m evaluation.run_baselines --task ambiguity, then copy part_a_experiments/ambiguity/ambiguity_ambiguity_tfidf_lr.joblib into models/component1/part_a_active/",
    "weak_words": "python -m evaluation.run_baselines --task ambiguity, then copy part_a_experiments/ambiguity/ambiguity_ambiguity_qure_weak_word_rule.joblib into models/component1/part_a_active/",
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


def run(document_path, models_dir=None, generator=None):
    """Analyse one document and return a DataFrame with the COLUMNS above (empty frame, same columns, if nothing was extracted).

    `generator` (a generation.Backend) switches on the optional Part B step and appends generation.GENERATION_COLUMNS; with None the result
    is exactly the Part A result."""
    models = load_models(models_dir)
    text, fmt, warnings = load_document(document_path)
    name = Path(document_path).stem
    rows, _, _ = segment_document(name, text, fmt)
    if not rows:
        if generator is not None:
            from .generation import GENERATION_COLUMNS
            empty = pd.DataFrame(columns=COLUMNS + GENERATION_COLUMNS)
        else:
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
    if generator is not None:
        from .generation import GENERATION_COLUMNS, generate_structured
        generated = [generate_structured(generator, t).as_columns() for t in shown]
        out = out.copy()
        for column in GENERATION_COLUMNS:
            out[column] = [g[column] for g in generated]
    out.attrs["warnings"] = warnings
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agents.requirement_agent.agent", description="Analyse the requirements in a document (no LLM).")
    ap.add_argument("document", help=".txt, .html, .pdf, .docx or .rtf file")
    ap.add_argument("--out", required=True, help="output CSV path")
    ap.add_argument("--models-dir", default=None, help="directory with the saved models (default: models/component1/part_a_active)")
    ap.add_argument("--generate", action="store_true", help="optional Part B: add a user story, technical task and acceptance criteria per requirement (off by default)")
    ap.add_argument("--generation-backend", choices=["replay", "ollama"], default="ollama", help="where the generated text comes from (default: ollama)")
    ap.add_argument("--replay-file", default=None, help="JSON list of {id, requirement_text, output} for --generation-backend replay")
    a = ap.parse_args(argv)
    generator = None
    try:
        if a.generate:
            from .generation import make_backend
            generator = make_backend(a.generation_backend, a.replay_file)
        result = run(a.document, a.models_dir, generator)
    except (ModelMissing, UnsupportedFormat, FileNotFoundError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        from .generation import BackendError
        if not isinstance(exc, BackendError):
            raise
        print(f"STOP: generation backend: {exc}", file=sys.stderr)
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
        if generator is not None:
            print(f"  generated: ok {int((result.gen_status == 'ok').sum())}, needs_clarification {int((result.gen_status == 'needs_clarification').sum())}, "
                  f"manual review {int(result.gen_manual_review.sum())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
