/** Types of the Component 1 API (docs/c1_api_contract.md, docs/c1_openapi.json). */
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

export interface Project {
  id: number
  name: string
  created_at: string
  sources: number
  requirements: number
}

export interface Source {
  id: number
  filename: string
  ext: string
  size_bytes: number
  pages: number | null
  warnings: string[]
  created_at: string
}

export interface RejectedFile {
  filename: string
  code: string
  message: string
}

export interface UploadResult {
  accepted: Source[]
  rejected: RejectedFile[]
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

export interface RequirementRow {
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
  generation_state: GenerationState
  decision: DecisionKind | null
}

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

/** A word from the rule-based vague-term list (separate from Part A). */
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

export interface DecisionHistoryItem {
  decision: DecisionKind
  edited_text: string | null
  note: string | null
  created_at: string
}

export interface RequirementDetail {
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
  decision: DecisionRecord | null
  decision_history: DecisionHistoryItem[]
}

export interface DecisionIn {
  decision: DecisionKind
  edited_text?: string | null
  note?: string | null
}

export interface DecisionOut extends DecisionRecord {
  uid: string
  history: DecisionHistoryItem[]
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
}
