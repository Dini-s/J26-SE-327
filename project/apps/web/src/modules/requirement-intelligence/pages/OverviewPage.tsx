import { ArrowRight, FileText, Layers, ListChecks, Send, Target, type LucideIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useOverview, usePublish, useSprints } from '../api/hooks'
import type { Overview, SyncStatus } from '../api/types'
import { FindingBars, SprintBars, StatusDonut, DECISION_COLOR } from '../components/Charts'
import { ExportMenu } from '../components/ExportMenu'
import { JiraIcon } from '../components/JiraIcon'
import { JiraActions } from '../components/JiraControls'
import { ProcessStrip } from '../components/ProcessStrip'
import { ChangeSprintDialog } from '../components/PlanDialogs'
import { Skeleton, Spinner } from '../components/ui'
import { useModule } from '../context/ModuleState'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { publishErrorMessage } from '../lib/handoff'
import { formatDate } from '../lib/planning'

const when = (iso: string) => new Date(iso).toLocaleString()

interface KpiProps {
  testid: string
  label: string
  value: string
  sub: string
  icon: LucideIcon
  tint: string
  to: string
}

function Kpi({ testid, label, value, sub, icon: Icon, tint, to }: KpiProps) {
  return (
    <Link to={to} data-testid={testid} className="c1-card flex items-center gap-3 px-4 py-3 transition hover:border-indigo-200 focus-visible:outline-offset-2">
      <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${tint}`}>
        <Icon size={19} aria-hidden="true" />
      </span>
      <span className="min-w-0">
        <span className="block text-xs text-body">{label}</span>
        <span className="block text-2xl font-bold leading-tight text-heading">{value}</span>
        <span className="block truncate text-[11px] text-secondary-text">{sub}</span>
      </span>
    </Link>
  )
}

function Kpis({ o }: { o: Overview }) {
  const types = Object.entries(o.sources.by_type)
    .map(([k, n]) => `${copy.sources.type[k as keyof typeof copy.sources.type] ?? k} ${n}`)
    .join(' · ')
  return (
    <section className="grid grid-cols-1 gap-3 sm:grid-cols-2" aria-label={copy.overview.kpis}>
      <Kpi testid="kpi-requirements" label={copy.overview.requirements} value={String(o.counts.requirements)} sub={copy.overview.requirementsSub} icon={FileText} tint="bg-primary-light text-primary" to="/requirement/review" />
      <Kpi testid="kpi-pending" label={copy.overview.needsDecision} value={String(o.decisions.pending)} sub={copy.overview.needsDecisionSub} icon={ListChecks} tint="bg-amber-50 text-amber-600" to="/requirement/review" />
      <Kpi testid="kpi-documents" label={copy.overview.documents} value={String(o.sources.count)} sub={copy.overview.documentsSub(types || copy.common.none)} icon={Layers} tint="bg-violet-50 text-violet-600" to="/requirement/sources" />
      <Kpi testid="kpi-analysis" label={copy.overview.analysis} value={copy.overview.analysisValue(o.analysis.ready, o.analysis.total)} sub={copy.overview.analysisSub} icon={Target} tint="bg-emerald-50 text-emerald-600" to="/requirement/sources" />
    </section>
  )
}

function CurrentSprintCard({ o, pid }: { o: Overview; pid: number }) {
  const [open, setOpen] = useState(false)
  const sprints = useSprints(pid)
  const s = o.current_sprint
  return (
    <section className="c1-card flex flex-col p-4" aria-label={copy.plan.cardTitle} data-testid="current-sprint-card">
      <div className="flex items-start justify-between gap-2">
        <span className="c1-label">{copy.plan.cardTitle}</span>
        <button type="button" className="c1-btn-secondary !px-2.5 !py-1" onClick={() => setOpen(true)} disabled={!sprints.data}>
          {copy.plan.change}
        </button>
      </div>
      {s ? (
        <>
          <h2 className="mt-1 text-lg font-bold leading-tight text-heading" data-testid="current-sprint-name">
            {s.name}
          </h2>
          {(s.start_date || s.end_date) && <p className="mt-0.5 text-xs text-secondary-text">{copy.plan.dates(s.start_date, s.end_date)}</p>}
          {s.goal && (
            <p className="mt-1 text-xs text-body" data-testid="current-sprint-goal">
              <span className="font-medium text-heading">{copy.plan.goal}: </span>
              {s.goal}
            </p>
          )}
          <div className="mt-3 text-xs text-body">
            <div className="flex justify-between">
              <span>{copy.plan.decided(s.decided, s.requirements)}</span>
              <span className="text-secondary-text">{s.percent_decided}%</span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-secondary-bg" role="progressbar" aria-valuemin={0} aria-valuemax={s.requirements} aria-valuenow={s.decided} aria-label={copy.plan.cardTitle}>
              <div className="h-full rounded-full" style={{ width: `${s.percent_decided}%`, backgroundColor: DECISION_COLOR.accepted }} />
            </div>
            <p className="mt-1 text-[11px] text-secondary-text">{copy.plan.needDecision(s.pending)}</p>
          </div>
        </>
      ) : (
        <p className="mt-2 text-xs text-secondary-text">{copy.plan.none}</p>
      )}
      {open && sprints.data && <ChangeSprintDialog pid={pid} sprints={sprints.data} onClose={() => setOpen(false)} />}
    </section>
  )
}

function StatusCard({ o }: { o: Overview }) {
  const total = o.counts.requirements
  return (
    <section className="c1-card p-4" aria-label={copy.overview.progressTitle} data-testid="decision-progress">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-heading">{copy.overview.progressTitle}</h2>
        <span className="text-xs text-secondary-text" data-testid="percent-decided">
          {copy.overview.percentDecided(o.decisions.percent_decided)}
        </span>
      </div>
      {total === 0 ? (
        <p className="mt-3 text-xs text-secondary-text">
          {copy.overview.noRequirements}{' '}
          <Link to="/requirement/sources" className="font-medium text-primary underline-offset-2 hover:underline">
            {copy.overview.goToSources}
          </Link>
        </p>
      ) : (
        <>
          <StatusDonut decisions={o.decisions} total={total} />
          <Link to="/requirement/review" className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-2 hover:underline">
            {copy.overview.openQueue} <ArrowRight size={12} aria-hidden="true" />
          </Link>
        </>
      )}
    </section>
  )
}

const BADGE: Record<string, string> = {
  analyzed: 'border-success-border bg-success-bg text-success-text',
  analyzing: 'border-info-border bg-info-bg text-blue-800',
  not_analyzed: 'border-warning-border bg-warning-bg text-warning-text',
  failed: 'border-danger-border bg-danger-bg text-danger-text',
}

function LatestUploads({ o }: { o: Overview }) {
  const sprintName = (id: number | null) => o.by_sprint.find((s) => s.sprint_id === id)
  return (
    <section className="c1-card p-4" aria-label={copy.overview.latestTitle} data-testid="latest-uploads">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-heading">{copy.overview.latestTitle}</h2>
        <Link to="/requirement/sources" className="inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-2 hover:underline">
          {copy.overview.manageSources} <ArrowRight size={12} aria-hidden="true" />
        </Link>
      </div>
      {o.latest_uploads.length === 0 ? (
        <p className="mt-3 text-xs text-secondary-text">{copy.overview.latestNone}</p>
      ) : (
        <ul className="mt-2 divide-y divide-border">
          {o.latest_uploads.map((s) => {
            const sprint = sprintName(s.default_sprint_id)
            return (
              <li key={s.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-xs" data-testid="latest-upload">
                {s.source_type === 'jira' ? <JiraIcon size={14} /> : <FileText size={14} className="shrink-0 text-primary" aria-hidden="true" />}
                <span className="min-w-0 flex-1 truncate font-medium text-heading">{s.filename}</span>
                <span className="text-secondary-text">{copy.sources.type[s.source_type] ?? s.source_type}</span>
                <span className="text-secondary-text" data-testid="latest-place">
                  {sprint ? sprint.name : copy.plan.unassigned}
                </span>
                <span className={`rounded-full border px-2 py-px text-[10.5px] font-semibold ${BADGE[s.analysis_state]}`}>{copy.sources.state[s.analysis_state]}</span>
                <span className="w-24 text-right text-secondary-text">{copy.overview.latestRequirements(s.requirements)}</span>
                <span className="sr-only">{copy.sources.uploadedOn(formatDate(s.uploaded_at))}</span>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

const DOT: Record<string, string> = { synced: 'bg-emerald-500', syncing: 'bg-blue-500', pending: 'bg-amber-500', retrying: 'bg-amber-500', unreachable: 'bg-red-500', not_configured: 'bg-slate-400' }

function syncText(sync: SyncStatus): string {
  const t = copy.graph.state[sync.state]
  if (typeof t === 'function') return sync.last_synced_at ? t(when(sync.last_synced_at)) : copy.graph.syncedNever
  return t ?? sync.state
}

function syncHint(sync: SyncStatus): string | null {
  if (!sync.enabled && sync.state !== 'not_configured') return copy.graph.off
  if (sync.state === 'not_configured') return copy.graph.notConnectedHint
  if (sync.state === 'retrying') return copy.graph.retryingHint
  if (sync.state === 'unreachable') return copy.graph.unreachableHint
  if (sync.state === 'pending') return copy.graph.pendingHint
  return null
}

function GraphCard({ o, pid }: { o: Overview; pid: number }) {
  const publish = usePublish(pid)
  const toasts = useToasts()
  const sync = o.sync
  const empty = o.counts.requirements === 0
  const hint = syncHint(sync)
  const onSyncNow = () =>
    publish.mutate(undefined, {
      onSuccess: (r) => toasts.push(copy.graph.syncedToast(r.counts.Requirement ?? 0), 'success'),
      onError: (e) => toasts.push(publishErrorMessage(e), 'error'),
    })
  const sent = sync.counts ? Object.entries(sync.counts).filter(([k]) => copy.graph.items[k]) : []
  return (
    <section id="knowledge-graph" className="c1-card scroll-mt-4 p-4" aria-label={copy.graph.title} data-testid="graph-card">
      <h2 className="text-sm font-semibold text-heading">{copy.graph.title}</h2>
      <p className="mt-1 text-xs text-secondary-text">{copy.graph.intro}</p>
      <p className="mt-3 flex items-center gap-2 text-xs font-medium text-heading" role="status" data-testid="sync-state" data-state={sync.state}>
        <span className={`h-2 w-2 rounded-full ${DOT[sync.state] ?? 'bg-slate-400'}`} aria-hidden="true" />
        {syncText(sync)}
      </p>
      {hint && (
        <p className="mt-1 text-[11.5px] text-secondary-text" data-testid="sync-hint">
          {hint}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <ExportMenu projectId={pid} canExport={!empty} />
      </div>
      <details className="mt-3 text-xs text-secondary-text" data-testid="sync-details">
        <summary className="cursor-pointer font-medium text-heading">{copy.graph.details}</summary>
        <dl className="mt-1.5 divide-y divide-border">
          <div className="flex justify-between gap-3 py-1">
            <dt>{copy.graph.lastSync}</dt>
            <dd className="text-right text-heading">{sync.last_synced_at ? when(sync.last_synced_at) : copy.common.none}</dd>
          </div>
          {sync.next_attempt_at && (
            <div className="flex justify-between gap-3 py-1">
              <dt>{copy.graph.nextAttempt}</dt>
              <dd className="text-right text-heading">{when(sync.next_attempt_at)}</dd>
            </div>
          )}
          {sent.length > 0 && (
            <div className="flex justify-between gap-3 py-1">
              <dt>{copy.graph.sent}</dt>
              <dd className="text-right text-heading">{sent.map(([k, n]) => `${n} ${copy.graph.items[k]}`).join(' · ')}</dd>
            </div>
          )}
        </dl>
        <button
          type="button"
          className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-2 hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
          data-testid="sync-now"
          disabled={publish.isPending || empty || sync.state === 'not_configured'}
          title={sync.state === 'not_configured' ? copy.graph.syncNowDisabled : empty ? copy.handoff.nothingToPublish : undefined}
          onClick={onSyncNow}
        >
          {publish.isPending ? <Spinner className="h-3 w-3" /> : <Send size={11} aria-hidden="true" />} {copy.graph.syncNow}
        </button>
      </details>
    </section>
  )
}

function Page({ children }: { children: ReactNode }) {
  return <div className="space-y-3">{children}</div>
}

/** Where the project stands: the current sprint, the numbers, charts, the latest uploads and the knowledge graph. All from one overview call. */
export function OverviewPage() {
  const { project } = useModule()
  const q = useOverview(project?.id)

  if (!project || q.isLoading) {
    return (
      <div className="space-y-3" aria-busy="true" aria-label={copy.common.loading}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }
  if (q.isError || !q.data) {
    return (
      <div role="alert" className="rounded-xl border border-danger-border bg-danger-bg p-4 text-xs text-danger-text">
        {copy.overview.loadFailed(q.error?.message ?? copy.common.unknown)}
        <button type="button" className="ml-3 font-semibold underline" onClick={() => void q.refetch()}>
          {copy.common.retry}
        </button>
      </div>
    )
  }
  const o = q.data
  return (
    <Page>
      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <CurrentSprintCard o={o} pid={project.id} />
        <Kpis o={o} />
      </div>
      <ProcessStrip pipeline={o.pipeline} />
      <div className="grid gap-3 xl:grid-cols-3">
        <StatusCard o={o} />
        <SprintBars rows={o.by_sprint} />
        <FindingBars counts={o.findings_by_type} />
      </div>
      <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <LatestUploads o={o} />
        <div className="space-y-3">
          <GraphCard o={o} pid={project.id} />
          <JiraActions pid={project.id} variant="card" />
        </div>
      </div>
    </Page>
  )
}
