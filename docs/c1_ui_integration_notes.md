# C1 UI integration notes (Phase 1: what `project/apps/web` is)

Read on 2026-10-16 from the merged branch. Nothing here was changed to find it out.

## 1. Stack of `project/apps/web`
| | |
|---|---|
| Framework | React 19.2 (`react`, `react-dom ^19.2.8`), **plain JavaScript (JSX), no TypeScript** (no tsconfig) |
| Bundler | Vite 8 (`@vitejs/plugin-react`), `vite.config.js` has only the react and Tailwind plugins |
| Router | `react-router-dom ^7.18` (`BrowserRouter`, one layout route with `<Outlet/>`) |
| State / data | none yet: no store, no data-fetching library, no `fetch` call anywhere (the dashboard shows static data from `src/data/dashboardData.js`) |
| Styling | Tailwind CSS **v4** (`@tailwindcss/vite`, CSS-first `@theme` tokens in `src/index.css`: `primary`, `danger*`, `warning*`, `success*`, `info*`, `ai*`, `border`, `heading`, `body`, `secondary-text`, `muted`, `page`...), mostly utility classes written in the JSX; one component class `.input-style` |
| UI library | none (own components in `src/component/`), icons from `lucide-react ^1.57` |
| Package manager | npm (`package-lock.json`) |
| Dev port | not set, so the Vite default **5173** (http://localhost:5173) |
| Commands | `npm run dev`, `npm run build` (= `vite build`), `npm run lint` (ESLint 10 flat config for `*.js/*.jsx`), `npm run preview` |
| Tests | **none** (no test runner, no Playwright) |
| `node_modules` | not installed in the repository (needs `npm install`) |

## 2. Shell structure
- `src/main.jsx` -> `App.jsx` -> `routes/AppRoutes.jsx`: one `BrowserRouter`, one layout route `/` (`Layouts/DashboardLayout.jsx`) with child routes. Today only `index` (redirect to `/overview`) and `overview` exist.
- `Layouts/DashboardLayout.jsx`: fixed dark sidebar (260 px, collapsible to 72 px) + sticky `TopHeader` (static title "ASPIRE", date, refresh, bell) + `<main className="p-4 sm:p-6"><Outlet/></main>` on a `bg-slate-50` page.
- Sidebar items are **data**: `src/data/navigation.js` (`item` / `section` entries with `label`, `path`, `icon`, optional `children`, `number`, `numberColor`). `SidebarItem` renders a `NavLink` (exact match). There is **no "Coming soon" mechanism**: every listed item is a link; a path with no registered route simply renders an empty `<Outlet/>` (there is no catch-all or 404 route).
- **"Requirement Intelligence"** is already in `navigation.js` (number 1, green, icon `FileText`, path `/requirement`) but **no route is registered for it**, so it renders nothing today. A module page is registered by adding a `<Route>` under the layout route in `AppRoutes.jsx`.
- The sidebar footer shows a hard-coded "Active Repository: Spring PetClinic" card (static). There is no project selector and no project context.

## 3. Differences from `frontend/c1`
| | `frontend/c1` | `apps/web` |
|---|---|---|
| Language | TypeScript 6, strict | JavaScript (JSX) |
| React | 19.3 | 19.2 |
| Router | none (single page) | react-router-dom 7 |
| Data | TanStack Query 5 | none |
| Tailwind | 3.4 (`tailwind.config.js`, PostCSS) | 4 (`@theme` in CSS, Vite plugin) |
| Tokens | mockup tokens (`brand`, `ink`, `nav`, `risk-*`, `ok`, `info`, `ai`; radius `card`/`ctl`) | slate palette + `primary` #4f46e5 (the same indigo as my `brand-600`), `danger/warning/success/info/ai` sets |
| Fonts | `@fontsource/inter` | `Inter, system-ui` family, no font package |
| Tests | Vitest 5 + RTL + jsdom (195), Playwright e2e | none |
| Lint | ESLint + typescript-eslint | ESLint (js/jsx only) |
| Own sidebar / header / layout | yes (`Sidebar.tsx`, `Header.tsx`, page grid) | the shell's; mine are duplicates and are not ported |

## 4. Backends and CORS
- `apps/web` calls nothing yet: no base URL, no env variable, no proxy configuration (Vite `server` is unset).
- `project/apps/api` is **empty** (`main.py` and `requirements.txt` have 0 bytes), so it declares no port and **there is no port clash with C1's API (8000) today**. If it later uses uvicorn's default port 8000, one of the two needs another port, so the C1 start script gets a `-Port` option (the web app reads the C1 address from `VITE_C1_API_BASE`).
- C1's API (FastAPI) allows the origins `http://localhost:5173` and `http://127.0.0.1:5173` only. `apps/web` on its default port is `http://localhost:5173`, so it is already allowed; for any other port or host the allow-list is made configurable (`C1_CORS_ORIGINS`).
- The old `frontend/c1` dev server also uses 5173 (`--strictPort`): the two UIs cannot run at the same time.

## 5. Current project
The shell exposes none. C1 keeps its stub behaviour: the API's first workspace project (integer id) and, for Neo4j publishing, `C1_PROJECT_ID` (`demo-project`). The page shows that project's name in its own status area.

## Gate result
`apps/web` is React, has a workable place to register a page (`AppRoutes.jsx` + an existing sidebar item) and nothing in it conflicts with a port of the C1 module. No blocker: Phase 2 proceeds. Points to watch: the shell is JavaScript, so TypeScript, TanStack Query and Vitest are added next to it; the shell has no tests or lint rules for `.ts/.tsx`, so those are added for the module only.
