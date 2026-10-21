# data/training_pairs: requirement / code pairs

These files are the **raw training pairs** for the stage-1 CodeBERT (see `scripts/data_preparation.ipynb`). Every item is a requirement, the code that implements it, and 2 hard negatives (code that looks similar but does something else). **The text was written with language models; it is not real project data.** The real, expert-labelled projects are in `data/processed/`.

| Folder / file | What it is |
|---|---|
| `user_domains/` | 30 domain files (65 items each) prepared by the project owner. *To fill in: which tool(s) produced the text and how the domains were chosen.* |
| `corpus_a/`, `corpus_b/` | JSON batches (`corpus_a/` is reserved and currently empty) |
| `prompts/`, `corpus_c/`, `replies/`, `batches/` | the prompts, batches and replies of the CSV runs (CSV format `requirement_id, requirement_text, code_text, label, kind`) |
| `_cache_*.json` | small caches of earlier runs |

Cleaning: `scripts/prepare_training_pairs.py` (explained cell by cell in `scripts/data_preparation.ipynb`) removes unusable items and writes `data/training_pairs_clean/`. Re-running it reproduces that folder byte for byte.

Limits to state when this data is mentioned: written by LLMs in one style; train and test from the same writers, so scores on it say that a model can learn this kind of data, not that it works on real projects (the cross-validation on the real projects answers that).
