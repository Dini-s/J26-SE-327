"""Jira Cloud: connect with OAuth 2.0 (3LO, read-only) and import sprints and issues as requirements. docs/c1_jira_integration.md describes the whole flow.

Read-only on purpose: the scopes are the classic `read:jira-work read:jira-user offline_access` plus the granular `read:board-scope:jira-software read:sprint:jira-software read:project:jira` (boards and sprints) and nothing here ever sends anything to Jira but GET requests.
Tokens live in the project's own sqlite file (table jira_connections) and nowhere else: no response, log line, export or graph publish contains one, and error
messages are fixed texts that never repeat what Jira or the token endpoint answered.

Sections: (1) settings, (2) the HTTP layer (retries on 429/5xx), (3) ADF to plain text, (4) the service: connect, callback, tokens, reads, import.
"""
import hashlib
import logging
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from . import neo4j_config
from .db import dumps, loads, now
from .errors import ApiError

log = logging.getLogger("c1.jira")

# fixed: whatever ATLASSIAN_SCOPES says, C1 asks for these and only these (all read-only). The first three are classic (projects, issue search, refresh token);
# the last three are the granular ones the Jira Software board and sprint reads (/rest/agile/1.0/...) are documented to need.
SCOPES = ("read:jira-work", "read:jira-user", "offline_access", "read:board-scope:jira-software", "read:sprint:jira-software", "read:project:jira")
AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
API_BASE = "https://api.atlassian.com/ex/jira/"
DEFAULT_REDIRECT_URI = "http://localhost:8000/api/integrations/jira/callback"
DEFAULT_FRONTEND_URL = "http://localhost:5173/requirement"

STATE_TTL = timedelta(minutes=10)
REFRESH_MARGIN = timedelta(seconds=60)
MAX_TRIES = 4  # a request that gets 429 or 5xx is tried again, with a pause, up to this many times
MAX_WAIT = 30.0
PAGE = 50
MAX_PAGES = 100
SEARCH_PAGE = 100
MAX_ISSUES = 2000  # per import; more than that is cut off and reported as `truncated`
MAX_TEXT = 4000
SPRINT_STATES = ("active", "future", "closed")
DEFAULT_SPRINT_STATES = ("active", "future")
DEFAULT_ISSUE_TYPES = ("Story", "Task")
SOURCE_PREFIX = "Jira · "
ISSUE_FIELDS = "summary,description,issuetype,status,sprint,closedSprints,project"

_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,19}$")
_TYPE = re.compile(r"^[\w .\-]{1,40}$")
_ISSUE_NUMBER = re.compile(r"-(\d+)$")

ALLOWED_KEYS = frozenset({"ATLASSIAN_CLIENT_ID", "ATLASSIAN_CLIENT_SECRET", "ATLASSIAN_REDIRECT_URI", "C1_FRONTEND_URL"})

MSG = {
    "jira_not_configured": "Jira is not set up on this server. Ask your administrator to set it up, then try again.",
    "jira_not_connected": "This project is not connected to Jira. Connect it first.",
    "jira_expired": "The Jira connection has expired. Connect again to continue.",
    "jira_unreachable": "Jira could not be reached. Try again in a moment.",
    "jira_request_failed": "Jira did not accept the request. Try again later.",
    "jira_forbidden": "Jira refused this request. The connected account may not have access to it.",
    "jira_scope_missing": "Jira did not accept the permissions of this connection for this request. Reconnect Jira to allow board access.",
    "jira_not_found": "Jira could not find what was asked for.",
    "jira_bad_request": "Jira did not understand the request.",
}


def _fail(code, status):
    return ApiError(status, code, MSG[code])


# ------------------------------------------------------------------------------------------------------------------- (1) settings
@dataclass(frozen=True)
class JiraConfig:
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = DEFAULT_REDIRECT_URI
    frontend_url: str = DEFAULT_FRONTEND_URL

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret)

    def __repr__(self):  # the secret is never printed
        return f"JiraConfig(client_id_set={bool(self.client_id)}, client_secret_set={bool(self.client_secret)}, redirect_uri={self.redirect_uri!r})"

    __str__ = __repr__


