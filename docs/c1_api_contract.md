# Component 1 API contract (Requirement Intelligence)

Base URL `http://127.0.0.1:8000`, JSON everywhere except the CSV export. Start it from `project/`:

```
uvicorn agents.requirement_agent.api.app:app --port 8000
```

Generated schema: `docs/c1_openapi.json` (also served live at `/openapi.json` and `/docs`). CORS allows `http://localhost:5173` and `http://127.0.0.1:5173` (the dev server of the web app `project/apps/web`); more origins, for another port or host, go in `C1_CORS_ORIGINS` (comma separated, no `*`).
The UI mockup `docs/ui/c1_mockup.png` was not in the repository when this was written, so the endpoints follow the agreed list, not the picture.

## Conventions

- **Errors** always have the same shape, with an HTTP status that matches:
  `{"error": {"code": "unsupported_file_type", "message": "virus.exe: file type .exe is not allowed. Allowed: .txt, .md, .pdf, .docx."}}`
  Codes: `validation_error` (422), `invalid_parameter` (400), `invalid_decision` (400), `edited_text_required` (400), `edited_text_unchanged` (400), `unsupported_file_type` (400), `empty_file` (400),
  `project_name_taken` (409), `project_key_mismatch` / `project_name_mismatch` (422, publish),
  `file_too_large` (413), `source_not_found` (404), `project_busy` (409), `unreadable_file` (422), `no_sources` (400), `project_not_found` / `requirement_not_found` / `job_not_found` / `not_found` (404),
  `ambiguous_requirement_id` (409), `models_missing` (503), `internal_error` (500).
- **Requirement ids.** `id` is the per-project display id (`REQ-001`, in order of first appearance; kept when a project is analysed again and the text is unchanged).
  `uid` (`p1-REQ-001`) is unique across projects. Every `{rid}` path accepts the `uid`, or the `id` when only one project has it (otherwise 409).
- **Time** values are UTC ISO strings. `page` is `null` for non-PDF sources. `paragraph` is: blank-line separated block (txt, md; whole file), block on the page (pdf),
  or position among paragraphs and table cells (docx), starting at 1.
- **What is a heuristic.** Part A labels come from baseline models (macro-F1 about 0.7-0.8, see `models/component1/MODEL_MANIFEST.md`). `risk` is an unvalidated hand-made
  score (`agents/requirement_agent/api/risk.py`): ambiguous +2, each weak word +1 (max +2), security +1, duplicate +1, conflict candidate +1; 4 or more HIGH, 2-3 MEDIUM, 1 LOW, 0 NONE.
  Conflicts are rule-based candidates (MiniLM cosine >= 0.80 plus a prohibition or different numeric limit) and always say "needs human decision". No accuracy is claimed for them.
  Drafts (story, task, criteria) are model output. Only `decision` is a human choice.
- **Settings (environment).** `C1_GENERATION_BACKEND` = `replay` (default) | `ollama` | `mock`; `C1_REPLAY_FILE` (default `evaluation/component1/generation/ft_outputs.json`);
  `LLM_BASE_URL` (default `http://localhost:11434/v1`), `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT` for Ollama; `C1_WORKSPACE` (default `outputs/c1_workspace`);
  `C1_NEO4J_*` / `NEO4J_*` for publishing to Neo4j (see `c1_neo4j_contract.md`).
  The workspace holds `c1.db`, `uploads/` and the API's own embedding cache; it is git-ignored.

## Live mode (local Ollama model `c1-req`)

Run these from the repository root (from the `project` folder use `..\scripts\...`).

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_c1_live.ps1      # terminal 1: checks Ollama + model, starts the API on :8000 in live mode (-Port <n> for another port)
powershell -ExecutionPolicy Bypass -File scripts\run_c1_frontend.ps1  # terminal 2: the web app (project\apps\web); the C1 page is http://localhost:5173/requirement
.venv\Scripts\python.exe scripts\check_c1_live.py                    # terminal 3: end-to-end check of the running API (own project, cleans up)
```
The backend mode is fixed when the API starts: change it by restarting the API. The UI's engine card always shows the mode and model the API reports.

## Processing target: device or cloud (switchable while the API runs)

Drafts are generated on one of two **targets**, chosen at runtime with `PUT /api/engine` (no restart):

| target | what it is | in flight at once |
|---|---|---|
| `device` (default) | the API's own Ollama model (`LLM_BASE_URL`, `LLM_MODEL`; `c1-req`) | 1 |
| `cloud` | any remote OpenAI-compatible server (for example Ollama on a rented GPU or a notebook) | `cloud_concurrency`, 1 to 8 (default 4) |

No speed-up is promised: the number of items in flight is the only difference this API controls. The cloud target is **disabled** when the API runs with `C1_GENERATION_BACKEND` = `replay` or `mock`.

**How it works.** A dispatcher thread takes the next item from the priority queue only while the ACTIVE target has a free slot, resolves the target for that item at that moment, and hands it to a pool of 8 worker threads. So priority order (forced regenerate, P1, P2, P3), Pause/Resume (stop taking NEW items, the ones in flight finish), the cache lookup and the 3-attempt rule for invalid model output all work the same on both targets, and a switch takes effect for the next item. One cache key is never generated by two workers at once: duplicates wait and take the first reply from the cache. The sqlite database runs in WAL mode for the concurrent writers.

**Cache and provenance.** The cache key is text + backend kind + model name, **not** the target, so a draft made on one target is reused on the other and switching does not regenerate. Every draft says where it was made: `generated_on` (`device` | `cloud`), `endpoint_host` (host name of the cloud server only, `null` for the device), `backend` and `model`. A cached draft keeps the place it was originally made. Greedy wording can differ slightly across hardware and quantisation, so two targets may word the same requirement a little differently; compare numbers only between runs made on the same target.

**Failures.** A cloud connection error, timeout or HTTP 5xx marks that item `failed` with `AI engine unavailable: Cloud unreachable (timeout | connection error | HTTP 503)`; an HTTP 4xx gives `... Cloud rejected the request (HTTP 401); check the key and the model`. There is no retry loop (only invalid model output is retried, 3 attempts) and **no automatic fallback to the device**. After 3 cloud connection failures in a row the queue pauses itself: `task_drafts.paused` is true and `task_drafts.paused_reason` is `"cloud_unreachable"`. The user resumes explicitly (`POST .../generation/resume`) or switches target (which also ends this automatic pause). A cloud redirect to another host is never followed (the key is not sent there).

**Secrets.** `cloud_api_key` is write-only. The address and key are stored in the workspace database (git-ignored); no response, log line or error message contains the key or the full address, only the host name.

### GET /api/engine
```json
{"target": "device", "cloud_available": true, "cloud_disabled_reason": null,
 "device": {"backend": "ollama", "model": "c1-req", "reachable": true, "concurrency": 1},
 "cloud": {"configured": true, "host": "gpu.example.com", "model": "c1-req", "concurrency": 4, "consent": true, "consent_at": "2026-10-16T08:00:00+00:00",
           "reachable": true, "last_tested_at": "2026-10-16T08:01:00+00:00"}}
