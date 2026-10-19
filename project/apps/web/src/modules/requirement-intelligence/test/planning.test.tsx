import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Overview } from '../api/types'
import { groupSources, nextSprintName } from '../lib/planning'
import * as fx from './fixtures'
import { json, mockApi, renderApp } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

const overviewWith = (o: Partial<Overview>) => (c: { url: URL }) => (c.url.pathname === '/api/projects/1/overview' ? json({ ...fx.overview, ...o }) : undefined)
const listCalls = (calls: { url: URL }[]) => calls.filter((c) => c.url.pathname === '/api/projects/1/requirements')

describe('Overview: current sprint card', () => {
  it('shows the sprint, dates, goal and progress from the service, and no phase', async () => {
    mockApi()
    renderApp()
    const card = await screen.findByTestId('current-sprint-card')
    expect(card).toHaveTextContent('Current sprint')
    expect(screen.getByTestId('current-sprint-name')).toHaveTextContent('Sprint 1')
    expect(card).not.toHaveTextContent(/phase/i)
    expect(card).toHaveTextContent('2026-10-05 – 2026-10-16')
    expect(screen.getByTestId('current-sprint-goal')).toHaveTextContent('Goal: Sign-in and accounts')
    expect(card).toHaveTextContent('10 of 30 decided')
    expect(card).toHaveTextContent('20 need a decision')
    expect(within(card).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '10')
  })

  it('leaves out dates and goal when the sprint has none', async () => {
    mockApi(overviewWith({ current_sprint: { ...fx.overview.current_sprint!, start_date: null, end_date: null, goal: null, phase_id: null }, current_phase: null }))
    renderApp()
    const card = await screen.findByTestId('current-sprint-card')
    expect(screen.queryByTestId('current-sprint-goal')).toBeNull()
    expect(card).not.toHaveTextContent('–')
  })

  it('Change: picks another sprint and sets it as current', async () => {
    const { calls } = mockApi((c) => (c.method === 'PUT' && c.url.pathname === '/api/projects/1/current-sprint' ? json({ ...fx.sprints[1]!, is_current: true }) : undefined))
    renderApp()
    await userEvent.click(await screen.findByRole('button', { name: 'Change' }))
    const dialog = screen.getByRole('dialog', { name: 'Change the current sprint' })
    const select = within(dialog).getByTestId('current-sprint-select') as HTMLSelectElement
    expect([...select.options].map((o) => o.textContent)).toEqual(['Sprint 1 (Current)', 'Sprint 2', 'Sprint 3', 'Create a new sprint'])
    expect(select).toHaveValue('1')
    await userEvent.selectOptions(select, '2')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Set as current' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PUT')!.body!)).toEqual({ sprint_id: 2 })
    expect(await screen.findByText('Sprint 2 is now the current sprint.')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('Change: creates a new sprint and makes it current', async () => {
    const { calls } = mockApi((c) => {
      if (c.method === 'POST' && c.url.pathname === '/api/projects/1/sprints') return json({ ...fx.sprints[2]!, id: 7, name: 'Sprint 7' }, 201)
      if (c.method === 'PUT' && c.url.pathname === '/api/projects/1/current-sprint') return json({ ...fx.sprints[2]!, id: 7, name: 'Sprint 7', is_current: true })
      return undefined
    })
    renderApp()
    await userEvent.click(await screen.findByRole('button', { name: 'Change' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.selectOptions(within(dialog).getByTestId('current-sprint-select'), '__new')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Set as current' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Enter a name.')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
    await userEvent.type(within(dialog).getByLabelText('New sprint name'), 'Sprint 7')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Set as current' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'POST')!.body!)).toEqual({ name: 'Sprint 7' })
    expect(JSON.parse(calls.find((c) => c.method === 'PUT')!.body!)).toEqual({ sprint_id: 7 })
  })
})

describe('Overview: charts', () => {
  it('draws one stacked bar per sprint from the service numbers, with a text alternative', async () => {
    mockApi()
    renderApp()
    const chart = await screen.findByTestId('chart-sprints')
    const bars = within(chart).getAllByTestId('sprint-bar')
    expect(bars).toHaveLength(3)
    const parts = [...bars[0]!.querySelectorAll('[data-segment]')].map((e) => [e.getAttribute('data-segment'), e.getAttribute('data-count')])
    expect(parts).toEqual([['accepted', '7'], ['edited', '2'], ['rejected', '1'], ['pending', '20']])
    // one scale for all sprints: Sprint 2 (12 of 30) is shorter than Sprint 1
    const width = (i: number) => parseFloat((bars[i]!.querySelector('[data-segment]')!.parentElement as HTMLElement).style.width)
    expect(width(0)).toBeCloseTo(100)
    expect(width(1)).toBeCloseTo(40)
    expect(width(2)).toBe(0)
    expect(screen.getByTestId('chart-sprints-text')).toHaveTextContent('Sprint 1: 7 accepted, 2 edited, 1 rejected, 20 pending; Sprint 2: 3 accepted, 2 edited, 0 rejected, 7 pending')
    expect(chart).toHaveTextContent('Current')
  })

  it('lists the findings by type with the numbers of the service', async () => {
    mockApi()
    renderApp()
    const chart = await screen.findByTestId('chart-findings')
    expect(within(chart).getAllByTestId('finding-bar').map((b) => [b.getAttribute('data-type'), b.getAttribute('data-count')])).toEqual([['ambiguity', '8'], ['conflict', '2'], ['duplicate', '3'], ['security', '5']])
    expect(screen.getByTestId('chart-findings-text')).toHaveTextContent('Ambiguities: 8; Conflicts: 2; Duplicates: 3; Security: 5')
  })

  it('every chart has a title and works with no data', async () => {
    mockApi(overviewWith({ by_sprint: [], by_phase: [] }))
    renderApp()
    expect(await screen.findByRole('heading', { name: 'Decisions by sprint' })).toBeInTheDocument()
    expect(screen.getByTestId('chart-sprints')).toHaveTextContent('Nothing to show yet.')
    expect(screen.queryByTestId('chart-phases')).toBeNull()
  })
})

describe('grouping helper', () => {
  it('lists sprints only, the current one first, and documents without a sprint last', () => {
    const lonely = { ...fx.source, id: 5, default_sprint_id: null, sprints: [] }
    const moved = [{ ...fx.sprints[0]!, position: 3 }, { ...fx.sprints[1]!, position: 1 }, fx.sprints[2]!]
    const groups = groupSources(moved, [fx.source, fx.source2, lonely])
    expect(groups.map((g) => g.sprint?.name ?? 'Unassigned')).toEqual(['Sprint 1', 'Sprint 2', 'Sprint 3', 'Unassigned'])
    expect(groups[0]!.docs.map((d) => [d.source.id, d.count])).toEqual([[1, 30]])
    expect(groups[1]!.docs.map((d) => [d.source.id, d.count])).toEqual([[1, 12]])
    expect(groups[2]!.docs.map((d) => d.source.id)).toEqual([2])
    expect(groups[3]!.docs.map((d) => d.source.id)).toEqual([5])
  })

  it('has no Unassigned group when every document has a sprint', () => {
    expect(groupSources(fx.sprints, [fx.source, fx.source2]).map((g) => g.key)).toEqual(['sprint-1', 'sprint-2', 'sprint-3'])
  })

  it('offers Sprint N+1 as the next name', () => {
    expect(nextSprintName(fx.sprints)).toBe('Sprint 4')
    expect(nextSprintName([])).toBe('Sprint 1')
    expect(nextSprintName([{ ...fx.sprints[0]!, name: 'Sprint 7' }, { ...fx.sprints[1]!, name: 'Login' }])).toBe('Sprint 8')
    expect(nextSprintName([{ ...fx.sprints[0]!, name: 'Alpha' }, { ...fx.sprints[1]!, name: 'Beta' }, { ...fx.sprints[2]!, name: 'Gamma' }])).toBe('Sprint 4')
  })
})

describe('Review Queue: Filters panel', () => {
  const REVIEW = '/requirement/review'
  const open = async () => {
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('filters-button'))
    return screen.getByTestId('filters-panel')
  }

  it('keeps the status chips and puts the other filters in one panel', async () => {
    mockApi()
    renderApp(REVIEW)
    const panel = await open()
    expect(screen.getByTestId('status-pending')).toBeInTheDocument()
    for (const label of ['Risk level', 'Finding type', 'Suggested action', 'Sprint', 'Document']) expect(within(panel).getByLabelText(label)).toBeInTheDocument()
    expect(within(panel).queryByLabelText('Phase')).toBeNull()
    expect(screen.queryByTestId('filter-chips')).toBeNull()
    expect(screen.getByTestId('filters-button')).toHaveTextContent('Filters')
  })

  it('shows a removable chip for every active filter, and the button counts them', async () => {
    const { calls } = mockApi()
    renderApp(REVIEW)
    const panel = await open()
    await userEvent.selectOptions(within(panel).getByLabelText('Risk level'), 'HIGH')
    await userEvent.selectOptions(within(panel).getByLabelText('Sprint'), '2')
    await userEvent.selectOptions(within(panel).getByLabelText('Document'), 'CoreBanking_SRS_v2.pdf')
    await userEvent.click(within(panel).getByRole('button', { name: 'Done' }))
    expect(screen.getByTestId('filters-button')).toHaveTextContent('Filters (3)')
    expect(screen.getAllByTestId('filter-chip').map((c) => c.textContent)).toEqual(['Risk: HIGH', 'Sprint: Sprint 2', 'Document: CoreBanking_SRS_v2.pdf'])
    await waitFor(() => expect(listCalls(calls).some((c) => c.url.searchParams.get('risk') === 'HIGH' && c.url.searchParams.get('sprint_id') === '2')).toBe(true))
    await userEvent.click(screen.getByRole('button', { name: 'Remove filter: Sprint: Sprint 2' }))
    expect(screen.getAllByTestId('filter-chip')).toHaveLength(2)
    expect(screen.getByTestId('filters-button')).toHaveTextContent('Filters (2)')
    await waitFor(() => expect(listCalls(calls).at(-1)!.url.searchParams.has('sprint_id')).toBe(false))
    await userEvent.click(screen.getByTestId('filters-button'))
    await userEvent.click(screen.getByRole('button', { name: 'Clear all filters' }))
    expect(screen.queryByTestId('filter-chips')).toBeNull()
    expect(screen.getByTestId('filters-button')).toHaveTextContent('Filters')
  })

  it('the document filter narrows the list', async () => {
    mockApi()
    renderApp(REVIEW)
    const panel = await open()
    expect(screen.getAllByTestId('finding-row')).toHaveLength(3)
    await userEvent.selectOptions(within(panel).getByLabelText('Document'), 'CoreBanking_SRS_v2.pdf')
    expect(screen.getAllByTestId('finding-row')).toHaveLength(3)
    expect(screen.getAllByTestId('filter-chip').map((c) => c.textContent)).toEqual(['Document: CoreBanking_SRS_v2.pdf'])
  })

  it('shows the sprint on the rows, and no sprint chip in the detail header', async () => {
    mockApi()
    renderApp(REVIEW)
    const rows = await screen.findAllByTestId('finding-row')
    expect(rows.map((r) => within(r).getByTestId('row-sprint').textContent)).toEqual(['Sprint 1', 'Sprint 1', 'Sprint 2'])
    await screen.findByTestId('detail-id')
    expect(screen.queryByTestId('detail-sprint')).toBeNull()
  })

  it('Escape closes the panel', async () => {
    mockApi()
    renderApp(REVIEW)
    await open()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByTestId('filters-panel')).toBeNull()
  })
})

