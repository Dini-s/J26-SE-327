# Component 1 web UI (Requirement Intelligence)

React + TypeScript + Vite + Tailwind CSS single page that calls the Component 1 API (`docs/c1_api_contract.md`, `docs/c1_openapi.json`). Design reference: `docs/ui/c1_mockup.png`; the values taken from it are in `DESIGN_TOKENS.md`.

## Run it on Windows (PowerShell)

You need Node.js 20 or newer (`node --version`; this was built with 22) and the Python virtual environment of the repository.

Shortcuts for a live model (Ollama `c1-req`): `scripts\run_c1_live.ps1` starts the API in live mode after checking Ollama and the model, `scripts\run_c1_frontend.ps1` starts this UI (installing packages only if `node_modules` is missing), and `scripts\check_c1_live.py` checks the running API end to end. Optional browser smoke test against that live stack: `npm run e2e` (Playwright using the installed Chrome; saves a screenshot to `project/outputs/c1_live_check/`).

Reading aids in the detail view (none of them change Part A): requirements for which the AI model asked for clarification carry an "AI asked for clarification" badge, and the Ambiguities card shows the Part A count with a separate "+N asked by AI" line. Words from a small rule-based list (`project/agents/requirement_agent/api/vague.py`) are underlined as "Vague term (rule-based)"; this list is a hint, not a model, and no accuracy is claimed for it. A draft that contains numbers missing from the requirement text shows "Contains number(s) not in the source: verify".

1. Start the API (terminal 1, from the `project` folder). For a throw-away demo database use a scratch workspace; the default is `outputs/c1_workspace`.
   ```powershell
   cd project
   ..\.venv\Scripts\Activate.ps1
   $env:C1_GENERATION_BACKEND = "replay"
   uvicorn agents.requirement_agent.api.app:app --port 8000
   ```
   `replay` reads stored model outputs from `evaluation/component1/generation/ft_outputs.json`; a requirement whose text is not in that file shows "failed: not in replay file". For a live model use `$env:C1_GENERATION_BACKEND = "ollama"` plus `LLM_MODEL` (and `LLM_BASE_URL` if not the default).
2. Start the UI (terminal 2, from the repository root):
   ```powershell
   cd frontend\c1
   npm install
   npm run dev
   ```
3. Open http://127.0.0.1:5173 . The API address comes from `VITE_API_BASE` (default `http://127.0.0.1:8000`; copy `.env.example` to `.env` to change it). The API only allows the origins `http://localhost:5173` and `http://127.0.0.1:5173`, so keep the dev server on port 5173 (`--strictPort` is set).

## Task drafts: which are written, in what order, and how to follow them

Writing a draft takes about 15 to 30 seconds per requirement on a laptop GPU, so a large document is not generated in full by default. Next to **Run analysis** the selector "Task drafts" sets the policy of that run (it is remembered in the browser):

| Choice | What happens |
|---|---|
| Smart: important requirements first (default) | drafts are queued for **P1** only; the others show "Not generated yet. Click Generate draft" |
| All requirements (slow) | everything is queued, ordered P1, P2, P3 |
| None: I will choose | the analysis runs, nothing is queued |

**P1** = Part A ambiguity `defect`, security flag, a rule-based vague term, or NFR. **P2** = other requirements that are not duplicate secondaries. **P3** = secondary members of a duplicate group. (The classes decide order and what "smart" queues; they are not a quality judgement.) A reply that is already cached is shown at once and never runs again.

The panel under the summary cards shows the real queue: "Drafts X of N done, Y not generated, Z needs clarification, W failed". The time left is the mean of the last 10 real reply times times the drafts waiting, and it is hidden until 3 replies have finished. **Pause** stops taking new drafts (the one being written finishes), **Resume** continues, **Generate all remaining** queues every requirement without a draft. The queue and the pause flag are saved by the API, so a restart picks up where it stopped. The "Task drafts" card counts generated, needs clarification, not generated yet and failed separately; on the Ambiguities card "+N asked by AI" reads "(N so far, drafts pending)" while drafts are still missing.

**Clarification flow.** If the model needs clarification, open "Edit manually", write the clearer text and save: the original text and the history stay. Then press **Regenerate** on the task draft: it is written from your clarified text and labelled "Generated from your clarified text". An edit must really change the text; to keep the text as it is, accept it (the panel offers this) instead. Accepting a requirement the AI asked about shows a one-line "Accept anyway?" question that never blocks.

**Speed.** The model is read from Ollama once and kept for 5 minutes by default. See `project\models\component1\part_b\README.md` for the measured effect of `num_gpu`/`num_ctx` and for `setx OLLAMA_KEEP_ALIVE 1h` (and optionally `setx OLLAMA_FLASH_ATTENTION 1`, then quit and restart Ollama). These variables belong to the Ollama server, not to the API script. Tuned settings can change the wording slightly, so run the local evaluation with the settings used for the demo.

## Scripts
| Command | What it does |
|---|---|
| `npm run dev` | dev server on 127.0.0.1:5173 |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint |
| `npm test` | Vitest + React Testing Library (fetch is mocked; no backend needed; run it from `frontend/c1`, the contract test reads `docs/c1_openapi.json`) |
| `npm run build` | typecheck, then production build into `dist/` |

## How to use it
1. **Upload source files** (button or drag and drop onto the sources card): `.txt .md .pdf .docx`, 20 MB each. File type and size are checked in the browser; server errors appear as messages.
2. **Run analysis** (enabled once a source exists). The pipeline strip follows the job stage from the API; a progress bar shows draft generation while it runs.
3. Click a stat card or use the search and filters to narrow the findings; use the up and down arrow keys in the list and Enter to jump to the detail.
4. In the detail panel read the explanation, check the draft, then **Accept**, **Edit manually** (write a clarified requirement) or **Reject**. **Export analysis** downloads CSV or JSON.

## Notes
- Every number on the page comes from the API. The tool does not write a "suggested revision": only the model draft (story, task, criteria, follow-up questions) and your own edit exist.
- Model confidence is the FR/NFR classifier's probability for its own label, a model probability and not a verified accuracy. Risk levels come from an unvalidated heuristic in the backend; conflicts are rule-based candidates that need a human decision.
- The header pill follows `/api/health` every 15 s: "AI engine ready", "Generation offline" (models loaded but the generation backend is unreachable) or "Engine error".
- Sidebar items other than Requirement intelligence are disabled ("Coming soon"). The signed-in user is a fixed placeholder in `src/config.ts`.
