import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { DRAFT_POLL_MS, HEALTH_POLL_MS, JOB_POLL_MS, PAGE_SIZE, SYNC_POLL_MS, limits } from '../config'
import { isGenerating } from '../lib/format'
import { ApiClientError, api } from './client'
import type { AssignRangesResult, JiraImportInput, JiraImportResult, DecisionIn, DecisionOut, Engine, EngineTarget, EngineTestResult, EngineUpdate, GenerateOut, Job, ListFilters, PageRange, Phase, Policy, Project, PublishResult, ReanalyzeResult, RequirementDetail, RequirementList, SourceType, Sprint, SprintDeleted, SprintInput, UploadResult } from './types'

export const keys = {
  health: ['health'] as const,
  engine: ['engine'] as const,
  projects: ['projects'] as const,
  overview: (pid: number) => ['overview', pid] as const,
  sources: (pid: number) => ['sources', pid] as const,
  summary: (pid: number) => ['summary', pid] as const,
  list: (pid: number, f: ListFilters) => ['requirements', pid, f.risk, f.type, f.q, f.sprint ?? null] as const,
  listAll: (pid: number) => ['requirements', pid] as const,
  detail: (uid: string) => ['requirement', uid] as const,
  job: (id: string) => ['job', id] as const,
  phases: (pid: number) => ['phases', pid] as const,
  sprints: (pid: number) => ['sprints', pid] as const,
  jira: (pid: number) => ['jira', pid] as const,
}

type Client = ReturnType<typeof useQueryClient>

/** Everything that shows counts of a project: the numbers on the overview, the project list and the summary. */
function refreshCounts(qc: Client, pid?: number) {
  void qc.invalidateQueries({ queryKey: pid === undefined ? ['summary'] : keys.summary(pid) })
  void qc.invalidateQueries({ queryKey: pid === undefined ? ['overview'] : keys.overview(pid) })
  void qc.invalidateQueries({ queryKey: keys.projects })
}

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.health, refetchInterval: HEALTH_POLL_MS, retry: false })

export const useEngine = () => useQuery({ queryKey: keys.engine, queryFn: api.engine, refetchInterval: HEALTH_POLL_MS, retry: false })

/** Change the processing target or the cloud settings (partial update). The answer is the new engine state; health, drafts and ETA follow it. */
export function useUpdateEngine() {
  const qc = useQueryClient()
  return useMutation<Engine, Error, EngineUpdate>({
    mutationFn: (body) => api.updateEngine(body),
    onSuccess: (engine) => {
      qc.setQueryData(keys.engine, engine)
      void qc.invalidateQueries({ queryKey: keys.health })
      void qc.invalidateQueries({ queryKey: ['summary'] })
      void qc.invalidateQueries({ queryKey: ['overview'] })
    },
  })
}

/** Test the connection (the saved settings, not the form). A failed test is a normal answer with ok = false. */
export function useTestEngine() {
  const qc = useQueryClient()
  return useMutation<EngineTestResult, Error, EngineTarget>({
    mutationFn: (target) => api.testEngine(target),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: keys.engine })
      void qc.invalidateQueries({ queryKey: keys.health })
    },
  })
}

/** Projects that are not archived (the switcher also offers archived ones when asked). */
export const useProjects = (includeArchived = false) =>
  useQuery({ queryKey: [...keys.projects, includeArchived] as const, queryFn: () => api.projects(includeArchived), retry: false })

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation<Project, Error, string>({ mutationFn: (name) => api.createProject(name), onSuccess: () => void qc.invalidateQueries({ queryKey: keys.projects }) })
}

export function useRenameProject() {
  const qc = useQueryClient()
  return useMutation<Project, Error, { pid: number; name: string }>({
    mutationFn: ({ pid, name }) => api.renameProject(pid, name),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.projects })
      void qc.invalidateQueries({ queryKey: ['overview'] })
    },
  })
}

export function useArchiveProject() {
  const qc = useQueryClient()
  return useMutation<Project, Error, number>({ mutationFn: (pid) => api.archiveProject(pid), onSuccess: () => void qc.invalidateQueries({ queryKey: keys.projects }) })
}

