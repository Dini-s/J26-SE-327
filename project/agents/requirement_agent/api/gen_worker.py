"""Part B jobs for the API: ONE worker thread takes requirements from a priority queue and calls the existing generation module.

Per-requirement state: not_requested | queued | running | done | needs_clarification | failed | manual_review.
    done / needs_clarification   a valid reply (cached by sha256(requirement text + backend + model name))
    manual_review                the model replied but all 3 attempts were invalid (the last raw reply is kept; not cached)
    failed                       no reply at all: Ollama unreachable, or the text is not in the replay file (nothing is made up)
A single requirement can be re-run at once with priority over the queue (`run_now`), which skips the cache.

Policy (chosen per analysis run, see priority.py): smart = queue P1 only, all = queue everything ordered P1, P2, P3, manual = queue nothing. Requirements
that are not queued stay "not_requested" (shown as "not generated yet") until the user asks. A cached reply is applied at once, whatever the policy.
The queue lives in memory but every queued/running requirement is also a row in `generation` with its priority, so a restart re-queues them
(`resume_pending`). Pause stops the worker from taking NEW items (the one in flight finishes); the flag is saved in sqlite. Each live reply's duration is
stored in `gen_latency` and is the only input to the ETA (mean of the last 10; no ETA before 3 samples).
"""
import hashlib
import json
import queue
import threading
import time

from .. import config as agent_config
from .. import generation as gen
from ..generation import BackendError, MockBackend, OllamaBackend, ReplayBackend, ReplayMiss
from . import priority, settings
from .db import dumps, loads, now

STATES = ("not_requested", "queued", "running", "done", "needs_clarification", "failed", "manual_review")
NOT_IN_REPLAY = "not in replay file"
ENGINE_UNAVAILABLE = "AI engine unavailable"  # the UI shows its "engine unavailable" state when a failed draft's message starts with this
MAX_FAST_FAILS = 3
ETA_WINDOW = 10
ETA_MIN_SAMPLES = 3
ORIGINAL, CLARIFIED = "original", "clarified"


def _norm(text):
    return " ".join(str(text or "").split())


def mock_reply(system, user):
    """Deterministic, clearly artificial reply for tests and demos (C1_GENERATION_BACKEND=mock). Not model output."""
    text = user[len(gen.USER_PREFIX):] if user.startswith(gen.USER_PREFIX) else user
    short = text.rstrip(".").strip()
    return json.dumps({
        "status": "ok",
        "user_story": f"As a user, I want {short[:1].lower() + short[1:]}, so that the requirement is met.",
        "technical_task": f"Implement and verify: {short}.",
        "acceptance_criteria": [f"Given the system is running, when the requirement is exercised, then the stated behaviour is met.",
                                f"Given invalid input, when the requirement is exercised, then the system reports an error."],
        "rationale": "MOCK output for testing; not produced by a language model.",
    })


def make_backend(name, replay_file=None):
    if name == "replay":
        return ReplayBackend(settings.replay_file(replay_file)), "replay"
    if name == "ollama":
        s = agent_config.llm_settings()
        return OllamaBackend(s), s["model"] or "(LLM_MODEL not set)"
    if name == "mock":
        return MockBackend(mock_reply), "mock"
    raise ValueError(f"unknown backend {name!r}")


def cache_key(text, backend_name, model_name):
    return hashlib.sha256("\n".join([text, backend_name, model_name]).encode("utf-8")).hexdigest()


