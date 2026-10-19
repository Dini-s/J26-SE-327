"""Component 1: Jira connect and import (read-only).

No test reaches Atlassian: the service gets a scripted fake HTTP client that plays the token endpoint, the site list and the Jira API, and a fake clock. Tests that
need the saved Part A models (the analysis after an import) are skipped when the models are missing, like the other API tests.
"""
import json
import sqlite3
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from agents.requirement_agent.api import jira, neo4j_store
from agents.requirement_agent.api.jira import HttpxClient, JiraConfig, NetworkError, Response
from tests.test_c1_api import MODELS_PRESENT, error_of, make_client  # noqa: F401  (fixture)
from tests.test_c1_neo4j import isolated_settings  # noqa: F401  (autouse there: no real settings are read)

needs_models = pytest.mark.skipif(not MODELS_PRESENT, reason="saved models missing in models/component1/part_a_active")

CLIENT_ID, CLIENT_SECRET = "client-id-123", "client-secret-XYZ"
CFG = JiraConfig(CLIENT_ID, CLIENT_SECRET, "http://localhost:8000/api/integrations/jira/callback", "http://localhost:5173/requirement")
PREFIX = "https://api.atlassian.com/ex/jira/cloud-1"
SECRETS = (CLIENT_SECRET, "tok-access-", "tok-refresh-", "good-code")


# ------------------------------------------------------------------------------------------------------------------ the fakes
class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def sprint(i, name, state, start="2026-10-05", end="2026-10-16", goal=None):
    return {"id": i, "name": name, "state": state, "startDate": f"{start}T01:00:00.000Z" if start else None, "endDate": f"{end}T01:00:00.000Z" if end else None, "goal": goal}


def issue(key, summary, kind="Story", status="To Do", desc=None, sprint_=None, closed=()):
    fields = {"summary": summary, "issuetype": {"name": kind}, "status": {"name": status}, "project": {"key": key.split("-")[0]}}
    if desc is not None:
        fields["description"] = desc
    if sprint_ is not None:
        fields["sprint"] = sprint_
    if closed:
        fields["closedSprints"] = list(closed)
    return {"key": key, "fields": fields}


def adf(*paragraphs):
    return {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragraphs]}


class FakeJira:
    """Atlassian as far as C1 talks to it. Every request is recorded; `script` queues answers (status codes or exceptions) for a kind of request."""

    def __init__(self):
        self.calls, self.script = [], {}
        self.n = 0
        self.access, self.refresh = "tok-access-0", "tok-refresh-0"  # what Atlassian currently accepts
        self.projects = [{"key": "ABC", "name": "Alpha"}, {"key": "DEF", "name": "Delta"}, {"key": "GHI", "name": "Gamma"}]
        self.boards = [{"id": 7, "name": "ABC board", "type": "scrum"}, {"id": 8, "name": "ABC kanban", "type": "kanban"}]
        self.sprints = [sprint(10, "Sprint 1", "active", goal="Login"), sprint(11, "Sprint 2", "future", "2026-10-19", "2026-10-30"), sprint(9, "Old sprint", "closed", "2026-09-21", "2026-10-02")]
        self.issues = []
        self.page = 2
        self.sites = [{"id": "cloud-1", "name": "Acme", "url": "https://acme.atlassian.net", "scopes": list(jira.SCOPES)}]
        self.token_status = 200

    def push(self, kind, *answers):
        self.script.setdefault(kind, []).extend(answers)

    def _scripted(self, kind):
        queue = self.script.get(kind)
        if queue:
            return queue.pop(0)
        return None

    def token(self, body):
        if self.token_status != 200:
            return Response(self.token_status, {"error": "invalid_grant"})
        self.n += 1
        if body["grant_type"] == "authorization_code":
            if body["code"] != "good-code":
                return Response(403, {"error": "invalid_grant"})
        elif body["refresh_token"] != self.refresh:
            return Response(403, {"error": "invalid_grant", "error_description": "Unknown or invalid refresh token."})
        self.access, self.refresh = f"tok-access-{self.n}", f"tok-refresh-{self.n}"
        return Response(200, {"access_token": self.access, "refresh_token": self.refresh, "expires_in": 3600, "scope": " ".join(jira.SCOPES)})

    def request(self, method, url, headers=None, params=None, json=None):
        self.calls.append(SimpleNamespace(method=method, url=url, headers=headers or {}, params=params or {}, json=json))
        kind = "token" if url == jira.TOKEN_URL else "sites" if url == jira.RESOURCES_URL else url.rsplit("/rest/", 1)[-1].split("?")[0]
        scripted = self._scripted(kind)
        if scripted is not None:
            if isinstance(scripted, Exception):
                raise scripted
            return scripted if isinstance(scripted, Response) else Response(scripted, {}, {})
        if url == jira.TOKEN_URL:
            return self.token(json)
        bearer = (headers or {}).get("Authorization", "")
        if bearer != f"Bearer {self.access}":
            return Response(401, {"message": "Unauthorized"})
        if url == jira.RESOURCES_URL:
            return Response(200, self.sites)
        assert url.startswith(PREFIX), url
        path = url[len(PREFIX):]
        start, size = int(params.get("startAt", 0)), int(params.get("maxResults", 50))
        if path == "/rest/api/3/project/search":
            return self._page(self.projects, start, min(size, self.page))
        if path == "/rest/agile/1.0/board":
            return self._page(self.boards, start, min(size, self.page))
        if path.startswith("/rest/agile/1.0/board/") and path.endswith("/sprint"):
            if path.split("/")[5] == "8":
                return Response(400, {"errorMessages": ["The board does not support sprints"]})
            wanted = params.get("state", "active,future,closed").split(",")
            return self._page([s for s in self.sprints if s["state"] in wanted], start, min(size, self.page))
        if path == "/rest/api/3/search/jql":
            first = int(params["nextPageToken"][1:]) if params.get("nextPageToken") else 0
            chunk = self.issues[first:first + self.page]
            body = {"issues": chunk}
            if first + self.page < len(self.issues):
                body["nextPageToken"] = f"p{first + self.page}"
            else:
                body["isLast"] = True
            return Response(200, body)
        return Response(404, {})

    @staticmethod
    def _page(items, start, size):
        chunk = items[start:start + size]
        return Response(200, {"values": chunk, "startAt": start, "maxResults": size, "isLast": start + size >= len(items)})

    def token_calls(self):
        return [x for x in self.calls if x.url == jira.TOKEN_URL]

    def api_calls(self, part):
        return [c for c in self.calls if part in c.url]


