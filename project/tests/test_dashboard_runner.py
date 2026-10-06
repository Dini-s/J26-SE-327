"""Run-control logic: validation, command building and the one-run-at-a-time guard."""

import sys
import time

import pytest

from apps.api import runner


def test_validate_applies_defaults_and_bounds():
    p = runner.validate({"dataset": "itrust"})
    assert p == {"dataset": "itrust", "retrieval": "hybrid", "top_k": 5, "limit_sources": 10}
    assert runner.validate({"dataset": "itrust", "limit_sources": ""})["limit_sources"] is None


@pytest.mark.parametrize(
    "bad",
    [{"dataset": "nope"}, {"dataset": "itrust", "retrieval": "x"}, {"dataset": "itrust", "top_k": 0},
     {"dataset": "itrust", "top_k": 999}, {"dataset": "itrust", "limit_sources": 9999},
     {"dataset": "itrust", "top_k": "abc"}],
)
def test_validate_rejects_bad_input(bad):
    with pytest.raises(runner.RunnerError):
        runner.validate(bad)


def test_estimate_counts_calls():
    e = runner.estimate(runner.validate({"dataset": "itrust", "limit_sources": 10, "top_k": 5}))
    assert (e["requirements"], e["calls"]) == (10, 50) and e["minutes"] == round(50 * runner.SECONDS_PER_CALL / 60)
    assert runner.estimate(runner.validate({"dataset": "itrust", "limit_sources": None, "top_k": 2}))["requirements"] == 131


def test_build_command_is_a_list_with_no_shell():
    cmd = runner.build_command(runner.validate({"dataset": "itrust", "top_k": 3, "limit_sources": 7}))
    assert cmd[0] == sys.executable and isinstance(cmd, list)
    assert cmd[cmd.index("--top-k") + 1] == "3" and cmd[cmd.index("--limit-sources") + 1] == "7"


def test_start_stop_lifecycle_and_single_run_guard(monkeypatch):
    monkeypatch.setattr(runner, "_external_pids", lambda: [])
    runner._state.update(proc=None)
    sleeper = [sys.executable, "-c", "import time; time.sleep(30)"]
    runner.start({"dataset": "itrust"}, command=sleeper)
    try:
        assert runner.status()["state"] == "running"
        with pytest.raises(runner.RunnerError, match="already"):
            runner.start({"dataset": "itrust"}, command=sleeper)
        runner.stop()
        for _ in range(50):
            if runner.status()["state"] == "idle":
                break
            time.sleep(0.1)
        assert runner.status()["state"] == "idle"
    finally:
        runner._state.update(proc=None)


def test_external_run_blocks_start_and_cannot_be_stopped(monkeypatch):
    monkeypatch.setattr(runner, "_external_pids", lambda: [4242])
    runner._state.update(proc=None)
    assert runner.status()["state"] == "external"
    with pytest.raises(runner.RunnerError, match="already"):
        runner.start({"dataset": "itrust"}, command=[sys.executable, "-c", "pass"])
    with pytest.raises(runner.RunnerError):
        runner.stop()
