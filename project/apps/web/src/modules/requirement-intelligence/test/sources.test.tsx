import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Source, Sprint } from '../api/types'
import { limits } from '../config'
import * as fx from './fixtures'
import { json, mockApi, renderApp, type Handler } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

const PAGE = '/requirement/sources'
const SRS = 'CoreBanking_SRS_v2.pdf'
const BRD = 'Payments_BRD.docx'
/** One analysed document in one sprint, and one that still needs the analysis (both in Sprint 1, so both are visible at once). */
const single: Source = { ...fx.source, sprints: [{ sprint_id: 1, count: 42 }] }
const pendingDoc: Source = { ...fx.source2, id: 2, filename: BRD, default_sprint_id: 1 }
const emptySummary = { ...fx.summary, requirements: 0, ambiguities: { count: 0, high_risk: 0, asked_by_ai: 0 }, conflicts: 0, duplicates: 0, task_drafts: { ...fx.summary.task_drafts, generated: 0, total: 0 }, open_findings: 0 }
const finishedJob = { ...fx.job, stage: 'share' as const, generation: { total: 42, done: 42, failed: 0, queued: 0, running: 0 } }
const runningJob = { ...fx.job, stage: 'improve' as const }
const analyzeUrl = '/api/projects/1/analyze'
const posts = (calls: { method: string; url: URL }[], path = analyzeUrl) => calls.filter((c) => c.method === 'POST' && c.url.pathname === path)
const dropped = () => new Response(null, { status: 204 })

/** Serve a fixed list of documents, then whatever `more` answers. */
const docs = (list: Source[], more?: Handler): Handler => (c) => {
  if (c.url.pathname === '/api/projects/1/sources' && c.method === 'GET') return json(list)
  return more?.(c)
}
const ready = () => screen.findByText(SRS)
/** One sprint is shown at a time (the current one first): this shows another. */
const view = async (key: string) => userEvent.selectOptions(await screen.findByTestId('sprint-view'), key)
/** The analysis asks which drafts to write first: this answers (with the remembered choice unless one is given). */
const confirmAnalyse = async (policy?: 'smart' | 'all' | 'manual') => {
  if (policy) await userEvent.click(screen.getByTestId(`policy-${policy}`))
  await userEvent.click(screen.getByTestId('analyse-confirm'))
}

