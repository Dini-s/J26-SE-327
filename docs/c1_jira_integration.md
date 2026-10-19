# Component 1: Jira integration (read-only)

Connect a project to a Jira Cloud site and import sprints and issues as requirements. Nothing is ever written to Jira: the connection asks for read scopes only and
the code sends GET requests only (a test checks that). Code: `project/agents/requirement_agent/api/jira.py`; API: `docs/c1_api_contract.md` ("Jira").

## What it does
1. **Connect** (OAuth 2.0, three-legged): the user approves read access in Atlassian; C1 stores the site and the tokens in the project's own database file.
2. **Import**: pick a Jira project, optionally a board, the sprint states and the issue types. Jira sprints become sprints here (`origin = jira`), the issues become
   requirements in one virtual document per Jira project (`Jira · KEY`), one requirement per issue. The normal analysis, task drafts, review and the knowledge-graph
   sync then work on them like on any other requirement.
3. **Import again** any time: it is idempotent by issue key (see below).
4. **Disconnect**: the tokens are deleted; everything imported stays.

## Settings (names only, values go in the shared `.env` or the environment)
| Name | Default | Meaning |
|---|---|---|
| `ATLASSIAN_CLIENT_ID`, `ATLASSIAN_CLIENT_SECRET` | none | the OAuth app; without both, the status is `not_configured` |
| `ATLASSIAN_REDIRECT_URI` | `http://localhost:8000/api/integrations/jira/callback` | must equal the callback URL of the app in the Atlassian developer console |
| `C1_FRONTEND_URL` | `http://localhost:5173/requirement` | where the browser goes after the connection (`?jira=connected` or `?jira=error&reason=...`) |

Only these four names are read from the `.env` file (the same strict reader as the graph settings: no other line is kept). `ATLASSIAN_SCOPES` is **not** read: C1 always asks for
`read:jira-work read:jira-user offline_access` (classic) plus `read:board-scope:jira-software read:sprint:jira-software read:project:jira` (granular, for boards and sprints), so a write scope in a shared file can never reach the connection. All six are read-only.

## Verified against the Atlassian documentation, and what is assumed
Checked on 2026-10-19 against developer.atlassian.com and Atlassian's own notices.

| Topic | Status | Notes |
|---|---|---|
| Authorize URL `https://auth.atlassian.com/authorize` with `audience=api.atlassian.com`, `client_id`, `scope`, `redirect_uri`, `state`, `response_type=code`, `prompt=consent` | verified | `offline_access` is what returns a refresh token |
| Token endpoint `POST https://auth.atlassian.com/oauth/token` (JSON): `authorization_code` and `refresh_token` grants | verified | |
| Refresh tokens rotate: every refresh returns a new refresh token and disables the old one; an old one used again fails with 403 `invalid_grant`; 90 days of inactivity expire it; a 10-minute reuse window exists | verified | C1 saves the new refresh token before using the new access token; the refresh is done under a per-project lock |
| `GET https://api.atlassian.com/oauth/token/accessible-resources` gives the site `id` (cloud id), `name`, `url` | verified | the first site is used |
| API base `https://api.atlassian.com/ex/jira/{cloudid}/...` | verified | |
| Issue search is `GET /rest/api/3/search/jql` with `nextPageToken` paging (`/rest/api/3/search` was removed) | verified | Atlassian's notice and RFC; the search result has no total, so C1 pages until there is no token |
| `read:jira-work` covers searching issues | verified (documented as "search for issues and objects associated with issues") | |
| `read:jira-work` covers `GET /rest/api/3/project/search` | assumed | the scopes page does not map endpoints; the project listing is "Jira project and issue data" |
| Agile `GET /rest/agile/1.0/board` needs `read:board-scope:jira-software` and `read:project:jira` | verified (Atlassian reference page of the board API) | classic `read:jira-work` is not listed for it, which matches the 401 seen with a real connection |
| Agile sprint reads need `read:sprint:jira-software` | verified for `GET /rest/agile/1.0/sprint/{id}`; **assumed** for `GET .../board/{id}/sprint` (that page section could not be read) | the same scope family; the board scope is requested too |
| "Jira Software doesn't support classic scopes. Use granular scopes instead." | verified | Jira Software scopes page |
| Classic and granular scopes may be mixed in one authorization request | **assumed, not verified** | no Atlassian page says so or forbids it (the scopes page only advises classic scopes where possible); a public request (ECO-143) asks for a single URL with both, third-party notes report it works. C1 mixes them, keeping the classic scopes that already work for projects and issue search. If the consent screen or token refuses the mix, switch to an all-granular set (e.g. `read:issue-details:jira`, `read:project:jira`, `read:user:jira`, plus the two Software scopes) |
| The all-granular scopes for `project/search` and `search/jql` | not verified | the endpoint pages could not be read in full, so C1 keeps the classic scopes for them |
| `read:jira-user` | kept as asked | none of the calls C1 makes needs it |
| Issue search can return the fields `sprint` and `closedSprints` | assumed | standard in Jira Cloud (the sprint field of the issue); unknown field names in `fields` are ignored by Jira |
| 429 carries a `Retry-After` header | assumed | C1 uses it when present (at most 30 s), otherwise 1, 2, 4 s |

The stored connection remembers the permissions it was made with. A connection made before the board scopes were requested is reported as `needs_reconnect: true`
(state stays `connected`: projects and issue import still work, only board access is missing). Choosing Connect again fixes it; nothing imported is lost.
A 401 or 403 from the board or sprint reads is answered with `jira_scope_missing` ("Reconnect Jira to allow board access.").

## Connection flow
1. `POST /api/projects/{pid}/integrations/jira/connect` makes a random `state` (single use, valid 10 minutes, bound to the project, stored only as a hash) and returns the
   Atlassian authorize URL. The browser is sent there.
