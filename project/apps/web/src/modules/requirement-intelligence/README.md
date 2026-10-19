# Requirement Intelligence in the web app

The first intelligence component of the ASPIRE shell: four pages under **`/requirement`**. The sidebar item "Requirement Intelligence" expands like "Repository Intelligence" (children declared in `src/data/navigation.js`); the shell mounts the whole module with one route, `requirement/*` in `src/routes/AppRoutes.jsx`. Those two are the only shell files the module touches.

| Page | Route | What it is for |
|---|---|---|
| Overview | `/requirement` | key numbers, decision progress, documents and last analysis, hand-off (export, publish to the knowledge graph); one call to `GET /api/projects/{pid}/overview` |
| Sources & Findings | `/requirement/sources` | tab **Sources**: add documents (type SRS / BRD / Other, Jira is listed as coming soon), Run analysis, Clear all; tab **Findings**: Ambiguities / Duplicates / Conflicts / Risk across the whole document, each item links to the Review Queue (`?tab=findings&view=...`) |
| Review Queue | `/requirement/review` | filters (status with counts, risk, type, search; pending first), list and detail (original text, issues, follow-up questions, task draft) and the **decision card** (`?uid=...` selects a requirement) |
| Task Drafts | `/requirement/drafts` | draft policy, progress panel, Pause / Resume / Generate all remaining, drafts by requirement, Regenerate, Generate draft |

Every page has the same header (`RequirementIntelligencePage.tsx`): the page title, a searchable **project dropdown** (switch, New project, Rename, Archive, Restore; the choice is remembered in `localStorage`, guarded with try/catch) and an **AI engine** pill that opens **Processing details**: the On device | Cloud switch, the cloud settings and the technical facts (model, host, mode). Those facts, and the model name, are shown nowhere else.