@pytest.fixture
def fake():
    return FakeJira()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def c(make_client, fake, clock):  # noqa: F811
    client = make_client(jira_http=fake, jira_config=lambda: CFG)
    svc = client.app.state.jira
    svc.clock, svc.sleep = clock, lambda s: client.slept.append(s)
    client.slept, client.fake, client.clock = [], fake, clock
    return client


J = "/api/projects/1/integrations/jira"


def connect(c, project=1):
    url = c.post(f"/api/projects/{project}/integrations/jira/connect").json()["authorize_url"]
    state = parse_qs(urlsplit(url).query)["state"][0]
    return c.get("/api/integrations/jira/callback", params={"code": "good-code", "state": state}, follow_redirects=False)


def location(r):
    return r.headers["location"]


def importing(c, **body):
    body = dict({"project_key": "ABC", "analyze": False, "target_sprint_id": "match"}, **body)
    return c.post(f"{J}/import", json=body)


def jira_issues(c):
    return {r["issue_key"]: r for r in c.app.state.db.all("SELECT * FROM jira_issues")}


def sprints(c):
    return {s["name"]: s for s in c.get("/api/projects/1/sprints").json()}


# ------------------------------------------------------------------------------------------------------------------ settings
def test_settings_come_from_the_environment_and_the_scopes_are_fixed(tmp_path):
    env = {"ATLASSIAN_CLIENT_ID": "id", "ATLASSIAN_CLIENT_SECRET": "s3cr3t-value", "ATLASSIAN_SCOPES": "write:jira-work read:confluence-content.all"}
    cfg = jira.load_config(env, [])
    assert cfg.configured and cfg.redirect_uri == jira.DEFAULT_REDIRECT_URI == "http://localhost:8000/api/integrations/jira/callback"
    assert cfg.frontend_url == jira.DEFAULT_FRONTEND_URL == "http://localhost:5173/requirement"
    assert jira.SCOPES == ("read:jira-work", "read:jira-user", "offline_access", "read:board-scope:jira-software", "read:sprint:jira-software", "read:project:jira")
    assert all(s.startswith("read:") or s == "offline_access" for s in jira.SCOPES)  # ATLASSIAN_SCOPES is not read: no write scope can sneak in
    assert not jira.load_config({}, []).configured
    assert not jira.load_config({"ATLASSIAN_CLIENT_ID": "id"}, []).configured
    over = jira.load_config(dict(env, ATLASSIAN_REDIRECT_URI="https://x.example/cb", C1_FRONTEND_URL="https://app.example/requirement"), [])
    assert (over.redirect_uri, over.frontend_url) == ("https://x.example/cb", "https://app.example/requirement")
    assert "s3cr3t-value" not in repr(cfg) and "s3cr3t-value" not in str(cfg)


def test_the_env_file_is_read_for_the_jira_names_only(tmp_path):
    f = tmp_path / ".env"
    f.write_text("LLM_API_KEY=do-not-keep-me\nATLASSIAN_CLIENT_ID=from-file\nATLASSIAN_CLIENT_SECRET=file-secret\nATLASSIAN_SCOPES=write:jira-work\nREDIS_URL=redis://x\n", encoding="utf-8")
    cfg = jira.load_config({}, [f])
    assert (cfg.client_id, cfg.client_secret) == ("from-file", "file-secret")
    assert "do-not-keep-me" not in repr(cfg) and not hasattr(cfg, "scopes")
    assert jira.load_config({"ATLASSIAN_CLIENT_ID": "from-env"}, [f]).client_id == "from-env"  # the environment wins


def test_frontend_redirect_keeps_the_existing_query():
    assert jira.frontend_redirect("http://x/requirement", jira="connected") == "http://x/requirement?jira=connected"
    assert jira.frontend_redirect("http://x/requirement?a=1", jira="error", reason="state_invalid") == "http://x/requirement?a=1&jira=error&reason=state_invalid"


# ------------------------------------------------------------------------------------------------------------------ status and connect
def test_status_says_not_configured_and_connect_is_refused(make_client):  # noqa: F811
    c = make_client(jira_http=FakeJira(), jira_config=lambda: JiraConfig())
    assert c.get(J).json() == {"state": "not_configured", "needs_reconnect": False, "site": None, "connected_at": None, "last_import": None}
    r = c.post(f"{J}/connect")
    assert r.status_code == 409 and error_of(r)["code"] == "jira_not_configured"
    assert "ATLASSIAN" not in error_of(r)["message"]


def test_status_not_connected_and_unknown_project(c):
    assert c.get(J).json()["state"] == "not_connected"
    assert error_of(c.get("/api/projects/99/integrations/jira"))["code"] == "project_not_found"


def test_connect_builds_the_authorize_url_with_a_fresh_state(c):
    first = c.post(f"{J}/connect").json()["authorize_url"]
    second = c.post(f"{J}/connect").json()["authorize_url"]
    parts = urlsplit(first)
    q = {k: v[0] for k, v in parse_qs(parts.query).items()}
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == jira.AUTHORIZE_URL
    assert q["audience"] == "api.atlassian.com" and q["client_id"] == CLIENT_ID and q["response_type"] == "code" and q["prompt"] == "consent"
    assert q["scope"] == " ".join(jira.SCOPES) and "read:board-scope:jira-software" in q["scope"].split() and "read:sprint:jira-software" in q["scope"].split() and q["redirect_uri"] == CFG.redirect_uri
    assert len(q["state"]) >= 32 and q["state"] != parse_qs(urlsplit(second).query)["state"][0]
    assert CLIENT_SECRET not in first
    rows = c.app.state.db.all("SELECT * FROM jira_states")
    assert len(rows) == 2 and all(q["state"] not in str(r) for r in rows)  # only a hash of the state is stored


# ------------------------------------------------------------------------------------------------------------------ callback
def test_callback_exchanges_the_code_and_stores_the_site(c, fake):
    r = connect(c)
    assert r.status_code == 302 and location(r) == "http://localhost:5173/requirement?jira=connected"
    token_call = fake.token_calls()[0]
    assert token_call.method == "POST" and token_call.json == {"grant_type": "authorization_code", "code": "good-code", "redirect_uri": CFG.redirect_uri, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}
    sites_call = [x for x in fake.calls if x.url == jira.RESOURCES_URL][0]
    assert sites_call.headers["Authorization"] == "Bearer tok-access-1"
    status = c.get(J).json()
    assert status["state"] == "connected" and status["site"] == {"name": "Acme", "url": "https://acme.atlassian.net"} and status["connected_at"]
    assert set(status) == {"state", "needs_reconnect", "site", "connected_at", "last_import"}
    row = c.app.state.db.one("SELECT * FROM jira_connections")
    assert row["cloud_id"] == "cloud-1" and row["access_token"] == "tok-access-1" and row["refresh_token"] == "tok-refresh-1"


