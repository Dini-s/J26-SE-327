import { useQueryClient } from '@tanstack/react-query'
import { ChevronRight, CloudUpload, Pencil, Plus, Search, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState, type KeyboardEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { isJobFinished, useAnalyze, useClearSources, useDeleteSource, useJob, useReanalyze, useRequirementList, useSources, useSprints, useSummary, useUpdateSprint } from '../api/hooks'
import type { FindingType, Policy, RequirementRow, RiskFilter, Source, Sprint } from '../api/types'
import { ConfirmDialog } from '../components/Dialog'
import { AnalysisBadge, AnalyzeError, AnalyzingNotice, jobBadge } from '../components/Notices'
import { JiraActions } from '../components/JiraControls'
import { AnalyseDialog } from '../components/AnalyseDialog'
import { DraftsStatus } from '../components/DraftsStatus'
import { MoveDialog } from '../components/MoveDialog'
import { MoveDocumentsDialog, NextSprintCreated } from '../components/NextSprint'
import { SprintDialog } from '../components/PlanDialogs'
import { TYPE_ICON } from '../components/RequirementList'
import { SourceCard } from '../components/SourceCard'
import { UploadDialog } from '../components/UploadDialog'
import { AiClarifyBadge, RiskBadge, Skeleton, Spinner } from '../components/ui'
import { SEARCH_DEBOUNCE_MS } from '../config'
import { useModule } from '../context/ModuleState'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { TYPE_LABEL, primaryType, sourceLabel } from '../lib/format'
import { groupSources, needsAnalysis, nextSprintName, ownSprints } from '../lib/planning'

type Tab = 'sources' | 'findings'
type View = 'ambiguities' | 'duplicates' | 'conflicts' | 'risk'
const VIEWS: View[] = ['ambiguities', 'duplicates', 'conflicts', 'risk']
const VIEW_TYPE: Record<View, FindingType> = { ambiguities: 'ambiguity', duplicates: 'duplicate', conflicts: 'conflict', risk: 'all' }
const RISK_ORDER: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1, NONE: 0 }

// ------------------------------------------------------------------------------------------------------------------ sources tab
type Dialogue =
  | { kind: 'upload'; sprintId?: number }
  | { kind: 'sprint'; sprint?: Sprint }
  | { kind: 'next-sprint' }
  | { kind: 'sprint-created'; sprint: Sprint }
  | { kind: 'move-documents'; sprint: Sprint }
  | { kind: 'move'; source: Source }
  | { kind: 'analyse'; sources: Source[]; all: boolean; again: boolean }
  | { kind: 'remove'; source: Source }
  | { kind: 'clear' }

function Badge({ children }: { children: string }) {
  return <span className="rounded-full bg-primary px-2 py-px text-[10px] font-semibold text-white">{children}</span>
}

