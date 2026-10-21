# Software knowledge project: Component 4 (Traceability Intelligence)

Component 4 (C4) links each requirement to the code that implements it, has an LLM check every link, keeps re-checking
the links when requirements or code change, and reports which requirements are weak, orphaned or broken.
The other components (C1 requirements, C2 code, C3 quality and testing) share one Neo4j graph; C4 writes only its own
`VERIFIED_TRACE` edges, `DecayFlag` nodes and `HAS_DECAY` edges.

```
requirement --(stage 1: TF-IDF + MiniLM shortlist)--> candidate files --(LLM check, evidence prompt)--> VERIFIED_TRACE
      ^                                                                                                    |
      |<-- re-check when text changes (hash) <-- DecayFlag kept as history <-- Redis event trace_decayed -> C3
```

## Folders

| Folder | What is in it |
|---|---|
| `agents/traceability_agent/` | the component: retrieval, verification, decay, completeness, reports, evaluation; its own [README](agents/traceability_agent/README.md) explains every command |
| `shared/` | graph client with the write-ownership guard, LLM client, embeddings, schemas |
| `apps/api/` | small Python API that the dashboard calls (links, analytics, labelling, exports, jobs) |
| `apps/web/` | React dashboard; the C4 pages are described in its [README](apps/web/README.md) |
| `data/processed/` | the CoEST datasets in one format (iTrust, eTour, LibEST, CM-1, SMOS, eANCI, EBT) plus PetClinic |
| `data/results/` | every measured result as JSON (see the README there) |
| `docs/` | the analysis write-up and the notebook reference output |
| `scripts/` | notebooks (data loading, replay, Colab training, reproduction) and small run scripts |

## Setup (once)

1. Neo4j running, Redis running (only needed for the decay message to C3), an LLM server reachable (Ollama, model `gemma2-8k`, chosen by the comparison in `scripts/model_comparison_evidence.ipynb`).
2. From this folder:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env     # fill in NEO4J_*, LLM_*; never commit .env
   python -m agents.traceability_agent setup
   ```
3. Save the embedding model once with `scripts/download_model.ipynb`.

## Run

```bash
python -m apps.api.server                    # API on port 8000
cd apps/web && npm ci && npm run dev         # dashboard on http://127.0.0.1:5173/traceability
```

Pick the repository in the sidebar. Useful commands (details in the agent README):

```bash
python -m agents.traceability_agent link --project spring-petclinic --only-unlinked   # create links
python -m agents.traceability_agent changed --project spring-petclinic --code-changed <id>   # react to a commit
python -m agents.traceability_agent score  --project spring-petclinic                # completeness, orphans, broken
python -m agents.traceability_agent report --project spring-petclinic --out data/results/trace_report
python -m pytest -q                                                                   # tests
```

## What was measured (honest summary)

* Stage-1 recall is the bottleneck (iTrust top-10 about 42%): the LLM cannot recover a link the shortlist misses.
* Hand check of 40 PetClinic links (labelled by an AI reviewer, not a human): the evidence prompt, now the default, gives 82% precision against 58% for the older prompt, at the cost of missing about a third of the correct links.
* A fine-tuned CodeBERT cross-encoder did not generalise; MiniLM fusion adds a small gain that fine-tuning does not improve; more training data did not help CodeBERT.
* Decay detection (deliberately breaking known links): the LLM alone flagged 76% of 46 edits; with the added meaning-change check (numbers, negations, flags, operators) 96% (interval 86% to 99%), no harmless edit flagged. Only 11 of 30 ground-truth links were usable, and the check was built for these kinds of edits, so the number is favourable.

Full tables, limits and the proposal-versus-built comparison: [docs/c4_reranker_and_stage1_analysis.md](docs/c4_reranker_and_stage1_analysis.md).