def test_a_state_works_once(c):
    url = c.post(f"{J}/connect").json()["authorize_url"]
    state = parse_qs(urlsplit(url).query)["state"][0]
    ok = c.get("/api/integrations/jira/callback", params={"code": "good-code", "state": state}, follow_redirects=False)
    assert location(ok).endswith("?jira=connected")
    c.delete(J)
    again = c.get("/api/integrations/jira/callback", params={"code": "good-code", "state": state}, follow_redirects=False)  # a replay of the same address
    assert location(again) == "http://localhost:5173/requirement?jira=error&reason=state_invalid"
    assert c.get(J).json()["state"] == "not_connected"


def test_an_unknown_missing_or_expired_state_is_refused(c, clock):
    for params in ({"code": "good-code", "state": "nope"}, {"code": "good-code"}, {}):
        r = c.get("/api/integrations/jira/callback", params=params, follow_redirects=False)
        assert location(r).endswith("?jira=error&reason=state_invalid")
    url = c.post(f"{J}/connect").json()["authorize_url"]
    state = parse_qs(urlsplit(url).query)["state"][0]
    clock.t += 601  # ten minutes and a second
    r = c.get("/api/integrations/jira/callback", params={"code": "good-code", "state": state}, follow_redirects=False)
    assert location(r).endswith("?jira=error&reason=state_invalid") and c.get(J).json()["state"] == "not_connected"
    assert connect(c).status_code == 302 and c.get(J).json()["state"] == "connected"  # a fresh one is fine


def test_a_state_made_for_one_project_connects_only_that_project(c):
    other = c.post("/api/projects", json={"name": "Second"}).json()["id"]
    assert location(connect(c, other)).endswith("?jira=connected")
    assert c.get(f"/api/projects/{other}/integrations/jira").json()["state"] == "connected"
    assert c.get(J).json()["state"] == "not_connected"


def test_the_user_saying_no_and_a_failed_exchange_go_back_with_an_error(c, fake):
    url = c.post(f"{J}/connect").json()["authorize_url"]
    state = parse_qs(urlsplit(url).query)["state"][0]
    r = c.get("/api/integrations/jira/callback", params={"error": "access_denied", "state": state}, follow_redirects=False)
    assert location(r) == "http://localhost:5173/requirement?jira=error&reason=access_denied"
    url = c.post(f"{J}/connect").json()["authorize_url"]
    state = parse_qs(urlsplit(url).query)["state"][0]
    r = c.get("/api/integrations/jira/callback", params={"code": "bad-code", "state": state}, follow_redirects=False)
    assert location(r) == "http://localhost:5173/requirement?jira=error&reason=exchange_failed"
    fake.sites = []
    assert location(connect(c)).endswith("?jira=error&reason=no_site")
    assert c.get(J).json()["state"] == "not_connected"


def test_the_return_address_is_the_configured_one(make_client, fake):  # noqa: F811
    cfg = JiraConfig(CLIENT_ID, CLIENT_SECRET, CFG.redirect_uri, "https://app.example/requirement?x=1")
    c = make_client(jira_http=fake, jira_config=lambda: cfg)
    assert location(connect(c)) == "https://app.example/requirement?x=1&jira=connected"


# ------------------------------------------------------------------------------------------------------------------ tokens
def test_the_refresh_token_rotates_and_the_new_one_is_saved(c, fake, clock):
    connect(c)
    assert c.get(f"{J}/projects").status_code == 200 and len(fake.token_calls()) == 1  # a fresh token is used as it is
    clock.t += 3600 - 30  # inside the one-minute margin: refreshed before the call
    assert c.get(f"{J}/projects").status_code == 200
    refresh = fake.token_calls()[-1]
    assert refresh.json["grant_type"] == "refresh_token" and refresh.json["refresh_token"] == "tok-refresh-1"
    row = c.app.state.db.one("SELECT * FROM jira_connections")
    assert (row["access_token"], row["refresh_token"]) == ("tok-access-2", "tok-refresh-2")
    clock.t += 3600
    assert c.get(f"{J}/projects").status_code == 200
    assert fake.token_calls()[-1].json["refresh_token"] == "tok-refresh-2"  # the rotated one, not the first
    assert c.get(J).json()["state"] == "connected"


def test_a_refresh_that_fails_marks_the_connection_expired_until_it_is_connected_again(c, fake, clock):
    connect(c)
    fake.refresh = "tok-refresh-other"  # Atlassian no longer knows ours (revoked, or unused for 90 days)
    clock.t += 7200
    r = c.get(f"{J}/projects")
    assert r.status_code == 409 and error_of(r)["code"] == "jira_expired"
    status = c.get(J).json()
    assert status["state"] == "expired" and status["site"]["name"] == "Acme"
    row = c.app.state.db.one("SELECT * FROM jira_connections")
    assert row["access_token"] == "" and row["refresh_token"] == ""
    calls = len(fake.calls)
    assert error_of(c.get(f"{J}/projects"))["code"] == "jira_expired" and len(fake.calls) == calls  # no more attempts with nothing to refresh
    assert error_of(importing(c))["code"] == "jira_expired"
    fake.refresh = "tok-refresh-0"
    assert location(connect(c)).endswith("?jira=connected") and c.get(J).json()["state"] == "connected"
    assert c.get(f"{J}/projects").status_code == 200


def test_a_401_gets_one_refresh_and_a_second_try(c, fake):
    connect(c)
    fake.access = "tok-access-revoked"  # the access token stopped working before it ran out
    fake.refresh = "tok-refresh-1"
    r = c.get(f"{J}/projects")
    assert r.status_code == 200 and [p["key"] for p in r.json()] == ["ABC", "DEF", "GHI"]
    assert [x.json["grant_type"] for x in fake.token_calls()] == ["authorization_code", "refresh_token"]


def test_a_401_that_survives_the_refresh_is_a_missing_permission_not_an_expiry(c, fake):
    connect(c)
    fake.push("agile/1.0/board", 401, 401)
    r = c.get(f"{J}/boards", params={"project_key": "ABC"})
    assert r.status_code == 403 and error_of(r)["code"] == "jira_scope_missing"
    assert c.get(J).json()["state"] == "connected"


