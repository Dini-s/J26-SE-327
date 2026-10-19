"""Deleting uploaded sources (one or all) with everything derived from them, the 409 rule while a job runs, path safety, and analyse-twice idempotence."""
import threading
from datetime import datetime, timedelta, timezone

import pytest

from agents.requirement_agent.api import cleanup
from agents.requirement_agent.api.app import create_app
from agents.requirement_agent.api.gen_worker import mock_reply
from agents.requirement_agent.generation import Backend
from tests.test_c1_api import (  # noqa: F401  (fixtures and helpers are shared with the API tests)
    CONFLICT_DOC, MODELS_PRESENT, SAMPLE, CountingBackend, analyze, client, error_of, make_client, reqs, upload,
)

pytestmark = pytest.mark.skipif(not MODELS_PRESENT, reason="saved models missing in models/component1/part_a_active")

DOC_A = b"1. Performance\n\n1.1 The system shall return search results within 2 seconds.\n1.2 The system shall allow users to export reports as PDF.\n"
DOC_B = b"2. Performance\n\n2.1 The system shall return search results within 5 seconds.\n2.2 The system shall not allow users to export reports as PDF.\n"


def two_sources(c):
    r = upload(c, [("a.txt", DOC_A, "text/plain"), ("b.txt", DOC_B, "text/plain")])
    assert r.status_code == 201
    return [s["id"] for s in r.json()["accepted"]]


def files_on_disk(c):
    return sorted(p for p in (c.app.state.workspace / "uploads").rglob("*") if p.is_file())


def table(c, name, where="1=1", args=()):
    return c.app.state.db.all(f"SELECT * FROM {name} WHERE {where}", args)


class BlockingBackend(Backend):
    """Holds every generation until released, so a project stays 'busy'."""

    def __init__(self):
        self.release = threading.Event()

    def generate(self, system, user):
        self.release.wait(30)
        return mock_reply(system, user)


# ------------------------------------------------------------------------------------------------------------------- one source
def test_delete_one_of_two_sources(client):
    a, b = two_sources(client)
    analyze(client, files=())
    assert reqs(client)["total"] == 4
    assert len(files_on_disk(client)) == 2

    r = client.delete(f"/api/projects/1/sources/{b}")
    assert r.status_code == 204 and r.content == b""
    assert [s["id"] for s in client.get("/api/projects/1/sources").json()] == [a]
    assert len(files_on_disk(client)) == 1
    items = reqs(client)["items"]
    assert [i["id"] for i in items] == ["REQ-001", "REQ-002"] and {i["source_file"] for i in items} == {"a.txt"}
    s = client.get("/api/projects/1/summary").json()
    assert s["requirements"] == 2 and s["conflicts"] == 0 and s["task_drafts"]["total"] == 2
    assert client.get("/api/requirements/REQ-003").status_code == 404


def test_cascade_removes_results_decisions_and_conflicts_of_that_source_only(client):
    a, b = two_sources(client)
    analyze(client, files=())
    ids = {i["source_file"] + i["id"]: i["uid"] for i in reqs(client)["items"]}
    mine = ids["a.txtREQ-001"]
    theirs = ids["b.txtREQ-003"]
    for uid in (mine, theirs):
        assert client.post(f"/api/requirements/{uid}/decision", json={"decision": "accepted"}).status_code == 200
        assert client.put(f"/api/requirements/{uid}/decision", json={"decision": "accepted", "note": "again"}).status_code == 200  # the first one goes to the audit table
    assert table(client, "conflicts"), "the two files should produce a conflict candidate"

    assert client.delete(f"/api/projects/1/sources/{b}").status_code == 204
    assert [r["uid"] for r in table(client, "requirements")] == [mine, ids["a.txtREQ-002"]]
    assert [r["uid"] for r in table(client, "generation")] == [mine, ids["a.txtREQ-002"]]
    assert [r["uid"] for r in table(client, "decisions")] == [mine]
    assert {r["uid"] for r in table(client, "decision_audit")} == {mine}
    assert table(client, "conflicts") == []
    assert client.get("/api/requirements/REQ-001").json()["decision"]["decision"] == "accepted"


def test_remaining_requirements_lose_links_to_deleted_ones_and_their_risk_is_recomputed(client):
    a, b = two_sources(client)
    analyze(client, files=())
    before = client.get("/api/requirements/REQ-001").json()
    assert before["conflicts"] and before["conflicts"][0]["id"] == "REQ-003"
    assert before["risk"]["score"] >= 1
    client.delete(f"/api/projects/1/sources/{b}")
    after = client.get("/api/requirements/REQ-001").json()
    assert after["conflicts"] == [] and after["duplicates"] == []
    assert not any(f["type"] == "conflict" for f in after["findings"]) and "REQ-003" not in after["explanation"]
    assert after["risk"]["score"] == before["risk"]["score"] - 1
    assert reqs(client, type="conflict")["total"] == 0


