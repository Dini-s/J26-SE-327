import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as fx from './fixtures'
import { json, mockApi, renderApp } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

const rowsShown = async () => (await screen.findAllByTestId('finding-row')).length
const emptyList = { total: 0, limit: 500, offset: 0, items: [] }
const emptyOverview = {
  ...fx.overview,
  counts: { ...fx.overview.counts, requirements: 0, ambiguities: { total: 0, detected: 0, asked_by_ai: 0 }, conflicts: 0, duplicates: 0, drafts: { ...fx.overview.counts.drafts, total: 0, done: 0, needs_clarification: 0, failed: 0, not_generated: 0 } },
  decisions: { accepted: 0, edited: 0, rejected: 0, pending: 0, decided: 0, percent_decided: 0 },
  sources: { count: 0, by_type: {}, total_size_bytes: 0, latest_upload_at: null },
  last_analysis_at: null,
}

// ------------------------------------------------------------------------------------------------------------ overview
describe('Overview', () => {
  it('shows the key numbers of the overview response', async () => {
    mockApi()
    renderApp()
    const card = (key: string) => screen.getByTestId(`kpi-${key}`)
    await waitFor(() => expect(within(card('requirements')).getByText('42')).toBeInTheDocument())
    expect(within(card('pending')).getByText('27')).toBeInTheDocument()
    expect(card('pending')).toHaveTextContent('Needs decision')
    expect(within(card('documents')).getByText('2')).toBeInTheDocument()
    expect(card('documents')).toHaveTextContent('SRS 1 · BRD 1')
    expect(card('analysis')).toHaveTextContent('1 of 2 ready')
  })

  it('each number links to the page where it is worked on', async () => {
    mockApi()
    renderApp()
    await screen.findByTestId('kpi-pending')
    expect(screen.getByTestId('kpi-requirements')).toHaveAttribute('href', '/requirement/review')
    expect(screen.getByTestId('kpi-pending')).toHaveAttribute('href', '/requirement/review')
    expect(screen.getByTestId('kpi-documents')).toHaveAttribute('href', '/requirement/sources')
    expect(screen.getByTestId('kpi-analysis')).toHaveAttribute('href', '/requirement/sources')
  })

  it('shows the requirement status as a ring with counts, percentages and the total in the middle', async () => {
    mockApi()
    renderApp()
    const card = await screen.findByTestId('decision-progress')
    expect(screen.getByTestId('percent-decided')).toHaveTextContent('35.7% decided')
    expect(within(card).getByTestId('donut-total')).toHaveTextContent('42')
    const parts = [...card.querySelectorAll('[data-segment]')].map((e) => [e.getAttribute('data-segment'), e.getAttribute('data-count')])
    expect(parts).toEqual([['accepted', '10'], ['edited', '4'], ['rejected', '1'], ['pending', '27']])
    const legend = within(card).getAllByTestId('donut-legend').map((l) => l.textContent)
    expect(legend).toEqual(['Accepted1023.8%', 'Edited49.5%', 'Rejected12.4%', 'Pending2764.3%'])
    expect(within(card).getByTestId('status-donut-text')).toHaveTextContent('42 requirements: Accepted 10 (23.8%); Edited 4 (9.5%); Rejected 1 (2.4%); Pending 27 (64.3%)')
    expect(card.querySelector('svg')!.closest('[aria-hidden="true"]')).not.toBeNull() // the picture is hidden from readers, the text above carries the numbers
    expect(screen.queryByRole('progressbar', { name: 'Requirement status' })).toBeNull()
  })

  it('a project without requirements says so instead of drawing a ring', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/overview' ? json({ ...fx.overview, counts: { ...fx.overview.counts, requirements: 0 }, decisions: { accepted: 0, edited: 0, rejected: 0, pending: 0, decided: 0, percent_decided: 0 } }) : undefined))
    renderApp()
    const card = await screen.findByTestId('decision-progress')
    expect(card).toHaveTextContent('No requirements yet.')
    expect(within(card).queryByTestId('status-donut')).toBeNull()
  })

  it('lists the latest uploads with type, sprint, state and requirement count', async () => {
    mockApi()
    renderApp()
    const card = await screen.findByTestId('latest-uploads')
    const items = within(card).getAllByTestId('latest-upload')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent('Billing_BRD.docx')
    expect(items[0]).toHaveTextContent('BRD')
    expect(within(items[0]!).getByTestId('latest-place')).toHaveTextContent(/^Sprint 3$/)
    expect(items[0]).toHaveTextContent('Needs analysis')
    expect(items[0]).toHaveTextContent('0 requirements')
    expect(within(items[1]!).getByTestId('latest-place')).toHaveTextContent(/^Sprint 1$/)
    expect(items[1]).toHaveTextContent('Analysed')
    expect(items[1]).toHaveTextContent('42 requirements')
    expect(within(card).getByRole('link', { name: /Manage sources/ })).toHaveAttribute('href', '/requirement/sources')
  })

  it('an empty project invites adding documents instead of showing an empty bar', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/overview' ? json(emptyOverview) : undefined))
    renderApp()
    const card = await screen.findByTestId('decision-progress')
    expect(card).toHaveTextContent('No requirements yet.')
    expect(within(card).getByRole('link', { name: /Add documents/ })).toHaveAttribute('href', '/requirement/sources')
    expect(within(card).queryByRole('progressbar')).toBeNull()
    expect(screen.getByTestId('sync-now')).toBeDisabled()
  })

  it('shows placeholders while loading and a retry when the overview fails', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/overview' ? json({ error: { code: 'internal_error', message: 'boom' } }, 500) : undefined))
    renderApp()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Could not load the overview: boom')
    expect(within(alert).getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('has a header with the page title, the project and the AI engine pill', async () => {
    mockApi()
    renderApp()
    expect(await screen.findByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('Core Banking Platform'))
    expect(screen.getByTestId('engine-pill')).toBeInTheDocument()
  })
})

