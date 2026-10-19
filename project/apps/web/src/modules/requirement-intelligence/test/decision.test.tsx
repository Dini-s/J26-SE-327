import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DecisionIn, RequirementDetail } from '../api/types'
import { DecisionCard } from '../components/DecisionCard'
import * as fx from './fixtures'
import { json, mockApi, renderApp } from './utils'

afterEach(() => vi.unstubAllGlobals())

const asking = { ...fx.detail, generation: { ...fx.generationDone, state: 'needs_clarification' as const, status: 'needs_clarification', clarification_questions: ['How quickly?'] } }
const decided = (d: Partial<NonNullable<RequirementDetail['decision']>> = {}): RequirementDetail => ({
  ...fx.detail,
  decision: { decision: 'accepted', edited_text: null, note: 'looks fine', updated_at: '2026-10-14T09:30:00+00:00', ...d },
})

function show(detail: RequirementDetail = fx.detail, busy = false) {
  const onDecide = vi.fn<(b: DecisionIn) => Promise<boolean>>(async () => true)
  const onRemove = vi.fn<() => Promise<boolean>>(async () => true)
  render(<DecisionCard detail={detail} busy={busy} onDecide={onDecide} onRemove={onRemove} />)
  return { onDecide, onRemove }
}

describe('DecisionCard before a decision', () => {
  it('explains Accept, Edit manually and Reject and what is passed on, without internal names', () => {
    show()
    const help = screen.getByTestId('decision-help')
    expect(help).toHaveTextContent('Accept')
    expect(help).toHaveTextContent('Edit manually')
    expect(help).toHaveTextContent('Reject')
    expect(help).toHaveTextContent('Accepted and edited requirements are passed on to downstream analysis')
    expect(screen.getByTestId('decision-pending')).toHaveTextContent('No decision yet')
    expect(screen.queryByRole('button', { name: /Change decision|Remove decision/ })).toBeNull()
  })

  it('accepts at once, with the optional note', async () => {
    const { onDecide } = show()
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'accepted', note: null })
    onDecide.mockClear()
    await userEvent.type(screen.getByLabelText(/Comment/), ' needs a review ')
    await userEvent.click(screen.getByRole('button', { name: /Reject/ }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'rejected', note: 'needs a review' })
  })

  it('asks once, without blocking, when the AI asked for clarification', async () => {
    const { onDecide } = show(asking)
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }))
    const confirm = screen.getByTestId('accept-confirm')
    expect(confirm).toHaveTextContent('The AI asked for clarification. Accept anyway?')
    expect(onDecide).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Reject/ })).toBeEnabled()
    await userEvent.click(within(confirm).getByRole('button', { name: 'Accept anyway' }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'accepted', note: null })
  })

  it('Cancel on the question records nothing, and no question is asked when there are none', async () => {
    const { onDecide } = show(asking)
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }))
    await userEvent.click(within(screen.getByTestId('accept-confirm')).getByRole('button', { name: 'Cancel' }))
    expect(onDecide).not.toHaveBeenCalled()
    expect(screen.queryByTestId('accept-confirm')).toBeNull()
  })

  it('Edit manually with the unchanged text cannot be saved as an edit; a text that differs only in spacing counts as unchanged', async () => {
    const { onDecide } = show()
    await userEvent.click(screen.getByRole('button', { name: /Edit manually/ }))
    expect(screen.getByLabelText('Clarified requirement text')).toHaveValue(fx.detail.original_text)
    expect(screen.getByTestId('unchanged-note')).toHaveTextContent('same as the original')
    expect(screen.getByRole('button', { name: 'Accept unchanged text' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Clarified requirement text'), { target: { value: '  ' + fx.detail.original_text.replace(/ /g, '   ') + '\n' } })
    expect(screen.getByRole('button', { name: 'Accept unchanged text' })).toBeDisabled()
    expect(onDecide).not.toHaveBeenCalled()
  })

  it('an explicit confirmation records the unchanged text as Accepted, never as Edited', async () => {
    const { onDecide } = show()
    await userEvent.click(screen.getByRole('button', { name: /Edit manually/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Keep the text unchanged/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Accept unchanged text' }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'accepted', note: null })
  })

  it('a changed text is saved as Edited', async () => {
    const { onDecide } = show()
    await userEvent.click(screen.getByRole('button', { name: /Edit manually/ }))
    fireEvent.change(screen.getByLabelText('Clarified requirement text'), { target: { value: 'The system shall notify users within 2 seconds.' } })
    expect(screen.queryByTestId('unchanged-note')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Save and update draft' }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'edited', edited_text: 'The system shall notify users within 2 seconds.', note: null })
  })
})

describe('DecisionCard after a decision', () => {
  it('shows a status card with the decision, date and note, and only Change decision and Remove decision', () => {
    show(decided())
    const card = screen.getByTestId('decision-card')
    expect(card).toHaveAttribute('data-status', 'accepted')
    expect(screen.getByTestId('decision-status')).toHaveTextContent('Accepted')
    expect(screen.getByTestId('decision-date')).toHaveTextContent('Decided')
    expect(screen.getByTestId('decision-note')).toHaveTextContent('looks fine')
    expect(within(card).getAllByRole('button').map((b) => b.textContent?.trim())).toEqual(['Change decision', 'Remove decision'])
    expect(screen.queryByRole('button', { name: 'Accept' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Reject/ })).toBeNull()
    expect(screen.queryByTestId('decision-history')).toBeNull()
    expect(card).not.toHaveTextContent(/history/i)
  })

  it('an edited decision shows the clarified text and the hint to regenerate', () => {
    show(decided({ decision: 'edited', edited_text: 'The system shall notify users within 2 seconds.', note: null }))
    expect(screen.getByTestId('edited-text')).toHaveTextContent('within 2 seconds')
    expect(screen.getByTestId('edited-text')).toHaveTextContent('The task draft is written again from this text')
    expect(screen.queryByTestId('decision-note')).toBeNull()
  })

  it('Change decision opens the choices again, prefilled, and Cancel goes back', async () => {
    const { onDecide } = show(decided())
    await userEvent.click(screen.getByRole('button', { name: 'Change decision' }))
    expect(screen.getByRole('button', { name: 'Accept' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Comment/)).toHaveValue('looks fine')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Change decision' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Change decision' }))
    await userEvent.click(screen.getByRole('button', { name: /Reject/ }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'rejected', note: 'looks fine' })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Change decision' })).toBeInTheDocument()) // saved: back to the status card
  })

  it('Remove decision asks first, and Cancel keeps the decision', async () => {
    const { onRemove } = show(decided())
    await userEvent.click(screen.getByRole('button', { name: 'Remove decision' }))
    const dialog = screen.getByRole('dialog', { name: 'Remove this decision?' })
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus() // Enter never confirms by accident
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(onRemove).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Remove decision' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove decision' }))
    expect(onRemove).toHaveBeenCalledTimes(1)
  })

  it('Escape closes the confirmation', async () => {
    show(decided())
    await userEvent.click(screen.getByRole('button', { name: 'Remove decision' }))
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})

describe('decisions in the Review Queue', () => {
  const put = (calls: { method: string; url: URL; body?: string }[]) => calls.filter((c) => c.method === 'PUT' && c.url.pathname === '/api/requirements/p1-REQ-001/decision')

  it('commits with PUT, then shows only Change decision and Remove decision (no history), and uses DELETE to remove it', async () => {
    let current: RequirementDetail['decision'] = null
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/requirements/p1-REQ-001/decision' && c.method === 'PUT') {
        const body = JSON.parse(c.body!)
        current = { decision: body.decision, edited_text: null, note: body.note ?? null, updated_at: '2026-10-14T09:30:00+00:00' }
        return json({ uid: 'p1-REQ-001', ...current })
      }
      if (c.url.pathname === '/api/requirements/p1-REQ-001/decision' && c.method === 'DELETE') {
        current = null
        return new Response(null, { status: 204 })
      }
      if (c.url.pathname === '/api/requirements/p1-REQ-001' && c.method === 'GET') return json({ ...fx.detail, decision: current })
      return undefined
    })
    renderApp('/requirement/review')
    await userEvent.click(await screen.findByRole('button', { name: 'Accept' }))
    await waitFor(() => expect(put(calls)).toHaveLength(1))
    expect(JSON.parse(put(calls)[0]!.body!)).toEqual({ decision: 'accepted', note: null })
    expect(calls.some((c) => c.method === 'POST' && c.url.pathname.endsWith('/decision'))).toBe(false)
    expect(await screen.findByRole('button', { name: 'Change decision' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Accept' })).toBeNull()
    expect(screen.queryByTestId('decision-history')).toBeNull()
    expect(await screen.findByText('REQ-001 marked accepted.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Remove decision' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove decision' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url.pathname === '/api/requirements/p1-REQ-001/decision')).toBe(true))
    expect(await screen.findByRole('button', { name: 'Accept' })).toBeInTheDocument()
  })

  it('a refused decision shows the message and keeps the choices', async () => {
    mockApi((c) => (c.method === 'PUT' && c.url.pathname.endsWith('/decision') ? json({ error: { code: 'invalid_decision', message: 'nope' } }, 400) : undefined))
    renderApp('/requirement/review')
    await userEvent.click(await screen.findByRole('button', { name: 'Accept' }))
    expect(await screen.findByText('Decision not saved: nope')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Accept' })).toBeEnabled()
  })

  it('edit manually saves the clarified text through PUT', async () => {
    const { calls } = mockApi((c) => (c.method === 'PUT' && c.url.pathname.endsWith('/decision') ? json({ uid: 'p1-REQ-001', decision: 'edited', edited_text: 'x', note: null, updated_at: 't' }) : undefined))
    renderApp('/requirement/review')
    await userEvent.click(await screen.findByRole('button', { name: /Edit manually/ }))
    fireEvent.change(screen.getByLabelText('Clarified requirement text'), { target: { value: 'The system shall notify users within 2 seconds.' } })
    await userEvent.click(screen.getByRole('button', { name: 'Save and update draft' }))
    await waitFor(() => expect(put(calls)).toHaveLength(1))
    expect(JSON.parse(put(calls)[0]!.body!)).toEqual({ decision: 'edited', edited_text: 'The system shall notify users within 2 seconds.', note: null })
  })
})