export function useUnarchiveProject() {
  const qc = useQueryClient()
  return useMutation<Project, Error, number>({ mutationFn: (pid) => api.unarchiveProject(pid), onSuccess: () => void qc.invalidateQueries({ queryKey: keys.projects }) })
}

/** One call for the overview page; refreshed every 2 s while drafts are being written. */
export const useOverview = (pid: number | undefined) =>
  useQuery({
    queryKey: keys.overview(pid ?? 0),
    queryFn: () => api.overview(pid!),
    enabled: pid !== undefined,
    retry: false,
    refetchInterval: (q) => {
      if ((q.state.data?.generation.in_progress ?? 0) > 0) return JOB_POLL_MS
      const sync = q.state.data?.sync
      return sync?.enabled && ['pending', 'syncing', 'retrying', 'unreachable'].includes(sync.state) ? SYNC_POLL_MS : false
    },
  })

/** Hand the accepted and edited requirements on. A project is always published under its own key, so no body is sent. */
export function usePublish(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<PublishResult, Error, void>({
    mutationFn: () => api.publish(pid!),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: keys.overview(pid ?? 0) })
      void qc.invalidateQueries({ queryKey: keys.projects })
    },
  })
}

export const useSources = (pid: number | undefined) =>
  useQuery({ queryKey: keys.sources(pid ?? 0), queryFn: () => api.sources(pid!), enabled: pid !== undefined, retry: false })

/** Refresh the numbers every 2 s while drafts are queued or running (also after a reload: the queue is saved by the service) or when `live` is set. */
export const useSummary = (pid: number | undefined, live = false) =>
  useQuery({
    queryKey: keys.summary(pid ?? 0),
    queryFn: () => api.summary(pid!),
    enabled: pid !== undefined,
    retry: false,
    refetchInterval: (q) => (live || (q.state.data?.task_drafts.in_progress ?? 0) > 0 ? JOB_POLL_MS : false),
  })

export const isJobFinished = (job: Job | undefined) => !!job && (job.stage === 'share' || !!job.error) && job.generation.queued === 0

/** Polls the job every 2 s until the analysis is done and the draft queue is empty. */
export const useJob = (jobId: string | null) =>
  useQuery({
    queryKey: keys.job(jobId ?? ''),
    queryFn: () => api.job(jobId!),
    enabled: !!jobId,
    retry: false,
    refetchInterval: (q) => (isJobFinished(q.state.data) ? false : JOB_POLL_MS),
  })

/** The requirements of a project, `pageSize` at a time (the default is one page for most projects; the service allows up to 500). */
export function useRequirementList(pid: number | undefined, filters: ListFilters, pageSize = PAGE_SIZE) {
  return useInfiniteQuery({
    queryKey: [...keys.list(pid ?? 0, filters), pageSize] as const,
    queryFn: ({ pageParam }) => api.requirements(pid!, filters, pageSize, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last: RequirementList) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
    enabled: pid !== undefined,
    retry: false,
    placeholderData: keepPreviousData,
  })
}

/** One requirement; refreshed every 1.5 s while its draft is queued or running. */
export const useRequirement = (uid: string | null) =>
  useQuery({
    queryKey: keys.detail(uid ?? ''),
    queryFn: () => api.requirement(uid!),
    enabled: !!uid,
    retry: false,
    refetchInterval: (q) => (q.state.data && isGenerating(q.state.data.generation.state) ? DRAFT_POLL_MS : false),
  })

export function useGenerate() {
  const qc = useQueryClient()
  return useMutation<GenerateOut, Error, string>({
    mutationFn: (uid: string) => api.generate(uid),
    onSuccess: (data, uid) => {
      // the service answers "queued", or the state of a cached reply that was applied at once
      qc.setQueryData<RequirementDetail>(keys.detail(uid), (d) => (d ? { ...d, generation: { ...d.generation, state: data.generation_state, message: '' } } : d))
      void qc.invalidateQueries({ queryKey: keys.detail(uid) })
      void qc.invalidateQueries({ queryKey: ['requirements'] })
      refreshCounts(qc)
    },
  })
}

