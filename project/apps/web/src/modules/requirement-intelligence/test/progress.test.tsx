import { act, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TaskDrafts } from '../api/types'
import { DraftProgress } from '../components/DraftProgress'
import { barText, formatDuration, formatEta, formatRough, handledCount, percentHandled, segments } from '../lib/progress'
import * as fx from './fixtures'

const noop = () => undefined
const make = (o: Partial<TaskDrafts> = {}): TaskDrafts => ({ ...fx.summary.task_drafts, total: 44, generated: 27, needs_clarification: 7, failed: 0, not_generated: 10, in_progress: 10, queued: 10, ...o })
const panel = (d: TaskDrafts) => <DraftProgress drafts={d} onPause={noop} onResume={noop} onGenerateAll={noop} busy={false} analysing={false} />
const tick = (ms: number) => act(() => void vi.advanceTimersByTime(ms))
const eta = () => screen.getByTestId('draft-eta')

describe('percentage and "handled"', () => {
  it('handled = done + needs clarification + failed (+ manual review, which also needs no more machine work)', () => {
    expect(handledCount(make())).toBe(34)
    expect(handledCount(make({ failed: 2, manual_review: 1 }))).toBe(37)
  })

  it.each([
    [34, 44, 77], // 77.27
    [1, 3, 33],
    [2, 3, 67],
    [1, 8, 13], // 12.5 rounds up
    [0, 44, 0],
    [44, 44, 100],
    [43, 44, 98], // 97.7
  ])('%i of %i handled is %i%%', (handled, total, pct) => {
    expect(percentHandled(make({ total, generated: handled, needs_clarification: 0, failed: 0 }))).toBe(pct)
  })

  it('is 0 when there are no drafts at all', () => {
    expect(percentHandled(make({ total: 0, generated: 0, needs_clarification: 0 }))).toBe(0)
  })

  it('shows the percentage and "34 of 44 handled" next to the bar and keeps the counts line', () => {
    render(panel(make()))
    expect(screen.getByTestId('draft-percent')).toHaveTextContent('77%')
    expect(screen.getByTestId('draft-handled')).toHaveTextContent('34 of 44 handled')
    expect(screen.getByTestId('draft-counts')).toHaveTextContent('Drafts 27 of 44 done, 10 not generated, 7 needs clarification, 0 failed, 10 waiting')
  })
})

describe('segmented bar colours', () => {
  it('are explicit colours on the segments and on the legend dots (not class lookups)', () => {
    render(panel(make()))
    const parts = [...screen.getByTestId('draft-bar').querySelectorAll<HTMLElement>('[data-segment]')]
    expect(parts.map((p) => p.style.backgroundColor)).toEqual(['rgb(16, 185, 129)', 'rgb(245, 158, 11)', 'rgb(239, 68, 68)', 'rgb(203, 213, 225)'])
    for (const p of parts) expect(p.style.width).not.toBe('')
    expect(screen.getByTestId('draft-legend').querySelectorAll('li span[style]')).toHaveLength(4)
  })
})

describe('segmented bar', () => {
  it('has the aria values of the handled share and a readable text', () => {
    render(panel(make()))
    const bar = screen.getByRole('progressbar', { name: 'Draft progress' })
    expect(bar).toHaveAttribute('aria-valuemin', '0')
    expect(bar).toHaveAttribute('aria-valuemax', '44')
    expect(bar).toHaveAttribute('aria-valuenow', '34')
    expect(bar).toHaveAttribute('aria-valuetext', '34 of 44 handled (77%): 27 done, 7 need clarification, 0 failed, 10 waiting')
  })

  it('has one segment per kind, sized by its count, and the parts add up to the whole', () => {
    const d = make({ failed: 3, in_progress: 7, queued: 7 })
    render(panel(d))
    const bar = screen.getByTestId('draft-bar')
    const get = (k: string) => bar.querySelector(`[data-segment="${k}"]`) as HTMLElement
    expect(get('done')).toHaveAttribute('data-count', '27')
    expect(get('clarify')).toHaveAttribute('data-count', '7')
    expect(get('failed')).toHaveAttribute('data-count', '3')
    expect(get('waiting')).toHaveAttribute('data-count', '7')
    expect(parseFloat(get('done').style.width)).toBeCloseTo((27 / 44) * 100, 3)
    const sum = segments(d).reduce((n, s) => n + s.count, 0)
    expect(sum).toBe(44)
    expect(get('failed')).toHaveAttribute('title', 'Failed: 3')
  })

  it('has a legend with the four kinds and their counts', () => {
    render(panel(make({ failed: 3 })))
    const legend = within(screen.getByTestId('draft-legend'))
    expect(legend.getByText('Done 27')).toBeInTheDocument()
    expect(legend.getByText('Needs clarification 7')).toBeInTheDocument()
    expect(legend.getByText('Failed 3')).toBeInTheDocument()
    expect(legend.getByText('Waiting 10')).toBeInTheDocument()
  })

  it('counts manual review as failed in the bar text', () => {
    expect(barText(make({ failed: 1, manual_review: 2 }))).toContain('3 failed')
  })
})

