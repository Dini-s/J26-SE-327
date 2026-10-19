// Runs against the real shell in a real browser; the requirement service is answered here (route on port 8000), so no backend and no model server are needed.
import { expect, test, type Page } from '@playwright/test'
import * as fx from '../src/modules/requirement-intelligence/test/fixtures'

const json = (body: unknown, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })
const TITLES = [
  ['Overview', '/requirement'],
  ['Sources & Findings', '/requirement/sources'],
  ['Review Queue', '/requirement/review'],
  ['Publish', '/requirement/drafts'],
] as const

interface Seen {
  puts: string[]
  decisions: { method: string; body: string }[]
}

/** Answers the service on port 8000. Decisions are kept, so the page can show what it saved. */
async function mockApi(page: Page, seen: Seen = { puts: [], decisions: [] }) {
  let decision: { decision: string; edited_text: null; note: string | null; updated_at: string } | null = null
  await page.route(
    (url) => url.port === '8000',
    async (route) => {
      const req = route.request()
      const p = new URL(req.url()).pathname
      const m = req.method()
      if (m === 'PUT' && p === '/api/engine') seen.puts.push(req.postData() ?? '')
      if (p === '/api/health') return route.fulfill(json({ ...fx.health, generation_backend: 'ollama', model: 'c1-req' }))
      if (p === '/api/engine') return route.fulfill(json(fx.engine))
      if (p === '/api/projects') return route.fulfill(json([fx.project]))
      if (p === '/api/projects/1/overview') return route.fulfill(json(fx.overview))
      if (p === '/api/projects/1/sources') return route.fulfill(json([fx.source]))
      if (p === '/api/projects/1/summary') return route.fulfill(json(fx.summary))
      if (p === '/api/projects/1/sprints') return route.fulfill(json(fx.sprints))
      if (p === '/api/projects/1/phases') return route.fulfill(json(fx.phases))
      if (p === '/api/projects/1/sprints/1/summary') return route.fulfill(json(fx.sprintSummary))
      if (p === '/api/projects/1/sync') return route.fulfill(json(fx.sync))
      if (p === '/api/projects/1/integrations/jira') return route.fulfill(json(fx.jiraNotConnected))
      if (p === '/api/projects/1/requirements') return route.fulfill(json({ total: fx.rows.length, limit: 500, offset: 0, items: fx.rows.map((r, i) => (i === 0 && decision ? { ...r, decision: decision.decision } : r)) }))
      if (p === '/api/requirements/p1-REQ-001/decision') {
        seen.decisions.push({ method: m, body: req.postData() ?? '' })
        if (m === 'PUT') {
          const body = JSON.parse(req.postData() ?? '{}')
          decision = { decision: body.decision, edited_text: null, note: body.note ?? null, updated_at: '2026-10-14T09:30:00+00:00' }
          return route.fulfill(json({ uid: 'p1-REQ-001', ...decision }))
        }
        decision = null
        return route.fulfill({ status: 204 })
      }
      if (p.startsWith('/api/requirements/')) return route.fulfill(json({ ...fx.detail, decision, generation: { ...fx.generationDone, backend: 'ollama', model: 'c1-req' } }))
      return route.fulfill(json({ error: { code: 'not_found', message: `no mock for ${m} ${p}` } }, 404))
    },
  )
}

