import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Engine, Generation, TaskDrafts } from '../api/types'
import { DraftCard } from '../components/DraftCard'
import { DraftProgress } from '../components/DraftProgress'
import { CloudUnreachableBanner, EngineSwitch } from '../components/EngineSwitch'
import { Sidebar } from '../components/Sidebar'
import { ENGINE_409, engineStatus, targetLabel } from '../lib/engine'
import * as fx from './fixtures'
import { json, mockApi, renderApp, renderWithProviders, type Call } from './utils'

afterEach(() => vi.unstubAllGlobals())

const HOST = 'gpu.example.com'
const KEY = 'sk-secret-key-123'
const cloudReadyEngine = (over: Partial<Engine> = {}): Engine => ({
  ...fx.engine,
  cloud: { configured: true, host: HOST, model: 'c1-req', concurrency: 4, consent: true, consent_at: '2026-10-16T08:00:00+00:00', reachable: true, last_tested_at: '2026-10-16T08:01:00+00:00' },
  ...over,
})
const onCloud = (): Engine => ({ ...cloudReadyEngine(), target: 'cloud' })
const err = (code: string, message = 'raw message') => json({ error: { code, message } }, 409)

const bodyOf = (c: Call) => JSON.parse(c.body ?? '{}') as Record<string, unknown>
const putCalls = (calls: Call[]) => calls.filter((c) => c.url.pathname === '/api/engine' && c.method === 'PUT')

const show = (engine: Engine | undefined, cloudPaused = false) => renderWithProviders(<EngineSwitch engine={engine} cloudPaused={cloudPaused} />)
const cloudSegment = () => screen.getByRole('radio', { name: /cloud/i })
const openGear = async () => userEvent.click(screen.getByRole('button', { name: 'Cloud settings' }))

