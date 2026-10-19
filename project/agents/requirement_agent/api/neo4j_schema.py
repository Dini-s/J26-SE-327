"""Names of the published Neo4j graph: every label, relationship type and property name lives here and nowhere else.

PROPOSAL, NOT YET AGREED WITH THE TEAM (docs/c1_neo4j_contract.md). Renaming something later is a change in this file only: the Cypher in
neo4j_store.py is built from these constants and the property maps are built with them.
"""

SCHEMA_VERSION = "c1.neo4j.v1-proposal"  # on every node: lets readers see which proposal wrote it
PAYLOAD_SCHEMA_VERSION = "c1.clarified_requirements.v1"  # the record inside Requirement.payload_json (see docs/c1_api_contract.md)
PRODUCED_BY = "c1"


class Label:
    PROJECT = "Project"
    SOURCE = "SourceDocument"
    REQUIREMENT = "Requirement"
    ISSUE = "Issue"
    DRAFT = "TaskDraft"
    SPRINT = "Sprint"


class Rel:
    HAS_SOURCE = "HAS_SOURCE"
    CONTAINS = "CONTAINS"
    HAS_ISSUE = "HAS_ISSUE"
    HAS_DRAFT = "HAS_DRAFT"
    DUPLICATE_OF = "DUPLICATE_OF"
    HAS_SPRINT = "HAS_SPRINT"  # (Project)-[:HAS_SPRINT]->(Sprint)
    PLANNED_IN = "PLANNED_IN"  # (Requirement)-[:PLANNED_IN]->(Sprint), from the requirement's effective sprint
    INCLUDES_SOURCE = "INCLUDES_SOURCE"  # (Sprint)-[:INCLUDES_SOURCE {requirements}]->(SourceDocument), derived on every sync


class Common:
    """On every node."""
    PROJECT_ID = "project_id"
    PRODUCED_BY = "produced_by"
    SCHEMA_VERSION = "schema_version"


class ProjectP:
    ID = Common.PROJECT_ID
    NAME = "name"


class SourceP:
    ID = "source_id"
    FILENAME = "filename"
    SOURCE_TYPE = "source_type"
    SHA256 = "sha256"
    UPLOADED_AT = "uploaded_at"
    ACTIVE = "active"


class RequirementP:
    ID = "req_id"
    TEXT = "text"
    KIND = "kind"
    STATUS = "status"
    FINAL_TEXT = "final_text"
    SECURITY_FLAG = "security_flag"
    SPRINT_ID = "sprint_id"  # the graph id of its effective sprint, or null
    ACTIVE = "active"
    PUBLISHED_AT = "published_at"
    PAYLOAD_JSON = "payload_json"


class IssueP:
    ID = "issue_id"
    TYPE = "type"
    DETAIL = "detail"
    RAISED_BY = "raised_by"
    ACTIVE = "active"


class DraftP:
    ID = "draft_id"
    USER_STORY = "user_story"
    TECHNICAL_TASK = "technical_task"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"  # native list of strings
    RATIONALE = "rationale"
    NEEDS_CLARIFICATION = "needs_clarification"
    CLARIFICATION_QUESTIONS = "clarification_questions"  # native list of strings
    GENERATED_BY = "generated_by"  # the model
    GENERATED_ON = "generated_on"  # device | cloud
    ENDPOINT_HOST = "endpoint_host"  # host name only, never an address or a key
    ACTIVE = "active"


class DuplicateP:
    ID = "dup_id"
    SCORE = "score"
    ACTIVE = "active"


class IncludesP:
    REQUIREMENTS = "requirements"  # how many requirements of that document are planned in that sprint
    ACTIVE = "active"


class SprintP:
    ID = "sprint_id"
    NAME = "name"
    GOAL = "goal"
    START = "start"
    END = "end"
    ORIGIN = "origin"  # manual | detected | jira
    IS_CURRENT = "is_current"
    ACTIVE = "active"


# values
STATUSES = ("pending", "accepted", "edited", "rejected")
APPROVED_STATUSES = ("accepted", "edited")  # what C2-C4 read as "approved" (together with active = true)
SOURCE_TYPES = ("srs", "brd", "other", "jira")
UPLOAD_SOURCE_TYPES = ("srs", "brd", "other")  # what a file upload may say; `jira` documents only come from the Jira import
DEFAULT_SOURCE_TYPE = "srs"
ISSUE_TYPES = ("ambiguity", "vague", "security", "risk")
RAISED_BY = ("part_a", "rule", "ai")

# one uniqueness constraint per id; indexes for the common queries
UNIQUE_IDS = (
    (Label.PROJECT, ProjectP.ID),
    (Label.SOURCE, SourceP.ID),
    (Label.REQUIREMENT, RequirementP.ID),
    (Label.ISSUE, IssueP.ID),
    (Label.DRAFT, DraftP.ID),
    (Label.SPRINT, SprintP.ID),
)
INDEXES = (
    (Label.REQUIREMENT, Common.PROJECT_ID),
    (Label.REQUIREMENT, RequirementP.STATUS),
    (Label.SPRINT, Common.PROJECT_ID),
)
