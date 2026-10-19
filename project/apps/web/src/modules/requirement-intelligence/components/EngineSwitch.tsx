import { CheckCircle2, Cloud, Cpu, Laptop, RefreshCw, Settings, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTestEngine, useUpdateEngine } from '../api/hooks'
import type { Engine, EngineTarget, EngineTestResult, EngineUpdate } from '../api/types'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { cloudReady, engineErrorMessage } from '../lib/engine'
import { Spinner } from './ui'

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
    if (!url && !e.cloud.configured) err.url = copy.engine.urlRequired
    else if (url && !/^https:\/\/[^\s/?#@]+(\/[^\s?#]*)?$/i.test(url)) err.url = copy.engine.urlInvalid
    if (!f.model.trim()) err.model = copy.engine.modelRequired
  }
  const n = Number(f.concurrency)
  if (f.concurrency.trim() === '' || !Number.isInteger(n) || n < 1 || n > 8) err.concurrency = copy.engine.concurrencyInvalid
  if (!f.consent && !e.cloud.consent) err.consent = copy.engine.consentRequired
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
}

/** "Process: On device | Cloud (gear)" with the cloud settings popover. Shown inside Processing details. */
export function EngineSwitch({ engine }: Props) {
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
  const busy = update.isPending || test.isPending
  const locked = target === 'cloud'

  const choose = (t: EngineTarget) => {
    if (!engine || t === engine.target || busy) return
    setSwitchMessage(null)
    update.mutate(
      { target: t },
      {
        onSuccess: () => toasts.push(copy.engine.switchedNotice, 'success'),
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
      if (dirty) toasts.push(copy.engine.saved, 'success')
      else setFormMessage(copy.engine.nothingChanged)
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

  const cloudName = !cloudAvailable ? copy.engine.cloudUnavailable : ready || target === 'cloud' ? copy.engine.cloud : copy.engine.cloudSetUp
  const segment = (active: boolean) =>
    `inline-flex items-center gap-1.5 px-3 py-1.5 text-[12.5px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${active ? 'bg-primary text-white' : 'bg-white text-heading hover:bg-primary-light'}`

  return (
    <div className="flex flex-col items-end gap-1" data-testid="engine-switch">
      <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1.5">
        <span id="engine-process-label" className="text-[12px] font-medium text-secondary-text">
          {copy.engine.process}
        </span>
        <div className="relative flex items-center gap-1.5" ref={wrap}>
          <div role="radiogroup" aria-labelledby="engine-process-label" className="inline-flex overflow-hidden rounded-lg border border-border">
            <button
              type="button"
              role="radio"
              aria-checked={target === 'device'}
              className={segment(target === 'device')}
              disabled={!engine || busy}
              onClick={() => choose('device')}
            >
              <Laptop size={14} aria-hidden="true" /> {copy.engine.device}
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={target === 'cloud'}
              className={`${segment(target === 'cloud')} border-l border-border`}
              disabled={!engine || busy || !cloudAvailable || (!ready && target !== 'cloud')}
              title={!cloudAvailable ? (engine?.cloud_disabled_reason ?? copy.engine.cloudNotAllowed) : !ready && target !== 'cloud' ? copy.engine.cloudHint : undefined}
              onClick={() => choose('cloud')}
            >
              <Cloud size={14} aria-hidden="true" /> {cloudName}
            </button>
          </div>
          {cloudAvailable && (
            <button
              ref={gear}
              type="button"
              aria-label={copy.engine.settings}
              aria-haspopup="dialog"
              aria-expanded={open}
              disabled={!engine}
              className="rounded-lg border border-border bg-white p-2 text-body hover:bg-primary-light disabled:cursor-not-allowed disabled:opacity-50"
              onClick={openPopover}
            >
              <Settings size={15} aria-hidden="true" />
            </button>
          )}

          {open && form && engine && (
            <div role="dialog" aria-label={copy.engine.settings} data-testid="cloud-popover" className="absolute right-0 top-full z-30 mt-2 w-[380px] max-w-[92vw] rounded-xl border border-border bg-white p-4 text-left shadow-sm">
              <div className="flex items-center justify-between">
                <div className="c1-label">{copy.engine.server}</div>
                <span className="text-[11.5px] text-secondary-text" data-testid="cloud-state">
                  {!engine.cloud.configured ? copy.engine.notSetUp : engine.cloud.reachable === true ? copy.engine.testedOk(engine.cloud.host) : engine.cloud.reachable === false ? copy.engine.testFailed(engine.cloud.host) : copy.engine.notTested(engine.cloud.host)}
                </span>
              </div>
              {locked && (
                <div className="mt-2 rounded-lg border border-info-border bg-info-bg px-2.5 py-1.5 text-[11.5px] text-blue-800" data-testid="cloud-locked">
                  <p>{copy.engine.locked}</p>
                  <button type="button" className="c1-btn-secondary mt-1.5 !px-2.5 !py-1" disabled={busy} onClick={() => choose('device')}>
                    <Laptop size={13} aria-hidden="true" /> {copy.engine.unlock}
                  </button>
                </div>
              )}

              <label className="mt-3 block text-[12px] font-medium text-heading" htmlFor="cloud-url">
                {copy.engine.urlLabel}
              </label>
              <input
                id="cloud-url"
                ref={firstField}
                type="text"
                inputMode="url"
                autoComplete="off"
                spellCheck={false}
                placeholder={engine.cloud.configured ? copy.engine.urlSaved(engine.cloud.host) : copy.engine.urlExample}
                value={form.url}
                disabled={locked}
                aria-invalid={!!errors.url}
                aria-describedby={errors.url ? 'cloud-url-error' : undefined}
                onChange={(e) => set('url', e.target.value)}
                className="mt-1 w-full rounded-lg border border-border bg-white px-2.5 py-1.5 text-[12.5px] text-heading disabled:bg-page disabled:opacity-60"
              />
              {errors.url && (
                <p id="cloud-url-error" role="alert" className="mt-1 text-[11.5px] text-danger-text">
                  {errors.url}
                </p>
              )}

              <div className="mt-3 flex items-center justify-between">
                <label className="text-[12px] font-medium text-heading" htmlFor="cloud-key">
                  {copy.engine.keyLabel}
                </label>
                {keySaved && !form.removeKey && (
                  <span className="flex items-center gap-2 text-[11.5px] text-success-text" data-testid="key-saved">
                    <CheckCircle2 size={13} aria-hidden="true" /> {copy.engine.keySaved}
                    <button type="button" className="font-medium text-primary underline-offset-2 hover:underline disabled:opacity-50" disabled={locked} onClick={() => set('removeKey', true)}>
                      {copy.engine.keyRemove}
                    </button>
                  </span>
                )}
                {form.removeKey && <span className="text-[11.5px] text-secondary-text">{copy.engine.keyRemoved}</span>}
              </div>
              <input
                id="cloud-key"
                type="password"
                autoComplete="off"
                spellCheck={false}
                placeholder={copy.engine.keyPlaceholder}
                value={form.key}
                disabled={locked}
                onChange={(e) => setForm((f) => (f ? { ...f, key: e.target.value, removeKey: false } : f))}
                className="mt-1 w-full rounded-lg border border-border bg-white px-2.5 py-1.5 text-[12.5px] text-heading disabled:bg-page disabled:opacity-60"
              />

              <div className="mt-3 grid grid-cols-[1fr_110px] gap-3">
                <div>
                  <label className="block text-[12px] font-medium text-heading" htmlFor="cloud-model">
                    {copy.engine.modelLabel}
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
                    className="mt-1 w-full rounded-lg border border-border bg-white px-2.5 py-1.5 text-[12.5px] text-heading disabled:bg-page disabled:opacity-60"
                  />
                </div>
                <div>
                  <label className="block text-[12px] font-medium text-heading" htmlFor="cloud-concurrency">
                    {copy.engine.concurrencyLabel}
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
                    className="mt-1 w-full rounded-lg border border-border bg-white px-2.5 py-1.5 text-[12.5px] text-heading"
                  />
                </div>
              </div>
              {errors.model && (
                <p id="cloud-model-error" role="alert" className="mt-1 text-[11.5px] text-danger-text">
                  {errors.model}
                </p>
              )}
              {errors.concurrency && (
                <p id="cloud-concurrency-error" role="alert" className="mt-1 text-[11.5px] text-danger-text">
                  {errors.concurrency}
                </p>
              )}

              <label className="mt-3 flex items-start gap-2 text-[12px] text-heading">
                <input type="checkbox" checked={form.consent} onChange={(e) => set('consent', e.target.checked)} aria-describedby={errors.consent ? 'cloud-consent-error' : undefined} className="mt-0.5" />
                <span>{copy.engine.consent}</span>
              </label>
              {errors.consent && (
                <p id="cloud-consent-error" role="alert" className="mt-1 text-[11.5px] text-danger-text">
                  {errors.consent}
                </p>
              )}

              {formMessage && (
                <p role="alert" data-testid="cloud-form-message" className="mt-3 rounded-lg border border-warning-border bg-warning-bg px-2.5 py-1.5 text-[12px] text-warning-text">
                  {formMessage}
                </p>
              )}
              {result && (
                <p
                  role="status"
                  data-testid="cloud-test-result"
                  data-ok={result.ok}
                  className={`mt-3 flex items-start gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12px] ${result.ok ? 'border-success-border bg-success-bg text-success-text' : 'border-danger-border bg-danger-bg text-danger-text'}`}
                >
                  {result.ok ? <CheckCircle2 size={14} className="mt-0.5 shrink-0" aria-hidden="true" /> : <XCircle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />}
                  <span>
                    {result.detail}
                    {result.ok && result.latency_ms !== null ? ` (${result.latency_ms} ms)` : ''}
                  </span>
                </p>
              )}

              <div className="mt-4 flex items-center justify-end gap-2">
                <button type="button" className="c1-btn-secondary !px-3 !py-1.5 !text-[12.5px]" disabled={busy} onClick={() => void onTest()}>
                  {test.isPending ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw size={14} aria-hidden="true" />} {copy.engine.test}
                </button>
                <button type="button" className="c1-btn-primary !px-3 !py-1.5 !text-[12.5px]" disabled={busy} onClick={() => void onSave()}>
                  {update.isPending && !test.isPending ? <Spinner className="h-3.5 w-3.5" /> : null} {copy.common.save}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {switchMessage && (
        <p role="alert" data-testid="engine-error" className="max-w-[420px] text-right text-[11.5px] leading-snug text-danger-text">
          {switchMessage}
        </p>
      )}
    </div>
  )
}

interface BannerProps {
  busy: boolean
  onRetry: () => void
  /** Open the AI engine panel, where the engine is chosen. */
  onOpen: () => void
}

/** The queue paused itself after 3 failed cloud requests. Nothing is switched automatically: the user picks Retry or Switch to device. */
export function CloudUnreachableBanner({ busy, onRetry, onOpen }: BannerProps) {
  return (
    <div role="alert" data-testid="cloud-banner" className="mt-5 flex flex-wrap items-center gap-3 rounded-xl border border-danger-border bg-danger-bg px-5 py-3.5 text-[13px] text-danger-text ">
      <XCircle size={18} className="shrink-0" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <strong>{copy.engine.bannerTitle}</strong> {copy.engine.bannerText}
      </span>
      <button type="button" disabled={busy} className="inline-flex items-center gap-1.5 rounded-md border border-danger-border bg-white px-3 py-1.5 font-semibold hover:bg-red-50 disabled:opacity-50" onClick={onRetry}>
        <RefreshCw size={14} aria-hidden="true" /> {copy.common.retry}
      </button>
      <button type="button" disabled={busy} className="inline-flex items-center gap-1.5 rounded-md border border-danger-border bg-white px-3 py-1.5 font-semibold hover:bg-red-50 disabled:opacity-50" onClick={onOpen}>
        <Cpu size={14} aria-hidden="true" /> {copy.engine.openEngine}
      </button>
    </div>
  )
}
