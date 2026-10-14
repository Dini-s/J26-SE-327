"""The web server: serves the page, answers JSON, and refuses writes that do not come from its own page."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from apps.api import server


@pytest.fixture(scope="module")
def base():
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _post(url, headers):
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_page_and_unknown_route(base):
    with urllib.request.urlopen(base + "/", timeout=5) as r:
        assert r.status == 200 and b"C4 Traceability" in r.read()
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(base + "/api/nope", timeout=5)
    assert exc.value.code == 404


def test_activity_is_json(base):
    with urllib.request.urlopen(base + "/api/activity", timeout=10) as r:
        assert json.loads(r.read())["state"] in ("idle", "running", "external")


def test_writes_need_the_page_header_and_same_origin(base):
    assert _post(base + "/api/reset", {}) == 403  # no header: e.g. a form on another site
    host = base.split("://", 1)[1]
    assert _post(base + "/api/reset", {"X-Requested-With": "c4-web", "Origin": "http://evil.example"}) == 403
    # from the page itself the request is accepted and then validated (no project chosen -> 400)
    assert _post(base + "/api/reset", {"X-Requested-With": "c4-web", "Origin": f"http://{host}"}) == 400


# ---- buttons for requirements that C1 already wrote: create trace links, scan for drift
def _call(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Requested-With": "c4-web"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


@pytest.fixture
def fake_graph(monkeypatch):
    state = {"requirements": 26, "unlinked": 26, "ids": [], "codeFiles": 37, "links": 0}
    started = []
    monkeypatch.setattr(server, "_need_neo4j", lambda: None)
    monkeypatch.setattr(server.sources, "neo4j_unlinked", lambda project: dict(state))
    monkeypatch.setattr(server.runner, "status", lambda: {"state": "idle"})
    monkeypatch.setattr(server.runner, "start", lambda params: started.append(params) or {"pid": 1})
    return state, started


def test_create_trace_links_for_unlinked_requirements(base, fake_graph):
    state, started = fake_graph
    status, body = _call(base, "/api/link-existing", {"project": "spring-petclinic", "top_k": 3})
    assert status == 200 and body["requirements"] == 26 and body["calls"] == 78 and body["minutes"] == 68
    assert started == [{"kind": "link", "project": "spring-petclinic", "top_k": 3, "retrieval": "hybrid", "limit_sources": 0, "only_unlinked": True}]


@pytest.mark.parametrize("change,message", [({"requirements": 0, "unlinked": 0}, "no requirements"), ({"codeFiles": 0}, "no code files"),
                                           ({"unlinked": 0}, "already has a trace link")])
def test_create_trace_links_refuses_when_there_is_nothing_to_do(base, fake_graph, change, message):
    state, started = fake_graph
    state.update(change)
    status, body = _call(base, "/api/link-existing", {"project": "spring-petclinic"})
    assert status == 400 and message in body["detail"] and started == []


def test_create_trace_links_needs_a_project_and_an_idle_ai(base, fake_graph, monkeypatch):
    assert _call(base, "/api/link-existing", {})[0] == 400
    monkeypatch.setattr(server.runner, "status", lambda: {"state": "running"})
    assert _call(base, "/api/link-existing", {"project": "spring-petclinic"})[0] == 409


def test_scan_for_drift_needs_links_and_starts_a_monitor_run(base, fake_graph):
    state, started = fake_graph
    status, body = _call(base, "/api/scan", {"project": "spring-petclinic"})
    assert status == 400 and "no trace links" in body["detail"] and started == []
    state["links"] = 12
    status, body = _call(base, "/api/scan", {"project": "spring-petclinic", "force": True})
    assert status == 200 and body["links"] == 12
    assert started == [{"kind": "monitor", "project": "spring-petclinic", "force": True}]
    assert _call(base, "/api/scan", {})[0] == 400