test('the module in the shell: the sidebar item expands to four pages, each with its own title and active state', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await mockApi(page)
  await page.goto('/requirement')

  const nav = page.locator('aside')
  await expect(nav.getByRole('link', { name: 'Research Overview' })).toBeVisible()
  for (const [, path] of TITLES) await expect(nav.locator(`a[href="${path}"]`).last()).toBeVisible() // expanded because a page of the module is open
  await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible()
  await expect(nav.locator('a[href="/requirement"]').last()).toHaveClass(/bg-blue-600/)

  // overview content
  await expect(page.getByTestId('kpi-requirements')).toContainText('42')
  await expect(page.getByTestId('decision-progress')).toContainText('35.7% decided')
  await expect(page.getByTestId('donut-total')).toHaveText('42')
  await expect(page.getByTestId('process-stage')).toHaveCount(5)
  await expect(page.getByTestId('process-stage').nth(3)).toHaveAttribute('data-state', 'active')
  await expect(page.getByTestId('current-sprint-name')).toHaveText('Sprint 1')
  await expect(page.getByTestId('sync-state')).toContainText('Synced at')
  await expect(page.getByTestId('chart-sprints')).toBeVisible()
  await expect(page.getByTestId('jira-card').getByTestId('jira-connect')).toBeEnabled()
  await expect(page.getByTestId('jira-card')).not.toContainText('Coming soon')

  // header: project and the compact engine pill
  await expect(page.getByTestId('project-trigger')).toContainText('Core Banking Platform')
  await expect(page.getByTestId('engine-pill')).toContainText('AI engine')
  await expect(page.getByTestId('engine-pill')).toHaveAttribute('data-state', 'ready')
  await expect(page.getByTestId('engine-pill')).not.toContainText(/device|cloud/i) // the pill is a status dot only
  await expect(page.getByTestId('engine-pill')).not.toContainText('c1-req')

  for (const [title, path] of TITLES.slice(1)) {
    await nav.locator(`a[href="${path}"]`).last().click()
    await expect(page).toHaveURL(new RegExp(`${path}$`))
    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
    await expect(nav.locator(`a[href="${path}"]`).last()).toHaveClass(/bg-blue-600/)
    await expect(nav.locator('a[href="/requirement"]').last()).not.toHaveClass(/bg-blue-600/)
  }

  // back to the shell's own overview
  await page.getByRole('link', { name: 'Research Overview' }).click()
  await expect(page).toHaveURL(/\/overview$/)
  expect(errors).toEqual([])
})

test('Processing details holds the switch, the cloud settings and the technical facts; the cloud form validates before anything is sent', async ({ page }) => {
  const seen: Seen = { puts: [], decisions: [] }
  await mockApi(page, seen)
  await page.goto('/requirement')
  await page.getByTestId('engine-pill').click()
  const details = page.getByRole('dialog', { name: 'Processing details' })
  await expect(details).toBeVisible()
  await expect(details.getByRole('radio', { name: /on device/i })).toBeChecked()
  await expect(details.getByRole('radio', { name: /set up cloud/i })).toBeDisabled()
  await expect(details.getByTestId('technical-details')).toContainText('c1-req') // model and mode are shown here and nowhere else

  await details.getByRole('button', { name: 'Cloud settings' }).click()
  const dialog = page.getByRole('dialog', { name: 'Cloud settings' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(dialog.getByText(/enter the cloud url/i)).toBeVisible()
  await expect(dialog.getByText(/tick this box/i)).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(details).toBeVisible() // Escape closes the inner popover first
  await page.keyboard.press('Escape')
  await expect(details).toBeHidden()
  expect(seen.puts).toEqual([])
})

test('Review Queue: a decision becomes a status card with only Change and Remove; Remove asks first and goes back to the choices', async ({ page }) => {
  const seen: Seen = { puts: [], decisions: [] }
  await mockApi(page, seen)
  await page.goto('/requirement/review')

  await expect(page.getByTestId('finding-row')).toHaveCount(fx.rows.length)
  await expect(page.getByTestId('provenance')).toContainText('Generated by AI')
  await expect(page.getByTestId('provenance')).not.toContainText(/on device|cloud/i)
  await expect(page.getByTestId('provenance')).not.toContainText('c1-req')
  await page.getByRole('button', { name: 'Accept', exact: true }).click()

  const card = page.getByTestId('decision-card')
  await expect(card).toHaveAttribute('data-status', 'accepted')
  await expect(card.getByRole('button')).toHaveText(['Change decision', 'Remove decision'])
  await expect(page.getByTestId('decision-history')).toHaveCount(0)
  expect(seen.decisions.map((d) => d.method)).toEqual(['PUT'])

  await card.getByRole('button', { name: 'Remove decision' }).click()
  const dialog = page.getByRole('dialog', { name: 'Remove this decision?' })
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
  await dialog.getByRole('button', { name: 'Remove decision' }).click()
  await expect(page.getByRole('button', { name: 'Accept', exact: true })).toBeVisible()
  expect(seen.decisions.map((d) => d.method)).toEqual(['PUT', 'DELETE'])
})

test('Improve needs attention when drafts failed: the strip opens the failed drafts, and “Retry failed drafts” queues only those', async ({ page }) => {
  await mockApi(page)
  const improve = { ...fx.overview.pipeline.improve, state: 'attention', requirements: 334, decided: 5, drafts_written: 327, drafts: { ready: 320, needs_clarification: 7, failed: 7, waiting: 0 } }
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/overview', (route) => route.fulfill(json({ ...fx.overview, pipeline: { ...fx.overview.pipeline, improve } })))
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/summary', (route) => route.fulfill(json({ ...fx.summary, task_drafts: { ...fx.summary.task_drafts, failed: 7 } })))
  let retried = 0
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/drafts/retry-failed', (route) => {
    retried += 1
    return route.fulfill(json({ queued: 7 }, 202))
  })
  await page.goto('/requirement')
  const stage = page.getByTestId('process-stage').nth(3)
  await expect(stage.getByTestId('stage-state')).toHaveText('Needs attention')
  await stage.getByRole('link').click()
  await expect(page).toHaveURL(/\/requirement\/drafts\?filter=failed$/)
  await expect(page.getByTestId('publish-table')).toBeVisible()
  await expect(page.getByTestId('failed-banner-title')).toHaveText('7 drafts could not be written') // the Publish page keeps the banner and the retry
  await page.getByTestId('retry-failed').click()
  await expect(page.getByText('7 failed drafts queued again.')).toBeVisible()
  expect(retried).toBe(1)
})

