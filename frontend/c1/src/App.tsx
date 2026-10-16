import { useQueryClient } from '@tanstack/react-query'
import { WifiOff } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiClientError } from './api/client'
import {
  isJobFinished, useAnalyze, useClearSources, useDeleteSource, useGenerateRemaining, useHealth, useJob, usePauseGeneration, useProjects, useRequirementList, useSources, useSummary, useUpload,
} from './api/hooks'
import type { FindingType, ListFilters, Policy } from './api/types'
import { DetailPanel } from './components/DetailPanel'
import { FindingsPanel } from './components/FindingsPanel'
import { Header } from './components/Header'
import { Sidebar } from './components/Sidebar'
import { DraftProgress } from './components/DraftProgress'
import { StatCards } from './components/StatCards'
import { AnalyzeError, AnalyzingNotice, Banners, PipelineStrip, SourcesCard, TitleBlock, jobBadge } from './components/TopSection'
import { ALLOWED_EXTENSIONS, API_BASE, MAX_UPLOAD_BYTES } from './config'
import { useToasts } from './context/Toasts'

const isNetwork = (e: unknown) => e instanceof ApiClientError && e.status === 0

const POLICY_KEY = 'c1.draftPolicy'
function loadPolicy(): Policy {
  try {
    const v = window.localStorage.getItem(POLICY_KEY)
    return v === 'all' || v === 'manual' || v === 'smart' ? v : 'smart'
  } catch {
    return 'smart' // storage can be blocked: the default is fine
  }
}

const RUN_TOAST: Record<Policy, string> = {
  smart: 'Part A finished. Drafts for the important requirements are being written.',
  all: 'Part A finished. Task drafts are being generated.',
  manual: 'Part A finished. No drafts were queued: use Generate draft on a requirement.',
}