describe('documents grouped by sprint', () => {
  it('shows one sprint at a time, the current one first, with a chooser that lists every sprint and its documents; no phase anywhere', async () => {
    mockApi(docs([single, { ...pendingDoc, default_sprint_id: 3 }], (c) => (c.url.pathname === '/api/projects/1/sprints' ? json([{ ...fx.sprints[1]!, position: 1 }, { ...fx.sprints[0]!, position: 2 }, fx.sprints[2]!]) : undefined)))
    renderApp(PAGE)
    await ready()
    const groups = screen.getAllByTestId('sprint-group')
    expect(groups.map((g) => g.getAttribute('aria-label'))).toEqual(['Sprint 1']) // the current sprint only
    expect(groups[0]).toHaveAttribute('data-current', 'true')
    expect(within(groups[0]!).getByText('Current')).toBeInTheDocument()
    expect(screen.queryByText(BRD)).toBeNull() // Sprint 3's document is not shown here
    const chooser = screen.getByTestId('sprint-view') as HTMLSelectElement
    expect([...chooser.options].map((o) => o.textContent)).toEqual(['Sprint 1 (current) · 1 document', 'Sprint 2 · 0 documents', 'Sprint 3 · 1 document'])
    expect(chooser).toHaveValue('sprint-1')
    expect(screen.queryByText(/phase/i)).toBeNull()
    expect(screen.queryByText('Unassigned')).toBeNull() // only when a document has no sprint
    expect(within(groups[0]!).getByText(SRS)).toBeInTheDocument()
    await view('sprint-3')
    expect(screen.getAllByTestId('sprint-group').map((g) => g.getAttribute('aria-label'))).toEqual(['Sprint 3'])
    expect(screen.getByText(BRD)).toBeInTheDocument()
    expect(screen.queryByText(SRS)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Show or hide Sprint 3' }))
    expect(screen.queryByText(BRD)).toBeNull()
  })

  it('sprints that an earlier Jira import made are not in the chooser or in any sprint list on this page', async () => {
    const imported = { ...fx.sprints[1]!, id: 9, name: 'SCRUM Sprint 1', origin: 'jira' as const, external_id: '10', is_current: false, position: 9 }
    mockApi(docs([single], (c) => (c.url.pathname === '/api/projects/1/sprints' && c.method === 'GET' ? json([...fx.sprints, imported]) : undefined)))
    renderApp(PAGE)
    await ready()
    const chooser = screen.getByTestId('sprint-view') as HTMLSelectElement
    expect([...chooser.options].map((o) => o.textContent)).toEqual(['Sprint 1 (current) · 1 document', 'Sprint 2 · 0 documents', 'Sprint 3 · 0 documents'])
    await userEvent.click(screen.getByRole('button', { name: `Move ${SRS} to a sprint` }))
    const move = within(screen.getByRole('dialog')).getByTestId('move-sprint') as HTMLSelectElement
    expect([...move.options].map((o) => o.textContent)).not.toContain('SCRUM Sprint 1')
  })

  it('Edit sprint details opens the dialog of the sprint on screen, and saves its name, dates and goal', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'PATCH' && c.url.pathname === '/api/projects/1/sprints/1' ? json({ ...fx.sprints[0]!, name: 'Sprint One' }) : undefined)))
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByTestId('edit-sprint'))
    const dialog = screen.getByRole('dialog', { name: 'Edit Sprint 1' })
    expect(within(dialog).getByLabelText('Name')).toHaveValue('Sprint 1')
    expect(within(dialog).getByLabelText('Goal')).toHaveValue('Sign-in and accounts')
    await userEvent.clear(within(dialog).getByLabelText('Name'))
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Sprint One')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save sprint' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH' && c.url.pathname === '/api/projects/1/sprints/1')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PATCH')!.body!)).toMatchObject({ name: 'Sprint One' })
  })

  it('Edit sprint details follows the sprint chosen in the chooser and is not offered for Unassigned', async () => {
    mockApi(docs([single, { ...pendingDoc, default_sprint_id: null }]))
    renderApp(PAGE)
    await ready()
    await view('sprint-2')
    await userEvent.click(screen.getByTestId('edit-sprint'))
    expect(screen.getByRole('dialog', { name: 'Edit Sprint 2' })).toBeInTheDocument()
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))
    await view('unassigned')
    expect(screen.queryByTestId('edit-sprint')).toBeNull()
  })

  it('the sprints that have no documents are not on the page until they are chosen', async () => {
    mockApi(docs([single]))
    renderApp(PAGE)
    await ready()
    expect(screen.getAllByTestId('sprint-group')).toHaveLength(1)
    expect(screen.queryAllByTestId('empty-sprint')).toHaveLength(0)
    expect(screen.queryByTestId('toggle-empty-sprints')).toBeNull()
    await view('sprint-2')
    expect(screen.getAllByTestId('sprint-group')).toHaveLength(1)
    expect(screen.getByTestId('empty-sprint')).toBeInTheDocument()
  })

  it('an empty sprint says "No documents yet" and offers Upload here', async () => {
    mockApi(docs([single]))
    renderApp(PAGE)
    await ready()
    await view('sprint-2')
    const empty = screen.getAllByTestId('empty-sprint')
    expect(empty).toHaveLength(1)
    expect(empty[0]).toHaveTextContent('No documents yet')
    expect(within(empty[0]!).getByRole('button', { name: 'Upload documents to Sprint 2' })).toHaveTextContent('Upload here')
  })

  it('a document that spans several sprints is listed under each with that sprint’s count', async () => {
    mockApi(docs([fx.source]))
    renderApp(PAGE)
    const first = await screen.findByTestId('source-card')
    expect(first).toHaveTextContent('30 requirements here (42 in all)')
    await view('sprint-2')
    expect(screen.getByTestId('source-card')).toHaveTextContent('12 requirements here (42 in all)')
    for (const card of screen.getAllByTestId('source-card')) {
      const chips = within(card).getAllByTestId('sprint-chip').map((c) => c.textContent)
      expect(chips).toEqual(['Sprint 1 · 30', 'Sprint 2 · 12'])
    }
  })

  it('documents without a sprint come last, under Unassigned, without an Upload here', async () => {
    mockApi(docs([single, { ...pendingDoc, default_sprint_id: null }]))
    renderApp(PAGE)
    await ready()
    await view('unassigned')
    const groups = screen.getAllByTestId('sprint-group')
    expect(groups.at(-1)).toHaveAttribute('aria-label', 'Unassigned')
    expect(await within(groups.at(-1)!).findByText(BRD)).toBeInTheDocument()
    expect(within(groups.at(-1)!).queryByRole('button', { name: /Upload documents to/ })).toBeNull()
  })

  it('a document card shows what it is, how far it is, what it holds and where it sits', async () => {
    mockApi(docs([single, pendingDoc]))
    renderApp(PAGE)
    await ready()
    const [analysed, waiting] = screen.getAllByTestId('source-card')
    expect(analysed).toHaveTextContent(SRS)
    expect(analysed).toHaveTextContent('SRS')
    expect(within(analysed!).getByTestId('source-state')).toHaveTextContent('Analysed')
    expect(analysed).toHaveTextContent('12 p.')
    expect(analysed).toHaveTextContent('1 KB')
    expect(analysed).toHaveTextContent(`Uploaded ${new Date(single.uploaded_at).toLocaleDateString()}`)
    expect(within(analysed!).getByTestId('source-counts')).toHaveTextContent('42 requirements · 8 ambiguities · 29 drafts ready · 2 need clarification · 1 drafts failed')
    expect(within(analysed!).getByRole('button', { name: `Re-analyse ${SRS}` })).toBeInTheDocument()
    expect(within(waiting!).getByTestId('source-state')).toHaveTextContent('Needs analysis')
    expect(within(waiting!).queryByTestId('source-counts')).toBeNull()
    expect(within(waiting!).getByRole('button', { name: `Analyse ${BRD}` })).toBeInTheDocument()
    expect(within(waiting!).queryByRole('button', { name: /Re-analyse/ })).toBeNull()
  })

  it('shows every state badge: Analysed, Analysing, Needs analysis, Failed', async () => {
    const states = ['analyzed', 'analyzing', 'not_analyzed', 'failed'] as const
    const list = states.map((analysis_state, i) => ({ ...single, id: i + 1, filename: `doc${i}.pdf`, analysis_state }))
    mockApi(docs(list))
    renderApp(PAGE)
    await screen.findByText('doc0.pdf')
    expect(screen.getAllByTestId('source-state').map((s) => s.textContent?.trim())).toEqual(['Analysed', 'Analysing', 'Needs analysis', 'Failed'])
  })

  it('a detected sprint says so and can be confirmed', async () => {
    const detected: Sprint[] = fx.sprints.map((s) => (s.id === 2 ? { ...s, origin: 'detected' as const, confirmed: false } : s))
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/projects/1/sprints' && c.method === 'GET') return json(detected)
      if (c.url.pathname === '/api/projects/1/sprints/2' && c.method === 'PATCH') return json({ ...detected[1]!, confirmed: true })
      return docs([single])(c)
    })
    renderApp(PAGE)
    await ready()
    await view('sprint-2')
    const note = await screen.findByTestId('detected-sprint')
    expect(note).toHaveTextContent('Detected from document · Confirm')
    await userEvent.click(within(note).getByRole('button', { name: 'Confirm' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH' && c.url.pathname === '/api/projects/1/sprints/2')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PATCH')!.body!)).toEqual({ confirmed: true })
  })

  it('the Jira connection has its own row above the toolbar (tests/jira.test.tsx covers every state)', async () => {
    mockApi()
    renderApp(PAGE)
    const row = await screen.findByTestId('jira-row')
    const jira = await within(row).findByTestId('jira-connect')
    await waitFor(() => expect(jira).toBeEnabled())
    expect(screen.getByTestId('sources-card')).not.toContainElement(row)
    expect(row.compareDocumentPosition(screen.getByTestId('sources-card')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy() // the row comes first
    expect(screen.getByTestId('sources-card')).not.toHaveTextContent('Coming soon')
  })
})

