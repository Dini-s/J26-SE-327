import type { Engine, Generation, GraphStatus, Health, Job, JiraBoard, JiraImportResult, JiraProject, JiraSprint, JiraStatus, Overview, Phase, Project, RequirementDetail, RequirementRow, Source, Sprint, Summary, SyncStatus } from '../api/types'

export const health: Health = { status: 'ok', part_a_loaded: true, generation_backend: 'replay', generation_reachable: true, model: 'replay', generation_target: 'device' }
/** GET /api/engine on a fresh install: the device is ready, the cloud is not set up. */
export const engine: Engine = {
  target: 'device', cloud_available: true, cloud_disabled_reason: null,
  device: { backend: 'ollama', model: 'c1-req', reachable: true, concurrency: 1 },
  cloud: { configured: false, host: null, model: 'c1-req', concurrency: 4, consent: false, consent_at: null, reachable: null, last_tested_at: null },
}
export const project: Project = {
  id: 1, project_key: 'demo-project', name: 'Core Banking Platform', archived: false, created_at: '2026-10-13T06:00:00+00:00', sources: 1, requirements: 42,
  decisions: { accepted: 0, edited: 0, rejected: 0, pending: 42 }, last_analysis_at: '2026-10-13T06:05:00+00:00', last_published_at: null, out_of_date: true,
}
export const source: Source = {
  id: 1, filename: 'CoreBanking_SRS_v2.pdf', ext: '.pdf', size_bytes: 1000, pages: 12, warnings: [], created_at: '2026-10-13T06:00:00+00:00', uploaded_at: '2026-10-13T06:00:00+00:00', source_type: 'srs',
  default_sprint_id: 1, analysis_state: 'analyzed', analyzed_at: '2026-10-13T06:05:00+00:00', requirements: 42, ambiguities: 8, drafts: { ready: 29, needs_clarification: 2, failed: 1 },
  sprints: [{ sprint_id: 1, count: 30 }, { sprint_id: 2, count: 12 }],
}
/** A second document that nobody has analysed yet. */
export const source2: Source = {
  id: 2, filename: 'Billing_BRD.docx', ext: '.docx', size_bytes: 52000, pages: null, warnings: [], created_at: '2026-10-14T06:00:00+00:00', uploaded_at: '2026-10-14T06:00:00+00:00', source_type: 'brd',
  default_sprint_id: 3, analysis_state: 'not_analyzed', analyzed_at: null, requirements: 0, ambiguities: 0, drafts: { ready: 0, needs_clarification: 0, failed: 0 }, sprints: [],
}

export const phases: Phase[] = [{ id: 1, project_id: 1, name: 'Discovery', position: 1, sprints: 2 }]
const sprintBase = { project_id: 1, start_date: null, end_date: null, goal: null, origin: 'manual' as const, confirmed: true, external_id: null }
export const sprints: Sprint[] = [
  { ...sprintBase, id: 1, phase_id: 1, name: 'Sprint 1', start_date: '2026-10-05', end_date: '2026-10-16', goal: 'Sign-in and accounts', position: 1, is_current: true, requirements: 30, pending: 20, documents: 1 },
  { ...sprintBase, id: 2, phase_id: 1, name: 'Sprint 2', position: 2, is_current: false, requirements: 12, pending: 7, documents: 0 },
  { ...sprintBase, id: 3, phase_id: null, name: 'Sprint 3', position: 3, is_current: false, requirements: 0, pending: 0, documents: 1 },
]
export const sync: SyncStatus = { state: 'synced', enabled: true, last_synced_at: '2026-10-20T08:00:00+00:00', counts: { Requirement: 42 }, next_attempt_at: null, error: null }

export const summary: Summary = {
  requirements: 42,
  ambiguities: { count: 8, high_risk: 3, asked_by_ai: 0 },
  conflicts: 2,
  duplicates: 3,
  duplicate_groups: 2,
  security: 5,
  risk_counts: { HIGH: 3, MEDIUM: 8, LOW: 10, NONE: 21 },
  task_drafts: { generated: 29, total: 42, needs_clarification: 0, manual_review: 0, failed: 0, not_generated: 0, in_progress: 0, queued: 0, running: 0, paused: false, eta_seconds: null, latency_samples: 0, paused_reason: null },
  open_findings: 13,
  decided: 0,
}

/** The graph part of the overview when nothing is set up (the service names the internal system in `message`; the UI must not show it). */
export const graph: GraphStatus = {
  configured: false, reachable: false, project_id: 'demo-project', last_published_at: null, out_of_date: true,
  error: 'neo4j_unconfigured', message: 'Neo4j is not configured. Set NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD.',
}

