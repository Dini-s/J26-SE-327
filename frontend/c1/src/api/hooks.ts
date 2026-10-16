import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { DRAFT_POLL_MS, HEALTH_POLL_MS, JOB_POLL_MS, PAGE_SIZE, limits } from '../config'
import { isGenerating } from '../lib/format'
import { ApiClientError, api } from './client'
import type { DecisionIn, DecisionOut, Engine, EngineTarget, EngineTestResult, EngineUpdate, GenerateOut, Job, ListFilters, Policy, RequirementDetail, RequirementList } from './types'

export const keys = {
  health: ['health'] as const,
  engine: ['engine'] as const,
  projects: ['projects'] as const,
  sources: (pid: number) => ['sources', pid] as const,
  summary: (pid: number) => ['summary', pid] as const,
  list: (pid: number, f: ListFilters) => ['requirements', pid, f.risk, f.type, f.q] as const,
  listAll: (pid: number) => ['requirements', pid] as const,
  detail: (uid: string) => ['requirement', uid] as const,
  job: (id: string) => ['job', id] as const,
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

export const useProjects = () => useQuery({ queryKey: keys.projects, queryFn: api.projects, retry: false })

export const useSources = (pid: number | undefined) =>
  useQuery({ queryKey: keys.sources(pid ?? 0), queryFn: () => api.sources(pid!), enabled: pid !== undefined, retry: false })

/** Refresh the numbers every 2 s while drafts are queued or running (also after a reload: the queue is saved by the API) or when `live` is set. */
export const useSummary = (pid: number | undefined, live = false) =>
  useQuery({
    queryKey: keys.summary(pid ?? 0),
    queryFn: () => api.summary(pid!),
    enabled: pid !== undefined,
    retry: false,
    refetchInterval: (q) => (live || (q.state.data?.task_drafts.in_progress ?? 0) > 0 ? JOB_POLL_MS : false),
  })

export const isJobFinished = (job: Job | undefined) => !!job && (job.stage === 'share' || !!job.error) && job.generation.queued === 0

/** Polls the job every 2 s until Part A is done and the generation queue is empty. */
export const useJob = (jobId: string | null) =>
  useQuery({
    queryKey: keys.job(jobId ?? ''),
    queryFn: () => api.job(jobId!),
    enabled: !!jobId,
    retry: false,
    refetchInterval: (q) => (isJobFinished(q.state.data) ? false : JOB_POLL_MS),
  })

export function useRequirementList(pid: number | undefined, filters: ListFilters) {
  return useInfiniteQuery({
    queryKey: keys.list(pid ?? 0, filters),
    queryFn: ({ pageParam }) => api.requirements(pid!, filters, PAGE_SIZE, pageParam),
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
      // the API answers "queued", or the state of a cached reply that was applied at once
      qc.setQueryData<RequirementDetail>(keys.detail(uid), (d) => (d ? { ...d, generation: { ...d.generation, state: data.generation_state, message: '' } } : d))
      void qc.invalidateQueries({ queryKey: keys.detail(uid) })
      void qc.invalidateQueries({ queryKey: ['summary'] })
      void qc.invalidateQueries({ queryKey: ['requirements'] })
    },
  })
}

interface DecisionContext {
  detail: RequirementDetail | undefined
  lists: [readonly unknown[], { pages: RequirementList[]; pageParams: unknown[] } | undefined][]
}

/** Decision with an optimistic update of the detail and the list rows; both are restored when the API refuses. */
export function useDecision(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation<DecisionOut, Error, { uid: string; body: DecisionIn }, DecisionContext>({
    mutationFn: ({ uid, body }) => api.decide(uid, body),
    onMutate: async ({ uid, body }) => {
      await qc.cancelQueries({ queryKey: keys.detail(uid) })
      const detail = qc.getQueryData<RequirementDetail>(keys.detail(uid))
      const lists = qc.getQueriesData<{ pages: RequirementList[]; pageParams: unknown[] }>({ queryKey: keys.listAll(pid ?? 0) })
      const stamp = new Date().toISOString()
      if (detail) {
        const edited = body.decision === 'edited' ? (body.edited_text ?? null) : null
        qc.setQueryData<RequirementDetail>(keys.detail(uid), {
          ...detail,
          decision: { decision: body.decision, edited_text: edited, note: body.note ?? null, updated_at: stamp },
          decision_history: [...detail.decision_history, { decision: body.decision, edited_text: edited, note: body.note ?? null, created_at: stamp }],
        })
      }
      for (const [key, data] of lists) {
        if (!data) continue
        qc.setQueryData(key, { ...data, pages: data.pages.map((p) => ({ ...p, items: p.items.map((r) => (r.uid === uid ? { ...r, decision: body.decision } : r)) })) })
      }
      return { detail, lists }
    },
    onError: (_err, { uid }, ctx) => {
      if (!ctx) return
      if (ctx.detail) qc.setQueryData(keys.detail(uid), ctx.detail)
      for (const [key, data] of ctx.lists) qc.setQueryData(key, data)
    },
    onSettled: (_d, _e, { uid }) => {
      void qc.invalidateQueries({ queryKey: keys.detail(uid) })
      void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
      void qc.invalidateQueries({ queryKey: keys.summary(pid ?? 0) })
    },
  })
}

export function useUpload(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => api.upload(pid!, files),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.sources(pid ?? 0) })
      void qc.invalidateQueries({ queryKey: keys.projects })
    },
  })
}

function refreshAfterSourceChange(qc: ReturnType<typeof useQueryClient>, pid: number | undefined) {
  qc.removeQueries({ queryKey: ['requirement'] })
  void qc.invalidateQueries({ queryKey: keys.sources(pid ?? 0) })
  void qc.invalidateQueries({ queryKey: keys.summary(pid ?? 0) })
  void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
  void qc.invalidateQueries({ queryKey: keys.projects })
}

/**
 * Remove one source and everything derived from it (the API refuses with 409 while a job runs).
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
  return useMutation({
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
      void qc.invalidateQueries({ queryKey: keys.summary(pid ?? 0) })
      void qc.invalidateQueries({ queryKey: keys.listAll(pid ?? 0) })
      void qc.invalidateQueries({ queryKey: keys.projects })
    },
  })
}

function refreshDrafts(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ['summary'] })
  void qc.invalidateQueries({ queryKey: ['requirements'] })
  void qc.invalidateQueries({ queryKey: ['requirement'] })
}

/** "Generate all remaining": queue every requirement that has no draft yet. */
export function useGenerateRemaining(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => api.generateRemaining(pid!), onSuccess: () => refreshDrafts(qc) })
}

/** Pause stops the queue from taking new items (the one in flight finishes); resume continues. */
export function usePauseGeneration(pid: number | undefined) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (pause: boolean) => (pause ? api.pause(pid!) : api.resume(pid!)), onSuccess: () => refreshDrafts(qc) })
}
