# Component 1: published graph in Neo4j

**Status: PROPOSAL, pending agreement with the team (C2, C3, C4).** Every label, relationship type and property name below lives in one file,
`project/agents/requirement_agent/api/neo4j_schema.py`; renaming something is a change in that file only (the Cypher and the property maps are built from it).

## What this is
- C1 keeps its working data in sqlite (`outputs/c1_workspace/c1.db`) and keeps doing so. Neo4j is a second, **shared "published" store** for the clarified requirements.
  C1 only writes to it (one way); C1 never reads Neo4j back to run its own pipeline.
- The platform's login and project creation belong to other components. Until they are connected, C1 projects are its own (soft, never deleted): each has an
  immutable **`project_key`** (a slug; the first project's is `demo-project`) and a name. A project is published under its own key and name; a `project_id` or
  `project_name` in the request may only repeat them (else 422), so nothing is published under a made-up id.
- Same graph for the local Neo4j Desktop and for an online database later: only the URI and credentials change.

## Settings (environment, then the shared `.env`)
| Setting | C1 name (wins) | Team name | Default |
|---|---|---|---|
| URI | `C1_NEO4J_URI` | `NEO4J_URI` | none (not configured) |
| user | `C1_NEO4J_USER` | `NEO4J_USERNAME` (also `NEO4J_USER`) | none |
| password | `C1_NEO4J_PASSWORD` | `NEO4J_PASSWORD` | none |
| database | `C1_NEO4J_DATABASE` | `NEO4J_DATABASE` | `neo4j` |
| project id and name | the project's `project_key` and `name` (no setting) | | `demo-project`, `Core Banking Platform` |

The shared `.env` (repo root or `project/`, git-ignored) is **not** loaded into the process environment. A small reader takes only the keys above from it, and only
when they are not already in the environment; every other line (`LLM_*`, `REDIS_*`, ...) is skipped and its value is never kept, logged or returned. The password is
never printed or logged. The Python driver is an optional dependency (`neo4j==6.4.1` in `project/requirements.txt`): without it, or without Neo4j, everything else in C1 works.
Check the connection (publishes nothing): `.venv\Scripts\python.exe scripts\check_c1_neo4j.py`. Look at the result with the read-only queries in `scripts/c1_neo4j_queries.cypher`.

## Graph (every node carries `project_id`, `produced_by = "c1"`, `schema_version = "c1.neo4j.v1-proposal"`)
```
(Project)-[:HAS_SOURCE]->(SourceDocument)-[:CONTAINS]->(Requirement)-[:HAS_ISSUE]->(Issue)
                                                        (Requirement)-[:HAS_DRAFT]->(TaskDraft)
                                                        (Requirement)-[:DUPLICATE_OF {score}]->(Requirement)
(Project)-[:HAS_SPRINT]->(Sprint)
(Requirement)-[:PLANNED_IN]->(Sprint)                                          <- from the requirement's effective sprint
(Sprint)-[:INCLUDES_SOURCE {requirements}]->(SourceDocument)                   <- derived on every sync
```
| Label | Properties |
|---|---|
| `Project` | `project_id`, `name` |
| `SourceDocument` | `source_id`, `project_id`, `filename`, `source_type` (`srs` | `brd` | `other` | `jira`; a Jira document is named `Jira · KEY` and holds the issues imported from that Jira project), `sha256` (of the uploaded file, for a Jira document of the imported issue texts; the file itself is never sent)\| `brd` \| `other`), `sha256` (of the uploaded file; the file itself is never sent), `uploaded_at`, `active` |
| `Requirement` | `req_id`, `project_id`, `text` (original), `kind` (`FR` \| `NFR`), `status` (`pending` \| `accepted` \| `edited` \| `rejected`), `final_text` (the edited text for `edited`, otherwise the original), `security_flag`, `sprint_id` (graph id of its effective sprint, or null), `active`, `published_at`, `payload_json` |
| `Issue` | `issue_id`, `project_id`, `type` (`ambiguity` \| `vague` \| `security` \| `risk`), `detail`, `raised_by` (`part_a` \| `rule` \| `ai`), `active` |
| `TaskDraft` | `draft_id`, `project_id`, `user_story`, `technical_task`, `acceptance_criteria` (list of strings), `rationale`, `needs_clarification`, `clarification_questions` (list of strings), `generated_by` (model), `generated_on` (`device` \| `cloud`), `endpoint_host` (host name only), `active` |
| `Sprint` | `sprint_id`, `project_id`, `name`, `goal`, `start`, `end`, `origin` (`manual` \| `detected` \| `jira`), `is_current`, `active` |
| `HAS_SPRINT`, `PLANNED_IN` | `active` on `PLANNED_IN` (see below) |
| `INCLUDES_SOURCE` | `requirements` (how many requirements of that document are planned in that sprint), `project_id`, `active` |
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
| `Project.project_id` | the project's `project_key` (unique, never changes) | `demo-project` |
| `SourceDocument.source_id` | `<project_id>:src<workspace source id>` | `demo-project:src3` |
| `Requirement.req_id` | `<source_id>:<workspace requirement id>` = `<project_id>:src<source id>:<REQ-nnn>` | `demo-project:src3:REQ-012` |
| `Issue.issue_id` | `<req_id>:<type>:<raised_by>` (vague: `<req_id>:vague:<term>`) | `demo-project:src3:REQ-012:risk:rule` |
| `TaskDraft.draft_id` | `<req_id>:draft` | `demo-project:src3:REQ-012:draft` |
| `DUPLICATE_OF.dup_id` | `<later req_id>\|<earlier req_id>` | |
| `Sprint.sprint_id` | `<project_id>:sprint<workspace sprint id>` | `demo-project:sprint4` |
| `Phase.phase_id` | `<project_id>:phase<workspace phase id>` | `demo-project:phase2` |

