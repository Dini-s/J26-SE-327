import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DecisionOut } from '../api/types'
import * as fx from './fixtures'
import { json, mockApi, renderApp } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
})

const rowsShown = async () => (await screen.findAllByTestId('finding-row')).length

describe('stat cards', () => {
  it('show the numbers of the summary response and nothing else', async () => {
    mockApi()
    renderApp()
    const card = (key: string) => screen.getByTestId(`stat-${key}`)
    await waitFor(() => expect(within(card('requirements')).getByText('42')).toBeInTheDocument())
    expect(within(card('requirements')).getByText('Source-linked')).toBeInTheDocument()
    expect(within(card('ambiguities')).getByText('8')).toBeInTheDocument()
    expect(within(card('ambiguities')).getByText('Part A · 3 high risk')).toBeInTheDocument()
    expect(within(card('conflicts')).getByText('2')).toBeInTheDocument()
    expect(within(card('conflicts')).getByText('Candidate, decision required')).toBeInTheDocument()
    expect(within(card('duplicates')).getByText('3')).toBeInTheDocument()
    expect(within(card('drafts')).getByText('29 / 42')).toBeInTheDocument()
    expect(screen.getByText('13 open')).toBeInTheDocument()
  })

  it('show skeletons instead of numbers while loading', () => {
    mockApi(() => new Promise<Response>(() => undefined) as unknown as Response)
    renderApp()
    expect(within(screen.getByTestId('stat-requirements')).queryByText('42')).toBeNull()
  })

  it('clicking a card filters the findings by that type', async () => {
    const { calls } = mockApi()
    renderApp()
    await rowsShown()
    await userEvent.click(screen.getByTestId('stat-conflicts'))
    await waitFor(() => expect(calls.some((c) => c.url.pathname.endsWith('/requirements') && c.url.searchParams.get('type') === 'conflict')).toBe(true))
    expect(screen.getByTestId('stat-conflicts')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText('Type filter')).toHaveValue('conflict')
  })
})

describe('findings filters and search', () => {
  it('sends the search text (debounced) and the risk filter to the API and shows the filtered rows', async () => {
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/projects/1/requirements' && c.url.searchParams.get('risk') === 'HIGH') {
        const items = fx.rows.filter((r) => r.risk_level === 'HIGH')
        return json({ total: items.length, limit: 50, offset: 0, items })
      }
      return undefined
    })
    renderApp()
    expect(await rowsShown()).toBe(3)

    await userEvent.type(screen.getByRole('searchbox', { name: /Search requirements/ }), 'login')
    await waitFor(() => expect(calls.some((c) => c.url.searchParams.get('q') === 'login')).toBe(true))
    const before = calls.filter((c) => c.url.searchParams.get('q') === 'log').length
    expect(before).toBe(0) // typed fast: only the final text was sent

    await userEvent.selectOptions(screen.getByLabelText('Risk filter'), 'HIGH')
    await waitFor(() => expect(calls.some((c) => c.url.searchParams.get('risk') === 'HIGH')).toBe(true))
    await waitFor(async () => expect(await rowsShown()).toBe(2))
    expect(screen.getByText('Showing 2 of 2')).toBeInTheDocument()
  })

  it('says so when nothing matches', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/requirements' && c.url.searchParams.get('q') ? json({ total: 0, limit: 50, offset: 0, items: [] }) : undefined))
    renderApp()
    await rowsShown()
    await userEvent.type(screen.getByRole('searchbox', { name: /Search requirements/ }), 'zzz')
    expect(await screen.findByTestId('empty-list')).toHaveTextContent('No requirements match these filters.')
  })

  it('rows show id, type, risk badge, text and the source reference', async () => {
    mockApi()
    renderApp()
    const rows = await screen.findAllByTestId('finding-row')
    expect(rows[0]).toHaveTextContent('REQ-001')
    expect(rows[0]).toHaveTextContent('Ambiguity')
    expect(rows[0]).toHaveTextContent('The system should quickly notify users about suspicious logins.')
    expect(rows[0]).toHaveTextContent('CoreBanking_SRS_v2.pdf · Page 12, paragraph 3')
    expect(within(rows[0]!).getByTestId('risk-badge')).toHaveTextContent('HIGH')
    expect(rows[1]).toHaveTextContent('Conflict')
    expect(rows[2]).toHaveTextContent('Duplicate')
    expect(within(rows[2]!).getByTestId('risk-badge')).toHaveTextContent('MEDIUM')
  })

  it('arrow keys move the selection and the detail follows', async () => {
    const { calls } = mockApi()
    renderApp()
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
})

