import { AlertTriangle, ArrowRight, Check, CheckCircle2, CloudUpload, Code2, FileSearch, FileText, Network, RefreshCw, Sparkles, X, XCircle } from 'lucide-react'
import { useEffect, useRef, useState, type DragEvent, type ReactNode } from 'react'
import type { Job, Policy, Source, Stage } from '../api/types'
import { ALLOWED_EXTENSIONS } from '../config'
import { Spinner } from './ui'

const BUSY_HINT = 'Wait for the running analysis to finish.'

export const POLICY_LABEL: Record<Policy, string> = {
  smart: 'Smart: important requirements first',
  all: 'All requirements (slow)',
  manual: 'None: I will choose',
}
export const POLICY_HELP: Record<Policy, string> = {
  smart: 'Writes drafts for ambiguous, security, vague and non-functional requirements first. The rest wait until you click Generate draft.',
  all: 'Writes a draft for every requirement, most important first. This can take a long time on a laptop GPU.',
  manual: 'Runs the analysis only. Click Generate draft on a requirement, or Generate all remaining.',
}

interface TitleProps {
  onFiles: (files: File[]) => void
  onRun: () => void
  canRun: boolean
  running: boolean
  policy: Policy
  onPolicy: (p: Policy) => void
  /** The processing-target switch, shown next to Run analysis. */
  engine?: ReactNode
}

/** Title, description and the actions (upload, draft policy, run). */
export function TitleBlock({ onFiles, onRun, canRun, running, policy, onPolicy, engine }: TitleProps) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <section id="top" className="px-6 pt-8 xl:px-9">
      <div className="label-caps flex items-center gap-2 !text-brand-600">
        <FileSearch size={15} aria-hidden="true" />
        Component 1
      </div>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div className="min-w-0 max-w-[760px]">
          <h1 className="text-[34px] font-medium leading-tight tracking-tight text-ink xl:text-[40px]">Requirement Intelligence</h1>
          <p className="mt-3 text-[14.5px] leading-relaxed text-ink-body">
            Turn raw requirement sources into clearer, risk-aware and stakeholder-ready requirement knowledge—without creating RVUs or test artifacts.
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
        <div className="flex flex-wrap items-center justify-end gap-3">
          <input
            ref={input}
            type="file"
            multiple
            hidden
            accept={ALLOWED_EXTENSIONS.join(',')}
            aria-label="Choose source files"
            data-testid="file-input"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? [])
              e.target.value = ''
              if (files.length) onFiles(files)
            }}
          />
          <button type="button" className="btn-secondary" onClick={() => input.current?.click()}>
            <CloudUpload size={18} />
            Upload source files
          </button>
          <button type="button" className="btn-primary" disabled={!canRun || running} aria-busy={running} title={running ? 'Analysis in progress' : canRun ? undefined : 'Upload a source file first'} onClick={onRun}>
            {running ? <Spinner className="h-[18px] w-[18px]" /> : <Sparkles size={18} />}
            {running ? 'Analysing…' : 'Run analysis'}
          </button>
        </div>
        {engine}
        <label className="flex items-center gap-2 text-[12px] text-ink-muted">
          Task drafts
          <select
            value={policy}
            onChange={(e) => onPolicy(e.target.value as Policy)}
            disabled={running}
            aria-label="Task drafts to write automatically"
            data-testid="policy-select"
            className="rounded-ctl border border-line bg-white px-2 py-1.5 text-[12.5px] text-ink"
          >
            {(Object.keys(POLICY_LABEL) as Policy[]).map((p) => (
              <option key={p} value={p}>
                {POLICY_LABEL[p]}
              </option>
            ))}
          </select>
        </label>
        <p className="max-w-[420px] text-right text-[11.5px] leading-snug text-ink-muted" data-testid="policy-help">
          {POLICY_HELP[policy]}
        </p>
        </div>
      </div>
    </section>
  )
}

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

/** Shown while the analysis request is open. Mount it only while that is true: the timer starts at mount. */
export function AnalyzingNotice() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const start = Date.now()
    const id = window.setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => window.clearInterval(id)
  }, [])
  return (
    <div role="status" data-testid="analyzing-notice" className="mx-6 mt-5 flex items-start gap-3 rounded-card border border-info-line bg-info-bg px-5 py-3.5 text-[13px] text-info-text xl:mx-9">
      <Spinner className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <strong>Analysing… {mmss(seconds)} elapsed.</strong> The first run is slower because the models have to load; it can take 1 to 2 minutes. Keep this page open.
      </div>
    </div>
  )
}

/** Inline (not only a toast) error for a failed or timed-out analysis request. */
export function AnalyzeError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" data-testid="analyze-error" className="mx-6 mt-5 flex flex-wrap items-center gap-3 rounded-card border border-risk-highLine bg-risk-highBg px-5 py-3.5 text-[13px] text-risk-highText xl:mx-9">
      <XCircle size={18} className="shrink-0" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <strong>The analysis did not finish.</strong> {message}
      </span>
      <button type="button" className="inline-flex items-center gap-1.5 rounded-md border border-risk-highLine bg-white px-3 py-1.5 font-semibold hover:bg-red-50" onClick={onRetry}>
        <RefreshCw size={14} aria-hidden="true" /> Try again
      </button>
    </div>
  )
}

