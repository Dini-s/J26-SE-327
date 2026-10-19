/** Types of the requirement service API (docs/c1_api_contract.md, docs/c1_openapi.json). */
export type RiskLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE'
export type FindingType = 'all' | 'ambiguity' | 'conflict' | 'duplicate' | 'security'
export type RiskFilter = 'all' | RiskLevel
export type Stage = 'collect' | 'identify' | 'analyse' | 'improve' | 'share'
export type GenerationState = 'not_requested' | 'queued' | 'running' | 'done' | 'needs_clarification' | 'failed' | 'manual_review'
export type DecisionKind = 'accepted' | 'edited' | 'rejected'

export interface Health {
  status: string
  part_a_loaded: boolean
  generation_backend: string
  generation_reachable: boolean
  model: string
  /** Where drafts are written now. */
  generation_target: EngineTarget
}

export type EngineTarget = 'device' | 'cloud'

export interface DecisionCounts {
  accepted: number
  edited: number
  rejected: number
  pending: number
}

export interface Project {
  id: number
  /** Unique, immutable slug; also the project id in the knowledge graph. */
  project_key: string
  name: string
  archived: boolean
  created_at: string
  sources: number
  requirements: number
  decisions: DecisionCounts
  last_analysis_at: string | null
  last_published_at: string | null
  out_of_date: boolean
}

export type SourceType = 'srs' | 'brd' | 'other' | 'jira'

export type AnalysisState = 'not_analyzed' | 'analyzing' | 'analyzed' | 'failed'

export interface Source {
  id: number
  filename: string
  ext: string
  size_bytes: number
  pages: number | null
  warnings: string[]
  created_at: string
  uploaded_at: string
  source_type: SourceType
  default_sprint_id: number | null
  analysis_state: AnalysisState
  analyzed_at: string | null
  requirements: number
  ambiguities: number
  drafts: { ready: number; needs_clarification: number; failed: number }
  /** Where its requirements are, by effective sprint (null = no sprint). */
  sprints: { sprint_id: number | null; count: number }[]
}

export interface Phase {
  id: number
  project_id: number
  name: string
  position: number
  sprints: number
}

export type SprintOrigin = 'manual' | 'detected' | 'jira'

export interface Sprint {
  id: number
  project_id: number
  phase_id: number | null
  name: string
  start_date: string | null
  end_date: string | null
  goal: string | null
  origin: SprintOrigin
  /** false = proposed from a document name; a person confirms it. */
  confirmed: boolean
  external_id: string | null
  position: number
  is_current: boolean
  requirements: number
  pending: number
  documents: number
}

export interface SprintInput {
  name: string
  phase_id?: number | null
  start_date?: string | null
  end_date?: string | null
  goal?: string | null
}

export interface DetectedSprint {
  filename: string
  sprint_id: number
  name: string
  confirmed: boolean
}

export interface SprintDeleted {
  deleted: number
  reassigned_to: number | null
  requirements_moved: number
}

export interface PageRange {
  from_page: number
  to_page: number
  sprint_id: number
}

export interface AssignRangesResult {
  assigned: number
  requirements: number
  without_page: number
}

export interface ReanalyzeResult {
  source_id: number
  kept: number
  changed: number
  removed: number
  added: number
  queued: number
  job: Job | null
}

export interface RejectedFile {
  filename: string
  code: string
  message: string
}

export interface UploadResult {
  accepted: Source[]
  rejected: RejectedFile[]
  sprint_detected: boolean
  detected: DetectedSprint[]
}

/** Which drafts an analysis run queues by itself: smart = important ones, all = every one, manual = none. */
export type Policy = 'smart' | 'all' | 'manual'

export interface GenerationCounts {
  total: number
  done: number
  failed: number
  queued: number
  running: number
}

export interface Job {
  job_id: string
  project_id: number
  stage: Stage
  part_a_done: boolean
  generation: GenerationCounts
  requirements: number
  error: string | null
  policy: Policy
}

