import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DecisionIn, Generation, TaskDrafts } from '../api/types'
import { DecisionPanel } from '../components/DecisionPanel'
import { DraftCard } from '../components/DraftCard'
import { DraftProgress, formatEta } from '../components/DraftProgress'
import { StatCards } from '../components/StatCards'
import { POLICY_HELP, POLICY_LABEL, TitleBlock } from '../components/TopSection'
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

  it('says "Calculating time left…" until something is known, then shows the API estimate', () => {
    const { rerender } = show(drafts({ in_progress: 4, queued: 4, eta_seconds: null, latency_samples: 2 }))
    expect(screen.getByTestId('draft-eta')).toHaveTextContent('Calculating time left…')
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

// ------------------------------------------------------------------------------------------------------------ stat cards
describe('stat cards with partial generation', () => {
  const show = (summary: Partial<typeof fx.summary>) => render(<StatCards summary={{ ...fx.summary, ...summary }} loading={false} active="all" onSelect={() => undefined} />)

  it('Task drafts keeps generated, needs clarification, not generated yet and failed apart', () => {
    show({ task_drafts: drafts({ in_progress: 1, queued: 1, manual_review: 1 }) })
    const card = screen.getByTestId('stat-drafts')
    expect(within(card).getByText('4 / 10')).toBeInTheDocument() // only valid drafts
    expect(within(card).getByTestId('drafts-clarification')).toHaveTextContent('2 needs clarification')
    expect(within(card).getByTestId('drafts-not-generated')).toHaveTextContent('3 not generated yet')
    expect(within(card).getByTestId('drafts-in-progress')).toHaveTextContent('1 in progress')
    expect(within(card).getByTestId('drafts-failed')).toHaveTextContent('1 failed')
    expect(within(card).getByTestId('drafts-manual-review')).toHaveTextContent('1 manual review')
  })

  it('shows no line for a kind that has zero, and marks a paused queue', () => {
    show({ task_drafts: drafts({ needs_clarification: 0, not_generated: 0, failed: 0, in_progress: 2, queued: 2, paused: true }) })
    const card = screen.getByTestId('stat-drafts')
    expect(within(card).queryByTestId('drafts-clarification')).toBeNull()
    expect(within(card).queryByTestId('drafts-not-generated')).toBeNull()
    expect(within(card).queryByTestId('drafts-failed')).toBeNull()
    expect(within(card).getByTestId('drafts-in-progress')).toHaveTextContent('2 in progress (paused)')
  })

  it.each([
    [0, 3, 0, '+0 asked by AI (0 so far, drafts pending)'],
    [2, 3, 0, '+2 asked by AI (2 so far, drafts pending)'],
    [2, 0, 1, '+2 asked by AI (2 so far, drafts pending)'], // drafts are still being written
    [2, 0, 0, '+2 asked by AI'],
    [0, 0, 0, '+0 asked by AI'],
  ])('Ambiguities: asked_by_ai=%i, not generated=%i, in progress=%i -> %s', (n, notGenerated, inProgress, text) => {
    show({ ambiguities: { count: 8, high_risk: 3, asked_by_ai: n }, task_drafts: drafts({ not_generated: notGenerated, in_progress: inProgress, queued: inProgress }) })
    const line = within(screen.getByTestId('stat-ambiguities')).getByTestId('asked-by-ai')
    expect(line).toHaveTextContent(text)
    if (text.includes('pending')) expect(line.getAttribute('title')).toContain('not written yet')
    expect(within(screen.getByTestId('stat-ambiguities')).getByText('8')).toBeInTheDocument() // Part A number untouched
  })
})

// ------------------------------------------------------------------------------------------------------------ policy selector
describe('draft policy selector', () => {
  const show = (policy: 'smart' | 'all' | 'manual', onPolicy = vi.fn()) => {
    render(<TitleBlock onFiles={() => undefined} onRun={() => undefined} canRun running={false} policy={policy} onPolicy={onPolicy} />)
    return onPolicy
  }

  it('offers the three plain-language choices and explains the chosen one in one line', () => {
    show('smart')
    const select = screen.getByTestId('policy-select') as HTMLSelectElement
    expect([...select.options].map((o) => o.value)).toEqual(['smart', 'all', 'manual'])
    expect([...select.options].map((o) => o.textContent)).toEqual([POLICY_LABEL.smart, POLICY_LABEL.all, POLICY_LABEL.manual])
    expect(select.value).toBe('smart')
    expect(screen.getByTestId('policy-help')).toHaveTextContent(POLICY_HELP.smart)
  })

  it.each(['smart', 'all', 'manual'] as const)('explains %s', (p) => {
    show(p)
    expect(screen.getByTestId('policy-help')).toHaveTextContent(POLICY_HELP[p])
  })

  it('reports a change', async () => {
    const onPolicy = show('smart')
    await userEvent.selectOptions(screen.getByTestId('policy-select'), 'manual')
    expect(onPolicy).toHaveBeenCalledWith('manual')
  })
})

describe('policy in the app', () => {
  beforeEach(() => window.localStorage.clear())

  const analyzeCall = (calls: { method: string; url: URL }[]) => calls.find((c) => c.method === 'POST' && c.url.pathname === '/api/projects/1/analyze')

  it('sends smart by default and the chosen policy afterwards, and remembers it', async () => {
    const { calls } = mockApi((c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/analyze' ? json({ ...fx.job, policy: 'smart' }, 202) : undefined))
    renderApp()
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByRole('button', { name: /Run analysis/ }))
    await waitFor(() => expect(analyzeCall(calls)).toBeTruthy())
    expect(analyzeCall(calls)!.url.searchParams.get('policy')).toBe('smart')
  })

  it('sends policy=all after choosing it', async () => {
    const { calls } = mockApi((c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/analyze' ? json({ ...fx.job, policy: 'all' }, 202) : undefined))
    renderApp()
    await screen.findAllByTestId('finding-row')
    await userEvent.selectOptions(screen.getByTestId('policy-select'), 'all')
    expect(window.localStorage.getItem('c1.draftPolicy')).toBe('all')
    await userEvent.click(screen.getByRole('button', { name: /Run analysis/ }))
    await waitFor(() => expect(analyzeCall(calls)).toBeTruthy())
    expect(analyzeCall(calls)!.url.searchParams.get('policy')).toBe('all')
  })

  it('starts with the remembered policy', async () => {
    window.localStorage.setItem('c1.draftPolicy', 'manual')
    mockApi()
    renderApp()
    expect(await screen.findByTestId('policy-select')).toHaveValue('manual')
    expect(screen.getByTestId('policy-help')).toHaveTextContent(POLICY_HELP.manual)
  })

  it('works without browser storage', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    mockApi()
    renderApp()
    expect(await screen.findByTestId('policy-select')).toHaveValue('smart')
    vi.restoreAllMocks()
  })
})

describe('draft controls in the app', () => {
  const partial = { ...fx.summary, task_drafts: drafts({ in_progress: 2, queued: 2 }) }
  const post = (calls: { method: string; url: URL }[], path: string) => calls.some((c) => c.method === 'POST' && c.url.pathname === path)

  it('Pause, Resume and Generate all remaining call the API', async () => {
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/projects/1/summary') return json(partial)
      if (c.method === 'POST' && c.url.pathname === '/api/projects/1/generation/pause') return json({ paused: true })
      if (c.method === 'POST' && c.url.pathname === '/api/projects/1/generate') return json({ queued: 3 }, 202)
      return undefined
    })
    renderApp()
    await userEvent.click(await screen.findByRole('button', { name: /Pause/ }))
    await waitFor(() => expect(post(calls, '/api/projects/1/generation/pause')).toBe(true))
    await userEvent.click(screen.getByRole('button', { name: /Generate all remaining/ }))
    await waitFor(() => expect(post(calls, '/api/projects/1/generate')).toBe(true))
    expect(await screen.findByText('3 drafts queued.')).toBeInTheDocument()
  })

  it('a paused queue shows Resume, calls the API and does not count as running', async () => {
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/projects/1/summary') return json({ ...fx.summary, task_drafts: drafts({ in_progress: 2, queued: 2, paused: true }) })
      if (c.method === 'POST' && c.url.pathname === '/api/projects/1/generation/resume') return json({ paused: false })
      return undefined
    })
    renderApp()
    const resume = await screen.findByRole('button', { name: /Resume/ })
    expect(screen.getByRole('button', { name: /Run analysis/ })).toBeEnabled() // paused: nothing is running
    await userEvent.click(resume)
    await waitFor(() => expect(post(calls, '/api/projects/1/generation/resume')).toBe(true))
  })

  it('a requirement that is not generated yet offers Generate draft, which asks the API for that one', async () => {
    const none: Generation = { ...fx.generationDone, state: 'not_requested', message: '', status: null, user_story: '', technical_task: '', acceptance_criteria: [], rationale: '', attempts: 0, backend: '', model: '', generated_from: '' }
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/requirements/p1-REQ-001' && c.method === 'GET') return json({ ...fx.detail, generation: none })
      if (c.method === 'POST' && c.url.pathname === '/api/requirements/p1-REQ-001/generate') return json({ uid: 'p1-REQ-001', generation_state: 'queued' }, 202)
      return undefined
    })
    renderApp()
    const card = await screen.findByTestId('draft-card')
    await waitFor(() => expect(card).toHaveAttribute('data-state', 'not_requested'))
    expect(card).toHaveTextContent('Not generated yet. Click Generate draft to write one.')
    await userEvent.click(within(card).getByRole('button', { name: /Generate draft/ }))
    await waitFor(() => expect(post(calls, '/api/requirements/p1-REQ-001/generate')).toBe(true))
  })
})

