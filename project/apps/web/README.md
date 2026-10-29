# ASPIRE frontend

React with JavaScript/JSX, Vite, Tailwind CSS, and React Router.

```sh
npm install
npm run dev
npm run build
```

`src/main.jsx` mounts `App.jsx`. Routes are defined in `src/routes/AppRoutes.jsx`.
The shared dashboard is at `/overview`; Quality & Testing Intelligence is at
`/quality/overview`, `/quality/requirements`, `/quality/requirements/:requirementId`,
and `/quality/reports`.

- `src/pages/`: dashboard and quality pages (`.jsx`).
- `src/Layouts/`: dashboard and quality layouts (`.jsx`).
- `src/component/common/`: reusable UI components.
- `src/component/quality/QualityApp.jsx`: quality initialization and page selection.
- `src/services/qualityApi.js`: quality API client.

Vite proxies `/api` and `/health` to `http://127.0.0.1:8000`.
Set `VITE_API_BASE_URL` to override the default `/api/quality` endpoint.
