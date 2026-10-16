# Component 1 API contract (Requirement Intelligence)

Base URL `http://127.0.0.1:8000`, JSON everywhere except the CSV export. Start it from `project/`:

```
uvicorn agents.requirement_agent.api.app:app --port 8000
```

Generated schema: `docs/c1_openapi.json` (also served live at `/openapi.json` and `/docs`). CORS allows `http://localhost:5173` and `http://127.0.0.1:5173`.
The UI mockup `docs/ui/c1_mockup.png` was not in the repository when this was written, so the endpoints follow the agreed list, not the picture.

## Conventions

- **Errors** always have the same shape, with an HTTP status that matches:
  `{"error": {"code": "unsupported_file_type", "message": "virus.exe: file type .exe is not allowed. Allowed: .txt, .md, .pdf, .docx."}}`
  Codes: `validation_error` (422), `invalid_parameter` (400), `invalid_decision` (400), `edited_text_required` (400), `edited_text_unchanged` (400), `unsupported_file_type` (400), `empty_file` (400),
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
  `LLM_BASE_URL` (default `http://localhost:11434/v1`), `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT` for Ollama; `C1_WORKSPACE` (default `outputs/c1_workspace`).
  The workspace holds `c1.db`, `uploads/` and the API's own embedding cache; it is git-ignored.

## Live mode (local Ollama model `c1-req`)

Run these from the repository root (from the `project` folder use `..\scripts\...`).

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_c1_live.ps1      # terminal 1: checks Ollama + model, starts the API on :8000 in live mode
powershell -ExecutionPolicy Bypass -File scripts\run_c1_frontend.ps1  # terminal 2: UI on http://127.0.0.1:5173
.venv\Scripts\python.exe scripts\check_c1_live.py                    # terminal 3: end-to-end check of the running API (own project, cleans up)
```
The backend mode is fixed when the API starts: change it by restarting the API. The UI's engine card always shows the mode and model the API reports.

## Generation states

`not_requested`, `queued`, `running`, `done` (valid `ok` draft), `needs_clarification` (valid reply with questions), `manual_review` (three invalid replies; `raw_output` keeps the last one),
`failed` (no reply: the model server is unreachable, or `"not in replay file"` - nothing is invented; an unreachable server gives a message starting with `AI engine unavailable`, which the UI shows with a Retry button). One worker thread runs the queue. Results are cached by sha256(requirement text + backend + model).

## Endpoints

### GET /api/health
```json
{"status": "ok", "part_a_loaded": true, "generation_backend": "replay", "generation_reachable": true, "model": "replay"}
```
`status` is `degraded` when the Part A models are missing. `generation_reachable` is false for an unreachable Ollama, an Ollama that does not serve the configured `LLM_MODEL`, or a missing replay file. The call never fails because of the backend.

### GET /api/projects, POST /api/projects
Request `{"name": "Second project"}` (1-120 characters), response 201
`{"id": 2, "name": "Second project", "created_at": "2026-10-13T06:46:50+00:00", "sources": 0, "requirements": 0}`.
The project "Core Banking Platform" (id 1) is created on first start.

### POST /api/projects/{pid}/sources
`multipart/form-data`, field `files` repeated. Allowed: `.txt .md .pdf .docx`, 20 MB each. File names are reduced to a safe base name; the file is stored under a generated name.
Response 201 (`rejected` lists files that were not accepted; if nothing was accepted the first error is returned instead with its status):
```json
{"accepted": [{"id": 1, "filename": "sample_srs.txt", "ext": ".txt", "size_bytes": 255, "pages": null, "warnings": [], "created_at": "2026-10-13T06:46:50+00:00"}],
 "rejected": []}