// ---------------------------------------------------------------------------------------------------------------- the switch
describe('Process switch', () => {
  it('shows the device as the active target and keeps Cloud disabled, reading "Set up cloud…", until it is set up', () => {
    mockApi()
    show(fx.engine)
    expect(screen.getByText('Process:')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /on device/i })).toBeChecked()
    const cloud = cloudSegment()
    expect(cloud).toHaveTextContent('Set up cloud…')
    expect(cloud).toBeDisabled()
    expect(cloud).not.toBeChecked()
    const status = screen.getByTestId('engine-status')
    expect(status).toHaveAttribute('data-state', 'ready')
    expect(status).toHaveTextContent('Ready')
    expect(status).toHaveTextContent('c1-req')
    expect(status).toHaveTextContent('On device')
  })

  it.each([
    ['not consented', { consent: false }],
    ['not tested', { reachable: null }],
    ['last test failed', { reachable: false }],
    ['not configured', { configured: false, host: null }],
  ])('Cloud stays disabled when it is %s', (_n, patch) => {
    mockApi()
    const e = cloudReadyEngine()
    show({ ...e, cloud: { ...e.cloud, ...patch } })
    expect(cloudSegment()).toBeDisabled()
    expect(cloudSegment()).toHaveTextContent('Set up cloud…')
  })

  it('Cloud is enabled once configured, consented and tested', () => {
    mockApi()
    show(cloudReadyEngine())
    expect(cloudSegment()).toBeEnabled()
    expect(cloudSegment()).toHaveTextContent(/^\s*Cloud\s*$/)
  })

  it('when the server mode does not allow cloud: Cloud is disabled, says so and has no gear', () => {
    mockApi()
    show({ ...fx.engine, cloud_available: false, cloud_disabled_reason: 'Cloud is disabled while the generation backend is replay or mock.' })
    expect(cloudSegment()).toBeDisabled()
    expect(cloudSegment()).toHaveTextContent('Cloud unavailable')
    expect(cloudSegment()).toHaveAttribute('title', expect.stringContaining('replay or mock'))
    expect(screen.queryByRole('button', { name: 'Cloud settings' })).toBeNull()
  })

  it('has accessible names for the group, both choices and the gear', () => {
    mockApi()
    show(fx.engine)
    expect(screen.getByRole('radiogroup', { name: 'Process:' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /on device/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cloud settings' })).toHaveAttribute('aria-haspopup', 'dialog')
  })

  it('status of each state: ready (device), unreachable (device down), unreachable (cloud paused), ready (cloud), checking', () => {
    expect(engineStatus(undefined, false)).toBe('checking')
    expect(engineStatus(fx.engine, false)).toBe('ready')
    expect(engineStatus({ ...fx.engine, device: { ...fx.engine.device, reachable: false } }, false)).toBe('unreachable')
    expect(engineStatus(onCloud(), false)).toBe('ready')
    expect(engineStatus(onCloud(), true)).toBe('unreachable')
    expect(engineStatus({ ...onCloud(), cloud: { ...onCloud().cloud, reachable: false } }, false)).toBe('unreachable')
    expect(engineStatus({ ...onCloud(), cloud: { ...onCloud().cloud, configured: false, reachable: null } }, false)).toBe('not_set_up')
  })

  it('shows "Unreachable" with the cloud model when the queue paused itself', () => {
    mockApi()
    show(onCloud(), true)
    const status = screen.getByTestId('engine-status')
    expect(status).toHaveAttribute('data-state', 'unreachable')
    expect(status).toHaveTextContent('Unreachable')
    expect(status).toHaveTextContent(`Cloud (${HOST})`)
  })

  it('switching: choosing Cloud then On device sends the target and the page follows the answer', async () => {
    const state = { engine: cloudReadyEngine() }
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/engine' && c.method === 'GET') return json(state.engine)
      if (c.url.pathname === '/api/engine' && c.method === 'PUT') {
        state.engine = { ...state.engine, target: bodyOf(c).target as Engine['target'] }
        return json(state.engine)
      }
      return undefined
    })
    renderApp()
    const group = await screen.findByRole('radiogroup', { name: 'Process:' })
    await waitFor(() => expect(within(group).getByRole('radio', { name: /cloud/i })).toBeEnabled())
    await userEvent.click(within(group).getByRole('radio', { name: /cloud/i }))
    await waitFor(() => expect(within(group).getByRole('radio', { name: /cloud/i })).toBeChecked())
    expect(bodyOf(putCalls(calls)[0]!)).toEqual({ target: 'cloud' })
    expect(screen.getByTestId('engine-status')).toHaveTextContent(`Cloud (${HOST})`)
    await userEvent.click(within(group).getByRole('radio', { name: /on device/i }))
    await waitFor(() => expect(within(group).getByRole('radio', { name: /on device/i })).toBeChecked())
    expect(bodyOf(putCalls(calls)[1]!)).toEqual({ target: 'device' })
  })

  it.each(Object.keys(ENGINE_409))('409 %s is shown as a plain sentence, never as JSON', async (code) => {
    mockApi((c) => (c.url.pathname === '/api/engine' && c.method === 'PUT' ? err(code, '{"raw":"json"}') : undefined))
    show(cloudReadyEngine())
    await userEvent.click(cloudSegment())
    const msg = await screen.findByTestId('engine-error')
    expect(msg).toHaveTextContent(ENGINE_409[code]!)
    expect(msg.textContent).not.toMatch(/[{}]|"error"|raw/)
    expect(msg).toHaveAttribute('role', 'alert')
  })

  it('has one plain sentence for each documented 409 code', () => {
    expect(Object.keys(ENGINE_409).sort()).toEqual(['cloud_consent_required', 'cloud_disabled', 'cloud_not_configured', 'cloud_not_tested', 'engine_in_use'])
    expect(ENGINE_409.cloud_disabled).toMatch(/server mode does not allow cloud/i)
    expect(ENGINE_409.cloud_not_configured).toMatch(/enter the cloud url first/i)
    expect(ENGINE_409.cloud_consent_required).toMatch(/tick the box/i)
    expect(ENGINE_409.cloud_not_tested).toMatch(/run test connection first/i)
    expect(ENGINE_409.engine_in_use).toMatch(/switch to on device first/i)
  })
})