test('Jira: back from the sign-in shows a notice, then Import from Jira lists projects and boards and reports what was imported', async ({ page }) => {
  await mockApi(page)
  const base = 'http://localhost:8000/api/projects/1/integrations/jira'
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/integrations/jira', (route) => route.fulfill(json(fx.jiraConnected)))
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/integrations/jira/projects', (route) => route.fulfill(json(fx.jiraProjects)))
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/integrations/jira/boards', (route) => route.fulfill(json(fx.jiraBoards)))
  let sent = ''
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/integrations/jira/import', (route) => {
    sent = route.request().postData() ?? ''
    return route.fulfill(json(fx.jiraImported))
  })
  expect(base).toContain('integrations/jira')
  await page.goto('/requirement?jira=connected')
  await expect(page.getByText('Jira is connected.')).toBeVisible()
  await expect(page).toHaveURL(/\/requirement$/)
  await expect(page.getByTestId('jira-site')).toHaveText('Connected to Acme')
  await page.getByTestId('jira-import').click()
  await page.getByTestId('jira-project').selectOption('ABC')
  await expect(page.getByTestId('jira-board')).toBeEnabled()
  await page.getByTestId('jira-board').selectOption('7')
  await expect(page.getByTestId('jira-target')).toHaveValue('') // the current sprint
  await expect(page.getByTestId('jira-target').locator('option')).toHaveText(['Sprint 1 (current)', 'Sprint 2', 'Sprint 3'])
  await page.getByTestId('jira-import-submit').click()
  await expect(page.getByTestId('jira-result')).toContainText('12 new issues')
  expect(JSON.parse(sent)).toMatchObject({ project_key: 'ABC', board_id: 7, issue_types: ['Story', 'Task'], target_sprint_id: null })
  await page.getByTestId('jira-done').click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('Review Queue: 50 per page with previous / next, See all, and the page size is remembered', async ({ page }) => {
  await mockApi(page)
  const items = Array.from({ length: 120 }, (_, i) => ({ ...fx.rows[i % 3]!, uid: `p1-REQ-${String(i + 1).padStart(3, '0')}`, id: `REQ-${String(i + 1).padStart(3, '0')}` }))
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/requirements', (route) => route.fulfill(json({ total: 120, limit: 500, offset: 0, items })))
  await page.goto('/requirement/review')
  await expect(page.getByTestId('finding-row')).toHaveCount(50)
  await expect(page.getByTestId('pager-showing')).toHaveText('Showing 1-50 of 120')
  await page.getByTestId('pager-next').focus()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('pager-showing')).toHaveText('Showing 51-100 of 120')
  await page.getByTestId('page-size-all').click()
  await expect(page.getByTestId('finding-row')).toHaveCount(120)
  await page.reload()
  await expect(page.getByTestId('finding-row')).toHaveCount(120)
  await page.getByTestId('page-size-50').click()
  await expect(page.getByTestId('finding-row')).toHaveCount(50)
})

