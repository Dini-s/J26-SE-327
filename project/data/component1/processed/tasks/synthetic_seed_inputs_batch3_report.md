# Synthetic seed inputs, batch 3: report

File: `processed/tasks/synthetic_seed_inputs_batch3.csv` (2300 rows; target 2300). Seed 327. No model or LLM calls; test texts were embedded in memory only for the similarity guard and are not printed or written.

## Counts per source

| source | rows | FR | NFR | unlabeled |
|---|---|---|---|---|
| FR_NFR | 1371 | 811 | 560 | 0 |
| PURE | 330 | 0 | 330 | 0 |
| DS4 | 230 | 0 | 0 | 230 |
| QuRE | 230 | 0 | 0 | 230 |
| PROMISE | 89 | 9 | 80 | 0 |
| DS2 | 25 | 0 | 0 | 25 |
| security_requirements | 17 | 0 | 0 | 17 |
| DS3 | 5 | 0 | 0 | 5 |
| DS1 | 3 | 0 | 0 | 3 |
| **all** | 2300 | 820 | 970 | 510 |

Words per text: min 6, median 15, max 59. Rows with a cleaned text (original in `synthetic_seed_inputs_batch3_raw.csv`): 461.
Weak-word / vague / short seeds (so the generator meets needs_clarification cases): 403 (18%).

Quotas vs available (label, group): FR/FR_NFR: wanted 560, available 2236, got 811; NFR/FR_NFR: wanted 560, available 1110, got 560; NFR/PROMISE: wanted 80, available 96, got 80; FR/PROMISE: wanted 60, available 9, got 9; NFR/PURE: wanted 330, available 1164, got 330; any/DS4: wanted 230, available 412, got 230; any/QuRE: wanted 230, available 1176, got 230; any/other: wanted 50, available 325, got 50. PROMISE is nearly exhausted by batches 1-2, so it cannot keep its 35 % share; FR_NFR, PURE, DS4 and QuRE make up the difference.

## Filter funnel (rows removed by each filter, in order)

| step | rows |
|---|---|
| train requirement_text rows that are in master_requirements.csv | 13040 |
| removed: id of an existing seed (batches 1-2), frozen test id or generation_eval id | 550 |
| rows whose text was cleaned (artifact removal; kept, not removed) | 3177 |
| removed: fewer than 6 or more than 60 words (after cleaning) | 179 |
| removed: empty or does not end like a sentence | 1810 |
| removed: garbled/placeholder (mostly_non_letters) | 16 |
| removed: garbled/placeholder (placeholder) | 18 |
| removed: garbled/placeholder (repeated_characters) | 1 |
| removed: garbled/placeholder (very_long_token) | 11 |
| removed: extraction noise (page_number) | 0 |
| removed: extraction noise (table_fragment) | 3 |
| removed: extraction noise (all_caps_heading) | 0 |
| removed: extraction noise (url_only) | 0 |
| removed: extraction noise (encoding_noise) | 23 |
| removed: extraction noise (starts_mid_sentence) | 222 |
| removed: unlabeled row of a labelled source (FR_NFR, PROMISE, PURE) | 3271 |
| removed: same normalized text as an existing seed / val / test / eval text | 0 |
| removed: same normalized text as another pool row (kept the first by hash order) | 8 |
| removed: cosine > 0.9 to an existing seed (batches 1-2) | 94 |
| removed: cosine >= 0.85 to a test text or an eval input | 306 |
| candidates left for the stratified pick | 6528 |
| skipped during the pick: cosine > 0.9 to an already selected seed | 42 |

## Confirmations (computed from the written file)

- ids overlapping frozen_test_ids.csv: **0**
- ids overlapping generation_eval_ids.csv: **0**
- ids overlapping batches 1-2: **0**
- texts with the same normalized text as an existing seed / val / test / eval text: **0**
- max cosine of any batch-3 seed to any of the 3125 test/eval texts: **0.849** (limit 0.85; OK)
- max cosine to a batch 1-2 seed: 0.900 (limit 0.9)
- max cosine between two batch-3 seeds: 0.900 (limit 0.9)
