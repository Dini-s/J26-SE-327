import { Pause, Play, Sparkles } from 'lucide-react'
import type { TaskDrafts } from '../api/types'
import { Spinner } from './ui'

/** "about 12 min" style text for a number of seconds. */
export function formatEta(seconds: number): string {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))} s`
  const minutes = Math.ceil(seconds / 60)
  if (minutes < 60) return `about ${minutes} min`
  return `about ${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

interface Props {
  drafts?: TaskDrafts
  onPause: () => void
  onResume: () => void
  onGenerateAll: () => void
  /** A request for pause / resume / generate-all is in flight. */
  busy: boolean
  /** The analysis itself is running: nothing can be queued yet. */
  analysing: boolean
  /** "On device" or "Cloud (host)": where the drafts are being written. */
  target?: string
}

/**
 * Real progress of the draft queue: the counts come from the API, the time left from the mean of the last 10 real reply times (hidden until 3
 * exist). Shown while drafts wait or run, or while some requirements have no draft yet.
 */
export function DraftProgress({ drafts: d, onPause, onResume, onGenerateAll, busy, analysing, target }: Props) {
  if (!d || d.total === 0 || (d.not_generated === 0 && d.in_progress === 0 && !d.paused)) return null
  const resolved = d.generated + d.needs_clarification + d.manual_review + d.failed
  const pct = Math.round((resolved / d.total) * 100)
  const working = d.in_progress > 0
  return (
    <section className="mx-6 mt-4 rounded-card border border-line bg-white px-5 py-3.5 xl:mx-9" aria-label="Draft progress" data-testid="draft-progress" data-paused={d.paused}>
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <p className="text-[13px] text-ink" data-testid="draft-counts">
          Drafts <strong>{d.generated}</strong> of {d.total} done, {d.not_generated} not generated, {d.needs_clarification} needs clarification, {d.failed} failed
          {d.manual_review > 0 ? `, ${d.manual_review} manual review` : ''}
          {working ? `, ${d.in_progress} waiting` : ''}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {working && !d.paused && (
            <button type="button" className="btn-secondary !px-3 !py-1.5 !text-[12.5px]" disabled={busy} onClick={onPause} title="Stop taking new drafts; the one being written finishes">
              <Pause size={14} aria-hidden="true" /> Pause
            </button>
          )}
          {d.paused && (
            <button type="button" className="btn-primary !px-3 !py-1.5 !text-[12.5px]" disabled={busy} onClick={onResume}>
              <Play size={14} aria-hidden="true" /> Resume
            </button>
          )}
          {d.not_generated > 0 && (
            <button
              type="button"
              className="btn-secondary !px-3 !py-1.5 !text-[12.5px]"
              disabled={busy || analysing}
              onClick={onGenerateAll}
              title={`Write drafts for the ${d.not_generated} requirements that have none yet`}
            >
              {busy ? <Spinner className="h-3.5 w-3.5" /> : <Sparkles size={14} aria-hidden="true" />} Generate all remaining
            </button>
          )}
        </div>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-brand-100" role="progressbar" aria-valuemin={0} aria-valuemax={d.total} aria-valuenow={resolved} aria-label="Draft progress">
        <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1.5 text-[11.5px] text-ink-muted" data-testid="draft-eta">
        {d.paused && d.paused_reason === 'cloud_unreachable'
          ? `Paused: cloud unreachable. ${d.in_progress} waiting. Nothing new starts until you choose Retry or Switch to device.`
          : d.paused
          ? `Paused: ${d.in_progress} waiting. The draft being written finishes, then nothing new starts until you press Resume.`
          : working
            ? d.eta_seconds !== null
              ? `${formatEta(d.eta_seconds)} left (from the last ${d.latency_samples} real replies)`
              : `Estimating time left: needs 3 finished drafts (${d.latency_samples} so far)`
            : 'Nothing is being written. Open a requirement and press Generate draft, or use Generate all remaining.'}
      </p>
      {target && (
        <p className="mt-0.5 text-[11.5px] text-ink-muted" data-testid="draft-target">
          Processing: {target}
        </p>
      )}
    </section>
  )
}