function SourcesTab() {
  const { project, jobId, setJobId, setStale, stale, policy, setPolicy } = useModule()
  const pid = project?.id
  const qc = useQueryClient()
  const toasts = useToasts()
  const sources = useSources(pid)
  const sprints = useSprints(pid)
  const summary = useSummary(pid)
  const job = useJob(jobId)
  const finished = isJobFinished(job.data)
  const analyze = useAnalyze(pid)
  const reanalyze = useReanalyze(pid)
  const removeSource = useDeleteSource(pid)
  const updateSprint = useUpdateSprint(pid)
  const clearSources = useClearSources(pid, () => {
    setJobId(null)
    setStale(false)
  })
  const [dialog, setDialog] = useState<Dialogue | null>(null)
  const [closed, setClosed] = useState<Record<string, boolean>>({})
  const [workingOn, setWorkingOn] = useState<number | null>(null)
  const [viewing, setViewing] = useState<string | null>(null)
  const [picked, setPicked] = useState<Set<number>>(new Set())

  const drafts = summary.data?.task_drafts
  const generating = !drafts?.paused && ((drafts?.in_progress ?? 0) > 0 || (!!job.data && job.data.generation.queued > 0))
  const running = analyze.isPending || reanalyze.isPending || generating
  const list = useMemo(() => sources.data ?? [], [sources.data])
  const sprintList = useMemo(() => ownSprints(sprints.data ?? []), [sprints.data])
  const pending = list.filter(needsAnalysis)
  const groups = useMemo(() => groupSources(sprintList, list), [sprintList, list])
  // one sprint is shown at a time: the current one until another is chosen (a sprint made with "Add to next sprint" is shown right away)
  const defaultKey = (groups.find((g) => g.sprint?.is_current) ?? groups[0])?.key ?? null
  const viewKey = viewing !== null && groups.some((g) => g.key === viewing) ? viewing : defaultKey
  const shownGroups = groups.filter((g) => g.key === viewKey)
  const shownSprint = shownGroups[0]?.sprint ?? null
  const shownIds = new Set(shownGroups.flatMap((g) => g.docs.map((d) => d.source.id)))
  const selection = list.filter((s) => picked.has(s.id))
  const requirementCount = summary.data?.requirements ?? project?.requirements ?? 0
  const busy = running || removeSource.isPending || clearSources.isPending
  const isOpen = (key: string, fallback: boolean) => closed[key] === undefined ? fallback : !closed[key]
  const toggle = (key: string, fallback: boolean) => setClosed((c) => ({ ...c, [key]: isOpen(key, fallback) }))

  // one last refresh of the numbers when the queue has finished
  useEffect(() => {
    if (finished) {
      void qc.invalidateQueries({ queryKey: ['summary'] })
      void qc.invalidateQueries({ queryKey: ['requirements'] })
      void qc.invalidateQueries({ queryKey: ['overview'] })
      void qc.invalidateQueries({ queryKey: ['sources'] })
    }
  }, [finished, qc])

  const runAll = (p: Policy) =>
    analyze.mutate(p, {
      onSuccess: (j) => {
        setJobId(j.job_id)
        setStale(false)
        toasts.push(copy.sources.runDone[j.policy ?? p], 'success')
      },
      onError: (e) => toasts.push(e.message, 'error'),
    })
  const analyseOne = async (s: Source, p: Policy) => {
    setWorkingOn(s.id)
    try {
      const r = await reanalyze.mutateAsync({ sourceId: s.id, policy: p })
      if (r.job) setJobId(r.job.job_id)
      setStale(false)
      toasts.push(r.kept + r.changed + r.removed > 0 ? copy.sources.reanalysed(r.kept, r.changed, r.removed, r.added) : copy.sources.analysedOne(s.filename), 'success')
    } catch (e) {
      toasts.push(copy.sources.analyseFailed((e as Error).message), 'error')
    } finally {
      setWorkingOn(null)
    }
  }
  /** The analysis always asks which drafts to write first; the answer is remembered. */
  const confirmAnalyse = async (p: Policy) => {
    if (dialog?.kind !== 'analyse') return
    const { sources: chosen, all } = dialog
    setPolicy(p)
    setDialog(null)
    if (all) return runAll(p)
    for (const s of chosen) await analyseOne(s, p)
    setPicked(new Set())
  }
  const askAnalyse = (chosen: Source[], all = false) => setDialog({ kind: 'analyse', sources: chosen, all, again: chosen.length === 1 && !needsAnalysis(chosen[0]!) })
  const toggle_ = (id: number) =>
    setPicked((old) => {
      const next = new Set(old)
      if (!next.delete(id)) next.add(id)
      return next
    })
  return (
    <div className="space-y-3" role="tabpanel" id="tab-sources-panel" aria-labelledby="tab-sources">
      <JiraActions pid={pid} variant="row" />
      <DraftsStatus pid={pid} />
      <section className="c1-card p-4" aria-label={copy.sources.listTitle} data-testid="sources-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="mr-1 text-sm font-semibold text-heading">{copy.sources.listCount(list.length)}</h2>
            <button type="button" className="c1-btn-secondary" disabled={pid === undefined} onClick={() => setDialog({ kind: 'upload' })} data-testid="upload-button">
              <CloudUpload size={15} aria-hidden="true" /> {copy.sources.uploadAction}
            </button>
            {list.length > 0 && (
              <button
                type="button"
                className="text-xs font-medium text-primary underline-offset-2 hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
                disabled={busy}
                title={busy ? copy.sources.busyHint : copy.sources.clearHint}
                onClick={() => setDialog({ kind: 'clear' })}
              >
                {copy.sources.clearAll}
              </button>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <AnalysisBadge state={jobBadge(job.data, finished, analyze.isPending, requirementCount, stale)} />
            <button
              type="button"
              className="c1-btn-primary"
              data-testid="analyse-pending"
              disabled={pending.length === 0 || running}
              aria-busy={analyze.isPending}
              title={running ? copy.sources.runningHint : list.length === 0 ? copy.sources.needFile : pending.length === 0 ? copy.sources.allAnalysed : undefined}
              onClick={() => askAnalyse(pending, true)}
            >
              {analyze.isPending ? <Spinner className="h-3.5 w-3.5" /> : <Sparkles size={14} aria-hidden="true" />} {analyze.isPending ? copy.sources.analysingShort : copy.sources.analyseN(pending.length)}
            </button>
          </div>
        </div>

        {sources.isLoading ? (
          <Skeleton className="mt-3 h-10 w-full" />
        ) : list.length === 0 ? (
          <p className="mt-3 text-xs text-body">{copy.sources.empty}</p>
        ) : (
          <div className="mt-3 space-y-2" data-testid="source-groups">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2" data-testid="sources-bar">
              <label className="flex items-center gap-2 text-xs text-secondary-text">
                {copy.sources.viewSprint}
                <select value={viewKey ?? ''} onChange={(e) => setViewing(e.target.value)} data-testid="sprint-view" className="rounded-lg border border-border bg-white px-2 py-1 text-xs text-heading">
                  {groups.map((g) => (
                    <option key={g.key} value={g.key}>
                      {copy.sources.viewOption(g.sprint ? g.sprint.name : copy.plan.unassigned, !!g.sprint?.is_current, g.docs.length)}
                    </option>
                  ))}
                </select>
              </label>
              {shownIds.size > 0 && (
                <>
                  <button type="button" className="text-xs font-medium text-primary underline-offset-2 hover:underline" data-testid="select-docs" onClick={() => setPicked(new Set(shownIds))}>
                    {copy.sources.selectAll}
                  </button>
                  {picked.size > 0 && (
                    <>
                      <span className="text-xs font-medium text-heading" data-testid="docs-selected">
                        {copy.sources.selectedCount(picked.size)}
                      </span>
                      <button type="button" className="text-xs font-medium text-primary underline-offset-2 hover:underline" data-testid="clear-docs" onClick={() => setPicked(new Set())}>
                        {copy.sources.clearSelection}
                      </button>
                      <button type="button" className="c1-btn-primary !px-3 !py-1" disabled={running} data-testid="analyse-selected" onClick={() => askAnalyse(selection)}>
                        <Sparkles size={13} aria-hidden="true" /> {copy.sources.analyseSelected(selection.length)}
                      </button>
                    </>
                  )}
                </>
              )}
            </div>
            {shownGroups.map((g) => {
              const sprint = g.sprint
              const name = sprint ? sprint.name : copy.plan.unassigned
              const open = isOpen(g.key, true)
              const upload = (
                <button type="button" className="c1-btn-secondary !px-2.5 !py-1" aria-label={copy.sources.uploadHereLabel(name)} data-testid="upload-here" disabled={busy} onClick={() => setDialog({ kind: 'upload', sprintId: sprint!.id })}>
                  <CloudUpload size={13} aria-hidden="true" /> {copy.sources.uploadHere}
                </button>
              )
              return (
                <section key={g.key} className="overflow-hidden rounded-lg border border-border" data-testid="sprint-group" data-current={!!sprint?.is_current} aria-label={name}>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 bg-primary-light/50 px-3 py-2" data-testid="sprint-heading">
                    <button type="button" className="flex min-w-0 items-center gap-1.5 text-xs font-semibold text-heading" aria-expanded={open} aria-label={copy.sources.groupToggle(name)} onClick={() => toggle(g.key, true)}>
                      <ChevronRight size={14} className={`shrink-0 transition-transform ${open ? 'rotate-90' : ''}`} aria-hidden="true" />
                      <span className="truncate">{name}</span>
                    </button>
                    {sprint?.is_current && <Badge>{copy.plan.current}</Badge>}
                    {sprint && (sprint.start_date || sprint.end_date) && <span className="text-[11px] text-secondary-text">{copy.plan.dates(sprint.start_date, sprint.end_date)}</span>}
                    <span className="text-[11px] text-secondary-text">{copy.sources.groupCount(g.docs.length)}</span>
                    {sprint && sprint.origin === 'detected' && !sprint.confirmed && (
                      <span className="flex items-center gap-1.5 text-[11px] text-blue-800" data-testid="detected-sprint">
                        {copy.plan.detected} ·{' '}
                        <button type="button" className="font-semibold underline-offset-2 hover:underline" onClick={() => updateSprint.mutate({ id: sprint.id, confirmed: true }, { onSuccess: () => toasts.push(copy.plan.confirmed(sprint.name), 'success'), onError: (e) => toasts.push(copy.plan.saveFailed(e.message), 'error') })}>
                          {copy.plan.confirm}
                        </button>
                      </span>
                    )}
                    <span className="ml-auto flex items-center gap-1">
                      {sprint && g.docs.length > 0 && upload}
                      {sprint && (
                        <button type="button" className="rounded p-1 text-muted hover:bg-white hover:text-heading" aria-label={copy.plan.editSprint(sprint.name)} onClick={() => setDialog({ kind: 'sprint', sprint })}>
                          <Pencil size={12} aria-hidden="true" />
                        </button>
                      )}
                    </span>
                  </div>
                  {open &&
                    (g.docs.length === 0 ? (
                      <div className="flex flex-wrap items-center gap-3 border-t border-border px-3 py-3" data-testid="empty-sprint">
                        <p className="text-[11.5px] text-secondary-text">{copy.sources.noDocsYet}</p>
                        {sprint && upload}
                      </div>
                    ) : (
                      <ul className="divide-y divide-border border-t border-border">
                        {g.docs.map((d) => (
                          <SourceCard
                            key={d.source.id}
                            source={d.source}
                            count={sprint ? d.count : null}
                            sprints={sprintList}
                            busy={busy}
                            working={workingOn === d.source.id}
                            onAnalyse={() => askAnalyse([d.source])}
                            onReanalyse={() => askAnalyse([d.source])}
                            selected={picked.has(d.source.id)}
                            onToggle={() => toggle_(d.source.id)}
                            onMove={() => setDialog({ kind: 'move', source: d.source })}
                            onRemove={() => setDialog({ kind: 'remove', source: d.source })}
                          />
                        ))}
                      </ul>
                    ))}
                </section>
              )
            })}
          </div>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button type="button" className="c1-btn-secondary" disabled={pid === undefined} onClick={() => setDialog({ kind: 'next-sprint' })} data-testid="add-next-sprint">
            <Plus size={14} aria-hidden="true" /> {copy.sources.addNextSprint}
          </button>
          {shownSprint && (
            <button type="button" className="c1-btn-secondary" onClick={() => setDialog({ kind: 'sprint', sprint: shownSprint })} data-testid="edit-sprint">
              <Pencil size={14} aria-hidden="true" /> {copy.sources.editSprintDetails}
            </button>
          )}
        </div>
      </section>

      {(analyze.isPending || reanalyze.isPending) && <AnalyzingNotice />}
      {analyze.isError && !analyze.isPending && <AnalyzeError message={analyze.error.message} onRetry={() => runAll(policy)} />}

      {pid !== undefined && dialog?.kind === 'upload' && <UploadDialog key={dialog.sprintId ?? 'auto'} pid={pid} sprints={sprintList} sprintId={dialog.sprintId} onClose={() => setDialog(null)} />}
      {pid !== undefined && dialog?.kind === 'sprint' && <SprintDialog pid={pid} sprint={dialog.sprint} sprints={sprintList} defaultName={nextSprintName(sprintList)} onClose={() => setDialog(null)} />}
      {pid !== undefined && dialog?.kind === 'next-sprint' && (
        <SprintDialog pid={pid} sprints={sprintList} defaultName={nextSprintName(sprintList)} onCreated={(sprint) => {
            setViewing(`sprint-${sprint.id}`)
            setDialog({ kind: 'sprint-created', sprint })
          }} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === 'sprint-created' && (
        <NextSprintCreated sprint={dialog.sprint} canMove={list.length > 0} onUpload={() => setDialog({ kind: 'upload', sprintId: dialog.sprint.id })} onMove={() => setDialog({ kind: 'move-documents', sprint: dialog.sprint })} onClose={() => setDialog(null)} />
      )}
      {pid !== undefined && dialog?.kind === 'move-documents' && <MoveDocumentsDialog pid={pid} sprint={dialog.sprint} sources={list} onClose={() => setDialog(null)} />}
      {pid !== undefined && dialog?.kind === 'move' && <MoveDialog pid={pid} source={dialog.source} sprints={sprintList} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'analyse' && <AnalyseDialog names={dialog.sources.map((x) => x.filename)} again={dialog.again} policy={policy} onCancel={() => setDialog(null)} onConfirm={(p) => void confirmAnalyse(p)} />}
      {dialog?.kind === 'clear' && (
        <ConfirmDialog
          title={copy.sources.clearTitle}
          message={copy.sources.clearMessage}
          confirmLabel={copy.sources.clearAll}
          danger
          busy={clearSources.isPending}
          onCancel={() => setDialog(null)}
          onConfirm={() =>
            clearSources.mutate(undefined, {
              onSuccess: () => {
                setDialog(null)
                toasts.push(copy.sources.cleared, 'success')
              },
              onError: (e) => {
                setDialog(null)
                toasts.push(copy.sources.clearFailed(e.message), 'error')
              },
            })
          }
        />
      )}
      {dialog?.kind === 'remove' && (
        <ConfirmDialog
          title={copy.sources.removeTitle(dialog.source.filename)}
          message={copy.sources.removeMessage}
          confirmLabel={copy.sources.remove}
          danger
          busy={removeSource.isPending}
          onCancel={() => setDialog(null)}
          onConfirm={() =>
            removeSource.mutate(dialog.source.id, {
              onSuccess: () => {
                setDialog(null)
                toasts.push(copy.sources.removed, 'success')
              },
              onError: (e) => {
                setDialog(null)
                toasts.push(copy.sources.removeFailed(e.message), 'error')
              },
            })
          }
        />
      )}
    </div>
  )
}

// ------------------------------------------------------------------------------------------------------------------ findings tab
function FindingItem({ row }: { row: RequirementRow }) {
  const kind = primaryType(row.flags)
  const { icon: Icon, tint } = TYPE_ICON[kind]
  return (
    <li data-testid="finding-item" className="flex items-start gap-3 border-b border-border px-4 py-3 last:border-b-0">
      <Icon size={19} className={`mt-0.5 shrink-0 ${tint}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-bold text-primary">{row.id}</span>
          <span className="text-secondary-text">{TYPE_LABEL[kind]}</span>
          {row.generation_state === 'needs_clarification' && <AiClarifyBadge />}
        </div>
        <p className="mt-0.5 line-clamp-2 text-[13px] leading-snug text-heading">{row.text}</p>
        <p className="mt-1 truncate text-[10.5px] text-muted">{sourceLabel(row.source_file, row.page, row.paragraph)}</p>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1.5">
        <RiskBadge level={row.risk_level} />
        <Link to={`/requirement/review?uid=${encodeURIComponent(row.uid)}`} className="text-[11.5px] font-medium text-primary underline-offset-2 hover:underline" aria-label={copy.findings.openLabel(row.id)}>
          {copy.findings.open}
        </Link>
      </div>
    </li>
  )
}

function FindingsTab({ view, onView }: { view: View; onView: (v: View) => void }) {
  const { project } = useModule()
  const pid = project?.id
  const sources = useSources(pid)
  const [text, setText] = useState('')
  const [q, setQ] = useState('')
  const [risk, setRisk] = useState<RiskFilter>('all')
  const [file, setFile] = useState('all')

  useEffect(() => {
    if (text === q) return
    const id = window.setTimeout(() => setQ(text), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(id)
  }, [text, q])

  const filters = useMemo(() => ({ risk, type: VIEW_TYPE[view], q }), [risk, view, q])
  const list = useRequirementList(pid, filters, 500)
  const all = list.data?.pages.flatMap((p) => p.items) ?? []
  const total = list.data?.pages[0]?.total ?? 0
  const rows = all
    .filter((r) => (file === 'all' || r.source_file === file) && (view !== 'risk' || risk !== 'all' || r.risk_level !== 'NONE'))
    .sort((a, b) => (view === 'risk' ? (RISK_ORDER[b.risk_level]! - RISK_ORDER[a.risk_level]! || b.risk_score - a.risk_score) : 0))
  const files = Array.from(new Set((sources.data ?? []).map((s) => s.filename)))

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = VIEWS.indexOf(view)
    if (e.key === 'ArrowRight') onView(VIEWS[(i + 1) % VIEWS.length]!)
    else if (e.key === 'ArrowLeft') onView(VIEWS[(i + VIEWS.length - 1) % VIEWS.length]!)
    else return
    e.preventDefault()
    window.setTimeout(() => document.getElementById(`view-${VIEWS[(i + (e.key === 'ArrowRight' ? 1 : VIEWS.length - 1)) % VIEWS.length]}`)?.focus(), 0)
  }

  return (
    <div className="c1-card" role="tabpanel" id="tab-findings-panel" aria-labelledby="tab-findings">
      <div className="border-b border-border p-4">
        <div role="radiogroup" aria-label={copy.findings.viewLabel} onKeyDown={onKey} className="inline-flex flex-wrap overflow-hidden rounded-lg border border-border">
          {VIEWS.map((v, i) => (
            <button
              key={v}
              id={`view-${v}`}
              type="button"
              role="radio"
              aria-checked={view === v}
              tabIndex={view === v ? 0 : -1}
              onClick={() => onView(v)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${i > 0 ? 'border-l border-border' : ''} ${view === v ? 'bg-primary text-white' : 'bg-white text-heading hover:bg-primary-light'}`}
            >
              {copy.findings.view[v]}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-secondary-text">{copy.findings.hint[view]}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <label className="relative min-w-[180px] flex-1">
            <span className="sr-only">{copy.findings.search}</span>
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden="true" />
            <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder={copy.findings.search} className="w-full rounded-lg border border-border bg-secondary-bg py-1.5 pl-9 pr-3 text-xs text-heading placeholder:text-muted" />
          </label>
          <label>
            <span className="sr-only">{copy.findings.riskFilter}</span>
            <select value={risk} onChange={(e) => setRisk(e.target.value as RiskFilter)} className="rounded-lg border border-border bg-secondary-bg px-2.5 py-1.5 text-xs text-heading">
              <option value="all">{copy.findings.allRisks}</option>
              <option value="HIGH">{copy.common.risk.HIGH}</option>
              <option value="MEDIUM">{copy.common.risk.MEDIUM}</option>
              <option value="LOW">{copy.common.risk.LOW}</option>
              {view !== 'risk' && <option value="NONE">{copy.common.risk.NONE}</option>}
            </select>
          </label>
          <label>
            <span className="sr-only">{copy.findings.fileFilter}</span>
            <select value={file} onChange={(e) => setFile(e.target.value)} className="max-w-[220px] rounded-lg border border-border bg-secondary-bg px-2.5 py-1.5 text-xs text-heading">
              <option value="all">{copy.findings.allFiles}</option>
              {files.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {list.isError ? (
        <div role="alert" className="m-4 rounded-lg border border-danger-border bg-danger-bg p-3 text-xs text-danger-text">
          {(list.error as Error).message}
        </div>
      ) : list.isLoading ? (
        <div className="space-y-3 p-4" aria-busy="true" aria-label={copy.common.loading}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="px-4 py-10 text-center text-xs text-secondary-text" data-testid="empty-findings">
          {copy.findings.empty[view]}
        </div>
      ) : (
        <>
          <ul aria-label={copy.findings.view[view]} data-testid="findings-list">
            {rows.map((r) => (
              <FindingItem key={r.uid} row={r} />
            ))}
          </ul>
          <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-2.5 text-xs text-secondary-text">
            <span>{copy.findings.showing(rows.length, total)}</span>
            {list.hasNextPage && (
              <button type="button" className="rounded-md border border-border px-3 py-1 font-medium text-heading hover:bg-primary-light disabled:opacity-50" disabled={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
                {list.isFetchingNextPage ? copy.common.loading : copy.common.showMore}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ------------------------------------------------------------------------------------------------------------------ page
/** Two tabs: Sources (add documents, run the analysis) and Findings (ambiguities, duplicates, conflicts and risk across the whole document). */
export function SourcesFindingsPage() {
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'findings' ? 'findings' : 'sources'
  const viewParam = params.get('view') as View | null
  const view: View = viewParam && VIEWS.includes(viewParam) ? viewParam : 'ambiguities'
  const setTab = (t: Tab) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        next.set('tab', t)
        return next
      },
      { replace: true },
    )
  const setView = (v: View) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        next.set('tab', 'findings')
        next.set('view', v)
        return next
      },
      { replace: true },
    )
  const onTabKey = (e: KeyboardEvent) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End') return
    e.preventDefault()
    const next: Tab = tab === 'sources' ? 'findings' : 'sources'
    setTab(next)
    window.setTimeout(() => document.getElementById(`tab-${next}`)?.focus(), 0)
  }
  const tabClass = (active: boolean) => `-mb-px border-b-2 px-4 py-2 text-xs font-medium transition-colors ${active ? 'border-primary text-primary' : 'border-transparent text-secondary-text hover:text-heading'}`
  return (
    <div className="space-y-3">
      <div role="tablist" aria-label={copy.pages.sources.title} onKeyDown={onTabKey} className="flex border-b border-border">
        <button id="tab-sources" type="button" role="tab" aria-selected={tab === 'sources'} aria-controls="tab-sources-panel" tabIndex={tab === 'sources' ? 0 : -1} className={tabClass(tab === 'sources')} onClick={() => setTab('sources')}>
          {copy.sources.tabSources}
        </button>
        <button id="tab-findings" type="button" role="tab" aria-selected={tab === 'findings'} aria-controls="tab-findings-panel" tabIndex={tab === 'findings' ? 0 : -1} className={tabClass(tab === 'findings')} onClick={() => setTab('findings')}>
          {copy.sources.tabFindings}
        </button>
      </div>
      {tab === 'sources' ? <SourcesTab /> : <FindingsTab view={view} onView={setView} />}
    </div>
  )
}