export const overview: Overview = {
  project: { id: 1, project_key: 'demo-project', name: 'Core Banking Platform', archived: false },
  counts: {
    requirements: 42,
    ambiguities: { total: 10, detected: 8, asked_by_ai: 2 },
    conflicts: 2,
    duplicates: 3,
    drafts: { total: 42, done: 29, ready: 29, needs_clarification: 2, waiting: 0, failed: 1, not_generated: 10, manual_review: 0 },
  },
  decisions: { accepted: 10, edited: 4, rejected: 1, pending: 27, decided: 15, percent_decided: 35.7 },
  sources: { count: 2, by_type: { srs: 1, brd: 1 }, total_size_bytes: 182000, latest_upload_at: '2026-10-13T06:00:00+00:00' },
  last_analysis_at: '2026-10-13T06:05:00+00:00',
  generation: { state: 'idle', target: 'device', in_progress: 0, paused_reason: null, eta_seconds: null },
  neo4j: graph,
  current_sprint: { id: 1, name: 'Sprint 1', phase_id: 1, start_date: '2026-10-05', end_date: '2026-10-16', goal: 'Sign-in and accounts', requirements: 30, pending: 20, decided: 10, percent_decided: 33.3 },
  current_phase: { id: 1, name: 'Discovery', sprints: 2, requirements: 42, pending: 27, decided: 15, percent_decided: 35.7 },
  by_sprint: [
    { sprint_id: 1, name: 'Sprint 1', phase_id: 1, is_current: true, total: 30, accepted: 7, edited: 2, rejected: 1, pending: 20 },
    { sprint_id: 2, name: 'Sprint 2', phase_id: 1, is_current: false, total: 12, accepted: 3, edited: 2, rejected: 0, pending: 7 },
    { sprint_id: 3, name: 'Sprint 3', phase_id: null, is_current: false, total: 0, accepted: 0, edited: 0, rejected: 0, pending: 0 },
  ],
  by_phase: [
    { phase_id: 1, name: 'Discovery', sprints: 2, total: 42, accepted: 10, edited: 4, rejected: 1, pending: 27 },
    { phase_id: null, name: null, sprints: 1, total: 0, accepted: 0, edited: 0, rejected: 0, pending: 0 },
  ],
  findings_by_type: { ambiguity: 8, conflict: 2, duplicate: 3, security: 5 },
  latest_uploads: [source2, source],
  analysis: { ready: 1, total: 2 },
  sync,
  pipeline: {
    collect: { state: 'done', documents: 2 },
    identify: { state: 'done', documents: 2, requirements: 42 },
    analyse: { state: 'waiting', analysed: 1, total: 2, failed: 0 },
    improve: { state: 'active', requirements: 42, decided: 15, drafts_written: 31, drafts: { ready: 29, needs_clarification: 2, failed: 1, waiting: 0 } },
    share: { state: 'done', sync_state: 'synced', last_synced_at: sync.last_synced_at },
  },
}

export const rows: RequirementRow[] = [
  {
    jira: null, uid: 'p1-REQ-001', id: 'REQ-001', text: 'The system should quickly notify users about suspicious logins.', source_file: 'CoreBanking_SRS_v2.pdf', page: 12, paragraph: 3,
    fr_nfr: 'NFR', risk_level: 'HIGH', risk_score: 4, flags: { ambiguity: true, conflict: false, duplicate: false, security: true }, generation_state: 'done', failure_reason: null, decision: null, sprint_id: 1,
    suggestion: { action: 'edit', reasons: ['The wording is unclear.', 'Risk level is high.'] },
  },
  {
    jira: null, uid: 'p1-REQ-002', id: 'REQ-002', text: 'A customer may update their registered mobile number without additional verification.', source_file: 'CoreBanking_SRS_v2.pdf', page: 7, paragraph: 6,
    fr_nfr: 'FR', risk_level: 'HIGH', risk_score: 4, flags: { ambiguity: false, conflict: true, duplicate: false, security: false }, generation_state: 'done', failure_reason: null, decision: null, sprint_id: 1,
    suggestion: { action: 'edit', reasons: ['May conflict with another requirement.', 'Risk level is high.'] },
  },
  {
    jira: null, uid: 'p1-REQ-003', id: 'REQ-003', text: 'Administrators shall be able to temporarily deactivate a customer account.', source_file: 'CoreBanking_SRS_v2.pdf', page: 10, paragraph: 2,
    fr_nfr: 'FR', risk_level: 'MEDIUM', risk_score: 2, flags: { ambiguity: false, conflict: false, duplicate: true, security: false }, generation_state: 'failed', failure_reason: 'engine_unavailable', decision: null, sprint_id: 2,
    suggestion: { action: 'reject', reasons: ['Repeats REQ-001, which comes earlier; keep the first and drop this copy.'] },
  },
]

