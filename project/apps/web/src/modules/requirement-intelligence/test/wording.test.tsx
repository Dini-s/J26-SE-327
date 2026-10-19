import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as fx from './fixtures'
import { json, mockApi, renderApp, type Handler } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

/** Words a person must never read in this module (item 7 of the brief). Technical facts live in "Processing details" only. */
const FORBIDDEN: [string, RegExp][] = [
  ['C1..C4', /\bC[1-4]\b/],
  ['Component N', /\bComponent\s*\d/i],
  ['Part A/B', /\bPart\s*[AB]\b/],
  ['c1-req', /c1-req/i],
  ['ollama', /ollama/i],
  ['RVU', /\bRVUs?\b/],
  ['detector', /detector/i],
  ['the API', /\bthe API\b/i],
  ['Neo4j', /neo4j/i],
  ['Cypher', /cypher/i],
  ['probability', /probabilit/i],
  ['phase', /\bphases?\b/i],
]

/** Everything a person can read or hear on the page: text, and the text attributes that screen readers and tooltips use. */
function readable(): string[] {
  const out = [document.body.textContent ?? '']
  for (const el of document.body.querySelectorAll('[title],[aria-label],[placeholder],[alt],[aria-valuetext]')) {
    for (const a of ['title', 'aria-label', 'placeholder', 'alt', 'aria-valuetext']) {
      const v = el.getAttribute(a)
      if (v) out.push(v)
    }
  }
  for (const el of document.body.querySelectorAll('option')) out.push(el.textContent ?? '')
  return out
}

function expectClean(where: string) {
  const text = readable()
  for (const [name, re] of FORBIDDEN) {
    const hit = text.find((t) => re.test(t))
    expect(hit === undefined, `${where}: "${name}" found in: ${hit?.slice(Math.max(0, (hit.search(re) ?? 0) - 40), (hit.search(re) ?? 0) + 60)}`).toBe(true)
  }
}

/** Where drafts are written (this device or the cloud) is named inside the AI engine panel only, never in the page, a notice or the pill. */
function expectNoEngineWording(where: string) {
  const text = readable()
  const hit = text.find((t) => /\bon device\b|\bcloud\b|\bthis device\b|\bswitch to device\b/i.test(t))
  expect(hit === undefined, `${where}: engine wording found in: ${hit?.slice(0, 120)}`).toBe(true)
}

// What the service really sends: names of the model and the backend, and text that names the graph database.
const real: Handler = (c) => {
  if (c.url.pathname === '/api/health') return json({ ...fx.health, generation_backend: 'ollama', model: 'c1-req' })
  if (c.url.pathname === '/api/projects/1/overview') return json({ ...fx.overview, neo4j: { ...fx.graph, message: 'Neo4j is not configured. Set NEO4J_URI.' } })
  return undefined
}

describe('no internal wording in the Jira controls', () => {
  it('every state, the connection notices and the import dialog', async () => {
    const jiraWords = /oauth|token|atlassian|\bscopes?\b|client (id|secret)|redirect/i
    const J = '/api/projects/1/integrations/jira'
    for (const s of [fx.jiraNotConfigured, fx.jiraNotConnected, fx.jiraConnected, fx.jiraExpired]) {
      mockApi((c) => (c.url.pathname === J && c.method === 'GET' ? json(s) : c.url.pathname === `${J}/projects` ? json(fx.jiraProjects) : c.url.pathname === `${J}/boards` ? json(fx.jiraBoards) : real(c)))
      const { unmount } = renderApp('/requirement?jira=error&reason=state_invalid')
      await screen.findByTestId('jira-card')
      await waitFor(() => expect(screen.getByTestId('jira-card')).toHaveAttribute('data-state', s.state))
      expectClean(`jira ${s.state}`)
      expect(readable().find((t) => jiraWords.test(t))).toBeUndefined()
      if (s.state === 'connected') {
        await userEvent.click(screen.getByTestId('jira-import'))
        await waitFor(() => expect(screen.getByTestId('jira-project')).toBeEnabled())
        await userEvent.selectOptions(screen.getByTestId('jira-project'), 'ABC')
        await waitFor(() => expect(screen.getByTestId('jira-board')).toBeEnabled())
        expectClean('jira import dialog')
        expect(readable().find((t) => jiraWords.test(t))).toBeUndefined()
      }
      unmount()
      vi.unstubAllGlobals()
    }
  })
})

