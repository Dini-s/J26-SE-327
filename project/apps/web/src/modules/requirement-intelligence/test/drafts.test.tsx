import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Generation, TaskDrafts } from '../api/types'
import { DraftCard } from '../components/DraftCard'
import { DraftProgress } from '../components/DraftProgress'
import { copy } from '../copy'
import { formatEta } from '../lib/progress'
import * as fx from './fixtures'
import { json, mockApi, renderApp } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

const drafts = (o: Partial<TaskDrafts> = {}): TaskDrafts => ({ ...fx.summary.task_drafts, generated: 4, total: 10, not_generated: 3, needs_clarification: 2, failed: 1, ...o })

// ------------------------------------------------------------------------------------------------------------ progress panel
describe('DraftProgress', () => {
  const noop = () => undefined
  const show = (d: TaskDrafts, extra: Partial<Parameters<typeof DraftProgress>[0]> = {}) =>
    render(<DraftProgress drafts={d} onPause={noop} onResume={noop} onGenerateAll={noop} busy={false} analysing={false} {...extra} />)

  it('says how many drafts are done, not generated, need clarification and failed', () => {
    show(drafts())
    expect(screen.getByTestId('draft-counts')).toHaveTextContent('Drafts 4 of 10 done, 3 not generated, 2 needs clarification, 1 failed')
    expect(screen.getByRole('progressbar', { name: 'Draft progress' })).toHaveAttribute('aria-valuenow', '7') // 4 + 2 + 1 are settled
  })

  it('is hidden when there is nothing to do or nothing to show', () => {
    const { container, rerender } = render(<DraftProgress drafts={drafts({ not_generated: 0, in_progress: 0 })} onPause={noop} onResume={noop} onGenerateAll={noop} busy={false} analysing={false} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<DraftProgress drafts={undefined} onPause={noop} onResume={noop} onGenerateAll={noop} busy={false} analysing={false} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<DraftProgress drafts={drafts({ total: 0, not_generated: 0 })} onPause={noop} onResume={noop} onGenerateAll={noop} busy={false} analysing={false} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('says "Calculating…" until something is known, then shows the service estimate', () => {
    const { rerender } = show(drafts({ in_progress: 4, queued: 4, eta_seconds: null, latency_samples: 2 }))
    expect(screen.getByTestId('draft-eta')).toHaveTextContent('Calculating…')
    rerender(<DraftProgress drafts={drafts({ in_progress: 4, queued: 4, eta_seconds: 600, latency_samples: 5 })} onPause={noop} onResume={noop} onGenerateAll={noop} busy={false} analysing={false} />)
    expect(screen.getByTestId('draft-eta')).toHaveTextContent('About 10 min left')
  })

  it('formats the time left in whole minutes', () => {
    expect(formatEta(20)).toBe('Under 1 min left')
    expect(formatEta(61)).toBe('About 2 min left')
    expect(formatEta(3600)).toBe('About 1 h 0 min left')
    expect(formatEta(5400)).toBe('About 1 h 30 min left')
  })

  it('offers Pause while drafts run, Resume while paused, and Generate all remaining while some are missing', async () => {
    const onPause = vi.fn()
    const onResume = vi.fn()
    const onGenerateAll = vi.fn()
    const { rerender } = show(drafts({ in_progress: 2, queued: 2 }), { onPause, onResume, onGenerateAll })
    await userEvent.click(screen.getByRole('button', { name: /Pause/ }))
    expect(onPause).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('button', { name: /Resume/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /Generate all remaining/ }))
    expect(onGenerateAll).toHaveBeenCalledTimes(1)
    rerender(<DraftProgress drafts={drafts({ in_progress: 2, queued: 2, paused: true })} onPause={onPause} onResume={onResume} onGenerateAll={onGenerateAll} busy={false} analysing={false} />)
    expect(screen.queryByRole('button', { name: /Pause/ })).toBeNull()
    expect(screen.getByTestId('draft-eta')).toHaveTextContent('Paused: 2 waiting')
    await userEvent.click(screen.getByRole('button', { name: /Resume/ }))
    expect(onResume).toHaveBeenCalledTimes(1)
  })

  it('has no Generate all button when every requirement has a draft or is queued, and disables it while analysing or busy', () => {
    const { rerender } = show(drafts({ not_generated: 0, in_progress: 3, queued: 3 }))
    expect(screen.queryByRole('button', { name: /Generate all remaining/ })).toBeNull()
    rerender(<DraftProgress drafts={drafts()} onPause={noop} onResume={noop} onGenerateAll={noop} busy={false} analysing />)
    expect(screen.getByRole('button', { name: /Generate all remaining/ })).toBeDisabled()
    rerender(<DraftProgress drafts={drafts()} onPause={noop} onResume={noop} onGenerateAll={noop} busy analysing={false} />)
    expect(screen.getByRole('button', { name: /Generate all remaining/ })).toBeDisabled()
  })
})

// ------------------------------------------------------------------------------------------------------------ task drafts page
describe('Analysis: which task drafts to write', () => {
  beforeEach(() => window.localStorage.clear())

  const analyzeCall = (calls: { method: string; url: URL }[]) => calls.find((c) => c.method === 'POST' && c.url.pathname === '/api/projects/1/analyze')
  const pendingOnly = (c: { url: URL; method: string }) => {
    if (c.url.pathname === '/api/projects/1/sources' && c.method === 'GET') return json([fx.source2]) // a document that still needs the analysis
    return c.method === 'POST' && c.url.pathname === '/api/projects/1/analyze' ? json({ ...fx.job, policy: 'all' }, 202) : undefined
  }

  it('Task Drafts no longer has the “How drafts are written” section', async () => {
    mockApi()
    renderApp('/requirement/drafts')
    await screen.findAllByTestId('finding-row')
    expect(screen.queryByTestId('policy-select')).toBeNull()
    expect(screen.queryByText('How drafts are written')).toBeNull()
  })

  it('the question offers the three plain-language choices and explains each', async () => {
    mockApi(pendingOnly)
    renderApp('/requirement/sources')
    await waitFor(() => expect(screen.getByTestId('analyse-pending')).toBeEnabled())
    await userEvent.click(screen.getByTestId('analyse-pending'))
    const box = screen.getByTestId('analyse-policy')
    for (const p of ['smart', 'all', 'manual'] as const) {
      expect(within(box).getByTestId(`policy-${p}`)).toBeInTheDocument()
      expect(box).toHaveTextContent(copy.drafts.policy[p].label)
      expect(box).toHaveTextContent(copy.drafts.policy[p].help)
    }
  })

  it('starts with the remembered policy and runs the analysis with it', async () => {
    window.localStorage.setItem('requirement-intelligence.draftPolicy', 'all')
    const { calls } = mockApi(pendingOnly)
    renderApp('/requirement/sources')
    await waitFor(() => expect(screen.getByTestId('analyse-pending')).toBeEnabled())
    await userEvent.click(await screen.findByTestId('analyse-pending'))
    expect(screen.getByTestId('policy-all')).toBeChecked()
    await userEvent.click(screen.getByTestId('analyse-confirm'))
    await waitFor(() => expect(analyzeCall(calls)).toBeTruthy())
    expect(analyzeCall(calls)!.url.searchParams.get('policy')).toBe('all')
  })

  it('sends smart by default, and the choice made in the question is what is sent and remembered', async () => {
    const { calls } = mockApi(pendingOnly)
    renderApp('/requirement/sources')
    await waitFor(() => expect(screen.getByTestId('analyse-pending')).toBeEnabled())
    await userEvent.click(await screen.findByTestId('analyse-pending'))
    expect(screen.getByTestId('policy-smart')).toBeChecked()
    await userEvent.click(screen.getByTestId('policy-manual'))
    await userEvent.click(screen.getByTestId('analyse-confirm'))
    await waitFor(() => expect(analyzeCall(calls)).toBeTruthy())
    expect(analyzeCall(calls)!.url.searchParams.get('policy')).toBe('manual')
    expect(window.localStorage.getItem('requirement-intelligence.draftPolicy')).toBe('manual')
  })

  it('Cancel sends nothing', async () => {
    const { calls } = mockApi(pendingOnly)
    renderApp('/requirement/sources')
    await waitFor(() => expect(screen.getByTestId('analyse-pending')).toBeEnabled())
    await userEvent.click(await screen.findByTestId('analyse-pending'))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))
    expect(analyzeCall(calls)).toBeUndefined()
  })

  it('works without browser storage', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const { calls } = mockApi(pendingOnly)
    renderApp('/requirement/sources')
    await waitFor(() => expect(screen.getByTestId('analyse-pending')).toBeEnabled())
    await userEvent.click(await screen.findByTestId('analyse-pending'))
    expect(screen.getByTestId('policy-smart')).toBeChecked()
    await userEvent.click(screen.getByTestId('policy-all')) // still applied for this visit
    await userEvent.click(screen.getByTestId('analyse-confirm'))
    await waitFor(() => expect(analyzeCall(calls)).toBeTruthy())
    expect(analyzeCall(calls)!.url.searchParams.get('policy')).toBe('all')
  })
})

