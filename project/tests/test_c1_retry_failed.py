"""Component 1: the Improve stage says `attention` (not `failed`) when only some drafts failed, failed drafts carry a short reason code, and the failed ones
can be queued again (POST /api/projects/{pid}/drafts/retry-failed).

The model is a scripted backend that can be switched between "down" and "up"; no model server and no real workspace are used.
"""
import pytest

from agents.requirement_agent import generation as gen
from agents.requirement_agent.api import gen_worker, service
from agents.requirement_agent.api.gen_worker import ENGINE_UNAVAILABLE, NOT_IN_REPLAY, failure_reason, mock_reply
from agents.requirement_agent.generation import MockBackend
from tests.test_c1_api import error_of, make_client  # noqa: F401  (fixture)
from tests.test_c1_neo4j import isolated_settings, seed  # noqa: F401  (isolated_settings is autouse there)

TD = dict(generated=0, needs_clarification=0, failed=0, in_progress=0)


@pytest.fixture
def engine_state():
    return {"up": False, "calls": 0}


@pytest.fixture
def c(make_client, engine_state):  # noqa: F811
    """A seeded workspace (four requirements; REQ-004 already has a failed draft) and a model that is down until `engine_state["up"]` is set."""
    def reply(system, user):
        engine_state["calls"] += 1
        if not engine_state["up"]:
            raise gen.BackendError("connection refused by gpu.example.com")
        return mock_reply(system, user)

    client = make_client(backend=MockBackend(reply))
    seed(client.app.state.db, project=False)
    return client


def retry(c, pid=1):
    return c.post(f"/api/projects/{pid}/drafts/retry-failed")


def overview(c):
    return c.get("/api/projects/1/overview").json()


# ------------------------------------------------------------------------------------------------------------------ the reason code
def test_failure_reason_is_a_short_code_from_the_stored_message():
    cases = {
        f"{ENGINE_UNAVAILABLE}: connection refused": "engine_unavailable",
        f"{ENGINE_UNAVAILABLE}: skipped after repeated failures; start the model server and press Retry": "engine_skipped",
        f"{ENGINE_UNAVAILABLE}: Cloud unreachable (timed out)": "cloud_unreachable",
        f"{ENGINE_UNAVAILABLE}: Cloud rejected the request (HTTP 401); check the key and the model": "cloud_rejected",
        NOT_IN_REPLAY: "not_in_replay",
        "unexpected error: KeyError": "unexpected",
        "replay file not found": "engine_not_ready",
        "": "unknown",
    }
    for message, code in cases.items():
        assert failure_reason(message) == code
        assert " " not in failure_reason(message)


def test_failed_drafts_show_the_reason_in_the_list_and_the_detail_and_nothing_else(c):
    db = c.app.state.db
    db.run("UPDATE generation SET message=? WHERE uid='p1-REQ-004'", (f"{ENGINE_UNAVAILABLE}: Cloud unreachable (gpu.example.com timed out)",))
    items = {i["id"]: i for i in c.get("/api/projects/1/requirements").json()["items"]}
    assert items["REQ-004"]["generation_state"] == "failed" and items["REQ-004"]["failure_reason"] == "cloud_unreachable"
    assert items["REQ-001"]["failure_reason"] is None and items["REQ-002"]["failure_reason"] is None  # done, and no draft at all
    assert "gpu.example.com" not in str({k: v for k, v in items["REQ-004"].items() if k != "text"})
    g = c.get("/api/requirements/REQ-004").json()["generation"]
    assert g["state"] == "failed" and g["failure_reason"] == "cloud_unreachable"
    assert c.get("/api/requirements/REQ-001").json()["generation"]["failure_reason"] is None


# ------------------------------------------------------------------------------------------------------------------ the Improve stage
def test_improve_needs_attention_when_some_drafts_failed_and_none_is_waiting():
    p = service.pipeline(["analyzed"], 334, 5, dict(TD, generated=327, failed=7), {"state": "synced", "last_synced_at": None})
    assert p["improve"]["state"] == "attention" and p["improve"]["drafts"]["failed"] == 7 and p["improve"]["drafts_written"] == 327
    # all decided, drafts still failed: it is not "done" yet either
    assert service.pipeline(["analyzed"], 10, 10, dict(TD, generated=9, failed=1), {"state": "synced", "last_synced_at": None})["improve"]["state"] == "attention"
    # a draft that needs clarification counts as written
    assert service.pipeline(["analyzed"], 10, 0, dict(TD, needs_clarification=1, failed=9), {"state": "synced", "last_synced_at": None})["improve"]["state"] == "attention"


