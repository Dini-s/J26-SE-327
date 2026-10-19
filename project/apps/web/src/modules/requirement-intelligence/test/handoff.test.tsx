import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '../api/client'
import type { SyncStatus } from '../api/types'
import { publishErrorMessage } from '../lib/handoff'
import * as fx from './fixtures'
import { json, mockApi, renderApp } from './utils'

afterEach(() => vi.unstubAllGlobals())

const WHEN = '2026-10-16T08:00:00+00:00'
const at = () => new Date(WHEN).toLocaleString()
const sync = (o: Partial<SyncStatus> = {}): SyncStatus => ({ ...fx.sync, ...o })
const withSync = (s: SyncStatus) => (c: { url: URL }) => (c.url.pathname === '/api/projects/1/overview' ? json({ ...fx.overview, sync: s }) : undefined)
const PUBLISH = '/api/projects/1/publish/neo4j'

describe('publishErrorMessage', () => {
  it('maps errors by code, not by the service text', () => {
    expect(publishErrorMessage(new ApiClientError(503, 'neo4j_unreachable', 'Could not reach Neo4j within 5 seconds.'))).toBe('The knowledge graph cannot be reached. Check that it is running, then try again.')
    expect(publishErrorMessage(new ApiClientError(503, 'neo4j_auth_failed', 'Neo4j refused the user name or password.'))).not.toMatch(/Neo4j/)
    expect(publishErrorMessage(new ApiClientError(0, 'network_error', 'Cannot reach the service at x.'))).toBe('Cannot reach the service at x.')
    expect(publishErrorMessage(new Error('whatever'))).toBe('Publishing failed. Try again.')
  })
})

describe('Knowledge graph card: the sync state in plain words', () => {
  it.each([
    ['synced', sync({ state: 'synced', last_synced_at: WHEN }), () => `Synced at ${at()}`],
    ['syncing', sync({ state: 'syncing' }), () => 'Syncing'],
    ['pending', sync({ state: 'pending', next_attempt_at: WHEN }), () => 'Changes waiting'],
    ['retrying', sync({ state: 'retrying', error: 'neo4j_unreachable', next_attempt_at: WHEN }), () => 'Retrying'],
    ['unreachable', sync({ state: 'unreachable', error: 'neo4j_unreachable', next_attempt_at: WHEN }), () => 'Retrying'],
    ['not_configured', sync({ state: 'not_configured', last_synced_at: null, counts: null }), () => 'Not connected'],
  ])('%s', async (state, s, text) => {
    mockApi(withSync(s))
    renderApp()
    const line = await screen.findByTestId('sync-state')
    expect(line).toHaveAttribute('data-state', state)
    expect(line).toHaveTextContent(text())
    expect(document.body).not.toHaveTextContent(/Neo4j|publish/i)
  })

  it('says what to do when it cannot be reached, and when it is not set up', async () => {
    mockApi(withSync(sync({ state: 'unreachable', error: 'neo4j_unreachable' })))
    const first = renderApp()
    expect(await screen.findByTestId('sync-hint')).toHaveTextContent('still tried again every few minutes')
    first.unmount()
    vi.unstubAllGlobals()
    mockApi(withSync(sync({ state: 'not_configured', last_synced_at: null })))
    renderApp()
    expect(await screen.findByTestId('sync-hint')).toHaveTextContent('Ask your administrator')
    expect(screen.getByTestId('sync-now')).toBeDisabled()
  })

  it('has no Publish button: Sync now is a small link inside the details, next to the last sync', async () => {
    mockApi()
    renderApp()
    const card = await screen.findByTestId('graph-card')
    expect(within(card).queryByRole('button', { name: /Publish/i })).toBeNull()
    const details = within(card).getByTestId('sync-details')
    expect(details).toHaveTextContent('Last sync')
    expect(details).toHaveTextContent(new Date(fx.sync.last_synced_at!).toLocaleString())
    expect(details).toHaveTextContent('42 requirements')
    expect(within(details).getByTestId('sync-now')).toHaveTextContent('Sync now')
    expect(within(card).getByRole('button', { name: /Export/ })).toBeInTheDocument()
  })

  it('Sync now sends a POST without a body, says how many were synced and refreshes the state', async () => {
    let state = sync({ state: 'pending' })
    const { calls } = mockApi((c) => {
      if (c.url.pathname === PUBLISH && c.method === 'POST') {
        state = sync({ state: 'synced', last_synced_at: WHEN })
        return json({ project_id: 'demo-project', published_at: WHEN, seconds: 0.4, counts: { Requirement: 42 }, deactivated: {}, content_hash: 'x' })
      }
      return withSync(state)(c)
    })
    renderApp()
    await screen.findByTestId('sync-state')
    await userEvent.click(screen.getByTestId('sync-now'))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.pathname === PUBLISH)).toBe(true))
    expect(calls.find((c) => c.method === 'POST' && c.url.pathname === PUBLISH)!.body).toBeUndefined()
    expect(await screen.findByText('Synced 42 requirements to the knowledge graph.')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('sync-state')).toHaveAttribute('data-state', 'synced'))
  })

  it('a failed Sync now shows a plain message by code, never the service text', async () => {
    mockApi((c) => (c.url.pathname === PUBLISH && c.method === 'POST' ? json({ error: { code: 'neo4j_unreachable', message: 'Could not reach Neo4j within 5 seconds.' } }, 503) : undefined))
    renderApp()
    await userEvent.click(await screen.findByTestId('sync-now'))
    expect(await screen.findByText('The knowledge graph cannot be reached. Check that it is running, then try again.')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/Neo4j/i)
  })

  it('the Integrations card offers Connect Jira (tests/jira.test.tsx covers every state)', async () => {
    mockApi()
    renderApp()
    const card = await screen.findByTestId('jira-card')
    const button = await within(card).findByRole('button', { name: /Connect Jira/ })
    await waitFor(() => expect(button).toBeEnabled())
    expect(card).not.toHaveTextContent('Coming soon')
  })
})