def load_config(environ=None, env_files=None):
    """ATLASSIAN_CLIENT_ID / ATLASSIAN_CLIENT_SECRET / ATLASSIAN_REDIRECT_URI / C1_FRONTEND_URL from the environment and, for these keys only, from the
    shared .env file (same strict reader as the graph settings: no other line is kept). ATLASSIAN_SCOPES is deliberately not read."""
    import os
    env = os.environ if environ is None else environ
    values = {}
    for path in (neo4j_config.ENV_FILES if env_files is None else env_files):
        if Path(path).is_file():
            values.update(neo4j_config.read_env_file(path, ALLOWED_KEYS))
            break
    values.update({k: env[k] for k in ALLOWED_KEYS if env.get(k)})
    return JiraConfig(values.get("ATLASSIAN_CLIENT_ID", ""), values.get("ATLASSIAN_CLIENT_SECRET", ""),
                      values.get("ATLASSIAN_REDIRECT_URI") or DEFAULT_REDIRECT_URI, values.get("C1_FRONTEND_URL") or DEFAULT_FRONTEND_URL)


def frontend_redirect(base, **params):
    """`base` with ?jira=... added (existing query parameters are kept)."""
    parts = urlsplit(base)
    query = parse_qsl(parts.query) + [(k, v) for k, v in params.items() if v]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


# ------------------------------------------------------------------------------------------------------------------- (2) HTTP
class NetworkError(Exception):
    """The request could not be made at all (no connection, timeout). Carries no details."""


@dataclass
class Response:
    status: int
    body: object = None
    headers: dict = None

    def header(self, name):
        for k, v in (self.headers or {}).items():
            if k.lower() == name.lower():
                return v
        return None