describe('Review Queue: select and move to a sprint', () => {
  const REVIEW = '/requirement/review'
  const assign = (calls: { method: string; url: URL }[]) => calls.find((c) => c.method === 'POST' && c.url.pathname === '/api/projects/1/requirements/assign') as { body?: string } | undefined

  it('Select shows a checkbox on every row; Move to sprint needs a selection', async () => {
    mockApi()
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    expect(screen.queryAllByTestId('row-check')).toHaveLength(0)
    await userEvent.click(screen.getByTestId('select-mode'))
    expect(screen.getAllByTestId('row-check')).toHaveLength(3)
    expect(screen.getByTestId('selected-count')).toHaveTextContent('0 selected')
    expect(screen.getByTestId('move-selected')).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select REQ-001' }))
    expect(screen.getByTestId('selected-count')).toHaveTextContent('1 selected')
    expect(screen.getByTestId('move-selected')).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: 'Select all shown' }))
    expect(screen.getByTestId('selected-count')).toHaveTextContent('3 selected')
    await userEvent.click(screen.getByTestId('select-mode')) // leaving the mode forgets the selection
    expect(screen.queryAllByTestId('row-check')).toHaveLength(0)
  })

  it('moves the selected requirements to the chosen sprint', async () => {
    const { calls } = mockApi((c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/requirements/assign' ? json({ assigned: 2, sprint_id: 2 }) : undefined))
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('select-mode'))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select REQ-001' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select REQ-002' }))
    await userEvent.click(screen.getByTestId('move-selected'))
    const dialog = screen.getByRole('dialog', { name: 'Move 2 requirements to a sprint' })
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
    await userEvent.selectOptions(within(dialog).getByTestId('bulk-sprint'), '2')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Move' }))
    await waitFor(() => expect(assign(calls)).toBeTruthy())
    expect(JSON.parse(assign(calls)!.body!)).toEqual({ requirement_ids: ['p1-REQ-001', 'p1-REQ-002'], sprint_id: 2 })
    expect(await screen.findByText('2 requirements moved to Sprint 2.')).toBeInTheDocument()
    expect(screen.queryAllByTestId('row-check')).toHaveLength(0)
  })

  it('"Follow the document again" sends a null sprint', async () => {
    const { calls } = mockApi((c) => (c.method === 'POST' && c.url.pathname === '/api/projects/1/requirements/assign' ? json({ assigned: 1, sprint_id: null }) : undefined))
    renderApp(REVIEW)
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('select-mode'))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select REQ-003' }))
    await userEvent.click(screen.getByTestId('move-selected'))
    await userEvent.selectOptions(screen.getByTestId('bulk-sprint'), '__follow')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Move' }))
    await waitFor(() => expect(assign(calls)).toBeTruthy())
    expect(JSON.parse(assign(calls)!.body!)).toEqual({ requirement_ids: ['p1-REQ-003'], sprint_id: null })
    expect(await screen.findByText('1 requirement follows its document again.')).toBeInTheDocument()
  })
})