```
### GET /api/projects/{pid}/sources
List of the same source objects.

### DELETE /api/projects/{pid}/sources/{source_id}
Removes one uploaded source and everything that came from it. Response **204** with no body.
Cascade (one transaction): the stored file (only if it is inside `outputs/c1_workspace/uploads/`; a path outside that folder is never touched), the source row, every requirement
extracted from that source, and for those requirements their draft (generation) results, decisions with their history, and candidate conflicts. The other sources keep their
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
Analysing again **replaces** the previous derived results of the project, so it never creates duplicates: the requirement count and ids are the same when nothing changed. A requirement keeps its id, decision and draft only when its text and its source (the same uploaded file) are unchanged; the same text in a re-uploaded or second file is a new requirement. Error `no_sources` if nothing was uploaded.

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
`task_drafts.generated` = requirements with state `done` (a valid draft exists). The other draft numbers are counted apart: `needs_clarification` (the model asked questions), `manual_review`, `failed`, `not_generated` (nothing requested yet), `in_progress` (= `queued` + `running`). `paused` is true while the queue takes no new item. `eta_seconds` = mean of the last 10 real reply times of this backend and model x the items waiting; it is `null` until `latency_samples` reaches 3 and when nothing is waiting (no estimate is invented). `open_findings` = findings on requirements that have no decision yet.

### GET /api/projects/{pid}/requirements
Query: `risk` (HIGH|MEDIUM|LOW|NONE), `type` (all|ambiguity|conflict|duplicate|security), `q` (text, id or file name, case-insensitive), `limit` (1-500, default 50), `offset`. Invalid values give `invalid_parameter`.
```json
{"total": 6, "limit": 50, "offset": 0, "items": [
  {"uid": "p1-REQ-003", "id": "REQ-003", "text": "The system shall be easy to use and respond quickly where appropriate.", "source_file": "sample_srs.txt",
   "page": null, "paragraph": 2, "fr_nfr": "NFR", "risk_level": "MEDIUM", "risk_score": 3,
   "flags": {"ambiguity": true, "conflict": false, "duplicate": false, "security": false}, "generation_state": "failed", "decision": null}]}
```

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
 "findings": [], "explanation": "Classified as FR (probability of NFR 0.12, embeddings + logistic regression baseline). No ambiguity, weak word, security, duplicate or conflict finding from the Part A detectors.",
 "generation": {"state": "done", "message": "", "status": "ok",
   "user_story": "As a user, I want to reset all options and user variables to their defaults, so that I can start over.",
   "technical_task": "Add a reset function that sets all options and user variables to their default values.",
   "acceptance_criteria": ["Given a user has changed options and user variables, when the user resets them, then they are set to their defaults.",
                           "Given the reset has completed, when the user views the options and variables, then no custom values remain."],
   "rationale": "Role assumed: user.", "clarification_questions": [], "attempts": 1, "manual_review": false, "raw_output": "", "updated_at": "2026-10-13T06:47:11+00:00",
   "backend": "ollama", "model": "c1-req", "numbers_not_in_source": [], "generated_from": "original"},
 "decision": null, "decision_history": []}
```
`generation.backend` and `generation.model` say which backend wrote the stored reply (`ollama`, `replay` or `mock`; empty when nothing was generated): a draft is live model output only when `backend` is `ollama`.
`ambiguities.count` and `high_risk` in the summary come from Part A only. `ambiguities.asked_by_ai` is a separate number: requirements that Part A did not label `defect` but for which the generation model returned `needs_clarification`.

`vague_terms` is a list of `{term, start, end}` (character offsets into `text`) from a small rule-based word list in `api/vague.py` (quickly, fast, user-friendly, as needed, etc.; case-insensitive, whole words only). It is separate from Part A: it never changes `ambiguity.label`, the probability, `weak_words` or any count, and no accuracy is claimed for it.

`generation.numbers_not_in_source` lists numbers that appear in the model's reply (rationale, story, task, criteria, questions) but not in the text the model was given (the clarified text when `generated_from` is `clarified`), using the strict rule of the SFT validator (`95%` in the source and `5%` in the reply is listed). It is a hint to verify, not a verdict, and is empty when nothing was generated.

