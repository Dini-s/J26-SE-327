import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { limits } from '../config'
import * as fx from './fixtures'
import { json, mockApi, renderApp } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
})

const rowsShown = async () => (await screen.findAllByTestId('finding-row')).length
const source2 = { ...fx.source, id: 2, filename: 'Payments_SRS.docx', ext: '.docx', pages: null }
const emptySummary = { ...fx.summary, requirements: 0, ambiguities: { count: 0, high_risk: 0, asked_by_ai: 0 }, conflicts: 0, duplicates: 0, task_drafts: { generated: 0, total: 0 }, open_findings: 0 }
const finishedJob = { ...fx.job, stage: 'share' as const, generation: { total: 42, done: 42, failed: 0, queued: 0, running: 0 } }
const runningJob = { ...fx.job, stage: 'improve' as const }
const analyzeUrl = '/api/projects/1/analyze'
const posts = (calls: { method: string; url: URL }[]) => calls.filter((c) => c.method === 'POST' && c.url.pathname === analyzeUrl)
const dropped = new Response(null, { status: 204 })

describe('removing sources', () => {
  /** A stateful fake: DELETE changes the source list, and the findings and summary shrink with it. */
  function sourceApi() {
    let sources = [fx.source, source2]
    return mockApi((c) => {
      const p = c.url.pathname
      if (c.method === 'DELETE' && p === '/api/projects/1/sources') {
        sources = []
        return dropped.clone()
      }
      const m = /^\/api\/projects\/1\/sources\/(\d+)$/.exec(p)
      if (c.method === 'DELETE' && m) {
        sources = sources.filter((s) => s.id !== Number(m[1]))
        return dropped.clone()
      }
      if (p === '/api/projects/1/sources') return json(sources)
      if (sources.length === 0 && p === '/api/projects/1/summary') return json(emptySummary)
      if (sources.length === 0 && p === '/api/projects/1/requirements') return json({ total: 0, limit: 50, offset: 0, items: [] })
      if (sources.length === 1 && p === '/api/projects/1/requirements') return json({ total: 1, limit: 50, offset: 0, items: [fx.rows[0]] })
      return undefined
    })
  }

  it('asks for an inline confirmation, then deletes the source and refreshes the page', async () => {
    const { calls } = sourceApi()
    renderApp()
    expect(await rowsShown()).toBe(3)
    await userEvent.click(screen.getByRole('button', { name: 'Remove Payments_SRS.docx' }))
    const confirm = screen.getByRole('group', { name: 'Confirm removing Payments_SRS.docx' })
    expect(confirm).toHaveTextContent('Remove file and its results?')
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false) // nothing is sent before the confirmation
    await userEvent.click(within(confirm).getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url.pathname === '/api/projects/1/sources/2')).toBe(true))
    await waitFor(() => expect(screen.queryByText('Payments_SRS.docx')).toBeNull())
    expect(screen.getByText('CoreBanking_SRS_v2.pdf', { selector: 'li span' })).toBeInTheDocument()
    expect(await screen.findByText('Source removed together with its requirements and results.')).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByTestId('finding-row')).toHaveLength(1)) // the findings list was refreshed
  })

  it('cancel keeps the source and sends nothing', async () => {
    const { calls } = sourceApi()
    renderApp()
    await rowsShown()
    await userEvent.click(screen.getByRole('button', { name: 'Remove CoreBanking_SRS_v2.pdf' }))
    await userEvent.click(within(screen.getByRole('group', { name: /Confirm removing/ })).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('group', { name: /Confirm removing/ })).toBeNull()
    expect(screen.getByRole('button', { name: 'Remove CoreBanking_SRS_v2.pdf' })).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
  })

  it('Clear all asks first, then removes everything and shows the empty state', async () => {
    const { calls } = sourceApi()
    renderApp()
    await rowsShown()
    await userEvent.click(screen.getByRole('button', { name: 'Clear all' }))
    const group = screen.getByRole('group', { name: 'Confirm clearing all sources' })
    expect(group).toHaveTextContent('Clear all sources and their results?')
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await userEvent.click(within(group).getByRole('button', { name: 'Clear all' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url.pathname === '/api/projects/1/sources')).toBe(true))
    expect(await screen.findByTestId('empty-list')).toHaveTextContent('Upload an SRS to begin.')
    expect(screen.getByTestId('sources-card')).toHaveTextContent('0 files')
    await waitFor(() => expect(within(screen.getByTestId('stat-requirements')).getByText('0')).toBeInTheDocument())
    expect(screen.getByTestId('analysis-badge')).toHaveTextContent('Not analysed yet')
    expect(screen.queryByRole('button', { name: 'Clear all' })).toBeNull()
  })

  it('clears the detail panel when the selected requirement disappears', async () => {
    sourceApi()
    renderApp()
    await screen.findByTestId('detail-id')
    await userEvent.click(screen.getByRole('button', { name: 'Clear all' }))
    await userEvent.click(within(screen.getByRole('group', { name: 'Confirm clearing all sources' })).getByRole('button', { name: 'Clear all' }))
    expect(await screen.findByText('Select a requirement to see its analysis.')).toBeInTheDocument()
    expect(screen.queryByTestId('detail-id')).toBeNull()
  })

  it('shows the server message when the API refuses (409) and keeps the source', async () => {
    mockApi((c) => (c.method === 'DELETE' ? json({ error: { code: 'project_busy', message: 'An analysis or draft generation is still running for this project.' } }, 409) : undefined))
    renderApp()
    await rowsShown()
    await userEvent.click(screen.getByRole('button', { name: 'Remove CoreBanking_SRS_v2.pdf' }))
    await userEvent.click(within(screen.getByRole('group', { name: /Confirm removing/ })).getByRole('button', { name: 'Remove' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not remove the source: An analysis or draft generation is still running')
    expect(screen.getByText('CoreBanking_SRS_v2.pdf', { selector: 'li span' })).toBeInTheDocument()
  })

  it('remove and Clear all are disabled with a tooltip while a job is running', async () => {
    mockApi((c) => {
      if (c.method === 'POST' && c.url.pathname === analyzeUrl) return json(runningJob, 202)
      if (c.url.pathname === '/api/jobs/abc123') return json(runningJob)
      return undefined
    })
    renderApp()
    await rowsShown()
    expect(screen.getByRole('button', { name: 'Remove CoreBanking_SRS_v2.pdf' })).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: /Run analysis/ }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Remove CoreBanking_SRS_v2.pdf' })).toBeDisabled())
    expect(screen.getByRole('button', { name: 'Remove CoreBanking_SRS_v2.pdf' })).toHaveAttribute('title', 'Wait for the running analysis to finish.')
    expect(screen.getByRole('button', { name: 'Clear all' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Clear all' })).toHaveAttribute('title', 'Wait for the running analysis to finish.')
  })
})

describe('stale analysis hint', () => {
  it('appears after uploading new files to an analysed project and goes away after the next analysis', async () => {
    mockApi((c) => {
      if (c.method === 'POST' && c.url.pathname === '/api/projects/1/sources') return json({ accepted: [source2], rejected: [] }, 201)
      if (c.method === 'POST' && c.url.pathname === analyzeUrl) return json(finishedJob, 202)
      if (c.url.pathname === '/api/jobs/abc123') return json(finishedJob)
      return undefined
    })
    renderApp()
    await rowsShown()
    await waitFor(() => expect(screen.getByTestId('analysis-badge')).toHaveTextContent('Analysis complete'))
    fireEvent.change(screen.getByTestId('file-input'), { target: { files: [new File(['x'], 'new.txt')] } })
    await waitFor(() => expect(screen.getByTestId('analysis-badge')).toHaveTextContent('Sources changed, run analysis again'))
    await userEvent.click(screen.getByRole('button', { name: /Run analysis/ }))
    await waitFor(() => expect(screen.getByTestId('analysis-badge')).toHaveTextContent('Analysis complete'))
  })

  it('does not appear when nothing had been analysed yet', async () => {
    mockApi((c) => {
      const p = c.url.pathname
      if (c.method === 'POST' && p === '/api/projects/1/sources') return json({ accepted: [fx.source], rejected: [] }, 201)
      if (p === '/api/projects/1/summary') return json(emptySummary)
      if (p === '/api/projects/1/requirements') return json({ total: 0, limit: 50, offset: 0, items: [] })
      return undefined
    })
    renderApp()
    await screen.findByTestId('empty-list')
    fireEvent.change(screen.getByTestId('file-input'), { target: { files: [new File(['x'], 'new.txt')] } })
    expect(await screen.findByText(/1 file added/)).toBeInTheDocument()
    expect(screen.getByTestId('analysis-badge')).toHaveTextContent('Not analysed yet')
  })
})

describe('pipeline strip', () => {
  const steps = () => [...document.querySelectorAll('[data-stage]')].map((s) => s.getAttribute('data-state'))
  const spinners = () => document.querySelectorAll('[aria-label="Analysis pipeline"] .animate-spin')

  it('idle: no step is done and nothing spins', async () => {
    mockApi((c) => {
      const p = c.url.pathname
      if (p === '/api/projects/1/summary') return json(emptySummary)
      if (p === '/api/projects/1/requirements') return json({ total: 0, limit: 50, offset: 0, items: [] })
      return undefined
    })
    renderApp()
    await screen.findByTestId('empty-list')
    await waitFor(() => expect(screen.getByRole('list', { name: 'Analysis pipeline' })).toHaveAttribute('data-mode', 'idle'))
    expect(steps()).toEqual(['pending', 'pending', 'pending', 'pending', 'pending'])
    expect(spinners()).toHaveLength(0)
    expect(screen.queryByRole('img', { name: 'done' })).toBeNull()
  })

  it('complete: every step is done and nothing spins', async () => {
    mockApi()
    renderApp()
    await rowsShown()
    await waitFor(() => expect(screen.getByRole('list', { name: 'Analysis pipeline' })).toHaveAttribute('data-mode', 'complete'))
    expect(steps()).toEqual(['done', 'done', 'done', 'done', 'done'])
    expect(spinners()).toHaveLength(0)
  })

  it('running: only the current step spins', async () => {
    mockApi((c) => {
      if (c.method === 'POST' && c.url.pathname === analyzeUrl) return json(runningJob, 202)
      if (c.url.pathname === '/api/jobs/abc123') return json(runningJob)
      return undefined
    })
    renderApp()
    await rowsShown()
    await userEvent.click(screen.getByRole('button', { name: /Run analysis/ }))
    await waitFor(() => expect(document.querySelector('[data-stage="improve"]')).toHaveAttribute('data-state', 'active'))
    expect(steps()).toEqual(['done', 'done', 'done', 'active', 'pending'])
    expect(spinners()).toHaveLength(1)
    expect(document.querySelector('[data-stage="improve"] .animate-spin')).not.toBeNull()
  })
})

describe('Run analysis', () => {
  it('sends the request at once, shows Analysing… with elapsed time, disables the button, then finishes', async () => {
    let release!: (r: Response) => void
    const pending = new Promise<Response>((resolve) => (release = resolve))
    const { calls } = mockApi((c) => {
      if (c.method === 'POST' && c.url.pathname === analyzeUrl) return pending
      if (c.url.pathname === '/api/jobs/abc123') return json(finishedJob)
      return undefined
    })
    renderApp()
    await rowsShown()
    const button = screen.getByRole('button', { name: /Run analysis/ })
    await waitFor(() => expect(button).toBeEnabled()) // enabled once the sources have loaded
    await userEvent.click(button)
    await waitFor(() => expect(posts(calls)).toHaveLength(1))
    const busy = screen.getByRole('button', { name: /Analysing…/ })
    expect(busy).toBeDisabled()
    expect(busy).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByTestId('analysis-badge')).toHaveTextContent('Analysing')
    const notice = screen.getByTestId('analyzing-notice')
    expect(notice).toHaveTextContent('Analysing… 0:00 elapsed')
    expect(notice).toHaveTextContent('The first run is slower')
    expect(document.querySelector('[data-stage="collect"]')).toHaveAttribute('data-state', 'active')
    await userEvent.click(busy) // a second click does nothing
    expect(posts(calls)).toHaveLength(1)
    release(json(finishedJob, 202))
    await waitFor(() => expect(screen.queryByTestId('analyzing-notice')).toBeNull())
    // the job is polled once more (the test client drops unobserved cache entries at once), then the button is free again
    await waitFor(() => expect(screen.getByRole('button', { name: /Run analysis/ })).toBeEnabled())
    await waitFor(() => expect(screen.getByTestId('analysis-badge')).toHaveTextContent('Analysis complete'))
  })

  it('shows an inline error (not only a toast) when the request fails, and can try again', async () => {
    let attempts = 0
    const { calls } = mockApi((c) => {
      if (c.method === 'POST' && c.url.pathname === analyzeUrl) {
        attempts += 1
        return attempts === 1 ? json({ error: { code: 'models_missing', message: 'Saved model missing: fr_nfr_fr_nfr_emb_lr.joblib' } }, 503) : json(finishedJob, 202)
      }
      if (c.url.pathname === '/api/jobs/abc123') return json(finishedJob)
      return undefined
    })
    renderApp()
    await rowsShown()
    await userEvent.click(screen.getByRole('button', { name: /Run analysis/ }))
    const inline = await screen.findByTestId('analyze-error')
    expect(inline).toHaveTextContent('The analysis did not finish.')
    expect(inline).toHaveTextContent('Saved model missing: fr_nfr_fr_nfr_emb_lr.joblib')
    expect(screen.getByRole('button', { name: /Run analysis/ })).toBeEnabled()
    await userEvent.click(within(inline).getByRole('button', { name: /Try again/ }))
    await waitFor(() => expect(screen.queryByTestId('analyze-error')).toBeNull())
    expect(posts(calls)).toHaveLength(2)
  })

  it('shows an inline error when the request times out', async () => {
    const before = limits.analyzeTimeoutMs
    limits.analyzeTimeoutMs = 80
    try {
      mockApi((c) =>
        c.method === 'POST' && c.url.pathname === analyzeUrl
          ? new Promise<Response>((_resolve, reject) => c.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))))
          : undefined,
      )
      renderApp()
      await rowsShown()
      await userEvent.click(screen.getByRole('button', { name: /Run analysis/ }))
      const inline = await screen.findByTestId('analyze-error')
      expect(inline).toHaveTextContent('did not answer within')
      expect(screen.queryByTestId('analyzing-notice')).toBeNull()
      expect(screen.getByRole('button', { name: /Run analysis/ })).toBeEnabled()
    } finally {
      limits.analyzeTimeoutMs = before
    }
  })

  it('stays disabled until a source exists', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/sources' && c.method === 'GET' ? json([]) : undefined))
    renderApp()
    await screen.findByText(/0 files/)
    expect(screen.getByRole('button', { name: /Run analysis/ })).toBeDisabled()
  })
})
