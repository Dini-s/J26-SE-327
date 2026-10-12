# Duplicate detector: seeded evaluation

**All pairs here are rule-made (`seeded_eval_only`); they are not human-labelled duplicates, are never training data, and the frozen test split is not used.** Threshold 0.955 was chosen on 3000 development pairs from the train split (max F1 0.853); numbers below are on 1500 held-out pairs from the val split (500 positives, 500 hard negatives, 500 easy negatives). 95 % bootstrap CIs in brackets.

| negatives used | precision | recall | F1 |
|---|---|---|---|
| easy + hard negatives | 0.716 [0.682, 0.753] | 0.938 [0.915, 0.957] | 0.812 [0.784, 0.837] |
| easy negatives only (without hard negatives) | 1.000 [1.000, 1.000] | 0.938 [0.916, 0.959] | 0.968 [0.956, 0.979] |

Pair-level classification by cosine >= threshold. With DBSCAN grouping (a pair is a duplicate when both texts fall in the same group):

| negatives used | precision | recall | F1 |
|---|---|---|---|
| easy + hard negatives | 0.716 [0.682, 0.753] | 0.938 [0.915, 0.957] | 0.812 [0.784, 0.837] |
| easy negatives only | 1.000 [1.000, 1.000] | 0.938 [0.916, 0.959] | 0.968 [0.956, 0.979] |

Recall by edit type and flag rate of the negatives (eval set):

| item | value | pairs |
|---|---|---|
| recall_by_edit:case_punctuation | 0.972 | 178 |
| recall_by_edit:clause_reorder | 0.867 | 15 |
| recall_by_edit:drop_modifier | 0.979 | 47 |
| recall_by_edit:modal_swap | 0.857 | 84 |
| recall_by_edit:trailing_clause | 0.938 | 176 |
| false_positive_rate:easy_negative | 0.000 | 500 |
| false_positive_rate:hard_negative | 0.372 | 500 |

Limits: positives are simple rule edits, so recall says nothing about free paraphrase; hard negatives are constructed by swapping the last two words, so they may be easier or harder than real near-misses; no human labels were used.
