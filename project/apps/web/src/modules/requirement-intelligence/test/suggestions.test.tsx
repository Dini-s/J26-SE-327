import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DecisionIn, RequirementDetail, RequirementRow } from '../api/types'
import { DecisionCard } from '../components/DecisionCard'
import { DraftCard } from '../components/DraftCard'
import * as fx from './fixtures'
import { json, mockApi, renderApp } from './utils'

afterEach(() => vi.unstubAllGlobals())

const accept = { action: 'accept' as const, reasons: ['Clear wording, no open questions, low risk, no conflict or duplicate.'] }
const reject = { action: 'reject' as const, reasons: ['Repeats REQ-001, which comes earlier; keep the first and drop this copy.'] }
const withSuggestion = (s: RequirementDetail['suggestion']): RequirementDetail => ({ ...fx.detail, suggestion: s })

function show(detail: RequirementDetail) {
  const onDecide = vi.fn<(b: DecisionIn) => Promise<boolean>>(async () => true)
  render(<DecisionCard detail={detail} busy={false} onDecide={onDecide} onRemove={async () => true} />)
  return { onDecide }
}

describe('Suggestion panel in the decision card', () => {
  it('shows the suggested action and the reasons, and says it is not a decision', () => {
    show(fx.detail)
    const panel = screen.getByTestId('suggestion-panel')
    expect(within(panel).getByTestId('suggestion-action')).toHaveTextContent('Suggested: Edit')
    expect(within(panel).getByTestId('suggestion-reasons')).toHaveTextContent('The wording is unclear.')
    expect(panel).toHaveTextContent('not a decision')
  })

  it('Accept: asks for confirmation and saves nothing until it is confirmed', async () => {
    const { onDecide } = show(withSuggestion(accept))
    await userEvent.click(screen.getByRole('button', { name: 'Use this suggestion' }))
    const confirm = screen.getByTestId('accept-confirm')
    expect(confirm).toHaveTextContent('Accept this requirement as suggested?')
    expect(onDecide).not.toHaveBeenCalled()
    await userEvent.click(within(confirm).getByRole('button', { name: 'Accept' }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'accepted', note: null })
  })

  it('Edit: opens the box filled with the original text and saves nothing', async () => {
    const { onDecide } = show(fx.detail)
    expect(screen.queryByLabelText('Clarified requirement text')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Use this suggestion' }))
    expect(screen.getByLabelText('Clarified requirement text')).toHaveValue(fx.detail.original_text)
    expect(onDecide).not.toHaveBeenCalled()
  })

  it('Reject: fills the comment and saves nothing', async () => {
    const { onDecide } = show(withSuggestion(reject))
    await userEvent.click(screen.getByRole('button', { name: 'Use this suggestion' }))
    expect(screen.getByLabelText(/Comment/)).toHaveValue(reject.reasons[0])
    expect(onDecide).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /Reject/ }))
    expect(onDecide).toHaveBeenCalledWith({ decision: 'rejected', note: reject.reasons[0] })
  })

  it('labels the comment as not used to write drafts', () => {
    show(fx.detail)
    expect(screen.getByLabelText('Comment (optional, not used to write drafts)')).toBeInTheDocument()
  })
})

describe('hint for a draft that needs clarification', () => {
  const asking = { ...fx.detail, generation: { ...fx.generationDone, state: 'needs_clarification' as const, status: 'needs_clarification', clarification_questions: ['How quickly?'] } }
  const hint = 'Use Edit manually to write the clarified requirement; a new draft is created from it.'

  it('is shown while there is no decision', () => {
    show(asking)
    expect(screen.getByTestId('clarify-hint')).toHaveTextContent(hint)
  })

  it('is not shown for a finished draft or after a decision', () => {
    show(fx.detail)
    expect(screen.queryByTestId('clarify-hint')).toBeNull()
  })

  it('is not shown once the requirement has a decision', () => {
    show({ ...asking, decision: { decision: 'accepted', edited_text: null, note: null, updated_at: '2026-10-14T09:30:00+00:00' } })
    expect(screen.queryByTestId('clarify-hint')).toBeNull()
  })
})

