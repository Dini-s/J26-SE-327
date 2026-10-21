# Independent verification of the Component 1 baseline results

Existing results were treated as claims to check. Checks ran against the saved files with scratch scripts and reruns kept outside the repo.
Seed 327, repo commit `55605ac` plus untracked work. This is the **second verification round**, run after the P15 correction, the CV re-slicing,
the new RESULTS.md tables and the rewritten error notes.

## Summary

| # | Item | First round | Now |
|---|---|---|---|
| 1 | Test isolation and selection logic | PASS (code); history NOT CHECKABLE | **PASS** (code); history NOT CHECKABLE (1c) |
| 2 | Split consistency | FAIL (`PROMISE_P15` spanned train and test) | **PASS** |
| 3 | Reproducibility | PASS | **PASS** |
| 4 | Report consistency | FAIL (4 unsupported claims in the error notes) | **PASS** |
| 5 | Reporting hygiene | FAIL (no per-class tables or confusion matrices; misleading CV slice) | **PASS** (small notes in 5) |
| 6 | Known limits | restated | restated |

## What changed since the first round
- `build_task_datasets.py` now excludes any row whose project group sits in the test split but which landed in train/val (reason `held_out_project_split_conflict`), applied after the text-overlap removal so the test split cannot change. It excluded one row, `PROMISE_NICE:656b1b569a`, from `classification_fr_nfr`, `classification_nfr_subtype` and `generation_inputs`.
- `frozen_test_ids.csv` is byte-identical (SHA-256 `5b2fed2f...6350`, 6,582 rows) and the frozen hash recorded in `manifest.json` is unchanged. The manifest file itself changed, because it records the hashes of the three task files that lost one row. No row was added to test.
- The three baseline tasks were rerun with the same code, seed and grids (see "Rerun after a one-row train correction" in `RESULTS.md` and `rerun_test_changes.csv`): 100 test/cross-source values changed, all in models that learn from training rows; best model by validation is unchanged in every task.
- CV is now reported as two separate slices (grouped CV on rows with real groups, stratified CV on rows without groups). RESULTS.md has per-class results and confusion matrices.
- `ERROR_ANALYSIS_NOTES.md` was rewritten with counts.

## 1. Test isolation: PASS (code)

**1a. Who reads the test rows.** Searched `agents/`, `evaluation/*.py`, `experiments/` for `frozen_test_ids`, `"test"`, `read_csv`, `tasks/`.
- Only `evaluation/data_access.py` reads `tasks/*.csv` and `frozen_test_ids.csv`. `load_task` (line 28) raises `FrozenTestError` for any split other than train/val and asserts no test row in its output.
- `load_test_for_final_evaluation` (line 60) calls `verify_frozen_test` first (line 62): SHA-256 of `frozen_test_ids.csv` against `manifest.json`, SHA-256 of the task file, and test record ids equal to the frozen ids.
- Exactly three call sites in `evaluation/run_baselines.py`: line 240 (`final_fr_nfr`), line 372 (`final_ambiguity`), line 481 (`main`, nfr_subtype branch), each after that task's `develop`/`cross_validate` calls. An AST test enforces this; a mutation (a test-loader call added to `run_fr_nfr`) made it fail.
- `agents/requirement_agent/{features,classifier,ambiguity}.py` and `evaluation/metrics.py` read no files and never mention the loader (enforced by `test_training_modules_do_not_know_the_test_loader`).
- `experiments/component1/build_task_datasets.py` writes the test rows (it creates the splits) and never trains.

**1b. Selection logic.** Every choice is made from train/val: `tune_and_fit` (`classifier.py:141`) scores each C on the validation arrays only; best model per task is `run_baselines.py:160` (single-label) and `:284` (multi-label), computed from `val_score` and never recomputed in `final()`; cross-source models are tuned on the source family's val rows; QuRE weak words come from QuRE train rows; CV and leave-one-project-out use train+val only; no threshold is tuned.

**1c. NOT CHECKABLE (history, not code).**
- The keyword-rule cue lists were written before any run, from general vocabulary.
- A first smoke run of `fr_nfr` printed test scores before the final run. Afterwards the C grid for LR was extended to include 1000 because the **validation** table showed the best value on the grid edge. No other model, feature or hyperparameter choice changed. This is also disclosed in RESULTS.md. A stricter reader should treat the LR C grid as seen-test-adjacent.
- `manifest.json` is not pinned by an external hash, so an edit of both manifest and files together would pass the check.

## 2. Split consistency: PASS

Keys recomputed independently (lowercase, collapsed whitespace, alphanumerics only) from `requirement_text_original` and `requirement_text_normalized`.

