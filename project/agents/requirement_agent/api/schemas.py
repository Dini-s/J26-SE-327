"""Request and response models (pydantic) for the Component 1 API. They also produce docs/c1_openapi.json."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Health(BaseModel):
    status: str
    part_a_loaded: bool
    generation_backend: str
    generation_reachable: bool
    model: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProjectOut(BaseModel):
    id: int
    name: str
    created_at: str
    sources: int
    requirements: int


class SourceOut(BaseModel):
    id: int
    filename: str
    ext: str
    size_bytes: int
    pages: Optional[int] = None
    warnings: List[str] = []
    created_at: str


class RejectedFile(BaseModel):
    filename: str
    code: str
    message: str


class UploadResult(BaseModel):
    accepted: List[SourceOut]
    rejected: List[RejectedFile]


class GenerationCounts(BaseModel):
    total: int
    done: int
    failed: int
    queued: int
    running: int


class Job(BaseModel):
    job_id: str
    project_id: int
    stage: Literal["collect", "identify", "analyse", "improve", "share"]
    part_a_done: bool
    generation: GenerationCounts
    requirements: int = 0
    error: Optional[str] = None
    policy: str = "smart"  # generation policy of this run: smart | all | manual


class AmbiguitySummary(BaseModel):
    count: int  # Part A (ambiguity classifier): requirements labelled `defect`
    high_risk: int
    asked_by_ai: int = 0  # separate from `count`: Part A says ok, but the generation model asked for clarification


class TaskDrafts(BaseModel):
    generated: int  # state `done`: a valid draft exists
    total: int
    needs_clarification: int = 0  # the model asked questions instead of writing a draft (counted apart from `generated`)
    manual_review: int = 0
    failed: int = 0
    not_generated: int = 0  # nothing requested yet ("not generated yet")
    in_progress: int = 0  # queued + running
    queued: int = 0
    running: int = 0
    paused: bool = False  # the queue takes no new item (the one in flight finishes)
    eta_seconds: Optional[int] = None  # mean of the last 10 real latencies x remaining; null until 3 samples exist
    latency_samples: int = 0


class Summary(BaseModel):
    requirements: int
    ambiguities: AmbiguitySummary
    conflicts: int
    duplicates: int
    duplicate_groups: int
    security: int
    risk_counts: Dict[str, int]
    task_drafts: TaskDrafts
    open_findings: int
    decided: int


class Flags(BaseModel):
    ambiguity: bool
    conflict: bool
    duplicate: bool
    security: bool


class RequirementRow(BaseModel):
    uid: str
    id: str
    text: str
    source_file: str
    page: Optional[int] = None
    paragraph: Optional[int] = None
    fr_nfr: str
    risk_level: str
    risk_score: int
    flags: Flags
    generation_state: str
    decision: Optional[str] = None


class RequirementList(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[RequirementRow]


class DecisionIn(BaseModel):
    decision: Literal["accepted", "edited", "rejected"]
    edited_text: Optional[str] = Field(default=None, max_length=5000)
    note: Optional[str] = Field(default=None, max_length=2000)


class DecisionOut(BaseModel):
    uid: str
    decision: str
    edited_text: Optional[str] = None
    note: Optional[str] = None
    updated_at: str
    history: List[Dict[str, Any]]


class GenerationOut(BaseModel):
    state: str
    message: str
    status: Optional[str] = None
    user_story: str
    technical_task: str
    acceptance_criteria: List[str]
    rationale: str
    clarification_questions: List[str]
    attempts: int
    manual_review: bool
    raw_output: str
    updated_at: Optional[str] = None
    generated_from: str = ""  # "original" | "clarified" (the user's edited text) | "" when nothing was generated
    numbers_not_in_source: List[str] = []  # numbers in the reply that the requirement text does not contain (strict check, a hint to verify)
    backend: str = ""  # which backend wrote the stored reply: ollama | replay | mock ("" = nothing generated)
    model: str = ""


class RequirementDetail(BaseModel):
    uid: str
    id: str
    project_id: int
    text: str
    original_text: str
    source: Dict[str, Any]
    classification: Dict[str, Any]
    ambiguity: Dict[str, Any]
    security: Dict[str, Any]
    duplicates: List[Dict[str, Any]]
    duplicate_group: str
    conflicts: List[Dict[str, Any]]
    risk: Dict[str, Any]
    findings: List[Dict[str, Any]]
    explanation: str
    vague_terms: List[Dict[str, Any]]  # rule-based hints {term, start, end}; separate from Part A, see api/vague.py
    generation: GenerationOut
    decision: Optional[Dict[str, Any]] = None
    decision_history: List[Dict[str, Any]]


class GenerateAllOut(BaseModel):
    queued: int


class PausedOut(BaseModel):
    paused: bool


class GenerateOut(BaseModel):
    uid: str
    generation_state: str
