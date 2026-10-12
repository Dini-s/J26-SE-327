# Synthetic seed inputs, batch 2: report

File: `processed/tasks/synthetic_seed_inputs_batch2.csv` (400 rows; target 400). Seed 327. No model or LLM calls; test texts were embedded in memory only for the similarity guard and are not printed or written anywhere.

## Counts

Split: all rows are `train` (selected only from rows with split == train in `generation_inputs.csv`; `master_requirements.csv` has no split column).

| source | FR | NFR | unlabeled | total | target share |
|---|---|---|---|---|---|
| FR_NFR | 110 | 50 | 0 | 160 | 40 % (actual 40%) |
| PROMISE | 60 | 80 | 0 | 140 | 35 % (actual 35%) |
| PURE | 0 | 40 | 0 | 40 | 10 % (actual 10%) |
| other | 0 | 0 | 60 | 60 | 15 % (actual 15%) |
| **all** | 170 | 170 | 60 | 400 | |

Sources inside "other": DS4=27, QuRE=22, DS2=5, security_requirements=5, DS3=1.

FR/NFR among labelled rows: 170 FR / 170 NFR.
Words per text: min 6, median 16, max 52.

## Weak-word / vague / short rows (for needs_clarification cases)

60 of 400 rows (15%): short=27, weak_word=22, vague_term=11. Weak words are the 23 QuRE weak words from train rows; vague terms are a small fixed list (etc., and/or, as appropriate, adequate, user-friendly, ...); short = at most 8 words.

## Filter funnel (rows removed by each filter, applied in this order)

| step | rows |
|---|---|
| train requirement_text rows that are in master_requirements.csv | 13040 |
| removed: id in batch 1 / frozen test ids / generation_eval ids | 150 |
| removed: fewer than 6 or more than 60 words | 176 |
| removed: does not end like a sentence | 1810 |
| removed: extraction noise (page_number) | 0 |
| removed: extraction noise (table_fragment) | 5 |
| removed: extraction noise (all_caps_heading) | 0 |
| removed: extraction noise (url_only) | 0 |
| removed: extraction noise (encoding_noise) | 23 |
| removed: extraction noise (starts_mid_sentence) | 223 |
| removed: no FR/NFR label and not an 'other' source row (unlabeled rows of labelled sources) | 3287 |
| removed: same normalized text as a batch-1 seed or any val/test text | 0 |
| removed: same normalized text as another pool row (kept the first by hash order) | 0 |
| removed: cosine >= 0.9 to a batch-1 seed | 30 |
| removed: cosine >= 0.9 to a frozen test text | 167 |
| candidates left for the stratified pick | 7169 |
| skipped during the pick: cosine >= 0.9 to an already selected row | 2 |

## Confirmations (computed from the written file)

- ids overlapping frozen_test_ids.csv: **0**
- ids overlapping generation_eval_ids.csv: **0**
- ids overlapping batch 1 (synthetic_seed_inputs.csv): **0**
- texts with the same normalized text as a batch-1 seed or any val/test text: **0**
- max cosine similarity of any batch-2 row to any of the 3122 frozen-test texts: **0.898** (limit 0.9; OK)
- max cosine similarity to any batch-1 seed: 0.858
- max cosine similarity between two batch-2 rows: 0.895
- split of every selected row in generation_inputs.csv: train (400 of 400)

Notes: similarity uses all-MiniLM-L6-v2 embeddings of the normalized text; the noise filters are heuristics; the quota shortfalls, if any: none.
