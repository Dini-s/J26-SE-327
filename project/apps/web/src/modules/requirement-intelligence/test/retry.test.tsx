import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Overview, Summary } from '../api/types'
import * as fx from './fixtures'
import { json, mockApi, renderApp } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

const DRAFTS = '/requirement/drafts'
const SOURCES = '/requirement/sources' // the progress and Retry failed drafts live here; the Publish page has the banner and Retry too
const RETRY = '/api/projects/1/drafts/retry-failed'
const summaryWith = (td: Partial<Summary['task_drafts']>) => (c: { url: URL }) => (c.url.pathname === '/api/projects/1/summary' ? json({ ...fx.summary, task_drafts: { ...fx.summary.task_drafts, ...td } }) : undefined)
const withPipeline = (improve: Partial<Overview['pipeline']['improve']>) => (c: { url: URL }) => (c.url.pathname === '/api/projects/1/overview' ? json({ ...fx.overview, pipeline: { ...fx.overview.pipeline, improve: { ...fx.overview.pipeline.improve, ...improve } } }) : undefined)
const retries = (calls: { method: string; url: URL; body?: string }[]) => calls.filter((c) => c.method === 'POST' && c.url.pathname === RETRY)
const failedDrafts = { failed: 7, generated: 22 }

describe('process strip: Needs attention', () => {
  it('shows Improve as “Needs attention”, in amber, and opens the failed drafts', async () => {
    mockApi(withPipeline({ state: 'attention', requirements: 334, decided: 5, drafts_written: 327, drafts: { ready: 320, needs_clarification: 7, failed: 7, waiting: 0 } }))
    renderApp()
    const stage = (await screen.findAllByTestId('process-stage'))[3]!
    expect(stage).toHaveAttribute('data-state', 'attention')
    expect(within(stage).getByTestId('stage-state')).toHaveTextContent('Needs attention')
    expect(within(stage).getByTestId('stage-state').className).toContain('amber')
    expect(within(stage).getByTestId('stage-detail')).toHaveTextContent('5 of 334 decided · 327 drafts · 7 failed')
    expect(within(stage).getByRole('link')).toHaveAttribute('href', '/requirement/drafts?filter=failed')
  })

  it('the detail wraps instead of running into the next stage', async () => {
    mockApi(withPipeline({ state: 'attention', drafts: { ready: 20, needs_clarification: 1, failed: 7, waiting: 0 } }))
    renderApp()
    const detail = within((await screen.findAllByTestId('process-stage'))[3]!).getByTestId('stage-detail')
    expect(detail.className).toContain('max-w-[15rem]')
    expect(detail.className).toContain('break-words')
  })

  it('Improve opens the Review Queue when no draft failed, and still opens the failed drafts when every one failed', async () => {
    mockApi(withPipeline({ state: 'active', drafts: { ready: 30, needs_clarification: 0, failed: 0, waiting: 0 } }))
    const first = renderApp()
    expect(within((await screen.findAllByTestId('process-stage'))[3]!).getByRole('link')).toHaveAttribute('href', '/requirement/review')
    first.unmount()
    vi.unstubAllGlobals()
    mockApi(withPipeline({ state: 'failed', drafts_written: 0, drafts: { ready: 0, needs_clarification: 0, failed: 9, waiting: 0 } }))
    renderApp()
    const stage = (await screen.findAllByTestId('process-stage'))[3]!
    expect(within(stage).getByTestId('stage-state')).toHaveTextContent('Failed')
    expect(within(stage).getByRole('link')).toHaveAttribute('href', '/requirement/drafts?filter=failed')
  })

  it('does not point at the failed drafts while others are still being written', async () => {
    mockApi(withPipeline({ state: 'active', drafts: { ready: 20, needs_clarification: 0, failed: 2, waiting: 3 } }))
    renderApp()
    expect(within((await screen.findAllByTestId('process-stage'))[3]!).getByRole('link')).toHaveAttribute('href', '/requirement/review')
  })

  it('the link lands on the Publish page, which has the failed-draft banner', async () => {
    mockApi((c) => withPipeline({ state: 'attention' })(c) ?? summaryWith(failedDrafts)(c))
    renderApp()
    await userEvent.click(within((await screen.findAllByTestId('process-stage'))[3]!).getByRole('link'))
    expect(await screen.findByTestId('publish-table')).toBeInTheDocument()
    expect(await screen.findByTestId('failed-banner-title')).toHaveTextContent('7 drafts could not be written')
  })
})