describe('removing documents', () => {
  /** A stateful fake: DELETE changes the document list. */
  function sourceApi() {
    let list = [single, pendingDoc]
    return mockApi((c) => {
      const p = c.url.pathname
      if (c.method === 'DELETE' && p === '/api/projects/1/sources') {
        list = []
        return dropped()
      }
      const m = /^\/api\/projects\/1\/sources\/(\d+)$/.exec(p)
      if (c.method === 'DELETE' && m) {
        list = list.filter((s) => s.id !== Number(m[1]))
        return dropped()
      }
      if (p === '/api/projects/1/sources') return json(list)
      if (list.length === 0 && p === '/api/projects/1/summary') return json(emptySummary)
      return undefined
    })
  }

  it('lists the documents with their type, and asks in a dialog before removing one', async () => {
    const { calls } = sourceApi()
    renderApp(PAGE)
    await ready()
    const card = screen.getByTestId('sources-card')
    expect(card).toHaveTextContent('2 documents')
    expect(within(card).getByText('SRS')).toBeInTheDocument()
    expect(within(card).getByText('BRD')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: `Remove ${BRD}` }))
    const dialog = screen.getByRole('dialog', { name: `Remove ${BRD}?` })
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false) // nothing is sent before the confirmation
    await userEvent.click(within(dialog).getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url.pathname === '/api/projects/1/sources/2')).toBe(true))
    await waitFor(() => expect(screen.queryByText(BRD)).toBeNull())
    expect(await screen.findByText('Document removed together with its requirements and results.')).toBeInTheDocument()
    expect(screen.getByTestId('sources-card')).toHaveTextContent('1 document')
  })

  it('cancel keeps the document and sends nothing', async () => {
    const { calls } = sourceApi()
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByRole('button', { name: `Remove ${SRS}` }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('button', { name: `Remove ${SRS}` })).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
  })

  it('Clear all asks in a dialog first, then removes everything and shows the empty state', async () => {
    const { calls } = sourceApi()
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Clear all' }))
    const dialog = screen.getByRole('dialog', { name: 'Clear all documents?' })
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus()
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Clear all' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url.pathname === '/api/projects/1/sources')).toBe(true))
    expect(await screen.findByText(/No documents yet/)).toBeInTheDocument()
    expect(screen.getByTestId('sources-card')).toHaveTextContent('0 documents')
    expect(screen.getByTestId('analysis-badge')).toHaveTextContent('Not analysed yet')
    expect(screen.queryByRole('button', { name: 'Clear all' })).toBeNull()
  })

  it('Escape closes the dialog and sends nothing', async () => {
    const { calls } = sourceApi()
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Clear all' }))
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
  })

  it('shows the service message when it refuses (409) and keeps the document', async () => {
    mockApi(docs([single], (c) => (c.method === 'DELETE' ? json({ error: { code: 'project_busy', message: 'An analysis or draft generation is still running for this project.' } }, 409) : undefined)))
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByRole('button', { name: `Remove ${SRS}` }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove' }))
    expect(await screen.findByText(/Could not remove the document: An analysis or draft generation is still running/)).toBeInTheDocument()
    expect(screen.getByText(SRS)).toBeInTheDocument()
  })

  it('remove and Clear all are disabled with a tooltip while a job is running', async () => {
    mockApi(
      docs([single, pendingDoc], (c) => {
        if (c.method === 'POST' && c.url.pathname === analyzeUrl) return json(runningJob, 202)
        if (c.url.pathname === '/api/jobs/abc123') return json(runningJob)
        return undefined
      }),
    )
    renderApp(PAGE)
    await ready()
    expect(screen.getByRole('button', { name: `Remove ${SRS}` })).toBeEnabled()
    await userEvent.click(screen.getByTestId('analyse-pending'))
    await confirmAnalyse()
    await waitFor(() => expect(screen.getByRole('button', { name: `Remove ${SRS}` })).toBeDisabled())
    expect(screen.getByRole('button', { name: `Remove ${SRS}` })).toHaveAttribute('title', 'Wait for the running analysis or drafts to finish.')
    expect(screen.getByRole('button', { name: 'Clear all' })).toBeDisabled()
  })
})