test('Review Queue: select all shown / all N, Accept selected asks first and makes one decision per requirement', async ({ page }) => {
  await mockApi(page)
  const items = Array.from({ length: 120 }, (_, i) => ({ ...fx.rows[i % 3]!, decision: null, uid: `p1-REQ-${String(i + 1).padStart(3, '0')}`, id: `REQ-${String(i + 1).padStart(3, '0')}` }))
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/requirements', (route) => route.fulfill(json({ total: 120, limit: 500, offset: 0, items })))
  const decided: string[] = []
  await page.route((url) => url.port === '8000' && /^\/api\/requirements\/[^/]+\/decision$/.test(url.pathname) && !!url.pathname, (route) => {
    if (route.request().method() === 'PUT') {
      decided.push(new URL(route.request().url()).pathname)
      return route.fulfill(json({ uid: 'x', decision: 'accepted', edited_text: null, note: null, decided_at: '2026-10-20T08:00:00+00:00' }))
    }
    return route.fallback()
  })
  await page.goto('/requirement/review')
  await expect(page.getByTestId('finding-row')).toHaveCount(50)
  await page.getByTestId('select-mode').click()
  await page.getByTestId('select-shown').click()
  await expect(page.getByTestId('selected-count')).toHaveText('50 selected')
  await page.getByTestId('select-all-n').click()
  await expect(page.getByTestId('selected-count')).toHaveText('120 selected')
  await page.getByTestId('accept-selected').click()
  expect(decided).toHaveLength(0) // asked first
  await page.getByRole('dialog').getByRole('button', { name: 'Accept' }).click()
  await expect(page.getByText('120 requirements accepted.')).toBeVisible()
  expect(decided).toHaveLength(120)
})

test('Review Queue: the Filters panel holds the filters and shows a removable chip', async ({ page }) => {
  await mockApi(page)
  await page.goto('/requirement/review')
  await expect(page.getByTestId('finding-row')).toHaveCount(fx.rows.length)
  await page.getByTestId('filters-button').click()
  await page.getByLabel('Suggested action').selectOption('edit')
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('filter-chip')).toHaveText('Suggested: Edit')
  await expect(page.getByTestId('finding-row')).toHaveCount(2)
  await page.getByRole('button', { name: 'Remove filter: Suggested: Edit' }).click()
  await expect(page.getByTestId('finding-row')).toHaveCount(fx.rows.length)
})

test('Sources & Findings: documents are grouped by sprint, with Upload here; the Jira upload type cannot be chosen; the Findings tab opens an item in the Review Queue', async ({ page }) => {
  await mockApi(page)
  await page.goto('/requirement/sources')
  await expect(page.getByTestId('sprint-group').first()).toHaveAttribute('data-current', 'true')
  await expect(page.getByTestId('sprint-group')).toHaveCount(1) // one sprint at a time: the current one
  await expect(page.getByTestId('empty-sprint')).toHaveCount(0)
  await page.getByTestId('sprint-view').selectOption('sprint-3')
  await expect(page.getByTestId('empty-sprint').first()).toContainText('No documents yet')
  await page.getByRole('button', { name: 'Upload documents to Sprint 3' }).click()
  await expect(page.getByTestId('upload-sprint')).toHaveValue('3')
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click()
  await expect(page.getByTestId('jira-row').getByTestId('jira-connect')).toBeEnabled()
  await page.getByTestId('sprint-view').selectOption('sprint-1')
  await page.getByTestId('upload-button').click()
  const type = page.getByTestId('source-type-select')
  await expect(type.locator('option[value="jira"]')).toHaveAttribute('disabled', '')
  await expect(type.locator('option[value="jira"]')).toHaveText('Jira (use Import from Jira)')
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click()
  await page.getByTestId('edit-sprint').click()
  await expect(page.getByRole('dialog', { name: /^Edit / })).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click()
  await page.getByTestId('add-next-sprint').click()
  await page.getByRole('dialog', { name: 'New sprint' }).getByRole('button', { name: 'Create sprint' }).click()
  await expect(page.getByRole('dialog', { name: /created$/ })).toBeVisible()
  await expect(page.getByTestId('next-sprint-upload')).toBeVisible()
  await expect(page.getByTestId('next-sprint-move')).toBeVisible()
  await page.getByTestId('next-sprint-done').click()
  await page.getByRole('tab', { name: 'Findings' }).click()
  await expect(page.getByRole('radio', { name: 'Ambiguities' })).toBeChecked()
  await page.getByRole('link', { name: 'Open REQ-002 in Review Queue' }).click()
  await expect(page).toHaveURL(/\/requirement\/review\?uid=p1-REQ-002$/)
  await expect(page.getByRole('option', { name: /REQ-002/ })).toHaveAttribute('aria-selected', 'true')
})

