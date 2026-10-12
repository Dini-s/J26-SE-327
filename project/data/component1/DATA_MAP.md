# Component 1 data map

Index of what is where. Nothing here was moved; paths are relative to `project/data/component1/` unless they start with `experiments/`, `evaluation/` or `models/`.
Row counts are copied from `processed/DATA_CARD.md`, `processed/tasks/manifest.json` or `evaluation/component1/results/RESULTS.md`; a dash means no count is recorded there.
`raw/` is read-only source data and is never edited.

## 1. FR / NFR classification

| item | files |
|---|---|
| raw sources | `raw/FR_NFR_Dataset.xlsx` (6117 rows in), `raw/promise.csv` (625), `raw/PROMISE-relabeled-NICE.csv` (622), `raw/nfr_labeled.txt`, `raw/test_labeled.txt`, `raw/software_requirements_extended.csv` (its normalized copy has 977 rows in, see DATA_CARD.md) |
| processed | `processed/master_requirements.csv` (33983), `processed/tasks/classification_fr_nfr.csv` (6139), `processed/nfr_labeled_parsed.csv`, `processed/test_labeled_parsed.csv`, `processed/software_requirements_extended_normalized.csv` |
| built by | `experiments/component1/prepare_labeled_datasets.py` (the `*_parsed.csv` files), `build_master.py` (master table), `build_task_datasets.py` (task file and splits) |
| models and results | `models/component1/part_a_active/fr_nfr_fr_nfr_emb_lr.joblib` (used by the agent), baselines in `part_a_experiments/fr_nfr/`; `evaluation/component1/results/fr_nfr_*.csv`, `RESULTS.md` |
| frozen test | pooled n=935 (RESULTS.md) |

## 2. Security and NFR subtype

| item | files |
|---|---|
| raw sources | `raw/security_requirements.csv` (511), `raw/pure_subset.csv` (11440), `raw/promise.csv` (625) |
| processed | `processed/tasks/classification_nfr_subtype.csv` (9343), `processed/nfr_label_mapping.csv` |
| built by | `build_master.py`, `build_task_datasets.py` |
| models and results | `models/component1/part_a_active/nfr_subtype_security_binary_rules.joblib` (used by the agent), baselines in `part_a_experiments/security_and_subtype/`; `evaluation/component1/results/nfr_subtype_*.csv` |
| frozen test | security n=1285, PROMISE multi-label n=43 (RESULTS.md) |

## 3. Ambiguity

| item | files |
|---|---|
| raw sources | `raw/QuRE.csv` (2187), `raw/DS1.xlsx` (985), `raw/DS2.xlsx` (1092), `raw/DS3.xlsx` (1522), `raw/DS4.xlsx` (1153), `raw/arta_evaluation/001-006_*.xlsx` |
| processed | `processed/tasks/ambiguity.csv` (4846), `processed/tasks/ambiguity_arta_conflict_samples.csv` (20) |
| built by | `build_master.py`, `build_task_datasets.py` |
| models and results | `models/component1/part_a_active/ambiguity_ambiguity_tfidf_lr.joblib` and `..._qure_weak_word_rule.joblib` (used by the agent), baselines in `part_a_experiments/ambiguity/`; `evaluation/component1/results/ambiguity_*.csv` |
| frozen test | pooled n=652 (RESULTS.md) |

## 4. Duplicates

| item | files |
|---|---|
| raw sources | none labelled; `DATA_CARD.md` states that no real labelled duplicate pairs exist in the sources |
| processed | `processed/master_requirements.csv` (text source), rule-made pairs in `evaluation/component1/results/duplicates_eval/seeded_pairs_dev.csv` and `seeded_pairs_eval.csv` |
| built by | `evaluation/duplicates_eval.py` (`--task seeded`) |
| config and results | `models/component1/part_a_active/duplicates_config.json` (threshold 0.955), `evaluation/component1/results/duplicates_eval/DUPLICATES_EVAL.md` |
| note | seeded pairs only: 3000 development pairs, 1500 held-out pairs (DUPLICATES_EVAL.md); F1 0.853 dev, 0.812 held-out; not human-labelled |

## 5. Part B: SFT data for the story generator (`processed/llm_sft/`)