describe('Sources & Findings: draft progress and controls (Task Drafts keeps the list)', () => {
  const partial = { ...fx.summary, task_drafts: drafts({ in_progress: 2, queued: 2 }) }
  const post = (calls: { method: string; url: URL }[], path: string) => calls.some((c) => c.method === 'POST' && c.url.pathname === path)

  it('Pause and Generate all remaining call the service and report the result', async () => {
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/projects/1/summary') return json(partial)
      if (c.method === 'POST' && c.url.pathname === '/api/projects/1/generation/pause') return json({ paused: true })
      if (c.method === 'POST' && c.url.pathname === '/api/projects/1/generate') return json({ queued: 3 }, 202)
      return undefined
    })
    renderApp('/requirement/sources')
    await userEvent.click(await screen.findByRole('button', { name: /Pause/ }))
    await waitFor(() => expect(post(calls, '/api/projects/1/generation/pause')).toBe(true))
    await userEvent.click(screen.getByRole('button', { name: /Generate all remaining/ }))
    await waitFor(() => expect(post(calls, '/api/projects/1/generate')).toBe(true))
    expect(await screen.findByText('3 drafts queued.')).toBeInTheDocument()
  })

  it('a paused queue shows Resume and calls the service', async () => {
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/projects/1/summary') return json({ ...fx.summary, task_drafts: drafts({ in_progress: 2, queued: 2, paused: true }) })
      if (c.method === 'POST' && c.url.pathname === '/api/projects/1/generation/resume') return json({ paused: false })
      return undefined
    })
    renderApp('/requirement/sources')
    await userEvent.click(await screen.findByRole('button', { name: /Resume/ }))
    await waitFor(() => expect(post(calls, '/api/projects/1/generation/resume')).toBe(true))
  })

  it('lists every requirement with its draft state and filters by it, with counts', async () => {
    mockApi()
    renderApp('/requirement/drafts')
    const rows = await screen.findAllByTestId('finding-row')
    expect(rows).toHaveLength(3)
    expect(screen.getByTestId('draft-filter-all')).toHaveTextContent('All (3)')
    expect(screen.getByTestId('draft-filter-ready')).toHaveTextContent('Ready (2)')
    expect(screen.getByTestId('draft-filter-failed')).toHaveTextContent('Failed (1)')
    await userEvent.click(screen.getByTestId('draft-filter-failed'))
    expect(screen.getAllByTestId('finding-row')).toHaveLength(1)
    expect(screen.getByTestId('finding-row')).toHaveTextContent('REQ-003')
    await userEvent.click(screen.getByTestId('draft-filter-none'))
    expect(screen.getByTestId('empty-list')).toHaveTextContent('No requirements match this draft status.')
  })

  it('a requirement without a draft offers Generate draft in the list and in the detail, each asking for that one', async () => {
    const none: Generation = { ...fx.generationDone, state: 'not_requested', message: '', status: null, user_story: '', technical_task: '', acceptance_criteria: [], rationale: '', attempts: 0, backend: '', model: '', generated_from: '' }
    const items = fx.rows.map((r, i) => (i === 0 ? { ...r, generation_state: 'not_requested' as const } : r))
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/projects/1/requirements') return json({ total: 3, limit: 500, offset: 0, items })
      if (c.url.pathname === '/api/requirements/p1-REQ-001' && c.method === 'GET') return json({ ...fx.detail, generation: none })
      if (c.method === 'POST' && c.url.pathname === '/api/requirements/p1-REQ-001/generate') return json({ uid: 'p1-REQ-001', generation_state: 'queued' }, 202)
      return undefined
    })
    renderApp('/requirement/drafts')
    const card = await screen.findByTestId('draft-card')
    await waitFor(() => expect(card).toHaveAttribute('data-state', 'not_requested'))
    expect(card).toHaveTextContent('Not written yet. Click Generate draft to write one.')
    await userEvent.click(screen.getByRole('button', { name: 'Generate draft for REQ-001' }))
    await waitFor(() => expect(post(calls, '/api/requirements/p1-REQ-001/generate')).toBe(true))
    await userEvent.click(within(card).getByRole('button', { name: /Generate draft/ }))
    expect(calls.filter((c) => c.method === 'POST' && c.url.pathname === '/api/requirements/p1-REQ-001/generate').length).toBeGreaterThanOrEqual(1)
  })

  it('the progress shows no engine wording and the Task Drafts page no longer has it', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/summary' ? json(partial) : undefined))
    const first = renderApp('/requirement/sources')
    expect(await screen.findByTestId('draft-progress')).toBeInTheDocument()
    expect(screen.queryByTestId('draft-target')).toBeNull()
    expect(screen.getByTestId('draft-progress')).not.toHaveTextContent(/on device|cloud|processing:/i)
    expect(document.body).not.toHaveTextContent('c1-req')
    first.unmount()
    vi.unstubAllGlobals()
    mockApi((c) => (c.url.pathname === '/api/projects/1/summary' ? json(partial) : undefined))
    renderApp('/requirement/drafts')
    await screen.findAllByTestId('finding-row')
    expect(screen.queryByTestId('draft-progress')).toBeNull()
  })
})

// ------------------------------------------------------------------------------------------------------------ clarification flow
describe('DraftCard: clarified text', () => {
  it("says when the draft was written from the user's clarified text", () => {
    render(<DraftCard generation={{ ...fx.generationDone, generated_from: 'clarified' }} onGenerate={() => undefined} busy={false} />)
    expect(screen.getByTestId('from-clarified')).toHaveTextContent('Generated by AI from your edited text')
  })

  it.each(['original', ''])('does not say it for %j', (origin) => {
    render(<DraftCard generation={{ ...fx.generationDone, generated_from: origin }} onGenerate={() => undefined} busy={false} />)
    expect(screen.queryByTestId('from-clarified')).toBeNull()
  })

  it('Regenerate on a needs_clarification draft calls generate', async () => {
    const onGenerate = vi.fn()
    render(<DraftCard generation={{ ...fx.generationDone, state: 'needs_clarification', status: 'needs_clarification', clarification_questions: ['What?'] }} onGenerate={onGenerate} busy={false} />)
    await userEvent.click(screen.getByRole('button', { name: /Regenerate/ }))
    expect(onGenerate).toHaveBeenCalledTimes(1)
  })
})