| Check | Result |
|---|---|
| Text overlap train/val/test, each task (fr_nfr, nfr_subtype, ambiguity, generation_inputs, pipeline_test_cornelius) | **0** for every pair, both text columns |
| Dependency pairs (`fr_text`, `nfr_text`, both keys) | **0** for every pair |
| One text key in more than one split across all task files | **0** keys |
| `PROMISE_P9`, `PROMISE_P10` rows in train/val | **0**; 53 rows, all test, in each of fr_nfr, nfr_subtype, generation_inputs; dependency: 698 pairs, all test, test contains only P9 and P10 |
| P9/P10 texts in train/val of any task or in train/val dependency pairs | **0** |
| Anchoring rule (non-PROMISE rows whose text is a PROMISE text inherit the PROMISE project's split) | 417 such rows (all in `ambiguity`, from DS3), **417/417** correct, 0 mismatches |
| Every PROMISE project that is in test (P9, P10, P14, P15) has no train/val row in any task | **yes** (previously P15 failed) |

Groups that span more than one split, all tasks, with explanations:
- `FR_NFR:ungrouped`, `QuRE:ungrouped`, `security_requirements:ungrouped`: dummy groups for sources with no document or project; split at text level (expected).
- `ARTA:DS3:text_requirements.json` (ambiguity): explained by the 417 anchored PROMISE copies; the other rows are in one split (the intentional anchoring exception).
- `Cornelius:*` (34 groups, pipeline test file): row-level hash split by design.
- No unexplained group remains.

## 3. Reproducibility: PASS

All three tasks were rerun into a scratch folder (`--no-save-models`) and all 17 output files, including `RESULTS.md`, `rerun_note.md` and the errors files, are **byte-identical** to the saved ones. The test and validation numbers of the final run are also identical to a run of the same code on the corrected data made before the report changes (0 value or CI differences over 1,548 compared rows). The unit tests run twice give identical metrics frames. Caveat: the rerun reuses the embedding cache; cached versus freshly computed embeddings differed by at most 9e-08 (60 texts).

## 4. Report consistency: PASS

- `RESULTS.md`: 516 summary rows, 181 per-class rows and 118 confusion rows (single-label 2-class tables and multi-label 2x2 tables) were parsed and compared with the CSVs (value to 3 decimals, CI bounds, support, n): **0 mismatches, 0 rows not found**. Every test confusion table sums to its `n_rows`.
- `ERROR_ANALYSIS_NOTES.md`: 50 numeric claims were recomputed with separate code (plain `csv`/`re`, not the code that produced the numbers); **0 mismatches**. One count needed a note: the 17 PURE false positives all contain a security cue in the normalized text the rule reads, but only 16 of 17 in the original text shown in the errors file; the notes now say both. Claims without a count are labelled hypothesis.
- Five-row spot check per task (rows 3, 9, 15, 21, 27 of each errors file), per-row attributes against the counted patterns: fr_nfr rows are 8-14 words, 4 of 5 contain *shall*, none multi-sentence (matches the counts); security rows include a PURE false positive with a cue (#21, *password*), a PURE false negative with no cue and 8 words (#27), and a `security_requirements` false negative (#15); multi-label rows #9, #21, #27 are empty predictions, #15 is A|PE->PE, all 5 end with a stray quote (30 of 30 in the sample); ambiguity rows #3, #9, #27 are ok->defect with a modal, #15 is a 60-word defect->ok row, #21 is an ok->defect row without a modal. All consistent with the stated counts.

## 5. Reporting hygiene: PASS

- Separate tables: frozen test, cross-source (frozen test), grouped CV, stratified CV, PROMISE-only leave-one-project-out, and validation each have their own table in `RESULTS.md`; the CSV `evaluation` column separates them too; the page header says they are not comparable estimates.
- CIs and support: every test, cv and cross-source summary row (424 of 424) and every pooled leave-one-project-out row (16 of 16) has a 95% CI and `n`. Per-class tables for the frozen test split show precision, recall, F1 (with CI) and support; 15 of 615 per-class rows have no CI because the class has no test support (PO in the PROMISE multi-label test, support 0).
- CV slices are now `grouped_cv:rows_with_real_groups` and `stratified_cv:rows_without_groups`, each with its own `n`: ambiguity 2,461 / 1,733; fr_nfr 403 / 4,801; security 7,682 / 373. The PROMISE multi-label grouped CV leaves out the ungrouped PROMISE rows (too few for a stratified slice) and says so.
- Remaining small points (not failures): per-project leave-one-project-out rows and validation rows have no CI by design (CSV only / tuning only); single-class projects P11-P13 give a trivial 1.0 and are explained in the notes; the PO row in the multi-label per-class table shows 0.000 with support 0, which should be read as "not evaluable".

## 6. Known limits (restated)

- PURE validation is a single document (HIPAA); PURE test has 32 security positives. Model selection on val is noisy for security.
- The PROMISE subtype test set has 43 rows (PO 0, SC 1, FT 2, L 3 positives); per-class numbers are unreliable. Rows with an empty subtype are excluded, not treated as all-zero.
- ARTA labels are derived from smell-term columns ("defect" = any smell term), and the ARTA files conflict (479 conflicts, excluded).
- QuRE and ARTA define ambiguity differently, so cross-source results mix definition shift with domain shift. The QuRE weak-word rule is lopsided: on QuRE test it catches 92% of defects but also flags 72% of `ok` rows (macro-F1 0.46); on ARTA it flags few rows (defect recall 0.17, precision 0.83; macro-F1 0.52). Pooled macro-F1 is 0.53 [0.49, 0.56].
- Reliability is not evaluated (34 positives in train, 0 in val).
- FR/NFR: FR_NFR has no project grouping; PROMISE-only leave-one-project-out is the domain-shift estimate; the 76 PROMISE test rows give wide CIs.
- The split has the PROMISE anchoring deviation from pure strategy B (150 PROMISE val+test rows instead of 4) and one row excluded for the held-out-project conflict.
- The LR models are sensitive to a single training row (the one-row correction moved security macro-F1 by up to 0.031), so differences of that size between models are not meaningful.
- Embedding models depend on the cached `all-MiniLM-L6-v2` vectors (CPU); the cache is git-ignored.