def test_a_403_on_boards_or_sprints_also_asks_to_reconnect(c, fake):
    connect(c)
    fake.push("agile/1.0/board", 403)
    r = c.get(f"{J}/boards", params={"project_key": "ABC"})
    assert r.status_code == 403 and error_of(r)["code"] == "jira_scope_missing" and "Reconnect Jira to allow board access" in error_of(r)["message"]
    fake.push("agile/1.0/board/7/sprint", 403)
    assert error_of(c.get(f"{J}/sprints", params={"board_id": 7, "target_sprint_id": "match"}))["code"] == "jira_scope_missing"


def test_a_connection_made_with_fewer_permissions_is_flagged_and_keeps_its_data(c, fake):
    connect(c)
    assert c.get(J).json()["needs_reconnect"] is False
    with c.app.state.db.connect() as con:
        con.execute("UPDATE jira_connections SET scope='read:jira-work read:jira-user offline_access'")
    st = c.get(J).json()
    assert st["state"] == "connected" and st["needs_reconnect"] is True and st["site"]["name"] == "Acme"
    assert c.get(f"{J}/projects").status_code == 200  # still usable without boards
    with c.app.state.db.connect() as con:
        con.execute("UPDATE jira_connections SET scope=''")  # made before the permissions were recorded
    assert c.get(J).json()["needs_reconnect"] is True
    connect(c)  # reconnecting stores the new permissions
    assert c.get(J).json()["needs_reconnect"] is False


def test_requests_are_never_anything_but_get_to_jira(c, fake):
    connect(c)
    c.get(f"{J}/projects")
    c.get(f"{J}/boards", params={"project_key": "ABC"})
    c.get(f"{J}/sprints", params={"board_id": 7, "target_sprint_id": "match"})
    importing(c, board_id=7)
    api = [x for x in fake.calls if x.url.startswith(PREFIX)]
    assert api and {x.method for x in api} == {"GET"}
    assert {x.method for x in fake.calls if x.url not in (jira.TOKEN_URL,)} == {"GET"}


# ------------------------------------------------------------------------------------------------------------------ http: retries and errors
def test_429_and_5xx_are_tried_again_with_the_servers_pause(c, fake):
    connect(c)
    fake.push("api/3/project/search", Response(429, {}, {"Retry-After": "3"}), 503)
    r = c.get(f"{J}/projects")
    assert r.status_code == 200 and c.slept == [3.0, 2.0] and len(fake.api_calls("project/search")) == 4  # two failures, then the two pages


def test_a_request_that_keeps_failing_ends_in_a_plain_error(c, fake):
    connect(c)
    fake.push("api/3/project/search", 503, 503, 503, 503)
    r = c.get(f"{J}/projects")
    assert r.status_code == 502 and error_of(r)["code"] == "jira_request_failed" and len(fake.api_calls("project/search")) == jira.MAX_TRIES
    fake.push("api/3/project/search", *([NetworkError()] * jira.MAX_TRIES))
    r = c.get(f"{J}/projects")
    assert r.status_code == 502 and error_of(r)["code"] == "jira_unreachable"
    assert c.get(J).json()["state"] == "connected"  # a Jira outage is not an expired connection


def test_a_pause_is_never_longer_than_thirty_seconds(c, fake):
    connect(c)
    fake.push("api/3/project/search", Response(429, {}, {"retry-after": "9999"}))
    assert c.get(f"{J}/projects").status_code == 200 and c.slept == [30.0]


def test_jira_answers_become_fixed_messages(c, fake):
    connect(c)
    for status, code, http in ((403, "jira_forbidden", 403), (404, "jira_not_found", 404), (400, "jira_bad_request", 400), (418, "jira_request_failed", 502)):
        fake.push("api/3/project/search", Response(status, {"errorMessages": [f"secret detail {status}"]}))
        r = c.get(f"{J}/projects")
        assert (r.status_code, error_of(r)["code"]) == (http, code) and "secret detail" not in r.text


# ------------------------------------------------------------------------------------------------------------------ reads and paging
def test_projects_boards_and_sprints_are_listed_across_pages(c, fake):
    connect(c)
    assert c.get(f"{J}/projects").json() == [{"key": "ABC", "name": "Alpha"}, {"key": "DEF", "name": "Delta"}, {"key": "GHI", "name": "Gamma"}]
    assert len(fake.api_calls("project/search")) == 2  # three projects, two per page
    assert c.get(f"{J}/boards", params={"project_key": "abc"}).json() == [{"id": 7, "name": "ABC board", "type": "scrum"}, {"id": 8, "name": "ABC kanban", "type": "kanban"}]
    assert fake.api_calls("/board")[-1].params["projectKeyOrId"] == "ABC"
    s = c.get(f"{J}/sprints", params={"board_id": 7, "target_sprint_id": "match"}).json()
    assert [(x["id"], x["name"], x["state"], x["start_date"], x["end_date"], x["goal"]) for x in s] == [(10, "Sprint 1", "active", "2026-10-05", "2026-10-16", "Login"), (11, "Sprint 2", "future", "2026-10-19", "2026-10-30", None)]
    assert fake.api_calls("/board/7/sprint")[-1].params["state"] == "active,future"
    assert [x["id"] for x in c.get(f"{J}/sprints", params={"board_id": 7, "target_sprint_id": "match", "states": "closed"}).json()] == [9]
    assert c.get(f"{J}/sprints", params={"board_id": 8}).json() == []  # a board without sprints


def test_reads_need_a_connection_and_valid_parameters(c):
    assert error_of(c.get(f"{J}/projects"))["code"] == "jira_not_connected"
    connect(c)
    assert c.get(f"{J}/boards", params={"project_key": "not a key"}).status_code == 400
    assert c.get(f"{J}/sprints", params={"board_id": 7, "target_sprint_id": "match", "states": "soon"}).status_code == 400
    assert c.get(f"{J}/sprints", params={"board_id": "x"}).status_code == 422