export const generationDone: Generation = {
  state: 'done', failure_reason: null, message: '', status: 'ok', user_story: 'As a customer, I want to be notified about suspicious logins, so that I can react.',
  technical_task: 'Send a notification when a suspicious login is detected.',
  acceptance_criteria: ['Given a suspicious login, when it is detected, then the user is notified.', 'Given a normal login, when it occurs, then no alert is sent.'],
  rationale: 'Role assumed: customer.', clarification_questions: [], attempts: 1, manual_review: false, raw_output: '', updated_at: '2026-10-13T06:01:00+00:00',
  numbers_not_in_source: [], generated_from: 'original', backend: 'replay', model: 'replay', generated_on: 'device', endpoint_host: null,
}

// decision_history is deprecated in the service and no longer typed or read by the module; the fixture keeps it so it has exactly the schema's fields
export const detail: RequirementDetail = {
  jira: null, sprint_id: 1, uid: 'p1-REQ-001', id: 'REQ-001', project_id: 1,
  text: rows[0]!.text, original_text: rows[0]!.text,
  source: { file: 'CoreBanking_SRS_v2.pdf', page: 12, paragraph: 3, position: 1, clause_label: '3.1' },
  classification: { fr_nfr: 'NFR', nfr_probability: 0.84 },
  ambiguity: { label: 'defect', probability_defect: 0.97, weak_words: ['quickly'], weak_word_spans: [{ word: 'quickly', start: 18, end: 25 }] },
  security: { is_security: true, cue_words: ['login'] },
  duplicates: [], duplicate_group: '', conflicts: [],
  risk: { level: 'HIGH', score: 4, note: 'unvalidated heuristic, not a trained model' },
  findings: [
    { type: 'ambiguity', message: 'Ambiguity model: `defect` with probability 0.97.', related: [] },
    { type: 'weak_word', message: 'Weak words found (QuRE list): quickly.', related: [] },
    { type: 'security', message: 'Security-related: keyword rule matched login.', related: [] },
  ],
  vague_terms: [{ term: 'quickly', start: 18, end: 25 }],
  explanation: 'Classified as NFR (probability of NFR 0.84, embeddings + logistic regression baseline). Ambiguity model: `defect` with probability 0.97.',
  generation: generationDone, decision: null,
  suggestion: { action: 'edit', reasons: ['The wording is unclear.', 'Risk level is high.'] },
  ...({ decision_history: [] } as object),
}

export const job: Job = {
  job_id: 'abc123', project_id: 1, stage: 'improve', part_a_done: true,
  generation: { total: 42, done: 10, failed: 0, queued: 32, running: 1 }, requirements: 42, error: null, policy: 'smart',
}

// ------------------------------------------------------------------------------------------------------------------ Jira
export const jiraNotConnected: JiraStatus = { state: 'not_connected', needs_reconnect: false, site: null, connected_at: null, last_import: null }
export const jiraConnected: JiraStatus = { state: 'connected', needs_reconnect: false, site: { name: 'Acme', url: 'https://acme.atlassian.net' }, connected_at: '2026-10-19T08:00:00+00:00', last_import: null }
export const jiraNeedsReconnect: JiraStatus = { ...jiraConnected, needs_reconnect: true }
export const jiraExpired: JiraStatus = { ...jiraConnected, state: 'expired' }
export const jiraNotConfigured: JiraStatus = { ...jiraNotConnected, state: 'not_configured' }
export const jiraProjects: JiraProject[] = [{ key: 'ABC', name: 'Alpha' }, { key: 'DEF', name: 'Delta' }]
export const jiraBoards: JiraBoard[] = [{ id: 7, name: 'ABC board', type: 'scrum' }, { id: 8, name: 'ABC kanban', type: 'kanban' }]
export const jiraSprints: JiraSprint[] = [{ id: 10, name: 'Sprint 1', state: 'active', start_date: '2026-10-05', end_date: '2026-10-16', goal: 'Login' }]
export const jiraImported: JiraImportResult = {
  sprints_created: 2, sprints_updated: 1, issues_new: 12, issues_updated: 3, issues_unchanged: 30, skipped: 1, missing: 2, truncated: false, queued: 9, job_id: 'abc123', analysis_error: null, target_sprint: { id: 1, name: 'Sprint 1' }, matched: false,
}