export type AnalysisBadgeState = 'none' | 'running' | 'complete' | 'failed' | 'stale'

function AnalysisBadge({ state }: { state: AnalysisBadgeState }) {
  if (state === 'running')
    return (
      <span role="status" data-testid="analysis-badge" className="flex items-center gap-1.5 rounded-full border border-info-line bg-info-bg px-3 py-1 text-[11.5px] font-semibold text-info-text">
        <Spinner className="h-3.5 w-3.5" /> Analysing
      </span>
    )
  if (state === 'failed')
    return (
      <span role="status" data-testid="analysis-badge" className="flex items-center gap-1.5 rounded-full border border-risk-highLine bg-risk-highBg px-3 py-1 text-[11.5px] font-semibold text-risk-highText">
        <XCircle size={14} /> Failed
      </span>
    )
  if (state === 'stale')
    return (
      <span role="status" data-testid="analysis-badge" className="flex items-center gap-1.5 rounded-full border border-risk-medLine bg-risk-medBg px-3 py-1 text-[11.5px] font-semibold text-risk-medText">
        <AlertTriangle size={14} /> Sources changed, run analysis again
      </span>
    )
  if (state === 'complete')
    return (
      <span role="status" data-testid="analysis-badge" className="flex items-center gap-1.5 rounded-full border border-ok-line bg-ok-bg px-3 py-1 text-[11.5px] font-semibold text-ok-text">
        Analysis complete <CheckCircle2 size={14} />
      </span>
    )
  return (
    <span role="status" data-testid="analysis-badge" className="rounded-full border border-line bg-white px-3 py-1 text-[11.5px] font-semibold text-ink-muted">
      Not analysed yet
    </span>
  )
}

interface SourcesProps {
  sources: Source[]
  loading: boolean
  badge: AnalysisBadgeState
  onFiles: (files: File[]) => void
  busy: boolean
  onRemove: (sourceId: number) => void
  onClear: () => void
}

