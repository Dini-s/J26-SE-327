# data/generated_pairs: requirement / code pairs written by language models

These files are the **raw training pairs** for the stage-1 CodeBERT (see `scripts/data_preparation.ipynb`). Every item is a requirement, the code that implements it, and 2 hard negatives (code that looks similar but does something else). **The text was generated with large language models; it is not real project data.** The real, expert-labelled projects are in `data/processed/`.

| Folder / file | What it is |
|---|---|
| `user_domains/` | 30 domain files (65 items each) prepared by the project owner. *To fill in: which tool(s) produced the text and how the domains were chosen.* |
| `deepseek/` | JSON batches produced with DeepSeek |
| `gemini_prompt/`, `gemini/`, `replies/`, `batches/` | the prompts, batches and replies of the Gemini runs (CSV format `requirement_id, requirement_text, code_text, label, kind`) |
| `final/` | output of `scripts/clean_generated_pairs.py` for the Gemini CSVs |
| `_cache_*.json` | small caches of earlier generation runs |

Cleaning: `scripts/prepare_generated_pairs.py` (explained cell by cell in `scripts/data_preparation.ipynb`) removes unusable items and writes `data/generated_pairs_clean/`. Re-running it reproduces that folder byte for byte.

Limits to state when this data is mentioned: written by LLMs in one style; train and test from the same writers, so scores on it say that a model can learn this kind of data, not that it works on real projects (the cross-validation on the real projects answers that).
