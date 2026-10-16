import type { Engine, Generation, Health, Job, Project, RequirementDetail, RequirementRow, Source, Summary } from '../api/types'

export const health: Health = { status: 'ok', part_a_loaded: true, generation_backend: 'replay', generation_reachable: true, model: 'replay', generation_target: 'device' }
/** GET /api/engine on a fresh install: the device is ready, the cloud is not set up. */
export const engine: Engine = {
  target: 'device', cloud_available: true, cloud_disabled_reason: null,
  device: { backend: 'ollama', model: 'c1-req', reachable: true, concurrency: 1 },
  cloud: { configured: false, host: null, model: 'c1-req', concurrency: 4, consent: false, consent_at: null, reachable: null, last_tested_at: null },
}
export const project: Project = { id: 1, name: 'Core Banking Platform', created_at: '2026-10-13T06:00:00+00:00', sources: 1, requirements: 42 }
export const source: Source = { id: 1, filename: 'CoreBanking_SRS_v2.pdf', ext: '.pdf', size_bytes: 1000, pages: 12, warnings: [], created_at: '2026-10-13T06:00:00+00:00' }

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

export const rows: RequirementRow[] = [
  {
    uid: 'p1-REQ-001', id: 'REQ-001', text: 'The system should quickly notify users about suspicious logins.', source_file: 'CoreBanking_SRS_v2.pdf', page: 12, paragraph: 3,
    fr_nfr: 'NFR', risk_level: 'HIGH', risk_score: 4, flags: { ambiguity: true, conflict: false, duplicate: false, security: true }, generation_state: 'done', decision: null,
  },
  {
    uid: 'p1-REQ-002', id: 'REQ-002', text: 'A customer may update their registered mobile number without additional verification.', source_file: 'CoreBanking_SRS_v2.pdf', page: 7, paragraph: 6,
    fr_nfr: 'FR', risk_level: 'HIGH', risk_score: 4, flags: { ambiguity: false, conflict: true, duplicate: false, security: false }, generation_state: 'done', decision: null,
  },
  {
    uid: 'p1-REQ-003', id: 'REQ-003', text: 'Administrators shall be able to temporarily deactivate a customer account.', source_file: 'CoreBanking_SRS_v2.pdf', page: 10, paragraph: 2,
    fr_nfr: 'FR', risk_level: 'MEDIUM', risk_score: 2, flags: { ambiguity: false, conflict: false, duplicate: true, security: false }, generation_state: 'failed', decision: null,
  },
]

export const generationDone: Generation = {
  state: 'done', message: '', status: 'ok', user_story: 'As a customer, I want to be notified about suspicious logins, so that I can react.',
  technical_task: 'Send a notification when a suspicious login is detected.',
  acceptance_criteria: ['Given a suspicious login, when it is detected, then the user is notified.', 'Given a normal login, when it occurs, then no alert is sent.'],
  rationale: 'Role assumed: customer.', clarification_questions: [], attempts: 1, manual_review: false, raw_output: '', updated_at: '2026-10-13T06:01:00+00:00',
  numbers_not_in_source: [], generated_from: 'original', backend: 'replay', model: 'replay', generated_on: 'device', endpoint_host: null,
}

export const detail: RequirementDetail = {
  uid: 'p1-REQ-001', id: 'REQ-001', project_id: 1,
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
  generation: generationDone, decision: null, decision_history: [],
}

export const job: Job = {
  job_id: 'abc123', project_id: 1, stage: 'improve', part_a_done: true,
  generation: { total: 42, done: 10, failed: 0, queued: 32, running: 1 }, requirements: 42, error: null, policy: 'smart',
}