describe('DraftCard while a draft is rewritten from edited text', () => {
  const card = (state: 'queued' | 'running' | 'done', updating: boolean) =>
    render(<DraftCard generation={{ ...fx.generationDone, state, generated_from: state === 'done' ? 'clarified' : '' }} onGenerate={() => undefined} busy={false} updating={updating} />)

  it.each(['queued', 'running'] as const)('says "Updating draft…" when %s', (state) => {
    card(state, true)
    expect(screen.getByTestId('draft-updating')).toHaveTextContent('Updating draft…')
    expect(screen.queryByText(/Waiting in the queue/)).toBeNull()
  })

  it('keeps the normal wording when the draft is not being rewritten', () => {
    card('queued', false)
    expect(screen.queryByTestId('draft-updating')).toBeNull()
    expect(screen.getByText(/Waiting in the queue/)).toBeInTheDocument()
  })

  it('then shows the result with its origin', () => {
    card('done', true)
    expect(screen.queryByTestId('draft-updating')).toBeNull()
    expect(screen.getByTestId('from-clarified')).toHaveTextContent('Generated by AI from your edited text')
  })
})

async function suggestFilter(value: string) {
  if (!screen.queryByTestId('filters-panel')) await userEvent.click(screen.getByTestId('filters-button'))
  await userEvent.selectOptions(screen.getByLabelText('Suggested action'), value)
}

describe('Review Queue: suggestions on the list', () => {
  const rows: RequirementRow[] = [
    { ...fx.rows[0]!, suggestion: accept },
    { ...fx.rows[1]!, suggestion: accept },
    { ...fx.rows[2]!, suggestion: reject },
    { ...fx.rows[0]!, uid: 'p1-REQ-004', id: 'REQ-004', decision: 'accepted', suggestion: accept },
  ]
  const list = (c: { url: URL }) => (c.url.pathname === '/api/projects/1/requirements' ? json({ total: rows.length, limit: 500, offset: 0, items: rows }) : undefined)

  it('shows "Suggested: …" on pending rows and the decision on decided rows', async () => {
    mockApi(list)
    renderApp('/requirement/review')
    const items = await screen.findAllByTestId('finding-row')
    const chips = screen.getAllByTestId('row-suggestion')
    expect(chips.map((c) => c.textContent)).toEqual(['Suggested: Accept', 'Suggested: Accept', 'Suggested: Reject'])
    expect(within(items[3]!).queryByTestId('row-suggestion')).toBeNull()
    expect(within(items[3]!).getByTestId('row-decision')).toHaveTextContent('Accepted')
  })

  it('filters by suggested action', async () => {
    mockApi(list)
    renderApp('/requirement/review')
    await screen.findAllByTestId('finding-row')
    await suggestFilter('reject')
    expect(screen.getAllByTestId('finding-row')).toHaveLength(1)
    expect(screen.getByTestId('row-suggestion')).toHaveTextContent('Suggested: Reject')
  })

  it('offers the bulk accept only for Pending + Suggested: Accept', async () => {
    mockApi(list)
    renderApp('/requirement/review')
    await screen.findAllByTestId('finding-row')
    await suggestFilter('accept')
    expect(screen.queryByTestId('bulk-accept')).toBeNull()
    await userEvent.click(screen.getByTestId('status-pending'))
    expect(screen.getByTestId('bulk-accept')).toHaveTextContent('Accept 2 suggested requirements')
    await suggestFilter('edit')
    expect(screen.queryByTestId('bulk-accept')).toBeNull()
  })

  it('confirms first, accepts with the fixed comment, skips one that changed and reports the numbers', async () => {
    const decided = new Set<string>()
    const { calls } = mockApi((c) => {
      const listed = list(c)
      if (listed) return listed
      const one = /^\/api\/requirements\/(p1-REQ-\d+)$/.exec(c.url.pathname)
      if (one && c.method === 'GET') {
        const uid = one[1]!
        // REQ-002 was decided by someone else after the list was loaded
        const decision = uid === 'p1-REQ-002' ? { decision: 'rejected' as const, edited_text: null, note: null, updated_at: 't' } : decided.has(uid) ? { decision: 'accepted' as const, edited_text: null, note: null, updated_at: 't' } : null
        return json({ ...fx.detail, uid, id: uid.slice(3), suggestion: accept, decision })
      }
      const put = /^\/api\/requirements\/(p1-REQ-\d+)\/decision$/.exec(c.url.pathname)
      if (put && c.method === 'PUT') {
        decided.add(put[1]!)
        return json({ uid: put[1], decision: 'accepted', edited_text: null, note: 'Accepted from suggestion', updated_at: 't' })
      }
      return undefined
    })
    renderApp('/requirement/review')
    await screen.findAllByTestId('finding-row')
    await suggestFilter('accept')
    await userEvent.click(screen.getByTestId('status-pending'))
    await userEvent.click(screen.getByTestId('bulk-accept'))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('2 pending requirements are suggested for acceptance')
    expect(calls.some((c) => c.method === 'PUT')).toBe(false) // nothing is saved before the confirmation
    await userEvent.click(within(dialog).getByRole('button', { name: 'Accept all' }))
    expect(await screen.findByText('Accepted 1 requirement. 1 skipped (already decided or no longer suggested).')).toBeInTheDocument()
    const puts = calls.filter((c) => c.method === 'PUT')
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0]!.url.pathname).toBe('/api/requirements/p1-REQ-001/decision')
    expect(JSON.parse(puts[0]!.body!)).toEqual({ decision: 'accepted', note: 'Accepted from suggestion' })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('Cancel on the confirmation saves nothing', async () => {
    const { calls } = mockApi(list)
    renderApp('/requirement/review')
    await screen.findAllByTestId('finding-row')
    await suggestFilter('accept')
    await userEvent.click(screen.getByTestId('status-pending'))
    await userEvent.click(screen.getByTestId('bulk-accept'))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)
  })
})

