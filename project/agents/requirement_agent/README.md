# requirement agent (Component 1)

Reads a Software Requirements Specification (SRS), splits it into candidate requirements and adds triage hints to each one. No LLM calls.
The full guide is `RequirementAgent_README.md` in the `project/` folder.

## Usage

Run from the `project/` folder (the `agents` package is not found from the repository root), with the project's virtual environment active
(`J26-SE-327/.venv`):

    cd project
    python -m agents.requirement_agent.agent "data/component1/processed/srs_extracted_text/2009 - library.txt" --out outputs/component1_demo.csv

- Input: `.txt`, `.html`/`.htm`, `.pdf`, `.docx` or `.rtf`. Legacy binary `.doc` is not supported (convert it first).
- Output: a CSV (`--out` is required; the folder is created if needed) with one row per candidate requirement, plus a one-line summary in the terminal.
  Optional `--models-dir <folder>` loads the saved models from another folder (default `models/component1/part_a_active`).

## Per-row output

| Step | Columns | Method | Model file in `models/component1/part_a_active/` |
|---|---|---|---|
| FR/NFR | `requirement_type`, `nfr_probability` | MiniLM embeddings + logistic regression | `fr_nfr_fr_nfr_emb_lr.joblib` |
| Security | `is_security`, `security_cue_words` | keyword rules | `nfr_subtype_security_binary_rules.joblib` |
| Ambiguity | `ambiguity_label`, `ambiguity_score` | TF-IDF + logistic regression | `ambiguity_ambiguity_tfidf_lr.joblib` |
| Weak words | `weak_words_matched` | QuRE weak-word rule | `ambiguity_ambiguity_qure_weak_word_rule.joblib` |
| Duplicates | `duplicate_group_id` | MiniLM cosine >= threshold + DBSCAN, within the document | `duplicates_config.json` (threshold 0.955) |

The segmenter also adds `requirement_id`, `source_document`, `source_format`, `position`, `line_start`, `clause_label`, `text`, `word_count` and
`rule_type_hint`. `boundary_status` is always `auto_unverified` and `document_warnings` lists reader warnings.

The agent loads only the four `.joblib` files above and the duplicates config. The other 21 models are comparison baselines in
`models/component1/part_a_experiments/` (`models/component1/MODEL_MANIFEST.md` lists all of them).

## Models must exist first

The `.joblib` files and `embedding_cache/` are git-ignored, so a fresh clone has none. A missing model stops the run with a message that names
the file and the command that creates it:

    python -m evaluation.run_baselines --task all --out-dir outputs/baseline_results
    python -m evaluation.duplicates_eval --task seeded --out-dir outputs/baseline_results

`run_baselines` saves the models under `models/component1/part_a_experiments/<group>/`; copy the four files the agent needs (listed above) into
`models/component1/part_a_active/` by hand. `duplicates_eval --task seeded` writes `part_a_active/duplicates_config.json` directly.
Without `--out-dir` these commands overwrite the committed results in `evaluation/component1/results/`. The first run that needs embeddings
downloads the `all-MiniLM-L6-v2` model, so it needs internet once.

## Scores (frozen test, macro-F1 [95 % CI])

FR/NFR 0.828 [0.802, 0.852]; security 0.721 [0.670, 0.767]; ambiguity 0.685 [0.649, 0.722]. Duplicates: F1 0.812 [0.784, 0.837] on seeded
(rule-made) pairs only, not on human-labelled duplicates. Details: `evaluation/component1/results/RESULTS.md`.

## Modules

`ingestion.py` (file -> text), `segmenter.py` (text -> candidate requirements), `features.py` (normalisation, TF-IDF, embeddings and cache),
`classifier.py` (baseline model definitions and security cue words), `ambiguity.py` (weak-word rule model), `duplicates.py` (grouping),
`agent.py` (pipeline and command line). Outputs are unverified candidates and baseline predictions: review them before relying on them.

## Optional Part B: generate a story per requirement (off by default)

    python -m agents.requirement_agent.agent <document> --out out.csv --generate --generation-backend replay --replay-file evaluation/component1/generation/ft_outputs.json
    python -m agents.requirement_agent.agent <document> --out out.csv --generate --generation-backend ollama

Without `--generate` the output is exactly the Part A output. With it, these columns are appended after the Part A columns: `gen_status` (`ok`, `needs_clarification` or `invalid`),
`user_story`, `technical_task`, `acceptance_criteria` (JSON list), `rationale`, `clarification_questions` (JSON list), `gen_attempts`, `gen_manual_review` and `gen_raw_output`
(filled only when the reply needs manual review). The prompt is the training prompt (`prompts.py`). An invalid reply is retried up to 2 more times; after 3 failures the row is
marked for manual review. `replay` returns stored outputs and stops with a message if a requirement text is not in the file; `ollama` calls an OpenAI-compatible endpoint set by
`LLM_BASE_URL` (default `http://localhost:11434/v1`), `LLM_MODEL` and `LLM_API_KEY` (see `config.py`). Code: `generation.py`, `schemas.py`; tests: `tests/test_generation.py`.

## API for the web UI

A FastAPI backend wraps Part A and Part B for the UI. Install the packages (`pip install -r requirements.txt`), then from `project/`:

    uvicorn agents.requirement_agent.api.app:app --port 8000

It binds to 127.0.0.1:8000 and allows the UI origins `http://localhost:5173` and `http://127.0.0.1:5173`. Interactive docs are at `/docs`.
Projects, uploads (`.txt .md .pdf .docx`, 20 MB each), results and decisions are stored in `outputs/c1_workspace/` (SQLite `c1.db` and `uploads/`, git-ignored).
Generation backend: `C1_GENERATION_BACKEND=replay|ollama|mock` (default `replay`, which reads `evaluation/component1/generation/ft_outputs.json`; a requirement whose text is
not in that file shows `failed: not in replay file`). For Ollama set `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. Full contract: `docs/c1_api_contract.md`; schema:
`docs/c1_openapi.json` (regenerate with `python -m agents.requirement_agent.api.export_openapi`). Tests: `tests/test_c1_api.py`, `tests/test_c1_risk_conflicts.py`.
The API keeps its own embedding cache in the workspace (set `C1_USE_MODEL_CACHE=1` to use the one under `models/component1/part_a_active/` instead).
