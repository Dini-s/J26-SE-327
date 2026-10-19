import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { RequirementRow } from '../api/types'
import * as fx from './fixtures'
import { json, mockApi, renderApp } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  window.localStorage.clear()
})

const REVIEW = '/requirement/review'
const SIZE_KEY = 'requirement-intelligence.pageSize'
const many = (n: number): RequirementRow[] => Array.from({ length: n }, (_, i) => ({ ...fx.rows[i % 3]!, uid: `p1-REQ-${String(i + 1).padStart(3, '0')}`, id: `REQ-${String(i + 1).padStart(3, '0')}` }))
const serve = (n: number) => (c: { url: URL }) => {
  if (c.url.pathname !== '/api/projects/1/requirements') return undefined
  const items = many(n)
  return json({ total: n, limit: 500, offset: 0, items })
}
const rowIds = () => screen.getAllByTestId('finding-row').map((r) => within(r).getByText(/^REQ-\d+$/).textContent)
const showing = () => screen.getByTestId('pager-showing').textContent

describe('Review Queue: pages', () => {
  it('shows 50 requirements per page with “Showing 1-20 of N”, and previous / next', async () => {
    mockApi(serve(120))
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    expect(rowIds()).toHaveLength(50)
    expect(rowIds()[0]).toBe('REQ-001')
    expect(showing()).toBe('Showing 1-50 of 120')
    expect(screen.getByTestId('pager-previous')).toBeDisabled()
    await userEvent.click(screen.getByTestId('pager-next'))
    expect(showing()).toBe('Showing 51-100 of 120')
    expect(rowIds()[0]).toBe('REQ-051')
    expect(screen.getByTestId('pager')).toHaveTextContent('Page 2 of 3')
    await userEvent.click(screen.getByTestId('pager-next'))
    expect(showing()).toBe('Showing 101-120 of 120')
    expect(rowIds()).toHaveLength(20)
    expect(screen.getByTestId('pager-next')).toBeDisabled()
    await userEvent.click(screen.getByTestId('pager-previous'))
    expect(showing()).toBe('Showing 51-100 of 120')
  })

  it('a short list has no previous / next', async () => {
    mockApi()
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    expect(showing()).toBe('Showing 1-3 of 3')
    expect(screen.queryByTestId('pager-next')).toBeNull()
    expect(screen.queryByTestId('pager-previous')).toBeNull()
  })

  it('“See all” shows every requirement and is remembered', async () => {
    mockApi(serve(120))
    const first = renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    expect(screen.getByTestId('page-size-50')).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByTestId('page-size-all'))
    expect(rowIds()).toHaveLength(120)
    expect(showing()).toBe('Showing all 120')
    expect(screen.queryByTestId('pager-next')).toBeNull()
    expect(window.localStorage.getItem(SIZE_KEY)).toBe('all')
    first.unmount()
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    expect(rowIds()).toHaveLength(120)
    expect(screen.getByTestId('page-size-all')).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByTestId('page-size-50'))
    expect(rowIds()).toHaveLength(50)
    expect(window.localStorage.getItem(SIZE_KEY)).toBe('50')
  })

  it('works when the browser blocks storage', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    mockApi(serve(120))
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    expect(rowIds()).toHaveLength(50)
    await userEvent.click(screen.getByTestId('page-size-all'))
    expect(rowIds()).toHaveLength(120)
  })

  it('a filter, a status or a search goes back to page 1', async () => {
    mockApi(serve(120))
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('pager-next'))
    expect(showing()).toBe('Showing 51-100 of 120')
    await userEvent.click(screen.getByTestId('status-pending'))
    expect(showing()).toBe('Showing 1-50 of 120')
    await userEvent.click(screen.getByTestId('pager-next'))
    await userEvent.click(screen.getByTestId('filters-button'))
    await userEvent.selectOptions(screen.getByLabelText('Suggested action'), 'edit')
    expect(showing()).toMatch(/^Showing 1-50 of /)
    await userEvent.click(screen.getByTestId('pager-next'))
    await userEvent.type(screen.getByRole('searchbox'), 'x')
    await waitFor(() => expect(showing()).toMatch(/^Showing 1-/))
  })

  it('the selection survives paging', async () => {
    mockApi(serve(120))
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('select-mode'))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select REQ-002' }))
    await userEvent.click(screen.getByTestId('pager-next'))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select REQ-055' }))
    expect(screen.getByTestId('selected-count')).toHaveTextContent('2 selected')
    await userEvent.click(screen.getByTestId('pager-previous'))
    expect(screen.getByRole('checkbox', { name: 'Select REQ-002' })).toBeChecked()
    expect(screen.getByTestId('selected-count')).toHaveTextContent('2 selected')
  })

  it('previous, next and the page size work from the keyboard', async () => {
    mockApi(serve(120))
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    screen.getByTestId('pager-next').focus()
    await userEvent.keyboard('{Enter}')
    expect(showing()).toBe('Showing 51-100 of 120')
    await userEvent.tab({ shift: true })
    expect(screen.getByTestId('pager-previous')).toHaveFocus()
    await userEvent.keyboard(' ')
    expect(showing()).toBe('Showing 1-50 of 120')
    screen.getByTestId('page-size-all').focus()
    await userEvent.keyboard('{Enter}')
    expect(rowIds()).toHaveLength(120)
    expect(screen.getByRole('navigation', { name: 'Pages' })).toBeInTheDocument()
  })
})

