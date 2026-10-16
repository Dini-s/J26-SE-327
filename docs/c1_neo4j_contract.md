# Component 1: published graph in Neo4j

**Status: PROPOSAL, pending agreement with the team (C2, C3, C4).** Every label, relationship type and property name below lives in one file,
`project/agents/requirement_agent/api/neo4j_schema.py`; renaming something is a change in that file only (the Cypher and the property maps are built from it).

## What this is
- C1 keeps its working data in sqlite (`outputs/c1_workspace/c1.db`) and keeps doing so. Neo4j is a second, **shared "published" store** for the clarified requirements.
  C1 only writes to it (one way); C1 never reads Neo4j back to run its own pipeline.
- The platform's login and project creation belong to other components. C1 receives a **project id**; until that exists it uses a stub: `C1_PROJECT_ID`
  (default `demo-project`) and `C1_PROJECT_NAME` (default `Core Banking Platform`). `POST` publish may carry an optional `project_id`.
- Same graph for the local Neo4j Desktop and for an online database later: only the URI and credentials change.

## Settings (environment, then the shared `.env`)
| Setting | C1 name (wins) | Team name | Default |
|---|---|---|---|
| URI | `C1_NEO4J_URI` | `NEO4J_URI` | none (not configured) |
| user | `C1_NEO4J_USER` | `NEO4J_USERNAME` (also `NEO4J_USER`) | none |
| password | `C1_NEO4J_PASSWORD` | `NEO4J_PASSWORD` | none |
| database | `C1_NEO4J_DATABASE` | `NEO4J_DATABASE` | `neo4j` |
| platform project | `C1_PROJECT_ID`, `C1_PROJECT_NAME` | | `demo-project`, `Core Banking Platform` |

The shared `.env` (repo root or `project/`, git-ignored) is **not** loaded into the process environment. A small reader takes only the keys above from it, and only
when they are not already in the environment; every other line (`LLM_*`, `REDIS_*`, ...) is skipped and its value is never kept, logged or returned. The password is
never printed or logged. The Python driver is an optional dependency (`neo4j==6.4.1` in `project/requirements.txt`): without it, or without Neo4j, everything else in C1 works.
Check the connection (publishes nothing): `.venv\Scripts\python.exe scripts\check_c1_neo4j.py`. Look at the result with the read-only queries in `scripts/c1_neo4j_queries.cypher`.

## Graph (every node carries `project_id`, `produced_by = "c1"`, `schema_version = "c1.neo4j.v1-proposal"`)
```
(Project)-[:HAS_SOURCE]->(SourceDocument)-[:CONTAINS]->(Requirement)-[:HAS_ISSUE]->(Issue)
                                                        (Requirement)-[:HAS_DRAFT]->(TaskDraft)
                                                        (Requirement)-[:DUPLICATE_OF {score}]->(Requirement)
(Project)-[:HAS_SPRINT]->(Sprint) , (Requirement)-[:PLANNED_IN]->(Sprint)     <- constants and constraint only, not written by C1 yet
```
| Label | Properties |
|---|---|
| `Project` | `project_id`, `name` |
| `SourceDocument` | `source_id`, `project_id`, `filename`, `source_type` (`srs` \| `brd` \| `other`), `sha256` (of the uploaded file; the file itself is never sent), `uploaded_at`, `active` |
| `Requirement` | `req_id`, `project_id`, `text` (original), `kind` (`FR` \| `NFR`), `status` (`pending` \| `accepted` \| `edited` \| `rejected`), `final_text` (the edited text for `edited`, otherwise the original), `security_flag`, `active`, `published_at`, `payload_json` |
| `Issue` | `issue_id`, `project_id`, `type` (`ambiguity` \| `vague` \| `security` \| `risk`), `detail`, `raised_by` (`part_a` \| `rule` \| `ai`), `active` |
| `TaskDraft` | `draft_id`, `project_id`, `user_story`, `technical_task`, `acceptance_criteria` (list of strings), `rationale`, `needs_clarification`, `clarification_questions` (list of strings), `generated_by` (model), `generated_on` (`device` \| `cloud`), `endpoint_host` (host name only), `active` |
| `Sprint` | `sprint_id`, `project_id`, `name`, `goal`, `start`, `end`, `origin` (not written yet) |
| `DUPLICATE_OF` | `dup_id`, `score`, `project_id`, `active` |

There are **no RVU nodes** (Component 3 owns those). Conflicts (rule-based candidates) are not published in this proposal.
Lists are native Neo4j string lists. Nested maps are never stored as properties: they stay inside `payload_json`.

`Requirement.payload_json` is a string holding the full `c1.clarified_requirements.v1` record of that requirement (the same record as in the JSON export,
see `c1_api_contract.md`, wrapped as `{"schema_version", "project": {"id", "name"}, "requirement": {...}}`), with two additions: `requirement.status` and
`requirement.source.source_id/source_type`, and `requirement.draft.provenance` (`model`, `backend`, `generated_on`, `endpoint_host`). It is the lossless hand-off: if a flat property is renamed later, the payload still has everything.
It never contains a cloud address, a path or a key.