2. After approval Atlassian sends the browser to `GET /api/integrations/jira/callback?code=...&state=...`. C1 uses up the state (a replayed, unknown, expired or missing state
   is refused), exchanges the code, reads the site list and stores the first site and the tokens, then redirects to `C1_FRONTEND_URL?jira=connected`.
   Any failure redirects to `?jira=error&reason=state_invalid|access_denied|exchange_failed|no_site|not_configured|invalid_request`; nothing else is revealed.
3. Access tokens last an hour. They are refreshed a minute before they run out, and once after a 401. If a refresh is refused, the status becomes `expired` (the
   tokens are deleted); the user connects again. A Jira outage (429, 5xx, no connection) is retried up to 4 times and then answered with `jira_request_failed` or
   `jira_unreachable`; it does not expire the connection.

## Import
`POST /api/projects/{pid}/integrations/jira/import`: `project_key`, `board_id` (optional), `sprint_states` (default `active`, `future`), `issue_types` (default `Story`, `Task`),
`target_sprint_id` (see below), `set_current` (`"match"` only: make the active Jira sprint current), `policy` (which drafts are queued, default `smart`) and `analyze` (default true).

* **Target sprint (`target_sprint_id`).** A C1 sprint id: every imported requirement and the document go to that sprint. Left out (null): the current sprint for new issues, issues
  already imported stay where they are. `"match"`: each issue goes to the C1 sprint of its Jira sprint (issues without a known Jira sprint go to the current sprint).
  No Jira sprint is created in the first two modes.
* **Sprints in `"match"` mode.** One Jira sprint = one C1 sprint, matched by its Jira id (`external_id`), created once and updated afterwards (name, dates, goal); a second one is never
  made for the same Jira sprint, with or without a board. Only sprints an issue is in are created (the active one also when `set_current` is on); empty Jira sprints are not. If a name is
  already taken here (Jira's "Sprint 1" and the sprint every project starts with, or a second Jira sprint with the same name), it is called "Sprint 1 (Jira)". With a board the issues are the ones
  in the board's sprints in the chosen states; without a board every issue of the project is read and the sprints come from the issues (again only the chosen states).
* **Issues.** One requirement per issue, in the document `Jira · KEY`. Its text is the summary, then the description (Atlassian Document Format turned into plain text: paragraphs,
  headings, lists, code, tables, mentions, links; media is left out), at most 4000 characters. Issues without any text are `skipped`. The issue key, type, status and link
  are shown in the API (`jira` on the requirement). The key is the requirement's clause label, so an issue keeps its place when others change.
* **Sprint of an issue.** The sprint the issue is in now (`sprint`, else one of `closedSprints`) among the imported sprints; otherwise the requirement follows its document.
* **Then** the normal analysis of the new or changed documents, the drafts the policy asks for (`queued`), and the automatic sync.

### Idempotent by key
| Case | Result |
|---|---|
| issue seen first time | new requirement (`issues_new`) |
| same text, same type, status and sprint | nothing changes (`issues_unchanged`): same requirement, decision and draft |
| status, type or sprint changed, same text | updated (`issues_updated`), no new analysis; a changed sprint moves the requirement |
| text changed | updated; the analysis follows the re-analysis rules: the changed issue becomes a new requirement, its old decision is copied to the audit table (`reanalysis_changed`) and the draft is written again; all others are untouched |
| issue not returned any more (same project and same board scope) | `missing`: the row is marked and listed in the import log, the requirement is **kept** (nothing is deleted); it is cleared when the issue returns |

An import with another board (or none) is another scope: its issues are not compared with the first one, so they are never reported missing by mistake. More than 2000 issues in
one import are cut off (`truncated`) and nothing is marked missing then.

## Security
* Tokens are stored in the table `jira_connections` of the project's database file (`outputs/c1_workspace/c1.db`), in clear text, like the rest of that file: protect the folder
  like any file with credentials. They are never in an API response, a log line, an export, the graph publish or the OpenAPI file. Tests scan all of these.
* Error messages are fixed texts; what Jira answered is never repeated. Logs carry the HTTP status only.
* The client secret is only read from the environment or the shared `.env` and is never stored in the database.
* Atlassian cannot be called with anything but GET; the token endpoint is called with POST.
* The authorization code travels in the callback address, so a web server's access log may contain it. It is single use and short lived; the tokens never appear in a URL.
* Disconnecting deletes the tokens here. It does not revoke the grant at Atlassian: do that at https://id.atlassian.com/manage-profile/apps if needed.

## Set up the Atlassian app (once)
1. https://developer.atlassian.com/console/myapps/ → create an **OAuth 2.0 integration**.
2. **Permissions**: add the **Jira API** with the classic scopes `read:jira-work` and `read:jira-user`, and add **Jira Software** with the granular scopes `read:board-scope:jira-software` and `read:sprint:jira-software` (and `read:project:jira` under the Jira API). The app must list every scope C1 asks for.
3. **Authorization**: add the callback URL exactly as `ATLASSIAN_REDIRECT_URI` (default `http://localhost:8000/api/integrations/jira/callback`).
4. **Settings**: copy the client id and secret into the shared `.env` (`ATLASSIAN_CLIENT_ID`, `ATLASSIAN_CLIENT_SECRET`), then restart the API.

## Test the real connection
See the steps in the report of the S2 change, or: restart the API (`scripts\run_c1_live.ps1`), open the Overview, choose **Connect Jira**, approve, you return with a "Jira connected"
notice; choose **Import from Jira**, pick the project (and board), import, then open the Review Queue: imported requirements show a **Jira** badge and their key.
