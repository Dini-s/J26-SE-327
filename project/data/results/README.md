# data/results: what each file is

| File | Content | Produced by |
|---|---|---|
| `summary.json` | C4 evaluation: stage-1 recall, precision/recall/F1, non-functional requirements | measured earlier in this repository |
| `decay_injection_*.json` | decay-injection test (known-good links, mutated code) | `python -m agents.traceability_agent.decay_injection` |
| `colab_results.json` | **copied by hand** from the Colab output: fine-tuned CodeBERT and MiniLM cross-encoders, untrained MiniLM, bootstrap intervals, training logs | Colab (T4). Not recomputable here without the Colab score files |
| `stage1_embeddings.json` | stage-1 recall of three embedding models on 7 datasets | `scripts/reproduce_reranker_analysis.ipynb` with `C4_FULL=1` |
| `petclinic_verdicts.json` | Llama 3.1 8B verdicts (258 pairs) collected from earlier runs | exported from `data/runs/*/events.jsonl` |
| `query_expansion_itrust.json` | the LLM's answers for the query-expansion experiment (20 iTrust requirements) | `python -m agents.traceability_agent.reranker.query_expansion generate` |
| `reranker.json` | short summary of the reranker results | written by hand |

To make the Colab part exactly reproducible, download `test_scores.jsonl` of both models from Colab (the last cell of
`scripts/train_reranker_colab.ipynb` includes them in `results.zip`; to get the Colab bundle run `python -m agents.traceability_agent.reranker.data pairs` and `... data bundle`) and put them in `data/reranker/colab_scores/`.

> The code that produced the experiment files above (reranker, learned ranker, old Colab notebooks and scripts) was moved to `J26-SE-327-removed-files/c4-experiments-*/`; the result files stay here. The current CodeBERT work is in three notebooks in `scripts/`: `codebert_training.ipynb` (writes `codebert_training_notebook.json`), `codebert_cross_validation.ipynb` (writes `cross_validation_codebert.json`) and `codebert_stage1_test.ipynb` (writes `stage1_codebert_real_projects.json`). `etour_codebert_stage1.json` and `training_pairs_codebert.json` are earlier results of the scripts these notebooks replaced.
