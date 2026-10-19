import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Generation, GenerationState } from '../api/types'
import { DraftCard } from '../components/DraftCard'
import { RequirementRowItem } from '../components/RequirementList'
import { HighlightLegend, HighlightedText } from '../components/HighlightedText'
import { RiskBadge } from '../components/ui'
import { classifierConfidence, highlightSegments, markSegments, primaryType, sourceLabel } from '../lib/format'
import * as fx from './fixtures'

describe('RiskBadge', () => {
  it.each([
    ['HIGH', 'HIGH', 'text-danger-text'],
    ['MEDIUM', 'MEDIUM', 'text-warning-text'],
    ['LOW', 'LOW', 'text-success-text'],
    ['NONE', 'NONE', 'text-neutral'],
  ] as const)('renders %s with its colours', (level, text, cls) => {
    render(<RiskBadge level={level} />)
    const badge = screen.getByTestId('risk-badge')
    expect(badge).toHaveTextContent(text)
    expect(badge).toHaveAttribute('data-level', level)
    expect(badge.className).toContain(cls)
  })

  it('adds the word RISK in the long form', () => {
    render(<RiskBadge level="HIGH" long />)
    expect(screen.getByTestId('risk-badge')).toHaveTextContent('HIGH RISK')
  })
})

describe('weak-word highlighting', () => {
  it('marks the spans returned by the API and keeps the rest of the text', () => {
    const text = 'The system should quickly notify users.'
    const { container } = render(<HighlightedText text={text} spans={[{ word: 'quickly', start: 18, end: 25 }]} />)
    const marks = container.querySelectorAll('mark')
    expect(marks).toHaveLength(1)
    expect(marks[0]).toHaveTextContent('quickly')
    expect(container.textContent).toBe(text)
  })

  it('handles several words, overlaps and bad offsets without losing text', () => {
    const text = 'easy to use and appropriate'
    const segs = highlightSegments(text, [
      { word: 'appropriate', start: 16, end: 27 },
      { word: 'easy', start: 0, end: 4 },
      { word: 'overlap', start: 2, end: 8 },
      { word: 'bad', start: 40, end: 50 },
    ])
    expect(segs.filter((s) => s.hit).map((s) => s.text)).toEqual(['easy', 'appropriate'])
    expect(segs.map((s) => s.text).join('')).toBe(text)
  })

  it('returns the plain text when there are no spans', () => {
    expect(highlightSegments('plain', [])).toEqual([{ text: 'plain', hit: false }])
  })
})

describe('format helpers', () => {
  it('shows the finding type of a row, most serious first', () => {
    expect(primaryType({ ambiguity: true, conflict: true, duplicate: true, security: true })).toBe('conflict')
    expect(primaryType({ ambiguity: true, conflict: false, duplicate: true, security: false })).toBe('ambiguity')
    expect(primaryType({ ambiguity: false, conflict: false, duplicate: false, security: false })).toBe('none')
  })

  it('writes the source reference like the mockup', () => {
    expect(sourceLabel('a.pdf', 12, 3)).toBe('a.pdf · Page 12, paragraph 3')
    expect(sourceLabel('a.txt', null, 2)).toBe('a.txt · paragraph 2')
    expect(sourceLabel('a.txt', null, null)).toBe('a.txt')
  })

  it('reports the probability of the predicted class as confidence', () => {
    expect(classifierConfidence({ fr_nfr: 'NFR', nfr_probability: 0.84 })).toBeCloseTo(0.84)
    expect(classifierConfidence({ fr_nfr: 'FR', nfr_probability: 0.12 })).toBeCloseTo(0.88)
  })
})