describe('Analyse (only what is pending)', () => {
  it('the main button counts the documents that need the analysis and sends one request', async () => {
    const { calls } = mockApi(
      docs([single, pendingDoc, { ...pendingDoc, id: 3, filename: 'Failed.docx', analysis_state: 'failed' }], (c) => {
        if (c.method === 'POST' && c.url.pathname === analyzeUrl) return json(finishedJob, 202)
        if (c.url.pathname === '/api/jobs/abc123') return json(finishedJob)
        return undefined
      }),
    )
    renderApp(PAGE)
    await ready()
    const button = screen.getByTestId('analyse-pending')
    expect(button).toHaveTextContent('Analyse 2 documents') // a failed one counts again, an analysed one does not
    await userEvent.click(button)
    expect(posts(calls)).toHaveLength(0) // it asks which drafts to write first
    expect(screen.getByRole('dialog', { name: 'Analyse 2 documents?' })).toBeInTheDocument()
    await confirmAnalyse()
    await waitFor(() => expect(posts(calls)).toHaveLength(1))
    expect(calls.some((c) => c.method === 'POST' && c.url.pathname.endsWith('/reanalyze'))).toBe(false)
  })

  it('is disabled at 0 and says why', async () => {
    mockApi(docs([single]))
    renderApp(PAGE)
    await ready()
    const button = screen.getByTestId('analyse-pending')
    expect(button).toHaveTextContent('Analyse 0 documents')
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', 'Every document is analysed.')
  })

  it('stays disabled until a document exists', async () => {
    mockApi(docs([]))
    renderApp(PAGE)
    await screen.findByText(/No documents yet/)
    expect(screen.getByTestId('analyse-pending')).toBeDisabled()
  })

  it('Analyse on one document asks which drafts to write, then sends the single-document request', async () => {
    const { calls } = mockApi(
      docs([single, pendingDoc], (c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/sources/2/reanalyze' ? json({ source_id: 2, kept: 0, changed: 0, removed: 0, added: 12, queued: 4, job: finishedJob }, 202) : undefined)),
    )
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByRole('button', { name: `Analyse ${BRD}` }))
    const dialog = screen.getByRole('dialog', { name: `Analyse ${BRD}?` })
    expect(within(dialog).getByTestId('policy-smart')).toBeChecked() // the remembered choice
    expect(dialog).toHaveTextContent('Which task drafts should be written after the analysis?')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
    await confirmAnalyse('all')
    await waitFor(() => expect(posts(calls, '/api/projects/1/sources/2/reanalyze')).toHaveLength(1))
    expect(posts(calls, '/api/projects/1/sources/2/reanalyze')[0]!.url.searchParams.get('policy')).toBe('all')
    expect(await screen.findByText(`${BRD} analysed.`)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(window.localStorage.getItem('requirement-intelligence.draftPolicy')).toBe('all') // remembered for next time
  })

  it('Re-analyse asks first: decisions on unchanged text are kept, changed or removed ones are archived', async () => {
    const { calls } = mockApi(
      docs([single], (c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/sources/1/reanalyze' ? json({ source_id: 1, kept: 40, changed: 2, removed: 1, added: 3, queued: 5, job: finishedJob }, 202) : undefined)),
    )
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByRole('button', { name: `Re-analyse ${SRS}` }))
    const dialog = screen.getByRole('dialog', { name: `Re-analyse ${SRS}?` })
    expect(dialog).toHaveTextContent('Decisions on requirements whose text has not changed are kept. Changed or removed requirements are archived')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: `Re-analyse ${SRS}` }))
    await confirmAnalyse()
    await waitFor(() => expect(posts(calls, '/api/projects/1/sources/1/reanalyze')).toHaveLength(1))
    expect(await screen.findByText('Re-analysis done: 40 kept, 2 changed, 1 removed, 3 new.')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('selected documents: tick some, Analyse selected (N) asks once and analyses each of them', async () => {
    const { calls } = mockApi(
      docs([single, pendingDoc, { ...pendingDoc, id: 3, filename: 'Third.docx' }], (c) => (c.method === 'POST' && c.url.pathname.endsWith('/reanalyze') ? json({ source_id: 0, kept: 0, changed: 0, removed: 0, added: 1, queued: 0, job: finishedJob }, 202) : undefined)),
    )
    renderApp(PAGE)
    await ready()
    expect(screen.queryByTestId('analyse-selected')).toBeNull()
    await userEvent.click(screen.getByRole('checkbox', { name: `Select ${BRD}` }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select Third.docx' }))
    expect(screen.getByTestId('docs-selected')).toHaveTextContent('2 selected')
    await userEvent.click(screen.getByTestId('analyse-selected'))
    expect(screen.getByRole('dialog', { name: 'Analyse 2 documents?' })).toBeInTheDocument()
    await confirmAnalyse('manual')
    await waitFor(() => expect(calls.filter((c) => c.method === 'POST' && c.url.pathname.endsWith('/reanalyze'))).toHaveLength(2))
    expect(calls.filter((c) => c.method === 'POST' && c.url.pathname.endsWith('/reanalyze')).map((c) => c.url.pathname)).toEqual(['/api/projects/1/sources/2/reanalyze', '/api/projects/1/sources/3/reanalyze'])
    expect(calls.filter((c) => c.method === 'POST' && c.url.pathname.endsWith('/reanalyze')).every((c) => c.url.searchParams.get('policy') === 'manual')).toBe(true)
    await waitFor(() => expect(screen.queryByTestId('docs-selected')).toBeNull()) // the selection is cleared when done
  })

  it('Select all shown takes the documents of the sprint on screen; Clear selection empties it', async () => {
    mockApi(docs([single, pendingDoc]))
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByTestId('select-docs'))
    expect(screen.getByTestId('docs-selected')).toHaveTextContent('2 selected')
    expect(screen.getByTestId('analyse-selected')).toHaveTextContent('Analyse selected (2)')
    await userEvent.click(screen.getByTestId('clear-docs'))
    expect(screen.queryByTestId('docs-selected')).toBeNull()
  })

  it('sends the request at once, shows Analysing… with elapsed time, disables the button, then finishes', async () => {
    let release!: (r: Response) => void
    const pending = new Promise<Response>((resolve) => (release = resolve))
    const { calls } = mockApi(
      docs([single, pendingDoc], (c) => {
        if (c.method === 'POST' && c.url.pathname === analyzeUrl) return pending
        if (c.url.pathname === '/api/jobs/abc123') return json(finishedJob)
        return undefined
      }),
    )
    renderApp(PAGE)
    await ready()
    const button = screen.getByTestId('analyse-pending')
    await waitFor(() => expect(button).toBeEnabled())
    await userEvent.click(button)
    await confirmAnalyse()
    await waitFor(() => expect(posts(calls)).toHaveLength(1))
    const busy = screen.getByRole('button', { name: /Analysing…/ })
    expect(busy).toBeDisabled()
    expect(busy).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByTestId('analysis-badge')).toHaveTextContent('Analysing')
    const notice = screen.getByTestId('analyzing-notice')
    expect(notice).toHaveTextContent('Analysing… 0:00 elapsed')
    expect(notice).toHaveTextContent('The first run is slower')
    await userEvent.click(busy) // a second click does nothing
    expect(posts(calls)).toHaveLength(1)
    release(json(finishedJob, 202))
    await waitFor(() => expect(screen.queryByTestId('analyzing-notice')).toBeNull())
    await waitFor(() => expect(screen.getByTestId('analysis-badge')).toHaveTextContent('Analysis complete'))
  })

  it('shows an inline error (not only a toast) when the request fails, and can try again', async () => {
    let attempts = 0
    const { calls } = mockApi(
      docs([single, pendingDoc], (c) => {
        if (c.method === 'POST' && c.url.pathname === analyzeUrl) {
          attempts += 1
          return attempts === 1 ? json({ error: { code: 'models_missing', message: 'Saved model missing: fr_nfr_fr_nfr_emb_lr.joblib' } }, 503) : json(finishedJob, 202)
        }
        if (c.url.pathname === '/api/jobs/abc123') return json(finishedJob)
        return undefined
      }),
    )
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByTestId('analyse-pending'))
    await confirmAnalyse()
    const inline = await screen.findByTestId('analyze-error')
    expect(inline).toHaveTextContent('The analysis did not finish.')
    expect(inline).toHaveTextContent('Saved model missing: fr_nfr_fr_nfr_emb_lr.joblib')
    expect(screen.getByTestId('analyse-pending')).toBeEnabled()
    await userEvent.click(within(inline).getByRole('button', { name: /Try again/ }))
    await waitFor(() => expect(screen.queryByTestId('analyze-error')).toBeNull())
    expect(posts(calls)).toHaveLength(2)
  })

  it('shows an inline error when the request times out', async () => {
    const before = limits.analyzeTimeoutMs
    limits.analyzeTimeoutMs = 80
    try {
      mockApi(
        docs([single, pendingDoc], (c) =>
          c.method === 'POST' && c.url.pathname === analyzeUrl ? new Promise<Response>((_resolve, reject) => c.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))) : undefined,
        ),
      )
      renderApp(PAGE)
      await ready()
      await userEvent.click(screen.getByTestId('analyse-pending'))
      await confirmAnalyse()
      const inline = await screen.findByTestId('analyze-error')
      expect(inline).toHaveTextContent('did not answer within')
      expect(screen.queryByTestId('analyzing-notice')).toBeNull()
      expect(screen.getByTestId('analyse-pending')).toBeEnabled()
    } finally {
      limits.analyzeTimeoutMs = before
    }
  })
})

