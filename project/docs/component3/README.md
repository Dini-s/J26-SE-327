# ASPIRE Component 3: Quality & Testing Intelligence

C3 provides requirement-centric QA decision support: it identifies what must be checked, assesses the evidence for each check, separates evidence adequacy from execution confirmation, and explains what evidence must change after a requirement update.

## Implementation availability

This guide describes `feature/quality-testing-intelligence`. The documentation-only update to `main` does not install the implementation. Use a checkout containing the C3 code, scripts, dataset, and frontend for the commands below. Integration of that implementation requires separate review.

C3 is a research prototype. Its outputs support QA review and do not certify product correctness. See [Limitations and research boundaries](LIMITATIONS.md).

## Analysis workflow

1. Read requirements and acceptance criteria.
2. Derive Requirement Validation Units (RVUs), retaining source fragments, constraints, confidence, and review flags.
3. Build an Expected Evidence Profile for each check.
4. Normalize Java/JUnit sources, Maven Surefire results, manual QA records, and performance evidence.
5. Retrieve candidates using keyword, TF-IDF, or semantic retrieval.
6. Assess evidence against the required behavior and conditions.
7. Check qualifying execution independently of adequacy.
8. Aggregate coverage and experimental scores; generate findings and recommended actions.
9. Classify evidence reuse for supplied requirement-change contexts.
10. Publish API results, dashboard views, JSON reports, and C3 USKG data.

Similarity identifies candidates; it does not establish adequacy. Adequate evidence does not establish successful execution. Synthetic or controlled PASS outcomes do not establish observed execution.

## Metrics

| Output | Interpretation |
|---|---|
| RVC | Adequate RVUs / total RVUs × 100 |
| Execution-confirmed coverage | Reported separately, using supported checks as the denominator |
| Validation status | Full requirement validation requires adequate evidence and qualifying successful execution for every check |
| Experimental RVES | Composite of relevance, adequacy, completeness, and execution strength on a 0–1 scale |
| Findings and review flags | Explain mismatches, uncertainty, and required human review |

Baseline RVES = `0.25R + 0.25A + 0.25C + 0.25E`. It is not a probability of correctness. Expert correlation, sensitivity analysis, and ablation remain necessary. Unsupported checks remain explicitly not assessed; they must not be interpreted as passes.

## Dataset and provenance

The documented development snapshot contains 30 requirements, 90 acceptance criteria, and 91 derived RVUs. It combines Spring PetClinic test sources and stored Surefire results with labelled controlled requirements, manual evidence, performance fixtures, and change cases. It is not an entirely observed production dataset or complete industrial SRS.

PetClinic source is pinned to `500158f732419217507c7656904b8e6aa1bcc0d6`. Consult `project/data/component3/manifests/` for dataset, environment, and reproducibility context. Preserve source labels and distinguish stored upstream execution results from tests of the C3 component itself.

## Setup

The recorded backend environment uses Python 3.12.10. Use a Node.js version compatible with the Vite version recorded in `apps/web/package.json` and its lockfile.

From the repository root, on the implementation branch:

```powershell
cd project
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If needed, copy `.env.example` to `.env` without overwriting existing configuration.

| Configuration | Default / meaning |
|---|---|
| C3_DATA_ROOT | `data/component3`; relative to `project/` |
| EMBEDDING_MODEL | `sentence-transformers/all-MiniLM-L6-v2` |
| TOP_K | `5` candidate matches |
| SEMANTIC_THRESHOLD | `0.35` |
| PETCLINIC_COMMIT | Source revision pinned above |

Semantic retrieval loads the embedding model lazily. First use may download model weights and take longer; later runs depend on the local cache. The baseline uses local embeddings and deterministic analysis without requiring a hosted LLM API key.

## Start the application

Terminal 1, from `project/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, from the repository root:

```powershell
cd project/apps/web
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

| Page / service | URL |
|---|---|
| Quality Overview | http://127.0.0.1:5173/quality/overview |
| Requirements | http://127.0.0.1:5173/quality/requirements |
| QA Reports & Analytics | http://127.0.0.1:5173/quality/reports |
| Health | http://127.0.0.1:8000/health |
| API schemas and interactive documentation | http://127.0.0.1:8000/docs |

Vite proxies `/api` and `/health` to port 8000. `VITE_API_BASE_URL` overrides the frontend default `/api/quality`. The quality interface calls bootstrap during initialization; initial preparation can take longer than loading saved artifacts.

## Rebuild and verify

Run from `project/` on the implementation branch:

```powershell
# Processing, normalization, analysis, revalidation, export, evaluation, release checks
.\.venv\Scripts\python.exe -m scripts.run_c3_release

# Component and API tests
.\.venv\Scripts\python.exe -m pytest -c pytest-c3.ini

# Fail when required independent gold labels are incomplete
.\.venv\Scripts\python.exe -m scripts.run_c3_evaluation --strict