class HttpxClient:
    """The real HTTP client (httpx). Tests pass a fake with the same `request` method instead, so no test ever reaches Atlassian."""

    def __init__(self, timeout=20.0):
        self.timeout = timeout

    def request(self, method, url, headers=None, params=None, json=None):
        import httpx
        try:
            r = httpx.request(method, url, headers=headers, params=params, json=json, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise NetworkError() from exc
        try:
            body = r.json()
        except ValueError:
            body = None
        return Response(r.status_code, body, dict(r.headers))


# ------------------------------------------------------------------------------------------------------------------- (3) ADF
def adf_to_text(node):
    """Atlassian Document Format (the description of an issue) as plain text. A plain string is returned as it is; unknown node types contribute their children."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node.strip()
    return _clean(_adf(node, ""))


def _clean(text):
    text = re.sub(r"[ \t]+\n", "\n", text.replace("\r", ""))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _kids(node, ctx=""):
    return "".join(_adf(c, ctx) for c in (node.get("content") or []) if isinstance(c, dict))


def _adf(node, ctx):
    kind, attrs = node.get("type"), node.get("attrs") or {}
    if kind == "text":
        return node.get("text", "")
    if kind == "hardBreak":
        return "\n"
    if kind == "mention":
        return attrs.get("text") or ""
    if kind == "emoji":
        return attrs.get("text") or attrs.get("shortName") or ""
    if kind in ("inlineCard", "blockCard"):
        return attrs.get("url") or ""
    if kind in ("media", "mediaSingle", "mediaGroup", "mediaInline", "rule"):
        return ""
    if kind in ("paragraph", "heading"):
        return _kids(node, ctx) + "\n\n"
    if kind in ("bulletList", "orderedList"):
        out = []
        for n, item in enumerate((c for c in (node.get("content") or []) if isinstance(c, dict)), start=int(attrs.get("order") or 1)):
            body = _clean(_kids(item, ctx)).replace("\n\n", "\n").replace("\n", "\n  ")
            out.append(f"{n}. {body}" if kind == "orderedList" else f"- {body}")
        return "\n".join(out) + "\n\n"
    if kind == "listItem":
        return _kids(node, ctx)
    if kind == "codeBlock":
        return _kids(node, ctx) + "\n\n"
    if kind in ("blockquote", "panel", "expand", "nestedExpand"):
        return _kids(node, ctx) + "\n"
    if kind == "table":
        rows = []
        for row in node.get("content") or []:
            cells = [_clean(_kids(cell, ctx)).replace("\n", " ") for cell in (row.get("content") or []) if isinstance(cell, dict)]
            rows.append(" | ".join(cells))
        return "\n".join(rows) + "\n\n"
    return _kids(node, ctx)  # doc and anything unknown


# ------------------------------------------------------------------------------------------------------------------- (4) the service
def _utc(ts=None):
    return datetime.fromtimestamp(ts, timezone.utc) if ts is not None else datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def _date(value):
    return (value or "")[:10] or None


def issue_number(key):
    m = _ISSUE_NUMBER.search(key or "")
    return int(m.group(1)) if m else None


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class JiraService:
    def __init__(self, db, http=None, config_loader=None, clock=time.time, sleep=time.sleep):
        self.db, self.http, self.clock, self.sleep = db, http or HttpxClient(), clock, sleep
        self._load = config_loader or load_config
        self._locks, self._guard = {}, threading.Lock()
        self._importing = set()

    # -- helpers
    def config(self):
        return self._load()

    def _lock(self, pid):
        with self._guard:
            return self._locks.setdefault(pid, threading.RLock())

    def _now(self):
        return _utc(self.clock())

    def _send(self, method, url, **kw):
        """One request; 429 and 5xx are tried again with a pause (the server's Retry-After, at most 30 s). The last answer is returned as it is."""
        for attempt in range(MAX_TRIES):
            last = attempt == MAX_TRIES - 1
            try:
                r = self.http.request(method, url, **kw)
            except NetworkError:
                if last:
                    raise _fail("jira_unreachable", 502) from None
                self.sleep(min(2.0 ** attempt, MAX_WAIT))
                continue
            if (r.status == 429 or r.status >= 500) and not last:
                try:
                    wait = float(r.header("Retry-After") or 0)
                except ValueError:
                    wait = 0.0
                self.sleep(min(wait or 2.0 ** attempt, MAX_WAIT))
                continue
            return r
        raise _fail("jira_unreachable", 502)

    def connection(self, pid):
        return self.db.one("SELECT * FROM jira_connections WHERE project_id=?", (pid,))

    # -- status
    def status(self, pid):
        cfg = self.config()
        row = self.connection(pid)
        last = self.db.one("SELECT at, counts FROM jira_imports WHERE project_id=? ORDER BY id DESC LIMIT 1", (pid,))
        if not cfg.configured:
            state = "not_configured"
        elif row is None:
            state = "not_connected"
        else:
            state = "expired" if row["status"] == "expired" else "connected"
        shown = row is not None and state in ("connected", "expired")
        granted = set((row["scope"] or "").split()) if row is not None else set()
        return {"state": state, "needs_reconnect": state == "connected" and not set(SCOPES) <= granted,
                "site": {"name": row["site_name"], "url": row["site_url"]} if shown else None,
                "connected_at": row["connected_at"] if shown else None,
                "last_import": {"at": last["at"], "counts": loads(last["counts"], {})} if last else None}

    # -- connect and callback
    def connect(self, pid):
        cfg = self.config()
        if not cfg.configured:
            raise _fail("jira_not_configured", 409)
        stamp = self._now()
        state = secrets.token_urlsafe(32)
        with self.db.connect() as con:
            con.execute("DELETE FROM jira_states WHERE used=1 OR created_at<?", (_iso(stamp - STATE_TTL),))
            con.execute("INSERT INTO jira_states (state_hash, project_id, created_at, used) VALUES (?,?,?,0)", (_digest(state), pid, _iso(stamp)))
        query = urlencode({"audience": "api.atlassian.com", "client_id": cfg.client_id, "scope": " ".join(SCOPES), "redirect_uri": cfg.redirect_uri,
                           "state": state, "response_type": "code", "prompt": "consent"})
        return {"authorize_url": f"{AUTHORIZE_URL}?{query}"}

    def _consume_state(self, state):
        """The project a state was made for, once: the state is used up by this call, and only ten minutes count."""
        if not state:
            return None
        cutoff = _iso(self._now() - STATE_TTL)
        with self.db.connect() as con:
            row = con.execute("SELECT project_id FROM jira_states WHERE state_hash=? AND used=0 AND created_at>=?", (_digest(state), cutoff)).fetchone()
            claimed = con.execute("UPDATE jira_states SET used=1 WHERE state_hash=? AND used=0 AND created_at>=?", (_digest(state), cutoff)).rowcount
        return row["project_id"] if row and claimed == 1 else None

    def callback(self, code, state, error=None):
        """Finish the connection. Always answers with the address to send the browser to (the module's page, with ?jira=connected or ?jira=error)."""
        cfg = self.config()
        base = cfg.frontend_url

        def back(ok, reason=None):
            return frontend_redirect(base, jira="connected" if ok else "error", reason=reason)

        pid = self._consume_state(state)
        if pid is None:
            return back(False, "state_invalid")
        if error:
            return back(False, "access_denied")
        if not code or not cfg.configured:
            return back(False, "not_configured" if not cfg.configured else "invalid_request")
        try:
            tokens = self._token_request(cfg, {"grant_type": "authorization_code", "code": code, "redirect_uri": cfg.redirect_uri})
            site = self._first_site(tokens["access_token"])
        except ApiError as exc:
            return back(False, "no_site" if exc.code == "jira_not_connected" else "exchange_failed")
        if site is None:
            return back(False, "no_site")
        stamp = self._now()
        with self._lock(pid):
            with self.db.connect() as con:
                con.execute("DELETE FROM jira_connections WHERE project_id=?", (pid,))
                con.execute("INSERT INTO jira_connections (project_id, cloud_id, site_name, site_url, access_token, refresh_token, expires_at, status, connected_at, updated_at, scope) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (pid, site["id"], site.get("name") or "", site.get("url") or "", tokens["access_token"], tokens.get("refresh_token") or "",
                             _iso(stamp + timedelta(seconds=int(tokens.get("expires_in") or 3600))), "connected", _iso(stamp), _iso(stamp),
                             str(tokens.get("scope") or " ".join(SCOPES))))
        return back(True)

    def _token_request(self, cfg, body):
        r = self._send("POST", TOKEN_URL, json=dict(body, client_id=cfg.client_id, client_secret=cfg.client_secret), headers={"Content-Type": "application/json"})
        data = r.body if isinstance(r.body, dict) else {}
        if r.status != 200 or not data.get("access_token"):
            if r.status in (400, 401, 403):
                raise _fail("jira_expired", 409)
            raise _fail("jira_request_failed", 502)
        return data

    def _first_site(self, access_token):
        r = self._send("GET", RESOURCES_URL, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
        if r.status != 200 or not isinstance(r.body, list):
            raise _fail("jira_request_failed", 502)
        sites = [s for s in r.body if isinstance(s, dict) and s.get("id")]
        return sites[0] if sites else None

    def disconnect(self, pid):
        """Forget the connection (the tokens are deleted here); what was imported stays."""
        with self._lock(pid), self.db.connect() as con:
            con.execute("DELETE FROM jira_connections WHERE project_id=?", (pid,))
            con.execute("DELETE FROM jira_states WHERE project_id=?", (pid,))

    # -- tokens
    def _expire(self, pid):
        with self.db.connect() as con:
            con.execute("UPDATE jira_connections SET status='expired', access_token='', refresh_token='', updated_at=? WHERE project_id=?", (_iso(self._now()), pid))

    def _access(self, pid, force=False):
        """(access token, cloud id), refreshed when it is about to run out. The refresh token rotates: the new one is saved before anything else happens."""
        with self._lock(pid):
            row = self.connection(pid)
            if row is None:
                raise _fail("jira_not_connected", 409)
            if row["status"] == "expired":
                raise _fail("jira_expired", 409)
            cfg = self.config()
            if not cfg.configured:
                raise _fail("jira_not_configured", 409)
            due = datetime.fromisoformat(row["expires_at"]) - REFRESH_MARGIN
            if force or not row["access_token"] or self._now() >= due:
                if not row["refresh_token"]:
                    self._expire(pid)
                    raise _fail("jira_expired", 409)
                try:
                    tokens = self._token_request(cfg, {"grant_type": "refresh_token", "refresh_token": row["refresh_token"]})
                except ApiError as exc:
                    if exc.code == "jira_expired":
                        self._expire(pid)
                    raise
                stamp = self._now()
                with self.db.connect() as con:
                    con.execute("UPDATE jira_connections SET access_token=?, refresh_token=?, expires_at=?, updated_at=? WHERE project_id=?",
                                (tokens["access_token"], tokens.get("refresh_token") or row["refresh_token"], _iso(stamp + timedelta(seconds=int(tokens.get("expires_in") or 3600))),
                                 _iso(stamp), pid))
                return tokens["access_token"], row["cloud_id"]
            return row["access_token"], row["cloud_id"]

    # -- reads
    def get(self, pid, path, params=None):
        """GET one Jira API path as the connected user. 401 gets one forced refresh and a second try."""
        for attempt in (0, 1):
            token, cloud = self._access(pid, force=attempt == 1)
            r = self._send("GET", f"{API_BASE}{cloud}{path}", params=params, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            if r.status == 401 and attempt == 0:
                continue
            break
        if r.status == 200:
            return r.body
        log.warning("jira request failed: status %s", r.status)  # the status only: never the path, the answer or a token
        if r.status == 401:
            raise _fail("jira_scope_missing", 403)
        if r.status == 403:
            raise _fail("jira_forbidden", 403)
        if r.status == 404:
            raise _fail("jira_not_found", 404)
        if r.status == 400:
            raise _fail("jira_bad_request", 400)
        raise _fail("jira_request_failed", 502)

    def _paged(self, pid, path, params=None, key="values"):
        out, start = [], 0
        for _ in range(MAX_PAGES):
            data = self.get(pid, path, dict(params or {}, startAt=start, maxResults=PAGE)) or {}
            values = data.get(key) or []
            out.extend(v for v in values if isinstance(v, dict))
            start += len(values)
            if data.get("isLast", True) or not values:
                break
        return out

    def projects(self, pid):
        return [{"key": p.get("key"), "name": p.get("name") or p.get("key")} for p in self._paged(pid, "/rest/api/3/project/search", {"orderBy": "name"}) if p.get("key")]

    def boards(self, pid, project_key):
        key = self._project_key(project_key)
        try:
            raw = self._paged(pid, "/rest/agile/1.0/board", {"projectKeyOrId": key})
        except ApiError as exc:
            if exc.code == "jira_forbidden":  # 401 and 403 on the board reads both mean "this connection may not read boards": reconnect
                raise _fail("jira_scope_missing", 403)
            raise
        return [{"id": b.get("id"), "name": b.get("name") or str(b.get("id")), "type": b.get("type") or ""} for b in raw if b.get("id") is not None]

    def sprints(self, pid, board_id, states=DEFAULT_SPRINT_STATES):
        states = self._states(states)
        try:
            raw = self._paged(pid, f"/rest/agile/1.0/board/{int(board_id)}/sprint", {"state": ",".join(states)})
        except ApiError as exc:
            if exc.code == "jira_bad_request":  # a board without sprints (Kanban)
                return []
            if exc.code == "jira_forbidden":
                raise _fail("jira_scope_missing", 403)
            raise
        return [s for s in (_remote_sprint(x) for x in raw) if s and s["state"] in states]

    # -- validation
    @staticmethod
    def _project_key(value):
        key = (value or "").strip().upper()
        if not _KEY.match(key):
            raise ApiError(400, "invalid_parameter", "project_key must be a Jira project key such as ABC.")
        return key

    @staticmethod
    def _states(values):
        states = tuple(dict.fromkeys(str(v).strip().lower() for v in (values or DEFAULT_SPRINT_STATES)))
        if not states or any(s not in SPRINT_STATES for s in states):
            raise ApiError(400, "invalid_parameter", f"sprint_states must be a list of {list(SPRINT_STATES)}.")
        return states

    @staticmethod
    def _types(values):
        types = tuple(dict.fromkeys(str(v).strip() for v in (values or DEFAULT_ISSUE_TYPES) if str(v).strip()))
        if not types or any(not _TYPE.match(t) for t in types):
            raise ApiError(400, "invalid_parameter", "issue_types must be a list of Jira issue type names such as Story and Task.")
        return types

    # -- search
    def search(self, pid, jql):
        """Every issue of the search, page by page (token paging of the enhanced search). Returns (issues, truncated)."""
        issues, token, truncated = [], None, False
        for _ in range(MAX_PAGES):
            params = {"jql": jql, "fields": ISSUE_FIELDS, "maxResults": SEARCH_PAGE}
            if token:
                params["nextPageToken"] = token
            data = self.get(pid, "/rest/api/3/search/jql", params) or {}
            issues.extend(i for i in (data.get("issues") or []) if isinstance(i, dict) and i.get("key"))
            token = data.get("nextPageToken")
            if len(issues) >= MAX_ISSUES:
                truncated = bool(token) or len(issues) > MAX_ISSUES
                issues = issues[:MAX_ISSUES]
                break
            if not token or data.get("isLast") is True:
                break
        return issues, truncated

    # -- import
    def import_issues(self, pid, project_key, board_id=None, sprint_states=None, issue_types=None, set_current=False, target_sprint_id=None):
        """Read sprints and issues from Jira and store them (sprints, one virtual document per Jira project, the issue map). Idempotent by issue key.
        `target_sprint_id`: a C1 sprint id (everything goes there), None (the current sprint) or "match" (each issue goes to the C1 sprint of its Jira sprint).
        Returns the counts and the ids of the documents that need an analysis. Nothing is sent to Jira."""
        key = self._project_key(project_key)
        target = self._target(pid, target_sprint_id)
        states, types = self._states(sprint_states), self._types(issue_types)
        board = int(board_id) if board_id not in (None, "") else None
        with self._guard:
            if pid in self._importing:
                raise ApiError(409, "import_running", "An import is already running for this project.")
            self._importing.add(pid)
        try:
            self._access(pid)  # fails early and plainly when the project is not connected
            remote = self.sprints(pid, board, states) if board is not None else []
            quoted = ", ".join('"' + t.replace('"', "") + '"' for t in types)
            jql = f'project = "{key}" AND issuetype in ({quoted})'
            if board is not None:
                jql += " AND sprint in (" + ",".join(str(s["id"]) for s in remote) + ")" if remote else ""
            issues, truncated = ([], False) if board is not None and not remote else self.search(pid, jql + " ORDER BY key ASC")
            return self._store(pid, key, board, states, remote, issues, truncated, set_current, target)
        finally:
            with self._guard:
                self._importing.discard(pid)

    def _target(self, pid, value):
        """(mode, sprint id): ("match", None), ("sprint", id of the chosen sprint) or ("current", None)."""
        if value == "match":
            return "match", None
        if value is None or value == "":
            return "current", None
        try:
            sid = int(value)
        except (TypeError, ValueError):
            raise ApiError(400, "invalid_parameter", 'target_sprint_id must be a sprint id or "match".')
        if not self.db.one("SELECT id FROM sprints WHERE id=? AND project_id=?", (sid, pid)):
            raise ApiError(404, "sprint_not_found", f"Sprint {sid} does not exist in project {pid}.")
        return "sprint", sid

    def _store(self, pid, key, board, states, remote, issues, truncated, set_current, target=("current", None)):
        mode, chosen = target
        counts = {"sprints_created": 0, "sprints_updated": 0, "issues_new": 0, "issues_updated": 0, "issues_unchanged": 0, "skipped": 0, "missing": 0}
        known = {s["id"]: s for s in remote}
        for issue in issues:  # the sprints the issues are in (a board's own list wins)
            for s in _issue_sprints(issue):
                if s["state"] in states:
                    known.setdefault(s["id"], s)
        # one Jira sprint = one C1 sprint, and only in "match" mode: the sprints the issues are in, plus the active one when asked for. Never an empty sprint otherwise.
        eligible = {}
        if mode == "match":
            for issue in issues:
                for s in _issue_sprints(issue):
                    if s["id"] in known:
                        eligible[s["id"]] = known[s["id"]]
            if set_current:
                for s in known.values():
                    if s["state"] == "active":
                        eligible.setdefault(s["id"], s)
        stamp = _iso(self._now())
        site = (self.connection(pid) or {}).get("site_url") or ""
        scope = "" if board is None else str(board)
        with self.db.connect() as con:
            local = {}
            for rid, s in eligible.items():
                local[rid] = self._upsert_sprint(con, pid, s, counts)
            if set_current and mode == "match":
                active = sorted((s for s in eligible.values() if s["state"] == "active"), key=lambda s: s["start_date"] or "", reverse=True)
                if active:
                    con.execute("UPDATE projects SET current_sprint_id=? WHERE id=?", (local[active[0]["id"]], pid))
            current = con.execute("SELECT current_sprint_id c FROM projects WHERE id=?", (pid,)).fetchone()["c"]
            seen, changed_source = set(), False
            src = con.execute("SELECT * FROM sources WHERE project_id=? AND source_type='jira' AND filename=?", (pid, SOURCE_PREFIX + key)).fetchone()
            if src is None and issues:
                sid = con.execute("INSERT INTO sources (project_id, filename, stored_path, ext, size_bytes, pages, warnings, extracted, created_at, source_type, sha256, default_sprint_id) "
                                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (pid, SOURCE_PREFIX + key, f"jira:{key}", ".jira", 0, None, "[]", dumps({"text": "", "line_map": []}),
                                                                      stamp, "jira", "", chosen or current)).lastrowid
                src = con.execute("SELECT * FROM sources WHERE id=?", (sid,)).fetchone()
            elif src is not None and mode == "sprint":
                con.execute("UPDATE sources SET default_sprint_id=? WHERE id=?", (chosen, src["id"]))
            for issue in issues:
                f = issue.get("fields") or {}
                summary = (f.get("summary") or "").strip()
                text = _compose(summary, adf_to_text(f.get("description")))
                if not text:
                    counts["skipped"] += 1
                    continue
                ikey = issue["key"]
                seen.add(ikey)
                if mode == "match":
                    sprint_local = next((local[s["id"]] for s in _issue_sprints(issue) if s["id"] in local), None) or current
                else:
                    sprint_local = chosen
                itype, status = (f.get("issuetype") or {}).get("name") or "", (f.get("status") or {}).get("name") or ""
                url = f"{site.rstrip('/')}/browse/{ikey}" if site else ""
                digest = _digest(text)
                old = con.execute("SELECT * FROM jira_issues WHERE project_id=? AND issue_key=?", (pid, ikey)).fetchone()
                if mode == "current":  # no sprint was chosen: new issues go to the current sprint, known ones stay where they are
                    sprint_local = old["sprint_id"] if old is not None and old["sprint_id"] is not None else current
                if old is None:
                    counts["issues_new"] += 1
                    con.execute("INSERT INTO jira_issues (project_id, issue_key, jira_project, source_id, issue_type, status, text, text_hash, sprint_id, url, scope, missing, updated_at) "
                                "VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?)", (pid, ikey, key, src["id"], itype, status, text, digest, sprint_local, url, scope, stamp))
                    changed_source = True
                    continue
                text_changed = old["text_hash"] != digest
                meta_changed = (old["issue_type"], old["status"], old["sprint_id"]) != (itype, status, sprint_local)
                counts["issues_updated" if (text_changed or meta_changed) else "issues_unchanged"] += 1
                con.execute("UPDATE jira_issues SET source_id=?, issue_type=?, status=?, text=?, text_hash=?, sprint_id=?, url=?, scope=?, missing=0, updated_at=? WHERE project_id=? AND issue_key=?",
                            (src["id"], itype, status, text, digest, sprint_local, url or old["url"], scope, stamp if (text_changed or meta_changed) else old["updated_at"], pid, ikey))
                if text_changed:
                    changed_source = True
                if old["sprint_id"] != sprint_local:  # the sprint follows Jira
                    con.execute("UPDATE requirements SET sprint_id=? WHERE source_id=? AND clause_label=?", (sprint_local, src["id"], ikey))
            missing = [r["issue_key"] for r in con.execute("SELECT issue_key FROM jira_issues WHERE project_id=? AND jira_project=? AND scope=? AND missing=0", (pid, key, scope)).fetchall()
                       if r["issue_key"] not in seen] if not truncated else []
            for k in missing:  # audited, not deleted: the requirement stays, the row says it was not in this import
                con.execute("UPDATE jira_issues SET missing=1, updated_at=? WHERE project_id=? AND issue_key=?", (stamp, pid, k))
            counts["missing"] = len(missing)
            source_ids = []
            if src is not None:
                rows = con.execute("SELECT issue_key, text_hash, text FROM jira_issues WHERE project_id=? AND source_id=? ORDER BY issue_key", (pid, src["id"])).fetchall()
                sha = _digest("\n".join(f"{r['issue_key']}:{r['text_hash']}" for r in rows))
                con.execute("UPDATE sources SET sha256=?, size_bytes=? WHERE id=?", (sha, sum(len(r["text"]) for r in rows), src["id"]))
                if changed_source or src["analysis_state"] != "analyzed":
                    source_ids.append(src["id"])
            con.execute("INSERT INTO jira_imports (project_id, jira_project, board_id, at, counts, missing_keys) VALUES (?,?,?,?,?,?)",
                        (pid, key, board, stamp, dumps(dict(counts, truncated=truncated)), dumps(missing)))
        target_sprint = None
        if mode != "match":
            row = self.db.one("SELECT id, name FROM sprints WHERE id=?", (chosen or current,)) if (chosen or current) else None
            target_sprint = {"id": row["id"], "name": row["name"]} if row else None
        return dict(counts, truncated=truncated, source_ids=source_ids, target_sprint=target_sprint, matched=mode == "match")

    @staticmethod
    def _upsert_sprint(con, pid, s, counts):
        """The local sprint of a Jira sprint (origin jira, matched by its Jira id); created or brought up to date."""
        row = con.execute("SELECT * FROM sprints WHERE project_id=? AND origin='jira' AND external_id=?", (pid, str(s["id"]))).fetchone()
        if row is None:
            taken = {r["name"].lower() for r in con.execute("SELECT name FROM sprints WHERE project_id=?", (pid,)).fetchall()}
            name, n = s["name"], 1
            while name.lower() in taken:  # Jira's "Sprint 1" may collide with a sprint made here
                n += 1
                name = f"{s['name']} (Jira)" if n == 2 else f"{s['name']} (Jira {n - 1})"
            position = (con.execute("SELECT COALESCE(MAX(position),0) m FROM sprints WHERE project_id=?", (pid,)).fetchone()["m"]) + 1
            counts["sprints_created"] += 1
            return con.execute("INSERT INTO sprints (project_id, phase_id, name, start_date, end_date, goal, origin, confirmed, external_id, position, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (pid, None, name, s["start_date"], s["end_date"], s["goal"], "jira", 1, str(s["id"]), position, now())).lastrowid
        if (row["start_date"], row["end_date"], row["goal"]) != (s["start_date"], s["end_date"], s["goal"]) or not row["name"].lower().startswith(s["name"].lower()):
            others = {r["name"].lower() for r in con.execute("SELECT name FROM sprints WHERE project_id=? AND id<>?", (pid, row["id"])).fetchall()}
            name = s["name"] if s["name"].lower() not in others else row["name"]
            con.execute("UPDATE sprints SET name=?, start_date=?, end_date=?, goal=? WHERE id=?", (name, s["start_date"], s["end_date"], s["goal"], row["id"]))
            counts["sprints_updated"] += 1
        return row["id"]


def _remote_sprint(x):
    if not isinstance(x, dict) or x.get("id") is None:
        return None
    return {"id": int(x["id"]), "name": x.get("name") or f"Sprint {x['id']}", "state": (x.get("state") or "").lower(),
            "start_date": _date(x.get("startDate")), "end_date": _date(x.get("endDate")), "goal": (x.get("goal") or "").strip() or None}


def _issue_sprints(issue):
    """The sprints an issue is in, the current one first (field `sprint`), then the closed ones."""
    f = issue.get("fields") or {}
    raw = ([f["sprint"]] if isinstance(f.get("sprint"), dict) else []) + [s for s in (f.get("closedSprints") or []) if isinstance(s, dict)]
    return [s for s in (_remote_sprint(x) for x in raw) if s]


def _compose(summary, description):
    text = summary if not description else f"{summary}\n\n{description}" if summary else description
    text = text.strip()
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 1].rstrip() + "…"