describe('requirement detail', () => {
  it('shows the display id, risk, real model confidence and highlights the weak word', async () => {
    mockApi()
    renderApp()
    const id = await screen.findByTestId('detail-id')
    expect(id).toHaveTextContent('REQ-001')
    expect(id).not.toHaveTextContent('p1-')
    expect(screen.getByTestId('detail-panel')).toHaveTextContent('HIGH RISK')
    expect(screen.getByTestId('confidence')).toHaveTextContent('Model confidence 84%')
    expect(document.getElementById('confidence-help')).toHaveTextContent('not a measured accuracy')
    const marks = screen.getByTestId('original-text').querySelectorAll('mark')
    expect([...marks].map((m) => m.textContent)).toEqual(['quickly'])
    expect(screen.getByTestId('explanation-card')).toHaveTextContent('Ambiguity detected')
    expect(screen.getByTestId('explanation-card')).toHaveTextContent('Weak words found (QuRE list): quickly.')
  })

  it('shows both texts and the reason for a conflict candidate, and duplicate partner with similarity', async () => {
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
    renderApp()
    const conflict = await screen.findByTestId('conflict-partner')
    expect(conflict).toHaveTextContent('REQ-001 (this requirement)')
    expect(conflict).toHaveTextContent(partner.text)
    expect(conflict).toHaveTextContent('Candidate conflict, needs human decision')
    expect(screen.getByTestId('explanation-card')).toHaveTextContent('Candidate conflict, needs human decision')
    expect(screen.getByTestId('duplicate-partners')).toHaveTextContent('similarity 0.973')
  })

  it('lists follow-up questions from the draft and does not invent a revision', async () => {
    mockApi((c) =>
      c.url.pathname === '/api/requirements/p1-REQ-001'
        ? json({ ...fx.detail, generation: { ...fx.generationDone, state: 'needs_clarification', clarification_questions: ['What does quickly mean in seconds?'] } })
        : undefined,
    )
    renderApp()
    const card = await screen.findByTestId('followup-card')
    await waitFor(() => expect(card).toHaveTextContent('What does quickly mean in seconds?'))
    expect(card).toHaveTextContent('Model-written')
    expect(screen.queryByText(/Suggested revision/i)).toBeNull()
    expect(screen.queryByRole('button', { name: /Accept revision/i })).toBeNull()
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
    renderApp()
    await screen.findByTestId('draft-card')
    await userEvent.click(await screen.findByRole('button', { name: /Regenerate/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.pathname === '/api/requirements/p1-REQ-001/generate')).toBe(true))
    await waitFor(() => expect(screen.getByTestId('draft-card')).toHaveAttribute('data-state', 'queued'))
  })
})