Code layout: `pages/` (the four pages), `components/` (dialogs, decision card, draft card, progress, project switcher, processing details...), `api/` (typed client, TanStack Query hooks, types), `context/` (project choice, running analysis, draft policy; toasts), `lib/`, `copy.ts`, `c1.css` (a few classes built from the shell's tokens), `test/`.

**All visible text is in `copy.ts`**, in neutral product language. A test (`test/wording.test.tsx`) renders every page in its states and fails on internal names (component numbers, model and server product names, "detector", "RVU", "the API", the graph database). Service-provided texts that name internal systems are mapped by error code and never shown (`lib/handoff.ts`).

## Run
1. Start the service (from the repository root): `powershell -ExecutionPolicy Bypass -File scripts\run_c1_live.ps1` (`-Port <n>` for another port).
2. Start the web app: `powershell -ExecutionPolicy Bypass -File scripts\run_c1_frontend.ps1` (or `npm install` and `npm run dev` in `project/apps/web`), open http://localhost:5173/requirement .
- The service address comes from `VITE_C1_API_BASE` (default `http://127.0.0.1:8000`, see `.env.example` in `project/apps/web`). It allows the origins `http://localhost:5173` and `http://127.0.0.1:5173`; for another origin set `C1_CORS_ORIGINS` for the service.
- Projects are managed in the module header (create, rename, archive). A project is published under its own immutable key; the page never sends a project id with a publish.

## Commands (in `project/apps/web`)
| Command | What it does |
|---|---|
| `npm run dev` / `npm run build` | the shell's own commands |
| `npm run typecheck` | `tsc --noEmit` for `src/modules`, `e2e` and the Playwright config |
| `npm run lint` | ESLint (the TypeScript module is clean; the JSX files of the shell have their own older findings) |
| `npm test` | Vitest + React Testing Library, fetch is mocked, no backend needed; the contract test reads `docs/c1_openapi.json` |
| `npm run e2e` | Playwright in the installed Chrome against the dev server: 4 tests with the service answered by the test (no backend, no model server) and 1 opt-in live test (`$env:C1_E2E_LIVE = "1"`, needs `scripts\run_c1_live.ps1` and the writing model; it writes a screenshot to `project/outputs/c1_live_check/`) |

## Decisions
A requirement has **one current decision** (`PUT` / `GET` / `DELETE /api/requirements/{rid}/decision`). Before a decision the card offers Accept, Edit manually and Reject with an optional note. After it, the card is a status card (decision, date, note, clarified text) with only **Change decision** and **Remove decision** (asks first; the requirement goes back to pending). There is no history: the module does not read the deprecated `history` / `decision_history` fields.

An edit must really change the text; to keep the text as it is, accept it (the editor offers this). Accepting a requirement the AI asked about shows a one-line "Accept anyway?" question that never blocks. After an edit, press **Regenerate** on the task draft: it is written from the clarified text and labelled "Generated from your clarified text".

## Task drafts: which are written, in what order, and how to follow them
Writing a draft takes about 15 to 30 seconds per requirement on a laptop GPU, so a large document is not generated in full by default. The selector on the Task Drafts page sets the policy of the next analysis (remembered in the browser):

| Choice | What happens |
|---|---|
| Smart: important requirements first (default) | drafts are queued for **P1** only; the others show "Not written yet. Click Generate draft" |
| All requirements (slow) | everything is queued, ordered P1, P2, P3 |
| None: I will choose | the analysis runs, nothing is queued |

**P1** = ambiguity `defect`, security flag, a rule-based vague term, or NFR. **P2** = other requirements that are not duplicate secondaries. **P3** = secondary members of a duplicate group. (The classes decide order and what "smart" queues; they are not a quality judgement.) A reply that is already cached is shown at once.

The progress panel shows the real queue: the counts line, a segmented bar (done, needs clarification, failed, waiting) with a legend, and a rounded percentage with "H of N handled". **Handled** = done + needs clarification + failed (+ manual review). The line under the bar: "Calculating…" while no draft has finished; "Rough estimate: ~N min left" with 1 or 2 finished drafts (computed in the browser from the throughput it has watched since it saw the queue running); "About N min left" once the service has its estimate (3 or more finished drafts, measured on the active target). If drafts are in progress but none has finished for more than 3 minutes, a calm line suggests waiting, pausing or retrying a failed draft; it never switches the engine. **Pause** stops taking new drafts (the one being written finishes), **Resume** continues, **Generate all remaining** queues every requirement without a draft. The queue and the pause flag are saved by the service.

A draft says where it was written: "Generated by AI · on device" or "· cloud". **Speed.** See `project\models\component1\part_b\README.md` for the measured effect of `num_gpu`/`num_ctx` and `OLLAMA_KEEP_ALIVE`; tuned settings can change the wording slightly.

## Processing target: On device or Cloud
In **Processing details** (`GET/PUT /api/engine`, "Processing target" in `docs/c1_api_contract.md`):

| Control | Meaning |
|---|---|
| **On device** | the service's own writing model, one draft at a time (default) |
| **Cloud** | a remote OpenAI-compatible server (for example the Colab notebook in `notebooks/`), several drafts in parallel. It stays disabled and reads **Set up cloud…** until the address is saved, consent is given and **Test connection** succeeded |
| gear icon | the cloud settings: Cloud URL (https), API key (optional, write-only: afterwards it only says "saved"), model name, parallel requests 1 to 8 (default 4), the consent box, **Test connection** and **Save** |
| status | **Ready**, **Not set up** or **Unreachable** for the active target |

**Test connection** saves the form first and then tests the saved settings. While Cloud is the active target the address, key and model are locked (switch to On device to change them). The browser only ever knows the host name, never the address.

**If the cloud stops answering**, the service pauses the drafts after 3 failed requests and every page shows a **Cloud unreachable** banner with **Retry** (resume on the cloud) and **Switch to device**. Nothing is switched automatically. The 409 answers of the engine endpoints are shown as plain sentences.

Colab and rented-GPU steps and a speed measurement are in `notebooks/README.md`. Keep `LLM_TIMEOUT` at 600: the first request through a tunnel can be slow while the model loads.

## Hand-off
The Overview has **Export** (CSV or JSON) and **Publish to knowledge graph** (`POST /api/projects/{pid}/publish/neo4j`, no body). The status line reads: not set up (the button is disabled and says why), not published yet, published at ..., out of date, or unreachable. Rules and schema: `docs/c1_neo4j_contract.md`.

## Notes
- Every number on the pages comes from the service. The tool does not write a "suggested revision": only the AI draft (story, task, criteria, follow-up questions) and your own edit exist.
- Model confidence is the classifier's probability for its own label, not a verified accuracy. Risk levels come from an unvalidated heuristic; conflicts are rule-based candidates that need a human decision.
- The review list loads up to 500 requirements at once and filters by decision status in the browser (the service has no status filter yet).
