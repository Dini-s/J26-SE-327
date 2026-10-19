import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PublishDocsResult, SprintSummary } from '../api/types'
import * as fx from './fixtures'
import { json, mockApi, renderApp, type Handler } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

const PAGE = '/requirement/drafts'
const PUBLISH = '/api/projects/1/publish'
const UNPUBLISH = '/api/projects/1/unpublish'
const SRS = 'CoreBanking_SRS_v2.pdf'
const result = (over: Partial<PublishDocsResult> = {}): PublishDocsResult => ({
  action: 'publish', changed: [{ document_id: 1, name: SRS }], skipped: [], published_documents: 2, total_documents: 3, sync: { state: 'synced', error: null }, ...over,
})
const answering = (path: string, body: PublishDocsResult): Handler => (c) => (c.method === 'POST' && c.url.pathname === path ? json(body) : undefined)
const posts = (calls: { method: string; url: URL; body?: string }[], path: string) => calls.filter((c) => c.method === 'POST' && c.url.pathname === path)
const row = (name: string) => screen.getAllByTestId('publish-row').find((r) => r.getAttribute('data-doc') === name)!
const ready = async () => screen.findByTestId('publish-table')

describe('Publish page: the table of one sprint', () => {
  it('replaces Task Drafts: heading Publish, no draft list or detail', async () => {
    mockApi()
    renderApp(PAGE)
    expect(await screen.findByRole('heading', { level: 1, name: 'Publish' })).toBeInTheDocument()
    await ready()
    expect(screen.queryByTestId('workspace')).toBeNull()
    expect(screen.queryByTestId('finding-row')).toBeNull()
    expect(screen.queryByTestId('draft-card')).toBeNull()
  })

  it('opens on the current sprint and reads its summary from the service', async () => {
    const { calls } = mockApi()
    renderApp(PAGE)
    await ready()
    const select = screen.getByTestId('publish-sprint') as HTMLSelectElement
    expect([...select.options].map((o) => o.textContent)).toEqual(['Sprint 1 (current)', 'Sprint 2', 'Sprint 3'])
    expect(select).toHaveValue('1')
    expect(calls.some((c) => c.url.pathname === '/api/projects/1/sprints/1/summary')).toBe(true)
    await userEvent.selectOptions(select, '2')
    await waitFor(() => expect(calls.some((c) => c.url.pathname === '/api/projects/1/sprints/2/summary')).toBe(true))
  })

  it('shows the summary bar', async () => {
    mockApi()
    renderApp(PAGE)
    await ready()
    expect(screen.getByTestId('summary-documents')).toHaveTextContent('Published 1 of 3 documents')
    expect(screen.getByTestId('summary-requirements')).toHaveTextContent('34 · 23 FR / 10 NFR')
    expect(screen.getByTestId('summary-drafts')).toHaveTextContent('26 ready · 2 need clarification · 1 failed')
    expect(screen.getByTestId('summary-decided')).toHaveTextContent('10 accepted · 3 edited · 1 rejected · 20 pending')
  })

  it('has one row per document with its numbers, findings and status', async () => {
    mockApi()
    renderApp(PAGE)
    await ready()
    expect(screen.getAllByTestId('publish-row').map((r) => r.getAttribute('data-doc'))).toEqual([SRS, 'ABC stories', 'Billing_BRD.docx'])
    const srs = row(SRS)
    expect(srs).toHaveTextContent('30')
    expect(srs).toHaveTextContent('20 FR / 9 NFR')
    expect(srs).toHaveTextContent('22 / 2 / 1')
    expect(srs).toHaveTextContent('A 8 · E 3 · R 1 · P 18')
    for (const f of ['Unclear 6', 'Conflict 1', 'Duplicate 2', 'Security 3']) expect(srs).toHaveTextContent(f)
    expect(within(srs).getByTestId('publish-state')).toHaveTextContent('Not published')
    expect(within(row('ABC stories')).getByTestId('publish-state')).toHaveTextContent('Published')
    expect(within(row('ABC stories')).getByTestId('jira-icon')).toBeInTheDocument()
    expect(within(srs).queryByTestId('jira-icon')).toBeNull()
    expect(row('Billing_BRD.docx')).toHaveTextContent('Needs analysis')
    expect(row('Billing_BRD.docx')).toHaveTextContent('None') // no findings
  })

  it('a row opens to its key findings and a link to the Review Queue filtered to that document', async () => {
    mockApi()
    renderApp(PAGE)
    await ready()
    expect(screen.queryByTestId('publish-detail')).toBeNull()
    await userEvent.click(within(row(SRS)).getByRole('button', { name: `Details of ${SRS}` }))
    const detail = screen.getByTestId('publish-detail')
    expect(detail).toHaveTextContent('Unclear wording: 6')
    expect(detail).toHaveTextContent('Possible conflicts: 1')
    expect(detail).toHaveTextContent('5 requirements have no task draft yet.')
    expect(within(detail).getByTestId('open-in-review')).toHaveAttribute('href', `/requirement/review?document=${encodeURIComponent(SRS)}`)
    await userEvent.click(within(detail).getByTestId('open-in-review'))
    expect(await screen.findByTestId('filter-chip')).toHaveTextContent(`Document: ${SRS}`)
    await screen.findAllByTestId('finding-row')
  })

  it('says so when the sprint has no documents', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/sprints/1/summary' ? json({ ...fx.sprintSummary, documents: 0, published: 0, requirements: 0, rows: [] } satisfies SprintSummary) : undefined))
    renderApp(PAGE)
    expect(await screen.findByTestId('publish-empty')).toHaveTextContent('No documents in this sprint yet.')
    expect(screen.getByTestId('publish-whole-sprint')).toBeDisabled()
  })

  it('shows a failed load as an alert', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/sprints/1/summary' ? json({ error: { code: 'sprint_not_found', message: 'Sprint 1 does not exist.' } }, 404) : undefined))
    renderApp(PAGE)
    expect(await screen.findByRole('alert')).toHaveTextContent('Sprint 1 does not exist.')
  })

  it('keeps the failed-draft banner and its retry link here', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/summary' ? json({ ...fx.summary, task_drafts: { ...fx.summary.task_drafts, failed: 2 } }) : undefined))
    renderApp(PAGE)
    expect(await screen.findByTestId('failed-banner-title')).toHaveTextContent('2 drafts could not be written')
    expect(screen.getByTestId('retry-failed')).toBeEnabled()
  })

  it('uses product words only', async () => {
    mockApi()
    renderApp(PAGE)
    await ready()
    expect(document.body.textContent).not.toMatch(/neo4j|graph|cypher|model|\bhost\b|phase/i)
  })
})

