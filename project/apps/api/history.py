"""Run history for the web app: every link run and every change (decay) run, newest first.

Read from the run logs in ``data/runs`` (one ``events.jsonl`` per run), so finished runs, the run in
progress and runs that were stopped half-way are all shown the same way. No web framework in here,
so it is testable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from apps.api.sources import RUNS_DIR, read_events


def _short(target_id: str) -> str:
    """``jbehave-core/.../Embedder.java`` -> ``Embedder.java`` (ids without a path stay as they are)."""
    return target_id.replace("\\", "/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]


def _state(finished: bool, newest_unfinished: bool, busy: bool) -> str:
    if finished:
        return "finished"
    return "running" if busy and newest_unfinished else "stopped"


def _run_dirs(runs_dir: Path) -> list[Path]:
    if not runs_dir.exists():
        return []
    return sorted((d for d in runs_dir.iterdir() if (d / "events.jsonl").exists()), reverse=True)


def link_runs(project: Optional[str] = None, busy: bool = False, runs_dir: Path = RUNS_DIR) -> list[dict[str, Any]]:
    """Every link run (C4 linking requirements to code), newest first.

    Args:
        project: Only runs started for this project (runs logged before projects existed have none).
        busy: A pipeline process is running, so the newest unfinished run is the live one.
    """
    rows: list[dict[str, Any]] = []
    live_slot = busy
    for d in _run_dirs(runs_dir):
        if "-link-" not in d.name:
            continue
        events = read_events(d)
        start = next((e for e in events if e["type"] == "run_start"), None)
        if start is None:
            continue
        end = next((e for e in events if e["type"] == "run_end"), None)
        newest_unfinished = end is None and live_slot
        if end is None:
            live_slot = False
        if project and start.get("project") != project:
            continue
        verify = next((e for e in events if e["type"] == "verify_start"), None)
        verdicts = {(e["source_id"], e["target_id"]): e for e in events if e["type"] == "verdict"}
        candidates = []
        for e in events:
            if e["type"] != "shortlist":
                continue
            for t in e["targets"]:
                v = verdicts.get((e["source_id"], t["id"]))
                candidates.append({
                    "requirement": e["source_id"], "target": t["id"], "file": _short(t["id"]), "score": t["score"],
                    "decision": "waiting" if v is None else ("review" if v.get("approval_status") == "pending_review" else "linked" if v["kept"] else "not linked"),
                    "confidence": v["confidence"] if v else None, "reason": v["reasoning"] if v else "",
                    "seconds": v.get("latency") if v else None,
                })
        rows.append({
            "id": d.name, "started": start["ts"], "finished": end["ts"] if end else None,
            "state": _state(end is not None, newest_unfinished, busy),
            "project": start.get("project"), "requirements": list(start.get("sources", [])),
            "top_k": start.get("top_k"), "total": verify["total"] if verify else len(candidates),
            "done": len(verdicts), "linked": sum(1 for c in candidates if c["decision"] == "linked"),
            "pending": sum(c["decision"] == "review" for c in candidates),
            "candidates": candidates,
        })
    return rows


def change_runs(project: Optional[str] = None, busy: bool = False, runs_dir: Path = RUNS_DIR) -> list[dict[str, Any]]:
    """Every decay pass (a commit reported to C4, or a monitor pass), newest first."""
    rows: list[dict[str, Any]] = []
    live_slot = busy
    for d in _run_dirs(runs_dir):
        if not d.name.endswith("-monitor"):
            continue
        events = read_events(d)
        start = next((e for e in events if e["type"] == "run_start"), None)
        if start is None:
            continue
        end = next((e for e in events if e["type"] == "run_end"), None)
        newest_unfinished = end is None and live_slot
        if end is None:
            live_slot = False
        if project and start.get("project") != project:
            continue
        rechecks = [
            {"requirement": e["source_id"], "target": e["target_id"], "file": _short(e["target_id"]),
             "before": e["previous_confidence"], "after": e["new_confidence"], "broken": e["decayed"], "restored": e.get("restored", False), "status": e.get("approval_status", "decayed" if e["decayed"] else "verified"),
             "reason": e["reason"]}
            for e in events if e["type"] == "recheck"
        ]
        messages = [{"delivered": e["delivered"], "event": e["event"]} for e in events if e["type"] == "decay_event"]
        rows.append({
            "id": d.name, "started": start["ts"], "finished": end["ts"] if end else None,
            "state": _state(end is not None, newest_unfinished, busy),
            "project": start.get("project"), "trigger": start.get("trigger", "monitor"),
            "files": [_short(c) for c in start.get("changed", [])],
            "rechecks": rechecks, "broken": sum(1 for r in rechecks if r["broken"]), "messages": messages,
        })
    return rows


def notifications(limit: int = 40, runs_dir: Path = RUNS_DIR) -> list[dict[str, Any]]:
    """Return recent decay notifications from durable run logs.

    Redis is live transport; the run log is the durable fallback so a dashboard opened
    after a decay still shows the event.
    """
    items: list[dict[str, Any]] = []
    for directory in _run_dirs(runs_dir):
        for event in read_events(directory):
            if event["type"] != "decay_event":
                continue
            payload = dict(event.get("event") or {})
            payload.setdefault("event", "trace_decayed")
            payload["project"] = event.get("project")
            payload["delivered"] = bool(event.get("delivered"))
            payload["timestamp"] = payload.get("timestamp") or event.get("ts")
            items.append(payload)
    return sorted(items, key=lambda item: item.get("timestamp") or "", reverse=True)[:max(1, min(limit, 100))]


def elapsed(since_iso: str, until_iso: Optional[str] = None) -> str:
    """Human duration between two ISO timestamps (``until`` defaults to now): ``45 s``, ``3 min 10 s``."""
    start = datetime.fromisoformat(since_iso)
    end = datetime.fromisoformat(until_iso) if until_iso else datetime.now(timezone.utc)
    seconds = max(0, int((end - start).total_seconds()))
    return f"{seconds} s" if seconds < 60 else f"{seconds // 60} min {seconds % 60} s"


def local_time(iso: str) -> str:
    """``2026-10-12T17:56:31+00:00`` -> ``Oct 12, 23:26`` in the machine's time zone."""
    return datetime.fromisoformat(iso).astimezone().strftime("%b %d, %H:%M")