```
`cloud.reachable` is the result of the last connection test of the CURRENT address, key and model (`null` = not tested since they changed). Neither the key nor the address is ever returned.

### PUT /api/engine
Partial update; send only what changes: `target` (`device` | `cloud`), `cloud_url`, `cloud_api_key` (`""` removes it), `cloud_model` (default `c1-req`), `cloud_concurrency` (1 to 8), `cloud_consent` (boolean; the time is stored). Returns the same object as GET.
`cloud_url` must be `https://host[:port][/path]` without user name, password, query or fragment (400 `invalid_cloud_url`; the message never repeats the address); `/v1` is appended when missing and a trailing slash is removed. Plain `http://` is accepted only if the API was started with `C1_ALLOW_INSECURE_CLOUD=1` (for a local test server).
Switching `target` to `cloud` needs all of: not in replay/mock mode (409 `cloud_disabled`), an address (409 `cloud_not_configured`), consent (409 `cloud_consent_required`) and a successful test of the current address, key and model (409 `cloud_not_tested`); changing the connection settings invalidates the test. While the cloud target is active the address, key and model cannot be changed (409 `engine_in_use`; `cloud_concurrency` can). Withdrawing consent while on the cloud switches back to the device. Switching to `device` is always possible.

### POST /api/engine/test
Body `{"target": "device" | "cloud"}`. The cloud test is `GET {base}/models` with a 10 s timeout and checks that the configured model id is served. Response `{"ok": true, "detail": "Connected; model 'c1-req' is served.", "latency_ms": 212}`. A failure is a normal answer with `ok: false` and a sanitised `detail` ("The server answered HTTP 401. Check the API key.", "Could not connect to the server.", "The server did not answer within 10 seconds.", "The server does not serve the model 'x'.", ...); it never contains the address or the key. A cloud test is refused with 409 when the cloud is disabled or has no address.

## Generation states

`not_requested`, `queued`, `running`, `done` (valid `ok` draft), `needs_clarification` (valid reply with questions), `manual_review` (three invalid replies; `raw_output` keeps the last one),
`failed` (no reply: the model server is unreachable, or `"not in replay file"` - nothing is invented; an unreachable server gives a message starting with `AI engine unavailable`, which the UI shows with a Retry button). A dispatcher and a pool of 8 worker threads run the queue (see "Processing target"). Results are cached by sha256(requirement text + backend kind + model).

## Endpoints

### GET /api/health
```json
{"status": "ok", "part_a_loaded": true, "generation_backend": "replay", "generation_reachable": true, "model": "replay", "generation_target": "device"}
```
`status` is `degraded` when the Part A models are missing. `generation_reachable` is false for an unreachable Ollama, an Ollama that does not serve the configured `LLM_MODEL`, or a missing replay file. `generation_target` is the active target (`device` | `cloud`); `model` and `generation_reachable` describe that target (for the cloud: the model id and the result of the last connection test, no request is made per call). The call never fails because of the backend.

### GET /api/projects, POST /api/projects, PATCH /api/projects/{pid}, POST /api/projects/{pid}/archive, POST /api/projects/{pid}/unarchive
Projects are never deleted, only archived (soft). Every project has a **`project_key`**: a slug (letters, digits, hyphens) that is unique, **immutable**, and is the project id used when publishing to Neo4j.
The project "Core Banking Platform" (id 1) is created on first start with the key `demo-project`; older workspaces get keys on start (project 1 `demo-project`, others a slug of their name).
```json
{"id": 2, "project_key": "second-project", "name": "Second project", "archived": false, "created_at": "2026-10-13T06:46:50+00:00", "sources": 0, "requirements": 0,
 "decisions": {"accepted": 0, "edited": 0, "rejected": 0, "pending": 0}, "last_analysis_at": null, "last_published_at": null, "out_of_date": true}
```
- `GET /api/projects` lists the projects that are not archived (`?include_archived=true` lists all). `decisions` counts requirements by status (`pending` = no decision yet); `last_analysis_at` is the end of the last finished analysis; `last_published_at` and `out_of_date` describe the last publish to Neo4j (read from the workspace, no connection is made; `out_of_date` is true when nothing was published yet or the project changed since).
- `POST` body `{"name": "Second project"}`: 2-80 characters after trimming (else 422 `validation_error`), unique among projects that are not archived, ignoring case (else 409 `project_name_taken`). Response 201. The key is made from the name (`second-project`; `-2`, `-3` ... when the slug is taken, also by an archived project).
- `PATCH` body `{"name": "..."}` renames (same rules; the key does not change). `POST .../archive` and `.../unarchive` return the project; unarchiving needs the name to be free among active projects (409 `project_name_taken`). Archiving deletes nothing and does not block other calls.