type DecisionVars = { uid: string; body: DecisionIn }

/** The one current decision of a requirement: PUT creates or replaces it. The detail is updated from the answer, the lists and counts are reloaded. */
export function useSetDecision(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<DecisionOut, Error, DecisionVars>({
    mutationFn: ({ uid, body }) => api.decide(uid, body),
    onSuccess: (out, { uid }) => {
      qc.setQueryData<RequirementDetail>(keys.detail(uid), (d) => (d ? { ...d, decision: { decision: out.decision, edited_text: out.edited_text, note: out.note, updated_at: out.updated_at } } : d))
      void qc.invalidateQueries({ queryKey: keys.detail(uid) }) // saving an edit starts a new draft: the card shows it at once
      void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
      refreshCounts(qc, pid)
    },
  })
}

/** Back to pending (DELETE). */
export function useRemoveDecision(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (uid) => api.removeDecision(uid),
    onSuccess: (_v, uid) => {
      qc.setQueryData<RequirementDetail>(keys.detail(uid), (d) => (d ? { ...d, decision: null } : d))
      void qc.invalidateQueries({ queryKey: keys.detail(uid) }) // the draft goes back to the original text
      void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
      refreshCounts(qc, pid)
    },
  })
}

export interface AcceptSuggestedResult {
  accepted: number
  /** Not accepted because the requirement was decided meanwhile or is no longer suggested for acceptance. */
  skipped: number
  failed: number
}

/** Accept the given requirements one by one, each only if it is still pending and still suggested for acceptance (checked just before it is saved). */
export function useAcceptSuggested(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<AcceptSuggestedResult, Error, { uids: string[]; note: string }>({
    mutationFn: async ({ uids, note }) => {
      const result = { accepted: 0, skipped: 0, failed: 0 }
      for (const uid of uids) {
        try {
          const current = await api.requirement(uid)
          if (current.decision !== null || current.suggestion.action !== 'accept') {
            result.skipped += 1
            continue
          }
          await api.decide(uid, { decision: 'accepted', note })
          result.accepted += 1
        } catch {
          result.failed += 1
        }
      }
      return result
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ['requirement'] })
      void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
      refreshCounts(qc, pid)
    },
  })
}

/**
 * "Accept selected": one accepted decision per requirement (the same call as a single accept, so the same rules and the same audit entry), a few at a time.
 * The caller passes only requirements without a decision.
 */
export function useAcceptSelected(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<{ accepted: number; failed: number }, Error, { uids: string[]; note: string }>({
    mutationFn: async ({ uids, note }) => {
      const result = { accepted: 0, failed: 0 }
      for (let i = 0; i < uids.length; i += 5) {
        await Promise.all(
          uids.slice(i, i + 5).map(async (uid) => {
            try {
              await api.decide(uid, { decision: 'accepted', note })
              result.accepted += 1
            } catch {
              result.failed += 1
            }
          }),
        )
      }
      return result
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ['requirement'] })
      void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
      refreshCounts(qc, pid)
    },
  })
}

export function useUpload(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<UploadResult, Error, { files: File[]; sourceType: SourceType; sprintId?: number; phaseId?: number }>({
    mutationFn: ({ files, sourceType, sprintId, phaseId }) => api.upload(pid!, files, sourceType, { sprintId, phaseId }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.sources(pid ?? 0) })
      void qc.invalidateQueries({ queryKey: keys.sprints(pid ?? 0) })
      refreshCounts(qc, pid)
    },
  })
}

export const usePhases = (pid: number | undefined) => useQuery({ queryKey: keys.phases(pid ?? 0), queryFn: () => api.phases(pid!), enabled: pid !== undefined, retry: false })
export const useSprints = (pid: number | undefined) => useQuery({ queryKey: keys.sprints(pid ?? 0), queryFn: () => api.sprints(pid!), enabled: pid !== undefined, retry: false })