// ------------------------------------------------------------------------------------------------------------ findings tab
describe('Findings', () => {
  const PATH = '/requirement/sources?tab=findings&view=ambiguities'
  const listCalls = (calls: { url: URL }[]) => calls.filter((c) => c.url.pathname === '/api/projects/1/requirements')

  it('starts with Ambiguities across the whole document and switches the view', async () => {
    const { calls } = mockApi()
    renderApp(PATH)
    expect(await screen.findByRole('radio', { name: 'Ambiguities' })).toBeChecked()
    expect(await rowsFound()).toBe(3)
    expect(listCalls(calls)[0]!.url.searchParams.get('type')).toBe('ambiguity')
    await userEvent.click(screen.getByRole('radio', { name: 'Duplicates' }))
    await waitFor(() => expect(listCalls(calls).some((c) => c.url.searchParams.get('type') === 'duplicate')).toBe(true))
    await userEvent.click(screen.getByRole('radio', { name: 'Conflicts' }))
    await waitFor(() => expect(listCalls(calls).some((c) => c.url.searchParams.get('type') === 'conflict')).toBe(true))
    expect(screen.getByRole('radio', { name: 'Conflicts' })).toBeChecked()
  })

  it('arrow keys move between the views', async () => {
    mockApi()
    renderApp(PATH)
    const first = await screen.findByRole('radio', { name: 'Ambiguities' })
    first.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('radio', { name: 'Duplicates' })).toBeChecked()
  })

  it('the Risk view lists the requirements by risk, highest first, and has no "NONE" filter', async () => {
    const items = [
      { ...fx.rows[2]!, uid: 'p1-REQ-009', id: 'REQ-009', risk_level: 'LOW' as const, risk_score: 1 },
      { ...fx.rows[0]!, risk_score: 4 },
      { ...fx.rows[2]!, uid: 'p1-REQ-010', id: 'REQ-010', risk_level: 'NONE' as const, risk_score: 0 },
      { ...fx.rows[2]!, risk_level: 'MEDIUM' as const, risk_score: 2 },
    ]
    const { calls } = mockApi((c) => (c.url.pathname === '/api/projects/1/requirements' ? json({ total: items.length, limit: 500, offset: 0, items }) : undefined))
    renderApp('/requirement/sources?tab=findings&view=risk')
    await screen.findAllByTestId('finding-item')
    expect(screen.getAllByTestId('finding-item').map((li) => li.querySelector('.font-bold')?.textContent)).toEqual(['REQ-001', 'REQ-003', 'REQ-009']) // REQ-010 has no risk
    expect(listCalls(calls)[0]!.url.searchParams.get('type')).toBeNull() // risk is across all types
    const risk = screen.getByLabelText('Risk level') as HTMLSelectElement
    expect([...risk.options].map((o) => o.value)).toEqual(['all', 'HIGH', 'MEDIUM', 'LOW'])
  })

  it('filters by risk level, search text (debounced) and document, and says so when nothing matches', async () => {
    const { calls } = mockApi((c) => (c.url.pathname === '/api/projects/1/requirements' && c.url.searchParams.get('q') === 'zzz' ? json(emptyList) : undefined))
    renderApp(PATH)
    await rowsFound()
    await userEvent.selectOptions(screen.getByLabelText('Risk level'), 'HIGH')
    await waitFor(() => expect(listCalls(calls).some((c) => c.url.searchParams.get('risk') === 'HIGH')).toBe(true))
    await userEvent.type(screen.getByRole('searchbox', { name: /Search requirements/ }), 'zzz')
    expect(await screen.findByTestId('empty-findings')).toHaveTextContent('No ambiguous requirements match these filters.')
    expect(listCalls(calls).some((c) => c.url.searchParams.get('q') === 'zz')).toBe(false) // typed fast: only the final text is sent
    await userEvent.selectOptions(screen.getByLabelText('Document'), 'CoreBanking_SRS_v2.pdf')
  })

  it('every finding links to the same requirement in the Review Queue', async () => {
    mockApi()
    renderApp(PATH)
    await rowsFound()
    const link = screen.getByRole('link', { name: 'Open REQ-002 in Review Queue' })
    expect(link).toHaveAttribute('href', '/requirement/review?uid=p1-REQ-002')
    await userEvent.click(link)
    expect(await screen.findByRole('heading', { level: 1, name: 'Review Queue' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('option', { name: /REQ-002/ })).toHaveAttribute('aria-selected', 'true'))
  })
})

