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