**Issues.** `ambiguity`/`part_a`: Part A labelled the requirement `defect`. `vague`/`rule`: a term of the rule-based list (one issue per distinct term). `security`/`part_a`:
the Part A security keyword flag. `risk`/`rule`: the unvalidated risk heuristic when it is not NONE. `ambiguity`/`ai`: the model asked for clarification. These are hints, not verified findings.

## Ids
| Id | Rule | Example |
|---|---|---|
| `Project.project_id` | the platform project id (`C1_PROJECT_ID`) | `demo-project` |
| `SourceDocument.source_id` | `<project_id>:src<workspace source id>` | `demo-project:src3` |
| `Requirement.req_id` | `<source_id>:<workspace requirement id>` = `<project_id>:src<source id>:<REQ-nnn>` | `demo-project:src3:REQ-012` |
| `Issue.issue_id` | `<req_id>:<type>:<raised_by>` (vague: `<req_id>:vague:<term>`) | `demo-project:src3:REQ-012:risk:rule` |
| `TaskDraft.draft_id` | `<req_id>:draft` | `demo-project:src3:REQ-012:draft` |
| `DUPLICATE_OF.dup_id` | `<later req_id>\|<earlier req_id>` | |

The workspace requirement id (`REQ-nnn`) is kept when a requirement's text and source are unchanged across re-analysis, so ids stay stable while the workspace lives. If a source
is removed and uploaded again it gets a new workspace id, so its requirements get new `req_id`s and the old nodes become `active = false`.

## Constraints and indexes (created on the first publish and by `check_c1_neo4j.py`, all `IF NOT EXISTS`)
Uniqueness on `Project.project_id`, `SourceDocument.source_id`, `Requirement.req_id`, `Issue.issue_id`, `TaskDraft.draft_id`, `Sprint.sprint_id`; indexes on `Requirement.project_id` and `Requirement.status`.

## Publish semantics
- **API.** `POST /api/projects/{pid}/publish/neo4j` (optional body `{"project_id", "project_name"}`) and `GET /api/projects/{pid}/publish/neo4j` (status), see `c1_api_contract.md`.
- **Idempotent.** Every node is `MERGE`d by its id and its properties are set again; publishing twice creates no duplicates.
- **What is sent.** Source metadata (no bytes), requirements with the human decision and `final_text`, issues, task drafts with provenance, duplicate links.
- **Removed items.** What is no longer in the workspace (a deleted source, a requirement dropped by re-analysis, a draft that no longer exists, a duplicate link that is gone) gets `active = false`. Nothing is ever deleted.
  Readers must filter on `active`.
- **Transactions.** One transaction per source (its project node, source, requirements, issues, drafts in `UNWIND` batches of 500), then one transaction for the duplicate links and the deactivation sweep.
  If a later transaction fails, the earlier ones stay (they are consistent and the next publish repeats them harmlessly); the publish is then not recorded as successful.
- **Out of date.** The API hashes everything a publish would send (without the publish time) and compares it with the hash stored in the sqlite table `publish_log` at the last successful publish.
- **Errors** (HTTP 503, plain message, no credentials, no stack trace): `neo4j_unconfigured`, `neo4j_driver_missing`, `neo4j_unreachable` (5 s timeouts), `neo4j_auth_failed`, and `neo4j_publish_failed` (any other error from Neo4j). A second publish while one runs gets 409 `publish_in_progress`.

## Example Cypher for C2, C3, C4
```cypher
// approved requirements of a project (what to build on)
MATCH (r:Requirement {project_id: $project_id})
WHERE r.status IN ['accepted', 'edited'] AND r.active
RETURN r.req_id, r.kind, r.final_text;

// the lossless record of one requirement
MATCH (r:Requirement {req_id: $req_id}) RETURN r.payload_json;   // a JSON string: parse it in the client

// approved requirements with their task draft
MATCH (r:Requirement {project_id: $project_id})
WHERE r.status IN ['accepted', 'edited'] AND r.active
OPTIONAL MATCH (r)-[:HAS_DRAFT]->(d:TaskDraft) WHERE d.active
RETURN r.req_id, r.final_text, d.user_story, d.technical_task, d.acceptance_criteria, d.generated_by, d.generated_on;

// security requirements that are still undecided
MATCH (r:Requirement {project_id: $project_id, status: 'pending'})
WHERE r.active AND r.security_flag RETURN r.req_id, r.text;

// duplicates of an approved requirement
MATCH (a:Requirement {project_id: $project_id})-[d:DUPLICATE_OF]->(b:Requirement)
WHERE d.active AND a.active AND b.active RETURN a.req_id, b.req_id, d.score;
```

## Open points for the team
Names of labels, relationships and properties; whether `Project` is owned by the platform (C1 only `MERGE`s it and does not overwrite an existing name); `req_id` stability across a removed and re-uploaded source;
whether conflicts, risk and Part A probabilities should be flat properties (today they are in `payload_json` only); who sets `Sprint` data; the `active` filter convention.