describe('Upload dialog', () => {
  const sourcesUrl = '/api/projects/1/sources'
  const stored = (r: object = {}) => json({ accepted: [pendingDoc], rejected: [], sprint_detected: false, detected: [], ...r }, 201)
  const post = (calls: { method: string; url: URL }[]) => calls.find((c) => c.method === 'POST' && c.url.pathname === sourcesUrl) as { form?: FormData } | undefined
  async function open() {
    await ready()
    await userEvent.click(screen.getByTestId('upload-button'))
    return screen.getByRole('dialog', { name: 'Upload documents' })
  }
  const choose = (file: File) => fireEvent.change(screen.getByTestId('file-input'), { target: { files: [file] } })

  it('offers SRS, BRD and Enter manually, lists Jira as disabled (it comes from the import); the sprint can be left to Automatic', async () => {
    mockApi(docs([single]))
    renderApp(PAGE)
    await open()
    const type = screen.getByTestId('source-type-select') as HTMLSelectElement
    expect([...type.options].map((o) => [o.value, o.textContent, o.disabled])).toEqual([
      ['srs', 'SRS', false],
      ['brd', 'BRD', false],
      ['manual', 'Enter manually', false],
      ['jira', 'Jira (use Import from Jira)', true],
    ])
    expect(screen.queryByTestId('upload-phase')).toBeNull()
    const sprint = screen.getByTestId('upload-sprint') as HTMLSelectElement
    expect([...sprint.options].map((o) => o.textContent)).toEqual(['Automatic', 'Sprint 1', 'Sprint 2', 'Sprint 3', 'New sprint…'])
    expect(sprint).toHaveValue('')
    expect(screen.getByRole('dialog')).toHaveTextContent('Uses the sprint named in the file, otherwise the current sprint.')
  })

  it('sends the files with the document type and no sprint when it is Automatic', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === sourcesUrl ? stored() : undefined)))
    renderApp(PAGE)
    await open()
    await userEvent.selectOptions(screen.getByTestId('source-type-select'), 'brd')
    choose(new File(['x'], 'brd.txt'))
    expect(screen.getByTestId('chosen-files')).toHaveTextContent('brd.txt')
    await userEvent.click(screen.getByTestId('upload-submit'))
    expect(await screen.findByText(/1 file added/)).toBeInTheDocument()
    const form = post(calls)!.form!
    expect(form.get('source_type')).toBe('brd')
    expect((form.get('files') as File).name).toBe('brd.txt')
    expect(form.has('sprint_id')).toBe(false)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('sends the chosen sprint', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === sourcesUrl ? stored() : undefined)))
    renderApp(PAGE)
    await open()
    choose(new File(['x'], 'a.txt'))
    await userEvent.selectOptions(screen.getByTestId('upload-sprint'), '2')
    await userEvent.click(screen.getByTestId('upload-submit'))
    await screen.findByText(/1 file added/)
    expect(post(calls)!.form!.get('sprint_id')).toBe('2')
    expect(post(calls)!.form!.has('phase_id')).toBe(false)
  })

  it('Upload here opens the dialog with that sprint chosen, and the files go to it', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === sourcesUrl ? stored() : undefined)))
    renderApp(PAGE)
    await ready()
    await view('sprint-3')
    await userEvent.click(screen.getByRole('button', { name: 'Upload documents to Sprint 3' }))
    expect(screen.getByTestId('upload-sprint')).toHaveValue('3')
    choose(new File(['x'], 'a.txt'))
    await userEvent.click(screen.getByTestId('upload-submit'))
    await screen.findByText(/1 file added/)
    expect(post(calls)!.form!.get('sprint_id')).toBe('3')
  })

  it('the Upload button of the toolbar leaves the sprint on Automatic', async () => {
    mockApi(docs([single]))
    renderApp(PAGE)
    await open()
    expect(screen.getByTestId('upload-sprint')).toHaveValue('')
  })

  it('a new sprint is created first, then the files go to it', async () => {
    const { calls } = mockApi(
      docs([single], (c) => {
        if (c.method === 'POST' && c.url.pathname === '/api/projects/1/sprints') return json({ ...fx.sprints[1]!, id: 10, name: 'Sprint 4', phase_id: null }, 201)
        if (c.method === 'POST' && c.url.pathname === sourcesUrl) return stored()
        return undefined
      }),
    )
    renderApp(PAGE)
    await open()
    choose(new File(['x'], 'a.txt'))
    await userEvent.selectOptions(screen.getByTestId('upload-sprint'), '__new')
    await userEvent.type(screen.getByLabelText('New sprint name'), 'Sprint 4')
    await userEvent.click(screen.getByTestId('upload-submit'))
    await screen.findByText(/1 file added/)
    const order = calls.filter((c) => c.method === 'POST').map((c) => c.url.pathname)
    expect(order.slice(0, 2)).toEqual(['/api/projects/1/sprints', sourcesUrl])
    expect(JSON.parse(calls.find((c) => c.url.pathname === '/api/projects/1/sprints' && c.method === 'POST')!.body!)).toEqual({ name: 'Sprint 4' })
    expect(post(calls)!.form!.get('sprint_id')).toBe('10')
  })

  it('asks for a file or a name before anything is sent', async () => {
    const { calls } = mockApi(docs([single]))
    renderApp(PAGE)
    await open()
    await userEvent.click(screen.getByTestId('upload-submit'))
    expect(screen.getByRole('alert')).toHaveTextContent('Choose at least one file.')
    choose(new File(['x'], 'a.txt'))
    await userEvent.selectOptions(screen.getByTestId('upload-sprint'), '__new')
    await userEvent.click(screen.getByTestId('upload-submit'))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a name.')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('Enter manually shows a text box instead of the file button; the typed requirements are added as a manual-entry document', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === sourcesUrl ? stored({ accepted: [{ ...pendingDoc, filename: 'Manual entry.txt', source_type: 'other' }] }) : undefined)))
    renderApp(PAGE)
    await open()
    expect(screen.queryByTestId('manual-entry')).toBeNull()
    await userEvent.selectOptions(screen.getByTestId('source-type-select'), 'manual')
    expect(screen.getByTestId('manual-entry')).toBeInTheDocument()
    expect(screen.queryByTestId('file-input')).toBeNull()
    await userEvent.click(screen.getByTestId('upload-submit'))
    expect(screen.getByRole('alert')).toHaveTextContent('Type at least one requirement first.')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
    await userEvent.type(screen.getByLabelText('Requirements'), 'The system shall lock an account after 5 failed logins.')
    await userEvent.click(screen.getByTestId('upload-submit'))
    expect(await screen.findByText(/1 file added/)).toBeInTheDocument()
    const form = post(calls)!.form!
    expect(form.get('source_type')).toBe('other')
    const file = form.get('files') as File
    expect(file.name).toMatch(/^Manual entry .*\.txt$/)
    expect(await file.text()).toBe('The system shall lock an account after 5 failed logins.\n')
  })

  it('checks the file type and size in the browser and shows a message, without calling the service', async () => {
    const { calls } = mockApi(docs([single]))
    renderApp(PAGE)
    await open()
    choose(new File(['x'], 'virus.exe'))
    expect(await screen.findByText(/virus\.exe: file type \.exe is not allowed/)).toBeInTheDocument()
    const big = new File(['x'], 'big.txt')
    Object.defineProperty(big, 'size', { value: 21 * 1024 * 1024 })
    choose(big)
    expect(await screen.findByText(/big\.txt: larger than the 20 MB limit/)).toBeInTheDocument()
    expect(screen.getByTestId('chosen-files')).toHaveTextContent('No files chosen yet.')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('shows the service message for a file it rejects, and says when a sprint was found in the document', async () => {
    mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === sourcesUrl ? stored({ accepted: [], rejected: [{ filename: 'a.txt', code: 'empty_file', message: 'a.txt: the file is empty.' }] }) : undefined)))
    const first = renderApp(PAGE)
    await open()
    choose(new File([''], 'a.txt'))
    await userEvent.click(screen.getByTestId('upload-submit'))
    expect(await screen.findByText('a.txt: the file is empty.')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument() // nothing was stored: the dialog stays
    first.unmount()
    vi.unstubAllGlobals()
    mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === sourcesUrl ? stored({ sprint_detected: true, detected: [{ filename: 'Sprint_3.txt', sprint_id: 5, name: 'Sprint 3', confirmed: false }] }) : undefined)))
    renderApp(PAGE)
    await open()
    choose(new File(['x'], 'Sprint_3.txt'))
    await userEvent.click(screen.getByTestId('upload-submit'))
    expect(await screen.findByText(/Sprint found in the document: Sprint 3/)).toBeInTheDocument()
  })
})