describe('Publish page: selecting', () => {
  it('Publish selected counts the chosen documents and is off while none is chosen', async () => {
    mockApi()
    renderApp(PAGE)
    await ready()
    const button = screen.getByTestId('publish-selected')
    expect(button).toHaveTextContent('Publish selected (0)')
    expect(button).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox', { name: `Select ${SRS}` }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select ABC stories' }))
    expect(button).toHaveTextContent('Publish selected (2)')
    expect(button).toBeEnabled()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select all documents' }))
    expect(button).toHaveTextContent('Publish selected (3)')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select all documents' }))
    expect(button).toHaveTextContent('Publish selected (0)')
  })

  it('a changed sprint starts with nothing chosen', async () => {
    mockApi()
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByRole('checkbox', { name: `Select ${SRS}` }))
    await userEvent.selectOptions(screen.getByTestId('publish-sprint'), '2')
    await waitFor(() => expect(screen.getByTestId('publish-selected')).toHaveTextContent('Publish selected (0)'))
  })
})

describe('Publish page: publishing', () => {
  it('one document: the dialog says what goes, the call names the document, the toast says what happened', async () => {
    const { calls } = mockApi(answering(PUBLISH, result()))
    renderApp(PAGE)
    await ready()
    await userEvent.click(within(row(SRS)).getByTestId('row-publish'))
    const dialog = screen.getByRole('dialog', { name: 'Publish this document?' })
    expect(within(dialog).getByTestId('plan-documents')).toHaveTextContent('1 document with 30 requirements will be published.')
    expect(within(dialog).getByTestId('plan-pending')).toHaveTextContent('18 requirements without a decision will be published as pending.')
    expect(within(dialog).queryByTestId('plan-skipped')).toBeNull()
    expect(posts(calls, PUBLISH)).toHaveLength(0) // nothing is sent before the question is answered
    await userEvent.click(within(dialog).getByTestId('publish-confirm'))
    await waitFor(() => expect(posts(calls, PUBLISH)).toHaveLength(1))
    expect(JSON.parse(posts(calls, PUBLISH)[0]!.body!)).toEqual({ document_ids: [1] })
    expect(await screen.findByText('1 document published.')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('cancelling sends nothing', async () => {
    const { calls } = mockApi()
    renderApp(PAGE)
    await ready()
    await userEvent.click(within(row(SRS)).getByTestId('row-publish'))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(posts(calls, PUBLISH)).toHaveLength(0)
  })

  it('a document that cannot be published has a disabled button with the reason', async () => {
    mockApi()
    renderApp(PAGE)
    await ready()
    const button = within(row('Billing_BRD.docx')).getByTestId('row-publish')
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', 'Analyse the document first.')
  })

  it('selected documents: the dialog lists the ones that are skipped and why, and only the others are sent', async () => {
    const { calls } = mockApi(answering(PUBLISH, result()))
    renderApp(PAGE)
    await ready()
    for (const name of [SRS, 'ABC stories', 'Billing_BRD.docx']) await userEvent.click(screen.getByRole('checkbox', { name: `Select ${name}` }))
    await userEvent.click(screen.getByTestId('publish-selected'))
    const dialog = screen.getByRole('dialog', { name: 'Publish 3 documents?' })
    expect(within(dialog).getByTestId('plan-documents')).toHaveTextContent('1 document with 30 requirements')
    const skipped = within(dialog).getByTestId('plan-skipped')
    expect(skipped).toHaveTextContent('2 documents are skipped:')
    expect(skipped).toHaveTextContent('ABC stories: Already published.')
    expect(skipped).toHaveTextContent('Billing_BRD.docx: Analyse the document first.')
    await userEvent.click(within(dialog).getByTestId('publish-confirm'))
    await waitFor(() => expect(posts(calls, PUBLISH)).toHaveLength(1))
    expect(JSON.parse(posts(calls, PUBLISH)[0]!.body!)).toEqual({ document_ids: [1] })
    await waitFor(() => expect(screen.getByTestId('publish-selected')).toHaveTextContent('Publish selected (0)'))
  })

  it('the whole sprint is sent as the sprint, not as a list', async () => {
    const { calls } = mockApi(answering(PUBLISH, result({ skipped: [{ document_id: 2, name: 'Billing_BRD.docx', reason: 'not_analyzed', message: 'Analyse the document first.' }] })))
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByTestId('publish-whole-sprint'))
    const dialog = screen.getByRole('dialog', { name: 'Publish the whole sprint?' })
    expect(within(dialog).getByTestId('plan-documents')).toHaveTextContent('1 document with 30 requirements')
    await userEvent.click(within(dialog).getByTestId('publish-confirm'))
    await waitFor(() => expect(posts(calls, PUBLISH)).toHaveLength(1))
    expect(JSON.parse(posts(calls, PUBLISH)[0]!.body!)).toEqual({ sprint_id: 1 })
    expect(await screen.findByText('1 document published. 1 skipped.')).toBeInTheDocument()
  })

  it('has nothing to publish: the confirm button says so and is off', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/sprints/1/summary' ? json({ ...fx.sprintSummary, rows: [fx.sprintSummary.rows[1]!] }) : undefined))
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByTestId('publish-whole-sprint'))
    expect(within(screen.getByRole('dialog')).getByTestId('publish-confirm')).toBeDisabled()
    expect(within(screen.getByRole('dialog')).getByTestId('publish-confirm')).toHaveTextContent('Nothing to publish')
  })

  it('says so when sharing did not finish, or has no connection yet, and that the publish itself happened', async () => {
    for (const [state, text] of [['retrying', 'Sharing did not finish'], ['not_configured', 'Sharing starts when the connection is set up']] as const) {
      mockApi(answering(PUBLISH, result({ sync: { state, error: 'x' } })))
      const view = renderApp(PAGE)
      await ready()
      await userEvent.click(within(row(SRS)).getByTestId('row-publish'))
      await userEvent.click(screen.getByTestId('publish-confirm'))
      expect(await screen.findByText('1 document published.')).toBeInTheDocument()
      expect(await screen.findByText(new RegExp(text))).toBeInTheDocument()
      view.unmount()
      vi.unstubAllGlobals()
    }
  })

  it('shows the refusal of the service in a toast and closes the question', async () => {
    mockApi((c) => (c.method === 'POST' && c.url.pathname === PUBLISH ? json({ error: { code: 'project_not_found', message: 'Project 1 does not exist.' } }, 404) : undefined))
    renderApp(PAGE)
    await ready()
    await userEvent.click(within(row(SRS)).getByTestId('row-publish'))
    await userEvent.click(screen.getByTestId('publish-confirm'))
    expect(await screen.findByText('Could not change the publish state: Project 1 does not exist.')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('reloads the sprint, the documents and the overview after a publish', async () => {
    const { calls } = mockApi(answering(PUBLISH, result()))
    renderApp(PAGE)
    await ready()
    const before = calls.filter((c) => c.url.pathname === '/api/projects/1/sprints/1/summary').length
    await userEvent.click(within(row(SRS)).getByTestId('row-publish'))
    await userEvent.click(screen.getByTestId('publish-confirm'))
    await waitFor(() => expect(calls.filter((c) => c.url.pathname === '/api/projects/1/sprints/1/summary').length).toBeGreaterThan(before))
  })
})

describe('Publish page: unpublishing', () => {
  it('a published document offers Unpublish, which takes just that document back', async () => {
    const { calls } = mockApi(answering(UNPUBLISH, result({ action: 'unpublish', changed: [{ document_id: 3, name: 'ABC stories' }], published_documents: 0 })))
    renderApp(PAGE)
    await ready()
    const published = row('ABC stories')
    expect(within(published).queryByTestId('row-publish')).toBeNull()
    await userEvent.click(within(published).getByTestId('row-unpublish'))
    await waitFor(() => expect(posts(calls, UNPUBLISH)).toHaveLength(1))
    expect(JSON.parse(posts(calls, UNPUBLISH)[0]!.body!)).toEqual({ document_ids: [3] })
    expect(await screen.findByText('1 document taken back.')).toBeInTheDocument()
    expect(posts(calls, PUBLISH)).toHaveLength(0)
  })

  it('syncing and will-retry states are shown in words', async () => {
    const withState = (publish_state: 'syncing' | 'sync_error'): Handler => (c) =>
      c.url.pathname === '/api/projects/1/sprints/1/summary' ? json({ ...fx.sprintSummary, rows: fx.sprintSummary.rows.map((r) => (r.document_id === 3 ? { ...r, publish_state } : r)) }) : undefined
    for (const [state, text] of [['syncing', 'Syncing'], ['sync_error', 'Will retry']] as const) {
      mockApi(withState(state))
      const view = renderApp(PAGE)
      await ready()
      expect(within(row('ABC stories')).getByTestId('publish-state')).toHaveTextContent(text)
      expect(within(row('ABC stories')).getByTestId('row-unpublish')).toBeInTheDocument() // still published: it can be taken back
      view.unmount()
      vi.unstubAllGlobals()
    }
  })
})

describe('Overview: the share stage', () => {
  it('says how many documents are published', async () => {
    mockApi()
    renderApp('/requirement')
    const stage = (await screen.findAllByTestId('process-stage'))[4]!
    expect(within(stage).getByTestId('stage-detail')).toHaveTextContent('Published 1 of 2 documents')
  })
})