describe('Task Drafts: sprint filter', () => {
  it('offers only the sprint filter and sends it to the service', async () => {
    const { calls } = mockApi()
    renderApp('/requirement/drafts')
    await screen.findAllByTestId('finding-row')
    await userEvent.click(screen.getByTestId('filters-button'))
    const panel = screen.getByTestId('filters-panel')
    expect(within(panel).getByLabelText('Sprint')).toBeInTheDocument()
    for (const label of ['Risk level', 'Finding type', 'Suggested action', 'Phase', 'Document']) expect(within(panel).queryByLabelText(label)).toBeNull()
    await userEvent.selectOptions(within(panel).getByLabelText('Sprint'), '1')
    await waitFor(() => expect(listCalls(calls).some((c) => c.url.searchParams.get('sprint_id') === '1')).toBe(true))
    expect(screen.getByTestId('filter-chip')).toHaveTextContent('Sprint: Sprint 1')
  })
})

describe('header pill', () => {
  it('shows only “AI engine” with a status dot: no device or cloud wording, no model or host', async () => {
    mockApi()
    renderApp()
    const pill = await screen.findByTestId('engine-pill')
    await waitFor(() => expect(pill).toHaveAttribute('data-state', 'ready'))
    expect(pill.textContent?.trim()).toBe('AI engine')
    expect(pill.querySelector('span[aria-hidden="true"]')).not.toBeNull()
    expect(pill).not.toHaveTextContent(/device|cloud|c1-req|ollama|replay/i)
    expect(pill).toHaveAttribute('aria-label', 'AI engine: Ready')
  })
})