describe('Move to sprint', () => {
  const open = async (name = SRS) => {
    await userEvent.click(await screen.findByRole('button', { name: `Move ${name} to a sprint` }))
    return screen.getByRole('dialog', { name: `Move ${name} to a sprint` })
  }

  it('moves the whole document', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'PUT' && c.url.pathname === '/api/projects/1/sources/1/sprint' ? json({ ...single, default_sprint_id: 2 }) : undefined)))
    renderApp(PAGE)
    await open()
    expect(screen.getByTestId('move-sprint')).toHaveValue('1')
    await userEvent.selectOptions(screen.getByTestId('move-sprint'), '2')
    await userEvent.click(screen.getByRole('button', { name: 'Move' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PUT')!.body!)).toEqual({ sprint_id: 2 })
    expect(await screen.findByText(`${SRS} now belongs to Sprint 2.`)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(calls.some((c) => c.url.pathname === '/api/projects/1/analyze' || c.url.pathname.endsWith('/reanalyze'))).toBe(false) // moving never analyses
  })

  it('gives page ranges to sprints', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/sources/1/assign-ranges' ? json({ assigned: 9, requirements: 42, without_page: 2 }) : undefined)))
    renderApp(PAGE)
    const dialog = await open()
    await userEvent.click(within(dialog).getByRole('radio', { name: 'Page ranges' }))
    fireEvent.change(within(dialog).getByLabelText('From page'), { target: { value: '1' } })
    fireEvent.change(within(dialog).getByLabelText('To page'), { target: { value: '5' } })
    await userEvent.selectOptions(within(dialog).getByLabelText('Sprint'), '2')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add a range' }))
    const rows = within(dialog).getByTestId('range-rows')
    expect(within(rows).getAllByLabelText('From page')).toHaveLength(2)
    await userEvent.click(within(rows).getAllByRole('button', { name: 'Remove range' })[1]!)
    expect(within(rows).getAllByLabelText('From page')).toHaveLength(1)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Move' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.pathname.endsWith('/assign-ranges'))).toBe(true))
    expect(JSON.parse(calls.find((c) => c.url.pathname.endsWith('/assign-ranges'))!.body!)).toEqual({ ranges: [{ from_page: 1, to_page: 5, sprint_id: 2 }] })
    expect(await screen.findByText('9 requirements moved. 2 without a page number stayed where they were.')).toBeInTheDocument()
  })

  it('refuses a range that ends before it starts, and sends nothing', async () => {
    const { calls } = mockApi(docs([single]))
    renderApp(PAGE)
    const dialog = await open()
    await userEvent.click(within(dialog).getByRole('radio', { name: 'Page ranges' }))
    fireEvent.change(within(dialog).getByLabelText('From page'), { target: { value: '5' } })
    fireEvent.change(within(dialog).getByLabelText('To page'), { target: { value: '2' } })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Move' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Each range needs a start page')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('page ranges are not offered for a document without page numbers', async () => {
    mockApi(docs([single, { ...pendingDoc, pages: null, analysis_state: 'analyzed' }]))
    renderApp(PAGE)
    const dialog = await open(BRD)
    expect(within(dialog).getByRole('radio', { name: 'Page ranges' })).toBeDisabled()
    expect(within(dialog).getByTestId('ranges-unavailable')).toHaveTextContent('no page numbers')
  })

  it('page ranges wait for the analysis', async () => {
    mockApi(docs([{ ...single, analysis_state: 'not_analyzed' }]))
    renderApp(PAGE)
    const dialog = await open()
    expect(within(dialog).getByRole('radio', { name: 'Page ranges' })).toBeDisabled()
    expect(within(dialog).getByTestId('ranges-unavailable')).toHaveTextContent('after the document is analysed')
  })
})

