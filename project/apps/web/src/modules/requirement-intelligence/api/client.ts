import { API_BASE } from '../config'
import type {
  ApiErrorBody, AssignRangesResult, JiraBoard, JiraConnect, JiraImportInput, JiraImportResult, JiraProject, JiraSprint, JiraSprintState, JiraStatus, DecisionIn, DecisionOut, Engine, EngineTarget, EngineTestResult, EngineUpdate, GenerateAllOut, GenerateOut, Health, Job, ListFilters, Overview, PageRange, PausedOut, Phase, Policy, Project, PublishDocsInput, PublishDocsResult, PublishResult,
  ReanalyzeResult, RequirementDetail, RequirementList, Source, SourceType, Sprint, SprintDeleted, SprintInput, SprintSummary, Summary, SyncStatus, UploadResult,
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
    throw new ApiClientError(0, 'network_error', `Cannot reach the service at ${API_BASE}.`)
  }
  if (!response.ok) throw await failure(response, `Request failed (${response.status}).`)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const withJson = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})
const postJson = (body: unknown) => withJson('POST', body)

export function listParams(f: ListFilters, limit: number, offset: number): string {
  const p = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (f.risk !== 'all') p.set('risk', f.risk)
  if (f.type !== 'all') p.set('type', f.type)
  if (f.q.trim()) p.set('q', f.q.trim())
  if (f.sprint != null) p.set('sprint_id', String(f.sprint))
  return p.toString()
}