/** Everything that shows sprints, phases or where a document sits is reloaded after a planning change. Planning never starts an analysis. */
function refreshPlanning(qc: Client, pid: number | undefined) {
  void qc.invalidateQueries({ queryKey: keys.phases(pid ?? 0) })
  void qc.invalidateQueries({ queryKey: keys.sprints(pid ?? 0) })
  void qc.invalidateQueries({ queryKey: keys.sources(pid ?? 0) })
  void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
  void qc.invalidateQueries({ queryKey: ['requirement'] })
  refreshCounts(qc, pid)
}

export function useCreatePhase(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<Phase, Error, string>({ mutationFn: (name) => api.createPhase(pid!, name), onSuccess: () => refreshPlanning(qc, pid) })
}
export function useUpdatePhase(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<Phase, Error, { id: number; name?: string; position?: number }>({ mutationFn: ({ id, ...body }) => api.updatePhase(pid!, id, body), onSuccess: () => refreshPlanning(qc, pid) })
}
export function useDeletePhase(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<void, Error, number>({ mutationFn: (id) => api.deletePhase(pid!, id), onSuccess: () => refreshPlanning(qc, pid) })
}
export function useCreateSprint(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<Sprint, Error, SprintInput>({ mutationFn: (body) => api.createSprint(pid!, body), onSuccess: () => refreshPlanning(qc, pid) })
}
export function useUpdateSprint(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<Sprint, Error, { id: number } & Partial<SprintInput> & { confirmed?: boolean }>({ mutationFn: ({ id, ...body }) => api.updateSprint(pid!, id, body), onSuccess: () => refreshPlanning(qc, pid) })
}
export function useDeleteSprint(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<SprintDeleted, Error, { id: number; reassignTo?: number }>({ mutationFn: ({ id, reassignTo }) => api.deleteSprint(pid!, id, reassignTo), onSuccess: () => refreshPlanning(qc, pid) })
}
export function useSetCurrentSprint(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<Sprint, Error, number>({ mutationFn: (id) => api.setCurrentSprint(pid!, id), onSuccess: () => refreshPlanning(qc, pid) })
}
export function useSetSourceSprint(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ sourceId, sprintId }: { sourceId: number; sprintId: number }) => api.setSourceSprint(pid!, sourceId, sprintId), onSuccess: () => refreshPlanning(qc, pid) })
}
export function useAssignRanges(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<AssignRangesResult, Error, { sourceId: number; ranges: PageRange[] }>({ mutationFn: ({ sourceId, ranges }) => api.assignRanges(pid!, sourceId, ranges), onSuccess: () => refreshPlanning(qc, pid) })
}
export function useAssignRequirements(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ ids, sprintId }: { ids: string[]; sprintId: number | null }) => api.assignRequirements(pid!, ids, sprintId), onSuccess: () => refreshPlanning(qc, pid) })
}

/** Analyse one document (also the first analysis of a document that has none): decisions on unchanged text are kept, changed or removed ones are archived. */
export function useReanalyze(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<ReanalyzeResult, Error, { sourceId: number; policy: Policy }>({
    mutationFn: ({ sourceId, policy }) => api.reanalyze(pid!, sourceId, policy),
    onSuccess: (r) => {
      if (r.job) qc.setQueryData(keys.job(r.job.job_id), r.job)
      void qc.invalidateQueries({ queryKey: ['requirement'] })
      void qc.invalidateQueries({ queryKey: keys.sources(pid ?? 0) })
      void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
      refreshCounts(qc, pid)
    },
  })
}

function refreshAfterSourceChange(qc: Client, pid: number | undefined) {
  qc.removeQueries({ queryKey: ['requirement'] })
  void qc.invalidateQueries({ queryKey: keys.sources(pid ?? 0) })
  void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
  refreshCounts(qc, pid)
}

/**
 * Remove one source and everything derived from it (the service refuses with 409 while a job runs).
 * `onDone` runs first, so the page can forget the selected requirement before its cached data is dropped (no request for a deleted id).
 */
export function useDeleteSource(pid: number | undefined, onDone?: () => void) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sourceId: number) => api.deleteSource(pid!, sourceId),
    onSuccess: () => {
      onDone?.()
      refreshAfterSourceChange(qc, pid)
    },
  })
}

