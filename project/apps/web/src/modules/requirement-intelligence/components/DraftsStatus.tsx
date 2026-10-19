import { AlertTriangle, RefreshCw } from 'lucide-react'
import { useEngine, useGenerateRemaining, useJob, usePauseGeneration, useRetryFailed, useSummary } from '../api/hooks'
import { useModule } from '../context/ModuleState'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { DraftProgress } from './DraftProgress'
import { Spinner } from './ui'

/** Why "Retry failed drafts" cannot be used right now, or null when it can. */
function retryFailedBusy(inProgress: number, engineDown: boolean): string | null {
  if (inProgress > 0) return copy.drafts.retryBusyHint
  return engineDown ? copy.drafts.retryEngineHint : null
}

/** "N drafts could not be written" with Retry failed drafts. Shown on Sources & Findings (under the progress) and on the Publish page. */
export function FailedDraftsBanner({ pid }: { pid: number | undefined }) {
  const toasts = useToasts()
  const summary = useSummary(pid)
  const engine = useEngine()
  const retryFailed = useRetryFailed(pid)
  const drafts = summary.data?.task_drafts
  const engineDown = !!engine.data && (engine.data.target === 'cloud' ? engine.data.cloud.reachable === false : !engine.data.device.reachable)
  const retryHint = retryFailedBusy(drafts?.in_progress ?? 0, engineDown)
  const onRetry = () =>
    retryFailed.mutate(undefined, {
      onSuccess: (r) => toasts.push(r.queued > 0 ? copy.drafts.retryQueued(r.queued) : copy.drafts.retryNothing, 'success'),
      onError: (e) => toasts.push(copy.drafts.retryFailedError(e.message), 'error'),
    })

  return (
    <>
      {!!drafts && drafts.failed > 0 && (
        <section className="c1-card flex flex-wrap items-center justify-between gap-3 border-warning-border bg-warning-bg px-4 py-3" aria-label={copy.drafts.failedBanner(drafts.failed)} data-testid="failed-banner">
          <div className="flex min-w-0 items-start gap-2 text-warning-text">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <div>
              <p className="text-xs font-semibold" data-testid="failed-banner-title">
                {copy.drafts.failedBanner(drafts.failed)}
              </p>
              <p className="text-[11.5px]">{copy.drafts.failedBannerHint}</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <button type="button" className="c1-btn-secondary !px-3 !py-1.5" data-testid="retry-failed" disabled={!!retryHint || retryFailed.isPending} title={retryHint ?? undefined} aria-describedby={retryHint ? 'retry-hint' : undefined} onClick={onRetry}>
              {retryFailed.isPending ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw size={13} aria-hidden="true" />} {copy.drafts.retryFailed}
            </button>
            {retryHint && (
              <span id="retry-hint" className="text-[11px] text-warning-text" data-testid="retry-hint">
                {retryHint}
              </span>
            )}
          </div>
        </section>
      )}
    </>
  )
}

/**
 * Where the writing of task drafts stands, with Pause / Resume / Generate all remaining and, when some drafts failed, Retry failed drafts.
 * Shown on Sources & Findings.
 */
export function DraftsStatus({ pid }: { pid: number | undefined }) {
  const { jobId } = useModule()
  const toasts = useToasts()
  const summary = useSummary(pid)
  const job = useJob(jobId)
  const pause = usePauseGeneration(pid)
  const generateRemaining = useGenerateRemaining(pid)
  const drafts = summary.data?.task_drafts
  const analysing = !!job.data && !job.data.part_a_done && !job.data.error

  const onPause = (p: boolean) => pause.mutate(p, { onError: (e) => toasts.push(p ? copy.drafts.pauseFailed(e.message) : copy.drafts.resumeFailed(e.message), 'error') })
  const onGenerateAll = () =>
    generateRemaining.mutate(undefined, {
      onSuccess: (r) => toasts.push(r.queued > 0 ? copy.drafts.queuedMany(r.queued) : copy.drafts.nothingToQueue, 'success'),
      onError: (e) => toasts.push(copy.drafts.queueFailed(e.message), 'error'),
    })

  return (
    <>
      <DraftProgress drafts={drafts} onPause={() => onPause(true)} onResume={() => onPause(false)} onGenerateAll={onGenerateAll} busy={pause.isPending || generateRemaining.isPending} analysing={analysing} />
      <FailedDraftsBanner pid={pid} />
    </>
  )
}