export const api = {
  health: () => request<Health>('/api/health'),
  engine: () => request<Engine>('/api/engine'),
  updateEngine: (body: EngineUpdate) => request<Engine>('/api/engine', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  testEngine: (target: EngineTarget) => request<EngineTestResult>('/api/engine/test', postJson({ target })),
  projects: (includeArchived = false) => request<Project[]>(`/api/projects${includeArchived ? '?include_archived=true' : ''}`),
  createProject: (name: string) => request<Project>('/api/projects', postJson({ name })),
  renameProject: (pid: number, name: string) => request<Project>(`/api/projects/${pid}`, withJson('PATCH', { name })),
  archiveProject: (pid: number) => request<Project>(`/api/projects/${pid}/archive`, { method: 'POST' }),
  unarchiveProject: (pid: number) => request<Project>(`/api/projects/${pid}/unarchive`, { method: 'POST' }),
  overview: (pid: number) => request<Overview>(`/api/projects/${pid}/overview`),
  publish: (pid: number) => request<PublishResult>(`/api/projects/${pid}/publish/neo4j`, { method: 'POST' }),
  publishDocuments: (pid: number, body: PublishDocsInput) => request<PublishDocsResult>(`/api/projects/${pid}/publish`, postJson(body)),
  unpublishDocuments: (pid: number, body: PublishDocsInput) => request<PublishDocsResult>(`/api/projects/${pid}/unpublish`, postJson(body)),
  sprintSummary: (pid: number, sprintId: number) => request<SprintSummary>(`/api/projects/${pid}/sprints/${sprintId}/summary`),
  sources: (pid: number) => request<Source[]>(`/api/projects/${pid}/sources`),
  upload: (pid: number, files: File[], sourceType: SourceType = 'srs', target: { sprintId?: number; phaseId?: number } = {}) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    form.append('source_type', sourceType)
    if (target.sprintId !== undefined) form.append('sprint_id', String(target.sprintId))
    if (target.phaseId !== undefined) form.append('phase_id', String(target.phaseId))
    return request<UploadResult>(`/api/projects/${pid}/sources`, { method: 'POST', body: form })
  },
  analyze: (pid: number, signal?: AbortSignal, policy: Policy = 'smart') => request<Job>(`/api/projects/${pid}/analyze?policy=${policy}`, { method: 'POST', signal }),
  jiraStatus: (pid: number) => request<JiraStatus>(`/api/projects/${pid}/integrations/jira`),
  jiraConnect: (pid: number) => request<JiraConnect>(`/api/projects/${pid}/integrations/jira/connect`, { method: 'POST' }),
  jiraDisconnect: (pid: number) => request<void>(`/api/projects/${pid}/integrations/jira`, { method: 'DELETE' }),
  jiraProjects: (pid: number) => request<JiraProject[]>(`/api/projects/${pid}/integrations/jira/projects`),
  jiraBoards: (pid: number, projectKey: string) => request<JiraBoard[]>(`/api/projects/${pid}/integrations/jira/boards?project_key=${encodeURIComponent(projectKey)}`),
  jiraSprints: (pid: number, boardId: number, states: JiraSprintState[] = ['active', 'future']) =>
    request<JiraSprint[]>(`/api/projects/${pid}/integrations/jira/sprints?board_id=${boardId}&states=${states.join(',')}`),
  jiraImport: (pid: number, body: JiraImportInput) => request<JiraImportResult>(`/api/projects/${pid}/integrations/jira/import`, postJson(body)),
  generateRemaining: (pid: number) => request<GenerateAllOut>(`/api/projects/${pid}/generate`, { method: 'POST' }),
  retryFailed: (pid: number) => request<GenerateAllOut>(`/api/projects/${pid}/drafts/retry-failed`, { method: 'POST' }),
  pause: (pid: number) => request<PausedOut>(`/api/projects/${pid}/generation/pause`, { method: 'POST' }),
  resume: (pid: number) => request<PausedOut>(`/api/projects/${pid}/generation/resume`, { method: 'POST' }),
  sync: (pid: number) => request<SyncStatus>(`/api/projects/${pid}/sync`),
  phases: (pid: number) => request<Phase[]>(`/api/projects/${pid}/phases`),
  createPhase: (pid: number, name: string) => request<Phase>(`/api/projects/${pid}/phases`, postJson({ name })),
  updatePhase: (pid: number, id: number, body: { name?: string; position?: number }) => request<Phase>(`/api/projects/${pid}/phases/${id}`, withJson('PATCH', body)),
  deletePhase: (pid: number, id: number) => request<void>(`/api/projects/${pid}/phases/${id}`, { method: 'DELETE' }),
  sprints: (pid: number) => request<Sprint[]>(`/api/projects/${pid}/sprints`),
  createSprint: (pid: number, body: SprintInput) => request<Sprint>(`/api/projects/${pid}/sprints`, postJson(body)),
  updateSprint: (pid: number, id: number, body: Partial<SprintInput> & { confirmed?: boolean }) => request<Sprint>(`/api/projects/${pid}/sprints/${id}`, withJson('PATCH', body)),
  deleteSprint: (pid: number, id: number, reassignTo?: number) =>
    request<SprintDeleted>(`/api/projects/${pid}/sprints/${id}${reassignTo !== undefined ? `?reassign_to=${reassignTo}` : ''}`, { method: 'DELETE' }),
  setCurrentSprint: (pid: number, sprintId: number) => request<Sprint>(`/api/projects/${pid}/current-sprint`, withJson('PUT', { sprint_id: sprintId })),
  setSourceSprint: (pid: number, sourceId: number, sprintId: number) => request<Source>(`/api/projects/${pid}/sources/${sourceId}/sprint`, withJson('PUT', { sprint_id: sprintId })),
  assignRanges: (pid: number, sourceId: number, ranges: PageRange[]) => request<AssignRangesResult>(`/api/projects/${pid}/sources/${sourceId}/assign-ranges`, postJson({ ranges })),
  assignRequirements: (pid: number, ids: string[], sprintId: number | null) => request<{ assigned: number; sprint_id: number | null }>(`/api/projects/${pid}/requirements/assign`, postJson({ requirement_ids: ids, sprint_id: sprintId })),
  reanalyze: (pid: number, sourceId: number, policy: Policy = 'smart') => request<ReanalyzeResult>(`/api/projects/${pid}/sources/${sourceId}/reanalyze?policy=${policy}`, { method: 'POST' }),
  deleteSource: (pid: number, sourceId: number) => request<void>(`/api/projects/${pid}/sources/${sourceId}`, { method: 'DELETE' }),
  clearSources: (pid: number) => request<void>(`/api/projects/${pid}/sources`, { method: 'DELETE' }),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  summary: (pid: number) => request<Summary>(`/api/projects/${pid}/summary`),
  requirements: (pid: number, f: ListFilters, limit: number, offset: number) =>
    request<RequirementList>(`/api/projects/${pid}/requirements?${listParams(f, limit, offset)}`),
  requirement: (uid: string) => request<RequirementDetail>(`/api/requirements/${encodeURIComponent(uid)}`),
  generate: (uid: string) => request<GenerateOut>(`/api/requirements/${encodeURIComponent(uid)}/generate`, { method: 'POST' }),
  decide: (uid: string, body: DecisionIn) => request<DecisionOut>(`/api/requirements/${encodeURIComponent(uid)}/decision`, withJson('PUT', body)),
  removeDecision: (uid: string) => request<void>(`/api/requirements/${encodeURIComponent(uid)}/decision`, { method: 'DELETE' }),
  exportUrl: (pid: number, format: 'csv' | 'json') => `${API_BASE}/api/projects/${pid}/export?format=${format}`,
}

/** Download an export through fetch so an API error can be shown instead of saving an error page. */
export async function downloadExport(pid: number, format: 'csv' | 'json'): Promise<void> {
  let response: Response
  try {
    response = await fetch(api.exportUrl(pid, format))
  } catch {
    throw new ApiClientError(0, 'network_error', `Cannot reach the service at ${API_BASE}.`)
  }
  if (!response.ok) throw await failure(response, 'Export failed.')
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `project_${pid}_requirements.${format}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