def test_improve_is_failed_only_when_every_draft_failed():
    p = service.pipeline(["analyzed"], 334, 0, dict(TD, failed=7), {"state": "synced", "last_synced_at": None})
    assert p["improve"]["state"] == "failed"


def test_waiting_drafts_keep_the_stage_active_and_no_failure_keeps_the_old_states():
    sync = {"state": "synced", "last_synced_at": None}
    assert service.pipeline(["analyzed"], 10, 0, dict(TD, generated=3, failed=2, in_progress=4), sync)["improve"]["state"] == "active"
    assert service.pipeline(["analyzed"], 10, 10, dict(TD, generated=10), sync)["improve"]["state"] == "done"
    assert service.pipeline(["analyzed"], 10, 0, TD, sync)["improve"]["state"] == "waiting"
    assert service.pipeline(["analyzed"], 10, 2, dict(TD, generated=5), sync)["improve"]["state"] == "active"


def test_the_overview_reports_attention(c):
    o = overview(c)  # seed: 2 written (one needs clarification), 1 failed, 3 decided of 4
    assert o["pipeline"]["improve"]["state"] == "attention"
    assert o["pipeline"]["improve"]["drafts"]["failed"] == 1


# ------------------------------------------------------------------------------------------------------------------ retry
def test_retry_failed_queues_only_the_failed_drafts_and_they_run_again(c, engine_state):
    db = c.app.state.db
    db.run("INSERT INTO generation (uid, state, message, attempts, manual_review, updated_at) VALUES ('p1-REQ-002','failed','AI engine unavailable: x',1,0,'2026-10-01T00:00:00+00:00')")
    before = {r["uid"]: r["updated_at"] for r in db.all("SELECT uid, updated_at FROM generation")}
    engine_state["up"] = True
    r = retry(c)
    assert r.status_code == 202 and r.json() == {"queued": 2}
    assert c.app.state.manager.wait_idle(60)
    after = {r["uid"]: r for r in db.all("SELECT * FROM generation")}
    assert after["p1-REQ-004"]["state"] in ("done", "needs_clarification") and after["p1-REQ-002"]["state"] in ("done", "needs_clarification")
    for uid in ("p1-REQ-001", "p1-REQ-003"):  # what was not failed is untouched
        assert after[uid]["updated_at"] == before[uid]
    assert engine_state["calls"] == 2
    assert overview(c)["pipeline"]["improve"]["drafts"]["failed"] == 0
    assert retry(c).json() == {"queued": 0}  # nothing left to retry


def test_a_failed_reply_is_never_cached_so_a_retry_really_runs_the_model(c, engine_state):
    db = c.app.state.db
    assert c.post("/api/requirements/REQ-004/generate").status_code == 202
    assert c.app.state.manager.wait_idle(60)
    g = c.get("/api/requirements/REQ-004").json()["generation"]
    assert g["state"] == "failed" and g["failure_reason"] == "engine_unavailable"
    assert "gpu.example.com" not in str(c.get("/api/projects/1/requirements").json())  # the host in the model's error text is not in the list
    assert db.one("SELECT COUNT(*) n FROM gen_cache")["n"] == 0
    calls = engine_state["calls"]
    engine_state["up"] = True
    assert retry(c).json() == {"queued": 1}
    assert c.app.state.manager.wait_idle(60)
    assert engine_state["calls"] > calls  # no cached failure was shown: the model was asked again
    assert c.get("/api/requirements/REQ-004").json()["generation"]["state"] in ("done", "needs_clarification")
    assert db.one("SELECT COUNT(*) n FROM gen_cache")["n"] == 1  # and the good reply is cached


def test_retry_after_repeated_failures_is_not_skipped(c, engine_state):
    m = c.app.state.manager
    m._fails = gen_worker.MAX_FAST_FAILS + 3  # the queue would skip device items after this many failures in a row
    engine_state["up"] = True
    assert retry(c).json() == {"queued": 1}
    assert m.wait_idle(60)
    assert c.get("/api/requirements/REQ-004").json()["generation"]["state"] in ("done", "needs_clarification")
    assert m._fails == 0


def test_retry_is_refused_while_drafts_are_being_written(c):
    db = c.app.state.db
    db.run("UPDATE generation SET state='running' WHERE uid='p1-REQ-001'")
    r = retry(c)
    assert r.status_code == 409 and error_of(r)["code"] == "generation_running"
    assert db.one("SELECT state FROM generation WHERE uid='p1-REQ-004'")["state"] == "failed"  # nothing was queued


def test_retry_of_an_unknown_project_is_404(c):
    assert error_of(retry(c, 99))["code"] == "project_not_found"