describe('vague terms (rule-based) are marked apart from weak words', () => {
  const text = 'The system should process payments quickly and be user-friendly.'
  const at = (w: string) => ({ term: w, start: text.indexOf(w), end: text.indexOf(w) + w.length })
  const vague = [at('quickly'), at('user-friendly')]

  it('markSegments keeps the two kinds apart and lets the weak word win on the same characters', () => {
    const marks = markSegments(text, [{ word: 'quickly', start: text.indexOf('quickly'), end: text.indexOf('quickly') + 7 }], vague)
    expect(marks.filter((m) => m.kind).map((m) => [m.kind, m.text])).toEqual([['weak', 'quickly'], ['vague', 'user-friendly']])
    expect(marks.map((m) => m.text).join('')).toBe(text)
    expect(markSegments(text, [], []).every((m) => m.kind === null)).toBe(true)
    expect(markSegments(text, [], [{ term: 'x', start: 5, end: 999 }]).every((m) => m.kind === null)).toBe(true) // bad offsets are ignored
  })

  it('renders vague terms with their own label and style, not the weak-word one', () => {
    render(<p><HighlightedText text={text} spans={[]} vague={vague} /></p>)
    const marks = document.querySelectorAll('mark')
    expect([...marks].map((m) => m.textContent)).toEqual(['quickly', 'user-friendly'])
    for (const m of marks) {
      expect(m).toHaveAttribute('data-kind', 'vague')
      expect(m).toHaveAttribute('title', 'Vague term (rule-based)')
    }
  })

  it('legend names only the styles that appear', () => {
    const { rerender } = render(<HighlightLegend text={text} spans={[]} vague={vague} />)
    expect(screen.getByTestId('highlight-legend')).toHaveTextContent('Vague term (rule-based)')
    expect(screen.getByTestId('highlight-legend')).not.toHaveTextContent('Weak word')
    rerender(<HighlightLegend text={text} spans={[{ word: 'quickly', start: text.indexOf('quickly'), end: text.indexOf('quickly') + 7 }]} vague={vague} />)
    expect(screen.getByTestId('highlight-legend')).toHaveTextContent('Weak word')
    rerender(<HighlightLegend text={text} spans={[]} vague={[]} />)
    expect(screen.queryByTestId('highlight-legend')).toBeNull()
  })
})

describe('AI clarification visibility', () => {
  it('a row shows the badge only when the model asked for clarification', () => {
    const { rerender } = render(<ul><RequirementRowItem row={{ ...fx.rows[0]!, generation_state: 'needs_clarification' }} selected={false} onSelect={() => undefined} /></ul>)
    expect(screen.getByTestId('ai-clarify-badge')).toHaveTextContent('AI asked for clarification')
    for (const state of ['done', 'failed', 'manual_review', 'not_requested'] as const) {
      rerender(<ul><RequirementRowItem row={{ ...fx.rows[0]!, generation_state: state }} selected={false} onSelect={() => undefined} /></ul>)
      expect(screen.queryByTestId('ai-clarify-badge')).toBeNull()
    }
  })
})

