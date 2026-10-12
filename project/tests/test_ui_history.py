"""Run history shown by the web app."""

import json

from apps.api import history


def _run(root, name, events):
    d = root / name
    d.mkdir()
    (d / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")


def test_link_runs_newest_first_with_decisions_and_live_state(tmp_path):
    _run(tmp_path, "20261012-100000-link-hybrid-top3", [
        {"type": "run_start", "ts": "2026-10-12T10:00:00+00:00", "project": "iTrust", "sources": ["NEW-001"], "top_k": 2},
        {"type": "shortlist", "source_id": "NEW-001", "targets": [{"id": "a/LoginFailureAction.java", "score": 1.0}, {"id": "AuthDAO", "score": 0.5}]},
        {"type": "verify_start", "total": 2},
        {"type": "verdict", "source_id": "NEW-001", "target_id": "a/LoginFailureAction.java", "kept": True, "confidence": 0.8, "reasoning": "r", "latency": 30.0},
        {"type": "verdict", "source_id": "NEW-001", "target_id": "AuthDAO", "kept": False, "confidence": 0.6, "reasoning": "x", "latency": 20.0},
        {"type": "run_end", "ts": "2026-10-12T10:01:00+00:00", "links": 1},
    ])
    _run(tmp_path, "20261012-110000-link-hybrid-top3", [
        {"type": "run_start", "ts": "2026-10-12T11:00:00+00:00", "project": "iTrust", "sources": ["NEW-002"], "top_k": 1},
        {"type": "shortlist", "source_id": "NEW-002", "targets": [{"id": "X", "score": 1.0}]},
    ])
    _run(tmp_path, "20261012-120000-link-hybrid-top3", [
        {"type": "run_start", "ts": "2026-10-12T12:00:00+00:00", "project": "eTour", "sources": ["NEW-003"], "top_k": 1},
    ])
    rows = history.link_runs("iTrust", busy=False, runs_dir=tmp_path)
    assert [r["requirements"] for r in rows] == [["NEW-002"], ["NEW-001"]]
    assert rows[0]["state"] == "stopped" and rows[0]["candidates"][0]["decision"] == "waiting"
    done = rows[1]
    assert done["state"] == "finished" and done["linked"] == 1 and done["done"] == 2
    assert [(c["file"], c["decision"]) for c in done["candidates"]] == [("LoginFailureAction.java", "linked"), ("AuthDAO", "not linked")]
    # while a process runs, only the newest unfinished run (any project) is the live one
    assert history.link_runs("eTour", busy=True, runs_dir=tmp_path)[0]["state"] == "running"
    assert history.link_runs("iTrust", busy=True, runs_dir=tmp_path)[0]["state"] == "stopped"


def test_change_runs_count_broken_links_and_messages(tmp_path):
    _run(tmp_path, "20261012-100000-change-monitor", [
        {"type": "run_start", "ts": "2026-10-12T10:00:00+00:00", "project": "iTrust", "trigger": "code_changed", "changed": ["LoginFailureAction"]},
        {"type": "decay_event", "delivered": True, "event": {"event": "trace_decayed", "requirementId": "NEW-006"}},
        {"type": "recheck", "source_id": "NEW-006", "target_id": "LoginFailureAction", "previous_confidence": 0.9, "new_confidence": 0.0, "decayed": True, "reason": "empty"},
        {"type": "recheck", "source_id": "NEW-007", "target_id": "LoginFailureAction", "previous_confidence": 0.8, "new_confidence": 0.8, "decayed": False, "reason": "ok"},
        {"type": "run_end", "ts": "2026-10-12T10:00:40+00:00"},
    ])
    (row,) = history.change_runs("iTrust", runs_dir=tmp_path)
    assert row["files"] == ["LoginFailureAction"] and row["broken"] == 1 and len(row["rechecks"]) == 2
    assert row["messages"][0]["delivered"] and row["state"] == "finished"
    assert history.elapsed(row["started"], row["finished"]) == "40 s"
