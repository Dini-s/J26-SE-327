import { defineConfig } from '@playwright/test'

/** Optional smoke test against the RUNNING live stack (API on 8000 in Ollama mode, UI on 5173). Uses the installed Chrome: no browser download. */
export default defineConfig({
  testDir: './e2e',
  timeout: 15 * 60_000,
  retries: 0,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5173', channel: 'chrome', headless: true },
})
