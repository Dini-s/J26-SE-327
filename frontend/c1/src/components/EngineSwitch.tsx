import { CheckCircle2, Cloud, Laptop, RefreshCw, Settings, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTestEngine, useUpdateEngine } from '../api/hooks'
import type { Engine, EngineTarget, EngineTestResult, EngineUpdate } from '../api/types'
import { useToasts } from '../context/Toasts'
import { ENGINE_STATUS_TEXT, cloudReady, engineErrorMessage, engineStatus, targetLabel, type EngineStatusState } from '../lib/engine'
import { Spinner } from './ui'

const DOT: Record<EngineStatusState, string> = { ready: 'bg-emerald-500', not_set_up: 'bg-slate-400', unreachable: 'bg-red-500', checking: 'bg-slate-400' }

interface Form {
  url: string
  key: string
  removeKey: boolean
  model: string
  concurrency: string
  consent: boolean
}
type Errors = Partial<Record<'url' | 'model' | 'concurrency' | 'consent', string>>

const initialForm = (e: Engine): Form => ({ url: '', key: '', removeKey: false, model: e.cloud.model, concurrency: String(e.cloud.concurrency), consent: e.cloud.consent })

/** Checks that need no server: the API repeats them and has the last word. */
function validate(f: Form, e: Engine, locked: boolean): Errors {
  const err: Errors = {}
  if (!locked) {
    const url = f.url.trim()
    if (!url && !e.cloud.configured) err.url = 'Enter the cloud URL, for example https://my-server.example.com.'
    else if (url && !/^https:\/\/[^\s/?#@]+(\/[^\s?#]*)?$/i.test(url)) err.url = 'Enter an address that starts with https:// and has no user name, password or query.'
    if (!f.model.trim()) err.model = 'Enter the model name (default c1-req).'
  }
  const n = Number(f.concurrency)
  if (f.concurrency.trim() === '' || !Number.isInteger(n) || n < 1 || n > 8) err.concurrency = 'Parallel requests must be a whole number from 1 to 8.'
  if (!f.consent && !e.cloud.consent) err.consent = 'Tick this box to allow requirement text to be sent to this server.'
  return err
}

/** Only what changed. The address, key and model are locked while Cloud is the active target. */
function buildUpdate(f: Form, e: Engine, locked: boolean): EngineUpdate {
  const u: EngineUpdate = {}
  if (!locked) {
    if (f.url.trim()) u.cloud_url = f.url.trim()
    if (f.removeKey) u.cloud_api_key = ''
    else if (f.key) u.cloud_api_key = f.key
    if (f.model.trim() !== e.cloud.model) u.cloud_model = f.model.trim()
  }
  if (Number(f.concurrency) !== e.cloud.concurrency) u.cloud_concurrency = Number(f.concurrency)
  if (f.consent !== e.cloud.consent) u.cloud_consent = f.consent
  return u
}

interface Props {
  engine?: Engine
  /** The queue paused itself after repeated cloud failures. */
  cloudPaused: boolean
}

/** "Process: On device | Cloud (gear)" with a status dot, the active model and the cloud settings popover. */
export function EngineSwitch({ engine, cloudPaused }: Props) {
  const toasts = useToasts()
  const update = useUpdateEngine()
  const test = useTestEngine()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<Form | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  const [formMessage, setFormMessage] = useState<string | null>(null)
  const [result, setResult] = useState<EngineTestResult | null>(null)
  const [keySaved, setKeySaved] = useState(false)
  const [switchMessage, setSwitchMessage] = useState<string | null>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const gear = useRef<HTMLButtonElement>(null)
  const firstField = useRef<HTMLInputElement>(null)

  const close = () => {
    setOpen(false)
    gear.current?.focus()
  }

  useEffect(() => {
    if (!open) return
    const outside = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        gear.current?.focus()
      }
    }
    document.addEventListener('mousedown', outside)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', outside)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  useEffect(() => {
    if (open) firstField.current?.focus()
  }, [open])

  const openPopover = () => {
    if (open) return close()
    if (!engine) return
    setForm(initialForm(engine))
    setErrors({})
    setFormMessage(null)
    setResult(null)
    setOpen(true)
  }

  const target: EngineTarget | null = engine?.target ?? null
  const ready = cloudReady(engine)
  const cloudAvailable = engine?.cloud_available ?? true
  const status = engineStatus(engine, cloudPaused)
  const model = engine ? (engine.target === 'cloud' ? engine.cloud.model : engine.device.model) : ''
  const busy = update.isPending || test.isPending
  const locked = target === 'cloud'

  const choose = (t: EngineTarget) => {
    if (!engine || t === engine.target || busy) return
    setSwitchMessage(null)
    update.mutate(
      { target: t },
      {
        onSuccess: (e) => toasts.push(t === 'cloud' ? `Drafts are now written in the cloud (${e.cloud.host ?? 'remote server'}).` : 'Drafts are now written on this device.', 'success'),
        onError: (e) => setSwitchMessage(engineErrorMessage(e)),
      },
    )
  }

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => (f ? { ...f, [k]: v } : f))

  /** Saves what changed. Resolves true when the API accepted it (or nothing changed). */
  const save = async (): Promise<boolean> => {
    if (!engine || !form) return false
    const problems = validate(form, engine, locked)
    setErrors(problems)
    setFormMessage(null)
    if (Object.keys(problems).length) return false
    const body = buildUpdate(form, engine, locked)
    if (Object.keys(body).length === 0) return true
    try {
      const saved = await update.mutateAsync(body)
      if (body.cloud_url || body.cloud_api_key !== undefined || body.cloud_model !== undefined) setResult(null) // the saved test no longer applies
      if (body.cloud_api_key) setKeySaved(true)
      if (body.cloud_api_key === '') setKeySaved(false)
      setForm({ ...initialForm(saved), concurrency: form.concurrency })
      return true
    } catch (e) {
      setFormMessage(engineErrorMessage(e))
      return false
    }
  }

  const onSave = async () => {
    if (!engine || !form) return
    const dirty = Object.keys(buildUpdate(form, engine, locked)).length > 0
    if (await save()) {
      setFormMessage(null)
      if (dirty) toasts.push('Cloud settings saved.', 'success')
      else setFormMessage('Nothing changed.')
    }
  }

  const onTest = async () => {
    if (!form || !engine) return
    if (!(await save())) return
    setResult(null)
    try {
      setResult(await test.mutateAsync('cloud'))
    } catch (e) {
      setFormMessage(engineErrorMessage(e))
    }
  }

  const cloudName = !cloudAvailable ? 'Cloud unavailable' : ready || target === 'cloud' ? 'Cloud' : 'Set up cloud…'
  const segment = (active: boolean) =>
    `inline-flex items-center gap-1.5 px-3 py-1.5 text-[12.5px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${active ? 'bg-brand-600 text-white' : 'bg-white text-ink hover:bg-brand-50'}`

  return (
    <div className="flex flex-col items-end gap-1" data-testid="engine-switch">
      <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1.5">
        <span id="engine-process-label" className="text-[12px] font-medium text-ink-muted">
          Process:
        </span>
        <div className="relative flex items-center gap-1.5" ref={wrap}>
          <div role="radiogroup" aria-labelledby="engine-process-label" className="inline-flex overflow-hidden rounded-ctl border border-line">
            <button
              type="button"
              role="radio"
              aria-checked={target === 'device'}
              className={segment(target === 'device')}
              disabled={!engine || busy}
              onClick={() => choose('device')}
            >
              <Laptop size={14} aria-hidden="true" /> On device
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={target === 'cloud'}
              className={`${segment(target === 'cloud')} border-l border-line`}
              disabled={!engine || busy || !cloudAvailable || (!ready && target !== 'cloud')}
              title={!cloudAvailable ? (engine?.cloud_disabled_reason ?? 'Cloud is not allowed in this server mode') : !ready && target !== 'cloud' ? 'Open the gear to set up, consent to and test a cloud server' : undefined}
              onClick={() => choose('cloud')}
            >
              <Cloud size={14} aria-hidden="true" /> {cloudName}
            </button>
          </div>
          {cloudAvailable && (
            <button
              ref={gear}
              type="button"
              aria-label="Cloud settings"
              aria-haspopup="dialog"
              aria-expanded={open}
              disabled={!engine}
              className="rounded-ctl border border-line bg-white p-2 text-ink-body hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={openPopover}
            >
              <Settings size={15} aria-hidden="true" />
            </button>
          )}

          {open && form && engine && (
            <div role="dialog" aria-label="Cloud settings" data-testid="cloud-popover" className="absolute right-0 top-full z-30 mt-2 w-[380px] max-w-[92vw] rounded-card border border-line bg-white p-4 text-left shadow-card">
              <div className="flex items-center justify-between">
                <div className="label-caps">Cloud server</div>
                <span className="text-[11.5px] text-ink-muted" data-testid="cloud-state">
                  {!engine.cloud.configured ? 'Not set up' : engine.cloud.reachable === true ? `Tested OK · ${engine.cloud.host ?? ''}` : engine.cloud.reachable === false ? `Test failed · ${engine.cloud.host ?? ''}` : `Not tested · ${engine.cloud.host ?? ''}`}
                </span>
              </div>
              {locked && (
                <p className="mt-2 rounded-ctl border border-info-line bg-info-bg px-2.5 py-1.5 text-[11.5px] text-info-text" data-testid="cloud-locked">
                  Cloud is active, so the address, key and model are locked. Switch to On device to change them.
                </p>
              )}

              <label className="mt-3 block text-[12px] font-medium text-ink" htmlFor="cloud-url">
                Cloud URL (https)
              </label>
              <input
                id="cloud-url"
                ref={firstField}
                type="text"
                inputMode="url"
                autoComplete="off"
                spellCheck={false}
                placeholder={engine.cloud.configured ? `Saved: ${engine.cloud.host ?? 'server'}. Leave empty to keep it.` : 'https://my-server.example.com'}
                value={form.url}
                disabled={locked}
                aria-invalid={!!errors.url}
                aria-describedby={errors.url ? 'cloud-url-error' : undefined}
                onChange={(e) => set('url', e.target.value)}
                className="mt-1 w-full rounded-ctl border border-line bg-white px-2.5 py-1.5 text-[12.5px] text-ink disabled:bg-page disabled:opacity-60"
              />
              {errors.url && (
                <p id="cloud-url-error" role="alert" className="mt-1 text-[11.5px] text-risk-highText">
                  {errors.url}
                </p>
              )}

              <div className="mt-3 flex items-center justify-between">
                <label className="text-[12px] font-medium text-ink" htmlFor="cloud-key">
                  API key (optional)
                </label>
                {keySaved && !form.removeKey && (
                  <span className="flex items-center gap-2 text-[11.5px] text-ok-text" data-testid="key-saved">
                    <CheckCircle2 size={13} aria-hidden="true" /> saved
                    <button type="button" className="font-medium text-brand-600 underline-offset-2 hover:underline disabled:opacity-50" disabled={locked} onClick={() => set('removeKey', true)}>
                      Remove key
                    </button>
                  </span>
                )}
                {form.removeKey && <span className="text-[11.5px] text-ink-muted">will be removed on Save</span>}
              </div>
              <input
                id="cloud-key"
                type="password"
                autoComplete="off"
                spellCheck={false}
                placeholder="Write-only: leave empty to keep the saved key"
                value={form.key}
                disabled={locked}
                onChange={(e) => setForm((f) => (f ? { ...f, key: e.target.value, removeKey: false } : f))}
                className="mt-1 w-full rounded-ctl border border-line bg-white px-2.5 py-1.5 text-[12.5px] text-ink disabled:bg-page disabled:opacity-60"
              />

              <div className="mt-3 grid grid-cols-[1fr_110px] gap-3">
                <div>
                  <label className="block text-[12px] font-medium text-ink" htmlFor="cloud-model">
                    Model name
                  </label>
                  <input
                    id="cloud-model"
                    type="text"
                    autoComplete="off"
                    spellCheck={false}
                    value={form.model}
                    disabled={locked}
                    aria-invalid={!!errors.model}
                    aria-describedby={errors.model ? 'cloud-model-error' : undefined}
                    onChange={(e) => set('model', e.target.value)}
                    className="mt-1 w-full rounded-ctl border border-line bg-white px-2.5 py-1.5 text-[12.5px] text-ink disabled:bg-page disabled:opacity-60"
                  />
                </div>
                <div>
                  <label className="block text-[12px] font-medium text-ink" htmlFor="cloud-concurrency">
                    Parallel requests
                  </label>
                  <input
                    id="cloud-concurrency"
                    type="number"
                    min={1}
                    max={8}
                    step={1}
                    value={form.concurrency}
                    aria-invalid={!!errors.concurrency}
                    aria-describedby={errors.concurrency ? 'cloud-concurrency-error' : undefined}
                    onChange={(e) => set('concurrency', e.target.value)}
                    className="mt-1 w-full rounded-ctl border border-line bg-white px-2.5 py-1.5 text-[12.5px] text-ink"
                  />
                </div>
              </div>
              {errors.model && (
                <p id="cloud-model-error" role="alert" className="mt-1 text-[11.5px] text-risk-highText">
                  {errors.model}
                </p>
              )}
              {errors.concurrency && (
                <p id="cloud-concurrency-error" role="alert" className="mt-1 text-[11.5px] text-risk-highText">
                  {errors.concurrency}
                </p>
              )}

              <label className="mt-3 flex items-start gap-2 text-[12px] text-ink">
                <input type="checkbox" checked={form.consent} onChange={(e) => set('consent', e.target.checked)} aria-describedby={errors.consent ? 'cloud-consent-error' : undefined} className="mt-0.5" />
                <span>Requirement text will be sent to this server</span>
              </label>
              {errors.consent && (
                <p id="cloud-consent-error" role="alert" className="mt-1 text-[11.5px] text-risk-highText">
                  {errors.consent}
                </p>
              )}

              {formMessage && (
                <p role="alert" data-testid="cloud-form-message" className="mt-3 rounded-ctl border border-risk-medLine bg-risk-medBg px-2.5 py-1.5 text-[12px] text-risk-medText">
                  {formMessage}
                </p>
              )}
              {result && (
                <p
                  role="status"
                  data-testid="cloud-test-result"
                  data-ok={result.ok}
                  className={`mt-3 flex items-start gap-1.5 rounded-ctl border px-2.5 py-1.5 text-[12px] ${result.ok ? 'border-ok-line bg-ok-bg text-ok-text' : 'border-risk-highLine bg-risk-highBg text-risk-highText'}`}
                >
                  {result.ok ? <CheckCircle2 size={14} className="mt-0.5 shrink-0" aria-hidden="true" /> : <XCircle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />}
                  <span>
                    {result.detail}
                    {result.ok && result.latency_ms !== null ? ` (${result.latency_ms} ms)` : ''}
                  </span>
                </p>
              )}

              <div className="mt-4 flex items-center justify-end gap-2">
                <button type="button" className="btn-secondary !px-3 !py-1.5 !text-[12.5px]" disabled={busy} onClick={() => void onTest()}>
                  {test.isPending ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw size={14} aria-hidden="true" />} Test connection
                </button>
                <button type="button" className="btn-primary !px-3 !py-1.5 !text-[12.5px]" disabled={busy} onClick={() => void onSave()}>
                  {update.isPending && !test.isPending ? <Spinner className="h-3.5 w-3.5" /> : null} Save
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 text-[12px] text-ink-body" role="status" data-testid="engine-status" data-state={status}>
        <span className={`h-2 w-2 rounded-full ${DOT[status]}`} aria-hidden="true" />
        <span className="font-medium text-ink">{ENGINE_STATUS_TEXT[status]}</span>
        {engine && model && <span className="text-ink-muted">· {model}</span>}
        {engine && <span className="text-ink-muted">· {targetLabel(engine.target, engine.cloud.host)}</span>}
      </div>
      {switchMessage && (
        <p role="alert" data-testid="engine-error" className="max-w-[420px] text-right text-[11.5px] leading-snug text-risk-highText">
          {switchMessage}
        </p>
      )}
    </div>
  )
}

interface BannerProps {
  host: string | null
  busy: boolean
  onRetry: () => void
  onSwitch: () => void
}

/** The queue paused itself after 3 failed cloud requests. Nothing is switched automatically: the user picks Retry or Switch to device. */
export function CloudUnreachableBanner({ host, busy, onRetry, onSwitch }: BannerProps) {
  return (
    <div role="alert" data-testid="cloud-banner" className="mx-6 mt-5 flex flex-wrap items-center gap-3 rounded-card border border-risk-highLine bg-risk-highBg px-5 py-3.5 text-[13px] text-risk-highText xl:mx-9">
      <XCircle size={18} className="shrink-0" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <strong>Cloud unreachable.</strong> The drafts paused after 3 failed requests to {host ? <strong>{host}</strong> : 'the cloud server'}. Nothing was switched automatically. Retry tries the cloud again; Switch to device writes the remaining drafts on this computer.
      </span>
      <button type="button" disabled={busy} className="inline-flex items-center gap-1.5 rounded-md border border-risk-highLine bg-white px-3 py-1.5 font-semibold hover:bg-red-50 disabled:opacity-50" onClick={onRetry}>
        <RefreshCw size={14} aria-hidden="true" /> Retry
      </button>
      <button type="button" disabled={busy} className="inline-flex items-center gap-1.5 rounded-md border border-risk-highLine bg-white px-3 py-1.5 font-semibold hover:bg-red-50 disabled:opacity-50" onClick={onSwitch}>
        <Laptop size={14} aria-hidden="true" /> Switch to device
      </button>
    </div>
  )
}
