# ASPIRE dashboard (React + Vite)

## C4 pages (Traceability Intelligence)

| Route | What it does | Data |
|---|---|---|
| `/traceability` | Overview: KPIs, pipeline, every verified/decayed link with the LLM's reason, decay events, completeness and orphans, measured results against the targets, what was tried to improve the shortlist | live from Neo4j; results from `data/results/*.json` |
| `/traceability/link` | **Link requirements:** create trace links for requirements that have none, or type a new requirement; run history and per-file AI verdicts | live; starts the real linking job |
| `/traceability/changes` | **Code changes:** scan for drift, simulate a commit (edit a linked file), see which links break, the message sent to C3, undo/reset | live; starts the real re-check job |
| `/traceability/analytics` | **Analytics:** coverage, confidence and links-per-requirement charts, links over time, completeness trend, requirements at risk, change hotspots, unstable files, weakest links, trusted links; **Impact analysis:** pick a code file or requirement and see what depends on it (and C3's RVUs/tests when C3 has written them) | live |
| `/traceability/labeling` | **Evaluate links:** read a requirement and its code, mark the link correct / wrong / unsure; gives precision with a 95% range and precision by AI confidence | live; labels saved in `data/labels/` |
| `/traceability/graph` | Requirement-to-code graph and traceability matrix with filters and a details panel | live |
| `/knowledge-graph` | **Unified Software Knowledge Graph:** drag/zoom graph with the modes Trace links, Code structure (C2), Requirement details (C1), Everything, and an inspector | live |

The Overview page also downloads the matrix CSV, links CSV and report JSON. The repository is chosen in the sidebar and the top-bar refresh reloads the data. These pages replace the old single-page demo (kept in `apps/web_legacy/`). The actions on the Link and Code changes pages run the same Python jobs as the old demo and write to your local Neo4j (demo mode: only a local database, only demo data).

The other pages of the dashboard still show sample data.

### Run

```bash
# terminal 1, from project/: the API (needs Neo4j running)
python -m apps.api.server                     # port 8000; C4_WEB_PORT=8001 python -m apps.api.server for another port

# terminal 2, from project/apps/web/
npm ci                                        # once
npm run dev                                   # http://127.0.0.1:5173/traceability
# if the API is on another port:  C4_API=http://127.0.0.1:8001 npm run dev
```

The dev server forwards `/api/...` to the Python API (`vite.config.js`). The API also serves the old single-page demo (the "legacy" demo with the Link, Code change, Graph and Results tabs) at http://127.0.0.1:8000/ from `apps/web_legacy/index.html`. All C4 actions (create links, simulate a commit, scan, undo, reset) are now in the React pages too.
Restart a Python server that was started before 16 Oct 2026: it does not have the new endpoints (`/api/links`, `/api/completeness`, `/api/analysis`).

---

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