export function useClearSources(pid: number | undefined, onDone?: () => void) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.clearSources(pid!),
    onSuccess: () => {
      onDone?.()
      qc.removeQueries({ queryKey: ['job'] })
      refreshAfterSourceChange(qc, pid)
    },
  })
}

/** The analysis request is synchronous and slow on a first run; it is cancelled after limits.analyzeTimeoutMs with a clear message. */
export function useAnalyze(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<Job, Error, Policy | undefined>({
    mutationFn: async (policy: Policy = 'smart') => {
      const ctrl = new AbortController()
      const timer = window.setTimeout(() => ctrl.abort(), limits.analyzeTimeoutMs)
      try {
        return await api.analyze(pid!, ctrl.signal, policy)
      } catch (e) {
        if (ctrl.signal.aborted)
          throw new ApiClientError(0, 'timeout', `The analysis did not answer within ${Math.max(1, Math.ceil(limits.analyzeTimeoutMs / 1000))} seconds. The server may still be working: wait a moment and reload, or try again.`)
        throw e
      } finally {
        window.clearTimeout(timer)
      }
    },
    onSuccess: (job) => {
      qc.setQueryData(keys.job(job.job_id), job)
      void qc.invalidateQueries({ queryKey: keys.sources(pid ?? 0) })
      void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
      refreshCounts(qc, pid)
    },
  })
}

function refreshDrafts(qc: Client) {
  void qc.invalidateQueries({ queryKey: ['requirements'] })
  void qc.invalidateQueries({ queryKey: ['requirement'] })
  refreshCounts(qc)
}

/** "Generate all remaining": queue every requirement that has no draft yet. */
export function useGenerateRemaining(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => api.generateRemaining(pid!), onSuccess: () => refreshDrafts(qc) })
}

/** The Jira connection of the project (never holds a token). */
export const useJiraStatus = (pid: number | undefined) => useQuery({ queryKey: keys.jira(pid ?? 0), queryFn: () => api.jiraStatus(pid!), enabled: pid !== undefined, retry: false })

/** Start the connection: the answer is the address the browser goes to. */
export function useJiraConnect(pid: number | undefined) {
  return useMutation({ mutationFn: () => api.jiraConnect(pid!) })
}

export function useJiraDisconnect(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => api.jiraDisconnect(pid!), onSuccess: () => qc.invalidateQueries({ queryKey: keys.jira(pid ?? 0) }) })
}

export const useJiraProjects = (pid: number | undefined) =>
  useQuery({ queryKey: ['jira', pid, 'projects'], queryFn: () => api.jiraProjects(pid!), enabled: pid !== undefined, retry: false, staleTime: 60_000 })

export const useJiraBoards = (pid: number | undefined, projectKey: string) =>
  useQuery({ queryKey: ['jira', pid, 'boards', projectKey], queryFn: () => api.jiraBoards(pid!, projectKey), enabled: pid !== undefined && projectKey !== '', retry: false, staleTime: 60_000 })

/** Import: afterwards everything that shows documents, requirements, sprints and counts is reloaded. */
export function useJiraImport(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<JiraImportResult, Error, JiraImportInput>({
    mutationFn: (body) => api.jiraImport(pid!, body),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ['sources'] })
      void qc.invalidateQueries({ queryKey: ['requirements'] })
      void qc.invalidateQueries({ queryKey: ['requirement'] })
      void qc.invalidateQueries({ queryKey: keys.sprints(pid ?? 0) })
      void qc.invalidateQueries({ queryKey: keys.jira(pid ?? 0) })
      refreshCounts(qc)
    },
  })
}

/** "Retry failed drafts": queue again only the drafts that failed. */
export function useRetryFailed(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => api.retryFailed(pid!), onSuccess: () => refreshDrafts(qc) })
}

/** Pause stops the queue from taking new items (the one in flight finishes); resume continues. */
export function usePauseGeneration(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (pause: boolean) => (pause ? api.pause(pid!) : api.resume(pid!)), onSuccess: () => refreshDrafts(qc) })
}