describe('decisions', () => {
  const out: DecisionOut = { uid: 'p1-REQ-001', decision: 'accepted', edited_text: null, note: null, updated_at: '2026-10-13T07:00:00+00:00', history: [] }

  it('shows the decision at once and keeps it when the API accepts', async () => {
    let decided = false
    const { calls } = mockApi((c) => {
      if (c.method === 'POST' && c.url.pathname.endsWith('/decision')) {
        decided = true
        return json(out)
      }
      if (decided && c.url.pathname === '/api/projects/1/requirements') {
        const items = fx.rows.map((r) => (r.uid === 'p1-REQ-001' ? { ...r, decision: 'accepted' as const } : r))
        return json({ total: items.length, limit: 50, offset: 0, items })
      }
      if (decided && c.url.pathname === '/api/requirements/p1-REQ-001') {
        return json({ ...fx.detail, decision: { decision: 'accepted', edited_text: null, note: null, updated_at: out.updated_at }, decision_history: [{ decision: 'accepted', edited_text: null, note: null, created_at: out.updated_at }] })
      }
      return undefined
    })
    renderApp()
    await screen.findByTestId('decision-panel')
    expect(screen.getByTestId('decision-status')).toHaveTextContent('No decision yet')
    await userEvent.click(screen.getByRole('button', { name: /Accept/ }))
    await waitFor(() => expect(screen.getByTestId('decision-status')).toHaveTextContent('Accepted'))
    expect(JSON.parse(calls.find((c) => c.method === 'POST' && c.url.pathname.endsWith('/decision'))!.body!)).toEqual({ decision: 'accepted', note: null })
    await waitFor(() => expect(screen.getByTestId('decision-history')).toHaveTextContent('Decision history (1)'))
    expect(screen.getAllByTestId('finding-row')[0]).toHaveTextContent('accepted')
  })

  it('shows it optimistically and rolls back with an error message when the API refuses', async () => {
    let release!: (r: Response) => void
    const pending = new Promise<Response>((resolve) => (release = resolve))
    mockApi((c) => (c.method === 'POST' && c.url.pathname.endsWith('/decision') ? (pending as unknown as Response) : undefined))
    renderApp()
    await screen.findByTestId('decision-panel')
    await userEvent.click(screen.getByRole('button', { name: /Reject/ }))
    await waitFor(() => expect(screen.getByTestId('decision-status')).toHaveTextContent('Rejected')) // optimistic: the API has not answered yet
    expect(screen.getAllByTestId('finding-row')[0]).toHaveTextContent('rejected')
    release(json({ error: { code: 'internal_error', message: 'Unexpected server error' } }, 500))
    await waitFor(() => expect(screen.getByTestId('decision-status')).toHaveTextContent('No decision yet'))
    expect(screen.getAllByTestId('finding-row')[0]).not.toHaveTextContent('rejected')
    expect(await screen.findByRole('alert')).toHaveTextContent('Decision not saved: Unexpected server error')
  })

  it('edit manually saves the clarified text through the decision endpoint', async () => {
    const text = 'The system shall notify users within 2 seconds.'
    let saved = false
    const { calls } = mockApi((c) => {
      if (c.method === 'POST' && c.url.pathname.endsWith('/decision')) {
        saved = true
        return json({ ...out, decision: 'edited', edited_text: text })
      }
      if (saved && c.url.pathname === '/api/requirements/p1-REQ-001') {
        return json({ ...fx.detail, decision: { decision: 'edited', edited_text: text, note: null, updated_at: out.updated_at } })
      }
      return undefined
    })
    renderApp()
    await screen.findByTestId('decision-panel')
    await userEvent.click(screen.getByRole('button', { name: /Edit manually/ }))
    const box = screen.getByLabelText('Clarified requirement text')
    fireEvent.change(box, { target: { value: 'The system shall notify users within 2 seconds.' } })
    await userEvent.click(screen.getByRole('button', { name: 'Save clarified text' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.pathname.endsWith('/decision'))).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'POST' && c.url.pathname.endsWith('/decision'))!.body!)).toEqual({
      decision: 'edited', edited_text: 'The system shall notify users within 2 seconds.', note: null,
    })
    await waitFor(() => expect(screen.getByTestId('edited-text')).toHaveTextContent('within 2 seconds'))
  })
})