test('Sources & Findings: Analyse asks which task drafts to write first, and Analyse selected works on ticked documents', async ({ page }) => {
  await mockApi(page)
  const second = { ...fx.source2, id: 2, filename: 'Payments_BRD.docx', default_sprint_id: 1 }
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/sources', (route) => route.fulfill(json([{ ...fx.source, sprints: [{ sprint_id: 1, count: 42 }] }, second])))
  const sent: string[] = []
  await page.route((url) => url.port === '8000' && url.pathname === '/api/projects/1/sources/2/reanalyze', (route) => {
    sent.push(new URL(route.request().url()).searchParams.get('policy') ?? '')
    return route.fulfill(json({ source_id: 2, kept: 0, changed: 0, removed: 0, added: 5, queued: 0, job: null }, 202))
  })
  await page.goto('/requirement/sources')
  await page.getByRole('checkbox', { name: 'Select Payments_BRD.docx' }).check()
  await expect(page.getByTestId('docs-selected')).toHaveText('1 selected')
  await page.getByTestId('analyse-selected').click()
  await expect(page.getByTestId('analyse-policy')).toBeVisible()
  expect(sent).toHaveLength(0) // asked first
  await page.getByTestId('policy-all').check()
  await page.getByTestId('analyse-confirm').click()
  await expect.poll(() => sent).toEqual(['all'])
})

test('Publish: a sprint table, publish one document after the question, take it back, and publish the whole sprint', async ({ page }) => {
  await mockApi(page)
  const sent: { path: string; body: unknown }[] = []
  for (const path of ['publish', 'unpublish']) {
    await page.route((url) => url.port === '8000' && url.pathname === `/api/projects/1/${path}`, (route) => {
      sent.push({ path, body: JSON.parse(route.request().postData() ?? '{}') })
      return route.fulfill(json({ action: path, changed: [{ document_id: 1, name: 'CoreBanking_SRS_v2.pdf' }], skipped: [], published_documents: 2, total_documents: 3, sync: { state: 'synced', error: null } }))
    })
  }
  await page.goto('/requirement/drafts')
  await expect(page.getByRole('heading', { level: 1, name: 'Publish' })).toBeVisible()
  await expect(page.getByTestId('publish-table')).toBeVisible()
  await expect(page.getByTestId('publish-row')).toHaveCount(3)
  await expect(page.getByTestId('summary-documents')).toContainText('Published 1 of 3 documents')

  const srs = page.locator('[data-testid="publish-row"][data-doc="CoreBanking_SRS_v2.pdf"]')
  await srs.getByTestId('row-publish').click()
  await expect(page.getByTestId('plan-documents')).toContainText('1 document with 30 requirements')
  await expect(page.getByTestId('plan-pending')).toContainText('18 requirements without a decision')
  expect(sent).toHaveLength(0) // asked first
  await page.getByTestId('publish-confirm').click()
  await expect(page.getByText('1 document published.')).toBeVisible()
  expect(sent).toEqual([{ path: 'publish', body: { document_ids: [1] } }])

  await page.locator('[data-testid="publish-row"][data-doc="ABC stories"]').getByTestId('row-unpublish').click()
  await expect.poll(() => sent.map((s) => s.path)).toEqual(['publish', 'unpublish'])
  expect(sent[1]!.body).toEqual({ document_ids: [3] })

  await page.getByRole('checkbox', { name: 'Select Billing_BRD.docx' }).check()
  await page.getByTestId('publish-selected').click()
  await expect(page.getByTestId('plan-skipped')).toContainText('Billing_BRD.docx: Analyse the document first.')
  await page.getByRole('button', { name: 'Cancel' }).click()

  await page.getByTestId('publish-whole-sprint').click()
  await page.getByTestId('publish-confirm').click()
  await expect.poll(() => sent.at(-1)).toEqual({ path: 'publish', body: { sprint_id: 1 } })

  await srs.getByRole('button', { name: 'Details of CoreBanking_SRS_v2.pdf' }).click()
  await page.getByTestId('open-in-review').click()
  await expect(page).toHaveURL(/\/requirement\/review\?document=CoreBanking_SRS_v2\.pdf$/)
  await expect(page.getByTestId('filter-chip')).toContainText('Document: CoreBanking_SRS_v2.pdf')
})
