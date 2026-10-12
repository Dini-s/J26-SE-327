# Requirement Intelligence Agent (Component 1)

## 1. Project Overview

The Requirement Intelligence Agent analyses requirements extracted from Software Requirements Specification (SRS) documents.

The current agent:
1. Reads a supported requirements document.
2. Extracts candidate requirements and splits them into individual rows.
3. Classifies each requirement as Functional Requirement (FR) or Non-Functional Requirement (NFR).
4. Flags possible security-related requirements and shows matched security cue words.
5. Detects possible ambiguity and provides an ambiguity label, a score and the matched weak words.
6. Identifies potential duplicate requirements within the document using text embeddings and a cosine-similarity threshold.
7. Exports the analysis results to a CSV file for review.

**Important:** The current agent does not call an LLM. Its results are automatic, unverified analysis hints from baseline models. Review them before treating them as final decisions.

## 2. Main Methods

| Task | Method | Saved file in `models/component1/part_a_active/` |
|---|---|---|
| FR/NFR classification | MiniLM sentence embeddings + Logistic Regression | `fr_nfr_fr_nfr_emb_lr.joblib` |
| Security detection | Keyword/rule-based model (also returns the matched cue words) | `nfr_subtype_security_binary_rules.joblib` |
| Ambiguity detection | TF-IDF + Logistic Regression (label and probability of `defect`) | `ambiguity_ambiguity_tfidf_lr.joblib` |
| Weak-word explanation | QuRE weak-word rule | `ambiguity_ambiguity_qure_weak_word_rule.joblib` |
| Duplicate detection | MiniLM embeddings + cosine threshold + DBSCAN grouping, within one document | `duplicates_config.json` (threshold 0.955) |

The agent loads only these four `.joblib` files and the duplicates config. The other 21 baseline models (majority, rules, TF-IDF + LR/SVM, embeddings + LR for each task, and the cross-source ambiguity models) are in `models/component1/part_a_experiments/` (`fr_nfr/`, `security_and_subtype/`, `ambiguity/`) for comparison and are never loaded by the agent. `models/component1/MODEL_MANIFEST.md` lists every file with its algorithm and frozen-test score.

A similarity match indicates a *potential* duplicate, not proof that two requirements are duplicates.

## 3. Important Files

```text
project/
├── agents/requirement_agent/
│   ├── agent.py          # Command-line entry point and the pipeline
│   ├── ingestion.py      # Reads .txt, .html, .pdf, .docx, .rtf
│   ├── segmenter.py      # Extracts candidate requirement rows
│   ├── classifier.py     # Baseline model definitions (majority, rules, TF-IDF + LR/SVM, embeddings + LR) and security cue helpers
│   ├── ambiguity.py      # QuRE weak-word rule model
│   ├── duplicates.py     # Cosine threshold + DBSCAN duplicate grouping
│   ├── features.py       # Text normalization, TF-IDF, MiniLM embeddings and their cache
│   └── tests/            # Agent tests
├── models/component1/    # part_a_active/ (models the agent loads + duplicates config), part_a_experiments/ (21 baselines), MODEL_MANIFEST.md (.joblib files and the embedding cache are git-ignored)
├── evaluation/
│   ├── run_baselines.py  # Train/evaluate baseline models
│   ├── duplicates_eval.py
│   └── component1/results/RESULTS.md
├── data/component1/processed/srs_extracted_text/  # Extracted SRS text samples (.txt)
├── tests/                # Project tests (pytest)
└── outputs/              # Empty folder for demo CSV output
```

## 4. Setup

Run commands from the `project/` directory unless stated otherwise.

### 4.1 Check Python

```powershell
python --version
```

### 4.2 Virtual environment

This repository keeps its virtual environment one level above `project/`, in `J26-SE-327/.venv` (it is git-ignored). If it already exists, activate it (from the repository root, `.\.venv\Scripts\Activate.ps1`; from `project/`, `..\.venv\Scripts\Activate.ps1`), then work from `project/`:

```powershell
.\.venv\Scripts\Activate.ps1
cd project
```

To create it for the first time (from the repository root `J26-SE-327/`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If script activation is blocked, use your IDE's environment activation or call the interpreter directly (`..\.venv\Scripts\python.exe` instead of `python`). Avoid changing system-wide security settings unnecessarily.

### 4.3 Install dependencies

```powershell
pip install -r requirements.txt
```

This installs pandas, scikit-learn, sentence-transformers, pypdf, python-docx, striprtf, joblib and the other packages in `requirements.txt`. The first run that needs embeddings downloads the `all-MiniLM-L6-v2` model, so it needs an internet connection once; later runs use the local copy and a text-embedding cache.

### 4.4 Saved models must exist

`models/component1/**/*.joblib` and `models/component1/part_a_active/embedding_cache/` are git-ignored, so a fresh clone does not contain them (the duplicates config and `MODEL_MANIFEST.md` are ordinary files). If they are missing the agent stops with `Saved model missing`; create them as described in section 8 (retrained models are saved to `part_a_experiments/`; copy the four you need into `part_a_active/`).

## 5. Run the Agent

### 5.1 Choose an input file

Supported formats are `.txt`, `.html`/`.htm`, `.pdf`, `.docx` and `.rtf`. Legacy binary `.doc` files are **not** supported (many files in `data/component1/raw/documents/srs/` are `.doc`); convert them to `.docx`, `.pdf` or `.txt` first. Ready-made text versions of the 79 sample SRS documents are in the folder `data/component1/processed/srs_extracted_text/`. That is a folder path, not a command, so do not type it on its own at the prompt. To list the files, run:

```powershell
Get-ChildItem "data/component1/processed/srs_extracted_text"
```

Confirm the exact filename before running the example.

### 5.2 Run command

Your prompt must end in `...\J26-SE-327\project>`. If it ends in `...\J26-SE-327>`, run `cd project` first: the `agents` package lives in `project/`, and from the repository root Python reports `No module named 'agents'`.

```powershell
python -m agents.requirement_agent.agent "data/component1/processed/srs_extracted_text/2009 - library.txt" --out "outputs/component1_demo.csv"
```

Command explanation:
- `python`: runs Python (use the project's virtual environment).
- `-m agents.requirement_agent.agent`: runs `agent.py` as a Python module, so package imports work. It must be run from `project/`.
- The quoted path: input SRS document, relative to `project/`.
- `--out "outputs/component1_demo.csv"`: where to save the CSV (required). The agent creates the output directory if necessary.
- Optional `--models-dir <folder>`: load the saved models from another folder (default `models/component1/part_a_active`).

The CSV is written with a UTF-8 BOM so Excel opens it correctly.

Running the agent can add the document's embeddings to `models/component1/part_a_active/embedding_cache/` (git-ignored); this is normal and only speeds up later runs.

### 5.3 Example terminal summary

```text
<number> candidate requirements -> outputs/component1_demo.csv
  warning: <any document warning>
  NFR: <count>, security-flagged: <count>, ambiguity=defect: <count>, in duplicate groups: <count>
```

The actual counts depend on the input document. The warning lines appear only when the reader reports a problem.

### 5.4 Print the result as JSON instead of CSV

The command line writes CSV only. To see the rows as JSON:

```powershell
python -c "import sys; from agents.requirement_agent.agent import run; print(run(sys.argv[1]).to_json(orient='records', indent=2))" "data/component1/processed/srs_extracted_text/2009 - library.txt"
```

## 6. Understand the CSV Output

| Column | Meaning |
|---|---|
| `requirement_id` | Identifier assigned to the extracted candidate (for example `SRS:<document>:0001`) |
| `source_document` | Input document name |
| `source_format` | Input format (`txt`, `html`, `pdf`, `docx`, `rtf`) |
| `position` | Order of the candidate in the document |
| `line_start` | Line in the extracted text where the candidate starts |
| `clause_label` | Clause number found in the document, such as `3.1` (empty if none) |
| `text` | Extracted requirement text |
| `word_count` | Number of words in `text` |
| `rule_type_hint` | Rule-based FR/NFR guess from the segmenter (`FR`, `NFR` or `unknown`); separate from the model prediction |
| `requirement_type` | Model-predicted FR or NFR |
| `nfr_probability` | Model probability for the NFR class |
| `is_security` | Whether security detection flagged the requirement |
| `security_cue_words` | Security-related cue words found |
| `ambiguity_label` | Predicted ambiguity label (`ok` or `defect`) |
| `ambiguity_score` | Model probability for the `defect` label |
| `weak_words_matched` | QuRE weak words matched in the requirement |
| `duplicate_group_id` | Group identifier (such as `DUP0001`) shared by potential duplicates; empty if none |
| `boundary_status` | Always `auto_unverified`: the requirement boundaries have not been checked by a person |
| `document_warnings` | Warnings reported during reading/extraction |

A requirement will not necessarily be flagged for security, ambiguity, or duplication.

## 7. Current Baseline Results

| Task | Model | Metric | Reported score [95% CI] |
|---|---|---|---:|
| FR/NFR classification | embeddings + LR | Macro-F1, frozen test | 0.828 [0.802, 0.852] |
| Security detection | keyword rules | Macro-F1, frozen test | 0.721 [0.670, 0.767] |
| Ambiguity detection | TF-IDF + LR | Macro-F1, frozen test | 0.685 [0.649, 0.722] |
| Weak-word rule (as a defect detector) | QuRE weak words | Macro-F1, frozen test | 0.525 [0.486, 0.561] |
| Duplicate detection | MiniLM cosine + DBSCAN | F1 on **seeded** pairs, held-out val | 0.812 [0.784, 0.837] |

The duplicate threshold (0.955) was chosen on seeded development pairs, where the best F1 was 0.853. All duplicate pairs are made by rules (case/punctuation changes, dropped modifiers, modal swaps and similar), so they are not human-labelled duplicates and say nothing about free paraphrases. With easy negatives only, F1 on the held-out pairs is 0.968.

The FR/NFR model is not the highest scorer on the frozen test (TF-IDF models reach about 0.865). It was chosen because it holds up best when tested on unseen PROMISE projects (leave-one-project-out macro-F1 0.798 against 0.64 to 0.65).

These results use different evaluation setups and should not be compared as if they were measured on the same test set. Macro-F1 is not accuracy.

For methodology, caveats, and detailed results, see:

```text
evaluation/component1/results/RESULTS.md
evaluation/component1/results/VERIFICATION.md
evaluation/component1/results/ERROR_ANALYSIS_NOTES.md
evaluation/component1/results/duplicates_eval/DUPLICATES_EVAL.md
models/component1/MODEL_MANIFEST.md
```

## 8. Rebuild or Evaluate Model Artifacts

These commands are for training/evaluation workflows, not required for every agent demo, except to create the saved models on a fresh clone:

```powershell
python -m evaluation.run_baselines --task fr_nfr
python -m evaluation.run_baselines --task nfr_subtype
python -m evaluation.run_baselines --task ambiguity
python -m evaluation.duplicates_eval --task seeded
```

- `--task fr_nfr`: trains and evaluates the FR/NFR baselines and saves `fr_nfr_*.joblib` to `models/component1/part_a_experiments/fr_nfr/`.
- `--task nfr_subtype`: trains and evaluates the security and PROMISE subtype baselines and saves `nfr_subtype_*.joblib` to `part_a_experiments/security_and_subtype/`.
- `--task ambiguity`: trains and evaluates the ambiguity baselines (including the weak-word rule) and saves `ambiguity_*.joblib` to `part_a_experiments/ambiguity/`.
- `--task seeded` (duplicates): evaluates duplicate detection on seeded pairs and writes `models/component1/part_a_active/duplicates_config.json` (the file the agent reads).
- `run_baselines` also accepts `--task all`; `duplicates_eval` also accepts `review` and `all`.

**These commands overwrite the result files.** By default they rewrite `RESULTS.md`, the per-task CSVs and notes in `evaluation/component1/results/`, and the models in `models/component1/part_a_experiments/`. The agent reads `part_a_active/`, which is not touched by `run_baselines`: copy the files you want there by hand. To create models without touching the committed results, send the results elsewhere:

```powershell
python -m evaluation.run_baselines --task all --out-dir outputs/baseline_results
python -m evaluation.duplicates_eval --task seeded --out-dir outputs/baseline_results
```

Other options: `--models-dir` (where to save models), `--no-save-models` (evaluate only) and `--n-boot` (bootstrap resamples). The training code uses the train and validation splits only, and the frozen test split is used only for the final reported numbers. For a presentation demo, run the existing agent first instead.

To check the code, run `python -m pytest tests -q` from `project/`.

## 9. Troubleshooting

**Saved model missing:** Check that the four `.joblib` files and `duplicates_config.json` exist in `models/component1/part_a_active/` (the `.joblib` files are git-ignored, so they are absent after a fresh clone). The error message names the missing file and the command that creates it (see section 8).

**Unsupported format:** Use `.txt`, `.html`, `.pdf`, `.docx`, or `.rtf`. Legacy `.doc` is rejected on purpose; convert it first.

**No candidate requirements extracted:** Try a different SRS document, or inspect whether the document contains requirement-like text (sentences with shall/must/should/will, or numbered clauses) that the segmenter can identify.

**Input file not found:** Check the path relative to `project/` and verify the exact filename.

**`ModuleNotFoundError: No module named 'agents'`:** You are not in `project/` (for example you are in the repository root `J26-SE-327/`). Run `cd project` and repeat the command.

**Python package/import errors:** Activate the project's virtual environment (`..\.venv`), install `requirements.txt`, and run the module command from the `project/` directory.

**First run is slow or fails offline:** The first run that needs embeddings downloads the `all-MiniLM-L6-v2` model. Connect to the internet once; later runs are fast.

## 10. Limitations

- Extracted candidate requirements and predictions may contain errors.
- `boundary_status=auto_unverified` means outputs have not been manually verified.
- The models are weak baselines. For example, ambiguity macro-F1 is 0.685 on the frozen test and drops to 0.37 to 0.49 when a model is trained on one source and tested on the other.
- Keyword-based security detection can miss unfamiliar wording or flag unrelated text.
- The FR/NFR model can label functional statements as NFR (for example, a security-related lock-out rule).
- Ambiguity scores are model outputs, not guaranteed probabilities of a real-world defect.
- Similarity-based duplicate detection can flag related but non-duplicate requirements (about 37% of the hard negatives in the seeded evaluation) or miss paraphrases. Duplicates are only searched within one document.
- Evaluation scores depend on dataset composition, labels, splits, and methodology.
- Review important outputs before using them for project decisions.

## 11. Quick Demo Checklist

- [ ] Open a terminal in the `project/` directory.
- [ ] Activate the virtual environment (`..\.venv\Scripts\Activate.ps1`).
- [ ] Confirm that `models/component1/part_a_active/` has the four `.joblib` files; if not, run section 8.
- [ ] Confirm that the input document exists (not a `.doc` file).
- [ ] Run the agent command with an output path under `outputs/`.
- [ ] Open the generated CSV and inspect the predictions.
- [ ] Open `evaluation/component1/results/RESULTS.md` to explain the evaluation results.
- [ ] Explain that outputs are unverified analysis hints and require review.