describe('Overview: process strip', () => {
  const stages = () => screen.getAllByTestId('process-stage')
  const withPipeline = (p: Partial<Overview['pipeline']>) => overviewWith({ pipeline: { ...fx.overview.pipeline, ...p } })
  const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })

  it('shows the five stages in order with a state and a live detail from the service', async () => {
    mockApi()
    renderApp()
    await screen.findByTestId('process-strip')
    expect(stages().map((s) => [s.getAttribute('data-stage'), s.getAttribute('data-state')])).toEqual([['collect', 'done'], ['identify', 'done'], ['analyse', 'waiting'], ['improve', 'active'], ['share', 'done']])
    expect(stages().map((s) => within(s).getByRole('link').textContent)).toEqual([
      'CollectDone2 documents',
      'IdentifyDone42 requirements',
      'AnalyseWaiting1 of 2 analysed',
      'ImproveIn progress15 of 42 decided · 31 drafts · 1 failed',
      `ShareDoneSynced ${clock(fx.sync.last_synced_at!)}`,
    ])
  })

  it('every stage opens its page', async () => {
    mockApi()
    renderApp()
    await screen.findByTestId('process-strip')
    expect(stages().map((s) => within(s).getByRole('link').getAttribute('href'))).toEqual(['/requirement/sources', '/requirement/sources', '/requirement/sources', '/requirement/drafts?filter=failed', '/requirement#knowledge-graph'])
    await userEvent.click(within(stages()[3]!).getByRole('link'))
    expect(await screen.findByTestId('workspace')).toBeInTheDocument()
  })

  it('shows each state: done, in progress, waiting and failed', async () => {
    mockApi(
      withPipeline({
        collect: { state: 'waiting', documents: 0 },
        identify: { state: 'active', documents: 3, requirements: 0 },
        analyse: { state: 'failed', analysed: 1, total: 3, failed: 1 },
        improve: { state: 'done', requirements: 42, decided: 42, drafts_written: 42, drafts: { ready: 40, needs_clarification: 2, failed: 0, waiting: 0 } },
        share: { state: 'active', sync_state: 'syncing', last_synced_at: null },
      }),
    )
    renderApp()
    await screen.findByTestId('process-strip')
    expect(stages().map((s) => within(s).getByTestId('stage-state').textContent)).toEqual(['Waiting', 'In progress', 'Failed', 'Done', 'In progress'])
    expect(stages().map((s) => within(s).getByTestId('stage-detail').textContent)).toEqual(['0 documents', '0 requirements', '1 of 3 analysed · 1 failed', '42 of 42 decided · 42 drafts', 'Syncing'])
  })

  it('names drafts that are still being written or failed, and the other sync states', async () => {
    mockApi(withPipeline({ improve: { state: 'active', requirements: 334, decided: 5, drafts_written: 173, drafts: { ready: 170, needs_clarification: 3, failed: 2, waiting: 4 } }, share: { state: 'waiting', sync_state: 'not_configured', last_synced_at: null } }))
    renderApp()
    await screen.findByTestId('process-strip')
    expect(within(stages()[3]!).getByTestId('stage-detail')).toHaveTextContent('5 of 334 decided · 173 drafts · 4 in progress · 2 failed')
    expect(within(stages()[4]!).getByTestId('stage-detail')).toHaveTextContent('Not connected')
  })

  it('each stage has one accessible name with its state and detail', async () => {
    mockApi()
    renderApp()
    await screen.findByTestId('process-strip')
    expect(screen.getByRole('link', { name: 'Analyse: Waiting. 1 of 2 analysed' })).toBeInTheDocument()
  })
})

describe('Overview: no phases', () => {
  it('the overview, the current sprint and the latest uploads never mention a phase', async () => {
    mockApi()
    renderApp()
    await screen.findByTestId('process-strip')
    await screen.findByTestId('latest-uploads')
    expect(document.body.textContent).not.toMatch(/phase/i)
    expect(screen.queryByTestId('chart-phases')).toBeNull()
  })
})
