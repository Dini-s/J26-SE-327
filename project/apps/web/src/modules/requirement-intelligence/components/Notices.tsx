import { AlertTriangle, CheckCircle2, RefreshCw, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { Job } from '../api/types'
import { copy } from '../copy'
import { Spinner } from './ui'

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
    <div role="status" data-testid="analyzing-notice" className="flex items-start gap-3 rounded-xl border border-info-border bg-info-bg px-4 py-3 text-xs text-blue-800">
      <Spinner className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <strong>{copy.sources.analysing(mmss(seconds))}</strong> {copy.sources.analysingHint}
      </div>
    </div>
  )
}

/** Inline (not only a toast) error for a failed or timed-out analysis request. */
export function AnalyzeError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" data-testid="analyze-error" className="flex flex-wrap items-center gap-3 rounded-xl border border-danger-border bg-danger-bg px-4 py-3 text-xs text-danger-text">
      <XCircle size={16} className="shrink-0" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <strong>{copy.sources.analyzeFailed}</strong> {message}
      </span>
      <button type="button" className="inline-flex items-center gap-1.5 rounded-md border border-danger-border bg-white px-3 py-1.5 font-semibold hover:bg-red-50" onClick={onRetry}>
        <RefreshCw size={13} aria-hidden="true" /> {copy.common.tryAgain}
      </button>
    </div>
  )
}

export type AnalysisBadgeState = 'none' | 'running' | 'complete' | 'failed' | 'stale'

export function AnalysisBadge({ state }: { state: AnalysisBadgeState }) {
  const base = 'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11.5px] font-semibold'
  if (state === 'running')
    return (
      <span role="status" data-testid="analysis-badge" className={`${base} border-info-border bg-info-bg text-blue-800`}>
        <Spinner className="h-3.5 w-3.5" /> {copy.sources.badge.running}
      </span>
    )
  if (state === 'failed')
    return (
      <span role="status" data-testid="analysis-badge" className={`${base} border-danger-border bg-danger-bg text-danger-text`}>
        <XCircle size={13} aria-hidden="true" /> {copy.sources.badge.failed}
      </span>
    )
  if (state === 'stale')
    return (
      <span role="status" data-testid="analysis-badge" className={`${base} border-warning-border bg-warning-bg text-warning-text`}>
        <AlertTriangle size={13} aria-hidden="true" /> {copy.sources.badge.stale}
      </span>
    )
  if (state === 'complete')
    return (
      <span role="status" data-testid="analysis-badge" className={`${base} border-success-border bg-success-bg text-success-text`}>
        {copy.sources.badge.complete} <CheckCircle2 size={13} aria-hidden="true" />
      </span>
    )
  return (
    <span role="status" data-testid="analysis-badge" className={`${base} border-border bg-white text-secondary-text`}>
      {copy.sources.badge.none}
    </span>
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
