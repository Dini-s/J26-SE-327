"""Run-control logic: validation, command building and the one-run-at-a-time guard."""

import sys
import time

import pytest

from apps.api import runner


def test_validate_applies_defaults_and_bounds():
    p = runner.validate({"dataset": "itrust"})
    assert p == {"kind": "evaluate", "dataset": "itrust", "retrieval": "hybrid", "top_k": 5, "limit_sources": 10, "requirement_ids": []}
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


def test_link_and_monitor_kinds_build_cli_commands():
    link = runner.build_command(runner.validate({"kind": "link", "top_k": 3, "limit_sources": 4}))
    assert link[-6:-2] == ["link", "--top-k", "3", "--retrieval"] or ("link" in link and "--limit-sources" in link)
    assert link[link.index("--limit-sources") + 1] == "4"
    mon = runner.build_command(runner.validate({"kind": "monitor", "force": True}))
    assert "monitor" in mon and "--once" in mon and "--force" in mon
    assert "--force" not in runner.build_command(runner.validate({"kind": "monitor"}))
    assert runner.estimate(runner.validate({"kind": "link", "top_k": 3, "limit_sources": 4}))["calls"] == 12
    assert runner.estimate(runner.validate({"kind": "monitor"}))["calls"] is None
    with pytest.raises(runner.RunnerError):
        runner.validate({"kind": "rm -rf"})


def test_external_detection_finds_a_real_cli_process():
    """Regression: pgrep treated the '-m ...' pattern as one of its own options and found nothing."""
    import subprocess

    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)", "-m", "agents.traceability_agent", "link"])
    try:
        time.sleep(0.5)
        assert proc.pid in runner._external_pids()
    finally:
        proc.kill()
        proc.wait()


def test_link_a_specific_requirement_builds_the_right_command_and_rejects_bad_ids():
    p = runner.validate({"kind": "link", "requirement_ids": ["NEW-001", "REQ_2.a"], "top_k": 3})
    cmd = runner.build_command(p)
    assert [cmd[i + 1] for i, c in enumerate(cmd) if c == "--requirement"] == ["NEW-001", "REQ_2.a"]
    assert "--limit-sources" not in cmd
    assert runner.estimate(p)["calls"] == 6
    for bad in (["a b"], ["x;rm -rf"], ["../x"], [""], "NEW-001", ["a"] * 21):
        with pytest.raises(runner.RunnerError):
            runner.validate({"kind": "link", "requirement_ids": bad})


def test_only_unlinked_links_all_requirements_without_a_link():
    p = runner.validate({"kind": "link", "project": "spring-petclinic", "top_k": 3, "limit_sources": 0, "only_unlinked": True})
    cmd = runner.build_command(p)
    assert "--only-unlinked" in cmd and "--requirement" not in cmd and "--limit-sources" not in cmd
    assert cmd[cmd.index("--project") + 1] == "spring-petclinic"
    # a named requirement list wins: the flag is dropped
    named = runner.validate({"kind": "link", "requirement_ids": ["NEW-1"], "only_unlinked": True})
    assert "only_unlinked" not in named
    assert "--only-unlinked" not in runner.build_command(runner.validate({"kind": "link"}))
