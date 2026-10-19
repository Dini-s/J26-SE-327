import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { JiraStatus } from '../api/types'
import { RequirementRoutes } from '../RequirementIntelligencePage'
import { ModuleStateProvider } from '../context/ModuleState'
import { goTo } from '../lib/navigate'
import * as fx from './fixtures'
import { json, mockApi, renderApp, renderWithProviders, type Handler } from './utils'

vi.mock('../lib/navigate', () => ({ goTo: vi.fn() }))

beforeEach(() => vi.mocked(goTo).mockClear())
afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

const J = '/api/projects/1/integrations/jira'
const SOURCES = '/requirement/sources'
const status = (s: JiraStatus): Handler => (c) => (c.url.pathname === J && c.method === 'GET' ? json(s) : undefined)
const both = (...hs: Handler[]): Handler => (c) => hs.map((h) => h(c)).find((r) => r !== undefined)
const withJira = (s: JiraStatus, ...more: Handler[]) => both(status(s), ...more)
const reads = (calls: { method: string; url: URL; body?: string }[], path: string, method = 'GET') => calls.filter((c) => c.method === method && c.url.pathname === path)
const FORBIDDEN_TERMS = /oauth|token|atlassian|scope|client id|client secret|\bapi\b/i

describe('Jira controls: every state, on the Overview and in Sources', () => {
  it('not set up on the server: Connect Jira is disabled and says why', async () => {
    mockApi(withJira(fx.jiraNotConfigured))
    renderApp()
    const card = await screen.findByTestId('jira-card')
    await waitFor(() => expect(within(card).getByTestId('jira-note')).toBeInTheDocument())
    expect(within(card).getByTestId('jira-connect')).toBeDisabled()
    expect(card).toHaveTextContent('Jira is not set up on this server. Ask your administrator to set it up.')
    expect(card).not.toHaveTextContent('Coming soon')
    expect(card).not.toHaveTextContent(FORBIDDEN_TERMS)
  })

  it('the Overview has a Jira card (icon, state, actions) and no Integrations block', async () => {
    mockApi(withJira(fx.jiraConnected))
    renderApp()
    const card = await screen.findByTestId('jira-card')
    expect(within(card).getByTestId('jira-icon')).toBeInTheDocument()
    expect(within(card).getByRole('heading', { name: 'Jira' })).toBeInTheDocument()
    await waitFor(() => expect(within(card).getByTestId('jira-state')).toHaveTextContent('Connected'))
    expect(screen.queryByText('Integrations')).toBeNull()
    expect(screen.queryByTestId('integrations-card')).toBeNull()
  })

  it('not connected: Connect Jira is available', async () => {
    mockApi(withJira(fx.jiraNotConnected))
    renderApp()
    const card = await screen.findByTestId('jira-card')
    const button = await within(card).findByTestId('jira-connect')
    await waitFor(() => expect(button).toBeEnabled())
    expect(card).toHaveAttribute('data-state', 'not_connected')
    expect(within(card).queryByTestId('jira-import')).toBeNull()
  })

  it('connected: the site, Import from Jira and Disconnect', async () => {
    mockApi(withJira(fx.jiraConnected))
    renderApp()
    const card = await screen.findByTestId('jira-card')
    expect(await within(card).findByTestId('jira-site')).toHaveTextContent('Connected to Acme')
    expect(within(card).getByTestId('jira-import')).toHaveTextContent('Import from Jira')
    expect(within(card).getByTestId('jira-disconnect')).toBeInTheDocument()
    expect(within(card).queryByTestId('jira-connect')).toBeNull()
    expect(within(card).queryByTestId('jira-reconnect')).toBeNull()
  })

  it('expired: says so and offers Reconnect, not Import', async () => {
    mockApi(withJira(fx.jiraExpired))
    renderApp()
    const card = await screen.findByTestId('jira-card')
    expect(await within(card).findByRole('alert')).toHaveTextContent('The Jira connection has expired. Connect again to keep importing.')
    expect(within(card).getByTestId('jira-reconnect')).toHaveTextContent('Reconnect')
    expect(within(card).queryByTestId('jira-import')).toBeNull()
    expect(within(card).getByTestId('jira-disconnect')).toBeInTheDocument()
  })

  it('when the status cannot be loaded the button stays off and says so', async () => {
    mockApi((c) => (c.url.pathname === J ? json({ error: { code: 'internal', message: 'boom' } }, 500) : undefined))
    renderApp()
    const card = await screen.findByTestId('jira-card')
    await waitFor(() => expect(within(card).getByTestId('jira-note')).toHaveTextContent('Jira status could not be loaded.'))
    expect(within(card).getByTestId('jira-connect')).toBeDisabled()
  })

  it('the Sources toolbar shows the same four states', async () => {
    for (const [s, state] of [[fx.jiraNotConfigured, 'not_configured'], [fx.jiraNotConnected, 'not_connected'], [fx.jiraConnected, 'connected'], [fx.jiraExpired, 'expired']] as const) {
      mockApi(withJira(s))
      const { unmount } = renderApp(SOURCES)
      const toolbar = await screen.findByTestId('jira-row')
      await waitFor(() => expect(toolbar).toHaveAttribute('data-state', state))
      expect(screen.getByTestId('sources-card')).not.toContainElement(toolbar)
      unmount()
      vi.unstubAllGlobals()
    }
  })
})

