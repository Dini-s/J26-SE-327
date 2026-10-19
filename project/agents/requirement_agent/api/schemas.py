"""Request and response models (pydantic) for the Component 1 API. They also produce docs/c1_openapi.json."""
from typing import Any, Dict, List, Literal, Optional, Union

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
    generation_target: str = "device"  # where drafts are generated now: device | cloud (see /api/engine)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)  # 2-80 characters after trimming; unique among projects that are not archived


class ProjectRename(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class DecisionCounts(BaseModel):
    accepted: int
    edited: int
    rejected: int
    pending: int  # no decision yet


class ProjectOut(BaseModel):
    id: int
    project_key: str  # slug, unique and immutable; the project id in the shared graph
    name: str
    archived: bool
    created_at: str
    sources: int
    requirements: int
    decisions: DecisionCounts
    last_analysis_at: Optional[str] = None
    last_published_at: Optional[str] = None
    out_of_date: bool  # true when nothing was published yet or the project changed since the last publish


class SourceOut(BaseModel):
    id: int
    filename: str
    ext: str
    size_bytes: int
    pages: Optional[int] = None
    warnings: List[str] = []
    created_at: str
    uploaded_at: str  # same moment as created_at
    source_type: str = "srs"  # srs | brd | other
    default_sprint_id: Optional[int] = None  # the sprint the document's requirements follow unless one is assigned directly
    analysis_state: Literal["not_analyzed", "analyzing", "analyzed", "failed"] = "not_analyzed"
    analyzed_at: Optional[str] = None
    published: bool = False  # shared with the other components (the user publishes documents; analysing or importing never does)
    published_at: Optional[str] = None
    requirements: int = 0
    ambiguities: int = 0
    drafts: "SourceDrafts"
    sprints: List["SourceSprintCount"] = []  # where its requirements are, by effective sprint


class SourceDrafts(BaseModel):
    ready: int
    needs_clarification: int
    failed: int


class SourceSprintCount(BaseModel):
    sprint_id: Optional[int] = None
    count: int


class RejectedFile(BaseModel):
    filename: str
    code: str
    message: str


class DetectedSprint(BaseModel):
    filename: str
    sprint_id: int
    name: str
    confirmed: bool  # false = proposed from the file name or first page; confirm it with PATCH /sprints/{id}


class UploadResult(BaseModel):
    accepted: List[SourceOut]
    rejected: List[RejectedFile]
    sprint_detected: bool  # true when at least one document named a sprint ("Sprint 3", "Iteration 2"); otherwise the chosen or current sprint was used
    detected: List[DetectedSprint] = []


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
    count: int  # requirements the ambiguity check labelled `defect`
    high_risk: int
    asked_by_ai: int = 0  # separate from `count`: the ambiguity check says ok, but the writing model asked for clarification


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
    paused_reason: Optional[str] = None  # "cloud_unreachable" when the queue paused itself after 3 cloud connection failures in a row
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


class Suggestion(BaseModel):
    """Rule-based hint, computed on every request and never stored: accept | edit | reject, with the reasons in plain words."""
    action: Literal["accept", "edit", "reject"]
    reasons: List[str]


class JiraRef(BaseModel):
    """Where an imported requirement comes from. `url` is the issue in the Jira site (empty when the site is not known)."""
    key: str
    type: str
    status: str
    url: str


class RequirementRow(BaseModel):
    sprint_id: Optional[int] = None  # effective sprint: the requirement's own, else its document's default
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
    failure_reason: Optional[str] = None  # when generation_state is `failed`: why, as a short code (see GenerationOut.failure_reason)
    decision: Optional[str] = None
    suggestion: Suggestion
    jira: Optional[JiraRef] = None  # set for requirements imported from Jira


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
    history: List[Dict[str, Any]] = Field(default=[], json_schema_extra={"deprecated": True})  # deprecated: only the current decision, kept for older clients


class DecisionState(BaseModel):
    """GET of the one current decision; `decision` is "pending" (and the rest null) while nothing is decided."""
    uid: str
    decision: Literal["accepted", "edited", "rejected", "pending"]
    edited_text: Optional[str] = None
    note: Optional[str] = None
    updated_at: Optional[str] = None


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
    generated_on: str = ""  # "device" | "cloud": where the reply was made (a cached reply keeps the place it was made)
    endpoint_host: Optional[str] = None  # host name of the cloud server, never the full address; null for the device
    failure_reason: Optional[str] = None  # state `failed` only: engine_unavailable | engine_skipped | cloud_unreachable | cloud_rejected | not_in_replay | engine_not_ready | unexpected | unknown


class RequirementDetail(BaseModel):
    jira: Optional[JiraRef] = None  # set for requirements imported from Jira
    sprint_id: Optional[int] = None  # effective sprint
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
    vague_terms: List[Dict[str, Any]]  # rule-based hints {term, start, end}; separate from the ambiguity check, see api/vague.py
    generation: GenerationOut
    suggestion: Suggestion
    decision: Optional[Dict[str, Any]] = None
    decision_history: List[Dict[str, Any]] = Field(default=[], json_schema_extra={"deprecated": True})  # deprecated: only the current decision


class EngineUpdate(BaseModel):
    """Partial update: only the fields that are sent change. `cloud_api_key` is write-only ("" removes it)."""
    target: Optional[Literal["device", "cloud"]] = None
    cloud_url: Optional[str] = Field(default=None, max_length=2000)
    cloud_api_key: Optional[str] = Field(default=None, max_length=1000)
    cloud_model: Optional[str] = Field(default=None, max_length=200)
    cloud_concurrency: Optional[int] = Field(default=None, ge=1, le=8)
    cloud_consent: Optional[bool] = None


class EngineTestIn(BaseModel):
    target: Literal["device", "cloud"]


class EngineTestOut(BaseModel):
    ok: bool
    detail: str  # never contains the address or the key
    latency_ms: Optional[int] = None


class DeviceEngine(BaseModel):
    backend: str
    model: str
    reachable: bool
    concurrency: int


class CloudEngine(BaseModel):
    configured: bool
    host: Optional[str] = None  # host name only
    model: str
    concurrency: int
    consent: bool
    consent_at: Optional[str] = None
    reachable: Optional[bool] = None  # result of the last connection test of the CURRENT settings; null = not tested
    last_tested_at: Optional[str] = None


class EngineOut(BaseModel):
    target: Literal["device", "cloud"]
    cloud_available: bool
    cloud_disabled_reason: Optional[str] = None
    device: DeviceEngine
    cloud: CloudEngine


class PublishIn(BaseModel):
    """Optional and only a check: a project is always published under its own key and name, so these may be omitted or must equal them (else 422)."""
    project_id: Optional[str] = Field(default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    project_name: Optional[str] = Field(default=None, min_length=1, max_length=200)


class PublishOut(BaseModel):
    project_id: str
    published_at: str
    seconds: float
    counts: Dict[str, int]  # nodes/links sent, per label or relationship type
    deactivated: Dict[str, int]  # items set active=false because they are no longer in the workspace
    content_hash: str


class PublishDocsIn(BaseModel):
    """Publish or unpublish documents: the listed ones, every analysed document of a sprint, or both."""
    document_ids: Optional[List[int]] = Field(default=None, max_length=1000)
    sprint_id: Optional[int] = None


class DocChanged(BaseModel):
    document_id: int
    name: str


class DocSkipped(BaseModel):
    document_id: int
    name: str
    reason: Literal["not_found", "not_analyzed", "analyzing", "failed", "no_requirements", "already_published", "not_published"]
    message: str


class PublishSync(BaseModel):
    """What happened to the sync that runs right after: `synced`, `not_configured` (nothing to sync with) or `retrying` (it will be tried again by itself)."""
    state: Literal["synced", "not_configured", "retrying"]
    error: Optional[str] = None


class PublishDocsOut(BaseModel):
    action: Literal["publish", "unpublish"]
    changed: List[DocChanged]
    skipped: List[DocSkipped]
    published_documents: int
    total_documents: int
    sync: PublishSync


class DocDecided(BaseModel):
    accepted: int
    edited: int
    rejected: int
    pending: int


class DocFindings(BaseModel):
    ambiguity: int
    conflict: int
    duplicate: int
    security: int


class SprintDocRow(BaseModel):
    document_id: int
    name: str
    source: Literal["file", "jira"]
    requirements: int  # the ones that are in this sprint
    fr: int
    nfr: int
    unclassified: int
    ready: int
    needs_clarification: int
    failed: int
    not_written: int
    decided: DocDecided
    findings: DocFindings
    analysis_state: Literal["not_analyzed", "analyzing", "analyzed", "failed"]
    publish_state: Literal["not_published", "published", "syncing", "sync_error"]
    published_at: Optional[str] = None


class SprintSummary(BaseModel):
    sprint_id: int
    name: str
    is_current: bool
    documents: int
    published: int
    requirements: int
    fr: int
    nfr: int
    ready: int
    needs_clarification: int
    failed: int
    not_written: int
    decided: DocDecided
    rows: List[SprintDocRow]


class PublishStatus(BaseModel):
    configured: bool
    reachable: bool
    project_id: str
    host: Optional[str] = None  # host name only
    database: Optional[str] = None
    server_version: Optional[str] = None
    last_published_at: Optional[str] = None
    last_counts: Optional[Dict[str, int]] = None
    out_of_date: bool  # true when nothing was published yet or the workspace changed since the last successful publish
    error: Optional[str] = None  # neo4j_unconfigured | neo4j_driver_missing | neo4j_unreachable | neo4j_auth_failed
    message: Optional[str] = None


class GenerateAllOut(BaseModel):
    queued: int


class PausedOut(BaseModel):
    paused: bool


class GenerateOut(BaseModel):
    uid: str
    generation_state: str


class AmbiguityOverview(BaseModel):
    total: int
    detected: int  # found by the ambiguity check (Summary.ambiguities.count)
    asked_by_ai: int  # the check said ok, but the writing model asked for clarification


class DraftOverview(BaseModel):
    total: int
    done: int
    ready: int  # the same number as `done`, under the name the pipeline uses
    needs_clarification: int
    waiting: int  # queued or running
    failed: int
    not_generated: int
    manual_review: int


class DecisionOverview(DecisionCounts):
    decided: int  # accepted + edited + rejected
    percent_decided: float  # 0-100, one decimal; 0 when there are no requirements


class SourcesOverview(BaseModel):
    count: int
    by_type: Dict[str, int]
    total_size_bytes: int
    latest_upload_at: Optional[str] = None


class GenerationOverview(BaseModel):
    state: Literal["idle", "running", "paused"]
    target: str  # device | cloud
    in_progress: int
    paused_reason: Optional[str] = None
    eta_seconds: Optional[int] = None


class OverviewProject(BaseModel):
    id: int
    project_key: str
    name: str
    archived: bool


class OverviewCounts(BaseModel):
    requirements: int
    ambiguities: AmbiguityOverview
    conflicts: int
    duplicates: int
    drafts: DraftOverview


class GraphOverview(BaseModel):
    """Publish status as in PublishStatus; when the graph cannot be reached `reachable` is false and `error` says why (the call itself does not fail)."""
    configured: bool
    reachable: bool
    project_id: str
    last_published_at: Optional[str] = None
    out_of_date: bool
    error: Optional[str] = None
    message: Optional[str] = None


class SyncStatus(BaseModel):
    """Background sync of the project to the graph database. `pending` and `retrying` come with `next_attempt_at`."""
    state: Literal["synced", "syncing", "pending", "retrying", "not_configured", "unreachable"]
    enabled: bool  # false when C1_AUTO_SYNC=0
    last_synced_at: Optional[str] = None
    counts: Optional[Dict[str, int]] = None
    next_attempt_at: Optional[str] = None
    error: Optional[str] = None  # neo4j_unreachable | neo4j_auth_failed | neo4j_publish_failed | neo4j_driver_missing


class PlanDecisions(BaseModel):
    total: int
    accepted: int
    edited: int
    rejected: int
    pending: int  # "needs review"


class SprintDecisions(PlanDecisions):
    sprint_id: int
    name: str
    phase_id: Optional[int] = None
    is_current: bool


class PhaseDecisions(PlanDecisions):
    phase_id: Optional[int] = None  # null = sprints that are in no phase
    name: Optional[str] = None
    sprints: int


class CurrentSprint(BaseModel):
    id: int
    name: str
    phase_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    goal: Optional[str] = None
    requirements: int
    pending: int
    decided: int
    percent_decided: float


class CurrentPhase(BaseModel):
    id: int
    name: str
    sprints: int
    requirements: int
    pending: int
    decided: int
    percent_decided: float


class FindingsByType(BaseModel):
    ambiguity: int
    conflict: int  # pairs
    duplicate: int  # pairs
    security: int


class AnalysisOverview(BaseModel):
    ready: int  # documents that are analysed
    total: int


StageState = Literal["done", "active", "waiting", "failed"]


class PipelineCollect(BaseModel):
    state: StageState
    documents: int


class PipelineIdentify(BaseModel):
    state: StageState
    documents: int
    requirements: int


class PipelineAnalyse(BaseModel):
    state: StageState
    analysed: int  # documents that are analysed
    total: int  # documents
    failed: int  # documents whose analysis failed


class PipelineDrafts(BaseModel):
    ready: int
    needs_clarification: int
    failed: int
    waiting: int


class PipelineImprove(BaseModel):
    state: Literal["done", "active", "waiting", "attention", "failed"]  # `attention`: some drafts failed and the rest works; `failed`: every draft failed
    requirements: int
    decided: int  # accepted + edited + rejected
    drafts_written: int  # ready + needs_clarification
    drafts: PipelineDrafts


class PipelineShare(BaseModel):
    state: StageState
    published: int = 0  # documents the user has published
    documents: int = 0
    sync_state: Literal["synced", "syncing", "pending", "retrying", "not_configured", "unreachable"]
    last_synced_at: Optional[str] = None


class Pipeline(BaseModel):
    """Where the project stands, in five stages; each has a state and the numbers behind it."""
    collect: PipelineCollect
    identify: PipelineIdentify
    analyse: PipelineAnalyse
    improve: PipelineImprove
    share: PipelineShare


class Overview(BaseModel):
    project: OverviewProject
    counts: OverviewCounts
    decisions: DecisionOverview
    sources: SourcesOverview
    last_analysis_at: Optional[str] = None
    generation: GenerationOverview
    neo4j: GraphOverview
    current_sprint: Optional[CurrentSprint] = None
    current_phase: Optional[CurrentPhase] = None
    by_sprint: List[SprintDecisions] = []
    by_phase: List[PhaseDecisions] = []
    findings_by_type: FindingsByType
    latest_uploads: List[SourceOut] = []  # the 5 newest documents, with the same stats as the document list
    analysis: AnalysisOverview
    sync: SyncStatus
    pipeline: Pipeline


# ------------------------------------------------------------------------------------------------------------------ planning
class PhaseIn(BaseModel):
    name: str = Field(max_length=200)


class PhaseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    position: Optional[int] = None


class PhaseOut(BaseModel):
    id: int
    project_id: int
    name: str
    position: int
    sprints: int


class SprintIn(BaseModel):
    name: str = Field(max_length=200)
    phase_id: Optional[int] = None
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None
    goal: Optional[str] = Field(default=None, max_length=2000)
    origin: Literal["manual", "detected", "jira"] = "manual"
    external_id: Optional[str] = Field(default=None, max_length=200)


class SprintUpdate(BaseModel):
    """Send only what changes; `phase_id: null` takes the sprint out of its phase."""
    name: Optional[str] = Field(default=None, max_length=200)
    phase_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    goal: Optional[str] = Field(default=None, max_length=2000)
    position: Optional[int] = None
    confirmed: Optional[bool] = None


class SprintOut(BaseModel):
    id: int
    project_id: int
    phase_id: Optional[int] = None
    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    goal: Optional[str] = None
    origin: Literal["manual", "detected", "jira"]
    confirmed: bool
    external_id: Optional[str] = None
    position: int
    is_current: bool
    requirements: int  # by effective sprint
    pending: int
    documents: int  # documents whose default sprint this is


class CurrentSprintIn(BaseModel):
    sprint_id: int


class SourceSprintIn(BaseModel):
    sprint_id: int


class PageRange(BaseModel):
    from_page: int
    to_page: int
    sprint_id: int


class AssignRangesIn(BaseModel):
    ranges: List[PageRange]


class AssignRangesOut(BaseModel):
    assigned: int
    requirements: int
    without_page: int  # requirements of this document that have no page number (cannot be assigned by page)


class AssignIn(BaseModel):
    requirement_ids: List[str]  # unique ids (p1-REQ-001) or display ids (REQ-001)
    sprint_id: Optional[int] = None  # null = follow the document's default sprint again


class AssignOut(BaseModel):
    assigned: int
    sprint_id: Optional[int] = None


class SprintDeleted(BaseModel):
    deleted: int
    reassigned_to: Optional[int] = None
    requirements_moved: int


class ReanalyzeOut(BaseModel):
    source_id: int
    kept: int  # decisions and drafts stay
    changed: int  # the text changed: its decision is moved to the audit trail
    removed: int
    added: int
    queued: int  # drafts queued for the new and changed requirements
    job: Optional[Job] = None


# ------------------------------------------------------------------------------------------------------------------ jira
class JiraSite(BaseModel):
    name: str
    url: str


class JiraImportInfo(BaseModel):
    at: str
    counts: Dict[str, Any]


class JiraStatus(BaseModel):
    """`not_configured` (the server has no Jira app settings), `not_connected`, `connected`, `expired` (connect again). Tokens are never part of any response."""
    state: Literal["not_configured", "not_connected", "connected", "expired"]
    needs_reconnect: bool = False  # connected, but with fewer permissions than the import now asks for (board access): Connect again, nothing imported is lost
    site: Optional[JiraSite] = None
    connected_at: Optional[str] = None
    last_import: Optional[JiraImportInfo] = None


class JiraConnectOut(BaseModel):
    authorize_url: str


class JiraProject(BaseModel):
    key: str
    name: str


class JiraBoard(BaseModel):
    id: int
    name: str
    type: str  # scrum | kanban | simple


class JiraSprintOut(BaseModel):
    id: int
    name: str
    state: Literal["active", "future", "closed"]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    goal: Optional[str] = None


class JiraImportIn(BaseModel):
    project_key: str = Field(max_length=20)
    board_id: Optional[int] = None  # with a board: its sprints in `sprint_states` and the issues in them; without: every issue of the project
    sprint_states: Optional[List[str]] = None  # active | future | closed; default active + future
    issue_types: Optional[List[str]] = None  # default Story, Task
    set_current: bool = False  # "match" only: make the active Jira sprint the current sprint
    target_sprint_id: Optional[Union[int, Literal["match"]]] = None  # a C1 sprint id (all go there), null = the current sprint, "match" = each issue to the C1 sprint of its Jira sprint
    policy: str = "smart"  # which drafts are queued after the analysis: smart | all | manual
    analyze: bool = True  # false: only store the issues, analyse later


class JiraImportOut(BaseModel):
    sprints_created: int
    sprints_updated: int
    issues_new: int
    issues_updated: int
    issues_unchanged: int
    skipped: int  # issues without any text
    target_sprint: Optional[Dict[str, Any]] = None  # {"id", "name"}: where everything went (null with "match": each issue went to its own sprint)
    matched: bool = False  # true when "match" was used
    missing: int  # imported before, not returned this time: kept and marked, never deleted
    truncated: bool  # more issues than one import takes (2000): the rest was not read
    queued: int  # task drafts queued after the analysis
    job_id: Optional[str] = None
    analysis_error: Optional[str] = None  # an error code when the import worked but the analysis could not run