class GenerationManager:
    def __init__(self, db, backend, backend_name, model_name, init_error=None):
        self.db, self.backend, self.backend_name, self.model_name = db, backend, backend_name, model_name
        self.init_error = init_error  # for example "replay file not found"; every job then fails with this message
        self.queue = queue.PriorityQueue()
        self._seq = 0
        self._ticket = {}
        self._lock = threading.Lock()
        self._fails = 0
        self._stop = threading.Event()
        self._paused = threading.Event()
        if (self.db.one("SELECT value FROM settings WHERE key='gen_paused'") or {}).get("value") == "1":
            self._paused.set()
        self._thread = threading.Thread(target=self._loop, name="c1-generation-worker", daemon=True)

    # ------------------------------------------------------------------------------------------------ lifecycle
    def start(self):
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self):
        self._stop.set()
        self.queue.put((99, 0, "", 0))  # wake the worker
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def wait_idle(self, timeout=60.0):
        end = time.time() + timeout
        while self.queue.unfinished_tasks and time.time() < end:
            time.sleep(0.02)
        return self.queue.unfinished_tasks == 0

    # ------------------------------------------------------------------------------------------------ state
    def _set(self, uid, state, message="", result=None, attempts=0, manual_review=False, key=None):
        self.db.run(
            "INSERT INTO generation (uid, state, message, result, attempts, manual_review, cache_key, updated_at) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(uid) DO UPDATE SET state=excluded.state, message=excluded.message, result=excluded.result, attempts=excluded.attempts, "
            "manual_review=excluded.manual_review, cache_key=excluded.cache_key, updated_at=excluded.updated_at",
            (uid, state, message, dumps(result) if result is not None else None, attempts, int(manual_review), key, now()))

    def enqueue(self, items):
        """items = [(uid, priority class 1-3)]; lower classes are taken first, then first come first served."""
        for uid, cls in items:
            with self._lock:
                self._seq += 1
                ticket = self._seq
                self._ticket[uid] = ticket
            self._set(uid, "queued")
            self.db.run("UPDATE generation SET priority=? WHERE uid=?", (cls, uid))
            self.queue.put((cls, ticket, uid, ticket))

    def source_text(self, uid):
        """(text to generate from, "original" | "clarified"). A decision "edited" with a really different text is the user's clarified text."""
        row = self.db.one("SELECT r.text, d.decision, d.edited_text FROM requirements r LEFT JOIN decisions d ON d.uid=r.uid WHERE r.uid=?", (uid,))
        if not row:
            return None, ORIGINAL
        edited = (row["edited_text"] or "").strip()
        if row["decision"] == "edited" and edited and _norm(edited) != _norm(row["text"]):
            return edited, CLARIFIED
        return row["text"], ORIGINAL

    def _apply_cache(self, uid):
        """A reply that is already cached is shown at once (it never runs again). Returns True when applied."""
        text, origin = self.source_text(uid)
        if text is None:
            return False
        key = cache_key(text, self.backend_name, self.model_name)
        hit = self.db.one("SELECT result FROM gen_cache WHERE key=?", (key,))
        if not hit:
            return False
        res = {**loads(hit["result"]), "backend": self.backend_name, "model": self.model_name, "source_text": text, "generated_from": origin}
        self._set(uid, "done" if res["status"] == "ok" else "needs_clarification", "from cache", res, res.get("attempts", 1), False, key)
        return True

    def plan(self, pid, policy):
        """After Part A: show cached replies, then queue what the policy selects (P1, P2, P3 order). Returns the number queued."""
        items = []
        ranked = sorted(priority.classes(self.db, pid).items(), key=lambda kv: kv[1])  # stable: document order inside a class
        for uid, cls in ranked:
            existing = self.db.one("SELECT state FROM generation WHERE uid=?", (uid,))
            if existing and existing["state"] in ("queued", "running"):
                continue
            if self._apply_cache(uid):
                continue
            if priority.selected(policy, cls):
                items.append((uid, cls))
        self.enqueue(items)
        return len(items)

    def enqueue_remaining(self, pid):
        """Queue every requirement that has no draft yet ("not generated yet"), best class first. Returns how many."""
        items = []
        ranked = sorted(priority.classes(self.db, pid).items(), key=lambda kv: kv[1])
        for uid, cls in ranked:
            if self.db.one("SELECT 1 x FROM generation WHERE uid=?", (uid,)):
                continue
            if self._apply_cache(uid):
                continue
            items.append((uid, cls))
        self.enqueue(items)
        return len(items)

    def resume_pending(self):
        """After a restart: everything that was queued or running goes back in the queue with its saved priority. Returns how many."""
        self.db.run("DELETE FROM generation WHERE uid NOT IN (SELECT uid FROM requirements)")
        rows = self.db.all("SELECT uid, priority FROM generation WHERE state IN ('queued','running') ORDER BY priority, updated_at, uid")
        self.enqueue([(r["uid"], r["priority"]) for r in rows])
        return len(rows)

    # ------------------------------------------------------------------------------------------------ pause / timing
    def eta(self, remaining):
        """(estimated seconds for `remaining` drafts or None, samples). Hidden (None) until 3 real latencies exist; nothing is made up."""
        mean, n = self.latency()
        if mean is None or n < ETA_MIN_SAMPLES or remaining <= 0:
            return None, n
        return int(round(mean * remaining)), n

    @property
    def paused(self):
        return self._paused.is_set()

    def set_paused(self, value):
        (self._paused.set if value else self._paused.clear)()
        self.db.run("INSERT INTO settings (key, value) VALUES ('gen_paused', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", ("1" if value else "0",))

    def latency(self):
        """(mean seconds of the last 10 live replies of this backend+model or None, number of samples used). No fake numbers: no samples -> None."""
        rows = self.db.all("SELECT seconds FROM gen_latency WHERE backend=? AND model=? ORDER BY id DESC LIMIT ?", (self.backend_name, self.model_name, ETA_WINDOW))
        if not rows:
            return None, 0
        return sum(r["seconds"] for r in rows) / len(rows), len(rows)

    def run_now(self, uid):
        """Regenerate one requirement before everything else in the queue, ignoring the cache."""
        with self._lock:
            self._seq += 1
            ticket = self._seq
            self._ticket[uid] = -ticket  # negative ticket = force
        self._set(uid, "queued")
        self.db.run("UPDATE generation SET priority=0 WHERE uid=?", (uid,))
        self.queue.put((0, ticket, uid, -ticket))

    def request(self, uid):
        """The "Generate draft" / "Regenerate" button. A requirement with no draft yet takes a cached reply if there is one; otherwise (and for any
        existing draft) it is generated now, before everything else in the queue. Returns the resulting state."""
        if not self.db.one("SELECT 1 x FROM generation WHERE uid=?", (uid,)) and self._apply_cache(uid):
            return self.db.one("SELECT state FROM generation WHERE uid=?", (uid,))["state"]
        self.run_now(uid)
        return "queued"

    # ------------------------------------------------------------------------------------------------ worker
    def _loop(self):
        while not self._stop.is_set():
            if self._paused.is_set():  # take no NEW item while paused; an item already in flight has finished by now
                self._stop.wait(0.2)
                continue
            try:
                item = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            _, _, uid, ticket = item
            if uid and self._paused.is_set():  # paused while this call was waiting: put the item back untouched
                self.queue.put(item)
                self.queue.task_done()
                continue
            try:
                if uid and self._ticket.get(uid) == ticket:
                    self._process(uid, force=ticket < 0)
            except Exception as exc:  # the worker must never die
                try:
                    self._set(uid, "failed", f"unexpected error: {exc.__class__.__name__}: {exc}")
                except Exception:
                    pass
            finally:
                self.queue.task_done()

    def _process(self, uid, force=False):
        text, origin = self.source_text(uid)  # the user's clarified text when there is one, else the original
        if text is None:
            return
        key = cache_key(text, self.backend_name, self.model_name)
        if not force and self._apply_cache(uid):
            return
        if self.init_error:
            self._set(uid, "failed", self.init_error, key=key)
            return
        if self._fails >= MAX_FAST_FAILS and not force and self.backend_name == "ollama":
            self._set(uid, "failed", f"{ENGINE_UNAVAILABLE}: skipped after repeated failures; start the model server and press Retry", key=key)
            return
        self._set(uid, "running", key=key)
        started = time.monotonic()
        try:
            result = gen.generate_structured(self.backend, text)
        except ReplayMiss:
            self._set(uid, "failed", NOT_IN_REPLAY, key=key)
            return
        except BackendError as exc:
            self._fails += 1
            self._set(uid, "failed", f"{ENGINE_UNAVAILABLE}: {exc}", key=key)
            return
        self._fails = 0
        self.db.run("INSERT INTO gen_latency (backend, model, seconds, created_at) VALUES (?,?,?,?)", (self.backend_name, self.model_name, time.monotonic() - started, now()))
        res = {"status": result.status, "user_story": result.user_story, "technical_task": result.technical_task,
               "acceptance_criteria": result.acceptance_criteria, "rationale": result.rationale,
               "clarification_questions": result.clarification_questions, "attempts": result.attempts,
               "manual_review": result.manual_review, "backend": self.backend_name, "model": self.model_name, "source_text": text, "generated_from": origin,
               "raw_output": result.raw_output if result.manual_review else "",
               "problems": result.problems}
        if result.manual_review:
            self._set(uid, "manual_review", "; ".join(result.problems), res, result.attempts, True, key)
            return
        self.db.run("INSERT OR REPLACE INTO gen_cache (key, result, created_at) VALUES (?,?,?)", (key, dumps(res), now()))
        self._set(uid, "done" if result.status == "ok" else "needs_clarification", "", res, result.attempts, False, key)

    # ------------------------------------------------------------------------------------------------ health
    def reachable(self):
        """Cheap check for /api/health. Never raises."""
        try:
            if self.init_error:
                return False
            if self.backend_name == "ollama":
                import urllib.request
                s = agent_config.llm_settings()
                with urllib.request.urlopen(s["base_url"] + "/models", timeout=2) as response:
                    listed = [m.get("id", "") for m in json.loads(response.read().decode("utf-8")).get("data", [])]
                wanted = s["model"]
                return bool(wanted) and (wanted in listed or f"{wanted}:latest" in listed)  # the server answers AND serves the configured model
            return True
        except Exception:
            return False
