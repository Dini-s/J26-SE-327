// Run from frontend/c1 (npm run e2e): paths are relative to the current folder.
import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const SRS = resolve(process.cwd(), '../../scripts/fixtures/live_check_srs.txt')
const SHOTS = resolve(process.cwd(), '../../project/outputs/c1_live_check')

test('live stack: upload, run analysis, a real model draft appears', async ({ page, request }) => {
  const health = await (await request.get('http://127.0.0.1:8000/api/health')).json()
  expect(health.generation_backend, 'start the API with scripts/run_c1_live.ps1').toBe('ollama')
  expect(health.generation_reachable, 'Ollama / model c1-req must be reachable').toBe(true)

  await page.goto('/')
  await page.getByTestId('file-input').setInputFiles(SRS)
  await expect(page.getByTestId('sources-card')).toContainText('live_check_srs.txt')

  await page.getByRole('button', { name: 'Run analysis' }).click()
  await expect(page.getByRole('button', { name: /Analysing/ })).toBeDisabled()

  // wait until at least one requirement has a draft written by the live model (tens of seconds per draft on a 4 GB GPU)
  const prov = page.getByTestId('provenance').first()
  // the default "smart" policy writes drafts for P1 requirements only: open rows until one has a finished draft
  await expect(async () => {
    const rows = page.getByTestId('finding-row')
    let found = false
    for (let i = 0; i < (await rows.count()) && !found; i++) {
      await rows.nth(i).click()
      found = (await page.getByTestId('provenance').count()) > 0
    }
    expect(found).toBe(true)
  }).toPass({ timeout: 10 * 60_000, intervals: [5_000] })
  await expect(prov).toContainText('Written by c1-req on device')

  mkdirSync(SHOTS, { recursive: true })
  await page.screenshot({ path: resolve(SHOTS, 'live_draft.png'), fullPage: true })

  // tidy up: remove only the file this test uploaded
  await page.getByRole('button', { name: 'Remove live_check_srs.txt' }).click()
  await page.getByRole('group', { name: /Confirm removing/ }).getByRole('button', { name: 'Remove' }).click()
  await expect(page.getByTestId('sources-card')).not.toContainText('live_check_srs.txt')
})
