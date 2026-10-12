# part_a_active: the models the requirement agent loads

`agents/requirement_agent/agent.py` reads only the files in this folder (`MODELS_DIR`). Scores are on the frozen test split, macro-F1 with 95 % bootstrap CIs, copied from `../MODEL_MANIFEST.md`.

| task | algorithm | filename | frozen-test macro-F1 [95 % CI] |
|---|---|---|---|
| FR vs NFR | MiniLM embeddings + logistic regression | `fr_nfr_fr_nfr_emb_lr.joblib` | 0.828 [0.802, 0.852] (n=935) |
| security flag | keyword rules | `nfr_subtype_security_binary_rules.joblib` | 0.721 [0.670, 0.767] (n=1285) |
| ambiguity (ok / defect) | TF-IDF + logistic regression | `ambiguity_ambiguity_tfidf_lr.joblib` | 0.685 [0.649, 0.722] (n=652) |
| weak words | QuRE weak-word rule | `ambiguity_ambiguity_qure_weak_word_rule.joblib` | 0.525 [0.486, 0.561] (n=652, as a defect detector) |
| near-duplicate grouping | MiniLM cosine threshold 0.955 + DBSCAN | `duplicates_config.json` | F1 0.812 [0.784, 0.837] on held-out seeded pairs |

**Duplicates:** the F1 is measured on rule-made *seeded* pairs only, not on human-labelled duplicates. 0.853 is the best F1 on the development pairs where the threshold was chosen; 0.812 is on the held-out pairs (with hard negatives). Recall on real paraphrases is unknown.

`embedding_cache/` holds cached MiniLM sentence vectors (git-ignored, rewritten when new texts are embedded). It is not a classifier.

The other 21 models are baselines kept for comparison in `../part_a_experiments/`. `python -m evaluation.run_baselines` saves there, so after a retrain copy the file you want into this folder by hand.