| item | files |
|---|---|
| seeds (train split only) | `processed/tasks/synthetic_seed_inputs.csv` (150), `synthetic_seed_inputs_batch2.csv`, `synthetic_seed_inputs_batch3.csv` and `_batch3_raw.csv`, with `_batch2_report.md` / `_batch3_report.md` |
| generated pairs | `processed/llm_sft/synthetic_batches/batch_001..046.jsonl`, `retry_001.jsonl` |
| validated and merged | `validated_new.jsonl`, `rejects.jsonl`, `qa_sample_100.jsonl`, `synthetic_pairs_all.jsonl` (2850 pairs: ok 2392, needs_clarification 458) |
| chat format for fine-tuning | `sft_train.jsonl` (2566), `sft_val.jsonl` (284); the earlier 550-pair set is kept as `synthetic_pairs_all_550.jsonl`, `sft_train_550.jsonl`, `sft_val_550.jsonl` |
| built by | `experiments/component1/build_synthetic_seed_batch2.py`, `build_synthetic_seed_batch3.py`, `sft_batches.py`, `validate_sft_pairs.py`, `build_sft_dataset.py` |
| checks | `tests/test_sft_dataset.py`, `tests/test_synthetic_seed_batch2.py` |
| note | outputs are synthetic and rule-validated only; see the SFT section of `processed/DATA_CARD.md` |

## 6. Evaluation splits (`processed/tasks/`)

| file | rows | purpose |
|---|---|---|
| `frozen_test_ids.csv` | 6582 | frozen test record ids (SHA-256 in `manifest.json`) |
| `manifest.json` | - | seed, settings, SHA-256 of every task file |
| `generation_eval_ids.csv` | 100 | ids only of test requirements reserved for the final base-vs-fine-tuned comparison |
| `generation_eval_inputs.csv` | - | texts for the same evaluation requirements (never used for training or seeds) |
| `generation_inputs.csv` | 21105 | pools of requirement texts and user-story references |
| `dependency_pairs.csv` | 7329 | FR-NFR pairs, semantics unconfirmed |
| `pipeline_test_cornelius.csv` | 200 | pipeline smoke test only |
| `dependency_spot_check.csv`, `srs_extraction_spot_check.csv` | 20, 100 | rows for manual checking |

Built by `experiments/component1/build_task_datasets.py`; read through `evaluation/data_access.py`, which refuses the test split during development.

## 7. SRS documents (agent input, not labelled)

| item | files |
|---|---|
| raw | `raw/documents/srs/` (76 files: pdf, doc, rtf), `raw/documents/html/` (3 files) |
| processed | `processed/srs_extracted_text/` (76 .txt files), `processed/srs_requirements_extracted.csv` (13361 candidate rows, all `auto_unverified`) |
| built by | `experiments/component1/build_srs_requirements.py` |
| used by | `agents/requirement_agent/` (demo input), `audit_tcs_requirement_boundaries.py` |

## 8. Audit reports (`audit_reports_component1/`, 82 files)

Outputs of the dataset audits, kept for traceability. Examples: `processed_build_report.csv` (98 rows, one per input file: rows in / dropped / out), `srs_requirements_per_document_counts.csv` (79), `dataset_suitability_tracker.csv` and its dated backups, `arta_*` (ARTA duplicate and label checks), `tcs_*` (TCS boundary audit v2/v3), `user_story_*`, `pure_*`, `cornelius_*`, `source_vs_project_*` (hash checks), `nfr_arff_git_diff_review.txt`.

## 9. Experiment scripts (`experiments/component1/`)