### GET /api/projects/{pid}/overview
Everything a project dashboard shows, in one call (404 `project_not_found`):
```json
{"project": {"id": 1, "project_key": "demo-project", "name": "Core Banking Platform", "archived": false},
 "counts": {"requirements": 44, "conflicts": 2, "duplicates": 3,
            "ambiguities": {"total": 14, "detected": 12, "asked_by_ai": 2},
            "drafts": {"total": 44, "done": 30, "ready": 30, "needs_clarification": 2, "waiting": 5, "failed": 1, "not_generated": 6, "manual_review": 0}},
 "decisions": {"accepted": 10, "edited": 4, "rejected": 1, "pending": 29, "decided": 15, "percent_decided": 34.1},
 "sources": {"count": 2, "by_type": {"srs": 1, "brd": 1}, "total_size_bytes": 182000, "latest_upload_at": "2026-10-16T07:50:00+00:00"},
 "last_analysis_at": "2026-10-16T07:55:00+00:00",
 "generation": {"state": "running", "target": "device", "in_progress": 5, "paused_reason": null, "eta_seconds": 240},
 "neo4j": {"configured": true, "reachable": false, "project_id": "demo-project", "last_published_at": null, "out_of_date": true, "error": "neo4j_unreachable", "message": "..."}}
```
Planning and upload numbers are added to the same object:
```json
{"current_sprint": {"id": 4, "name": "Sprint 3", "phase_id": 2, "start_date": "2026-10-12", "end_date": "2026-10-23", "goal": "Login", "requirements": 18, "pending": 7, "decided": 11, "percent_decided": 61.1},
 "current_phase": {"id": 2, "name": "Build", "sprints": 3, "requirements": 30, "pending": 12, "decided": 18, "percent_decided": 60.0},
 "by_sprint": [{"sprint_id": 4, "name": "Sprint 3", "phase_id": 2, "is_current": true, "total": 18, "accepted": 8, "edited": 2, "rejected": 1, "pending": 7}],
 "by_phase": [{"phase_id": 2, "name": "Build", "sprints": 3, "total": 30, "accepted": 12, "edited": 4, "rejected": 2, "pending": 12}, {"phase_id": null, "name": null, "sprints": 1, "total": 5, "accepted": 0, "edited": 0, "rejected": 0, "pending": 5}],
 "findings_by_type": {"ambiguity": 12, "conflict": 2, "duplicate": 3, "security": 5},
 "latest_uploads": ["the 5 newest documents, each as in GET /sources"],
 "analysis": {"ready": 2, "total": 3},
 "sync": {"state": "synced", "enabled": true, "last_synced_at": "...", "counts": {"Requirement": 44}, "next_attempt_at": null, "error": null},
 "pipeline": {"collect": {"state": "done", "documents": 3},
              "identify": {"state": "done", "documents": 3, "requirements": 44},
              "analyse": {"state": "active", "analysed": 2, "total": 3, "failed": 0},
              "improve": {"state": "active", "requirements": 44, "decided": 15, "drafts_written": 32, "drafts": {"ready": 30, "needs_clarification": 2, "failed": 1, "waiting": 5}},
              "share": {"state": "done", "sync_state": "synced", "last_synced_at": "2026-10-20T08:00:00+00:00"}}}
```
`pipeline` shows where the project stands in five stages; every stage has a `state` of `done`, `active`, `waiting` or `failed` and the numbers behind it. `collect`: `done` when there is at least one document. `identify`: `active` while a document is being analysed, `done` once requirements exist, `failed` when an analysis failed and nothing was found, otherwise `waiting`. `analyse`: `active` while a document is being analysed, `failed` when a document's analysis failed, `done` when every document is analysed, otherwise `waiting`. `improve` (decisions and task drafts): `active` while drafts are queued or running or some work is done, `attention` (amber, “Needs attention”) when some drafts failed, none is waiting and at least one draft was written (the failed ones can be retried, see `drafts/retry-failed`), `failed` only when drafts failed and none was written, `done` when every requirement is decided and no draft is waiting or failed, otherwise `waiting`; only `improve` can be `attention`; `drafts_written` = `ready` + `needs_clarification`. `share` follows `sync.state`: `synced` is `done`, `syncing` is `active`, `unreachable` is `failed`, and `pending`, `retrying` and `not_configured` are `waiting` (`done` needs at least one requirement). `counts.drafts.ready` is the same number as `counts.drafts.done`.
"Needs review" is `pending` (no decision yet). `current_phase` is null when the current sprint is in no phase; `by_phase` ends with the sprints that are in no phase (`phase_id: null`) when there are any. Counts use the effective sprint of each requirement. `analysis.ready` = documents that are analysed. `findings_by_type`: `conflict` and `duplicate` count pairs.

`ambiguities.detected` is what the ambiguity check labelled `defect` (the same number as `summary.ambiguities.count`); `asked_by_ai` is the requirements the check passed but the writing model asked about; `total` is their sum. `drafts.waiting` = queued + running. `generation.state` is `idle`, `running` or `paused`. `percent_decided` is 0-100 with one decimal (0 when there are no requirements). The `neo4j` part is the status of the publish endpoint without host and server details; when the graph is down or not configured the call still answers 200 with `reachable: false` and the reason in `error`/`message`.