def test_delete_unknown_source_and_project_use_the_error_shape(client):
    two_sources(client)
    assert error_of(client.delete("/api/projects/1/sources/999"))["code"] == "source_not_found"
    assert client.delete("/api/projects/1/sources/999").status_code == 404
    other = client.post("/api/projects", json={"name": "Other"}).json()["id"]
    sid = client.get("/api/projects/1/sources").json()[0]["id"]
    assert error_of(client.delete(f"/api/projects/{other}/sources/{sid}"))["code"] == "source_not_found"  # a source of another project
    assert error_of(client.delete("/api/projects/99/sources/1"))["code"] == "project_not_found"
    assert error_of(client.delete("/api/projects/99/sources"))["code"] == "project_not_found"
    assert len(client.get("/api/projects/1/sources").json()) == 2  # nothing was deleted by the failed calls


# ------------------------------------------------------------------------------------------------------------------------ all
def test_delete_all_sources_clears_everything_of_the_project(client):
    two_sources(client)
    analyze(client, files=())
    client.post("/api/requirements/REQ-001/decision", json={"decision": "rejected"})
    other = client.post("/api/projects", json={"name": "Other"}).json()["id"]
    analyze(client, files=(("c.txt", SAMPLE, "text/plain"),), pid=other)

    r = client.delete("/api/projects/1/sources")
    assert r.status_code == 204
    assert client.get("/api/projects/1/sources").json() == []
    assert reqs(client)["total"] == 0
    s = client.get("/api/projects/1/summary").json()
    assert s["requirements"] == 0 and s["conflicts"] == 0 and s["duplicates"] == 0 and (s["task_drafts"]["generated"], s["task_drafts"]["total"]) == (0, 0) and s["open_findings"] == 0
    db = client.app.state.db
    for name in ("requirements", "generation", "decisions", "decision_audit"):
        assert db.one(f"SELECT COUNT(*) n FROM {name} WHERE uid LIKE 'p1-%'")["n"] == 0, name
    assert db.one("SELECT COUNT(*) n FROM conflicts WHERE project_id=1")["n"] == 0
    assert not [p for p in files_on_disk(client) if "/1/" in str(p).replace("\\", "/")]
    # the other project is untouched
    assert reqs(client, pid=other)["total"] == 3 and len(client.get(f"/api/projects/{other}/sources").json()) == 1
    # an empty project can be cleared again, and used again afterwards
    assert client.delete("/api/projects/1/sources").status_code == 204
    analyze(client, files=(("again.txt", SAMPLE, "text/plain"),))
    assert reqs(client)["total"] == 3 and reqs(client)["items"][0]["id"] == "REQ-001"


# --------------------------------------------------------------------------------------------------------------- busy projects (409)
def test_delete_is_refused_while_drafts_are_being_generated(make_client):
    backend = BlockingBackend()
    c = make_client(backend=backend)
    a, b = two_sources(c)
    c.post("/api/projects/1/analyze")
    for call in (lambda: c.delete(f"/api/projects/1/sources/{b}"), lambda: c.delete("/api/projects/1/sources")):
        r = call()
        assert r.status_code == 409 and error_of(r)["code"] == "project_busy" and "still running" in error_of(r)["message"]
    assert len(c.get("/api/projects/1/sources").json()) == 2 and reqs(c)["total"] == 4  # nothing was removed
    backend.release.set()
    assert c.app.state.manager.wait_idle(60)
    assert c.delete(f"/api/projects/1/sources/{b}").status_code == 204


def test_delete_is_refused_while_part_a_is_running_but_not_for_a_stale_job(client):
    two_sources(client)
    db = client.app.state.db
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.run("INSERT INTO jobs (id, project_id, stage, part_a_done, created_at, updated_at) VALUES ('j1', 1, 'analyse', 0, ?, ?)", (stamp, stamp))
    r = client.delete("/api/projects/1/sources")
    assert r.status_code == 409 and error_of(r)["code"] == "project_busy"
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
    db.run("UPDATE jobs SET updated_at=? WHERE id='j1'", (old,))
    assert client.delete("/api/projects/1/sources").status_code == 204  # a job that stopped long ago does not block forever