export interface Summary {
  requirements: number
  ambiguities: { count: number; high_risk: number; asked_by_ai: number }
  conflicts: number
  duplicates: number
  duplicate_groups: number
  security: number
  risk_counts: Record<string, number>
  task_drafts: TaskDrafts
  open_findings: number
  decided: number
}

/** Draft counts, each kind apart. `eta_seconds` is null until 3 real latencies exist. */
export interface TaskDrafts {
  generated: number
  total: number
  needs_clarification: number
  manual_review: number
  failed: number
  not_generated: number
  in_progress: number
  queued: number
  running: number
  paused: boolean
  /** 'cloud_unreachable' when the queue paused itself after 3 failed cloud requests; otherwise null. */
  paused_reason: string | null
  eta_seconds: number | null
  latency_samples: number
}

export interface Flags {
  ambiguity: boolean
  conflict: boolean
  duplicate: boolean
  security: boolean
}

/** Rule-based hint (never stored): what a reviewer would probably do, and why. */
export type SuggestAction = 'accept' | 'edit' | 'reject'
export interface Suggestion {
  action: SuggestAction
  reasons: string[]
}

export interface RequirementRow {
  /** Effective sprint: the requirement's own, else its document's. */
  sprint_id: number | null
  uid: string
  id: string
  text: string
  source_file: string
  page: number | null
  paragraph: number | null
  fr_nfr: string
  risk_level: RiskLevel
  risk_score: number
  flags: Flags
  /** Set for requirements imported from Jira. */
  jira: JiraRef | null
  generation_state: GenerationState
  /** Why the draft failed (state `failed` only), as a short code. */
  failure_reason: FailureReason | null
  decision: DecisionKind | null
  suggestion: Suggestion
}

export type FailureReason = 'engine_unavailable' | 'engine_skipped' | 'cloud_unreachable' | 'cloud_rejected' | 'not_in_replay' | 'engine_not_ready' | 'unexpected' | 'unknown'

export interface RequirementList {
  total: number
  limit: number
  offset: number
  items: RequirementRow[]
}

export interface Partner {
  id: string
  uid: string
  similarity: number
  text: string
  source_file: string
  page: number | null
  paragraph: number | null
  kind?: string
  reason?: string
}

/** A word from the rule-based vague-term list (separate from the ambiguity check). */
export interface VagueTerm {
  term: string
  start: number
  end: number
}

export interface WeakWordSpan {
  word: string
  start: number
  end: number
}

export interface Finding {
  type: string
  message: string
  related: string[]
}

export interface Generation {
  state: GenerationState
  failure_reason: FailureReason | null
  message: string
  status: string | null
  user_story: string
  technical_task: string
  acceptance_criteria: string[]
  rationale: string
  clarification_questions: string[]
  attempts: number
  manual_review: boolean
  raw_output: string
  updated_at: string | null
  /** Which backend wrote the stored reply (ollama | replay | mock); empty when nothing was generated. */
  /** Numbers in the reply that the requirement text does not contain (a hint to verify). */
  numbers_not_in_source: string[]
  /** 'clarified' when the model was given the user's rewritten text. */
  generated_from: string
  backend: string
  model: string
  /** Where the stored reply was written: 'device' or 'cloud'. */
  generated_on: string
  /** Host name of the cloud server (never the address); null for the device. */
  endpoint_host: string | null
}

export interface DecisionRecord {
  decision: DecisionKind
  edited_text: string | null
  note: string | null
  updated_at: string
}

export interface RequirementDetail {
  /** Set for requirements imported from Jira. */
  jira: JiraRef | null
  sprint_id: number | null
  uid: string
  id: string
  project_id: number
  text: string
  original_text: string
  source: { file: string; page: number | null; paragraph: number | null; position: number | null; clause_label: string | null }
  classification: { fr_nfr: string; nfr_probability: number }
  ambiguity: { label: string; probability_defect: number; weak_words: string[]; weak_word_spans: WeakWordSpan[] }
  security: { is_security: boolean; cue_words: string[] }
  duplicates: Partner[]
  duplicate_group: string
  conflicts: Partner[]
  risk: { level: RiskLevel; score: number; note: string }
  findings: Finding[]
  explanation: string
  vague_terms: VagueTerm[]
  generation: Generation
  suggestion: Suggestion
  decision: DecisionRecord | null
}