// ------------------------------------------------------------------------------------------------------------ clarification flow
describe('DraftCard: clarified text', () => {
  it('says when the draft was written from the user\'s clarified text', () => {
    render(<DraftCard generation={{ ...fx.generationDone, generated_from: 'clarified' }} onGenerate={() => undefined} busy={false} />)
    expect(screen.getByTestId('from-clarified')).toHaveTextContent('Generated from your clarified text')
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

describe('DecisionPanel', () => {
  const asking = { ...fx.detail, generation: { ...fx.generationDone, state: 'needs_clarification' as const, status: 'needs_clarification', clarification_questions: ['How quickly?'] } }
  const show = (detail = fx.detail) => {
    const onDecide = vi.fn<(b: DecisionIn) => void>()
    render(<DecisionPanel detail={detail} pending={false} onDecide={onDecide} />)
    return onDecide
  }

  it('explains Accept, Edit manually and Reject and what is passed on to Component 3', () => {
    show()
    const help = screen.getByTestId('decision-help')
    expect(help).toHaveTextContent('Accept')
    expect(help).toHaveTextContent('Edit manually')
    expect(help).toHaveTextContent('Reject')
    expect(help).toHaveTextContent('Accepted and edited requirements are the ones passed on to Component 3')
  })

  it('accepts at once when the model did not ask for clarification', async () => {
    const onDecide = show()
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'accepted', note: null })
    expect(screen.queryByTestId('accept-confirm')).toBeNull()
  })

  it('asks once, without blocking, when the model asked for clarification', async () => {
    const onDecide = show(asking)
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }))
    const confirm = screen.getByTestId('accept-confirm')
    expect(confirm).toHaveTextContent('The AI asked for clarification. Accept anyway?')
    expect(onDecide).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Reject/ })).toBeEnabled() // the other choices stay available
    expect(screen.getByRole('button', { name: /Edit manually/ })).toBeEnabled()
    await userEvent.click(within(confirm).getByRole('button', { name: 'Accept anyway' }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'accepted', note: null })
    expect(screen.queryByTestId('accept-confirm')).toBeNull()
  })

  it('Cancel on the question records nothing', async () => {
    const onDecide = show(asking)
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }))
    await userEvent.click(within(screen.getByTestId('accept-confirm')).getByRole('button', { name: 'Cancel' }))
    expect(onDecide).not.toHaveBeenCalled()
    expect(screen.queryByTestId('accept-confirm')).toBeNull()
  })

  it('does not ask again once the user has written a clarified text', async () => {
    const onDecide = show({ ...asking, decision: { decision: 'edited', edited_text: 'Better text within 2 seconds.', note: null, updated_at: 't' } })
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }))
    expect(screen.queryByTestId('accept-confirm')).toBeNull()
    expect(onDecide).toHaveBeenCalledWith({ decision: 'accepted', note: null })
  })

  it('does not ask when there are no questions', async () => {
    const onDecide = show({ ...asking, generation: { ...asking.generation, clarification_questions: [] } })
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }))
    expect(screen.queryByTestId('accept-confirm')).toBeNull()
    expect(onDecide).toHaveBeenCalledTimes(1)
  })

  it('Edit manually with the unchanged text cannot be saved as an edit', async () => {
    const onDecide = show()
    await userEvent.click(screen.getByRole('button', { name: /Edit manually/ }))
    expect(screen.getByLabelText('Clarified requirement text')).toHaveValue(fx.detail.original_text)
    expect(screen.getByTestId('unchanged-note')).toHaveTextContent('same as the original')
    const save = screen.getByRole('button', { name: 'Accept unchanged text' })
    expect(save).toBeDisabled()
    await userEvent.click(save)
    expect(onDecide).not.toHaveBeenCalled()
  })

  it('a text that only differs in spacing counts as unchanged', async () => {
    show()
    await userEvent.click(screen.getByRole('button', { name: /Edit manually/ }))
    fireEvent.change(screen.getByLabelText('Clarified requirement text'), { target: { value: '  ' + fx.detail.original_text.replace(/ /g, '   ') + '\n' } })
    expect(screen.getByRole('button', { name: 'Accept unchanged text' })).toBeDisabled()
  })

  it('an explicit confirmation records the unchanged text as Accepted, never as Edited', async () => {
    const onDecide = show()
    await userEvent.click(screen.getByRole('button', { name: /Edit manually/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Keep the text unchanged/ }))
    const save = screen.getByRole('button', { name: 'Accept unchanged text' })
    expect(save).toBeEnabled()
    await userEvent.click(save)
    expect(onDecide).toHaveBeenCalledTimes(1)
    expect(onDecide).toHaveBeenCalledWith({ decision: 'accepted', note: null })
  })

  it('a changed text is saved as Edited', async () => {
    const onDecide = show()
    await userEvent.click(screen.getByRole('button', { name: /Edit manually/ }))
    fireEvent.change(screen.getByLabelText('Clarified requirement text'), { target: { value: 'The system shall notify users within 2 seconds.' } })
    expect(screen.queryByTestId('unchanged-note')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Save clarified text' }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'edited', edited_text: 'The system shall notify users within 2 seconds.', note: null })
  })

  it('keeps the original visible and tells the user to regenerate after an edit', () => {
    show({ ...fx.detail, decision: { decision: 'edited', edited_text: 'The system shall notify users within 2 seconds.', note: null, updated_at: 't' } })
    expect(screen.getByTestId('edited-text')).toHaveTextContent('within 2 seconds')
    expect(screen.getByTestId('edited-text')).toHaveTextContent('Press Regenerate on the task draft')
  })
})