describe('Jira: connect, return, disconnect', () => {
  it('Connect Jira asks the service for the address and sends the browser there', async () => {
    const { calls } = mockApi(withJira(fx.jiraNotConnected, (c) => (c.method === 'POST' && c.url.pathname === `${J}/connect` ? json({ authorize_url: 'https://auth.atlassian.com/authorize?state=abc' }) : undefined)))
    renderApp(SOURCES)
    const button = await within(await screen.findByTestId('jira-row')).findByTestId('jira-connect')
    await waitFor(() => expect(button).toBeEnabled())
    await userEvent.click(button)
    await waitFor(() => expect(goTo).toHaveBeenCalledWith('https://auth.atlassian.com/authorize?state=abc'))
    expect(reads(calls, `${J}/connect`, 'POST')).toHaveLength(1)
  })

  it('Reconnect does the same', async () => {
    mockApi(withJira(fx.jiraExpired, (c) => (c.method === 'POST' && c.url.pathname === `${J}/connect` ? json({ authorize_url: 'https://auth.atlassian.com/authorize?state=again' }) : undefined)))
    renderApp()
    await userEvent.click(await screen.findByTestId('jira-reconnect'))
    await waitFor(() => expect(goTo).toHaveBeenCalledWith('https://auth.atlassian.com/authorize?state=again'))
  })

  it('a refusal to start the connection is shown in plain words and nothing happens', async () => {
    mockApi(withJira(fx.jiraNotConnected, (c) => (c.method === 'POST' && c.url.pathname === `${J}/connect` ? json({ error: { code: 'jira_not_configured', message: 'Jira is not set up on this server.' } }, 409) : undefined)))
    renderApp()
    const button = await screen.findByTestId('jira-connect')
    await waitFor(() => expect(button).toBeEnabled())
    await userEvent.click(button)
    expect(await screen.findByText('Could not start the Jira connection: Jira is not set up on this server.')).toBeInTheDocument()
    expect(goTo).not.toHaveBeenCalled()
  })

  function renderAt(path: string) {
    function Probe() {
      const l = useLocation()
      return <output data-testid="location">{l.pathname + l.search}</output>
    }
    return renderWithProviders(
      <ModuleStateProvider>
        <MemoryRouter initialEntries={[path]}>
          <Probe />
          <Routes>
            <Route path="/requirement/*" element={<RequirementRoutes />} />
          </Routes>
        </MemoryRouter>
      </ModuleStateProvider>,
    )
  }

  it('back from Jira with ?jira=connected: a notice, the status is read again and the address is cleaned', async () => {
    const { calls } = mockApi(withJira(fx.jiraConnected))
    renderAt('/requirement?jira=connected')
    expect(await screen.findByText('Jira is connected.')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/requirement$/))
    expect(await screen.findByTestId('jira-site')).toHaveTextContent('Connected to Acme')
    expect(screen.getAllByText('Jira is connected.')).toHaveLength(1)
    expect(reads(calls, J).length).toBeGreaterThanOrEqual(1)
  })

  it('back from Jira with an error: says what went wrong, once, and keeps the other query parameters', async () => {
    mockApi(withJira(fx.jiraNotConnected))
    renderAt('/requirement/sources?tab=findings&jira=error&reason=access_denied')
    expect(await screen.findByText('Jira could not be connected. Access was not granted in Jira.')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/requirement/sources?tab=findings'))
    expect(screen.getByTestId('location').textContent).not.toMatch(/jira=|reason=/)
  })

  it('every reason gets its own sentence, and an unknown one only the general notice', async () => {
    for (const [reason, text] of [['state_invalid', 'expired or was already used'], ['exchange_failed', 'did not accept the connection'], ['no_site', 'No Jira site was found'], ['mystery', '']] as const) {
      mockApi(withJira(fx.jiraNotConnected))
      const { unmount } = renderAt(`/requirement?jira=error&reason=${reason}`)
      const toast = await screen.findByText(/Jira could not be connected\./)
      if (text) expect(toast).toHaveTextContent(text)
      else expect(toast.textContent).toBe('Jira could not be connected.')
      unmount()
      vi.unstubAllGlobals()
    }
  })

  it('an unknown ?jira value is only removed from the address', async () => {
    mockApi(withJira(fx.jiraNotConnected))
    renderAt('/requirement?jira=whatever')
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/requirement$/))
    expect(screen.queryByText(/Jira (is connected|could not be connected)/)).toBeNull()
  })

  it('Disconnect asks first, then removes the connection and says the imported items stay', async () => {
    const { calls } = mockApi(withJira(fx.jiraConnected, (c) => (c.method === 'DELETE' && c.url.pathname === J ? new Response(null, { status: 204 }) : undefined)))
    renderApp()
    await userEvent.click(await screen.findByTestId('jira-disconnect'))
    const dialog = screen.getByRole('dialog', { name: 'Disconnect Jira?' })
    expect(dialog).toHaveTextContent('Everything already imported stays.')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(reads(calls, J, 'DELETE')).toHaveLength(0)
    await userEvent.click(screen.getByTestId('jira-disconnect'))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Disconnect' }))
    expect(await screen.findByText('Jira was disconnected. Imported items were kept.')).toBeInTheDocument()
    expect(reads(calls, J, 'DELETE')).toHaveLength(1)
  })
})