describe('DraftCard states', () => {
  const base: Generation = { ...fx.generationDone, state: 'not_requested', message: '', status: null, user_story: '', technical_task: '', acceptance_criteria: [], rationale: '', attempts: 0 }
  const show = (g: Partial<Generation>) => {
    const onGenerate = vi.fn()
    render(<DraftCard generation={{ ...base, ...g }} onGenerate={onGenerate} busy={false} />)
    return { onGenerate, card: screen.getByTestId('draft-card') }
  }

  it('not requested: offers to generate', async () => {
    const { onGenerate, card } = show({})
    expect(card).toHaveAttribute('data-state', 'not_requested')
    expect(card).toHaveTextContent('Not written yet')
    await userEvent.click(screen.getByRole('button', { name: /Generate draft/ }))
    expect(onGenerate).toHaveBeenCalledTimes(1)
  })

  it('queued: says it is waiting and cannot be started again', () => {
    show({ state: 'queued' })
    expect(screen.getByText(/Waiting in the queue/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Regenerate/ })).toBeDisabled()
  })

  it('running: shows the spinner text', () => {
    show({ state: 'running' })
    expect(screen.getByRole('status')).toHaveTextContent('The AI is writing a draft')
    expect(screen.getByRole('button', { name: /Regenerate/ })).toBeDisabled()
  })

  it('done: shows story, task, criteria and rationale', async () => {
    const { onGenerate, card } = show(fx.generationDone)
    expect(card).toHaveAttribute('data-state', 'done')
    expect(card).toHaveTextContent(fx.generationDone.user_story)
    expect(card).toHaveTextContent(fx.generationDone.technical_task)
    expect(within(card).getAllByRole('listitem')).toHaveLength(2)
    expect(card).toHaveTextContent('Role assumed: customer.')
    await userEvent.click(screen.getByRole('button', { name: /Regenerate/ }))
    expect(onGenerate).toHaveBeenCalled()
  })

  it('needs_clarification: explains that questions are above and shows no draft', () => {
    const { card } = show({ state: 'needs_clarification', rationale: 'Not measurable.', clarification_questions: ['What does fast mean?'] })
    expect(card).toHaveTextContent('needs clarification')
    expect(card).toHaveTextContent('Not measurable.')
    expect(card).not.toHaveTextContent('User story')
  })

  it('failed: shows the server message', () => {
    show({ state: 'failed', message: 'not in replay file' })
    expect(screen.getByRole('alert')).toHaveTextContent('Writing the draft failed.')
    expect(screen.getByRole('alert')).toHaveTextContent('not in replay file')
  })

  it('manual_review: warns and keeps the raw reply behind a details element', () => {
    show({ state: 'manual_review', attempts: 3, raw_output: '{"status": "maybe"}', message: 'status must be one of' })
    expect(screen.getByRole('alert')).toHaveTextContent('Manual review needed')
    expect(screen.getByRole('alert')).toHaveTextContent('3 attempts')
    expect(screen.getByText('{"status": "maybe"}')).toBeInTheDocument()
  })

  it('engine unavailable: says so, keeps the analysis intact and offers Retry (no spinner, no draft text)', async () => {
    const { onGenerate, card } = show({ state: 'failed', message: 'AI engine unavailable: could not get a reply from http://localhost:11434/v1/chat/completions: refused' })
    expect(screen.getByRole('alert')).toHaveTextContent('AI engine unavailable.')
    expect(screen.getByRole('alert')).toHaveTextContent('could not get a reply')
    expect(screen.getByRole('alert')).toHaveTextContent('analysis results above are not affected')
    expect(card).not.toHaveTextContent('Writing the draft failed')
    expect(card).not.toHaveTextContent('User story')
    expect(card.querySelector('.animate-spin')).toBeNull()
    const retry = screen.getByRole('button', { name: /Retry/ })
    expect(retry).toBeEnabled()
    await userEvent.click(retry)
    expect(onGenerate).toHaveBeenCalledTimes(1)
  })

  it('running (slow model): shows a per-requirement Generating state and explains the wait', () => {
    show({ state: 'running' })
    expect(screen.getByRole('status')).toHaveTextContent('Writing…')
    expect(screen.getByRole('status')).toHaveTextContent('tens of seconds')
  })

  it.each([
    ['ollama', 'device', 'Generated by AI'],
    ['ollama', 'cloud', 'Generated by AI'],
    ['replay', 'device', 'Stored result of an earlier run'],
    ['mock', 'device', 'not written by AI'],
  ])('done: says where the draft came from (%s, %s) and never names the model or the host', (backend, on, text) => {
    show({ ...fx.generationDone, backend, model: 'c1-req', generated_on: on, endpoint_host: on === 'cloud' ? 'gpu.example.com' : null })
    expect(screen.getByTestId('provenance')).toHaveTextContent(text)
    expect(screen.getByTestId('provenance')).not.toHaveTextContent(/c1-req|gpu\.example\.com|on device|cloud/i)
  })

  it('shows a neutral note listing numbers that are not in the source', () => {
    show({ ...fx.generationDone, numbers_not_in_source: ['5', '10'] })
    expect(screen.getByTestId('numbers-note')).toHaveTextContent('Contains number(s) not in the source: verify (5, 10)')
  })

  it('shows no number note when every number is in the source, or when nothing was generated', () => {
    show(fx.generationDone)
    expect(screen.queryByTestId('numbers-note')).toBeNull()
    document.body.innerHTML = ''
    show({ state: 'failed', message: 'x', numbers_not_in_source: ['7'] })
    expect(screen.queryByTestId('numbers-note')).toBeNull()
  })

  it('has a visible label for every state', () => {
    const states: GenerationState[] = ['not_requested', 'queued', 'running', 'done', 'needs_clarification', 'failed', 'manual_review']
    for (const s of states) {
      const { unmount } = render(<DraftCard generation={{ ...base, state: s }} onGenerate={() => undefined} busy={false} />)
      expect(screen.getByTestId('draft-card')).toHaveAttribute('data-state', s)
      unmount()
    }
  })
})