export interface DecisionIn {
  decision: DecisionKind
  edited_text?: string | null
  note?: string | null
}

export interface DecisionOut extends DecisionRecord {
  uid: string
}

export interface GenerateAllOut {
  queued: number
}

export interface PausedOut {
  paused: boolean
}

export interface GenerateOut {
  uid: string
  generation_state: GenerationState
}

export interface DeviceEngine {
  backend: string
  model: string
  reachable: boolean
  concurrency: number
}

export interface CloudEngine {
  configured: boolean
  host: string | null
  model: string
  concurrency: number
  consent: boolean
  consent_at: string | null
  /** Result of the last connection test of the CURRENT settings; null = not tested. */
  reachable: boolean | null
  last_tested_at: string | null
}

/** GET /api/engine. The address is never returned (host only) and the key is write-only. */
export interface Engine {
  target: EngineTarget
  cloud_available: boolean
  cloud_disabled_reason: string | null
  device: DeviceEngine
  cloud: CloudEngine
}

/** PUT /api/engine: only the fields that change. `cloud_api_key` '' removes the key. */
export interface EngineUpdate {
  target?: EngineTarget
  cloud_url?: string
  cloud_api_key?: string
  cloud_model?: string
  cloud_concurrency?: number
  cloud_consent?: boolean
}

export interface EngineTestResult {
  ok: boolean
  detail: string
  latency_ms: number | null
}

export interface ApiErrorBody {
  error: { code: string; message: string }
}

export interface ListFilters {
  risk: RiskFilter
  type: FindingType
  q: string
  /** Only requirements of this (effective) sprint; sent to the service as sprint_id. */
  sprint?: number | null
}

/** GET /api/projects/{pid}/overview */
export interface Overview {
  project: { id: number; project_key: string; name: string; archived: boolean }
  counts: {
    requirements: number
    ambiguities: { total: number; detected: number; asked_by_ai: number }
    conflicts: number
    duplicates: number
    drafts: { total: number; done: number; ready: number; needs_clarification: number; waiting: number; failed: number; not_generated: number; manual_review: number }
  }
  decisions: DecisionCounts & { decided: number; percent_decided: number }
  sources: { count: number; by_type: Record<string, number>; total_size_bytes: number; latest_upload_at: string | null }
  last_analysis_at: string | null
  generation: { state: 'idle' | 'running' | 'paused'; target: EngineTarget; in_progress: number; paused_reason: string | null; eta_seconds: number | null }
  neo4j: GraphStatus
  current_sprint: CurrentSprint | null
  current_phase: CurrentPhase | null
  by_sprint: SprintDecisions[]
  by_phase: PhaseDecisions[]
  findings_by_type: { ambiguity: number; conflict: number; duplicate: number; security: number }
  latest_uploads: Source[]
  analysis: { ready: number; total: number }
  sync: SyncStatus
  pipeline: Pipeline
}

export type StageState = 'done' | 'active' | 'waiting' | 'failed'
/** Where the project stands, in five stages; each has a state and the numbers behind it. */
export interface Pipeline {
  collect: { state: StageState; documents: number }
  identify: { state: StageState; documents: number; requirements: number }
  analyse: { state: StageState; analysed: number; total: number; failed: number }
  improve: {
    /** `attention`: some drafts failed and the rest works; `failed`: every draft failed. */
    state: StageState | 'attention'
    requirements: number
    decided: number
    drafts_written: number
    drafts: { ready: number; needs_clarification: number; failed: number; waiting: number }
  }
  share: { state: StageState; sync_state: SyncStatus['state']; last_synced_at: string | null }
}

