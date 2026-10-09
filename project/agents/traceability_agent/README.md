# Traceability Agent (Component 4)

Generates, verifies and continuously re-checks trace links between requirements
and code/design entities in the shared USKG (Neo4j) graph.

**Approach (TraceLLM-style):** embedding similarity shortlists candidates (high
recall), then an LLM prompted as a "software traceability expert" confirms,
scores and explains each one (high precision). Pure embedding or rule-based
matching must trade precision against recall; shortlist-then-verify gets both
at bounded LLM cost.

## Graph contract

| Node / edge | Owner | C4 access |
|---|---|---|
| `Requirement`, `CodeEntity` (`kind`: code/test/design) | C1 / C2 | read only |
| `VERIFIED_TRACE` (Requirement -> CodeEntity): confidence, justification, status, verifiedAt, lastCheckedAt, textHash, linkType | **C4** | read/write |
| `DecayFlag`, `(Requirement)-[:HAS_DECAY]->(DecayFlag)` | **C4** | read/write |

`shared/uskg/client.py` is the only place Cypher lives; its only write statements
touch `VERIFIED_TRACE` and `DecayFlag`. Text property names on C1/C2 nodes are an
assumption (see that file's docstring), as is `CodeEntity.kind`. A relationship
cannot be the endpoint of another relationship in Neo4j, so `HAS_DECAY` hangs off
the requirement and the flag records `codeEntityId`.

## Pipeline

1. **Load** – requirements and code entities from the USKG.
2. **Clean + embed** – code is stripped of imports/licence headers and identifiers are split (`preprocess.py`); long files are cut into 60-word chunks and scored by their best chunk (`retrieval.py`); `shared/embeddings.Embedder` (sentence-transformers, `EMBEDDING_MODEL_NAME`) plus TF-IDF.
3. **Candidates** – `find_candidates()`: TF-IDF and embedding scores fused by z-score (`hybrid`), top-k (10) per requirement, no similarity cutoff (a cutoff only lost recall). On iTrust this shortlists ~42% of true links at top-10 (vs 9% for the first embeddings-only version).
4. **Verify** – `verify_candidates()`: LLM JSON verdict; kept if linked and confidence >= `PASS_THRESHOLD`; malformed replies are skipped; latency is recorded (target <= 5 s).
5. **Write** – `VERIFIED_TRACE` via `MERGE` (idempotent). Pairs that already have an edge are not re-verified.

**Decay** (`decay.py`): polls verified links; if either side's text hash differs from the stored `textHash`, re-verifies. A failed re-check sets `status=decayed`, creates a `DecayFlag` (the edge is never deleted) and publishes a `trace_decayed` JSON event on Redis (`events.py`). A Redis outage is logged but never loses the flag.

**Completeness** (`completeness.py`): per requirement, 0 for orphans (no `verified` link), else `100 * (0.6 * mean confidence + 0.4 * C3 evidence coverage)`; without evidence data, `100 * mean confidence`. The C3 evidence figures are an input (`evidence_coverage` mapping) until C3's schema is agreed.

Tunables are in `config.py`.

## Setup (from the project root)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in NEO4J_*, OPENAI_API_KEY; REDIS_URL for decay events
```

## Commands

```bash
python -m agents.traceability_agent setup                 # create Neo4j indexes (idempotent)
python -m agents.traceability_agent link --top-k 5        # find + verify links, write VERIFIED_TRACE (--dry-run to skip writing)
python -m agents.traceability_agent monitor --once        # decay pass; without --once it polls every --interval seconds
python -m agents.traceability_agent score                 # completeness per requirement + orphans
bash scripts/final_evaluation.sh                          # persona ablation, CM-1 write run, decay-injection (hours on a CPU LLM server)
```

Integration tests run against a real Neo4j when one is reachable (they use `__c4test__` ids and clean up); they skip otherwise. A draft of the report with measured results is in `docs/traceability_report_draft.md`.

## Run

```bash
python -c "from agents.traceability_agent.agent import TraceabilityAgent; print(TraceabilityAgent().run())"
python -c "from agents.traceability_agent.decay import DecayDetector; ..."   # needs uskg, llm, DecayEventPublisher()
```

## Dashboard

```bash
uvicorn apps.api.main:app --port 8000     # then open http://127.0.0.1:8000
```

Live progress, precision/recall, per-pair LLM verdicts, the trace graph and Neo4j status. It reads the event log that `evaluate.py --method full` (or any agent with `run_logger`) writes to `data/runs/<run>/events.jsonl`, and queries Neo4j when `NEO4J_*` in `.env` are valid. FastAPI backend in `apps/api`, single-page frontend in `apps/web/index.html`.

## Self-hosted LLM

Set `LLM_BASE_URL` (any OpenAI-compatible endpoint, e.g. Ollama at `http://host:8080/v1`), `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT` and `LLM_MAX_ARTIFACT_CHARS` in `.env`. On a CPU-only server expect ~1 minute per verification, so evaluate on a sample (`--limit-sources 10 --top-k 5`).

## Tests (all mocked; no network, database or Redis)

```bash
pytest agents/traceability_agent/tests
```

## Evaluation

Prepare a dataset (expects the raw files in `~/Downloads/traceability_datasets/`). **iTrust** (use cases -> Java/JSP code, 399 true links) is the primary requirement-to-code benchmark; CM-1 (requirements -> design) is a second check:

```bash
python scripts/load_dataset.py --dataset itrust   # writes data/processed/itrust/{artifacts,traces,gold}.json
python scripts/load_dataset.py --dataset cm1
```

The examples below use CM-1 paths; swap in `data/processed/itrust/...`. For iTrust, `--limit-sources N` keeps LLM cost down (131 requirements x top-10 = 1,310 calls for the full run).

Score a method against the gold pairs (precision / recall / F1):

```bash
# classic IR baseline, fully offline
python -m agents.traceability_agent.evaluate --gold data/processed/cm1/gold.json --artifacts data/processed/cm1/artifacts.json --method tfidf --sweep
# embeddings-only baseline, then the full pipeline (needs the embedding model; full also needs OPENAI_API_KEY)
python -m agents.traceability_agent.evaluate --gold ... --artifacts ... --method embeddings --sweep
python -m agents.traceability_agent.evaluate --gold ... --artifacts ... --method full
```

Decay-injection harness (mutates known-good targets, measures detection and false decays; needs `OPENAI_API_KEY`):

```bash
python -m agents.traceability_agent.decay_injection --artifacts data/processed/cm1/artifacts.json --links data/processed/cm1/traces.json --sample 10
```

CM-1 pairs requirements with *design* items, not code, so it validates link
recovery but not requirement-to-code behaviour; use iTrust/EasyClinic or
Defects4J for that.
