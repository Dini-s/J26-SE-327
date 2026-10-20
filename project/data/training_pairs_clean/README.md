# data/generated_pairs_clean: the cleaned pairs the CodeBERT was trained on

Written by `scripts/prepare_generated_pairs.py` from `data/generated_pairs/` (LLM-written pairs). `train.jsonl` and `valid.jsonl` hold 3 rows per item (1 right code, 2 hard negatives; fields `dataset, source_id, target_id, query, doc, label, kind`; the value of `dataset` is the historic tag `"synthetic"`, kept so the files stay byte-identical to what the model was trained on). `clean_report.json` counts what each rule removed. The split is by domain (seed 33).