| purpose | scripts |
|---|---|
| inventory and verification | `inventory_datasets.py`, `audit_datasets.py`, `verify_all_source_files.py`, `verify_all_source_hashes.py`, `audit_remaining_datasets.py` |
| dataset-specific audits | `audit_arta_*.py`, `check_arta_*.py`, `compare_arta_*.py`, `audit_cornelius_ambiguity.py`, `check_cornelius_label_conflicts.py`, `analyze_pure_duplicates.py`, `inspect_pure_conflicts.py`, `check_pure_encoding.py`, `audit_nfr_arff.py`, `compare_nfr_arff.py`, `compare_nfr_sources.py`, `audit_nfr_fr_trace.py`, `audit_user_stories.py`, `check_dataset_overlap.py`, `check_user_story_overlap.py`, `semantic_overlap_audit.py` |
| traceability matrices | `convert_trace_matrix.py`, `validate_trace_matrix.py`, `audit_trace_relationships.py` |
| processed data build | `prepare_labeled_datasets.py`, `build_master.py`, `build_srs_requirements.py`, `build_task_datasets.py`, `audit_tcs_requirement_boundaries.py`, `report_srs_ingestion_formats.py` |
| Part B (SFT) | `build_synthetic_seed_batch2.py`, `build_synthetic_seed_batch3.py`, `sft_batches.py`, `validate_sft_pairs.py`, `build_sft_dataset.py` |
| notes | `dataset_audit_notes.md` |

## Show in viva (6 files)

1. `processed/DATA_CARD.md`: every processed file, how it was built, row counts, caveats, and the SFT section.
2. `processed/master_requirements.csv`: the cleaned master table with provenance (33983 rows).
3. `processed/tasks/manifest.json`: seed and SHA-256 of the task files and the frozen test ids (shows the test split is fixed).
4. `evaluation/component1/results/RESULTS.md` (outside `data/`): baseline scores with confidence intervals.
5. `processed/llm_sft/synthetic_pairs_all.jsonl`: the 2850 story/task/criteria pairs for Part B.
6. `audit_reports_component1/processed_build_report.csv`: one row per input file with rows in, dropped and kept.

## Files in `data/component1/` that no script or test names

Found by searching every `.py` file (agents, evaluation, experiments, tests, config) for each file name. This is a name search only: a script can still write a file whose name it builds in code, or the file may come from a one-off command that is not in the repo. Nothing was deleted or moved.

**Likely produced by an existing script with a computed name** (confirm before treating as unused):
- `tcs_*_v3.csv/.md`, `tcs_requirement_boundary_audit.csv`: `audit_tcs_requirement_boundaries.py`
- `arta_001_003_005_presence_agreement.csv`, `arta_002_duplicate_metric_audit.csv`, `arta_annotation_*`, `arta_consolidated_audit_summary.csv`, `arta_file_structure_comparison.csv`: the `audit_arta_*` / `check_arta_*` scripts
- `dataset_suitability_tracker_backup_*.csv` (4 files): backups made before edits to the tracker
- `remaining_dataset_inventory.csv`: `audit_remaining_datasets.py`
- `nfr_source_original_vs_labeled_line_differences.csv`, `nfr_source_vs_labeled_detailed_differences.csv`: `compare_nfr_sources.py`

**No script in the repo appears to write or read them** (likely one-off outputs, or produced by scripts that are not in the repo):
- `audit_reports_component1/`: `basic_context_context_role_semantic_matches.csv`, `current_project_raw_inventory.csv`, `current_project_raw_inventory_detailed.csv`, `doc_extraction_audit.csv`, `document_candidates.csv`, `fr_nfr_dataset_exact_duplicates.csv`, `fr_nfr_dataset_label_conflicts.csv`, `fr_nfr_dataset_missing_labels.csv`, `nasa_x38_requirement_id_context_audit.csv`, `nfr_arff_git_diff_review.txt`, `nfr_dataset_overlap_comparison.csv`, `nfr_duplicate_label_conflict_review.csv`, `nfr_labeled_vs_test_labeled_overlap.csv`, `promise_vs_nice_label_disagreements.csv`, `security_requirements_duplicate_texts.csv`, `security_requirements_label_conflicts.csv`, `smelly_words_dictionary_audit.csv`, `software_requirements_extended_duplicates.csv`, `software_requirements_extended_label_conflicts.csv`, `source_extension_summary.csv`, `source_folder_summary.csv`, `source_vs_project_hash_verification_classified.csv`, `srs_all_documents_requirement_pattern_audit.csv`, `srs_manual_review_decisions_preview.csv`, `srs_manual_review_decisions_provisional.csv`, `srs_manual_review_priority_list.csv`, `srs_requirement_id_pattern_audit.csv`, `srs_text_extraction_report.csv`
- `raw/`: `nfr_project_before_replace.arff`, `nfr_README.txt` (raw files; left as they are)
