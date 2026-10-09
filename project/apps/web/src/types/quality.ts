export interface AcceptanceCriterion {
  ac_id: string;
  text: string;
}

export interface Requirement {
  requirement_id: string;

  title: string;
  text: string;

  type: string;
  subtype: string;
  risk: string;

  version: number;
  source: string;

  acceptance_criteria: AcceptanceCriterion[];

  ac_count?: number;
  rvu_count?: number;
}

export interface RVU {
  rvu_id: string;

  requirement_id: string;
  ac_id: string;

  atomic_text: string;
  behavior_type: string;

  source_text: string;
  source_fragment: string;

  source_span: {
    start: number;
    end: number;
  };

  constraints: string[];

  confidence: number;

  requires_review: boolean;

  review_reason?: string | null;

  extraction_method: string;
}

export interface EvidenceProfile {
  profile_id: string;

  rvu_id: string;
  requirement_id: string;
  ac_id: string;

  requirement_type: string;
  requirement_subtype: string;

  evidence_type: string;

  required_scenarios: string[];

  preconditions: string[];
  inputs: string[];

  expected_outcomes: string[];

  required_assertions: string[];

  metric?: string | null;
  percentile?: string | null;

  operator?: string | null;
  threshold?: number | null;
  unit?: string | null;

  load?: number | null;

  duration_seconds?: number | null;

  scope?: string | null;

  support_status: string;

  support_reason?: string | null;
}

export interface RequirementDetails {
  requirement: Requirement;

  rvus: RVU[];

  profiles: EvidenceProfile[];
}

export interface CandidateMatch {
  rvu_id: string;

  evidence_id: string;
  evidence_title: string;

  evidence_type: string;

  retrieval_method: string;

  similarity_score: number;

  rank: number;

  model_name: string;

  model_version?: string | null;

  source_path: string;
  source_tool: string;

  execution_status?: string | null;

  synthetic: boolean;
}

export interface ValidationEvidence {
  evidence_id: string;

  evidence_type: string;

  title: string;
  description: string;

  preconditions: string[];
  inputs: string[];
  steps: string[];

  expected_result?: string | null;

  assertions: string[];

  class_name?: string | null;

  method_name?: string | null;

  execution_status?: string | null;

  execution_duration_ms?: number | null;

  execution_run_id?: string | null;

  metric?: string | null;

  measured_value?: number | null;

  threshold?: number | null;

  percentile?: string | null;

  load?: number | null;

  duration_seconds?: number | null;

  scope?: string | null;

  unit?: string | null;

  source_path: string;
  source_tool: string;

  source_version?: string | null;

  raw_reference?: string | null;

  synthetic: boolean;

  metadata: Record<string, unknown>;

  timestamp: string;
}

export interface OverviewStats {
  requirements: number;

  acceptance_criteria: number;

  functional_requirements: number;

  non_functional_requirements: number;

  rvus: number;

  expected_profiles: number;

  evidence_items: number;

  automated_tests: number;

  manual_tests: number;

  performance_evidence: number;
}