const rowsFound = async () => (await screen.findAllByTestId('finding-item')).length

// ------------------------------------------------------------------------------------------------------------ review queue
describe('Review Queue list', () => {
  const REVIEW = '/requirement/review'

  it('rows show id, type, risk badge, text and the source reference', async () => {
    mockApi()
    renderApp(REVIEW)
    const rows = await screen.findAllByTestId('finding-row')
    expect(rows[0]).toHaveTextContent('REQ-001')
    expect(rows[0]).toHaveTextContent('Ambiguity')
    expect(rows[0]).toHaveTextContent('The system should quickly notify users about suspicious logins.')
    expect(rows[0]).toHaveTextContent('CoreBanking_SRS_v2.pdf · Page 12, paragraph 3')
    expect(within(rows[0]!).getByTestId('risk-badge')).toHaveTextContent('HIGH')
    expect(rows[1]).toHaveTextContent('Conflict')
    expect(rows[2]).toHaveTextContent('Duplicate')
  })

  it('lists the pending requirements first and keeps the document order inside each group', async () => {
    const items = [{ ...fx.rows[0]!, decision: 'accepted' as const }, fx.rows[1]!, { ...fx.rows[2]!, decision: 'rejected' as const }]
    mockApi((c) => (c.url.pathname === '/api/projects/1/requirements' ? json({ total: 3, limit: 500, offset: 0, items }) : undefined))
    renderApp(REVIEW)
    const rows = await screen.findAllByTestId('finding-row')
    expect(rows.map((r) => r.querySelector('.font-bold')?.textContent)).toEqual(['REQ-002', 'REQ-001', 'REQ-003'])
    expect(within(rows[1]!).getByTestId('row-decision')).toHaveTextContent('Accepted')
    expect(within(rows[0]!).queryByTestId('row-decision')).toBeNull()
  })

  it('has a button per decision status with the counts of the overview, and filters by it', async () => {
    const items = [{ ...fx.rows[0]!, decision: 'accepted' as const }, fx.rows[1]!, { ...fx.rows[2]!, decision: 'edited' as const }]
    mockApi((c) => (c.url.pathname === '/api/projects/1/requirements' ? json({ total: 3, limit: 500, offset: 0, items }) : undefined))
    renderApp(REVIEW)
    await rowsShown()
    await waitFor(() => expect(screen.getByTestId('status-pending')).toHaveTextContent('Pending (27)'))
    expect(screen.getByTestId('status-all')).toHaveTextContent('All (42)')
    expect(screen.getByTestId('status-accepted')).toHaveTextContent('Accepted (10)')
    expect(screen.getByTestId('status-edited')).toHaveTextContent('Edited (4)')
    expect(screen.getByTestId('status-rejected')).toHaveTextContent('Rejected (1)')
    expect(screen.getByTestId('status-all')).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByTestId('status-pending'))
    expect(screen.getAllByTestId('finding-row')).toHaveLength(1)
    expect(screen.getByTestId('finding-row')).toHaveTextContent('REQ-002')
    await userEvent.click(screen.getByTestId('status-edited'))
    expect(screen.getByTestId('finding-row')).toHaveTextContent('REQ-003')
    await userEvent.click(screen.getByTestId('status-rejected'))
    expect(screen.getByTestId('empty-list')).toHaveTextContent('No requirements match these filters.')
  })

  it('sends the search text (debounced), the risk level and the finding type to the service', async () => {
    const { calls } = mockApi()
    renderApp(REVIEW)
    await rowsShown()
    await userEvent.type(screen.getByRole('searchbox', { name: /Search requirements/ }), 'login')
    await waitFor(() => expect(calls.some((c) => c.url.searchParams.get('q') === 'login')).toBe(true))
    expect(calls.filter((c) => c.url.searchParams.get('q') === 'log')).toHaveLength(0)
    await userEvent.click(screen.getByTestId('filters-button'))
    await userEvent.selectOptions(screen.getByLabelText('Risk level'), 'HIGH')
    await waitFor(() => expect(calls.some((c) => c.url.searchParams.get('risk') === 'HIGH')).toBe(true))
    await userEvent.selectOptions(screen.getByLabelText('Finding type'), 'conflict')
    await waitFor(() => expect(calls.some((c) => c.url.searchParams.get('type') === 'conflict')).toBe(true))
  })

  it('says so when nothing matches, and invites adding documents when there are no requirements', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/requirements' ? json(emptyList) : undefined))
    renderApp(REVIEW)
    expect(await screen.findByTestId('empty-list')).toHaveTextContent('No requirements yet. Add documents and run the analysis in Sources & Findings.')
    await userEvent.click(screen.getByTestId('filters-button'))
    await userEvent.selectOptions(screen.getByLabelText('Risk level'), 'LOW')
    expect(await screen.findByText('No requirements match these filters.')).toBeInTheDocument()
    expect(screen.getByText('Select a requirement to see its analysis.')).toBeInTheDocument()
  })

  it('arrow keys move the selection (kept in the address) and the detail follows', async () => {
    const { calls } = mockApi()
    renderApp(REVIEW)
    await rowsShown()
    const list = screen.getByRole('listbox', { name: 'Requirements' })
    await waitFor(() => expect(within(list).getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'true'))
    list.focus()
    await userEvent.keyboard('{ArrowDown}')
    expect(within(list).getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true')
    await waitFor(() => expect(calls.some((c) => c.url.pathname === '/api/requirements/p1-REQ-002')).toBe(true))
    await userEvent.keyboard('{ArrowUp}{ArrowUp}')
    expect(within(list).getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'true')
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Requirement analysis' })).toHaveFocus())
  })

  it('opens the requirement named in the address', async () => {
    const { calls } = mockApi()
    renderApp('/requirement/review?uid=p1-REQ-003')
    await rowsShown()
    await waitFor(() => expect(calls.some((c) => c.url.pathname === '/api/requirements/p1-REQ-003')).toBe(true))
    expect(calls.some((c) => c.url.pathname === '/api/requirements/p1-REQ-001')).toBe(false)
  })
})