/** Selected sources with remove buttons (inline confirm), "Clear all" and the analysis badge; also a drop zone for files. */
export function SourcesCard({ sources, loading, badge, onFiles, busy, onRemove, onClear }: SourcesProps) {
  const [over, setOver] = useState(false)
  const [confirm, setConfirm] = useState<number | 'all' | null>(null)
  const drop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length) onFiles(files)
  }
  const confirming = busy ? null : confirm // a running job cancels any open confirmation
  return (
    <section
      className={`card mx-6 mt-6 flex flex-wrap items-center justify-between gap-4 px-5 py-4 xl:mx-9 ${over ? 'border-dashed !border-brand-600 bg-brand-50' : ''}`}
      aria-label="Selected requirement sources"
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
      data-testid="sources-card"
    >
      <div className="flex min-w-0 items-center gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
          <FileText size={21} aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <div className="label-caps">
              Selected requirement sources · {sources.length} {sources.length === 1 ? 'file' : 'files'}
            </div>
            {sources.length > 0 &&
              (confirming === 'all' ? (
                <span role="group" aria-label="Confirm clearing all sources" className="flex items-center gap-2 text-[11.5px] text-risk-highText">
                  Clear all sources and their results?
                  <button type="button" className="rounded border border-risk-highLine bg-risk-highBg px-2 py-0.5 font-semibold" onClick={() => { setConfirm(null); onClear() }}>
                    Clear all
                  </button>
                  <button type="button" className="rounded border border-line bg-white px-2 py-0.5 font-medium text-ink-body" onClick={() => setConfirm(null)}>
                    Cancel
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  className="text-[11.5px] font-medium text-brand-600 underline-offset-2 hover:underline disabled:cursor-not-allowed disabled:text-ink-faint disabled:no-underline"
                  disabled={busy}
                  title={busy ? BUSY_HINT : 'Remove all sources and their results'}
                  onClick={() => setConfirm('all')}
                >
                  Clear all
                </button>
              ))}
          </div>
          {loading ? (
            <div className="skeleton mt-2 h-6 w-48" />
          ) : sources.length === 0 ? (
            <p className="mt-1 text-[13.5px] text-ink-body">Upload an SRS to begin. Drop files here or use “Upload source files” (.txt, .md, .pdf, .docx, 20 MB each).</p>
          ) : (
            <ul className="mt-1.5 flex flex-wrap gap-2">
              {sources.map((s) => (
                <li key={s.id} className="flex items-center gap-1.5 rounded-md border border-line bg-white py-1 pl-2.5 pr-1 text-[12.5px] font-medium text-ink" title={s.warnings.join('; ') || undefined}>
                  <span>
                    {s.filename}
                    {s.pages !== null && <span className="ml-1.5 font-normal text-ink-muted">{s.pages} p.</span>}
                  </span>
                  {confirming === s.id ? (
                    <span role="group" aria-label={`Confirm removing ${s.filename}`} className="flex items-center gap-1.5 pl-1 text-[11.5px] font-normal text-risk-highText">
                      Remove file and its results?
                      <button type="button" className="rounded border border-risk-highLine bg-risk-highBg px-2 py-0.5 font-semibold" onClick={() => { setConfirm(null); onRemove(s.id) }}>
                        Remove
                      </button>
                      <button type="button" className="rounded border border-line bg-white px-2 py-0.5 font-medium text-ink-body" onClick={() => setConfirm(null)}>
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      aria-label={`Remove ${s.filename}`}
                      title={busy ? BUSY_HINT : `Remove ${s.filename}`}
                      disabled={busy}
                      className="rounded p-1 text-ink-faint hover:bg-risk-highBg hover:text-risk-highText disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
                      onClick={() => setConfirm(s.id)}
                    >
                      <X size={14} aria-hidden="true" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <AnalysisBadge state={badge} />
    </section>
  )
}

const STEPS: { stage: Stage; no: string; title: string; sub: string; icon: typeof FileText }[] = [
  { stage: 'collect', no: '01', title: 'Collect', sub: 'Documents · text · work items', icon: FileText },
  { stage: 'identify', no: '02', title: 'Identify', sub: 'Requirement statements + source', icon: FileSearch },
  { stage: 'analyse', no: '03', title: 'Analyse', sub: 'Ambiguity · duplicate · conflict', icon: Sparkles },
  { stage: 'improve', no: '04', title: 'Improve', sub: 'Revision · risk · task · question', icon: Code2 },
  { stage: 'share', no: '05', title: 'Share', sub: 'Enriched requirement records', icon: Network },
]

export type PipelineMode = 'idle' | 'running' | 'complete'

/**
 * Pipeline strip. idle: nothing has run, no step is done and nothing spins. running: steps before `stage` are done and only the current one spins.
 * complete: every step is done and nothing spins.
 */
export function PipelineStrip({ mode, stage }: { mode: PipelineMode; stage: Stage | null }) {
  const activeIndex = mode === 'running' ? Math.max(0, STEPS.findIndex((s) => s.stage === stage)) : -1
  return (
    <ol className="card mx-6 mt-5 grid grid-cols-2 gap-3 px-5 py-4 md:grid-cols-3 xl:mx-9 xl:grid-cols-5" aria-label="Analysis pipeline" data-mode={mode}>
      {STEPS.map((s, i) => {
        const done = mode === 'complete' || (mode === 'running' && i < activeIndex)
        const active = mode === 'running' && i === activeIndex
        const Icon = s.icon
        return (
          <li key={s.stage} data-stage={s.stage} data-state={done ? 'done' : active ? 'active' : 'pending'} aria-current={active ? 'step' : undefined} className="flex min-w-0 items-center gap-3">
            <span className={`flex h-6 shrink-0 items-center rounded-md px-1.5 text-[10px] font-bold ${done || active ? 'bg-brand-100 text-brand-700' : 'bg-risk-noneBg text-ink-muted'}`}>
              {done ? <Check size={12} aria-label="done" /> : s.no}
            </span>
            <Icon size={20} className={done || active ? 'shrink-0 text-brand-600' : 'shrink-0 text-ink-faint'} aria-hidden="true" />
            <div className="min-w-0">
              <div className={`flex items-center gap-1.5 text-[13.5px] font-semibold ${active ? 'text-brand-700' : 'text-ink'}`}>
                {s.title}
                {active && <Spinner className="h-3 w-3 text-brand-600" />}
              </div>
              <div className="truncate text-[11px] text-ink-muted">{s.sub}</div>
            </div>
            {i < STEPS.length - 1 && <ArrowRight size={18} className="ml-auto hidden shrink-0 text-ink-faint xl:block" aria-hidden="true" />}
          </li>
        )
      })}
    </ol>
  )
}

export function Banners() {
  return (
    <div className="mx-6 mt-5 grid gap-4 xl:mx-9 xl:grid-cols-2">
      <div className="flex items-center gap-3 rounded-card border border-ok-line bg-ok-bg px-5 py-3.5 text-[12.5px] text-ok-text">
        <Check size={18} className="shrink-0" aria-hidden="true" />
        <p>
          <strong>C1 owns:</strong> requirement identification, semantic analysis, risk, clarification, revisions and task drafts.
        </p>
      </div>
      <div className="flex items-center gap-3 rounded-card border border-info-line bg-info-bg px-5 py-3.5 text-[12.5px] text-info-text">
        <ArrowRight size={18} className="shrink-0" aria-hidden="true" />
        <p>
          <strong>C3 owns next:</strong> RVU extraction, QA evidence and test adequacy.
        </p>
      </div>
    </div>
  )
}

export function jobBadge(job: Job | undefined, finished: boolean, pending: boolean, requirements: number, stale: boolean): AnalysisBadgeState {
  if (pending) return 'running'
  if (job?.error) return 'failed'
  if (job && !finished) return 'running'
  if (stale) return 'stale'
  if (job) return 'complete'
  return requirements > 0 ? 'complete' : 'none'
}
