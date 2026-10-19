"""Where drafts are generated: "device" (the local Ollama model of this API) or "cloud" (any remote OpenAI-compatible server), switchable at runtime.

The settings live in the `settings` table of the workspace database (git-ignored). The cloud address and key are stored there in plain text, like any
local application setting, and are WRITE-ONLY for the API: no response, log line or error message contains the key or the full address; wherever an address would be
shown only its host name is. The cloud target can only be switched on after the user gave consent and a connection test of the CURRENT address, key and model
succeeded. Nothing here falls back from one target to the other: a failing cloud server never sends work to the device.

    cloud_url          https://host[:port][/path]; "/v1" is appended when missing; plain http only if the environment variable C1_ALLOW_INSECURE_CLOUD=1
    cloud_api_key      optional bearer token, write-only
    cloud_model        model id the remote server must serve (default c1-req)
    cloud_concurrency  items in flight at once on the cloud target, 1 to 8 (default 4); the device target always runs one
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .. import config as agent_config
from ..generation import OllamaBackend
from .errors import ApiError

DEVICE, CLOUD = "device", "cloud"
TARGETS = (DEVICE, CLOUD)
POOL_SIZE = 8  # threads in the worker pool; the active target decides how many may work at once
MAX_CONCURRENCY = 8
DEFAULT_CONCURRENCY = 4
DEFAULT_MODEL = "c1-req"
TEST_TIMEOUT = 10  # seconds for the connection test
INSECURE_ENV = "C1_ALLOW_INSECURE_CLOUD"


def _iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------------------------------------------------------- address handling
def insecure_allowed():
    return os.environ.get(INSECURE_ENV) == "1"


def normalize_url(raw):
    """The OpenAI base URL for a user-typed address, or an ApiError. Messages never repeat the address."""
    raw = (raw or "").strip()
    try:
        parts = urllib.parse.urlsplit(raw)
        host, _ = parts.hostname, parts.port  # reading .port validates it
    except ValueError:
        raise ApiError(400, "invalid_cloud_url", "cloud_url is not a valid address.") from None
    if parts.scheme not in ("https", "http") or not host:
        raise ApiError(400, "invalid_cloud_url", "cloud_url must be an https:// address with a host name.")
    if parts.scheme == "http" and not insecure_allowed():
        raise ApiError(400, "invalid_cloud_url", "cloud_url must use https. (Plain http is only allowed when the service is started with C1_ALLOW_INSECURE_CLOUD=1.)")
    if parts.username is not None or parts.password is not None:
        raise ApiError(400, "invalid_cloud_url", "cloud_url must not contain a user name or password; use the API key field.")
    if parts.query or parts.fragment:
        raise ApiError(400, "invalid_cloud_url", "cloud_url must not contain a query string or a fragment.")
    path = parts.path.rstrip("/")
    if not path.endswith("/v1"):
        path += "/v1"
    return f"{parts.scheme}://{parts.netloc}{path}"


def host_of(url):
    """Host name only (no scheme, port, path or credentials), or None."""
    try:
        return urllib.parse.urlsplit(url or "").hostname
    except ValueError:
        return None


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to the same scheme and host (so a key is never sent to another server)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if (old.scheme, old.hostname, old.port) != (new.scheme, new.hostname, new.port):
            return None  # urllib then raises the 3xx as an HTTPError
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def make_opener():
    return urllib.request.build_opener(_SameHostRedirects())


# ------------------------------------------------------------------------------------------------------------------- connection test
def probe(base, key, model, timeout=TEST_TIMEOUT):
    """GET {base}/models and check that `model` is served. Returns {"ok", "detail", "latency_ms"}; the detail never contains the address or the key."""
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    request = urllib.request.Request(base + "/models", headers=headers, method="GET")
    started = time.monotonic()

    def result(ok, detail):
        return {"ok": ok, "detail": detail, "latency_ms": int(round((time.monotonic() - started) * 1000))}

    try:
        with make_opener().open(request, timeout=timeout) as response:
            payload = json.loads(response.read(2_000_000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        hint = " Check the API key." if exc.code in (401, 403) else ""
        return result(False, f"The server answered HTTP {exc.code}.{hint}")
    except (urllib.error.URLError, OSError) as exc:
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        if isinstance(reason, TimeoutError):
            return result(False, f"The server did not answer within {timeout} seconds.")
        return result(False, "Could not connect to the server.")
    except ValueError:
        return result(False, "The server's answer was not a model list.")
    items = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return result(False, "The server's answer was not a model list.")
    ids = {str(m.get("id")) for m in items if isinstance(m, dict)}
    if model not in ids and f"{model}:latest" not in ids:
        return result(False, f"The server does not serve the model '{model}'.")
    return result(True, f"Connected; model '{model}' is served.")


# ------------------------------------------------------------------------------------------------------------------- stored settings
class Target:
    """What one queue item runs on, resolved when the item is picked: which backend object, which model, and what to record as provenance."""

    def __init__(self, kind, backend_name, model, backend, host=None, error=None):
        self.kind, self.backend_name, self.model, self.backend, self.host, self.error = kind, backend_name, model, backend, host, error


class EngineStore:
    def __init__(self, db, backend_name, model_name, device_backend=None):
        self.db = db
        self.backend_name = backend_name  # the API's C1_GENERATION_BACKEND: ollama | replay | mock
        self.model_name = model_name
        self.device_backend = device_backend

    # -- raw storage
    def _get(self, key, default=None):
        row = self.db.one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def _set(self, key, value):
        self.db.run("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def _del(self, *keys):
        for key in keys:
            self.db.run("DELETE FROM settings WHERE key=?", (key,))

    # -- state
    @property
    def disabled_reason(self):
        if self.backend_name != "ollama":
            return f"Cloud writing needs the on-device model to be set up; this service runs in {self.backend_name} mode."
        return None

    def target(self):
        t = self._get("engine_target", DEVICE)
        return t if t in TARGETS else DEVICE

    def changed_at(self):
        try:
            return float(self._get("engine_changed_at", "0"))
        except ValueError:
            return 0.0

    def cloud_url(self):
        return self._get("cloud_url") or None

    def cloud_key(self):
        return self._get("cloud_api_key") or None

    def cloud_model(self):
        return self._get("cloud_model") or DEFAULT_MODEL

    def cloud_concurrency(self):
        try:
            return min(MAX_CONCURRENCY, max(1, int(self._get("cloud_concurrency", str(DEFAULT_CONCURRENCY)))))
        except ValueError:
            return DEFAULT_CONCURRENCY

    def consent(self):
        return self._get("cloud_consent") == "1"

    def fingerprint(self):
        """Identifies the connection settings a test result belongs to (never exposed)."""
        raw = "\n".join([self.cloud_url() or "", self.cloud_key() or "", self.cloud_model()])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def tested(self):
        """(ok or None when there is no test of the current settings, ISO time of the last test or None)."""
        at = self._get("cloud_tested_at")
        if self._get("cloud_tested_fp") != self.fingerprint():
            return None, at
        return self._get("cloud_tested_ok") == "1", at

    def concurrency(self):
        """How many items may be in flight on the ACTIVE target."""
        return self.cloud_concurrency() if self.target() == CLOUD else 1

    # -- what the API shows
    def public(self, device_reachable):
        reachable, at = self.tested()
        return {
            "target": self.target(),
            "cloud_available": self.disabled_reason is None,
            "cloud_disabled_reason": self.disabled_reason,
            "device": {"backend": self.backend_name, "model": self.model_name, "reachable": bool(device_reachable), "concurrency": 1},
            "cloud": {"configured": bool(self.cloud_url()), "host": host_of(self.cloud_url()), "model": self.cloud_model(),
                      "concurrency": self.cloud_concurrency(), "consent": self.consent(), "consent_at": self._get("cloud_consent_at"),
                      "reachable": reachable, "last_tested_at": at},
        }

    # -- changes
    def update(self, changes):
        """Apply a partial update (a dict of the fields that were sent). Raises ApiError; nothing is applied when it raises."""
        on_cloud = self.target() == CLOUD
        connection_change = any(k in changes for k in ("cloud_url", "cloud_api_key", "cloud_model"))
        if connection_change and on_cloud and changes.get("target") != DEVICE:
            raise ApiError(409, "engine_in_use", "The cloud settings cannot be changed while the cloud target is active. Switch to the device first.")
        staged = {}
        if "cloud_url" in changes:
            staged["cloud_url"] = normalize_url(changes["cloud_url"]) if (changes["cloud_url"] or "").strip() else ""
        if "cloud_api_key" in changes:
            staged["cloud_api_key"] = (changes["cloud_api_key"] or "").strip()
        if "cloud_model" in changes:
            model = (changes["cloud_model"] or "").strip()
            if not model:
                raise ApiError(400, "invalid_parameter", "cloud_model must not be empty.")
            staged["cloud_model"] = model
        if "cloud_concurrency" in changes:
            staged["cloud_concurrency"] = int(changes["cloud_concurrency"])
        target = changes.get("target")
        if target is not None and target not in TARGETS:
            raise ApiError(400, "invalid_parameter", f"target must be one of {list(TARGETS)}.")

        # what the state would be after the update
        url = staged["cloud_url"] if "cloud_url" in staged else self.cloud_url()
        consent = changes["cloud_consent"] if "cloud_consent" in changes else self.consent()
        if target == CLOUD:
            self._check_can_switch(url, consent, would_change_connection=connection_change)

        for key, value in staged.items():
            if value == "" and key in ("cloud_url", "cloud_api_key"):
                self._del(key)
            else:
                self._set(key, value)
        if "cloud_consent" in changes:
            if changes["cloud_consent"]:
                self._set("cloud_consent", "1")
                self._set("cloud_consent_at", _iso())
            else:
                self._del("cloud_consent", "cloud_consent_at")
                if self.target() == CLOUD:  # no consent, no cloud
                    target = DEVICE
        if target is not None and target != self.target():
            self._set("engine_target", target)
            self._set("engine_changed_at", repr(time.time()))
        return {"switched": target if target is not None else None}

    def _check_can_switch(self, url, consent, would_change_connection):
        if self.disabled_reason:
            raise ApiError(409, "cloud_disabled", self.disabled_reason)
        if not url:
            raise ApiError(409, "cloud_not_configured", "Set the cloud address first.")
        if not consent:
            raise ApiError(409, "cloud_consent_required", "Consent is required before requirement text is sent to a cloud server.")
        ok, _ = self.tested()
        if would_change_connection or ok is not True:
            raise ApiError(409, "cloud_not_tested", "Run a successful connection test of the current cloud settings first.")

    def record_test(self, result):
        self._set("cloud_tested_ok", "1" if result["ok"] else "0")
        self._set("cloud_tested_at", _iso())
        self._set("cloud_tested_fp", self.fingerprint())

    # -- resolving a target for one item
    def identity(self):
        """(backend kind, model, generated_on, host) of the ACTIVE target, without building a backend; used for cache keys and provenance."""
        if self.target() == CLOUD:
            return self.backend_name, self.cloud_model(), CLOUD, host_of(self.cloud_url())
        return self.backend_name, self.model_name, DEVICE, None

    def resolve(self, timeout=None):
        """The Target for the item being picked now."""
        if self.target() != CLOUD:
            return Target(DEVICE, self.backend_name, self.model_name, self.device_backend)
        url, host = self.cloud_url(), host_of(self.cloud_url())
        if self.disabled_reason or not url:
            return Target(CLOUD, self.backend_name, self.cloud_model(), None, host, error="Cloud is not configured")
        settings = {"base_url": url, "model": self.cloud_model(), "api_key": self.cloud_key() or "",
                    "timeout": timeout if timeout is not None else agent_config.llm_settings()["timeout"]}
        return Target(CLOUD, self.backend_name, self.cloud_model(), OllamaBackend(settings, opener=make_opener(), redact=True), host)