describe('Jira: the import dialog', () => {
  const IMPORT = `${J}/import`
  const service = (more?: Handler) =>
    withJira(
      fx.jiraConnected,
      more ?? (() => undefined), // a test's own answer comes first
      (c) => (c.url.pathname === `${J}/projects` ? json(fx.jiraProjects) : undefined),
      (c) => (c.url.pathname === `${J}/boards` ? json(fx.jiraBoards) : undefined),
      (c) => (c.method === 'POST' && c.url.pathname === IMPORT ? json(fx.jiraImported) : undefined),
    )
  async function open(path = SOURCES) {
    renderApp(path)
    await userEvent.click(await screen.findByTestId('jira-import'))
    const dialog = screen.getByRole('dialog', { name: 'Import from Jira' })
    await waitFor(() => expect(within(dialog).getByTestId('jira-project')).toBeEnabled())
    return dialog
  }
  const body = (calls: { method: string; url: URL; body?: string }[]) => JSON.parse(reads(calls, IMPORT, 'POST')[0]!.body!)

  it('offers the projects, then the boards of the chosen project, with the usual defaults', async () => {
    const { calls } = mockApi(service())
    const dialog = await open()
    expect([...(within(dialog).getByTestId('jira-project') as HTMLSelectElement).options].map((o) => o.textContent)).toEqual(['Choose a project', 'Alpha (ABC)', 'Delta (DEF)'])
    expect(within(dialog).getByTestId('jira-board')).toBeDisabled()
    await userEvent.selectOptions(within(dialog).getByTestId('jira-project'), 'ABC')
    await waitFor(() => expect(within(dialog).getByTestId('jira-board')).toBeEnabled())
    expect(reads(calls, `${J}/boards`)[0]!.url.searchParams.get('project_key')).toBe('ABC')
    expect([...(within(dialog).getByTestId('jira-board') as HTMLSelectElement).options].map((o) => o.textContent)).toEqual(['No board (all issues of the project)', 'ABC board (scrum)', 'ABC kanban (kanban)'])
    await userEvent.selectOptions(within(dialog).getByTestId('jira-board'), '7')
    expect(within(dialog).getByRole('checkbox', { name: 'Active' })).toBeChecked()
    expect(within(dialog).getByRole('checkbox', { name: 'Future' })).toBeChecked()
    expect(within(dialog).getByRole('checkbox', { name: 'Closed' })).not.toBeChecked()
    expect(within(dialog).getByRole('checkbox', { name: 'Story' })).toBeChecked()
    expect(within(dialog).getByRole('checkbox', { name: 'Task' })).toBeChecked()
    expect(within(dialog).getByRole('checkbox', { name: 'Bug' })).not.toBeChecked()
    expect(within(dialog).queryByTestId('jira-set-current')).toBeNull()
    const target = within(dialog).getByTestId('jira-target') as HTMLSelectElement
    expect(target).toHaveValue('')
    expect([...target.options].map((o) => o.textContent)).toEqual(['Sprint 1 (current)', 'Sprint 2', 'Sprint 3']) // your own sprints, with or without a board
    expect(within(dialog).getByTestId('jira-target-hint')).toHaveTextContent('Everything imported goes to this sprint.')
    expect(dialog).not.toHaveTextContent(FORBIDDEN_TERMS)
  })

  it('sends the choices to the service and shows what the import did', async () => {
    const { calls } = mockApi(service())
    const dialog = await open()
    await userEvent.selectOptions(within(dialog).getByTestId('jira-project'), 'ABC')
    await waitFor(() => expect(within(dialog).getByTestId('jira-board')).toBeEnabled())
    await userEvent.selectOptions(within(dialog).getByTestId('jira-board'), '7')
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Closed' }))
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Task' }))
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Bug' }))
    await userEvent.type(within(dialog).getByLabelText('Other types (comma separated)'), 'Spike, Bug ,')
    await userEvent.click(within(dialog).getByTestId('jira-import-submit'))
    const result = await within(screen.getByRole('dialog', { name: 'Import finished' })).findByTestId('jira-result')
    expect(body(calls)).toEqual({ project_key: 'ABC', board_id: 7, sprint_states: ['active', 'future', 'closed'], issue_types: ['Story', 'Bug', 'Spike'], set_current: false, target_sprint_id: null, policy: 'smart' })
    for (const line of ['Added to Sprint 1', '12 new issues', '3 issues updated', '30 issues unchanged', '1 issue skipped (no text)', '2 issues no longer in Jira (kept here)', '9 drafts queued']) {
      expect(result).toHaveTextContent(line)
    }
    expect(screen.queryByTestId('jira-analysis-error')).toBeNull()
    await userEvent.click(screen.getByTestId('jira-done'))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('without a board no board is sent, and the draft policy of the page is used', async () => {
    window.localStorage.setItem('requirement-intelligence.draftPolicy', 'all')
    const { calls } = mockApi(service())
    const dialog = await open()
    await userEvent.selectOptions(within(dialog).getByTestId('jira-project'), 'DEF')
    await userEvent.click(within(dialog).getByTestId('jira-import-submit'))
    await screen.findByTestId('jira-result')
    const sent = body(calls)
    expect(sent).toEqual({ project_key: 'DEF', sprint_states: ['active', 'future'], issue_types: ['Story', 'Task'], set_current: false, target_sprint_id: null, policy: 'all' })
    expect('board_id' in sent).toBe(false)
    expect(screen.getByTestId('jira-result')).toHaveTextContent('Added to Sprint 1')
  })

  it('without a board there is no "Match Jira sprints"; a chosen sprint is sent by its id and named in the summary', async () => {
    const { calls } = mockApi(service((c) => (c.method === 'POST' && c.url.pathname === IMPORT ? json({ ...fx.jiraImported, target_sprint: { id: 2, name: 'Sprint 2' }, sprints_created: 0, sprints_updated: 0 }) : undefined)))
    const dialog = await open()
    await userEvent.selectOptions(within(dialog).getByTestId('jira-project'), 'DEF')
    const target = within(dialog).getByTestId('jira-target') as HTMLSelectElement
    expect([...target.options].map((o) => o.textContent)).not.toContain('Match Jira sprints')
    await userEvent.selectOptions(target, 'Sprint 2')
    await userEvent.click(within(dialog).getByTestId('jira-import-submit'))
    const result = await screen.findByTestId('jira-result')
    expect(body(calls).target_sprint_id).toBe(2)
    expect(result).toHaveTextContent('Added to Sprint 2')
    expect(result).not.toHaveTextContent('sprints added')
  })

  it('never offers a sprint that an earlier Jira import made: Jira goes into the sprint chosen here', async () => {
    const own = fx.sprints
    const imported = { ...fx.sprints[1]!, id: 9, name: 'SCRUM Sprint 1', origin: 'jira' as const, external_id: '10', is_current: false }
    mockApi(service((c) => (c.url.pathname === '/api/projects/1/sprints' ? json([...own, imported]) : undefined)))
    const dialog = await open()
    const names = [...(within(dialog).getByTestId('jira-target') as HTMLSelectElement).options].map((o) => o.textContent)
    expect(names).toEqual(['Sprint 1 (current)', 'Sprint 2', 'Sprint 3'])
    expect(names.join(' ')).not.toContain('SCRUM')
    expect(within(dialog).queryByText('Match Jira sprints')).toBeNull()
  })

  it('checks the form before anything is sent', async () => {
    const { calls } = mockApi(service())
    const dialog = await open()
    await userEvent.click(within(dialog).getByTestId('jira-import-submit'))
    expect(within(dialog).getByTestId('jira-error')).toHaveTextContent('Choose a Jira project.')
    await userEvent.selectOptions(within(dialog).getByTestId('jira-project'), 'ABC')
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Active' }))
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Future' }))
    await userEvent.click(within(dialog).getByTestId('jira-import-submit'))
    expect(within(dialog).getByTestId('jira-error')).toHaveTextContent('Choose at least one kind of sprint.')
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Active' }))
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Story' }))
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Task' }))
    await userEvent.click(within(dialog).getByTestId('jira-import-submit'))
    expect(within(dialog).getByTestId('jira-error')).toHaveTextContent('Choose at least one issue type.')
    expect(reads(calls, IMPORT, 'POST')).toHaveLength(0)
  })

  it('tells when the analysis could not run and when the import was cut off', async () => {
    mockApi(service((c) => (c.method === 'POST' && c.url.pathname === IMPORT ? json({ ...fx.jiraImported, analysis_error: 'models_missing', truncated: true, queued: 0, job_id: null, skipped: 0, missing: 0 }) : undefined)))
    const dialog = await open()
    await userEvent.selectOptions(within(dialog).getByTestId('jira-project'), 'ABC')
    await userEvent.click(within(dialog).getByTestId('jira-import-submit'))
    expect(await screen.findByTestId('jira-analysis-error')).toHaveTextContent('The issues were imported, but the analysis could not run.')
    expect(screen.getByTestId('jira-result')).toHaveTextContent('Only the first 2000 issues were read.')
    expect(screen.getByTestId('jira-result')).not.toHaveTextContent('skipped')
    expect(screen.getByTestId('jira-result')).not.toHaveTextContent('queued')
  })

  it('shows a refusal in plain words and keeps the form', async () => {
    mockApi(service((c) => (c.method === 'POST' && c.url.pathname === IMPORT ? json({ error: { code: 'jira_expired', message: 'The Jira connection has expired. Connect again to continue.' } }, 409) : undefined)))
    const dialog = await open()
    await userEvent.selectOptions(within(dialog).getByTestId('jira-project'), 'ABC')
    await userEvent.click(within(dialog).getByTestId('jira-import-submit'))
    expect(await within(dialog).findByTestId('jira-error')).toHaveTextContent('The import did not finish: The Jira connection has expired. Connect again to continue.')
    expect(within(dialog).getByTestId('jira-project')).toHaveValue('ABC')
    expect(screen.queryByTestId('jira-result')).toBeNull()
  })

  it('when the boards cannot be listed the import without a board is still possible', async () => {
    const { calls } = mockApi(service((c) => (c.url.pathname === `${J}/boards` ? json({ error: { code: 'jira_scope_missing', message: 'x' } }, 403) : undefined)))
    const dialog = await open()
    await userEvent.selectOptions(within(dialog).getByTestId('jira-project'), 'ABC')
    expect(await within(dialog).findByTestId('jira-boards-reconnect')).toHaveTextContent('Reconnect Jira to allow board access.')
    expect(within(dialog).queryByTestId('jira-boards-failed')).toBeNull()
    await userEvent.click(within(dialog).getByTestId('jira-import-submit'))
    await screen.findByTestId('jira-result')
    expect(body(calls).project_key).toBe('ABC')
  })

  it('a board refusal (401/403) offers Reconnect, which goes to Jira', async () => {
    mockApi(
      service((c) =>
        c.url.pathname === `${J}/boards`
          ? json({ error: { code: 'jira_scope_missing', message: 'Reconnect Jira to allow board access.' } }, 403)
          : c.method === 'POST' && c.url.pathname === `${J}/connect`
            ? json({ authorize_url: 'https://auth.example/authorize?x=1' })
            : undefined,
      ),
    )
    const dialog = await open()
    await userEvent.selectOptions(within(dialog).getByTestId('jira-project'), 'ABC')
    await userEvent.click(await within(dialog).findByTestId('jira-boards-reconnect-button'))
    await waitFor(() => expect(goTo).toHaveBeenCalledWith('https://auth.example/authorize?x=1'))
  })

  it('other board failures keep the general message', async () => {
    mockApi(service((c) => (c.url.pathname === `${J}/boards` ? json({ error: { code: 'jira_request_failed', message: 'x' } }, 502) : undefined)))
    const dialog = await open()
    await userEvent.selectOptions(within(dialog).getByTestId('jira-project'), 'ABC')
    expect(await within(dialog).findByTestId('jira-boards-failed')).toHaveTextContent('Jira would not list the boards.')
    expect(within(dialog).queryByTestId('jira-boards-reconnect')).toBeNull()
  })

  it('a connection made with fewer permissions asks to reconnect and keeps Import', async () => {
    mockApi(withJira(fx.jiraNeedsReconnect, (c) => (c.method === 'POST' && c.url.pathname === `${J}/connect` ? json({ authorize_url: 'https://auth.example/a' }) : undefined)))
    renderApp(SOURCES)
    expect(await screen.findByTestId('jira-needs-reconnect')).toHaveTextContent('Reconnect Jira to allow board access.')
    expect(screen.getByTestId('jira-import')).toBeEnabled()
    await userEvent.click(screen.getByTestId('jira-reconnect'))
    await waitFor(() => expect(goTo).toHaveBeenCalledWith('https://auth.example/a'))
  })

  it('when the projects cannot be loaded it says so', async () => {
    mockApi(service((c) => (c.url.pathname === `${J}/projects` ? json({ error: { code: 'jira_request_failed', message: 'Jira did not accept the request. Try again later.' } }, 502) : undefined)))
    renderApp(SOURCES)
    await userEvent.click(await screen.findByTestId('jira-import'))
    expect(await screen.findByText('Could not load the Jira projects: Jira did not accept the request. Try again later.')).toBeInTheDocument()
  })

  it('Escape closes it', async () => {
    mockApi(service())
    await open()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('is reachable from the Overview as well', async () => {
    mockApi(service())
    renderApp()
    const card = await screen.findByTestId('jira-card')
    await userEvent.click(await within(card).findByTestId('jira-import'))
    expect(screen.getByRole('dialog', { name: 'Import from Jira' })).toBeInTheDocument()
  })
})

describe('Jira: imported items', () => {
  const ref = { key: 'ABC-12', type: 'Story', status: 'In Progress', url: 'https://acme.atlassian.net/browse/ABC-12' }
  const rowsWith = (jira: typeof ref | null): Handler => (c) => {
    if (c.url.pathname === '/api/projects/1/requirements') return json({ total: 3, limit: 500, offset: 0, items: fx.rows.map((r, i) => (i === 0 ? { ...r, jira } : r)) })
    if (c.url.pathname === '/api/requirements/p1-REQ-001') return json({ ...fx.detail, jira })
    return undefined
  }

  it('the Review Queue row and the detail show the Jira badge, the key, the type and status, and a link', async () => {
    mockApi(rowsWith(ref))
    renderApp('/requirement/review')
    const rows = await screen.findAllByTestId('finding-row')
    expect(within(rows[0]!).getByTestId('row-jira')).toHaveTextContent('ABC-12')
    expect(within(rows[0]!).getByTestId('row-jira')).toHaveAttribute('title', 'Story · In Progress')
    expect(within(rows[0]!).getByTestId('row-jira')).toHaveAttribute('aria-label', 'Jira issue ABC-12')
    expect(within(within(rows[0]!).getByTestId('row-jira')).getByTestId('jira-icon')).toBeInTheDocument() // the Jira icon and the key
    expect(within(rows[1]!).queryByTestId('row-jira')).toBeNull()
    const origin = await screen.findByTestId('detail-jira')
    expect(within(origin).getByTestId('detail-jira-badge')).toHaveTextContent('ABC-12')
    expect(within(origin).getByTestId('detail-jira-status')).toHaveTextContent('Story · In Progress')
    const link = within(origin).getByRole('link', { name: 'Open ABC-12 in Jira' })
    expect(link).toHaveAttribute('href', 'https://acme.atlassian.net/browse/ABC-12')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
  })

  it('the Task Drafts list shows the badge too', async () => {
    mockApi(rowsWith(ref))
    renderApp('/requirement/drafts')
    const rows = await screen.findAllByTestId('finding-row')
    expect(within(rows[0]!).getByTestId('row-jira')).toHaveTextContent('ABC-12')
  })

  it('without an address there is no link, and ordinary requirements have no badge at all', async () => {
    mockApi(rowsWith({ ...ref, url: '' }))
    const first = renderApp('/requirement/review')
    const origin = await screen.findByTestId('detail-jira')
    expect(within(origin).queryByRole('link')).toBeNull()
    first.unmount()
    vi.unstubAllGlobals()
    mockApi()
    renderApp('/requirement/review')
    await screen.findAllByTestId('finding-row')
    await screen.findByTestId('detail-panel')
    expect(screen.queryByTestId('row-jira')).toBeNull()
    expect(screen.queryByTestId('detail-jira')).toBeNull()
  })

  it('a Jira document is listed as a Jira source', async () => {
    const doc = { ...fx.source, id: 5, filename: 'Jira · ABC', ext: '.jira', source_type: 'jira' as const, pages: null }
    mockApi((c) => (c.url.pathname === '/api/projects/1/sources' && c.method === 'GET' ? json([doc]) : undefined))
    renderApp(SOURCES)
    const cards = await screen.findAllByTestId('source-card')
    expect(cards[0]).toHaveTextContent('Jira · ABC')
    expect(within(cards[0]!).getAllByText('Jira').length).toBeGreaterThanOrEqual(1)
    expect(within(cards[0]!).getByTestId('jira-icon')).toBeInTheDocument() // the Jira icon next to a document imported from Jira
  })
})