def test_queued_entries_are_resumed_when_the_server_restarts(tmp_path, make_client):
    c = make_client(workspace=tmp_path / "ws2")
    analyze(c)
    db = c.app.state.db
    db.run("UPDATE generation SET state='queued', result=NULL WHERE uid='p1-REQ-001'")  # the in-memory queue entry is lost with the process
    c2 = make_client(workspace=tmp_path / "ws2")  # a restart on the same workspace
    assert c2.app.state.manager.wait_idle(60)
    g = c2.get("/api/requirements/REQ-001").json()["generation"]
    assert g["state"] == "done"  # it was queued again (the cached reply resolved it), not left queued forever and not failed
    assert c2.delete("/api/projects/1/sources").status_code == 204


# ----------------------------------------------------------------------------------------------------------------------- path safety
def test_traversal_in_the_url_cannot_delete_anything(client, tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me")
    two_sources(client)
    for bad in ("..%2F..%2Fvictim.txt", "../victim.txt", "%2e%2e", "1%00", "abc"):
        r = client.delete(f"/api/projects/1/sources/{bad}")
        assert r.status_code in (404, 405, 422), (bad, r.status_code)
    assert victim.read_text() == "keep me" and len(files_on_disk(client)) == 2


def test_a_tampered_stored_path_outside_uploads_is_never_deleted(client, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("do not delete")
    sneaky = tmp_path / "ws" / "uploads" / ".." / ".." / "outside.txt"
    db = client.app.state.db
    sid = db.run("INSERT INTO sources (project_id, filename, stored_path, ext, size_bytes, warnings, extracted, created_at) VALUES (1, 'evil.txt', ?, '.txt', 1, '[]', ?, 'now')",
                 (str(sneaky), '{"text": "", "line_map": []}'))
    assert client.delete(f"/api/projects/1/sources/{sid}").status_code == 204
    assert outside.read_text() == "do not delete"  # the row is gone, the file outside the uploads folder is not touched
    assert client.get("/api/projects/1/sources").json() == []


def test_remove_upload_only_deletes_inside_the_uploads_folder(tmp_path):
    ws = tmp_path / "ws"
    (ws / "uploads" / "1").mkdir(parents=True)
    inside, outside = ws / "uploads" / "1" / "x.txt", tmp_path / "x.txt"
    inside.write_text("a")
    outside.write_text("b")
    assert cleanup.remove_upload(ws, str(outside)) is False and outside.exists()
    assert cleanup.remove_upload(ws, str(ws / "uploads" / ".." / ".." / "x.txt")) is False and outside.exists()
    assert cleanup.remove_upload(ws, str(inside)) is True and not inside.exists()
    assert not (ws / "uploads" / "1").exists()  # the empty project folder is removed too
    assert cleanup.remove_upload(ws, str(ws / "uploads" / "1" / "gone.txt")) is True  # already gone is fine
    assert (ws / "uploads").exists()


# ----------------------------------------------------------------------------------------------- analyse twice and kept decisions
def test_analyzing_twice_does_not_duplicate_requirements(client):
    two_sources(client)
    analyze(client, files=())
    first = [(i["id"], i["text"], i["source_file"]) for i in reqs(client)["items"]]
    summary = client.get("/api/projects/1/summary").json()
    analyze(client, files=())
    analyze(client, files=())
    again = [(i["id"], i["text"], i["source_file"]) for i in reqs(client)["items"]]
    assert again == first and len(first) == 4
    assert client.get("/api/projects/1/summary").json() == summary
    assert len(table(client, "requirements")) == 4 and len(table(client, "generation")) == 4


def test_a_decision_survives_a_rerun_only_while_text_and_source_are_unchanged(client):
    ids = [upload(client, [("a.txt", DOC_A, "text/plain")]).json()["accepted"][0]["id"]]
    analyze(client, files=())
    client.post("/api/requirements/REQ-001/decision", json={"decision": "edited", "edited_text": "The system shall respond in 2 seconds."})
    analyze(client, files=())
    assert client.get("/api/requirements/REQ-001").json()["decision"]["decision"] == "edited"  # same text, same source: kept

    client.delete(f"/api/projects/1/sources/{ids[0]}")
    upload(client, [("a.txt", DOC_A, "text/plain")])  # the same file again is a new source
    analyze(client, files=())
    assert client.get("/api/requirements/REQ-001").json()["decision"] is None  # not kept: it is a different source

    # the same text in a second source does not take over the first one's id or decision
    upload(client, [("copy.txt", DOC_A, "text/plain")])
    analyze(client, files=())
    items = reqs(client)["items"]
    assert [i["source_file"] for i in items] == ["a.txt", "a.txt", "copy.txt", "copy.txt"]
    assert [i["id"] for i in items] == ["REQ-001", "REQ-002", "REQ-003", "REQ-004"]
