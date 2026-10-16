"""Component 1: runtime choice between the "device" (local Ollama) and a "cloud" OpenAI-compatible server, with a worker pool.

All HTTP goes to a mock OpenAI-compatible server on 127.0.0.1 (plain http is allowed with C1_ALLOW_INSECURE_CLOUD=1, which the fixture sets); there is no real
network. The device backend is a scripted object. Requirements are inserted straight into the workspace database, so these tests need no Part A models,
except the one test that goes through /api/analyze.
"""
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agents.requirement_agent import generation
from agents.requirement_agent.api import engine, service
from agents.requirement_agent.api.db import Database, now
from agents.requirement_agent.api.gen_worker import GenerationManager, mock_reply
from agents.requirement_agent.generation import MockBackend
from tests.test_c1_api import MODELS_PRESENT, SAMPLE, make_client, upload  # noqa: F401  (fixtures)
from tests.test_c1_generation_policy import insert_requirement

KEY = "sk-test-SECRET-key-123"


# ------------------------------------------------------------------------------------------------------------------ mock servers
class MockCloud:
    """A minimal OpenAI-compatible server: GET /v1/models and POST /v1/chat/completions, with switches for the failure cases."""

    def __init__(self, models=("c1-req",), key=None):
        self.models, self.key = list(models), key
        self.delay, self.status, self.gate, self.models_body = 0.0, None, None, None
        self.redirect = False
        self.users, self.auth, self.active, self.max_active = [], [], 0, 0
        self.lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, body=None, headers=None):
                data = json.dumps(body if body is not None else {}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

            def _authorised(self):
                got = self.headers.get("Authorization")
                with outer.lock:
                    outer.auth.append(got)
                return outer.key is None or got == f"Bearer {outer.key}"

            def do_GET(self):
                if not self._authorised():
                    return self._send(401, {"error": "bad key"})
                if self.path.startswith("/redirect/"):
                    return self._send(302, {}, {"Location": f"http://localhost:{outer.port}/v1/models"})
                if self.path == "/v1/models":
                    body = outer.models_body if outer.models_body is not None else {"object": "list", "data": [{"id": m} for m in outer.models]}
                    return self._send(200, body)
                self._send(404, {"error": "no such path"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                if not self._authorised():
                    return self._send(401, {"error": "bad key"})
                if self.path != "/v1/chat/completions":
                    return self._send(404, {})
                user = body["messages"][-1]["content"]
                with outer.lock:
                    outer.users.append(user)
                    outer.active += 1
                    outer.max_active = max(outer.max_active, outer.active)
                try:
                    if outer.gate is not None:
                        outer.gate.wait(30)
                    time.sleep(outer.delay)
                    if outer.redirect:
                        return self._send(302, {}, {"Location": f"http://localhost:{outer.port}/v1/chat/completions"})
                    if outer.status:
                        return self._send(outer.status, {"error": "server problem"})
                    reply = mock_reply(body["messages"][0]["content"], user)
                    self._send(200, {"choices": [{"message": {"role": "assistant", "content": reply}}]})
                finally:
                    with outer.lock:
                        outer.active -= 1

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        if self.gate is not None:
            self.gate.set()
        self.httpd.shutdown()
        self.httpd.server_close()

    def requirement_of(self, user):
        return user[len(generation.USER_PREFIX):]


@pytest.fixture
def cloud(monkeypatch):
    monkeypatch.setenv("C1_ALLOW_INSECURE_CLOUD", "1")
    server = MockCloud().start()
    yield server
    server.stop()


class Device(MockBackend):
    """The scripted 'local Ollama': records its calls and how many ran at once; can be held with a gate."""

    def __init__(self, gate=None):
        super().__init__(mock_reply)
        self.gate, self.entered = gate, threading.Event()
        self.users, self.active, self.max_active, self.lock = [], 0, 0, threading.Lock()

    def generate(self, system, user):
        with self.lock:
            self.users.append(user)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            self.entered.set()
            if self.gate is not None:
                assert self.gate.wait(30)
            return mock_reply(system, user)
        finally:
            with self.lock:
                self.active -= 1


@pytest.fixture
def app(make_client, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")  # the device is never probed over the real network
    monkeypatch.setenv("LLM_MODEL", "c1-req")
    # probing a closed local port can take seconds on Windows and these tests are not about the device probe: the device is reported as not reachable
    monkeypatch.setattr(GenerationManager, "device_reachable", lambda self: False)
    seen = []  # every response body of every call made through `call`

    class Ctx:
        pass

    ctx = Ctx()
    ctx.seen = seen

    def build(device=None, **kw):
        ctx.device = device or Device()
        ctx.client = make_client(backend=ctx.device, backend_name="ollama", model_name="c1-req", **kw)
        ctx.manager = ctx.client.app.state.manager
        ctx.db = ctx.client.app.state.db
        return ctx

    def call(method, path, **kw):
        r = getattr(ctx.client, method)(path, **kw)
        seen.append(r.text)
        return r

    ctx.build, ctx.call = build, call
    return ctx


def add_requirements(ctx, n, text=lambda i: f"The system shall handle case {i} for customers."):
    uids = []
    for i in range(1, n + 1):
        insert_requirement(ctx.db, i, text(i))
        ctx.db.run("UPDATE requirements SET risk_level='NONE', risk_score=0, nfr_probability=0.1, ambiguity_probability=0.1, weak_words='[]', security_cue_words='[]', duplicate_matches='[]', conflict_matches='[]', findings='[]' WHERE uid=?", (f"p1-REQ-{i:03d}",))
        uids.append(f"p1-REQ-{i:03d}")
    return uids


def payload(ctx, uid):
    row = ctx.db.one("SELECT text FROM requirements WHERE uid=?", (uid,))
    return service.generation_block(ctx.db.one("SELECT * FROM generation WHERE uid=?", (uid,)), row["text"])


def states(ctx):
    return {r["uid"]: r["state"] for r in ctx.db.all("SELECT uid, state FROM generation")}


def configure(ctx, server, concurrency=4, key=KEY):
    r = ctx.call("put", "/api/engine", json={"cloud_url": server.url, "cloud_api_key": key, "cloud_model": "c1-req", "cloud_concurrency": concurrency, "cloud_consent": True})
    assert r.status_code == 200, r.text
    t = ctx.call("post", "/api/engine/test", json={"target": "cloud"})
    assert t.status_code == 200 and t.json()["ok"] is True, t.text


def go(ctx, target):
    r = ctx.call("put", "/api/engine", json={"target": target})
    assert r.status_code == 200, r.text
    return r


def wait_for(cond, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def drafts(ctx):
    return ctx.call("get", "/api/projects/1/summary").json()["task_drafts"]


# ------------------------------------------------------------------------------------------------------------------ settings validation
def test_url_is_normalised_to_an_openai_base():
    assert engine.normalize_url("https://gpu.example.com") == "https://gpu.example.com/v1"
    assert engine.normalize_url("https://gpu.example.com/") == "https://gpu.example.com/v1"
    assert engine.normalize_url("  https://gpu.example.com:8443/v1/ ") == "https://gpu.example.com:8443/v1"
    assert engine.normalize_url("https://gpu.example.com/proxy/abc") == "https://gpu.example.com/proxy/abc/v1"
    assert engine.normalize_url("https://gpu.example.com/proxy/v1") == "https://gpu.example.com/proxy/v1"
    assert engine.host_of("https://user@gpu.example.com:8443/v1") == "gpu.example.com"


def test_url_validation_refuses_http_credentials_and_nonsense(monkeypatch):
    monkeypatch.delenv("C1_ALLOW_INSECURE_CLOUD", raising=False)
    bad = ["http://gpu.example.com", "ftp://gpu.example.com", "gpu.example.com", "", "https://", "https://user:pass@gpu.example.com", "https://user@gpu.example.com",
           "https://gpu.example.com/v1?token=abc", "https://gpu.example.com/v1#frag", "https://gpu.example.com:notaport/"]
    for url in bad:
        with pytest.raises(engine.ApiError) as err:
            engine.normalize_url(url)
        assert err.value.status == 400 and err.value.code == "invalid_cloud_url"
        if len(url) > len('https://'):
            assert url not in err.value.message  # the message never repeats the address
        assert "pass" not in err.value.message.replace("password", "")
    monkeypatch.setenv("C1_ALLOW_INSECURE_CLOUD", "1")
    assert engine.normalize_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080/v1"  # plain http only with the explicit switch
    with pytest.raises(engine.ApiError):
        engine.normalize_url("http://user:pass@127.0.0.1:8080")  # credentials are refused even then


def test_put_engine_validates_and_stores_the_normalised_address(app, monkeypatch):
    monkeypatch.delenv("C1_ALLOW_INSECURE_CLOUD", raising=False)
    app.build()
    for url in ("http://gpu.example.com", "https://me:secret@gpu.example.com", "nonsense"):
        r = app.call("put", "/api/engine", json={"cloud_url": url})
        assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_cloud_url", url
        assert url not in r.text
    assert app.call("get", "/api/engine").json()["cloud"]["configured"] is False  # nothing was stored
    r = app.call("put", "/api/engine", json={"cloud_url": "https://gpu.example.com/", "cloud_concurrency": 3, "cloud_model": "my-model"})
    assert r.status_code == 200
    assert app.client.app.state.engine.cloud_url() == "https://gpu.example.com/v1"
    cloud = r.json()["cloud"]
    assert cloud["configured"] is True and cloud["host"] == "gpu.example.com" and cloud["concurrency"] == 3 and cloud["model"] == "my-model" and cloud["reachable"] is None
    for bad in ({"cloud_concurrency": 0}, {"cloud_concurrency": 9}, {"target": "moon"}):
        assert app.call("put", "/api/engine", json=bad).status_code == 422
    assert app.call("put", "/api/engine", json={"cloud_model": "  "}).status_code == 400
    assert app.call("get", "/api/engine").json()["cloud"]["concurrency"] == 3  # refused updates change nothing


def test_defaults_and_partial_updates(app):
    app.build()
    e = app.call("get", "/api/engine").json()
    assert e["target"] == "device" and e["cloud_available"] is True and e["cloud_disabled_reason"] is None
    assert e["device"] == {"backend": "ollama", "model": "c1-req", "reachable": False, "concurrency": 1}
    assert e["cloud"] == {"configured": False, "host": None, "model": "c1-req", "concurrency": 4, "consent": False, "consent_at": None, "reachable": None, "last_tested_at": None}
    app.call("put", "/api/engine", json={"cloud_concurrency": 6})
    app.call("put", "/api/engine", json={"cloud_consent": True})
    e = app.call("get", "/api/engine").json()
    assert e["cloud"]["concurrency"] == 6 and e["cloud"]["consent"] is True and e["cloud"]["consent_at"] and e["target"] == "device"


def test_cloud_is_disabled_in_replay_and_mock_mode(make_client):
    c = make_client()  # the mock backend
    e = c.get("/api/engine").json()
    assert e["cloud_available"] is False and "mock mode" in e["cloud_disabled_reason"]
    c.put("/api/engine", json={"cloud_url": "https://gpu.example.com", "cloud_consent": True})
    r = c.put("/api/engine", json={"target": "cloud"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "cloud_disabled"
    r = c.post("/api/engine/test", json={"target": "cloud"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "cloud_disabled"
    assert c.get("/api/engine").json()["target"] == "device"


# ------------------------------------------------------------------------------------------------------------------ connection test
def test_connection_test_success_and_the_key_is_sent(app, cloud):
    cloud.key = KEY
    app.build()
    configure(app, cloud)
    r = app.call("post", "/api/engine/test", json={"target": "cloud"}).json()
    assert r["ok"] is True and isinstance(r["latency_ms"], int) and r["latency_ms"] >= 0 and "c1-req" in r["detail"]
    assert f"Bearer {KEY}" in cloud.auth  # the key reaches the server ...
    e = app.call("get", "/api/engine").json()["cloud"]
    assert e["reachable"] is True and e["last_tested_at"] and e["host"] == "127.0.0.1"


def test_connection_test_failures_are_sanitised(app, cloud):
    cloud.key = KEY
    app.build()
    configure(app, cloud)
    # wrong key
    app.call("put", "/api/engine", json={"cloud_api_key": "sk-wrong-value-999"})
    r = app.call("post", "/api/engine/test", json={"target": "cloud"}).json()
    assert r["ok"] is False and "HTTP 401" in r["detail"] and "API key" in r["detail"]
    assert app.call("get", "/api/engine").json()["cloud"]["reachable"] is False
    # model not served
    app.call("put", "/api/engine", json={"cloud_api_key": KEY, "cloud_model": "other-model"})
    r = app.call("post", "/api/engine/test", json={"target": "cloud"}).json()
    assert r["ok"] is False and "does not serve the model 'other-model'" in r["detail"]
    # not a model list
    cloud.models_body = {"unexpected": True}
    app.call("put", "/api/engine", json={"cloud_model": "c1-req"})
    r = app.call("post", "/api/engine/test", json={"target": "cloud"}).json()
    assert r["ok"] is False and "not a model list" in r["detail"]
    cloud.models_body = None
    # nothing listening
    dead = MockCloud()
    dead.start()
    dead.stop()  # its port is closed now: nothing listens there
    app.call("put", "/api/engine", json={"cloud_url": dead.url})
    r = app.call("post", "/api/engine/test", json={"target": "cloud"}).json()
    assert r["ok"] is False and r["detail"] == "Could not connect to the server."
    for text in app.seen:
        assert KEY not in text and "sk-wrong-value-999" not in text and cloud.url not in text and f":{cloud.port}" not in text and f":{dead.port}" not in text


def test_probe_reports_timeouts_and_refuses_redirects_to_another_host(cloud):
    cloud.delay = 0  # /models answers at once; make it slow through the gate on a path that waits
    slow = MockCloud()
    slow.start()
    try:
        slow.models_body = {"data": [{"id": "c1-req"}]}
        original = slow.httpd.RequestHandlerClass.do_GET

        def slow_get(self):
            time.sleep(1.0)
            original(self)

        slow.httpd.RequestHandlerClass.do_GET = slow_get
        r = engine.probe(slow.url + "/v1", None, "c1-req", timeout=0.3)
        assert r["ok"] is False and "did not answer within 0.3 seconds" in r["detail"]
    finally:
        slow.stop()
    r = engine.probe(cloud.url + "/redirect/x/v1", None, "c1-req")  # the server redirects to localhost: another host name, refused
    assert r["ok"] is False and "HTTP 302" in r["detail"]


def test_device_test_endpoint(app):
    app.build()
    r = app.call("post", "/api/engine/test", json={"target": "device"})
    assert r.status_code == 200 and r.json()["ok"] is False  # the local model server (port 9 here) does not answer
    assert "local model server" in r.json()["detail"] and isinstance(r.json()["latency_ms"], int)


# ------------------------------------------------------------------------------------------------------------------ switching rules
def test_switching_to_cloud_needs_configuration_consent_and_a_successful_test(app, cloud):
    app.build()

    def attempt():
        r = app.call("put", "/api/engine", json={"target": "cloud"})
        return r.status_code, r.json().get("error", {}).get("code"), r.json().get("error", {}).get("message")

    s, code, message = attempt()
    assert (s, code) == (409, "cloud_not_configured") and message
    app.call("put", "/api/engine", json={"cloud_url": cloud.url})
    s, code, message = attempt()
    assert (s, code) == (409, "cloud_consent_required") and "Consent" in message
    app.call("put", "/api/engine", json={"cloud_consent": True})
    s, code, message = attempt()
    assert (s, code) == (409, "cloud_not_tested") and "test" in message
    cloud.models = ["something-else"]
    assert app.call("post", "/api/engine/test", json={"target": "cloud"}).json()["ok"] is False
    assert attempt()[:2] == (409, "cloud_not_tested")  # a failed test does not count
    cloud.models = ["c1-req"]
    assert app.call("post", "/api/engine/test", json={"target": "cloud"}).json()["ok"] is True
    assert app.call("get", "/api/engine").json()["target"] == "device"  # a test alone does not switch
    assert attempt()[0] == 200
    assert app.call("get", "/api/engine").json()["target"] == "cloud"


def test_a_changed_address_key_or_model_needs_a_new_test(app, cloud):
    app.build()
    configure(app, cloud)
    for change in ({"cloud_api_key": "sk-another-key-456"}, {"cloud_model": "c1-req-v2"}, {"cloud_url": cloud.url + "/other"}):
        app.call("put", "/api/engine", json=change)
        r = app.call("put", "/api/engine", json={"target": "cloud"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "cloud_not_tested", change
        app.call("put", "/api/engine", json={"cloud_api_key": KEY, "cloud_model": "c1-req", "cloud_url": cloud.url})
        assert app.call("post", "/api/engine/test", json={"target": "cloud"}).json()["ok"] is True
    # switching and changing the connection in one request is refused too: that connection has not been tested
    r = app.call("put", "/api/engine", json={"target": "cloud", "cloud_model": "c1-req-v3"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "cloud_not_tested"
    assert app.call("get", "/api/engine").json()["cloud"]["model"] == "c1-req"  # nothing from the refused request was stored


def test_cloud_settings_are_locked_while_cloud_is_active_and_consent_can_be_withdrawn(app, cloud):
    app.build()
    configure(app, cloud)
    go(app, "cloud")
    r = app.call("put", "/api/engine", json={"cloud_url": "https://other.example.com"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "engine_in_use"
    assert app.call("put", "/api/engine", json={"cloud_concurrency": 2}).status_code == 200  # concurrency can change live
    h = app.call("get", "/api/health").json()
    assert h["generation_target"] == "cloud" and h["model"] == "c1-req" and h["generation_reachable"] is True
    r = app.call("put", "/api/engine", json={"cloud_consent": False})  # no consent, no cloud
    assert r.json()["target"] == "device" and r.json()["cloud"]["consent"] is False
    assert app.call("get", "/api/health").json()["generation_target"] == "device"


def test_health_reflects_the_active_target(app, cloud):
    app.build()
    cloud.models = ["c1-req"]
    app.call("put", "/api/engine", json={"cloud_url": cloud.url, "cloud_model": "c1-req", "cloud_consent": True})
    app.call("post", "/api/engine/test", json={"target": "cloud"})
    go(app, "cloud")
    assert app.call("get", "/api/health").json()["generation_target"] == "cloud"
    cloud.stop()  # the cloud server goes away: health shows the result of the last test, it does not probe on every call
    assert app.call("get", "/api/health").json()["generation_reachable"] is True
    assert app.call("post", "/api/engine/test", json={"target": "cloud"}).json()["ok"] is False
    assert app.call("get", "/api/health").json()["generation_reachable"] is False
    go(app, "device")
    assert app.call("get", "/api/health").json()["generation_target"] == "device"


# ------------------------------------------------------------------------------------------------------------------ dispatch
def test_each_item_runs_on_the_target_active_when_it_is_picked(app, cloud):
    gate = threading.Event()
    app.build(Device(gate))
    configure(app, cloud)
    uids = add_requirements(app, 6)
    app.manager.enqueue([(u, 1) for u in uids])
    assert app.device.entered.wait(30)  # the first item is in flight on the device and held there
    assert wait_for(lambda: states(app).get(uids[0]) == "running")
    go(app, "cloud")  # switch while the queue is full: the next items must go to the cloud
    assert wait_for(lambda: len(cloud.users) == 5)
    assert app.device.users and len(app.device.users) == 1  # nothing else went to the device
    gate.set()
    assert app.manager.wait_idle(30)
    on = {u: payload(app, u)["generated_on"] for u in uids}
    assert on[uids[0]] == "device" and all(on[u] == "cloud" for u in uids[1:])
    assert len(app.device.users) == 1 and len(cloud.users) == 5


def test_device_runs_one_at_a_time_and_cloud_up_to_its_concurrency(app, cloud):
    app.build()
    cloud.delay = 0.4
    configure(app, cloud, concurrency=4)
    uids = add_requirements(app, 6)
    app.manager.enqueue([(u, 1) for u in uids])  # on the device first
    assert app.manager.wait_idle(60)
    assert app.device.max_active == 1 and len(app.device.users) == 6
    # cloud with 4 in flight
    app.db.run("DELETE FROM generation")
    app.db.run("DELETE FROM gen_cache")
    go(app, "cloud")
    app.manager.enqueue([(u, 1) for u in uids] + [])
    assert app.manager.wait_idle(60)
    assert cloud.max_active == 4 and len(cloud.users) == 6
    # cloud with 1 in flight
    cloud.users.clear()
    cloud.max_active = 0
    app.db.run("DELETE FROM generation")
    app.db.run("DELETE FROM gen_cache")
    assert app.call("put", "/api/engine", json={"cloud_concurrency": 1}).status_code == 200
    app.manager.enqueue([(u, 1) for u in uids])
    assert app.manager.wait_idle(60)
    assert cloud.max_active == 1 and len(cloud.users) == 6


def test_priority_order_is_kept_on_the_cloud_target(app, cloud):
    app.build()
    cloud.delay = 0.05
    configure(app, cloud, concurrency=1)
    go(app, "cloud")
    uids = add_requirements(app, 5)
    app.manager.set_paused(True)
    app.manager.enqueue([(uids[0], 3), (uids[1], 2), (uids[2], 1), (uids[3], 3), (uids[4], 1)])
    app.manager.run_now(uids[3])  # an explicit request goes first of all
    app.manager.set_paused(False)
    assert app.manager.wait_idle(60)
    order = [cloud.requirement_of(u) for u in cloud.users]
    text = {u: app.db.one("SELECT text FROM requirements WHERE uid=?", (u,))["text"] for u in uids}
    assert order == [text[uids[3]], text[uids[2]], text[uids[4]], text[uids[1]], text[uids[0]]]  # forced, P1 (first come), P2, P3


def test_pause_stops_new_items_but_in_flight_cloud_items_finish(app, cloud):
    app.build()
    cloud.gate = threading.Event()
    configure(app, cloud, concurrency=2)
    go(app, "cloud")
    uids = add_requirements(app, 6)
    app.manager.enqueue([(u, 1) for u in uids])
    assert wait_for(lambda: cloud.active == 2)
    assert app.call("post", "/api/projects/1/generation/pause").json() == {"paused": True}
    cloud.gate.set()  # the two in-flight items complete
    assert wait_for(lambda: sum(1 for s in states(app).values() if s == "done") == 2)
    time.sleep(0.8)
    assert len(cloud.users) == 2  # nothing new was taken while paused
    d = drafts(app)
    assert d["generated"] == 2 and d["queued"] == 4 and d["paused"] is True and d["paused_reason"] is None
    assert app.call("post", "/api/projects/1/generation/resume").json() == {"paused": False}
    assert app.manager.wait_idle(60)
    assert drafts(app)["generated"] == 6 and len(cloud.users) == 6


def test_one_cache_key_is_never_generated_twice_at_once(app, cloud):
    app.build()
    cloud.delay = 0.3
    configure(app, cloud, concurrency=4)
    go(app, "cloud")
    uids = add_requirements(app, 4, text=lambda i: "The system shall export the monthly report as a file.")
    app.manager.enqueue([(u, 1) for u in uids])
    assert app.manager.wait_idle(60)
    assert len(cloud.users) == 1 and cloud.max_active == 1  # one real request; the other three waited and took the cached reply
    assert [payload(app, u)["backend"] for u in uids] == ["ollama"] * 4
    msgs = [app.db.one("SELECT message FROM generation WHERE uid=?", (u,))["message"] for u in uids]
    assert sorted(msgs) == ["", "from cache", "from cache", "from cache"]
    assert set(states(app).values()) == {"done"}


def test_a_failure_never_kills_the_pool(app, cloud):
    class Boom(Device):
        def generate(self, system, user):
            if "case 1 " in user:
                raise RuntimeError("boom with details")
            return super().generate(system, user)

    app.build(Boom())
    uids = add_requirements(app, 4)
    app.manager.enqueue([(u, 1) for u in uids])
    assert app.manager.wait_idle(30)
    st = states(app)
    assert st[uids[0]] == "failed" and all(st[u] == "done" for u in uids[1:])
    msg = app.db.one("SELECT message FROM generation WHERE uid=?", (uids[0],))["message"]
    assert msg == "unexpected error: RuntimeError"  # the class only: no details that could hold an address or a key
    assert all(t.is_alive() for t in app.manager._pool) and app.manager._dispatcher.is_alive()


def test_shutdown_is_clean(app):
    app.build()
    app.manager.stop()
    assert not app.manager._dispatcher.is_alive()
    assert not any(t.is_alive() for t in app.manager._pool)


def test_database_uses_wal_for_the_concurrent_writers(tmp_path):
    db = Database(tmp_path / "w.db")
    assert db.one("PRAGMA journal_mode")["journal_mode"] == "wal"


# ------------------------------------------------------------------------------------------------------------------ provenance and cache
def test_provenance_of_device_and_cloud_drafts_and_a_shared_cache(app, cloud):
    app.build()
    configure(app, cloud)
    uids = add_requirements(app, 2)
    app.manager.enqueue([(uids[0], 1)])
    assert app.manager.wait_idle(30)
    g = payload(app, uids[0])
    assert (g["generated_on"], g["endpoint_host"], g["backend"], g["model"]) == ("device", None, "ollama", "c1-req")
    go(app, "cloud")
    app.manager.enqueue([(uids[1], 1)])
    assert app.manager.wait_idle(30)
    g = payload(app, uids[1])
    assert (g["generated_on"], g["endpoint_host"], g["backend"], g["model"]) == ("cloud", "127.0.0.1", "ollama", "c1-req")
    # the cache is shared by both targets: the device draft is applied on the cloud target without a request, and keeps where it was made
    calls = len(cloud.users)
    app.db.run("DELETE FROM generation WHERE uid=?", (uids[0],))
    assert app.manager.request(uids[0]) == "done"
    assert len(cloud.users) == calls and len(app.device.users) == 1
    g = payload(app, uids[0])
    assert g["generated_on"] == "device" and g["endpoint_host"] is None
    # and the other way round
    go(app, "device")
    app.db.run("DELETE FROM generation WHERE uid=?", (uids[1],))
    assert app.manager.request(uids[1]) == "done"
    assert len(app.device.users) == 1
    g = payload(app, uids[1])
    assert g["generated_on"] == "cloud" and g["endpoint_host"] == "127.0.0.1"


def test_cache_key_has_the_backend_kind_and_model_not_the_target(app):
    from agents.requirement_agent.api.gen_worker import cache_key
    assert cache_key("text", "ollama", "c1-req") == cache_key("text", "ollama", "c1-req")
    assert cache_key("text", "ollama", "c1-req") != cache_key("text", "ollama", "other")
    assert cache_key("text", "ollama", "c1-req") != cache_key("text", "replay", "c1-req")


@pytest.mark.skipif(not MODELS_PRESENT, reason="saved models missing in models/component1/part_a_active")
def test_provenance_in_the_requirement_payload_through_analyze(app, cloud):
    app.build()
    configure(app, cloud)
    go(app, "cloud")
    assert upload(app.client, [("sample_srs.txt", SAMPLE, "text/plain")]).status_code == 201
    assert app.call("post", "/api/projects/1/analyze", params={"policy": "all"}).status_code == 202
    assert app.manager.wait_idle(120)
    g = app.call("get", "/api/requirements/REQ-001").json()["generation"]
    assert g["state"] == "done" and g["generated_on"] == "cloud" and g["endpoint_host"] == "127.0.0.1" and g["backend"] == "ollama" and g["model"] == "c1-req"
    assert len(app.device.users) == 0


# ------------------------------------------------------------------------------------------------------------------ failures
def test_cloud_failures_fail_the_item_pause_after_three_and_never_use_the_device(app, cloud):
    app.build()
    configure(app, cloud, concurrency=1)
    go(app, "cloud")
    cloud.status = 503
    uids = add_requirements(app, 6)
    app.manager.enqueue([(u, 1) for u in uids])
    assert wait_for(lambda: drafts(app)["paused"])
    d = drafts(app)
    assert d["paused_reason"] == "cloud_unreachable" and d["failed"] == 3 and d["queued"] == 3
    assert len(app.device.users) == 0  # no automatic fallback to the device
    for u in uids[:3]:
        m = app.db.one("SELECT message FROM generation WHERE uid=?", (u,))["message"]
        assert m == "AI engine unavailable: Cloud unreachable (HTTP 503)"
    time.sleep(0.6)
    assert len(cloud.users) == 3  # the paused queue takes nothing more
    # an explicit resume tries again (and pauses again after three more failures)
    app.call("post", "/api/projects/1/generation/resume")
    assert wait_for(lambda: drafts(app)["failed"] == 6 and drafts(app)["paused"])
    assert len(app.device.users) == 0
    # the server comes back: the user resumes and retries one item explicitly
    cloud.status = None
    assert app.call("post", "/api/projects/1/generation/resume").status_code == 200
    assert app.call("post", f"/api/requirements/{uids[0]}/generate").json()["generation_state"] == "queued"
    assert wait_for(lambda: states(app)[uids[0]] == "done")
    assert payload(app, uids[0])["generated_on"] == "cloud"


def test_switching_target_ends_an_automatic_pause_and_the_user_chooses_what_runs(app, cloud):
    app.build()
    configure(app, cloud, concurrency=1)
    go(app, "cloud")
    cloud.status = 500
    uids = add_requirements(app, 5)
    app.manager.enqueue([(u, 1) for u in uids])
    assert wait_for(lambda: drafts(app)["paused"])
    assert drafts(app)["paused_reason"] == "cloud_unreachable"
    go(app, "device")  # the user's explicit choice: the remaining two items now run on the device
    assert wait_for(lambda: not drafts(app)["paused"])
    assert app.manager.wait_idle(30)
    st = states(app)
    assert [st[u] for u in uids] == ["failed", "failed", "failed", "done", "done"]
    assert [payload(app, u)["generated_on"] for u in uids[3:]] == ["device", "device"]
    assert drafts(app)["paused_reason"] is None


def test_cloud_timeouts_and_rejections_have_clear_messages(app, cloud, monkeypatch):
    app.build()
    configure(app, cloud, concurrency=1)
    go(app, "cloud")
    uids = add_requirements(app, 3)
    monkeypatch.setenv("LLM_TIMEOUT", "0.3")
    cloud.delay = 1.0
    app.manager.enqueue([(uids[0], 1)])
    assert app.manager.wait_idle(30)
    assert app.db.one("SELECT message FROM generation WHERE uid=?", (uids[0],))["message"] == "AI engine unavailable: Cloud unreachable (timeout)"
    cloud.delay = 0
    cloud.status = 401
    app.manager.enqueue([(uids[1], 1)])
    assert app.manager.wait_idle(30)
    m = app.db.one("SELECT message FROM generation WHERE uid=?", (uids[1],))["message"]
    assert m == "AI engine unavailable: Cloud rejected the request (HTTP 401); check the key and the model"
    cloud.status = None
    cloud.redirect = True  # a redirect to another host is not followed
    before = len(cloud.users)
    app.manager.enqueue([(uids[2], 1)])
    assert app.manager.wait_idle(30)
    assert len(cloud.users) == before + 1  # one request, the redirect target was never contacted
    assert app.db.one("SELECT message FROM generation WHERE uid=?", (uids[2],))["message"] == "AI engine unavailable: Cloud unreachable (HTTP 302)"
    assert len(app.device.users) == 0


def test_invalid_model_output_still_gets_three_attempts_on_the_cloud(app, cloud):
    app.build()
    configure(app, cloud, concurrency=1)
    go(app, "cloud")
    handler = cloud.httpd.RequestHandlerClass
    original = handler.do_POST

    def bad_json_post(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        cloud.users.append(body["messages"][-1]["content"])
        self._send(200, {"choices": [{"message": {"content": "this is not json"}}]})

    handler.do_POST = bad_json_post
    try:
        uids = add_requirements(app, 1)
        app.manager.enqueue([(uids[0], 1)])
        assert app.manager.wait_idle(30)
    finally:
        handler.do_POST = original
    g = payload(app, uids[0])
    assert g["state"] == "manual_review" and g["attempts"] == 3 and len(cloud.users) == 3
    assert drafts(app)["paused"] is False  # invalid output is not a connection failure


# ------------------------------------------------------------------------------------------------------------------ ETA
def test_eta_restarts_when_the_target_changes(app, cloud):
    app.build()
    configure(app, cloud)
    uids = add_requirements(app, 3)
    app.manager.set_paused(True)
    app.manager.enqueue([(u, 1) for u in uids])
    base = time.time() - 60

    def add(target, finished, seconds=10):
        app.db.run("INSERT INTO gen_latency (backend, model, seconds, created_at, target, finished) VALUES ('ollama','c1-req',?,?,?,?)", (seconds, now(), target, finished))

    for k in range(3):
        add("device", base + 10 * (k + 1))
    d = drafts(app)
    assert d["latency_samples"] == 3 and d["eta_seconds"] == 30  # 3 per 30 s, 3 waiting
    go(app, "cloud")
    d = drafts(app)
    assert d["eta_seconds"] is None and d["latency_samples"] == 0  # the estimate starts from nothing after a switch
    for k in range(3):
        add("cloud", time.time() + 10 * (k + 1))
    d = drafts(app)
    assert d["latency_samples"] == 3 and d["eta_seconds"] is not None
    go(app, "device")
    d = drafts(app)
    assert d["eta_seconds"] is None and d["latency_samples"] == 0  # the old device completions are from before this switch


# ------------------------------------------------------------------------------------------------------------------ secrets
def test_the_key_and_the_full_address_never_leave_the_api(app, cloud, caplog, capfd):
    caplog.set_level(logging.DEBUG)
    cloud.key = KEY
    app.build()
    configure(app, cloud, concurrency=2)
    full = cloud.url + "/v1"
    go(app, "cloud")
    uids = add_requirements(app, 3)
    app.manager.enqueue([(u, 1) for u in uids])
    assert app.manager.wait_idle(30)
    cloud.status = 503  # failure messages must be clean too
    app.db.run("DELETE FROM generation")
    app.db.run("DELETE FROM gen_cache")
    app.manager.enqueue([(u, 1) for u in uids])
    assert app.manager.wait_idle(30)
    for path in ("/api/engine", "/api/health", "/api/projects/1/summary", "/api/projects/1/requirements", "/api/projects/1/export?format=json", "/api/projects/1/export?format=csv"):
        app.call("get", path)
    app.call("get", f"/api/requirements/{uids[0]}")
    app.call("put", "/api/engine", json={"cloud_url": "https://other.example.com"})  # refused (409): the error must be clean
    app.call("put", "/api/engine", json={"cloud_url": f"https://user:{KEY}@gpu.example.com"})  # refused (400): must not echo the secret
    app.call("post", "/api/engine/test", json={"target": "cloud"})
    for m in [payload(app, u)["numbers_not_in_source"] for u in uids]:
        assert m == []
    messages = [r["message"] for r in app.db.all("SELECT message FROM generation")]
    blob = "\n".join(app.seen + messages)
    out, err = capfd.readouterr()
    logs = caplog.text + out + err
    for text in (blob, logs):
        assert KEY not in text
        assert full not in text and cloud.url not in text and f":{cloud.port}" not in text
    assert "127.0.0.1" in blob  # the host name is shown, nothing more
    assert app.client.app.state.engine.cloud_key() == KEY  # it is stored, just never returned
    e = app.call("get", "/api/engine").json()
    assert "cloud_api_key" not in json.dumps(e) and "cloud_url" not in json.dumps(e)
    assert f"Bearer {KEY}" in cloud.auth