# ------------------------------------------------------------------------------------------------------------------ ADF
RICH = {"type": "doc", "version": 1, "content": [
    {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Login"}]},
    {"type": "paragraph", "content": [{"type": "text", "text": "The user "}, {"type": "text", "text": "shall", "marks": [{"type": "strong"}]}, {"type": "text", "text": " sign in."},
                                      {"type": "hardBreak"}, {"type": "text", "text": "Second line "}, {"type": "mention", "attrs": {"id": "1", "text": "@Sam"}},
                                      {"type": "text", "text": " "}, {"type": "emoji", "attrs": {"shortName": ":smile:", "text": "🙂"}}]},
    {"type": "bulletList", "content": [
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "email"}]}]},
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "password"}]},
                                         {"type": "bulletList", "content": [{"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "8 characters"}]}]}]}]}]},
    {"type": "orderedList", "attrs": {"order": 1}, "content": [
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "open"}]}]},
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "submit"}]}]}]},
    {"type": "codeBlock", "content": [{"type": "text", "text": "POST /login"}]},
    {"type": "mediaSingle", "content": [{"type": "media", "attrs": {"id": "file-1"}}]},
    {"type": "table", "content": [
        {"type": "tableRow", "content": [{"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Field"}]}]}, {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Rule"}]}]}]},
        {"type": "tableRow", "content": [{"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "email"}]}]}, {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "required"}]}]}]}]},
    {"type": "panel", "attrs": {"panelType": "info"}, "content": [{"type": "paragraph", "content": [{"type": "inlineCard", "attrs": {"url": "https://wiki.example/login"}}]}]},
    {"type": "somethingNew", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "kept"}]}]},
]}


def test_adf_becomes_plain_text():
    text = jira.adf_to_text(RICH)
    assert text == "\n".join([
        "Login", "", "The user shall sign in.", "Second line @Sam 🙂", "", "- email", "- password", "  - 8 characters", "", "1. open", "2. submit", "", "POST /login", "",
        "Field | Rule", "email | required", "", "https://wiki.example/login", "", "kept"])
    assert "file-1" not in text and "\n\n\n" not in text


