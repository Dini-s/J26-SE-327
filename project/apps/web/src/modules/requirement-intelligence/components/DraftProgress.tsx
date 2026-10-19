import { Pause, Play, Sparkles } from 'lucide-react'
import type { TaskDrafts } from '../api/types'
import { copy } from '../copy'
import { barText, formatEta, formatRough, handledCount, percentHandled, segments, stallMinutes, timeLeft, useRunClock } from '../lib/progress'
import { Spinner } from './ui'

interface Props {
  drafts?: TaskDrafts
  onPause: () => void
  onResume: () => void
  onGenerateAll: () => void
  /** A request for pause / resume / generate-all is in flight. */
  busy: boolean
  /** The analysis itself is running: nothing can be queued yet. */
  analysing: boolean
}

/**
 * Real progress of the draft queue: the counts and the time left come from the service; before it has an estimate (it needs 3 finished drafts)
 * the time left is a rough one from the throughput this page has watched (lib/progress.ts). Shown while drafts wait or run, or while some
 * requirements have no draft yet.
 */
export function DraftProgress({ drafts: d, onPause, onResume, onGenerateAll, busy, analysing }: Props) {
  const working = !!d && d.in_progress > 0
  const clock = useRunClock(d ? handledCount(d) : 0, working && !d?.paused)
  if (!d || d.total === 0 || (d.not_generated === 0 && d.in_progress === 0 && !d.paused)) return null
  const pct = percentHandled(d)
  const left = timeLeft(d, clock)
  const stalled = working && !d.paused ? stallMinutes(clock) : null
  return (
    <section className="c1-card px-4 py-3" aria-label={copy.progress.title} data-testid="draft-progress" data-paused={d.paused}>
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <p className="text-xs text-heading" data-testid="draft-counts">
          {copy.progress.counts(d.generated, d.total, d.not_generated, d.needs_clarification, d.failed, d.manual_review, working ? d.in_progress : 0)}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {working && !d.paused && (
            <button type="button" className="c1-btn-secondary !px-3 !py-1.5" disabled={busy} onClick={onPause} title={copy.progress.pauseHint}>
              <Pause size={13} aria-hidden="true" /> {copy.progress.pause}
            </button>
          )}
          {d.paused && (
            <button type="button" className="c1-btn-primary !px-3 !py-1.5" disabled={busy} onClick={onResume}>
              <Play size={13} aria-hidden="true" /> {copy.progress.resume}
            </button>
          )}
          {d.not_generated > 0 && (
            <button type="button" className="c1-btn-secondary !px-3 !py-1.5" disabled={busy || analysing} onClick={onGenerateAll} title={copy.progress.allHint(d.not_generated)}>
              {busy ? <Spinner className="h-3.5 w-3.5" /> : <Sparkles size={13} aria-hidden="true" />} {copy.progress.generateAll}
            </button>
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <div
          className="flex h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-secondary-bg"
          role="progressbar"
          aria-label={copy.progress.title}
          aria-valuemin={0}
          aria-valuemax={d.total}
          aria-valuenow={handledCount(d)}
          aria-valuetext={barText(d)}
          data-testid="draft-bar"
        >
          {segments(d).map((g) => (
            <div key={g.key} data-segment={g.key} data-count={g.count} title={`${g.label}: ${g.count}`} className="h-full transition-all" style={{ width: `${g.width}%`, backgroundColor: g.color }} />
          ))}
        </div>
        <span className="shrink-0 text-xs font-semibold text-heading" data-testid="draft-percent">
          {pct}%
        </span>
        <span className="shrink-0 text-[11.5px] text-body" data-testid="draft-handled">
          {copy.progress.handled(handledCount(d), d.total)}
        </span>
      </div>
      <ul className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-secondary-text" aria-label={copy.progress.legend} data-testid="draft-legend">
        {segments(d).map((g) => (
          <li key={g.key} className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: g.color }} aria-hidden="true" />
            {g.label} {g.count}
          </li>
        ))}
      </ul>
      <p className="mt-1.5 text-[11.5px] text-secondary-text" data-testid="draft-eta">
        {d.paused && d.paused_reason === 'cloud_unreachable'
          ? copy.progress.pausedCloud(d.in_progress)
          : d.paused
            ? copy.progress.paused(d.in_progress)
            : working
              ? left.kind === 'normal'
                ? formatEta(left.seconds)
                : left.kind === 'rough'
                  ? formatRough(left.seconds)
                  : copy.progress.calculating
              : copy.progress.idle}
      </p>
      {stalled !== null && (
        <p className="mt-1 text-[11.5px] text-warning-text" role="status" data-testid="draft-stall">
          {copy.progress.stall(stalled)}
        </p>
      )}
    </section>
  )
}
