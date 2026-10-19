import { defineConfig } from '@playwright/test'

/**
 * End-to-end tests of the Requirement Intelligence page (route /requirement) in the real shell.
 * - e2e/c1-page.spec.ts always runs: the browser is real, the C1 API is answered by the test (no backend, no Ollama).
 * - e2e/c1-live.spec.ts is opt-in (C1_E2E_LIVE=1): it needs the live API on :8000 (scripts/run_c1_live.ps1) and Ollama with the model c1-req.
 * Uses the installed Chrome (no browser download). Without Chrome: `npx playwright install chromium` and remove `channel` below.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 0,
  reporter: 'list',
  use: { baseURL: 'http://localhost:5173', channel: 'chrome', headless: true },
  webServer: { command: 'npm run dev -- --port 5173 --strictPort', url: 'http://localhost:5173', reuseExistingServer: true, timeout: 60_000 },
})