describe('page states', () => {
  it('shows the API-offline banner with a retry button', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    renderApp()
    const banner = await screen.findByTestId('offline-banner')
    expect(banner).toHaveTextContent('Cannot reach the Component 1 API')
    expect(within(banner).getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    expect(screen.getAllByRole('status').some((s) => s.getAttribute('data-state') === 'error' && s.textContent === 'Engine error')).toBe(true)
    expect(screen.getByRole('button', { name: /Export analysis/ })).toBeDisabled()
  })

  it('invites an upload when the project is empty', async () => {
    mockApi((c) => {
      const p = c.url.pathname
      if (p === '/api/projects/1/sources') return json([])
      if (p === '/api/projects/1/summary') return json({ ...fx.summary, requirements: 0, ambiguities: { count: 0, high_risk: 0, asked_by_ai: 0 }, conflicts: 0, duplicates: 0, task_drafts: { generated: 0, total: 0 }, open_findings: 0 })
      if (p === '/api/projects/1/requirements') return json({ total: 0, limit: 50, offset: 0, items: [] })
      return undefined
    })
    renderApp()
    expect(await screen.findByTestId('empty-list')).toHaveTextContent('Upload an SRS to begin.')
    expect(screen.getByTestId('sources-card')).toHaveTextContent('Upload an SRS to begin.')
    expect(screen.getByRole('button', { name: /Run analysis/ })).toBeDisabled()
    expect(screen.getByText('Select a requirement to see its analysis.')).toBeInTheDocument()
  })

  it('detail panel: AI badge in the header, vague term highlighted with its legend', async () => {
    const text = 'The system should process payments quickly.'
    const g = { ...fx.generationDone, state: 'needs_clarification' as const, status: 'needs_clarification', clarification_questions: ['How quickly?'] }
    mockApi((c) =>
      c.url.pathname === '/api/requirements/p1-REQ-001'
        ? json({ ...fx.detail, text, original_text: text, ambiguity: { ...fx.detail.ambiguity, weak_words: [], weak_word_spans: [] }, vague_terms: [{ term: 'quickly', start: 35, end: 42 }], generation: g })
        : undefined,
    )
    renderApp()
    const panel = await screen.findByTestId('detail-panel')
    await waitFor(() => expect(within(panel).getByTestId('ai-clarify-badge')).toBeInTheDocument())
    const mark = within(screen.getByTestId('original-text')).getByText('quickly')
    expect(mark).toHaveAttribute('data-kind', 'vague')
    expect(within(panel).getByTestId('highlight-legend')).toHaveTextContent('Vague term (rule-based)')
  })

  it('header pill follows /api/health', async () => {
    mockApi((c) => (c.url.pathname === '/api/health' ? json({ ...fx.health, generation_reachable: false }) : undefined))
    renderApp()
    await waitFor(() => expect(screen.getAllByRole('status').some((s) => s.textContent?.startsWith('Generation offline'))).toBe(true))
  })

  it('a slow first /api/health answer shows "Checking", not an error', async () => {
    mockApi((c) => (c.url.pathname === '/api/health' ? new Promise<Response>(() => undefined) : undefined))
    renderApp()
    await waitFor(() => expect(screen.getAllByRole('status').some((s) => s.textContent?.startsWith('Checking engine'))).toBe(true))
    expect(screen.queryByText('Engine error')).toBeNull()
    expect(screen.queryByText('API not reachable')).toBeNull()
    expect(await screen.findByTestId('detail-panel')).toBeInTheDocument()
  })

  it('model server down: header says offline, Part A results stay, the draft card says AI engine unavailable with Retry', async () => {
    const down = { ...fx.generationDone, state: 'failed' as const, message: 'AI engine unavailable: could not get a reply from http://localhost:11434/v1/chat/completions: refused', status: null, user_story: '', technical_task: '', acceptance_criteria: [], rationale: '', backend: '', model: '' }
    mockApi((c) => {
      if (c.url.pathname === '/api/health') return json({ ...fx.health, generation_backend: 'ollama', model: 'c1-req', generation_reachable: false })
      if (c.url.pathname === '/api/requirements/p1-REQ-001') return json({ ...fx.detail, generation: down })
      return undefined
    })
    renderApp()
    await waitFor(() => expect(screen.getAllByRole('status').some((s) => s.textContent?.startsWith('Generation offline'))).toBe(true))
    expect(await screen.findAllByTestId('finding-row')).not.toHaveLength(0) // Part A rows are there
    const card = await screen.findByTestId('draft-card')
    expect(card).toHaveTextContent('AI engine unavailable.')
    expect(card.querySelector('.animate-spin')).toBeNull()
    expect(within(card).getByRole('button', { name: /Retry/ })).toBeEnabled()
    expect(screen.getByRole('region', { name: 'Engine status' })).toHaveTextContent('ollama · c1-req')
  })

  it('sidebar: honest engine card, disabled modules, no graph card', async () => {
    mockApi()
    renderApp()
    const engine = await screen.findByRole('region', { name: 'Engine status' })
    await waitFor(() => expect(engine).toHaveTextContent('replay · replay'))
    expect(engine).toHaveTextContent('Loaded')
    expect(engine).toHaveTextContent('Yes')
    expect(screen.queryByText(/Shared graph connected/)).toBeNull()
    expect(screen.queryByText(/Neo4j/)).toBeNull()
    expect(screen.getByText('Core Banking Platform', { selector: '.truncate' })).toBeInTheDocument()
    for (const name of ['Framework overview', 'Repository intelligence', 'Quality & testing', 'Traceability intelligence', 'USKG knowledge graph']) {
      expect(screen.getByTitle(`${name}: Coming soon`)).toBeDisabled()
    }
    expect(screen.getByRole('link', { name: /Requirement intelligence/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('Researcher')).toBeInTheDocument()
  })

  it('pipeline follows the job stage', async () => {
    let analysed = false
    mockApi((c) => {
      if (c.method === 'POST' && c.url.pathname === '/api/projects/1/analyze') {
        analysed = true
        return json({ ...fx.job, stage: 'improve' }, 202)
      }
      if (c.url.pathname === '/api/jobs/abc123') return json({ ...fx.job, stage: 'improve' })
      if (analysed && c.url.pathname === '/api/projects/1/summary') return json({ ...fx.summary, task_drafts: { ...fx.summary.task_drafts, generated: 10, total: 42, in_progress: 32, queued: 31, running: 1 } })
      return undefined
    })
    renderApp()
    await rowsShown()
    await userEvent.click(screen.getByRole('button', { name: /Run analysis/ }))
    await waitFor(() => expect(document.querySelector('[data-stage="improve"]')).toHaveAttribute('data-state', 'active'))
    const state = (s: string) => document.querySelector(`[data-stage="${s}"]`)!.getAttribute('data-state')
    expect([state('collect'), state('identify'), state('analyse'), state('improve'), state('share')]).toEqual(['done', 'done', 'done', 'active', 'pending'])
    const bar = await screen.findByRole('progressbar', { name: 'Draft progress' })
    expect(bar).toHaveAttribute('aria-valuenow', '10')
    expect(screen.getByTestId('draft-counts')).toHaveTextContent('Drafts 10 of 42 done')
  })
})

describe('uploads', () => {
  const pick = async (file: File) => fireEvent.change(screen.getByTestId('file-input'), { target: { files: [file] } })

  it('checks the file type and size in the browser and shows a toast, without calling the API', async () => {
    const { calls } = mockApi()
    renderApp()
    await rowsShown()
    await pick(new File(['x'], 'virus.exe'))
    expect(await screen.findByText(/virus\.exe: file type \.exe is not allowed/)).toBeInTheDocument()
    const big = new File(['x'], 'big.txt')
    Object.defineProperty(big, 'size', { value: 21 * 1024 * 1024 })
    await pick(big)
    expect(await screen.findByText(/big\.txt: larger than the 20 MB limit/)).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST' && c.url.pathname.endsWith('/sources'))).toBe(false)
  })

  it('uploads allowed files and shows the server error message for a rejected one', async () => {
    const { calls } = mockApi((c) =>
      c.method === 'POST' && c.url.pathname === '/api/projects/1/sources'
        ? json({ accepted: [fx.source], rejected: [{ filename: 'broken.pdf', code: 'unreadable_file', message: 'The PDF could not be read: PdfReadError.' }] }, 201)
        : undefined,
    )
    renderApp()
    await rowsShown()
    await pick(new File(['hello'], 'spec.txt'))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.pathname === '/api/projects/1/sources')).toBe(true))
    expect(await screen.findByText('The PDF could not be read: PdfReadError.')).toBeInTheDocument()
    expect(await screen.findByText(/1 file added/)).toBeInTheDocument()
  })
})