# Full pipeline with strict evaluation checks
.\.venv\Scripts\python.exe -m scripts.run_c3_release --strict-evaluation
```

Pipeline commands write generated artifacts under the configured data root. Review those changes before committing.

The saved evaluation snapshot inspected for this guide reports `INCOMPLETE` readiness and missing gold-label sections. Strict evaluation is expected to fail until the required labels are supplied. Passing tests or non-strict release checks does not establish empirical accuracy. Publish evaluation metrics only with independent reference labels and reproducible experiment context.

## Worked demonstration

These controlled examples describe the saved development snapshot; inspect regenerated results before quoting numbers.

| Example | Validation intent | Supplied update |
|---|---|---|
| REQ-C3-F-017: Password Reset Token Validation | Valid-token use, expiry, and expired/consumed-token rejection | Expiry changes from 30 to 20 minutes |
| REQ-C3-NFR-021: Owner Search Response Performance | p95 below 2 seconds, failure rate below 1%, and no unhandled failure; the first two checks specify 100 concurrent users for 10 minutes | p95 tightens from 2 to 1.5 seconds with unchanged workload and duration |

Both saved examples have three checks, two adequate checks, 66.67% RVC, zero execution-confirmed checks, and partial validation. Evidence coverage and execution confirmation therefore tell different stories.

Demo sequence:

1. Overview: show coverage, execution confirmation, and priority findings.
2. Requirements: search an example ID; inspect risk and status.
3. Requirement Details → Summary & Evidence: select checks and inspect evidence, findings, and actions.
4. Requirement Details → Revalidation: compare old/new text and inspect decisions with reasons.
5. Reports: review summaries and requirement-level analysis, then export JSON.

For F-017, unchanged valid-token evidence remains reusable, old expiry evidence is outdated, the boundary check needs updating, and new rejection proof is needed. For NFR-021, failure-rate evidence stays reusable while response-time evidence needs replacement or modification and new proof.

Opening Revalidation shows supplied change cases; it does not edit requirements or run tests.

## Revalidation decisions

| Classification | Action | Meaning |
|---|---|---|
| REUSABLE | KEEP | Validation purpose unchanged |
| MODIFICATION_REQUIRED | UPDATE | Conditions or boundary need revision |
| OUTDATED | REPLACE | Evidence validates the previous constraint |
| NEW_EVIDENCE_REQUIRED | CREATE | Updated purpose lacks an existing artifact |

These decisions guide QA work. They do not automatically repair, rerun, or approve tests.

## API entry points

Paths below are relative to `/api/quality`; consult `/docs` for schemas and the full inventory.

| Method | Path | Purpose |
|---|---|---|
| POST | /bootstrap | Prepare dashboard analysis state |
| POST | /analyze | Run quality analysis |
| GET | /intelligence/overview | Aggregate coverage and findings |
| GET | /intelligence/requirements | Requirement-level results |
| GET | /intelligence/requirements/{requirement_id} | Checks, evidence, findings, change context |
| POST | /revalidation/run | Analyze supplied change cases |
| GET | /revalidation | Read reuse decisions |
| GET | /intelligence/reports | Report summaries |
| GET | /export/summary | Combined JSON export |

Routes under `/api/quality/integration` validate C1 requirement, C2 artifact-reference, and C4 change-context payloads and expose ownership information. Payload validation does not prove live integration.

## Artifact map

Paths are relative to the configured C3 data root.

| Location | Contents |
|---|---|
| raw/requirements, raw/junit, raw/surefire | Requirements, sources, stored execution reports |
| raw/manual_tests, raw/manual_execution, raw/performance | Structured evidence and execution records |
| raw/revalidation | Supplied change cases |
| processed/rvus, processed/evidence_profiles | Checks and evidence expectations |
| processed/normalized_evidence, processed/retrieval | Assets and candidate matches |
| processed/adequacy, processed/validation | Assessments, validation, analytics, history |
| processed/gaps, processed/revalidation | Findings, actions, reuse decisions |
| processed/evaluation, processed/release, processed/uskg | Evaluation, release checks, graph export |
| evaluation/gold_labels.json | Gold input consumed by evaluation service |
| manifests | Dataset and reproducibility context |

Requirement and full-report exports are JSON snapshots. Retain IDs, generation context, and provenance when sharing them.

## Component ownership

C3 owns RVUs, evidence profiles, normalized evidence, adequacy, validation, RVC/RVES, QA findings, recommendations, and evidence-reuse decisions.

C1 owns requirement anchors; C2 owns repository intelligence; C4 owns verified requirement/RVU-to-code trace relationships and decay detection. Candidate evidence matches are not C4-verified code traceability.

## Troubleshooting

- Import errors: run from `project/` with its virtual-environment interpreter.
- Frontend connection error: check `/health`, backend port 8000, and Vite proxy settings.
- Slow preparation: inspect embedding model download access and cache.
- Adequate evidence but partial validation: inspect execution provenance and every check's outcome.
- Strict evaluation fails: complete independent labels; do not describe non-strict success as completed evaluation.
- No trend: one saved analysis is a baseline; multiple comparable snapshots are needed.
