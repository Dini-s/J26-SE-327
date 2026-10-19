"""Keeps the graph database in step with the workspace, in the background.

A change (analysis finished, decision set or removed, draft written, sprint/phase/assignment change, source deleted) marks the project as changed.
The worker then syncs it once things are quiet:

    debounce    10 s after the last change
    rate        at most one sync per 30 s per project
    analysing   a sync may run while documents are being analysed: only analysed documents are sent, the others follow when they are finished
    unset       when the graph database is not configured the project is simply `not_configured`; nothing is tried and no error is raised
    failure     the same sync is tried again after 30 s, 60 s, 120 s, 240 s, then every 300 s; after 5 failures in a row the state is `unreachable`
    startup     a project that is out of date is synced when the service starts

It never blocks a request: the work happens on its own thread, and the publish itself (idempotent, single-flight) is the one the "sync now" button calls.
C1_AUTO_SYNC=0 switches the worker off. The clock is injectable so the timing can be tested without waiting.
"""
import logging
import threading
import time
from datetime import datetime, timezone

from .db import loads
from .errors import ApiError

log = logging.getLogger("c1.autosync")

DEBOUNCE_SECONDS = 10
MIN_INTERVAL_SECONDS = 30
BACKOFF_SECONDS = (30, 60, 120, 240, 300)  # the last value repeats
UNREACHABLE_AFTER_FAILURES = 5
TICK_SECONDS = 1.0
ENV_SWITCH = "C1_AUTO_SYNC"

STATES = ("synced", "syncing", "pending", "retrying", "not_configured", "unreachable")


def enabled_from_env(environ):
    return str(environ.get(ENV_SWITCH, "1")).strip().lower() not in ("0", "false", "no", "off")


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds") if ts else None