describe('no internal wording on any page', () => {
  it('Overview, in every sync state (the service names the graph database in its own messages)', async () => {
    const graphs = [fx.graph, { ...fx.graph, configured: true, error: 'neo4j_unreachable', message: 'Could not reach Neo4j within 5 seconds.' }]
    const syncs = [
      ...(['synced', 'syncing', 'pending', 'retrying', 'unreachable', 'not_configured'] as const).map((state) => ({ ...fx.sync, state, error: state === 'retrying' || state === 'unreachable' ? 'neo4j_unreachable' : null })),
      { ...fx.sync, enabled: false },
    ]
    for (const [i, sync] of syncs.entries()) {
      mockApi((c) => (c.url.pathname === '/api/projects/1/overview' ? json({ ...fx.overview, sync, neo4j: graphs[i % 2]! }) : real(c)))
      const { unmount } = renderApp('/requirement')
      await screen.findByTestId('sync-state')
      await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('Core Banking Platform'))
      await userEvent.click(screen.getByText('Details')) // the details of the card are read too
      expectClean(`overview (${sync.state})`)
      unmount()
      vi.unstubAllGlobals()
    }
  })

  it('Overview: the sprint dialog and the charts', async () => {
    mockApi(real)
    renderApp('/requirement')
    await userEvent.click(await screen.findByRole('button', { name: 'Change' }))
    await screen.findByTestId('current-sprint-select')
    expectClean('change sprint dialog')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    for (const id of ['chart-sprints', 'chart-findings', 'status-donut', 'process-strip', 'latest-uploads', 'jira-card']) expect(screen.getByTestId(id)).toBeInTheDocument()
    expectClean('overview charts')
  })

  it('Overview with nothing analysed yet and with a failed load', async () => {
    mockApi((c) => (c.url.pathname === '/api/projects/1/overview' ? json({ error: { code: 'internal_error', message: 'boom' } }, 500) : real(c)))
    renderApp('/requirement')
    await screen.findByRole('alert')
    expectClean('overview error')
  })

  it('Sources & Findings: the Sources tab, with and without documents', async () => {
    mockApi(real)
    const first = renderApp('/requirement/sources')
    await screen.findAllByText('CoreBanking_SRS_v2.pdf')
    expectClean('sources')
    await userEvent.click(screen.getByTestId('upload-button'))
    await screen.findByTestId('upload-sprint')
    expectClean('upload dialog')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await userEvent.click(screen.getAllByRole('button', { name: 'Move CoreBanking_SRS_v2.pdf to a sprint' })[0]!)
    expectClean('move dialog')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await userEvent.click(screen.getByRole('button', { name: 'Edit Sprint 1' }))
    expectClean('sprint dialog')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    first.unmount()
    vi.unstubAllGlobals()
    mockApi((c) => (c.url.pathname === '/api/projects/1/sources' ? json([]) : real(c)))
    renderApp('/requirement/sources')
    await screen.findByText(/No documents yet/)
    expectClean('sources empty')
  })

  it('Sources & Findings: every Findings view', async () => {
    mockApi(real)
    renderApp('/requirement/sources?tab=findings&view=ambiguities')
    await screen.findAllByTestId('finding-item')
    for (const view of ['Ambiguities', 'Duplicates', 'Conflicts', 'Risk']) {
      await userEvent.click(screen.getByRole('radio', { name: view }))
      await waitFor(() => expect(screen.getByRole('radio', { name: view })).toBeChecked())
      await screen.findAllByTestId('finding-item')
      expectClean(`findings ${view}`)
    }
  })

  it('Review Queue: undecided, decided, conflict and duplicate partners, every draft state', async () => {
    const partner = { id: 'REQ-005', uid: 'p1-REQ-005', similarity: 0.91, text: 'The system shall not notify users about logins.', source_file: 'b.txt', page: null, paragraph: 2 }
    const generations = [
      fx.generationDone,
      { ...fx.generationDone, state: 'needs_clarification' as const, status: 'needs_clarification', clarification_questions: ['How quickly?'], backend: 'ollama', model: 'c1-req', generated_on: 'cloud', endpoint_host: 'gpu.example.com' },
      { ...fx.generationDone, state: 'failed' as const, message: 'AI engine unavailable: could not get a reply from http://localhost:11434/v1/chat/completions: refused', backend: '', model: '' },
      { ...fx.generationDone, state: 'manual_review' as const, attempts: 3, raw_output: '{}', message: 'status must be one of' },
      { ...fx.generationDone, state: 'not_requested' as const, backend: '', model: '' },
      { ...fx.generationDone, state: 'running' as const },
      { ...fx.generationDone, backend: 'ollama', model: 'c1-req', generated_on: 'device' },
    ]
    for (const [i, generation] of generations.entries()) {
      const decision = i % 2 === 0 ? null : { decision: 'edited' as const, edited_text: 'The system shall notify users within 2 seconds.', note: 'clearer', updated_at: '2026-10-14T09:30:00+00:00' }
      mockApi((c) =>
        c.url.pathname === '/api/requirements/p1-REQ-001'
          ? json({ ...fx.detail, generation, decision, conflicts: [{ ...partner, reason: 'Candidate conflict, needs human decision: prohibits an action.' }], duplicates: [{ ...partner, id: 'REQ-006', uid: 'p1-REQ-006' }] })
          : real(c),
      )
      const { unmount } = renderApp('/requirement/review')
      await screen.findByTestId('draft-card')
      await waitFor(() => expect(screen.getByTestId('draft-card')).toHaveAttribute('data-state', generation.state))
      await waitFor(() => expect(screen.getByTestId('decision-card')).toHaveAttribute('data-status', decision ? 'edited' : 'none'))
      expectClean(`review state ${generation.state}`)
      unmount()
      vi.unstubAllGlobals()
    }
  })

  it('Sources & Findings and Task Drafts: idle, running, paused by the user and paused on an unreachable cloud, with the failure banner', async () => {
    const base = fx.summary.task_drafts
    const variants = [
      { ...base, not_generated: 10 },
      { ...base, total: 42, generated: 10, not_generated: 0, in_progress: 32, queued: 31, running: 1, eta_seconds: 600, latency_samples: 5 },
      { ...base, total: 42, generated: 10, in_progress: 32, queued: 32, paused: true, paused_reason: null },
      { ...base, total: 42, generated: 10, failed: 3, in_progress: 32, queued: 32, paused: true, paused_reason: 'cloud_unreachable' },
    ]
    for (const [i, task_drafts] of variants.entries()) {
      mockApi((c) => {
        if (c.url.pathname === '/api/projects/1/summary') return json({ ...fx.summary, task_drafts })
        if (c.url.pathname === '/api/engine' && i === 3) return json({ ...fx.engine, target: 'cloud', cloud: { ...fx.engine.cloud, configured: true, host: 'gpu.example.com', consent: true, reachable: true } })
        return real(c)
      })
      const sources = renderApp('/requirement/sources')
      await screen.findByTestId('draft-progress')
      if (i === 3) await screen.findByTestId('cloud-banner')
      expectClean(`sources variant ${i}`)
      expectNoEngineWording(`sources variant ${i}`)
      sources.unmount()
      const { unmount } = renderApp('/requirement/drafts')
      await screen.findAllByTestId('finding-row')
      expectClean(`task drafts variant ${i}`)
      expectNoEngineWording(`task drafts variant ${i}`)
      unmount()
      vi.unstubAllGlobals()
    }
  })

  it.each(['/requirement', '/requirement/sources', '/requirement/review', '/requirement/drafts'])('%s never says where drafts are written: that is only inside the AI engine panel', async (path) => {
    mockApi(real)
    renderApp(path)
    await screen.findByTestId('engine-pill')
    await waitFor(() => expect(screen.getByTestId('engine-pill')).toHaveAttribute('data-state', 'ready'))
    expectNoEngineWording(path)
  })

  it('the offline state and a missing project', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    const first = renderApp('/requirement')
    await screen.findByTestId('offline-banner')
    expectClean('offline')
    first.unmount()
    vi.unstubAllGlobals()
    mockApi((c) => (c.url.pathname === '/api/projects' ? json([]) : real(c)))
    renderApp('/requirement/review')
    await screen.findByTestId('no-project')
    expectClean('no project')
  })

  it('the check itself works: it catches every forbidden word', () => {
    document.body.innerHTML = '<p title="Part A models">C2 and Component 3, ollama c1-req RVU detector the API Neo4j Cypher probability phase</p>'
    const text = readable().join(' ')
    for (const [, re] of FORBIDDEN) expect(re.test(text)).toBe(true)
    document.body.innerHTML = ''
  })

  it('Processing details is the one place that may show the model and the mode', async () => {
    mockApi(real)
    renderApp('/requirement')
    await userEvent.click(await screen.findByTestId('engine-pill'))
    const details = await screen.findByTestId('technical-details')
    await waitFor(() => expect(details).toHaveTextContent('c1-req'))
    expect(details).toHaveTextContent('ollama')
    expect(screen.getByTestId('engine-pill')).not.toHaveTextContent(/c1-req|ollama/i)
  })
})
