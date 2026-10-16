import { Pause, Play, Sparkles } from 'lucide-react'
import type { TaskDrafts } from '../api/types'
import { barText, formatEta, formatRough, handledCount, percentHandled, segments, stallMinutes, timeLeft, useRunClock } from '../lib/progress'
import { Spinner } from './ui'

export { formatEta } from '../lib/progress'

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
 * Real progress of the draft queue: the counts and the time left come from the API; before the API has an estimate the time left is a rough one from
 * the throughput this page has watched (lib/progress.ts). Shown while drafts wait or run, or while some requirements have no draft yet.
 */
export function DraftProgress({ drafts: d, onPause, onResume, onGenerateAll, busy, analysing, target }: Props) {
  const working = !!d && d.in_progress > 0
  const clock = useRunClock(d ? handledCount(d) : 0, working && !d?.paused)
  if (!d || d.total === 0 || (d.not_generated === 0 && d.in_progress === 0 && !d.paused)) return null
  const pct = percentHandled(d)
  const left = timeLeft(d, clock)
  const stalled = working && !d.paused ? stallMinutes(clock) : null
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
      <div className="mt-2 flex items-center gap-3">
        <div
          className="flex h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-risk-noneBg"
          role="progressbar"
          aria-label="Draft progress"
          aria-valuemin={0}
          aria-valuemax={d.total}
          aria-valuenow={handledCount(d)}
          aria-valuetext={barText(d)}
          data-testid="draft-bar"
        >
          {segments(d).map((g) => (
            <div key={g.key} data-segment={g.key} data-count={g.count} title={`${g.label}: ${g.count}`} className={`h-full ${g.className} transition-all`} style={{ width: `${g.width}%` }} />
          ))}
        </div>
        <span className="shrink-0 text-[13px] font-semibold text-ink" data-testid="draft-percent">
          {pct}%
        </span>
        <span className="shrink-0 text-[12px] text-ink-body" data-testid="draft-handled">
          {handledCount(d)} of {d.total} handled
        </span>
      </div>
      <ul className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-muted" aria-label="Legend" data-testid="draft-legend">
        {segments(d).map((g) => (
          <li key={g.key} className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${g.className}`} aria-hidden="true" />
            {g.label} {g.count}
          </li>
        ))}
      </ul>
      <p className="mt-1.5 text-[11.5px] text-ink-muted" data-testid="draft-eta">
        {d.paused && d.paused_reason === 'cloud_unreachable'
          ? `Paused: cloud unreachable. ${d.in_progress} waiting. Nothing new starts until you choose Retry or Switch to device.`
          : d.paused
            ? `Paused: ${d.in_progress} waiting. The draft being written finishes, then nothing new starts until you press Resume.`
            : working
              ? left.kind === 'normal'
                ? formatEta(left.seconds)
                : left.kind === 'rough'
                  ? formatRough(left.seconds)
                  : 'Calculating time left…'
              : 'Nothing is being written. Open a requirement and press Generate draft, or use Generate all remaining.'}
      </p>
      {stalled !== null && (
        <p className="mt-1 text-[11.5px] text-risk-medText" role="status" data-testid="draft-stall">
          No draft has finished for {stalled} {stalled === 1 ? 'minute' : 'minutes'}. The server may be slow or unreachable. You can wait, press Pause, or retry a failed draft from its requirement.
        </p>
      )}
      {target && (
        <p className="mt-0.5 text-[11.5px] text-ink-muted" data-testid="draft-target">
          Processing: {target}
        </p>
      )}
    </section>
  )
}