class AutoSync:
    def __init__(self, db, store, clock=time.time, enabled=True):
        self.db, self.store, self.clock, self.enabled = db, store, clock, enabled
        self._lock = threading.Lock()
        self._p = {}  # project id -> in-memory state
        self._stop = threading.Event()
        self._thread = None

    # ------------------------------------------------------------------------------------------------ lifecycle
    def start(self):
        if self.enabled and self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="c1-autosync", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _loop(self):
        try:
            self.check_startup()
        except Exception:  # noqa: BLE001
            log.exception("auto-sync startup check failed")
        while not self._stop.wait(TICK_SECONDS):
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - the worker never dies
                log.exception("auto-sync tick failed")

    # ------------------------------------------------------------------------------------------------ changes
    def _state(self, pid):
        return self._p.setdefault(pid, {"dirty_at": None, "last_attempt": None, "next_attempt": None, "failures": 0, "state": None, "error": None,
                                        "last_synced_at": None, "counts": None, "syncing": False})

    def notify(self, pid, at=None):
        """The project changed. Cheap and safe to call from any request or worker thread."""
        if not self.enabled or pid is None:
            return
        with self._lock:
            st = self._state(pid)
            st["dirty_at"] = self.clock() if at is None else at
            if not st["syncing"] and st["state"] in (None, "synced", "not_configured"):
                st["state"] = "pending"

    def notify_uid(self, uid):
        row = self.db.one("SELECT project_id FROM requirements WHERE uid=?", (uid,))
        if row:
            self.notify(row["project_id"])

    def check_startup(self):
        """Sync every project that is out of date (changed while the service was off)."""
        if not self.enabled or not self.store.config().configured:
            return
        for p in self.db.all("SELECT id FROM projects WHERE archived=0"):
            try:
                if self.store.publish_info(p["id"])["out_of_date"]:
                    self.notify(p["id"], at=self.clock() - DEBOUNCE_SECONDS)
            except Exception:  # noqa: BLE001
                log.exception("auto-sync could not check project %s", p["id"])

    def record_manual(self, pid, result):
        """The "sync now" button published the project: the state follows it."""
        with self._lock:
            st = self._state(pid)
            st.update(state="synced", error=None, failures=0, next_attempt=None, last_synced_at=result["published_at"], counts=result["counts"])
            if not st["syncing"]:
                st["dirty_at"] = None

    # ------------------------------------------------------------------------------------------------ the worker step
    def tick(self):
        for pid in list(self._p):
            self.sync_if_due(pid)

    def due_at(self, st):
        """When the next attempt may start (None if nothing is waiting)."""
        if not st["dirty_at"]:
            return None
        return max(st["dirty_at"] + DEBOUNCE_SECONDS, (st["last_attempt"] + MIN_INTERVAL_SECONDS) if st["last_attempt"] else 0, st["next_attempt"] or 0)

    def sync_if_due(self, pid):
        now = self.clock()
        with self._lock:
            st = self._state(pid)
            due = self.due_at(st)
            if st["syncing"] or due is None or now < due:
                return False
        if not self.store.config().configured:
            with self._lock:
                st.update(state="not_configured", dirty_at=None, error=None)
            return False
        with self._lock:
            st.update(syncing=True, state="syncing", last_attempt=now)
            started_for = st["dirty_at"]
        try:
            info = self.store.publish_info(pid)
            if info["out_of_date"]:
                result = self.store.publish(pid)
                synced_at, counts = result["published_at"], result["counts"]
            else:
                synced_at, counts = info["last_published_at"], None
        except ApiError as exc:
            self._failed(st, exc.code, now)
            return False
        except Exception:  # noqa: BLE001
            log.exception("auto-sync failed")
            self._failed(st, "neo4j_publish_failed", now)
            return False
        with self._lock:
            st["syncing"] = False
            st.update(failures=0, next_attempt=None, error=None, last_synced_at=synced_at)
            if counts is not None:
                st["counts"] = counts
            if st["dirty_at"] == started_for:
                st.update(dirty_at=None, state="synced")
            else:
                st["state"] = "pending"  # something changed while it was syncing
        return True

    def _failed(self, st, code, now):
        with self._lock:
            st["syncing"] = False
            if code == "neo4j_unconfigured":
                st.update(state="not_configured", dirty_at=None, error=None)
            elif code == "publish_in_progress":  # the "sync now" button is running: look again shortly
                st.update(state="pending", next_attempt=now + DEBOUNCE_SECONDS)
            else:
                st["failures"] += 1
                delay = BACKOFF_SECONDS[min(st["failures"] - 1, len(BACKOFF_SECONDS) - 1)]
                st.update(state="unreachable" if st["failures"] >= UNREACHABLE_AFTER_FAILURES else "retrying", next_attempt=now + delay, error=code)

    # ------------------------------------------------------------------------------------------------ status
    def status(self, pid):
        """{"state", "enabled", "last_synced_at", "counts", "next_attempt_at", "error"}; reads the workspace only, never the graph database."""
        with self._lock:
            st = dict(self._state(pid))
        configured = self.store.config().configured
        last = self.db.one("SELECT published_at, counts FROM publish_log WHERE project_id=? ORDER BY id DESC LIMIT 1", (pid,))
        state, error, next_at = st["state"], st["error"], None
        if not configured:
            state, error = "not_configured", None
        elif state is None or state == "not_configured":  # nothing known in memory yet (just started, or just set up): compare the workspace with the last publish
            try:
                state = "pending" if self.store.publish_info(pid)["out_of_date"] else "synced"
            except Exception:  # noqa: BLE001
                state = "pending"
        if state in ("pending", "retrying", "unreachable"):
            next_at = self.due_at(st)
            if next_at is None and state == "pending" and self.enabled and configured:
                next_at = self.clock() + DEBOUNCE_SECONDS if not st["dirty_at"] else None
        return {"state": state, "enabled": self.enabled, "last_synced_at": st["last_synced_at"] or (last["published_at"] if last else None),
                "counts": st["counts"] or (loads(last["counts"], None) if last else None), "next_attempt_at": _iso(next_at) if self.enabled else None, "error": error}