`ambiguity.weak_word_spans` gives `{word, start, end}` character offsets into `text` for highlighting. `duplicates` and `conflicts` items are `{id, uid, similarity, text, source_file, page, paragraph}`; a conflict also has `kind` (`prohibition` or `numeric_limit`) and `reason`.
The explanation text is assembled from these values only. For a requirement that is not in the replay file, `generation` is `{"state": "failed", "message": "not in replay file", ...}` with empty draft fields.

### POST /api/projects/{pid}/generate
"Generate all remaining": queues every requirement that has no draft yet (state `not_requested`), best priority class first; cached replies are applied at once and not counted. Response 202 `{"queued": 4}`.

### POST /api/projects/{pid}/generation/pause, POST /api/projects/{pid}/generation/resume
Pause stops the single worker from taking NEW items; the item in flight finishes. Resume lets it continue. Response `{"paused": true|false}`. The flag is saved in the database, and so is the queue: after an API restart every queued or running requirement is queued again with its saved priority (the queue stays paused if it was). While paused, waiting items do not block deleting sources (`project_busy` only counts a running item).

### POST /api/requirements/{rid}/generate
"Generate draft" / "Regenerate" for one requirement. A requirement that has no draft yet takes a cached reply if one exists (response state `done` or `needs_clarification`, no model call); otherwise, and for any requirement that already has a draft, it is generated now, ahead of the queue and without using the cache. Response 202 `{"uid": "p1-REQ-001", "generation_state": "queued"}`; poll the requirement or the job.

### POST /api/requirements/{rid}/decision
An `edited` decision must carry text that differs from the original (only spacing counts as unchanged): otherwise `edited_text_unchanged` (400) and nothing is recorded; the client should record an `accepted` decision instead. When a requirement has an `edited` decision, **Generate / Regenerate uses that clarified text** (`generation.generated_from` is `"clarified"`; `"original"` otherwise). The original text and the decision history are kept.
Request `{"decision": "edited", "edited_text": "The system shall respond within 2 seconds.", "note": "made measurable"}`; `decision` is `accepted`, `edited` or `rejected`; `edited_text` is required for `edited`.
Response (the latest decision plus the history, oldest first):
```json
{"uid": "p1-REQ-003", "decision": "edited", "edited_text": "The system shall respond within 2 seconds.", "note": "made measurable", "updated_at": "2026-10-13T07:01:02+00:00",
 "history": [{"decision": "accepted", "edited_text": null, "note": "ok for now", "created_at": "2026-10-13T07:00:40+00:00"},
             {"decision": "edited", "edited_text": "The system shall respond within 2 seconds.", "note": "made measurable", "created_at": "2026-10-13T07:01:02+00:00"}]}
```
The original text is never changed.

### GET /api/projects/{pid}/export?format=csv|json
`csv`: one row per requirement, UTF-8 with BOM, `Content-Disposition: attachment`. Columns: `id, uid, source_file, page, paragraph, original_text, final_text, decision, decision_note, type, nfr_probability, risk_level, risk_score, ambiguity_label, ambiguity_probability, weak_words, security_related, duplicate_of, conflict_candidates, generation_state, user_story, technical_task, acceptance_criteria, rationale, clarification_questions`.
`final_text` is the edited text for an `edited` decision, otherwise the original. Text cells that start with `=`, `+`, `-` or `@` get a leading `'` so spreadsheets do not run them.

`json` is the hand-off record for Component 3. `shared/` defines no Component 1 to Component 3 contract yet (all files there are empty), so this is the schema, `schema_version` `c1.clarified_requirements.v1`:
```json
{"schema_version": "c1.clarified_requirements.v1", "generated_at": "...", "project": {"id": 1, "name": "Core Banking Platform"},
 "source_files": ["sample_srs.txt"], "note": "Part A labels, risk levels and candidate conflicts are automatic hints ...",
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