export default function App() {
  const qc = useQueryClient()
  const toasts = useToasts()
  const health = useHealth()
  const projects = useProjects()
  const project = projects.data?.[0]
  const pid = project?.id
  const sources = useSources(pid)
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob(jobId)
  const finished = isJobFinished(job.data)
  const summary = useSummary(pid)
  const drafts = summary.data?.task_drafts
  // drafts are being written: the saved queue (also after a reload) or the job just started; a paused queue is not "running"
  const generating = !drafts?.paused && ((drafts?.in_progress ?? 0) > 0 || (!!job.data && job.data.generation.queued > 0))
  const [policy, setPolicy] = useState<Policy>(loadPolicy)
  const onPolicy = (p: Policy) => {
    setPolicy(p)
    try {
      window.localStorage.setItem(POLICY_KEY, p)
    } catch {
      /* not saved, still applied for this page */
    }
  }
  const pauseGeneration = usePauseGeneration(pid)
  const generateRemaining = useGenerateRemaining(pid)
  const [filters, setFilters] = useState<ListFilters>({ risk: 'all', type: 'all', q: '' })
  const list = useRequirementList(pid, filters)
  const [selected, setSelected] = useState<string | null>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const upload = useUpload(pid)
  const analyze = useAnalyze(pid)
  const [stale, setStale] = useState(false)
  const removeSource = useDeleteSource(pid, () => setSelected(null))
  const clearSources = useClearSources(pid, () => {
    setSelected(null)
    setJobId(null)
    setStale(false)
  })

  const rows = list.data?.pages.flatMap((p) => p.items) ?? []
  const total = list.data?.pages[0]?.total ?? 0
  // without a choice the first row is shown, but not while the list is being refreshed: its rows may belong to a source that was just removed
  const activeUid = selected ?? (list.isFetching ? null : (rows[0]?.uid ?? null))
  const unreachable = isNetwork(projects.error) || isNetwork(health.error)
  const sourceList = sources.data ?? []
  const requirementCount = summary.data?.requirements ?? project?.requirements ?? 0
  const running = analyze.isPending || generating
  const analysisExists = requirementCount > 0 || !!job.data
  const mode = running ? 'running' : analysisExists && sourceList.length > 0 ? 'complete' : 'idle'

  // one last refresh of the numbers when the queue has finished
  useEffect(() => {
    if (finished) {
      void qc.invalidateQueries({ queryKey: ['summary'] })
      void qc.invalidateQueries({ queryKey: ['requirements'] })
    }
  }, [finished, qc])

  const onFilters = useCallback((f: ListFilters) => setFilters(f), [])

  const onFiles = (files: File[]) => {
    const ok: File[] = []
    for (const f of files) {
      const ext = f.name.includes('.') ? '.' + f.name.split('.').pop()!.toLowerCase() : ''
      if (!(ALLOWED_EXTENSIONS as readonly string[]).includes(ext)) toasts.push(`${f.name}: file type ${ext || '(none)'} is not allowed. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}.`, 'error')
      else if (f.size > MAX_UPLOAD_BYTES) toasts.push(`${f.name}: larger than the ${MAX_UPLOAD_BYTES / (1024 * 1024)} MB limit.`, 'error')
      else ok.push(f)
    }
    if (!ok.length || pid === undefined) return
    upload.mutate(ok, {
      onSuccess: (r) => {
        r.rejected.forEach((x) => toasts.push(x.message, 'error'))
        if (r.accepted.length && analysisExists) setStale(true)
        if (r.accepted.length) toasts.push(`${r.accepted.length} ${r.accepted.length === 1 ? 'file' : 'files'} added. Choose “Run analysis” to analyse them.`, 'success')
      },
      onError: (e) => toasts.push(e.message, 'error'),
    })
  }

  const onRun = () =>
    analyze.mutate(policy, {
      onSuccess: (j) => {
        setJobId(j.job_id)
        setSelected(null)
        setStale(false)
        toasts.push(RUN_TOAST[j.policy ?? policy], 'success')
      },
      onError: (e) => toasts.push(e.message, 'error'),
    })

  const onPause = (pause: boolean) =>
    pauseGeneration.mutate(pause, { onError: (e) => toasts.push(`Could not ${pause ? 'pause' : 'resume'} the drafts: ${e.message}`, 'error') })
  const onGenerateAll = () =>
    generateRemaining.mutate(undefined, {
      onSuccess: (r) => toasts.push(r.queued > 0 ? `${r.queued} drafts queued.` : 'Every requirement already has a draft or is queued.', 'success'),
      onError: (e) => toasts.push(`Could not queue the drafts: ${e.message}`, 'error'),
    })

  const onCard = (type: FindingType) => setFilters((f) => ({ ...f, type }))

  const onRemove = (sourceId: number) =>
    removeSource.mutate(sourceId, {
      onSuccess: () => toasts.push('Source removed together with its requirements and results.', 'success'),
      onError: (e) => toasts.push(`Could not remove the source: ${e.message}`, 'error'),
    })
  const onClear = () =>
    clearSources.mutate(undefined, {
      onSuccess: () => toasts.push('All sources and results were cleared.', 'success'),
      onError: (e) => toasts.push(`Could not clear the sources: ${e.message}`, 'error'),
    })
  const retry = () => {
    void qc.invalidateQueries()
  }

  return (
    <div className="flex min-h-screen">
      <div className="sticky top-0 h-screen shrink-0">
        <Sidebar project={project} health={health.data} healthError={isNetwork(health.error) || health.isError} />
      </div>
      <main className="min-w-0 flex-1" aria-label="Requirement intelligence">
        <Header health={health.data} unreachable={unreachable || health.isError} projectId={pid} canExport={(summary.data?.requirements ?? 0) > 0} />

        {unreachable && (
          <div role="alert" className="mx-6 mt-5 flex flex-wrap items-center gap-3 rounded-card border border-risk-highLine bg-risk-highBg px-5 py-3.5 text-[13px] text-risk-highText xl:mx-9" data-testid="offline-banner">
            <WifiOff size={18} aria-hidden="true" />
            <span className="flex-1">
              Cannot reach the Component 1 API at <strong>{API_BASE}</strong>. Start the backend and try again.
            </span>
            <button type="button" className="rounded-md border border-risk-highLine bg-white px-3 py-1.5 font-semibold hover:bg-red-50" onClick={retry}>
              Retry
            </button>
          </div>
        )}

        <TitleBlock onFiles={onFiles} onRun={onRun} canRun={sourceList.length > 0 && !running} running={analyze.isPending} policy={policy} onPolicy={onPolicy} />
        {analyze.isPending && <AnalyzingNotice />}
        {analyze.isError && !analyze.isPending && <AnalyzeError message={analyze.error.message} onRetry={onRun} />}
        <SourcesCard
          sources={sourceList}
          loading={sources.isLoading}
          badge={jobBadge(job.data, finished, analyze.isPending, requirementCount, stale)}
          onFiles={onFiles}
          busy={running || removeSource.isPending || clearSources.isPending}
          onRemove={onRemove}
          onClear={onClear}
        />
        <PipelineStrip mode={mode} stage={analyze.isPending ? 'collect' : (job.data?.stage ?? null)} />
        <Banners />
        <StatCards summary={summary.data} loading={summary.isLoading} active={filters.type} onSelect={onCard} />
        <DraftProgress
          drafts={drafts}
          onPause={() => onPause(true)}
          onResume={() => onPause(false)}
          onGenerateAll={onGenerateAll}
          busy={pauseGeneration.isPending || generateRemaining.isPending}
          analysing={analyze.isPending}
        />

        <div className="card mx-6 mb-10 mt-5 grid overflow-hidden xl:mx-9 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]" data-testid="workspace">
          <div className="border-line xl:border-r">
            <FindingsPanel
              filters={filters}
              onFilters={onFilters}
              rows={rows}
              total={total}
              open={summary.data?.open_findings}
              loading={list.isLoading || (pid === undefined && !projects.isError)}
              error={list.isError && !isNetwork(list.error) ? (list.error as Error).message : null}
              hasSources={sourceList.length > 0}
              selectedUid={activeUid}
              onSelect={setSelected}
              onOpen={() => headingRef.current?.focus()}
              onMore={() => void list.fetchNextPage()}
              hasMore={!!list.hasNextPage}
              loadingMore={list.isFetchingNextPage}
            />
          </div>
          <div className="min-w-0 border-t border-line xl:border-t-0">
            <DetailPanel uid={activeUid} projectId={pid} headingRef={headingRef} waiting={list.isFetching && selected === null} />
          </div>
        </div>
      </main>
    </div>
  )
}