describe('sprints', () => {
  it('edits a sprint: name, dates and goal', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'PATCH' && c.url.pathname === '/api/projects/1/sprints/1' ? json({ ...fx.sprints[0]!, name: 'Login sprint' }) : undefined)))
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Edit Sprint 1' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit Sprint 1' })
    expect(within(dialog).getByLabelText('Name')).toHaveValue('Sprint 1')
    expect(within(dialog).getByLabelText('Start date')).toHaveValue('2026-10-05')
    expect(within(dialog).getByLabelText('Goal')).toHaveValue('Sign-in and accounts')
    await userEvent.clear(within(dialog).getByLabelText('Name'))
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Login sprint')
    expect(within(dialog).queryByLabelText('Phase')).toBeNull()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save sprint' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PATCH')!.body!)).toEqual({ name: 'Login sprint', start_date: '2026-10-05', end_date: '2026-10-16', goal: 'Sign-in and accounts' })
    expect(await screen.findByText('Sprint “Login sprint” saved.')).toBeInTheDocument()
  })

  it('refuses an empty name and an end date before the start date', async () => {
    const { calls } = mockApi(docs([single]))
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Edit Sprint 1' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('End date'), { target: { value: '2026-10-01' } })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save sprint' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('The end date must not be before the start date.')
    await userEvent.clear(within(dialog).getByLabelText('Name'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save sprint' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Enter a name.')
    expect(calls.some((c) => c.method === 'PATCH')).toBe(false)
  })

  it('makes a sprint current', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'PUT' && c.url.pathname === '/api/projects/1/current-sprint' ? json({ ...fx.sprints[1]!, is_current: true }) : undefined)))
    renderApp(PAGE)
    await ready()
    await view('sprint-2')
    await userEvent.click(screen.getByRole('button', { name: 'Edit Sprint 2' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Make current' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PUT')!.body!)).toEqual({ sprint_id: 2 })
  })

  it('deleting a sprint that holds requirements asks where they go', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'DELETE' && c.url.pathname === '/api/projects/1/sprints/2' ? json({ deleted: 2, reassigned_to: 1, requirements_moved: 12 }) : undefined)))
    renderApp(PAGE)
    await ready()
    await view('sprint-2')
    await userEvent.click(screen.getByRole('button', { name: 'Edit Sprint 2' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete sprint' }))
    const panel = within(dialog).getByTestId('delete-sprint')
    expect(panel).toHaveTextContent('Move its requirements and documents to')
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    expect(within(panel).getByTestId('reassign-select')).toHaveValue('1')
    await userEvent.click(within(panel).getByRole('button', { name: 'Delete sprint' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
    expect(calls.find((c) => c.method === 'DELETE')!.url.search).toBe('?reassign_to=1')
    expect(await screen.findByText('Sprint “Sprint 2” deleted.')).toBeInTheDocument()
  })

  it('Add to next sprint offers the next name, with dates and a goal', async () => {
    const { calls } = mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/sprints' ? json({ ...fx.sprints[2]!, id: 4, name: 'Sprint 4' }, 201) : undefined)))
    renderApp(PAGE)
    await ready()
    expect(screen.queryByRole('button', { name: 'Add phase' })).toBeNull()
    await userEvent.click(screen.getByTestId('add-next-sprint'))
    const dialog = screen.getByRole('dialog', { name: 'New sprint' })
    expect(within(dialog).getByLabelText('Name')).toHaveValue('Sprint 4')
    fireEvent.change(within(dialog).getByLabelText('Start date'), { target: { value: '2026-11-02' } })
    fireEvent.change(within(dialog).getByLabelText('End date'), { target: { value: '2026-11-13' } })
    await userEvent.type(within(dialog).getByLabelText('Goal'), 'Payments')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create sprint' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.pathname === '/api/projects/1/sprints')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'POST')!.body!)).toEqual({ name: 'Sprint 4', start_date: '2026-11-02', end_date: '2026-11-13', goal: 'Payments' })
    expect(await screen.findByText('Sprint “Sprint 4” created.')).toBeInTheDocument()
    // then it offers what to do with the new sprint
    const next = screen.getByRole('dialog', { name: 'Sprint 4 created' })
    expect(within(next).getByTestId('next-sprint-upload')).toHaveTextContent('Upload here')
    expect(within(next).getByTestId('next-sprint-move')).toHaveTextContent('Move documents to it')
  })

  it('after creating the next sprint, Upload here opens the upload with that sprint chosen', async () => {
    const created = { ...fx.sprints[2]!, id: 4, name: 'Sprint 4' }
    mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/sprints' ? json(created, 201) : c.url.pathname === '/api/projects/1/sprints' && c.method === 'GET' ? json([...fx.sprints, created]) : undefined)))
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByTestId('add-next-sprint'))
    await userEvent.click(within(screen.getByRole('dialog', { name: 'New sprint' })).getByRole('button', { name: 'Create sprint' }))
    await userEvent.click(await screen.findByTestId('next-sprint-upload'))
    expect(await screen.findByTestId('upload-sprint')).toHaveValue('4')
  })

  it('after creating the next sprint, Move documents to it sets the sprint of the chosen documents', async () => {
    const created = { ...fx.sprints[2]!, id: 4, name: 'Sprint 4' }
    const { calls } = mockApi(
      docs([single, pendingDoc], (c) => {
        if (c.method === 'POST' && c.url.pathname === '/api/projects/1/sprints') return json(created, 201)
        if (c.method === 'PUT' && c.url.pathname.endsWith('/sprint')) return json({ ...single, default_sprint_id: 4 })
        return undefined
      }),
    )
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByTestId('add-next-sprint'))
    await userEvent.click(within(screen.getByRole('dialog', { name: 'New sprint' })).getByRole('button', { name: 'Create sprint' }))
    await userEvent.click(await screen.findByTestId('next-sprint-move'))
    const dialog = screen.getByRole('dialog', { name: 'Move documents to Sprint 4' })
    expect(within(dialog).getByTestId('move-documents-confirm')).toBeDisabled()
    await userEvent.click(within(dialog).getByRole('checkbox', { name: BRD }))
    await userEvent.click(within(dialog).getByTestId('move-documents-confirm'))
    expect(await screen.findByText('1 document moved to Sprint 4.')).toBeInTheDocument()
    const puts = calls.filter((c) => c.method === 'PUT' && c.url.pathname.endsWith('/sprint'))
    expect(puts).toHaveLength(1)
    expect(puts[0]!.url.pathname).toBe('/api/projects/1/sources/2/sprint')
    expect(JSON.parse(puts[0]!.body!)).toEqual({ sprint_id: 4 })
  })

  it('leaving the follow-up with “Not now” keeps the new sprint and changes nothing else', async () => {
    const created = { ...fx.sprints[2]!, id: 4, name: 'Sprint 4' }
    const { calls } = mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/sprints' ? json(created, 201) : undefined)))
    renderApp(PAGE)
    await ready()
    await userEvent.click(screen.getByTestId('add-next-sprint'))
    await userEvent.click(within(screen.getByRole('dialog', { name: 'New sprint' })).getByRole('button', { name: 'Create sprint' }))
    await userEvent.click(await screen.findByTestId('next-sprint-done'))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(calls.filter((c) => c.method !== 'GET')).toHaveLength(1)
  })

  it('the new sprint is the one shown, and “Add to next sprint” sits below the sprint, not in the toolbar', async () => {
    const created = { ...fx.sprints[2]!, id: 4, name: 'Sprint 4' }
    mockApi(docs([single], (c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/sprints' ? json(created, 201) : c.url.pathname === '/api/projects/1/sprints' && c.method === 'GET' ? json([...fx.sprints, created]) : undefined)))
    renderApp(PAGE)
    await ready()
    const button = screen.getByTestId('add-next-sprint')
    const groups = screen.getByTestId('source-groups')
    expect(groups.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy() // below the sprint on screen
    await userEvent.click(button)
    await userEvent.click(within(screen.getByRole('dialog', { name: 'New sprint' })).getByRole('button', { name: 'Create sprint' }))
    await userEvent.click(await screen.findByTestId('next-sprint-done'))
    await waitFor(() => expect(screen.getByTestId('sprint-view')).toHaveValue('sprint-4'))
    expect(screen.getAllByTestId('sprint-group').map((g) => g.getAttribute('aria-label'))).toEqual(['Sprint 4'])
    expect(screen.getByTestId('empty-sprint')).toHaveTextContent('No documents yet')
  })

  it('the draft progress is on this page, with Pause, Resume and Retry failed (see drafts.test.tsx and retry.test.tsx)', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/summary' ? json({ ...fx.summary, task_drafts: { ...fx.summary.task_drafts, total: 40, generated: 20, not_generated: 15, in_progress: 5, queued: 5, failed: 2 } }) : undefined))
    renderApp(PAGE)
    expect(await screen.findByTestId('draft-progress')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Pause/ })).toBeInTheDocument()
    expect(screen.getByTestId('failed-banner')).toBeInTheDocument()
  })
})

describe('tabs', () => {
  it('Sources is the first tab; the Findings tab opens with the arrow keys and the address remembers it', async () => {
    mockApi()
    renderApp(PAGE)
    const sources = await screen.findByRole('tab', { name: 'Sources' })
    expect(sources).toHaveAttribute('aria-selected', 'true')
    sources.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Findings' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByRole('radiogroup', { name: 'Findings view' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Findings' })).toHaveFocus())
    expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', 'tab-findings')
  })
})
