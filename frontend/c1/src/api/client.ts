import { API_BASE } from '../config'
import type {
  ApiErrorBody, DecisionIn, DecisionOut, Engine, EngineTarget, EngineTestResult, EngineUpdate, GenerateAllOut, GenerateOut, Health, Job, ListFilters, PausedOut, Policy, Project, RequirementDetail, RequirementList, Source, Summary, UploadResult,
} from './types'

/** Error with the code and message from the API error shape {error: {code, message}}. status 0 = the API could not be reached. */
export class ApiClientError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
  }
}

async function failure(response: Response, fallback: string): Promise<ApiClientError> {
  let body: Partial<ApiErrorBody> = {}
  try {
    body = (await response.json()) as Partial<ApiErrorBody>
  } catch {
    /* the body is not JSON */
  }
  return new ApiClientError(response.status, body.error?.code ?? 'http_error', body.error?.message ?? fallback)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(API_BASE + path, init)
  } catch {
    throw new ApiClientError(0, 'network_error', `Cannot reach the API at ${API_BASE}.`)
  }
  if (!response.ok) throw await failure(response, `Request failed (${response.status}).`)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const postJson = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export function listParams(f: ListFilters, limit: number, offset: number): string {
  const p = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (f.risk !== 'all') p.set('risk', f.risk)
  if (f.type !== 'all') p.set('type', f.type)
  if (f.q.trim()) p.set('q', f.q.trim())
  return p.toString()
}

export const api = {
  health: () => request<Health>('/api/health'),
  engine: () => request<Engine>('/api/engine'),
  updateEngine: (body: EngineUpdate) => request<Engine>('/api/engine', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  testEngine: (target: EngineTarget) => request<EngineTestResult>('/api/engine/test', postJson({ target })),
  projects: () => request<Project[]>('/api/projects'),
  sources: (pid: number) => request<Source[]>(`/api/projects/${pid}/sources`),
  upload: (pid: number, files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request<UploadResult>(`/api/projects/${pid}/sources`, { method: 'POST', body: form })
  },
  analyze: (pid: number, signal?: AbortSignal, policy: Policy = 'smart') => request<Job>(`/api/projects/${pid}/analyze?policy=${policy}`, { method: 'POST', signal }),
  generateRemaining: (pid: number) => request<GenerateAllOut>(`/api/projects/${pid}/generate`, { method: 'POST' }),
  pause: (pid: number) => request<PausedOut>(`/api/projects/${pid}/generation/pause`, { method: 'POST' }),
  resume: (pid: number) => request<PausedOut>(`/api/projects/${pid}/generation/resume`, { method: 'POST' }),
  deleteSource: (pid: number, sourceId: number) => request<void>(`/api/projects/${pid}/sources/${sourceId}`, { method: 'DELETE' }),
  clearSources: (pid: number) => request<void>(`/api/projects/${pid}/sources`, { method: 'DELETE' }),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  summary: (pid: number) => request<Summary>(`/api/projects/${pid}/summary`),
  requirements: (pid: number, f: ListFilters, limit: number, offset: number) =>
    request<RequirementList>(`/api/projects/${pid}/requirements?${listParams(f, limit, offset)}`),
  requirement: (uid: string) => request<RequirementDetail>(`/api/requirements/${encodeURIComponent(uid)}`),
  generate: (uid: string) => request<GenerateOut>(`/api/requirements/${encodeURIComponent(uid)}/generate`, { method: 'POST' }),
  decide: (uid: string, body: DecisionIn) => request<DecisionOut>(`/api/requirements/${encodeURIComponent(uid)}/decision`, postJson(body)),
  exportUrl: (pid: number, format: 'csv' | 'json') => `${API_BASE}/api/projects/${pid}/export?format=${format}`,
}

/** Download an export through fetch so an API error can be shown instead of saving an error page. */
export async function downloadExport(pid: number, format: 'csv' | 'json'): Promise<void> {
  let response: Response
  try {
    response = await fetch(api.exportUrl(pid, format))
  } catch {
    throw new ApiClientError(0, 'network_error', `Cannot reach the API at ${API_BASE}.`)
  }
  if (!response.ok) throw await failure(response, 'Export failed.')
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `c1_project_${pid}_requirements.${format}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