export interface PlanDecisions {
  total: number
  accepted: number
  edited: number
  rejected: number
  /** Needs a decision. */
  pending: number
}
export interface SprintDecisions extends PlanDecisions {
  sprint_id: number
  name: string
  phase_id: number | null
  is_current: boolean
}
export interface PhaseDecisions extends PlanDecisions {
  phase_id: number | null
  name: string | null
  sprints: number
}
export interface CurrentSprint {
  id: number
  name: string
  phase_id: number | null
  start_date: string | null
  end_date: string | null
  goal: string | null
  requirements: number
  pending: number
  decided: number
  percent_decided: number
}
export interface CurrentPhase {
  id: number
  name: string
  sprints: number
  requirements: number
  pending: number
  decided: number
  percent_decided: number
}

export type SyncState = 'synced' | 'syncing' | 'pending' | 'retrying' | 'not_configured' | 'unreachable'

/** Background sync to the knowledge graph (GET .../sync and `sync` in the overview). */
export interface SyncStatus {
  state: SyncState
  enabled: boolean
  last_synced_at: string | null
  counts: Record<string, number> | null
  next_attempt_at: string | null
  error: string | null
}

/** Publish status of a project (the overview and GET .../publish/neo4j). */
export interface GraphStatus {
  configured: boolean
  reachable: boolean
  project_id: string
  last_published_at: string | null
  out_of_date: boolean
  error: string | null
  message: string | null
}

export interface PublishResult {
  project_id: string
  published_at: string
  seconds: number
  counts: Record<string, number>
  deactivated: Record<string, number>
  content_hash: string
}

/** GET /api/requirements/{rid}/decision: "pending" while nothing is decided. */
export interface DecisionState {
  uid: string
  decision: DecisionKind | 'pending'
  edited_text: string | null
  note: string | null
  updated_at: string | null
}

// ------------------------------------------------------------------------------------------------------------------ Jira
/** Where an imported requirement comes from. */
export interface JiraRef {
  key: string
  type: string
  status: string
  /** The issue in the Jira site; empty when the site is not known. */
  url: string
}

export type JiraState = 'not_configured' | 'not_connected' | 'connected' | 'expired'

/** GET /api/projects/{pid}/integrations/jira (no token is ever part of it). */
export interface JiraStatus {
  state: JiraState
  /** Connected with fewer permissions than the import asks for now (board access): Connect again, nothing imported is lost. */
  needs_reconnect: boolean
  site: { name: string; url: string } | null
  connected_at: string | null
  last_import: { at: string; counts: Record<string, unknown> } | null
}

export interface JiraConnect {
  authorize_url: string
}
export interface JiraProject {
  key: string
  name: string
}
export interface JiraBoard {
  id: number
  name: string
  type: string
}
export type JiraSprintState = 'active' | 'future' | 'closed'
export interface JiraSprint {
  id: number
  name: string
  state: JiraSprintState
  start_date: string | null
  end_date: string | null
  goal: string | null
}
export interface JiraImportInput {
  project_key: string
  board_id?: number | null
  sprint_states?: JiraSprintState[]
  issue_types?: string[]
  set_current?: boolean
  /** A sprint id: everything goes there. Left out: the current sprint. `'match'`: each issue to the sprint of its Jira sprint. */
  target_sprint_id?: number | 'match' | null
  policy?: Policy
  analyze?: boolean
}
export interface JiraImportResult {
  sprints_created: number
  sprints_updated: number
  issues_new: number
  issues_updated: number
  issues_unchanged: number
  /** Issues without any text. */
  skipped: number
  /** Imported before, not returned now: kept and marked. */
  missing: number
  truncated: boolean
  /** Task drafts queued after the analysis. */
  queued: number
  job_id: string | null
  analysis_error: string | null
  /** Where everything went (null with `matched`: each issue went to its own sprint). */
  target_sprint: { id: number; name: string } | null
  matched: boolean
}
