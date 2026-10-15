## Rerun after a one-row train correction

The first full run found that project `PROMISE_P15` was in the test split while one row (`PROMISE_NICE:656b1b569a`) had landed in train. That row is now excluded (`held_out_project_split_conflict`) from `classification_fr_nfr`, `classification_nfr_subtype` and `generation_inputs`; nothing was moved into test. `frozen_test_ids.csv` is byte-identical (SHA-256 `5b2fed2f...6350`, 6,582 rows) and the frozen hash recorded in `manifest.json` is unchanged; the manifest file itself changed only because it records the hashes of the three task files that lost one row.
The three baseline tasks were then rerun with the same code, seed (327) and hyperparameter grids; no grid or selection rule changed. 
Disclosure kept from the first run: after a first smoke run printed FR/NFR test scores, the C grid for logistic regression (TF-IDF and embeddings) was extended to include 1000 because the validation table showed the best value on the grid edge. That grid is used here unchanged.

Effect on the frozen test split: 100 of 1140 test and cross-source metric values changed (all in models that learn from the training rows: `tfidf_lr`, `tfidf_svm`, `emb_lr`). `majority`, the keyword rules, and every ambiguity result are unchanged. Best model by validation is unchanged in every task. Tuned C changed for `emb_lr` on FR/NFR (100 -> 1000) and on security (10 -> 100). The full list (every metric, per class) is in `rerun_test_changes.csv`. Changes in the headline macro/micro-F1 values:

| task | subtask | slice | model | metric | before | after | change |
|---|---|---|---|---|---|---|---|
| nfr_subtype | security_binary | source=security_requirements | tfidf_lr | macro_f1 | 0.829 | 0.797 | -0.031 |
| nfr_subtype | security_binary | pooled | tfidf_lr | macro_f1 | 0.648 | 0.618 | -0.030 |
| nfr_subtype | security_binary | source=PURE | tfidf_lr | macro_f1 | 0.573 | 0.550 | -0.022 |
| nfr_subtype | security_binary | pooled | emb_lr | macro_f1 | 0.645 | 0.626 | -0.020 |
| nfr_subtype | security_binary | source=PURE | emb_lr | macro_f1 | 0.571 | 0.555 | -0.016 |
| nfr_subtype | promise_subtype_multilabel | pooled | tfidf_svm | micro_f1 | 0.500 | 0.485 | -0.015 |
| fr_nfr | fr_nfr | source=PROMISE | emb_lr | macro_f1 | 0.802 | 0.815 | +0.014 |
| nfr_subtype | promise_subtype_multilabel | pooled | emb_lr | micro_f1 | 0.606 | 0.617 | +0.011 |
| nfr_subtype | promise_subtype_multilabel | pooled | tfidf_svm | macro_f1 | 0.514 | 0.505 | -0.009 |
| nfr_subtype | promise_subtype_multilabel | pooled | emb_lr | macro_f1 | 0.513 | 0.521 | +0.008 |
| nfr_subtype | promise_subtype_multilabel | pooled | tfidf_lr | micro_f1 | 0.521 | 0.526 | +0.005 |
| nfr_subtype | promise_subtype_multilabel | pooled | tfidf_lr | macro_f1 | 0.525 | 0.530 | +0.005 |
| fr_nfr | fr_nfr | pooled | emb_lr | macro_f1 | 0.827 | 0.828 | +0.001 |
| fr_nfr | fr_nfr | source=FR_NFR | emb_lr | macro_f1 | 0.827 | 0.828 | +0.000 |

The largest shifts are on security with `tfidf_lr` / `emb_lr` (up to -0.031 macro-F1) and on the 43-row PROMISE subtype test (up to 0.015 micro-F1); these are well inside the reported bootstrap CIs but show how sensitive the LR models are to a single training row.