### POST /api/projects/{pid}/sources
`multipart/form-data`, field `files` repeated, optional field `source_type` = `srs` (default) | `brd` | `other` (applies to all files of the request; anything else is 400 `invalid_parameter`), optional `sprint_id` and `phase_id` (the sprint the documents start in; `phase_id` alone means the first sprint of that phase, a phase without sprint is 422; default: the project's current sprint). Uploading never starts an analysis. Allowed: `.txt .md .pdf .docx`, 20 MB each. File names are reduced to a safe base name; the file is stored under a generated name.
Response 201 (`rejected` lists files that were not accepted; if nothing was accepted the first error is returned instead with its status):
```json
{"accepted": [{"id": 1, "filename": "Sprint_3_SRS.txt", "ext": ".txt", "size_bytes": 255, "pages": null, "warnings": [], "created_at": "2026-10-13T06:46:50+00:00",
               "uploaded_at": "2026-10-13T06:46:50+00:00", "source_type": "srs", "default_sprint_id": 4, "analysis_state": "not_analyzed", "analyzed_at": null,
               "requirements": 0, "ambiguities": 0, "drafts": {"ready": 0, "needs_clarification": 0, "failed": 0}, "sprints": []}],
 "rejected": [], "sprint_detected": true,
 "detected": [{"filename": "Sprint_3_SRS.txt", "sprint_id": 4, "name": "Sprint 3", "confirmed": false}]}
```
**Sprint detection.** When no `sprint_id`/`phase_id` was sent and the file name or the first 2000 characters name "Sprint N" or "Iteration N", that sprint is used: an existing sprint of that name (case-insensitive), otherwise a new one proposed with `origin: "detected"`, `confirmed: false` (confirm it with `PATCH /sprints/{id}` `{"confirmed": true}`). `sprint_detected` is false when nothing was found and the chosen or current sprint was used.
### GET /api/projects/{pid}/sources
List of source objects, each with its stats: `source_type`, `pages`, `size_bytes`, `uploaded_at`, `default_sprint_id`, `analysis_state` (`not_analyzed` \| `analyzing` \| `analyzed` \| `failed`), `analyzed_at`, `requirements`, `ambiguities` (what the ambiguity check labelled `defect`), `drafts` `{ready, needs_clarification, failed}` and `sprints` `[{sprint_id, count}]` (where its requirements are, by effective sprint).

### DELETE /api/projects/{pid}/sources/{source_id}
Removes one uploaded source and everything that came from it. Response **204** with no body.
Cascade (one transaction): the stored file (only if it is inside `outputs/c1_workspace/uploads/`; a path outside that folder is never touched), the source row, every requirement
extracted from that source, and for those requirements their draft (generation) results, decisions (and their audit rows), and candidate conflicts. The other sources keep their
requirements, ids and decisions. Links from the remaining requirements to the deleted ones (duplicate and conflict partners and the findings that mention them) are removed and their
risk level is recomputed from what is left. The shared generation cache (text + backend + model) is kept; it holds no project data.
Errors: `project_not_found` / `source_not_found` (404, also when the source belongs to another project), `project_busy` (409): an analysis (Part A) or draft generation is
still running for the project, nothing is deleted; wait until `GET /api/jobs/{job_id}` shows stage `share` and try again.

### DELETE /api/projects/{pid}/sources
Removes all sources of the project and all derived results (requirements, findings, drafts, decisions, conflicts, jobs). Response 204; also 204 when there was nothing to delete.
Same safety and `project_busy` (409) rule. Other projects are not affected. Uploading and analysing again afterwards starts the ids again at `REQ-001`.

### POST /api/projects/{pid}/analyze
Runs Part A now (segment, classify, ambiguity, security, duplicates, candidate conflicts, risk) and then queues Part B drafts according to the **generation policy**, the optional query parameter `policy` (default `smart`; anything else is `invalid_parameter`, 400). Response 202 with the job (which reports the `policy` it ran with):

| policy | what is queued automatically |
|---|---|
| `smart` | only priority class P1 |
| `all` | everything, ordered P1, then P2, then P3 |
| `manual` | nothing |

Priority classes (`api/priority.py`, no model involved): **P1** = ambiguity label `defect`, or security flag, or a rule-based vague term (`vague_terms`), or NFR; **P2** = every other requirement that is not a secondary duplicate; **P3** = a secondary member of a duplicate group (all members after the first in document order). The P1 reasons come first, so a duplicate secondary that is also an NFR is P1. A requirement that is not queued has no generation row and is reported as `not_requested` ("not generated yet"). A reply that is already in the cache (text + backend + model) is shown at once whatever the policy and never runs again.
```json
{"job_id": "b7719990bb6e", "project_id": 1, "stage": "improve", "part_a_done": true,
 "generation": {"total": 6, "done": 0, "failed": 3, "queued": 3, "running": 0}, "requirements": 6, "error": null, "policy": "smart"}
```
**No re-analysis.** The run analyses only documents whose `analysis_state` is `not_analyzed` or `failed` (or whose content hash changed since they were analysed). Analysed documents are skipped completely: their requirements, results, decisions and drafts are not touched, and no draft is queued for them (drafts are queued for the requirements that are new in this run, by the chosen policy). The one project-wide step is the comparison between requirements (duplicates and candidate conflicts, from cached embeddings), because a new document can repeat or contradict an old one; the detectors run on the new documents only. With nothing to do the call still answers 202 with a finished job. Planning changes (sprints, phases, assignment) never trigger an analysis. A document is `analyzing` while it runs and `failed` if the run stopped; the next run tries it again. Error `no_sources` if nothing was uploaded, 409 `analysis_running` if one is already running.

### POST /api/projects/{pid}/sources/{source_id}/reanalyze
Analyses one document again (optional `policy` as for analyze). Requirements whose normalized text is unchanged keep their id, decision and draft; a requirement that changed or disappeared leaves its decision in the internal audit trail (reason `reanalysis_changed` / `reanalysis_removed`) and its draft is dropped; new and changed requirements get drafts by the policy. 202:
```json
{"source_id": 1, "kept": 40, "changed": 2, "removed": 1, "added": 3, "queued": 5, "job": {"job_id": "abc123", "stage": "improve", "...": "as GET /api/jobs/{id}"}}
```
`changed` = a requirement at the same place (page and paragraph) now has other text; `added` and `removed` are the rest. Errors: 404 `source_not_found`, 409 `project_busy` (an analysis or draft run is still going).

### GET /api/jobs/{job_id}
Same object. `stage` is `collect`, `identify`, `analyse` while Part A runs, `improve` while generation is queued or running (and the queue is not paused), `share` when everything has finished.
`generation.done` counts finished drafts of any kind (done, needs_clarification, manual_review); `failed` counts failed ones; `queued` includes running.

### GET /api/projects/{pid}/summary
Numbers for the cards (real output for a project with six requirements):
```json
{"requirements": 6, "ambiguities": {"count": 1, "high_risk": 0, "asked_by_ai": 0}, "conflicts": 0, "duplicates": 1, "duplicate_groups": 1, "security": 2,
 "risk_counts": {"HIGH": 0, "MEDIUM": 3, "LOW": 0, "NONE": 3}, "task_drafts": {"generated": 2, "total": 6, "needs_clarification": 1, "manual_review": 0, "failed": 0, "not_generated": 2, "in_progress": 1, "queued": 1, "running": 0, "paused": false, "eta_seconds": null, "latency_samples": 2}, "open_findings": 6, "decided": 0}
```
`ambiguities.count` = requirements with ambiguity label `defect`; `high_risk` = those of them with risk HIGH. `conflicts` = candidate conflict pairs; `duplicates` = duplicate pairs.
`task_drafts.generated` = requirements with state `done` (a valid draft exists). The other draft numbers are counted apart: `needs_clarification` (the model asked questions), `manual_review`, `failed`, `not_generated` (nothing requested yet), `in_progress` (= `queued` + `running`). `paused` is true while the queue takes no new item. `paused_reason` is `"cloud_unreachable"` when the queue paused itself after 3 cloud connection failures in a row, otherwise `null`. `eta_seconds` = items waiting divided by the wall-clock throughput of the last 10 completions of the active target (n completions between the earliest start and the latest finish, so parallel workers count); only completions after the last target switch are used, so it starts from nothing when the target changes; it is `null` until `latency_samples` reaches 3 and when nothing is waiting (no estimate is invented). `open_findings` = findings on requirements that have no decision yet.

### Phases and sprints
A project has phases (optional groups) and sprints (a sprint is in at most one phase). Every project starts with **"Sprint 1"** as its current sprint, and every document has a default sprint. The **effective sprint** of a requirement is its own `sprint_id` (an override) if set, else the default sprint of its document; a document may span several sprints and a sprint may hold several documents. Names are unique per project, ignoring case (409 `phase_name_taken` / `sprint_name_taken`). None of these calls starts an analysis.
| Call | Body / query | Answer |
|---|---|---|
| `GET /api/projects/{pid}/phases` | | `[{id, project_id, name, position, sprints}]` |
| `POST /api/projects/{pid}/phases` | `{name}` | 201 phase |
| `PATCH /api/projects/{pid}/phases/{id}` | `{name?, position?}` | phase |
| `DELETE /api/projects/{pid}/phases/{id}` | | 204; its sprints stay and lose the phase |
| `GET /api/projects/{pid}/sprints` | | `[{id, project_id, phase_id, name, start_date, end_date, goal, origin, confirmed, external_id, position, is_current, requirements, pending, documents}]` |
| `POST /api/projects/{pid}/sprints` | `{name, phase_id?, start_date?, end_date?, goal?, origin?: manual\|detected\|jira, external_id?}` (dates `YYYY-MM-DD`, end not before start) | 201 sprint |
| `PATCH /api/projects/{pid}/sprints/{id}` | only what changes: `{name, phase_id (null leaves the phase), start_date, end_date, goal, position, confirmed}` | sprint |
| `DELETE /api/projects/{pid}/sprints/{id}?reassign_to=ID` | `reassign_to` is required when the sprint holds requirements or documents or is the current one (409 `reassign_required`); the last sprint cannot be deleted (409 `last_sprint`) | `{deleted, reassigned_to, requirements_moved}` |
| `PUT /api/projects/{pid}/current-sprint` | `{sprint_id}` | sprint |
| `PUT /api/projects/{pid}/sources/{source_id}/sprint` | `{sprint_id}` (the document's default sprint) | source |
| `POST /api/projects/{pid}/sources/{source_id}/assign-ranges` | `{ranges: [{from_page, to_page, sprint_id}]}`, later ranges win | `{assigned, requirements, without_page}`: sets the override of requirements whose page is in a range; `without_page` cannot be assigned this way |
| `POST /api/projects/{pid}/requirements/assign` | `{requirement_ids: [uid or display id], sprint_id}`; `sprint_id: null` removes the override | `{assigned, sprint_id}` |
`GET .../requirements` takes `sprint_id` (effective sprint) as a filter, and every requirement row and detail has `sprint_id` (effective).

### GET /api/projects/{pid}/requirements
Query: `risk` (HIGH|MEDIUM|LOW|NONE), `sprint_id`, `type` (all|ambiguity|conflict|duplicate|security), `q` (text, id or file name, case-insensitive), `limit` (1-500, default 50), `offset`. Invalid values give `invalid_parameter`.
```json
{"total": 6, "limit": 50, "offset": 0, "items": [
  {"uid": "p1-REQ-003", "id": "REQ-003", "text": "The system shall be easy to use and respond quickly where appropriate.", "source_file": "sample_srs.txt",
   "page": null, "paragraph": 2, "fr_nfr": "NFR", "risk_level": "MEDIUM", "risk_score": 3,
   "flags": {"ambiguity": true, "conflict": false, "duplicate": false, "security": false}, "generation_state": "failed", "failure_reason": "engine_unavailable", "decision": null,
   "suggestion": {"action": "edit", "reasons": ["The wording is unclear.", "Risk level is medium."]}}]}
```
`suggestion` (also in the requirement detail) is a **suggested decision**, computed on every request by fixed rules (`api/suggest.py`): no model call, never stored, exported or published. `action` is `accept` (no ambiguity, no follow-up questions, risk NONE or LOW, no conflict, not a duplicate), `reject` (the later item of a duplicate pair; the reason names the earlier one) or `edit` (everything else: unclear wording, follow-up questions, conflict, higher risk, the earlier item of a duplicate pair); `reasons` are plain sentences.

### GET /api/requirements/{rid}
Full record (real output; `REQ-005` is in the replay file):
```json
{"uid": "p1-REQ-005", "id": "REQ-005", "project_id": 1,
 "text": "User shall be able to reset all options and user variables to defaults.", "original_text": "User shall be able to reset all options and user variables to defaults.",
 "source": {"file": "gen_sample.txt", "page": null, "paragraph": 2, "position": 2, "clause_label": "3.2"},
 "classification": {"fr_nfr": "FR", "nfr_probability": 0.1216},
 "ambiguity": {"label": "ok", "probability_defect": 0.1282, "weak_words": [], "weak_word_spans": []},
 "vague_terms": [],
 "security": {"is_security": false, "cue_words": []},
 "duplicates": [], "duplicate_group": "", "conflicts": [],
 "risk": {"level": "NONE", "score": 0, "note": "unvalidated heuristic, not a trained model"},
 "findings": [], "explanation": "Classified as FR (probability of NFR 0.12, embeddings + logistic regression baseline). No ambiguity, weak word, security, duplicate or conflict finding from the automatic checks.",
 "generation": {"state": "done", "message": "", "status": "ok",
   "user_story": "As a user, I want to reset all options and user variables to their defaults, so that I can start over.",
   "technical_task": "Add a reset function that sets all options and user variables to their default values.",
   "acceptance_criteria": ["Given a user has changed options and user variables, when the user resets them, then they are set to their defaults.",
                           "Given the reset has completed, when the user views the options and variables, then no custom values remain."],
   "rationale": "Role assumed: user.", "clarification_questions": [], "attempts": 1, "manual_review": false, "raw_output": "", "updated_at": "2026-10-13T06:47:11+00:00",
   "backend": "ollama", "model": "c1-req", "numbers_not_in_source": [], "generated_from": "original",
   "generated_on": "device", "endpoint_host": null},
 "suggestion": {"action": "accept", "reasons": ["Clear wording, no open questions, low risk, no conflict or duplicate."]},
 "decision": null, "decision_history": []}
```
`generation.backend` and `generation.model` say which backend wrote the stored reply (`ollama`, `replay` or `mock`; empty when nothing was generated): a draft is live model output only when `backend` is `ollama`. `generation.generated_on` (`device` | `cloud`) and `generation.endpoint_host` (host name of the cloud server, never the address; `null` for the device) say where it was made.
`ambiguities.count` and `high_risk` in the summary come from Part A only. `ambiguities.asked_by_ai` is a separate number: requirements that Part A did not label `defect` but for which the generation model returned `needs_clarification`.

`vague_terms` is a list of `{term, start, end}` (character offsets into `text`) from a small rule-based word list in `api/vague.py` (quickly, fast, user-friendly, as needed, etc.; case-insensitive, whole words only). It is separate from Part A: it never changes `ambiguity.label`, the probability, `weak_words` or any count, and no accuracy is claimed for it.

`generation.numbers_not_in_source` lists numbers that appear in the model's reply (rationale, story, task, criteria, questions) but not in the text the model was given (the clarified text when `generated_from` is `clarified`), using the strict rule of the SFT validator (`95%` in the source and `5%` in the reply is listed). It is a hint to verify, not a verdict, and is empty when nothing was generated.

`ambiguity.weak_word_spans` gives `{word, start, end}` character offsets into `text` for highlighting. `duplicates` and `conflicts` items are `{id, uid, similarity, text, source_file, page, paragraph}`; a conflict also has `kind` (`prohibition` or `numeric_limit`) and `reason`.
The explanation text is assembled from these values only. For a requirement that is not in the replay file, `generation` is `{"state": "failed", "message": "not in replay file", ...}` with empty draft fields.

### POST /api/projects/{pid}/generate
"Generate all remaining": queues every requirement that has no draft yet (state `not_requested`), best priority class first; cached replies are applied at once and not counted. Response 202 `{"queued": 4}`.

### Jira (read-only): /api/projects/{pid}/integrations/jira
Connect a project to Jira Cloud and import sprints and issues as requirements. Full description, scopes and what was verified: `docs/c1_jira_integration.md`. Tokens never appear in any response.

* `GET .../integrations/jira` -> `{"state": "not_configured" | "not_connected" | "connected" | "expired", "needs_reconnect": false, "site": {"name": "Acme", "url": "https://acme.atlassian.net"} | null, "connected_at": "..." | null, "last_import": {"at": "...", "counts": {...}} | null}`. `expired`: connect again. `needs_reconnect`: true when the connection lacks the board permissions (made earlier): Connect again, nothing imported is lost.
* `POST .../integrations/jira/connect` -> `{"authorize_url": "https://auth.atlassian.com/authorize?..."}` (state: random, single use, 10 minutes, bound to the project). 409 `jira_not_configured`.
* `GET /api/integrations/jira/callback?code=&state=&error=` (the OAuth redirect target, not called by the page): answers 302 to `C1_FRONTEND_URL` with `?jira=connected` or `?jira=error&reason=state_invalid|access_denied|exchange_failed|no_site|not_configured|invalid_request`.
* `DELETE .../integrations/jira` -> 204; deletes the tokens, keeps what was imported.
* `GET .../integrations/jira/projects` -> `[{"key": "ABC", "name": "Alpha"}]`; `GET .../boards?project_key=ABC` -> `[{"id": 7, "name": "ABC board", "type": "scrum"}]`; `GET .../sprints?board_id=7&states=active,future` -> `[{"id": 10, "name": "Sprint 1", "state": "active", "start_date": "2026-10-05", "end_date": "2026-10-16", "goal": null}]` (`[]` for a board without sprints).
* `POST .../integrations/jira/import` `{"project_key": "ABC", "board_id": 7, "sprint_states": ["active", "future"], "issue_types": ["Story", "Task"], "set_current": false, "target_sprint_id": 3 | "match" | null, "policy": "smart", "analyze": true}` (everything but `project_key` is optional; `target_sprint_id`: a sprint of the project = everything goes there, null = the current sprint, `"match"` = each issue to the C1 sprint of its Jira sprint, created once per Jira sprint; unknown id: 404 `sprint_not_found`) ->
  `{"sprints_created": 2, "sprints_updated": 0, "issues_new": 12, "issues_updated": 1, "issues_unchanged": 30, "skipped": 0, "missing": 0, "truncated": false, "queued": 9, "job_id": "abc123", "analysis_error": null, "target_sprint": {"id": 3, "name": "Sprint 1"} | null, "matched": false}`. `target_sprint` is where everything went (null with `"match"`).
  `skipped` = issues without text, `missing` = imported earlier and not returned now (kept and marked, never deleted), `queued` = task drafts queued after the analysis, `analysis_error` = a code when the import worked but the analysis could not run (the issues are stored and can be analysed from Sources).
* Errors (all `{"error": {"code", "message"}}`, fixed texts): 409 `jira_not_configured`, `jira_not_connected`, `jira_expired` (connect again), `import_running`, `project_busy`; 403 `jira_forbidden`, `jira_scope_missing` (Jira refused the permissions of the connection for this request, also a 403 on boards/sprints: the page shows Reconnect); 404 `jira_not_found`; 400 `jira_bad_request`; 502 `jira_unreachable`, `jira_request_failed`. 429 and 5xx from Jira are retried up to four times first.

Imported requirements: the document is `Jira · KEY` (`source_type: "jira"`, `ext: ".jira"`); each requirement has `jira: {"key": "ABC-12", "type": "Story", "status": "In Progress", "url": "https://acme.atlassian.net/browse/ABC-12"}` on its list row and in its detail (`null` for every other requirement), and its `source.clause_label` is the issue key. A file upload cannot say `source_type: "jira"`.

### POST /api/projects/{pid}/drafts/retry-failed
Queues again only the drafts of the project whose state is `failed` (best priority class first); nothing else is touched. Failed replies are never cached, so each one really runs the model again, and the counters of repeated failures start over so the queue does not skip them. Response 202 `{"queued": 7}` (`0` when nothing failed). 409 `generation_running` while any draft of the project is queued or running; 404 `project_not_found`.

`failure_reason` (on `generation` and on each list row, `null` unless the state is `failed`) is a short code, never the message and never a host: `engine_unavailable` (the model server could not be reached or answered with an error), `engine_skipped` (skipped after repeated failures), `cloud_unreachable`, `cloud_rejected` (the cloud server refused the request), `not_in_replay`, `engine_not_ready`, `unexpected`, `unknown`.

### POST /api/projects/{pid}/generation/pause, POST /api/projects/{pid}/generation/resume
Pause stops the single worker from taking NEW items; the item in flight finishes. Resume lets it continue. Response `{"paused": true|false}`. The flag is saved in the database, and so is the queue: after an API restart every queued or running requirement is queued again with its saved priority (the queue stays paused if it was). While paused, waiting items do not block deleting sources (`project_busy` only counts a running item).

### POST /api/requirements/{rid}/generate
"Generate draft" / "Regenerate" for one requirement. A requirement that has no draft yet takes a cached reply if one exists (response state `done` or `needs_clarification`, no model call); otherwise, and for any requirement that already has a draft, it is generated now, ahead of the queue and without using the cache. Response 202 `{"uid": "p1-REQ-001", "generation_state": "queued"}`; poll the requirement or the job.

### PUT, GET, DELETE /api/requirements/{rid}/decision (and POST, deprecated)
A requirement has **one current decision**. `PUT` creates it or replaces the earlier one; `DELETE` takes it back to pending (204, also when it was pending); `GET` returns it, or `decision: "pending"` with null fields. `POST` is a **deprecated alias of `PUT`** (same body, same response, also replaces).
An `edited` decision must carry non-empty text that differs from the original (only spacing counts as unchanged): otherwise `edited_text_required` / `edited_text_unchanged` (400) and nothing is recorded; the client should record an `accepted` decision instead. The **effective text** is the edited text while the decision is `edited`, otherwise the original (which is never changed). Generate / Regenerate use it (`generation.generated_from` is `"clarified"` or `"original"`); Regenerate skips the cache.
The stored draft follows the effective text: saving an `edited` decision with new text replaces the draft at once (a cached reply, else the requirement is queued ahead of everything else for the current target, whatever the policy; `generation.state` is `queued` until it is done); `DELETE`, or a change away from `edited`, goes back to the draft for the original text (cache, else queued in its priority class). A `rejected` requirement is never queued. A change of `note` only, or any change that leaves the effective text as it was, never touches the draft.
Request `{"decision": "edited", "edited_text": "The system shall respond within 2 seconds.", "note": "made measurable"}`; `decision` is `accepted`, `edited` or `rejected`; `edited_text` is required for `edited`.
Response:
```json
{"uid": "p1-REQ-003", "decision": "edited", "edited_text": "The system shall respond within 2 seconds.", "note": "made measurable", "updated_at": "2026-10-13T07:01:02+00:00",
 "history": [{"decision": "edited", "edited_text": "The system shall respond within 2 seconds.", "note": "made measurable", "created_at": "2026-10-13T07:01:02+00:00"}]}
```
`history` (here) and `decision_history` (in the requirement detail) are **deprecated**: they hold only the current decision, or nothing while pending. A decision that is replaced or removed is copied to an internal, append-only `decision_audit` table; no endpoint returns it, exports do not contain it, and it is never published to Neo4j. Workspaces that still have the old `decision_history` table are migrated on start: the newest row per requirement stays its current decision, the older rows move to `decision_audit` (reason `migrated`) and the old table is dropped.
Progress counts (`summary.decided`, `open_findings`, the overview), exports and the Neo4j publish all read this single decision.

### GET /api/projects/{pid}/sync (automatic sync to the graph database)
A background worker keeps the graph database in step with the project (the published documents; see `POST .../publish`). It reads the workspace only (the graph database is not contacted by this call):
```json
{"state": "pending", "enabled": true, "last_synced_at": "2026-10-20T08:00:00+00:00", "counts": {"Requirement": 44}, "next_attempt_at": "2026-10-20T08:05:10+00:00", "error": null}
```
`state`: `synced`, `syncing`, `pending` (changed, waiting for the quiet period), `retrying` (the last attempt failed, `next_attempt_at` says when the next one is), `unreachable` (5 failures in a row, still retried every 5 minutes) or `not_configured` (the graph database is not set up: nothing is tried and no error is raised). `error` is a code without secrets: `neo4j_unreachable`, `neo4j_auth_failed`, `neo4j_publish_failed`, `neo4j_driver_missing`.
Triggers: analysis finished, a decision set or removed, a draft written or replaced, a change of sprint, phase or assignment, a document deleted, the project renamed. The worker waits 10 s after the last change, syncs a project at most once per 30 s, may sync while other documents are still being analysed (only documents whose analysis is finished are sent; an unfinished one follows in the next sync after it finishes), and after a failure tries again after 30 s, 60 s, 120 s, 240 s, then every 300 s. It never blocks a request. It uses the same idempotent, single-flight publish as `POST .../publish/neo4j`, which stays as "sync now" (and updates this state). When the service starts, a project that is out of date is synced. `C1_AUTO_SYNC=0` switches the worker off (`enabled: false`). The same object is `sync` in the overview.

### POST /api/projects/{pid}/publish, POST /api/projects/{pid}/unpublish

Publishing is manual and per document. The body is `{"document_ids": [1, 2], "sprint_id": 3}`; give either or both (a sprint means every document of that sprint: the ones that follow it by default and the ones with a requirement in it); neither is 400 `invalid_parameter`, an unknown sprint is 404 `sprint_not_found`. Only analysed documents can be published; the others are **skipped** and come back with a reason (`not_analyzed`, `analyzing`, `failed`, `no_requirements`, `not_found`, `already_published`; unpublish: `not_published`). The call sets `published` / `published_at` on the documents (also in `SourceOut`), writes an internal audit row, and syncs now. Analysing or importing never publishes. Workspaces from before this existed keep their analysed documents published when the project had already been synced.
```json
{"action": "publish", "changed": [{"document_id": 1, "name": "srs.txt"}],
 "skipped": [{"document_id": 3, "name": "new.txt", "reason": "not_analyzed", "message": "Analyse the document first."}],
 "published_documents": 1, "total_documents": 3, "sync": {"state": "synced", "error": null}}
```
`sync.state` is `synced`, `not_configured` (nothing to sync with; the flag is still set) or `retrying` (the sync failed with `error`; the background sync tries again by itself). The call does not fail because of the graph database. Unpublishing makes the documents inactive for the other components; nothing is deleted.

### GET /api/projects/{pid}/sprints/{sid}/summary

Totals of the sprint and one row per document, counting the requirements that are in this sprint: `{"sprint_id", "name", "is_current", "documents", "published", "requirements", "fr", "nfr", "ready", "needs_clarification", "failed", "not_written", "decided": {"accepted","edited","rejected","pending"}, "rows": [...]}`. A row is `{"document_id", "name", "source": "file"|"jira", "requirements", "fr", "nfr", "unclassified", "ready", "needs_clarification", "failed", "not_written", "decided", "findings": {"ambiguity","conflict","duplicate","security"}, "analysis_state", "publish_state": "not_published"|"published"|"syncing"|"sync_error", "published_at"}`. 404 `sprint_not_found`. The overview's `pipeline.share` now also has `published` and `documents` ("Published X of Y documents") and is `waiting` until a document is published.

### POST /api/projects/{pid}/publish/neo4j ("sync now"), GET /api/projects/{pid}/publish/neo4j
"Sync now". Publish the clarified requirements to the shared Neo4j graph (one-way, idempotent; schema and rules in `c1_neo4j_contract.md`, a proposal pending team agreement).
A project is always published under **its own `project_key` and `name`**. `POST` takes an optional body `{"project_id": "demo-project", "project_name": "Core Banking Platform"}` that may only repeat them: any other `project_id` is refused with 422 `project_key_mismatch`, any other `project_name` with 422 `project_name_mismatch` (nothing is sent), so nothing can be published under a made-up id. Renaming a project changes the published name, never the key. It answers
```json
{"project_id": "demo-project", "published_at": "2026-10-16T08:00:00+00:00", "seconds": 0.42,
 "counts": {"Project": 1, "SourceDocument": 2, "Requirement": 44, "Issue": 61, "TaskDraft": 30, "DUPLICATE_OF": 3, "Sprint": 3, "PLANNED_IN": 44, "INCLUDES_SOURCE": 4},
 "deactivated": {"SourceDocument": 0, "Requirement": 0, "Issue": 0, "TaskDraft": 0, "DUPLICATE_OF": 0, "Sprint": 0, "INCLUDES_SOURCE": 0}, "content_hash": "..."}
```
`counts` are what was sent; `deactivated` counts items newly set to `active = false` because they are no longer in the workspace (nothing is deleted).
`GET` (optional query `project_id`, which must equal the key, else 422) is the status, always 200 once the project is valid:
```json
{"configured": true, "reachable": true, "project_id": "demo-project", "host": "localhost", "database": "neo4j", "server_version": "2026.09.0",
 "last_published_at": "2026-10-16T08:00:00+00:00", "last_counts": {"Requirement": 44}, "out_of_date": false, "error": null, "message": null}
```
`out_of_date` is true when nothing was published yet or when the content hash of everything a publish would send differs from the hash stored at the last successful publish.
`host` is the host name only. When Neo4j cannot be used, `reachable` is false and `error`/`message` say why. Errors of `POST`: 503 `neo4j_unconfigured`, `neo4j_driver_missing`, `neo4j_unreachable`,
`neo4j_auth_failed`, `neo4j_publish_failed` (plain messages; never the password or the address); 409 `publish_in_progress`; 404 `project_not_found`. Other endpoints are not affected.
Settings: `C1_NEO4J_URI` / `C1_NEO4J_USER` / `C1_NEO4J_PASSWORD` / `C1_NEO4J_DATABASE`, then `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` / `NEO4J_DATABASE`, from the environment or the shared `.env` (only these keys).

### GET /api/projects/{pid}/export?format=csv|json
`csv`: one row per requirement, UTF-8 with BOM, `Content-Disposition: attachment`. Columns: `id, uid, source_file, page, paragraph, original_text, final_text, decision, decision_note, type, nfr_probability, risk_level, risk_score, ambiguity_label, ambiguity_probability, weak_words, security_related, duplicate_of, conflict_candidates, generation_state, user_story, technical_task, acceptance_criteria, rationale, clarification_questions`.
`final_text` is the edited text for an `edited` decision, otherwise the original. Text cells that start with `=`, `+`, `-` or `@` get a leading `'` so spreadsheets do not run them.

`json` is the hand-off record for Component 3. `shared/` defines no Component 1 to Component 3 contract yet (all files there are empty), so this is the schema, `schema_version` `c1.clarified_requirements.v1`:
```json
{"schema_version": "c1.clarified_requirements.v1", "generated_at": "...", "project": {"id": 1, "name": "Core Banking Platform"},
 "source_files": ["sample_srs.txt"], "note": "Ambiguity and classification labels, risk levels and candidate conflicts are automatic hints ...",
 "requirements": [{
   "id": "REQ-003", "uid": "p1-REQ-003", "source": {"file": "sample_srs.txt", "page": null, "paragraph": 2},
   "original_text": "...", "final_text": "...",
   "decision": {"status": "edited", "edited_text": "...", "note": "...", "decided_at": "..."},
   "classification": {"type": "NFR", "nfr_probability": 0.9908},
   "quality": {"ambiguity_label": "defect", "ambiguity_probability": 1.0, "weak_words": ["appropriate"], "security_related": false,
               "risk_level": "MEDIUM", "risk_score": 3, "duplicates": ["REQ-002"], "conflict_candidates": [{"id": "REQ-005", "reason": "Candidate conflict, needs human decision: ..."}]},
   "draft": {"status": "ok", "user_story": "...", "technical_task": "...", "acceptance_criteria": ["..."], "rationale": "...", "clarification_questions": [], "manual_review": false}}]}
```
`decision` is `null` until a person decides; `draft` is `null` unless a reply exists (state done, needs_clarification or manual_review).