describe('duration text', () => {
  it('uses whole minutes and "under 1 min"', () => {
    expect(formatDuration(0)).toBe('under 1 min')
    expect(formatDuration(59)).toBe('under 1 min')
    expect(formatDuration(60)).toBe('1 min')
    expect(formatDuration(61)).toBe('2 min')
    expect(formatDuration(3540)).toBe('59 min')
    expect(formatDuration(3599)).toBe('1 h 0 min')
    expect(formatDuration(3660)).toBe('1 h 1 min')
    expect(formatEta(30)).toBe('Under 1 min left')
    expect(formatEta(420)).toBe('About 7 min left')
    expect(formatRough(30)).toBe('Rough estimate: under 1 min left')
    expect(formatRough(240)).toBe('Rough estimate: ~4 min left')
  })
})

describe('time left and stall warning (clock under test control)', () => {
  beforeEach(() => vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] }))
  afterEach(() => vi.useRealTimers())

  it('0 finished: "Calculating…" and no invented number', () => {
    render(panel(make()))
    tick(30_000)
    expect(eta()).toHaveTextContent('Calculating…')
    expect(eta().textContent).not.toMatch(/\d+ min/)
  })

  it('1 or 2 finished and no API estimate yet: a clearly labelled rough estimate from the throughput so far', () => {
    const { rerender } = render(panel(make()))
    tick(1000) // the page starts watching
    rerender(panel(make({ generated: 28, in_progress: 4, queued: 4 }))) // one draft finished
    tick(59_000)
    expect(eta()).toHaveTextContent('Rough estimate: ~4 min left') // 4 waiting at 1 draft per 59 s
    rerender(panel(make({ generated: 29, in_progress: 3, queued: 3 })))
    tick(1000)
    expect(eta()).toHaveTextContent(/^Rough estimate: ~\d+ min left$/)
  })

  it('a rough estimate under a minute says "under 1 min"', () => {
    const { rerender } = render(panel(make()))
    tick(1000)
    rerender(panel(make({ generated: 28, in_progress: 1, queued: 1 })))
    tick(30_000)
    expect(eta()).toHaveTextContent('Rough estimate: under 1 min left')
  })

  it('the API estimate (3 or more finished) replaces the rough one: "About N min left"', () => {
    const { rerender } = render(panel(make()))
    tick(1000)
    rerender(panel(make({ generated: 28, in_progress: 4, queued: 4 })))
    tick(5000)
    expect(eta()).toHaveTextContent('Rough estimate')
    rerender(panel(make({ generated: 30, in_progress: 2, queued: 2, eta_seconds: 420, latency_samples: 3 })))
    expect(eta()).toHaveTextContent(/^About 7 min left$/)
    expect(eta()).not.toHaveTextContent('Rough')
  })

  it('warns calmly when no draft finished for more than 3 minutes, and never switches anything', () => {
    const onPause = vi.fn()
    const { rerender } = render(<DraftProgress drafts={make()} onPause={onPause} onResume={noop} onGenerateAll={noop} busy={false} analysing={false} />)
    tick(170_000)
    expect(screen.queryByTestId('draft-stall')).toBeNull()
    tick(20_000)
    const warning = screen.getByTestId('draft-stall')
    expect(warning).toHaveTextContent('No draft has finished for 3 minutes. The server may be slow or unreachable.')
    expect(warning).toHaveTextContent('Pause')
    tick(60_000)
    expect(screen.getByTestId('draft-stall')).toHaveTextContent('for 4 minutes')
    expect(onPause).not.toHaveBeenCalled()
    // a finished draft clears it
    rerender(<DraftProgress drafts={make({ generated: 28, in_progress: 9, queued: 9 })} onPause={onPause} onResume={noop} onGenerateAll={noop} busy={false} analysing={false} />)
    tick(1000)
    expect(screen.queryByTestId('draft-stall')).toBeNull()
  })

  it('a paused queue never shows the warning', () => {
    render(panel(make({ paused: true })))
    tick(600_000)
    expect(screen.queryByTestId('draft-stall')).toBeNull()
  })

  it('no warning when nothing is in progress', () => {
    render(panel(make({ in_progress: 0, queued: 0, not_generated: 10 })))
    tick(600_000)
    expect(screen.queryByTestId('draft-stall')).toBeNull()
  })
})
