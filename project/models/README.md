# Models

- `component1/part_a_active/`: the 4 models plus the duplicates config that the requirement agent loads, with the embedding cache. See its README.
- `component1/part_a_experiments/`: the other 21 baseline models (`fr_nfr/`, `security_and_subtype/`, `ambiguity/`), written by `python -m evaluation.run_baselines`.
- `component1/MODEL_MANIFEST.md`: every model file with its algorithm and frozen-test score.

The `.joblib` files and the embedding cache are git-ignored (`models/component1/**/*.joblib`, `models/component1/**/embedding_cache/`).