// ---------------------------------------------------------------------------------------------------------------- the popover
describe('Cloud settings popover', () => {
  it('opens from the gear with every field, defaults and the consent text; Escape closes it and returns the focus', async () => {
    mockApi()
    show(fx.engine)
    await openGear()
    const dialog = screen.getByRole('dialog', { name: 'Cloud settings' })
    expect(within(dialog).getByLabelText('Cloud URL (https)')).toHaveValue('')
    expect(within(dialog).getByLabelText('API key (optional)')).toHaveAttribute('type', 'password')
    expect(within(dialog).getByLabelText('Model name')).toHaveValue('c1-req')
    expect(within(dialog).getByLabelText('Parallel requests')).toHaveValue(4)
    expect(within(dialog).getByRole('checkbox', { name: 'Requirement text will be sent to this server' })).not.toBeChecked()
    expect(within(dialog).getByRole('button', { name: /test connection/i })).toBeEnabled()
    expect(within(dialog).getByRole('button', { name: 'Save' })).toBeEnabled()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('button', { name: 'Cloud settings' })).toHaveFocus()
  })

  it('validates before anything is sent: empty address and no consent', async () => {
    const { calls } = mockApi()
    show(fx.engine)
    await openGear()
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(screen.getByText(/enter the cloud url/i)).toBeInTheDocument()
    expect(screen.getByText(/tick this box to allow requirement text/i)).toBeInTheDocument()
    expect(putCalls(calls)).toHaveLength(0)
  })

  it.each([
    ['http://example.com', /starts with https/i],
    ['example.com', /starts with https/i],
    ['https://user:pw@example.com', /starts with https/i],
    ['https://example.com/?x=1', /starts with https/i],
  ])('rejects the address %s', async (value, message) => {
    const { calls } = mockApi()
    show(fx.engine)
    await openGear()
    await userEvent.type(screen.getByLabelText('Cloud URL (https)'), value)
    await userEvent.click(screen.getByRole('checkbox', { name: /will be sent/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(putCalls(calls)).toHaveLength(0)
  })

  it.each(['0', '9', '2.5', ''])('rejects %j parallel requests', async (value) => {
    const { calls } = mockApi()
    show(fx.engine)
    await openGear()
    await userEvent.type(screen.getByLabelText('Cloud URL (https)'), 'https://x.example.com')
    await userEvent.click(screen.getByRole('checkbox', { name: /will be sent/i }))
    const n = screen.getByLabelText('Parallel requests')
    await userEvent.clear(n)
    if (value) await userEvent.type(n, value)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/whole number from 1 to 8/i)).toBeInTheDocument()
    expect(putCalls(calls)).toHaveLength(0)
  })

  it('rejects an empty model name', async () => {
    mockApi()
    show(fx.engine)
    await openGear()
    await userEvent.type(screen.getByLabelText('Cloud URL (https)'), 'https://x.example.com')
    await userEvent.click(screen.getByRole('checkbox', { name: /will be sent/i }))
    await userEvent.clear(screen.getByLabelText('Model name'))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/enter the model name/i)).toBeInTheDocument()
  })

  it('Save sends only what changed; afterwards the key field is empty and the page shows "saved" but never the key', async () => {
    const saved = cloudReadyEngine({ cloud: { ...cloudReadyEngine().cloud, reachable: null } })
    const { calls } = mockApi((c) => (c.url.pathname === '/api/engine' && c.method === 'PUT' ? json(saved) : undefined))
    show(fx.engine)
    await openGear()
    await userEvent.type(screen.getByLabelText('Cloud URL (https)'), `https://${HOST}/v1`)
    await userEvent.type(screen.getByLabelText('API key (optional)'), KEY)
    await userEvent.click(screen.getByRole('checkbox', { name: /will be sent/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByTestId('key-saved')
    expect(bodyOf(putCalls(calls)[0]!)).toEqual({ cloud_url: `https://${HOST}/v1`, cloud_api_key: KEY, cloud_consent: true })
    expect(screen.getByTestId('key-saved')).toHaveTextContent('saved')
    expect(screen.getByLabelText('API key (optional)')).toHaveValue('')
    expect(screen.getByLabelText('Cloud URL (https)')).toHaveValue('')
    expect(document.body.textContent).not.toContain(KEY)
    expect((screen.getByLabelText('API key (optional)') as HTMLInputElement).value).not.toContain(KEY)
  })

  it('once an address is saved the form shows only its host name, never the address', async () => {
    mockApi()
    show(cloudReadyEngine())
    await openGear()
    const url = screen.getByLabelText('Cloud URL (https)')
    expect(url).toHaveValue('')
    expect(url).toHaveAttribute('placeholder', expect.stringContaining(HOST))
    expect(screen.getByTestId('cloud-state')).toHaveTextContent(`Tested OK · ${HOST}`)
    expect(screen.getByRole('dialog').textContent).not.toContain('https://')
  })

  it('Remove key sends an empty key on Save', async () => {
    const { calls } = mockApi((c) => (c.url.pathname === '/api/engine' && c.method === 'PUT' ? json(cloudReadyEngine()) : undefined))
    show(cloudReadyEngine())
    await openGear()
    await userEvent.type(screen.getByLabelText('API key (optional)'), KEY)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByTestId('key-saved')
    await userEvent.click(screen.getByRole('button', { name: 'Remove key' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(putCalls(calls)).toHaveLength(2))
    expect(bodyOf(putCalls(calls)[1]!)).toEqual({ cloud_api_key: '' })
    await waitFor(() => expect(screen.queryByTestId('key-saved')).toBeNull())
  })

  it('shows the API error of a bad address as a plain sentence', async () => {
    mockApi((c) => (c.url.pathname === '/api/engine' && c.method === 'PUT' ? json({ error: { code: 'invalid_cloud_url', message: 'cloud_url must not contain a query string or a fragment.' } }, 400) : undefined))
    show(fx.engine)
    await openGear()
    await userEvent.type(screen.getByLabelText('Cloud URL (https)'), 'https://x.example.com')
    await userEvent.click(screen.getByRole('checkbox', { name: /will be sent/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByTestId('cloud-form-message')).toHaveTextContent('must not contain a query string')
  })

  it('Test connection saves the form first, then shows the success text and the time', async () => {
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/engine' && c.method === 'PUT') return json(cloudReadyEngine({ cloud: { ...cloudReadyEngine().cloud, reachable: null } }))
      if (c.url.pathname === '/api/engine/test') return json({ ok: true, detail: "Connected; model 'c1-req' is served.", latency_ms: 212 })
      return undefined
    })
    show(fx.engine)
    await openGear()
    await userEvent.type(screen.getByLabelText('Cloud URL (https)'), `https://${HOST}`)
    await userEvent.click(screen.getByRole('checkbox', { name: /will be sent/i }))
    await userEvent.click(screen.getByRole('button', { name: /test connection/i }))
    const result = await screen.findByTestId('cloud-test-result')
    expect(result).toHaveAttribute('data-ok', 'true')
    expect(result).toHaveTextContent("Connected; model 'c1-req' is served. (212 ms)")
    const order = calls.filter((c) => c.url.pathname.startsWith('/api/engine') && c.method !== 'GET').map((c) => `${c.method} ${c.url.pathname}`)
    expect(order).toEqual(['PUT /api/engine', 'POST /api/engine/test'])
    expect(bodyOf(calls.find((c) => c.url.pathname === '/api/engine/test')!)).toEqual({ target: 'cloud' })
  })

  it('Test connection shows a failure with the sanitised text', async () => {
    mockApi((c) => (c.url.pathname === '/api/engine/test' ? json({ ok: false, detail: 'The server answered HTTP 401. Check the API key.', latency_ms: null }) : undefined))
    show(cloudReadyEngine())
    await openGear()
    await userEvent.click(screen.getByRole('button', { name: /test connection/i }))
    const result = await screen.findByTestId('cloud-test-result')
    expect(result).toHaveAttribute('data-ok', 'false')
    expect(result).toHaveTextContent('The server answered HTTP 401. Check the API key.')
  })

  it('Test connection without an address shows the cloud_not_configured sentence from the API', async () => {
    mockApi((c) => {
      if (c.url.pathname === '/api/engine' && c.method === 'PUT') return json(fx.engine) // the form is saved first
      if (c.url.pathname === '/api/engine/test') return err('cloud_not_configured')
      return undefined
    })
    show({ ...fx.engine, cloud: { ...fx.engine.cloud, consent: true } })
    await openGear()
    await userEvent.type(screen.getByLabelText('Cloud URL (https)'), 'https://x.example.com')
    await userEvent.click(screen.getByRole('button', { name: /test connection/i }))
    expect(await screen.findByTestId('cloud-form-message')).toHaveTextContent(ENGINE_409.cloud_not_configured!)
  })

  it('locks the address, key and model while Cloud is active, but leaves parallel requests and consent editable', async () => {
    const { calls } = mockApi((c) => (c.url.pathname === '/api/engine' && c.method === 'PUT' ? json(onCloud()) : undefined))
    show(onCloud())
    await openGear()
    expect(screen.getByTestId('cloud-locked')).toBeInTheDocument()
    expect(screen.getByLabelText('Cloud URL (https)')).toBeDisabled()
    expect(screen.getByLabelText('API key (optional)')).toBeDisabled()
    expect(screen.getByLabelText('Model name')).toBeDisabled()
    const n = screen.getByLabelText('Parallel requests')
    expect(n).toBeEnabled()
    await userEvent.clear(n)
    await userEvent.type(n, '6')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(putCalls(calls)).toHaveLength(1))
    expect(bodyOf(putCalls(calls)[0]!)).toEqual({ cloud_concurrency: 6 })
  })

  it('engine_in_use on Save is explained in plain words', async () => {
    mockApi((c) => (c.url.pathname === '/api/engine' && c.method === 'PUT' ? err('engine_in_use') : undefined))
    show(cloudReadyEngine())
    await openGear()
    await userEvent.type(screen.getByLabelText('Cloud URL (https)'), 'https://other.example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByTestId('cloud-form-message')).toHaveTextContent(ENGINE_409.engine_in_use!)
  })
})

// ---------------------------------------------------------------------------------------------------------------- status card
describe('Engine status card (sidebar)', () => {
  const card = (engine: Engine) => {
    render(<Sidebar health={fx.health} healthError={false} engine={engine} />)
    return screen.getByRole('region', { name: 'Engine status' })
  }

  it('device mode: "On device" and no remote-server notice', () => {
    const c = card(fx.engine)
    expect(within(c).getByText('Processing')).toBeInTheDocument()
    expect(within(c).getByText('On device')).toBeInTheDocument()
    expect(within(c).queryByTestId('cloud-notice')).toBeNull()
  })

  it('cloud mode: "Cloud (hostname)" and the neutral notice', () => {
    const c = card(onCloud())
    expect(within(c).getByText(`Cloud (${HOST})`)).toBeInTheDocument()
    expect(within(c).getByTestId('cloud-notice')).toHaveTextContent('Requirement text is sent to a remote server.')
  })

  it('falls back to the target in /api/health while the engine call is still loading', () => {
    render(<Sidebar health={{ ...fx.health, generation_target: 'cloud' }} healthError={false} />)
    expect(screen.getByText('Cloud')).toBeInTheDocument()
    expect(screen.getByTestId('cloud-notice')).toBeInTheDocument()
  })

  it('targetLabel', () => {
    expect(targetLabel('device', null)).toBe('On device')
    expect(targetLabel('cloud', HOST)).toBe(`Cloud (${HOST})`)
    expect(targetLabel('cloud', null)).toBe('Cloud')
  })
})

// ---------------------------------------------------------------------------------------------------------------- failure banner
const pausedSummary = () => ({
  ...fx.summary,
  task_drafts: { ...fx.summary.task_drafts, total: 42, generated: 29, failed: 3, not_generated: 10, in_progress: 3, queued: 3, paused: true, paused_reason: 'cloud_unreachable' },
})

describe('Cloud unreachable banner', () => {
  it('shows the message and both explicit buttons; nothing is switched by itself', async () => {
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/engine' && c.method === 'GET') return json(onCloud())
      if (c.url.pathname === '/api/projects/1/summary') return json(pausedSummary())
      return undefined
    })
    renderApp()
    const banner = await screen.findByTestId('cloud-banner')
    expect(banner).toHaveTextContent('Cloud unreachable')
    expect(banner).toHaveTextContent(HOST)
    expect(within(banner).getByRole('button', { name: /retry/i })).toBeEnabled()
    expect(within(banner).getByRole('button', { name: /switch to device/i })).toBeEnabled()
    await screen.findByTestId('draft-progress')
    expect(calls.filter((c) => c.method !== 'GET')).toHaveLength(0)
  })

  it('Retry resumes the queue (and does not change the target)', async () => {
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/engine' && c.method === 'GET') return json(onCloud())
      if (c.url.pathname === '/api/projects/1/summary') return json(pausedSummary())
      if (c.url.pathname === '/api/projects/1/generation/resume') return json({ paused: false })
      return undefined
    })
    renderApp()
    await userEvent.click(within(await screen.findByTestId('cloud-banner')).getByRole('button', { name: /retry/i }))
    await waitFor(() => expect(calls.some((c) => c.url.pathname === '/api/projects/1/generation/resume' && c.method === 'POST')).toBe(true))
    expect(putCalls(calls)).toHaveLength(0)
  })

  it('Switch to device sends only the target change', async () => {
    const { calls } = mockApi((c) => {
      if (c.url.pathname === '/api/engine' && c.method === 'GET') return json(onCloud())
      if (c.url.pathname === '/api/engine' && c.method === 'PUT') return json({ ...onCloud(), target: 'device' })
      if (c.url.pathname === '/api/projects/1/summary') return json(pausedSummary())
      return undefined
    })
    renderApp()
    await userEvent.click(within(await screen.findByTestId('cloud-banner')).getByRole('button', { name: /switch to device/i }))
    await waitFor(() => expect(putCalls(calls)).toHaveLength(1))
    expect(bodyOf(putCalls(calls)[0]!)).toEqual({ target: 'device' })
    expect(calls.some((c) => c.url.pathname.endsWith('/generation/resume'))).toBe(false)
  })

  it('is not shown when the queue is not paused, or paused by the user', async () => {
    mockApi((c) => {
      if (c.url.pathname === '/api/projects/1/summary') return json({ ...fx.summary, task_drafts: { ...fx.summary.task_drafts, not_generated: 5, in_progress: 2, paused: true, paused_reason: null } })
      return undefined
    })
    renderApp()
    await screen.findByTestId('draft-progress')
    expect(screen.queryByTestId('cloud-banner')).toBeNull()
  })

  it('the banner works on its own with a missing host name', async () => {
    const onRetry = vi.fn()
    const onSwitch = vi.fn()
    render(<CloudUnreachableBanner host={null} busy={false} onRetry={onRetry} onSwitch={onSwitch} />)
    expect(screen.getByRole('alert')).toHaveTextContent('the cloud server')
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    await userEvent.click(screen.getByRole('button', { name: /switch to device/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
    expect(onSwitch).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------------------------------------------- progress panel and provenance
describe('Progress panel', () => {
  const noop = () => undefined
  const drafts = (over: Partial<TaskDrafts> = {}): TaskDrafts => ({ ...fx.summary.task_drafts, total: 20, generated: 8, not_generated: 12, in_progress: 12, queued: 12, ...over })
  const panel = (d: TaskDrafts, target?: string) => render(<DraftProgress drafts={d} onPause={noop} onResume={noop} onGenerateAll={noop} busy={false} analysing={false} target={target} />)

  it('says "paused: cloud unreachable" and names the target', () => {
    panel(drafts({ paused: true, paused_reason: 'cloud_unreachable' }), `Cloud (${HOST})`)
    expect(screen.getByTestId('draft-eta')).toHaveTextContent('Paused: cloud unreachable')
    expect(screen.getByTestId('draft-target')).toHaveTextContent(`Processing: Cloud (${HOST})`)
  })

  it('a pause by the user keeps its own wording', () => {
    panel(drafts({ paused: true, paused_reason: null }), 'On device')
    expect(screen.getByTestId('draft-eta')).toHaveTextContent('Paused: 12 waiting.')
    expect(screen.getByTestId('draft-eta')).not.toHaveTextContent('cloud unreachable')
  })

  it('shows the backend ETA unchanged, with the target', () => {
    panel(drafts({ eta_seconds: 125, latency_samples: 10 }), `Cloud (${HOST})`)
    expect(screen.getByTestId('draft-eta')).toHaveTextContent('about 3 min left (from the last 10 real replies)')
    expect(screen.getByTestId('draft-target')).toHaveTextContent(`Cloud (${HOST})`)
  })

  it('hides the ETA until the backend has 3 samples (the page invents nothing)', () => {
    panel(drafts({ eta_seconds: null, latency_samples: 1 }), 'On device')
    expect(screen.getByTestId('draft-eta')).toHaveTextContent('Estimating time left: needs 3 finished drafts (1 so far)')
  })

  it('shows no target line when the target is not known yet', () => {
    panel(drafts())
    expect(screen.queryByTestId('draft-target')).toBeNull()
  })
})

describe('Draft provenance', () => {
  const card = (g: Partial<Generation>) => {
    render(<DraftCard generation={{ ...fx.generationDone, ...g }} onGenerate={() => undefined} busy={false} />)
    return screen.getByTestId('provenance')
  }

  it('cloud: "Written by c1-req on cloud (host)"', () => {
    expect(card({ backend: 'ollama', model: 'c1-req', generated_on: 'cloud', endpoint_host: HOST })).toHaveTextContent(`Written by c1-req on cloud (${HOST})`)
  })

  it('device: "Written by c1-req on device"', () => {
    expect(card({ backend: 'ollama', model: 'c1-req', generated_on: 'device', endpoint_host: null })).toHaveTextContent('Written by c1-req on device')
  })

  it('cloud without a host name still says cloud', () => {
    expect(card({ backend: 'ollama', model: 'c1-req', generated_on: 'cloud', endpoint_host: null })).toHaveTextContent(/Written by c1-req on cloud(?! \()/)
  })

  it('a replay or mock draft keeps its own wording', () => {
    expect(card({ backend: 'replay', model: 'replay' })).toHaveTextContent('Stored output of an earlier model run (replay)')
  })
})