describe('Regenerate when the text has not changed (Review Queue)', () => {
  const asking = { ...fx.generationDone, state: 'needs_clarification' as const, status: 'needs_clarification', clarification_questions: ['How quickly?'] }
  const line = 'Edit the requirement text to get a new draft. The same text gives the same result.'

  it('disables Regenerate and says why while the draft needs clarification and the text is the original', async () => {
    mockApi((c) => (c.url.pathname === '/api/requirements/p1-REQ-001' ? json({ ...fx.detail, generation: asking }) : undefined))
    renderApp('/requirement/review')
    expect(await screen.findByTestId('same-text-note')).toHaveTextContent(line)
    expect(within(screen.getByTestId('draft-card')).getByRole('button', { name: 'Regenerate' })).toBeDisabled()
  })

  it('enables it again once the requirement has an edited decision', async () => {
    const edited = { decision: 'edited' as const, edited_text: 'The system shall notify users within 2 seconds.', note: null, updated_at: '2026-10-14T09:30:00+00:00' }
    mockApi((c) => (c.url.pathname === '/api/requirements/p1-REQ-001' ? json({ ...fx.detail, generation: asking, decision: edited }) : undefined))
    renderApp('/requirement/review')
    await screen.findByTestId('draft-card')
    expect(screen.queryByTestId('same-text-note')).toBeNull()
    expect(within(screen.getByTestId('draft-card')).getByRole('button', { name: 'Regenerate' })).toBeEnabled()
  })

  it('does not apply to a finished draft', async () => {
    mockApi()
    renderApp('/requirement/review')
    await screen.findByTestId('draft-card')
    expect(screen.queryByTestId('same-text-note')).toBeNull()
    expect(within(screen.getByTestId('draft-card')).getByRole('button', { name: 'Regenerate' })).toBeEnabled()
  })
})

describe('save button of the edit form', () => {
  it('is "Accept unchanged text" for the original text and "Save and update draft" for a changed one', async () => {
    show(fx.detail)
    await userEvent.click(screen.getByRole('button', { name: /Edit manually/ }))
    expect(screen.getByRole('button', { name: 'Accept unchanged text' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Clarified requirement text'), ' within 2 seconds')
    expect(screen.getByRole('button', { name: 'Save and update draft' })).toBeEnabled()
  })

  it('scrolls the task draft card into view after an edit is saved', async () => {
    const scroll = vi.fn()
    Element.prototype.scrollIntoView = scroll
    mockApi((c) => (c.method === 'PUT' && c.url.pathname.endsWith('/decision') ? json({ uid: 'p1-REQ-001', decision: 'edited', edited_text: 'x', note: null, updated_at: 't' }) : undefined))
    renderApp('/requirement/review')
    await userEvent.click(await screen.findByRole('button', { name: /Edit manually/ }))
    await userEvent.type(screen.getByLabelText('Clarified requirement text'), ' within 2 seconds')
    await userEvent.click(screen.getByRole('button', { name: 'Save and update draft' }))
    await waitFor(() => expect(scroll).toHaveBeenCalled())
    delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView
  })
})