describe('Sources & Findings: failed drafts', () => {
  it('says how many drafts could not be written and offers “Retry failed drafts”', async () => {
    mockApi(summaryWith(failedDrafts))
    renderApp(SOURCES)
    const banner = await screen.findByTestId('failed-banner')
    expect(screen.getByTestId('failed-banner-title')).toHaveTextContent('7 drafts could not be written')
    expect(banner).toHaveTextContent('Drafts that are done are not touched')
    expect(within(banner).getByTestId('retry-failed')).toBeEnabled()
    expect(screen.queryByTestId('retry-hint')).toBeNull()
  })

  it('speaks of one draft in the singular, and shows no banner without failures', async () => {
    mockApi(summaryWith({ failed: 1 }))
    const first = renderApp(SOURCES)
    expect(await screen.findByTestId('failed-banner-title')).toHaveTextContent('1 draft could not be written')
    first.unmount()
    vi.unstubAllGlobals()
    mockApi()
    renderApp(SOURCES)
    await screen.findByTestId('sources-card')
    expect(screen.queryByTestId('failed-banner')).toBeNull()
  })

  it('the Publish page keeps the failed-draft banner and its retry, without the progress bar', async () => {
    const { calls } = mockApi((c) => (c.method === 'POST' && c.url.pathname === RETRY ? json({ queued: 7 }, 202) : summaryWith(failedDrafts)(c)))
    renderApp(DRAFTS)
    await screen.findByTestId('publish-table')
    expect(await screen.findByTestId('failed-banner-title')).toHaveTextContent('7 drafts could not be written')
    expect(screen.queryByTestId('draft-progress')).toBeNull()
    await userEvent.click(screen.getByTestId('retry-failed'))
    expect(await screen.findByText('7 failed drafts queued again.')).toBeInTheDocument()
    expect(retries(calls)).toHaveLength(1)
  })

  it('Retry failed drafts calls the service once and says how many were queued', async () => {
    const { calls } = mockApi((c) => (c.method === 'POST' && c.url.pathname === RETRY ? json({ queued: 7 }, 202) : summaryWith(failedDrafts)(c)))
    renderApp(SOURCES)
    await userEvent.click(await screen.findByTestId('retry-failed'))
    expect(await screen.findByText('7 failed drafts queued again.')).toBeInTheDocument()
    expect(retries(calls)).toHaveLength(1)
    expect(retries(calls)[0]!.body).toBeUndefined()
  })

  it('says so when nothing was left to retry', async () => {
    mockApi((c) => (c.method === 'POST' && c.url.pathname === RETRY ? json({ queued: 0 }, 202) : summaryWith(failedDrafts)(c)))
    renderApp(SOURCES)
    await userEvent.click(await screen.findByTestId('retry-failed'))
    expect(await screen.findByText('No failed drafts to retry.')).toBeInTheDocument()
  })

  it('shows the service’s refusal in plain words', async () => {
    mockApi((c) => (c.method === 'POST' && c.url.pathname === RETRY ? json({ error: { code: 'generation_running', message: 'Drafts are being written right now.' } }, 409) : summaryWith(failedDrafts)(c)))
    renderApp(SOURCES)
    await userEvent.click(await screen.findByTestId('retry-failed'))
    expect(await screen.findByText(/Could not retry the failed drafts: Drafts are being written right now/)).toBeInTheDocument()
  })

  it('is disabled with a hint while drafts are being written', async () => {
    const { calls } = mockApi(summaryWith({ ...failedDrafts, in_progress: 3, queued: 3 }))
    renderApp(SOURCES)
    const button = await screen.findByTestId('retry-failed')
    expect(button).toBeDisabled()
    expect(screen.getByTestId('retry-hint')).toHaveTextContent('Drafts are being written. Retry the failed ones when it has finished.')
    expect(button).toHaveAttribute('aria-describedby', 'retry-hint')
    await userEvent.click(button)
    expect(retries(calls)).toHaveLength(0)
  })

  it('is disabled with a hint while the AI engine cannot be reached, on the device and in the cloud', async () => {
    mockApi((c) => (c.url.pathname === '/api/engine' ? json({ ...fx.engine, device: { ...fx.engine.device, reachable: false } }) : summaryWith(failedDrafts)(c)))
    const first = renderApp(SOURCES)
    expect(await screen.findByTestId('retry-failed')).toBeDisabled()
    await waitFor(() => expect(screen.getByTestId('retry-hint')).toHaveTextContent('The AI engine cannot be reached. Check it in Processing details, then try again.'))
    first.unmount()
    vi.unstubAllGlobals()
    mockApi((c) => (c.url.pathname === '/api/engine' ? json({ ...fx.engine, target: 'cloud', cloud: { ...fx.engine.cloud, reachable: false } }) : summaryWith(failedDrafts)(c)))
    renderApp(SOURCES)
    await waitFor(() => expect(screen.getByTestId('retry-failed')).toBeDisabled())
    expect(screen.getByTestId('retry-hint')).toHaveTextContent('cannot be reached')
  })

  it('an engine that has not been tested yet does not block the retry', async () => {
    mockApi((c) => (c.url.pathname === '/api/engine' ? json({ ...fx.engine, target: 'cloud', cloud: { ...fx.engine.cloud, reachable: null } }) : summaryWith(failedDrafts)(c)))
    renderApp(SOURCES)
    expect(await screen.findByTestId('retry-failed')).toBeEnabled()
  })

  it('the failed card shows the short reason', async () => {
    mockApi((c) => {
      if (c.url.pathname === '/api/requirements/p1-REQ-003') return json({ ...fx.detail, uid: 'p1-REQ-003', id: 'REQ-003', generation: { ...fx.generationDone, state: 'failed', failure_reason: 'cloud_rejected', message: 'AI engine unavailable: Cloud rejected the request (HTTP 401); check the key and the model' } })
      return summaryWith(failedDrafts)(c)
    })
    renderApp('/requirement/review?uid=p1-REQ-003')
    expect(await screen.findByTestId('failure-reason')).toHaveTextContent('Reason: The AI engine refused the request.')
  })

  it('uses neutral words only', async () => {
    mockApi(summaryWith(failedDrafts))
    renderApp(SOURCES)
    const banner = await screen.findByTestId('failed-banner')
    expect(banner.textContent).not.toMatch(/model|host|probabilit|neo4j|part a|c1|replay|\bapi\b/i)
  })
})