def test_adf_edge_cases():
    assert jira.adf_to_text(None) == "" and jira.adf_to_text({}) == "" and jira.adf_to_text({"type": "doc", "content": []}) == ""
    assert jira.adf_to_text("  already plain  ") == "already plain"  # an older description is a string
    assert jira.adf_to_text({"type": "doc", "content": ["not a node", {"type": "paragraph", "content": [{"type": "text", "text": "ok"}]}]}) == "ok"
    assert jira.adf_to_text({"type": "orderedList", "attrs": {"order": 3}, "content": [{"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "x"}]}]}]}) == "3. x"


# ------------------------------------------------------------------------------------------------------------------ import: sprints and the issue map
def standard(fake):
    s1, s2 = fake.sprints[0], fake.sprints[1]
    fake.issues = [
        issue("ABC-2", "Users shall reset their password by email", desc=adf("The link works for one hour."), sprint_=s1, status="In Progress"),
        issue("ABC-1", "The system shall let customers sign in", kind="Task", sprint_=s1),
        issue("ABC-10", "The portal shall show the account balance", desc=adf("Updated every minute."), sprint_=s2, closed=[fake.sprints[2]]),
        issue("ABC-11", "", desc=None, sprint_=s2),  # no text at all
    ]


def test_import_maps_sprints_and_stores_the_issues(c, fake):
    connect(c)
    standard(fake)
    r = importing(c, board_id=7, set_current=True)
    assert r.status_code == 200
    assert r.json() == {"sprints_created": 2, "sprints_updated": 0, "issues_new": 3, "issues_updated": 0, "issues_unchanged": 0, "skipped": 1, "missing": 0, "truncated": False,
                        "queued": 0, "job_id": None, "analysis_error": None, "target_sprint": None, "matched": True}
    jql = fake.api_calls("search/jql")[0].params["jql"]
    assert jql == 'project = "ABC" AND issuetype in ("Story", "Task") AND sprint in (10,11) ORDER BY key ASC'  # defaults: Story and Task, active and future sprints
    assert fake.api_calls("/board/7/sprint")[0].params["state"] == "active,future"
    by_name = sprints(c)
    s1 = by_name["Sprint 1 (Jira)"]  # "Sprint 1" was taken by the sprint every project starts with
    assert (s1["origin"], s1["start_date"], s1["end_date"], s1["goal"], s1["confirmed"]) == ("jira", "2026-10-05", "2026-10-16", "Login", True)
    assert by_name["Sprint 2"]["origin"] == "jira" and by_name["Sprint 2"]["start_date"] == "2026-10-19"
    assert s1["is_current"] is True  # the active Jira sprint, because set_current was on
    rows = jira_issues(c)
    assert sorted(rows) == ["ABC-1", "ABC-10", "ABC-2"]
    assert rows["ABC-2"]["text"] == "Users shall reset their password by email\n\nThe link works for one hour."
    assert (rows["ABC-2"]["issue_type"], rows["ABC-2"]["status"], rows["ABC-1"]["issue_type"]) == ("Story", "In Progress", "Task")
    assert rows["ABC-2"]["url"] == "https://acme.atlassian.net/browse/ABC-2"
    assert rows["ABC-2"]["sprint_id"] == s1["id"] and rows["ABC-10"]["sprint_id"] == by_name["Sprint 2"]["id"]
    src = c.get("/api/projects/1/sources").json()
    assert [(s["filename"], s["source_type"], s["ext"], s["analysis_state"], s["requirements"]) for s in src] == [("Jira · ABC", "jira", ".jira", "not_analyzed", 0)]
    assert c.get(J).json()["last_import"]["counts"]["issues_new"] == 3


def test_the_current_sprint_changes_only_when_asked(c, fake):
    connect(c)
    standard(fake)
    importing(c, board_id=7)
    assert sprints(c)["Sprint 1"]["is_current"] is True and sprints(c)["Sprint 1 (Jira)"]["is_current"] is False
    importing(c, board_id=7, set_current=True)
    assert sprints(c)["Sprint 1 (Jira)"]["is_current"] is True


def test_sprint_states_and_issue_types_are_passed_on(c, fake):
    connect(c)
    standard(fake)
    r = importing(c, board_id=7, sprint_states=["closed", "active"], issue_types=["Bug", "Epic"])
    assert r.status_code == 200
    assert fake.api_calls("/board/7/sprint")[0].params["state"] == "closed,active"
    assert fake.api_calls("search/jql")[0].params["jql"] == 'project = "ABC" AND issuetype in ("Bug", "Epic") AND sprint in (10,9) ORDER BY key ASC'
    assert {s["name"] for s in c.get("/api/projects/1/sprints").json()} >= {"Old sprint", "Sprint 1 (Jira)"}


def test_issues_are_read_page_by_page(c, fake):
    connect(c)
    fake.issues = [issue(f"ABC-{n}", f"Requirement number {n} shall hold") for n in range(1, 8)]
    assert importing(c).json()["issues_new"] == 7
    pages = fake.api_calls("search/jql")
    assert len(pages) == 4 and "nextPageToken" not in pages[0].params and [p.params["nextPageToken"] for p in pages[1:]] == ["p2", "p4", "p6"]
    assert "sprint in" not in pages[0].params["jql"]  # no board: every issue of the project


def test_without_a_board_the_sprints_come_from_the_issues(c, fake):
    connect(c)
    s1, s2, old = fake.sprints
    fake.issues = [issue("ABC-1", "Alpha requirement text", sprint_=s1), issue("ABC-2", "Beta requirement text", sprint_=old), issue("ABC-3", "Gamma requirement text")]
    r = importing(c, set_current=True).json()
    assert r["sprints_created"] == 1 and r["issues_new"] == 3  # the closed one is not in the chosen states, the issue in it just follows the document
    rows = jira_issues(c)
    current = sprints(c)["Sprint 1 (Jira)"]["id"]  # made current by set_current, so it is also where issues without a known Jira sprint go
    assert rows["ABC-1"]["sprint_id"] == current and rows["ABC-2"]["sprint_id"] == current and rows["ABC-3"]["sprint_id"] == current
    assert not fake.api_calls("/board/")


def test_a_board_with_no_matching_sprints_imports_nothing(c, fake):
    connect(c)
    fake.sprints = []
    r = importing(c, board_id=7).json()
    assert r["issues_new"] == 0 and not fake.api_calls("search/jql") and c.get("/api/projects/1/sources").json() == []


def test_the_import_checks_its_input(c, fake):
    connect(c)
    for body in ({"project_key": "a b"}, {"project_key": ""}, {"project_key": "ABC", "sprint_states": ["later"]}, {"project_key": "ABC", "issue_types": ['Story"; DROP']},
                 {"project_key": "ABC", "policy": "most"}):
        assert importing(c, **body).status_code == 400
    assert not fake.api_calls("search/jql")
    assert importing(c, project_key="abc").status_code == 200  # a key is case-insensitive
    assert fake.api_calls("search/jql")[0].params["jql"].startswith('project = "ABC"')


def test_a_long_search_is_cut_at_the_limit_and_says_so(c, fake, monkeypatch):
    connect(c)
    monkeypatch.setattr(jira, "MAX_ISSUES", 4)
    fake.issues = [issue(f"ABC-{n}", f"Requirement number {n} shall hold") for n in range(1, 8)]
    r = importing(c).json()
    assert r["issues_new"] == 4 and r["truncated"] is True and r["missing"] == 0


def test_upload_refuses_the_jira_type(c):
    r = c.post("/api/projects/1/sources", files=[("files", ("a.txt", b"The system shall log in.", "text/plain"))], data={"source_type": "jira"})
    assert r.status_code == 400 and error_of(r)["code"] == "invalid_parameter"


# ------------------------------------------------------------------------------------------------------------------ import: idempotent by key (with the analysis)
def rows_by_key(c):
    return {r["jira"]["key"]: r for r in c.get("/api/projects/1/requirements").json()["items"] if r["jira"]}


@needs_models
def test_import_runs_the_normal_analysis_and_shows_the_jira_key(c, fake):
    connect(c)
    standard(fake)
    r = c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match", "policy": "all"})
    assert r.status_code == 200
    out = r.json()
    assert out["issues_new"] == 3 and out["analysis_error"] is None and out["job_id"] and out["queued"] == 3
    assert c.app.state.manager.wait_idle(60)
    rows = rows_by_key(c)
    assert sorted(rows) == ["ABC-1", "ABC-10", "ABC-2"]
    ref = rows["ABC-2"]["jira"]
    assert ref == {"key": "ABC-2", "type": "Story", "status": "In Progress", "url": "https://acme.atlassian.net/browse/ABC-2"}
    assert rows["ABC-2"]["source_file"] == "Jira · ABC" and rows["ABC-2"]["text"].startswith("Users shall reset their password by email")
    assert rows["ABC-2"]["sprint_id"] == sprints(c)["Sprint 1 (Jira)"]["id"] and rows["ABC-10"]["sprint_id"] == sprints(c)["Sprint 2"]["id"]
    detail = c.get(f"/api/requirements/{rows['ABC-1']['uid']}").json()
    assert detail["jira"]["key"] == "ABC-1" and detail["jira"]["type"] == "Task" and detail["source"]["clause_label"] == "ABC-1"
    assert c.get("/api/projects/1/sources").json()[0]["analysis_state"] == "analyzed"
    assert c.get("/api/projects/1/summary").json()["task_drafts"]["total"] == 3


@needs_models
def test_importing_again_changes_nothing_and_a_changed_issue_follows_the_reanalysis_rules(c, fake):
    connect(c)
    standard(fake)
    c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match", "policy": "all"})
    assert c.app.state.manager.wait_idle(60)
    rows = rows_by_key(c)
    uids = {k: v["uid"] for k, v in rows.items()}
    for key in ("ABC-1", "ABC-2"):
        assert c.put(f"/api/requirements/{uids[key]}/decision", json={"decision": "accepted", "note": f"ok {key}"}).status_code == 200
    drafts = {r["uid"]: r["generation_state"] for r in c.get("/api/projects/1/requirements").json()["items"]}
    calls = len(fake.calls)

    again = c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match", "policy": "all"}).json()
    assert again["issues_new"] == 0 and again["issues_unchanged"] == 3 and again["issues_updated"] == 0 and again["queued"] == 0 and again["sprints_created"] == 0 and again["sprints_updated"] == 0
    assert {k: v["uid"] for k, v in rows_by_key(c).items()} == uids  # the same requirements
    assert {r["uid"]: r["generation_state"] for r in c.get("/api/projects/1/requirements").json()["items"]} == drafts  # no new drafts
    assert c.get(f"/api/requirements/{uids['ABC-1']}").json()["decision"]["decision"] == "accepted"
    assert len(fake.calls) > calls  # it did read Jira again

    # ABC-2 changes its text and ABC-10 only its status
    fake.issues[0] = issue("ABC-2", "Users shall reset their password by email within five minutes", desc=adf("The link works for one hour."), sprint_=fake.sprints[0], status="Done")
    fake.issues[2] = issue("ABC-10", "The portal shall show the account balance", desc=adf("Updated every minute."), sprint_=fake.sprints[1], status="In Review")
    changed = c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match", "policy": "all"}).json()
    assert (changed["issues_new"], changed["issues_updated"], changed["issues_unchanged"]) == (0, 2, 1)
    assert c.app.state.manager.wait_idle(60)
    rows = rows_by_key(c)
    assert rows["ABC-1"]["uid"] == uids["ABC-1"] and rows["ABC-10"]["uid"] == uids["ABC-10"]  # untouched text: same requirement
    assert rows["ABC-2"]["uid"] != uids["ABC-2"] and "within five minutes" in rows["ABC-2"]["text"]  # a new requirement for the new text
    assert rows["ABC-2"]["decision"] is None and c.get(f"/api/requirements/{uids['ABC-1']}").json()["decision"]["decision"] == "accepted"
    assert rows["ABC-10"]["jira"]["status"] == "In Review" and rows["ABC-2"]["jira"]["status"] == "Done"
    audit = c.app.state.db.all("SELECT uid, decision, reason FROM decision_audit WHERE reason LIKE 'reanalysis%'")
    assert audit == [{"uid": uids["ABC-2"], "decision": "accepted", "reason": "reanalysis_changed"}]  # the old decision is kept for the record
    assert len(c.get("/api/projects/1/requirements").json()["items"]) == 3


@needs_models
def test_an_issue_that_moves_sprint_in_jira_moves_its_requirement(c, fake):
    connect(c)
    standard(fake)
    c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match"})
    s2 = sprints(c)["Sprint 2"]["id"]
    assert rows_by_key(c)["ABC-1"]["sprint_id"] == sprints(c)["Sprint 1 (Jira)"]["id"]
    fake.issues[1] = issue("ABC-1", "The system shall let customers sign in", kind="Task", sprint_=fake.sprints[1])
    out = c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match"}).json()
    assert out["issues_updated"] == 1 and out["queued"] == 0
    assert rows_by_key(c)["ABC-1"]["sprint_id"] == s2


@needs_models
def test_an_issue_missing_from_jira_is_marked_and_audited_not_deleted(c, fake):
    connect(c)
    standard(fake)
    c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match"})
    uid = rows_by_key(c)["ABC-1"]["uid"]
    c.put(f"/api/requirements/{uid}/decision", json={"decision": "accepted"})
    gone = fake.issues.pop(1)  # ABC-1 left the selected sprints
    out = c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match"}).json()
    assert out["missing"] == 1 and out["issues_new"] == 0 and out["issues_unchanged"] == 2
    assert "ABC-1" in rows_by_key(c) and rows_by_key(c)["ABC-1"]["uid"] == uid and rows_by_key(c)["ABC-1"]["decision"] == "accepted"
    assert jira_issues(c)["ABC-1"]["missing"] == 1
    log = c.app.state.db.all("SELECT missing_keys FROM jira_imports ORDER BY id")
    assert json.loads(log[-1]["missing_keys"]) == ["ABC-1"] and json.loads(log[0]["missing_keys"]) == []
    again = c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match"}).json()
    assert again["missing"] == 0  # already marked: not counted twice
    fake.issues.insert(1, gone)  # and it comes back
    back = c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match"}).json()
    assert back["missing"] == 0 and jira_issues(c)["ABC-1"]["missing"] == 0 and rows_by_key(c)["ABC-1"]["uid"] == uid


def test_a_different_scope_does_not_make_other_issues_missing(c, fake):
    connect(c)
    standard(fake)
    importing(c, board_id=7)
    fake.issues = [issue("ABC-1", "The system shall let customers sign in", kind="Task")]
    assert importing(c).json()["missing"] == 0  # no board: another scope, the board's issues are not compared with it


# ------------------------------------------------------------------------------------------------------------------ disconnect and leaks
def test_disconnect_forgets_the_connection_and_keeps_what_was_imported(c, fake):
    connect(c)
    standard(fake)
    importing(c, board_id=7)
    r = c.delete(J)
    assert r.status_code == 204 and r.content == b""
    assert c.get(J).json() == {"state": "not_connected", "needs_reconnect": False, "site": None, "connected_at": None, "last_import": c.get(J).json()["last_import"]}
    assert c.app.state.db.one("SELECT COUNT(*) n FROM jira_connections")["n"] == 0
    assert len(jira_issues(c)) == 3 and c.get("/api/projects/1/sources").json()[0]["filename"] == "Jira · ABC"
    assert sprints(c)["Sprint 2"]["origin"] == "jira"
    assert error_of(importing(c))["code"] == "jira_not_connected"
    assert c.delete(J).status_code == 204  # disconnecting twice is fine


def test_deleting_a_jira_document_removes_its_issue_map_and_a_new_import_starts_again(c, fake):
    connect(c)
    standard(fake)
    importing(c, board_id=7)
    sid = c.get("/api/projects/1/sources").json()[0]["id"]
    assert c.delete(f"/api/projects/1/sources/{sid}").status_code == 204
    assert jira_issues(c) == {}
    assert importing(c, board_id=7).json()["issues_new"] == 3


@needs_models
def test_no_token_or_secret_leaves_the_service(c, fake, caplog):
    caplog.set_level("DEBUG")
    connect(c)
    standard(fake)
    fake.push("api/3/project/search", Response(403, {"errorMessages": ["tok-access-1 is not allowed"]}))
    texts = [c.get(J).text, c.get(f"{J}/projects").text, c.get(f"{J}/projects").text, c.get(f"{J}/boards", params={"project_key": "ABC"}).text, c.get(f"{J}/sprints", params={"board_id": 7, "target_sprint_id": "match"}).text]
    texts.append(c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match", "policy": "all"}).text)
    assert c.app.state.manager.wait_idle(60)
    texts += [c.get("/api/projects/1/requirements").text, c.get("/api/projects/1/sources").text, c.get("/api/projects/1/overview").text, c.get("/api/projects/1/export?format=csv").text,
              c.get("/api/projects/1/export?format=json").text, c.get("/api/projects/1/sync").text, c.get("/openapi.json").text, c.post(f"{J}/connect").text]
    texts.append(json.dumps(neo4j_store.build_bundle(c.app.state.db, 1, "demo-project", "x", all_documents=True).as_dict(), default=str))
    texts.append(" | ".join(r.getMessage() for r in caplog.records if r.name.startswith("c1")))  # our own log lines (the test client logs its own requests)
    texts.append(repr(c.app.state.jira.config()) + str(c.app.state.jira.config()))
    fake.token_status = 400
    c.app.state.db.run("UPDATE jira_connections SET expires_at='2000-01-01T00:00:00+00:00'")
    r = c.get(f"{J}/projects")
    texts.append(r.text)
    assert r.status_code == 409
    for text in texts:
        for secret in SECRETS:
            assert secret not in text, secret
    con = sqlite3.connect(c.app.state.db.path)
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        dump = str(con.execute(f"SELECT * FROM {name}").fetchall())
        assert CLIENT_SECRET not in dump  # the client secret is never stored
        if name != "jira_connections":
            assert "tok-access-" not in dump and "tok-refresh-" not in dump, name
    con.close()


def test_the_http_client_hides_network_details(monkeypatch):
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("could not connect to https://secret.example with token tok-access-9")

    monkeypatch.setattr(httpx, "request", boom)
    with pytest.raises(NetworkError) as exc:
        HttpxClient().request("GET", "https://api.atlassian.com/x", headers={"Authorization": "Bearer tok-access-9"})
    assert "tok-access-9" not in str(exc.value) and str(exc.value) == ""


def test_the_documented_paths_exist_in_the_schema(c):
    paths = c.get("/openapi.json").json()["paths"]
    base = "/api/projects/{pid}/integrations/jira"
    assert {"get", "delete"} <= set(paths[base]) and "post" in paths[base + "/connect"] and "post" in paths[base + "/import"]
    assert all(p in paths for p in (base + "/projects", base + "/boards", base + "/sprints", "/api/integrations/jira/callback"))


def test_an_import_whose_analysis_cannot_run_still_keeps_the_issues(c, fake, monkeypatch):
    from agents.requirement_agent.api import analysis
    from agents.requirement_agent.api.errors import ApiError

    def models_missing(*a, **k):
        raise ApiError(503, "models_missing", "saved models are missing")

    monkeypatch.setattr(analysis, "run_part_a", models_missing)
    connect(c)
    standard(fake)
    r = c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "target_sprint_id": "match"}).json()
    assert r["issues_new"] == 3 and r["analysis_error"] == "models_missing" and r["queued"] == 0
    assert len(jira_issues(c)) == 3 and c.get("/api/projects/1/sources").json()[0]["analysis_state"] == "not_analyzed"


def test_an_import_is_refused_while_drafts_are_being_written(c, fake):
    from tests.test_c1_neo4j import seed
    seed(c.app.state.db, project=False)
    c.app.state.db.run("UPDATE generation SET state='running' WHERE uid='p1-REQ-001'")
    connect(c)
    standard(fake)
    r = importing(c, board_id=7)
    assert r.status_code == 409 and error_of(r)["code"] == "project_busy" and not fake.api_calls("search/jql")


# ------------------------------------------------------------------------------------------------------------------ the target sprint
def test_by_default_everything_goes_to_the_current_sprint_and_no_jira_sprint_is_created(c, fake):
    connect(c)
    standard(fake)
    r = c.post(f"{J}/import", json={"project_key": "ABC", "board_id": 7, "analyze": False}).json()
    assert r["sprints_created"] == 0 and r["matched"] is False and r["target_sprint"]["name"] == "Sprint 1"
    assert set(sprints(c)) == {"Sprint 1"}  # no empty Jira sprints
    cur = sprints(c)["Sprint 1"]["id"]
    assert {v["sprint_id"] for v in jira_issues(c).values()} == {cur}
    assert c.get("/api/projects/1/sources").json()[0]["default_sprint_id"] == cur


def test_a_chosen_sprint_receives_everything_and_a_bad_one_is_refused(c, fake):
    connect(c)
    standard(fake)
    mine = c.post("/api/projects/1/sprints", json={"name": "Next"}).json()["id"]
    r = c.post(f"{J}/import", json={"project_key": "ABC", "analyze": False, "target_sprint_id": mine}).json()
    assert r["target_sprint"] == {"id": mine, "name": "Next"} and r["sprints_created"] == 0
    assert {v["sprint_id"] for v in jira_issues(c).values()} == {mine}
    bad = c.post(f"{J}/import", json={"project_key": "ABC", "target_sprint_id": 999})
    assert bad.status_code == 404 and error_of(bad)["code"] == "sprint_not_found"
    assert c.post(f"{J}/import", json={"project_key": "ABC", "target_sprint_id": "nope"}).status_code == 422


def test_a_reimport_with_the_default_keeps_issues_where_they_are(c, fake):
    connect(c)
    standard(fake)
    mine = c.post("/api/projects/1/sprints", json={"name": "Next"}).json()["id"]
    c.post(f"{J}/import", json={"project_key": "ABC", "analyze": False, "target_sprint_id": mine})
    again = c.post(f"{J}/import", json={"project_key": "ABC", "analyze": False}).json()  # no sprint chosen: known issues stay
    assert again["issues_unchanged"] == 3 and {v["sprint_id"] for v in jira_issues(c).values()} == {mine}


def test_match_reuses_the_c1_sprint_of_a_jira_sprint_and_never_makes_a_second_one(c, fake):
    connect(c)
    standard(fake)
    first = importing(c, board_id=7).json()
    assert first["sprints_created"] == 2 and first["matched"] is True and first["target_sprint"] is None
    ids = {r["external_id"]: r["id"] for r in c.app.state.db.all("SELECT id, external_id FROM sprints WHERE origin='jira'")}
    assert set(ids) == {"10", "11"}
    again = importing(c, board_id=7).json()
    assert again["sprints_created"] == 0
    assert importing(c).json()["sprints_created"] == 0  # a board-less import finds the same sprints by their Jira id
    assert {r["external_id"]: r["id"] for r in c.app.state.db.all("SELECT id, external_id FROM sprints WHERE origin='jira'")} == ids
    assert len(c.app.state.db.all("SELECT id FROM sprints")) == 3  # the default sprint and the two Jira ones, nothing more


def test_match_does_not_create_jira_sprints_nobody_is_in_unless_the_active_one_is_wanted(c, fake):
    connect(c)
    fake.issues = [issue("ABC-1", "Alpha requirement text", sprint_=fake.sprints[1])]  # only the future sprint has an issue
    importing(c, board_id=7)
    assert [r["external_id"] for r in c.app.state.db.all("SELECT external_id FROM sprints WHERE origin='jira'")] == ["11"]
    importing(c, board_id=7, set_current=True)  # the active sprint (10) was asked for: made and made current
    assert {r["external_id"] for r in c.app.state.db.all("SELECT external_id FROM sprints WHERE origin='jira'")} == {"10", "11"}
    assert sprints(c)["Sprint 1 (Jira)"]["is_current"] is True


def test_two_jira_sprints_with_one_name_stay_two_sprints_but_each_is_made_once(c, fake):
    connect(c)
    s1, s2 = fake.sprints[0], dict(fake.sprints[1], name=fake.sprints[0]["name"])
    fake.sprints[1] = s2
    fake.issues = [issue("ABC-1", "Alpha requirement text", sprint_=s1), issue("ABC-2", "Beta requirement text", sprint_=s2)]
    importing(c, board_id=7)
    importing(c, board_id=7)
    assert len(c.app.state.db.all("SELECT id FROM sprints WHERE origin='jira'")) == 2