describe('Review Queue: select and accept', () => {
  const decisions = (calls: { method: string; url: URL; body?: string }[]) => calls.filter((c) => c.method === 'PUT' && c.url.pathname.endsWith('/decision'))
  const accepting = (extra?: (c: { url: URL; method: string }) => Response | undefined) => (c: { url: URL; method: string }) => {
    if (c.method === 'PUT' && c.url.pathname.endsWith('/decision')) return json({ uid: c.url.pathname.split('/')[3], decision: 'accepted', edited_text: null, note: null, decided_at: '2026-10-20T08:00:00+00:00' })
    return extra?.(c) ?? serve(120)(c)
  }

  it('the page size is 50 with the choices 50 | See all', async () => {
    mockApi(serve(120))
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    expect(within(screen.getByRole('group', { name: 'Per page' })).getAllByRole('button').map((b) => b.textContent)).toEqual(['50', 'See all'])
  })

  it('“Select all shown” takes the page, “Select all N” takes the whole list, and the choice survives paging', async () => {
    mockApi(serve(120))
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('select-mode'))
    await userEvent.click(screen.getByTestId('select-shown'))
    expect(screen.getByTestId('selected-count')).toHaveTextContent('50 selected')
    await userEvent.click(screen.getByTestId('pager-next'))
    expect(screen.getByTestId('selected-count')).toHaveTextContent('50 selected')
    expect(screen.getByRole('checkbox', { name: 'Select REQ-051' })).not.toBeChecked()
    await userEvent.click(screen.getByTestId('select-all-n'))
    expect(screen.getByTestId('select-all-n')).toHaveTextContent('Select all 120')
    expect(screen.getByTestId('selected-count')).toHaveTextContent('120 selected')
    expect(screen.getByRole('checkbox', { name: 'Select REQ-051' })).toBeChecked()
    await userEvent.click(screen.getByTestId('select-clear'))
    expect(screen.getByTestId('selected-count')).toHaveTextContent('0 selected')
  })

  it('Accept selected (N) asks first, then makes one accepted decision per requirement', async () => {
    const { calls } = mockApi(accepting())
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('select-mode'))
    expect(screen.getByTestId('accept-selected')).toBeDisabled()
    await userEvent.click(screen.getByTestId('select-all-n'))
    expect(screen.getByTestId('accept-selected')).toHaveTextContent('Accept selected (120)')
    await userEvent.click(screen.getByTestId('accept-selected'))
    expect(decisions(calls)).toHaveLength(0) // nothing before the confirmation
    const dialog = screen.getByRole('dialog', { name: 'Accept the selected requirements?' })
    expect(dialog).toHaveTextContent('120 requirements will be accepted as they are, one decision each, and recorded in the history.')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Accept' }))
    expect(await screen.findByText('120 requirements accepted.')).toBeInTheDocument()
    expect(decisions(calls)).toHaveLength(120)
    expect(new Set(decisions(calls).map((c) => c.url.pathname)).size).toBe(120) // each requirement once
    expect(JSON.parse(decisions(calls)[0]!.body!)).toEqual({ decision: 'accepted', note: 'Accepted from a selection' })
    expect(screen.getByTestId('selected-count')).toHaveTextContent('0 selected')
  })

  it('Cancel in the confirmation changes nothing', async () => {
    const { calls } = mockApi(accepting())
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('select-mode'))
    await userEvent.click(screen.getByTestId('select-shown'))
    await userEvent.click(screen.getByTestId('accept-selected'))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))
    expect(decisions(calls)).toHaveLength(0)
    expect(screen.getByTestId('selected-count')).toHaveTextContent('50 selected')
  })

  it('requirements that already have a decision are left as they are and not counted', async () => {
    const decided = (c: { url: URL }) => {
      if (c.url.pathname !== '/api/projects/1/requirements') return undefined
      const items = many(60).map((r, i) => (i < 10 ? { ...r, decision: 'rejected' as const } : r))
      return json({ total: 60, limit: 500, offset: 0, items })
    }
    const { calls } = mockApi(accepting(decided))
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('select-mode'))
    await userEvent.click(screen.getByTestId('select-all-n'))
    expect(screen.getByTestId('accept-selected')).toHaveTextContent('Accept selected (50)')
    await userEvent.click(screen.getByTestId('accept-selected'))
    expect(screen.getByRole('dialog')).toHaveTextContent('10 selected requirements already have a decision and are left unchanged.')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Accept' }))
    await screen.findByText('50 requirements accepted.')
    expect(decisions(calls)).toHaveLength(50)
  })

  it('says how many decisions could not be saved', async () => {
    let n = 0
    mockApi((c) => {
      if (c.method === 'PUT' && c.url.pathname.endsWith('/decision')) {
        n += 1
        return n <= 3 ? json({ error: { code: 'internal', message: 'boom' } }, 500) : json({ uid: 'x', decision: 'accepted', edited_text: null, note: null, decided_at: '2026-10-20T08:00:00+00:00' })
      }
      return serve(120)(c)
    })
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('select-mode'))
    await userEvent.click(screen.getByTestId('select-shown'))
    await userEvent.click(screen.getByTestId('accept-selected'))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Accept' }))
    expect(await screen.findByText('47 requirements accepted. 3 decisions could not be saved.')).toBeInTheDocument()
  })
})