The workspace requirement id (`REQ-nnn`) is kept when a requirement's text and source are unchanged across re-analysis, so ids stay stable while the workspace lives. If a source
is removed and uploaded again it gets a new workspace id, so its requirements get new `req_id`s and the old nodes become `active = false`.

## Constraints and indexes (created on the first publish and by `check_c1_neo4j.py`, all `IF NOT EXISTS`)
Uniqueness on `Project.project_id`, `SourceDocument.source_id`, `Requirement.req_id`, `Issue.issue_id`, `TaskDraft.draft_id` and `Sprint.sprint_id`; indexes on `Requirement.project_id`, `Requirement.status` and `Sprint.project_id`.

## Publish semantics
- **API.** `POST /api/projects/{pid}/publish/neo4j` (optional body `{"project_id", "project_name"}` that must equal the project's key and name) and `GET /api/projects/{pid}/publish/neo4j` (status), see `c1_api_contract.md`.
- **Idempotent.** Every node is `MERGE`d by its id and its properties are set again; publishing twice creates no duplicates.
- **What is sent.** Source metadata (no bytes), requirements with the one current human decision and `final_text` (replaced or removed decisions stay in C1's internal audit table and are never sent), issues, task drafts with provenance, duplicate links.
- **Sprints.** The project's sprints are sent with every publish. The effective sprint of a requirement (its own, else its document's) becomes one `PLANNED_IN` link; `Sprint.is_current` marks the project's current sprint. A sprint that was deleted gets `active = false` (and `is_current = false`). A link that no longer holds (a requirement moved to another sprint) is not deleted: it gets `active = false`, and the current link `active = true`. Readers take the `PLANNED_IN` link with `coalesce(active, true) = true`.
- **Sprint to document.** `(Sprint)-[:INCLUDES_SOURCE {requirements}]->(SourceDocument)` is derived from the `PLANNED_IN` data on every sync: `requirements` is the number of requirements of that document whose effective sprint is that sprint. When the number drops to 0 the link gets `active = false` and `requirements = 0` (it is not deleted); when requirements come back it is `active = true` again. Only documents that are in the graph appear.
- **No phases.** Phases stay in the C1 workspace only: no `Phase` node and no `IN_PHASE` link are published (the older proposal had them; nodes already written by it are left alone, nothing is deleted).
- **Only published documents.** The user publishes documents (`POST /api/projects/{pid}/publish`); analysing or importing never does. Only a published document is active in the graph: its requirements, issues, task drafts, duplicate links and its `PLANNED_IN` / `INCLUDES_SOURCE` links. Unpublishing sets all of these to `active = false` on the next sync (nothing is deleted, and publishing again makes the same nodes active). `Project` and `Sprint` nodes are always synced. A published document is sent once its analysis is finished; a published document that is being analysed again keeps what the graph already holds about it (nothing is switched off) until the new result is sent. Every published document is sent in full (`scripts/c1_graph_counts.py` compares the numbers per document).
- **Downstream rule (Components 2-4).** Use a requirement only when its `SourceDocument` is published and active, its `status` is `accepted` or `edited`, and the requirement itself is `active`. `INCLUDES_SOURCE` counts only published documents.
- **Project name.** `Project.name` is set from the workspace on every sync, so a rename reaches the graph (the project id, its key, never changes).
- **Automatic.** The API publishes in the background after changes (`GET /api/projects/{pid}/sync`, `C1_AUTO_SYNC=0` switches it off); the publish is the same idempotent one, so syncing often is harmless.
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
Names of labels, relationships and properties; whether `Project` is owned by the platform (C1 sets `Project.name` from the workspace on every sync); `req_id` stability across a removed and re-uploaded source;
whether conflicts, risk and Part A probabilities should be flat properties (today they are in `payload_json` only); who sets `Sprint` data; the `active` filter convention.