describe('Review Queue detail', () => {
  const REVIEW = '/requirement/review'

  it('shows the display id, risk, only whether it is functional or not, and highlights the weak word', async () => {
    mockApi()
    renderApp(REVIEW)
    const id = await screen.findByTestId('detail-id')
    expect(id).toHaveTextContent('REQ-001')
    expect(id).not.toHaveTextContent('p1-')
    expect(screen.getByTestId('detail-panel')).toHaveTextContent('HIGH RISK')
    expect(screen.getByTestId('requirement-kind')).toHaveTextContent(/^(Functional|Non-functional) requirement$/)
    expect(screen.queryByTestId('confidence')).toBeNull() // no confidence text any more
    expect(document.body).not.toHaveTextContent(/confidence/i)
    const marks = screen.getByTestId('original-text').querySelectorAll('mark')
    expect([...marks].map((m) => m.textContent)).toEqual(['quickly'])
    expect(screen.getByTestId('explanation-card')).toHaveTextContent('Ambiguity detected')
    expect(screen.getByTestId('flagged-unclear')).toHaveTextContent('Flagged as unclear · High')
    expect(screen.getByTestId('explanation-card')).toHaveTextContent('Vague words: quickly')
    // plain levels instead of numbers: no percentage, no "probability", no "model" in the analysis part
    for (const part of [screen.getByTestId('requirement-kind'), screen.getByTestId('explanation-card')]) {
      expect(part.textContent).not.toMatch(/%|probabilit|model/i)
      expect(part.textContent).not.toMatch(/\d\.\d/)
    }
  })

  const asking = () => mockApi((c) => (c.url.pathname === '/api/requirements/p1-REQ-001' ? json({ ...fx.detail, generation: { ...fx.generationDone, state: 'needs_clarification', clarification_questions: ['What does quickly mean?'] } }) : undefined))

  it('shows original text, issues, follow-up questions, the task draft and the decision card, and no history or boundary card', async () => {
    asking()
    renderApp(REVIEW)
    await screen.findByTestId('detail-panel')
    for (const label of ['Original requirement', 'Follow-up questions', 'Task draft', 'Your decision']) expect(screen.getByRole('region', { name: label })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Issues found' })).toBeNull() // the card is gone: a round icon on the requirement shows it
    expect(screen.getByTestId('issue-indicator')).toBeInTheDocument()
    expect(screen.queryByTestId('decision-history')).toBeNull()
    expect(screen.queryByText(/Component boundary/i)).toBeNull()
  })

  it('the follow-up questions appear only for a requirement that needs them', async () => {
    mockApi()
    renderApp(REVIEW)
    await screen.findByTestId('detail-panel')
    expect(screen.queryByTestId('followup-card')).toBeNull()
    expect(screen.queryByRole('region', { name: 'Follow-up questions' })).toBeNull()
  })

  it('the issue icon is shown only until the requirement is marked or edited', async () => {
    const decided = (decision: string) => mockApi((c) => (c.url.pathname === '/api/requirements/p1-REQ-001' ? json({ ...fx.detail, decision: { decision, edited_text: decision === 'edited' ? 'New text.' : null, note: null, decided_at: '2026-10-20T08:00:00+00:00' } }) : undefined))
    mockApi()
    const open = renderApp(REVIEW)
    expect(await screen.findByTestId('issue-indicator')).toBeInTheDocument()
    open.unmount()
    vi.unstubAllGlobals()
    for (const decision of ['accepted', 'rejected', 'edited']) {
      decided(decision)
      const view = renderApp(REVIEW)
      await screen.findByTestId('detail-panel')
      await waitFor(() => expect(screen.getByTestId('decision-card')).toHaveAttribute('data-status', decision))
      expect(screen.queryByTestId('issue-indicator'), decision).toBeNull()
      view.unmount()
      vi.unstubAllGlobals()
    }
  })

  it('the order is the requirement, the task draft, the follow-up questions, then the decision', async () => {
    asking()
    renderApp(REVIEW)
    await screen.findByTestId('detail-panel')
    const order = ['Original requirement', 'Task draft', 'Follow-up questions', 'Your decision'].map((name) => screen.getByRole('region', { name }))
    for (let i = 1; i < order.length; i++) expect(order[i - 1]!.compareDocumentPosition(order[i]!) & Node.DOCUMENT_POSITION_FOLLOWING, `${i}`).toBeTruthy()
  })

  describe('the round issue icon on the requirement', () => {
    const withDetail = (over: Record<string, unknown>) => mockApi((c) => (c.url.pathname === '/api/requirements/p1-REQ-001' ? json({ ...fx.detail, ...over }) : undefined))
    const noIssues = { findings: [], conflicts: [], duplicates: [], security: { ...fx.detail.security, is_security: false, cue_words: [] }, ambiguity: { ...fx.detail.ambiguity, label: 'ok', weak_words: [], weak_word_spans: [], probability_defect: 0.01 }, risk: { ...fx.detail.risk, level: 'NONE' } }

    it('is green when nothing was found', async () => {
      withDetail(noIssues)
      renderApp(REVIEW)
      const icon = await screen.findByTestId('issue-indicator')
      expect(icon).toHaveAttribute('data-level', 'ok')
      expect(within(icon).getByRole('button')).toHaveAccessibleName('Issues found: No finding')
      expect(screen.getByTestId('original-text').closest('section')).toContainElement(icon) // inside the requirement card
    })

    it('is yellow for something to look at (unclear wording) and red for a conflict or a high risk', async () => {
      withDetail({ ...noIssues, ambiguity: { ...fx.detail.ambiguity, label: 'defect' }, findings: [{ type: 'ambiguity', message: 'x' }] })
      const first = renderApp(REVIEW)
      expect(await screen.findByTestId('issue-indicator')).toHaveAttribute('data-level', 'warning')
      first.unmount()
      vi.unstubAllGlobals()
      withDetail({ ...noIssues, risk: { ...fx.detail.risk, level: 'HIGH' } })
      renderApp(REVIEW)
      await waitFor(() => expect(screen.getByTestId('issue-indicator')).toHaveAttribute('data-level', 'danger'))
    })

    it('a candidate conflict is red', async () => {
      const partner = { id: 'REQ-005', uid: 'p1-REQ-005', similarity: 0.91, text: 'Other text.', source_file: 'b.txt', page: null, paragraph: 2, reason: 'Contradicts.' }
      withDetail({ ...noIssues, conflicts: [partner] })
      renderApp(REVIEW)
      expect(await screen.findByTestId('issue-indicator')).toHaveAttribute('data-level', 'danger')
    })
  })

  it('shows both texts and the reason for a conflict candidate, and a duplicate partner with its similarity', async () => {
    const partner = { id: 'REQ-005', uid: 'p1-REQ-005', similarity: 0.91, text: 'The system shall not notify users about logins.', source_file: 'b.txt', page: null, paragraph: 2 }
    mockApi((c) =>
      c.url.pathname === '/api/requirements/p1-REQ-001'
        ? json({
            ...fx.detail,
            conflicts: [{ ...partner, reason: 'Candidate conflict, needs human decision: the second requirement prohibits an action.' }],
            duplicates: [{ ...partner, id: 'REQ-006', uid: 'p1-REQ-006', similarity: 0.9731 }],
          })
        : undefined,
    )
    renderApp(REVIEW)
    const conflict = await screen.findByTestId('conflict-partner')
    expect(conflict).toHaveTextContent('REQ-001 (this requirement)')
    expect(conflict).toHaveTextContent(partner.text)
    expect(conflict).toHaveTextContent('Candidate conflict, needs human decision')
    expect(screen.getByTestId('duplicate-partners')).toHaveTextContent('Similarity: High')
  })

  it('lists follow-up questions from the draft and does not invent a revision', async () => {
    mockApi((c) =>
      c.url.pathname === '/api/requirements/p1-REQ-001'
        ? json({ ...fx.detail, generation: { ...fx.generationDone, state: 'needs_clarification', clarification_questions: ['What does quickly mean in seconds?'] } })
        : undefined,
    )
    renderApp(REVIEW)
    const card = await screen.findByTestId('followup-card')
    await waitFor(() => expect(card).toHaveTextContent('What does quickly mean in seconds?'))
    expect(card).toHaveTextContent('AI-written')
    expect(screen.queryByText(/Suggested revision/i)).toBeNull()
    expect(screen.queryByRole('button', { name: /Accept revision/i })).toBeNull()
  })

  it('shows the AI badge in the header and the vague term highlighted with its legend', async () => {
    const text = 'The system should process payments quickly.'
    const g = { ...fx.generationDone, state: 'needs_clarification' as const, status: 'needs_clarification', clarification_questions: ['How quickly?'] }
    mockApi((c) =>
      c.url.pathname === '/api/requirements/p1-REQ-001'
        ? json({ ...fx.detail, text, original_text: text, ambiguity: { ...fx.detail.ambiguity, weak_words: [], weak_word_spans: [] }, vague_terms: [{ term: 'quickly', start: 35, end: 42 }], generation: g })
        : undefined,
    )
    renderApp(REVIEW)
    const panel = await screen.findByTestId('detail-panel')
    await waitFor(() => expect(within(panel).getByTestId('ai-clarify-badge')).toBeInTheDocument())
    const mark = within(screen.getByTestId('original-text')).getByText('quickly')
    expect(mark).toHaveAttribute('data-kind', 'vague')
    expect(within(panel).getByTestId('highlight-legend')).toHaveTextContent('Vague term (rule-based)')
  })

  it('regenerate calls the endpoint and the draft card moves to queued', async () => {
    let queued = false
    const { calls } = mockApi((c) => {
      if (c.method === 'POST' && c.url.pathname.endsWith('/generate')) {
        queued = true
        return json({ uid: 'p1-REQ-001', generation_state: 'queued' }, 202)
      }
      if (queued && c.url.pathname === '/api/requirements/p1-REQ-001') return json({ ...fx.detail, generation: { ...fx.generationDone, state: 'queued', status: null, user_story: '' } })
      return undefined
    })
    renderApp(REVIEW)
    await screen.findByTestId('draft-card')
    await userEvent.click(await screen.findByRole('button', { name: /Regenerate/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.pathname === '/api/requirements/p1-REQ-001/generate')).toBe(true))
    await waitFor(() => expect(screen.getByTestId('draft-card')).toHaveAttribute('data-state', 'queued'))
  })

  it('model server down: the rows stay, the draft card says AI engine unavailable with Retry, and the pill says unreachable', async () => {
    const down = { ...fx.generationDone, state: 'failed' as const, message: 'AI engine unavailable: could not get a reply: refused', status: null, user_story: '', technical_task: '', acceptance_criteria: [], rationale: '', backend: '', model: '' }
    mockApi((c) => {
      if (c.url.pathname === '/api/engine') return json({ ...fx.engine, device: { ...fx.engine.device, reachable: false } })
      if (c.url.pathname === '/api/requirements/p1-REQ-001') return json({ ...fx.detail, generation: down })
      return undefined
    })
    renderApp(REVIEW)
    expect(await screen.findAllByTestId('finding-row')).not.toHaveLength(0)
    const card = await screen.findByTestId('draft-card')
    expect(card).toHaveTextContent('AI engine unavailable.')
    expect(card.querySelector('.animate-spin')).toBeNull()
    expect(within(card).getByRole('button', { name: /Retry/ })).toBeEnabled()
    await waitFor(() => expect(screen.getByTestId('engine-pill')).toHaveAttribute('data-state', 'unreachable'))
  })
})

// ------------------------------------------------------------------------------------------------------------ page states
describe('page states', () => {
  it('shows the offline banner when the service cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    renderApp()
    const banner = await screen.findByTestId('offline-banner')
    expect(banner).toHaveTextContent('Cannot reach the requirement service at')
    expect(banner).not.toHaveTextContent(/Component 1|the API/)
    await waitFor(() => expect(screen.getByTestId('engine-pill')).toHaveAttribute('data-state', 'unreachable'))
  })

  it('a slow first health answer shows no error', async () => {
    mockApi((c) => (c.url.pathname === '/api/health' ? new Promise<Response>(() => undefined) : undefined))
    renderApp()
    expect(await screen.findByTestId('kpi-requirements')).toBeInTheDocument()
    expect(screen.queryByTestId('offline-banner')).toBeNull()
  })

  it('without an active project it says so instead of loading forever', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects' ? json([]) : undefined))
    renderApp()
    expect(await screen.findByTestId('no-project')).toHaveTextContent('There is no active project.')
  })

  it('has no sidebar of its own (the shell owns it)', async () => {
    mockApi()
    renderApp()
    await screen.findByTestId('kpi-requirements')
    expect(screen.queryByRole('navigation')).toBeNull()
  })
})
