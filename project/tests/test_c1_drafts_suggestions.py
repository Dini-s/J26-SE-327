"""Component 1 API: drafts follow the effective text (edited text while the decision is `edited`, else the original) and the rule-based suggested decision.

Backends are scripted and the workspace is the seeded one from test_c1_neo4j.py: no model server, no Part A models, no graph.
"""
import json

import pytest

from agents.requirement_agent.api import suggest
from agents.requirement_agent.api.db import dumps
from agents.requirement_agent.generation import MockBackend
from tests.test_c1_api import make_client  # noqa: F401  (fixture)
from tests.test_c1_neo4j import isolated_settings, seed  # noqa: F401  (isolated_settings is autouse there)

ORIGINAL = "The bank shall keep audit logs for seven years."
CLEAR = "The bank shall keep audit logs for seven years and export them within 2 seconds."  # the scripted backend answers this one


def backend(calls):
    def reply(system, user):
        calls.append(user)
        if "within 2 seconds" in user:
            return json.dumps({"status": "ok", "user_story": "As an auditor, I want logs kept, so that I can review them.", "technical_task": "Keep audit logs seven years.",
                               "acceptance_criteria": ["Given a log, when seven years pass, then it is still readable.", "Given a request, when exporting, then it takes 2 seconds."],
                               "rationale": "Role assumed."})
        return json.dumps({"status": "needs_clarification", "clarification_questions": ["Which logs?"], "rationale": "Unclear."})
    return MockBackend(reply)


@pytest.fixture
def calls():
    return []


@pytest.fixture
def c(make_client, calls):  # noqa: F811
    client = make_client(backend=backend(calls))
    db = client.app.state.db
    seed(db, project=False)
    db.run("DELETE FROM decisions")
    db.run("DELETE FROM generation WHERE uid='p1-REQ-004'")  # seeded as failed; start with no draft
    return client


def wait(c):
    assert c.app.state.manager.wait_idle(30)


def draft(c, rid="REQ-004"):
    return c.get(f"/api/requirements/{rid}").json()["generation"]


def edit(c, text=CLEAR, note=None, rid="REQ-004"):
    return c.put(f"/api/requirements/{rid}/decision", json={"decision": "edited", "edited_text": text, "note": note})


def generate_original(c, calls):
    assert c.post("/api/requirements/REQ-004/generate").status_code == 202
    wait(c)
    assert draft(c)["state"] == "needs_clarification" and calls[-1].endswith(ORIGINAL)


# ------------------------------------------------------------------------------------------------------------------ drafts follow the text
def test_saving_an_edit_makes_a_new_draft_from_the_edited_text(c, calls):
    generate_original(c, calls)
    assert edit(c).status_code == 200
    wait(c)
    g = draft(c)
    assert g["state"] == "done" and g["generated_from"] == "clarified"
    assert calls[-1].endswith(CLEAR) and len(calls) == 2


def test_the_edit_goes_ahead_of_the_queue_whatever_the_policy(c, calls):
    generate_original(c, calls)
    c.post("/api/projects/1/generation/pause")
    edit(c)
    g = draft(c)
    assert g["state"] == "queued" and g["user_story"] == ""  # the old draft is replaced while the new one waits
    assert c.app.state.db.one("SELECT priority FROM generation WHERE uid='p1-REQ-004'")["priority"] == 0
    c.post("/api/projects/1/generation/resume")
    wait(c)
    assert draft(c)["state"] == "done"


def test_regenerate_uses_the_edited_text_and_skips_the_cache(c, calls):
    edit(c)
    wait(c)
    n = len(calls)
    assert c.post("/api/requirements/REQ-004/generate").status_code == 202
    wait(c)
    assert len(calls) == n + 1 and calls[-1].endswith(CLEAR) and draft(c)["generated_from"] == "clarified"


def test_a_comment_or_the_same_text_changes_nothing(c, calls):
    edit(c)
    wait(c)
    n, before = len(calls), draft(c)
    edit(c, note="just a comment")
    wait(c)
    assert len(calls) == n and draft(c)["updated_at"] == before["updated_at"]
    c.put("/api/requirements/REQ-004/decision", json={"decision": "accepted", "note": "fine"})  # leaves `edited`: that is a text change, tested below
    wait(c)
    n = len(calls)
    c.put("/api/requirements/REQ-004/decision", json={"decision": "accepted", "note": "another comment"})
    wait(c)
    assert len(calls) == n


def test_removing_the_decision_goes_back_to_the_original_text(c, calls):
    generate_original(c, calls)
    edit(c)
    wait(c)
    assert draft(c)["state"] == "done"
    assert c.delete("/api/requirements/REQ-004/decision").status_code == 204
    # the original wording is cached from the first run: shown at once, no new call
    assert draft(c)["state"] == "needs_clarification" and draft(c)["generated_from"] == "original" and len(calls) == 2
    assert edit(c).status_code == 200  # and the edited wording is cached too
    assert draft(c)["state"] == "done" and len(calls) == 2


def test_leaving_edited_queues_the_original_when_it_was_never_generated(c, calls):
    edit(c)
    wait(c)
    assert len(calls) == 1
    c.delete("/api/requirements/REQ-004/decision")
    wait(c)
    assert len(calls) == 2 and calls[-1].endswith(ORIGINAL)
    g = draft(c)
    assert g["state"] == "needs_clarification" and g["generated_from"] == "original"


def test_reject_never_queues_a_draft(c, calls):
    edit(c)
    wait(c)
    n = len(calls)
    c.put("/api/requirements/REQ-004/decision", json={"decision": "rejected", "note": "out of scope"})
    wait(c)
    assert len(calls) == n and draft(c)["state"] != "queued"


def test_a_requirement_without_a_draft_gets_none_from_a_comment(c, calls):
    c.put("/api/requirements/REQ-004/decision", json={"decision": "accepted", "note": "ok"})
    c.delete("/api/requirements/REQ-004/decision")
    wait(c)
    assert calls == [] and draft(c)["state"] == "not_requested"


# ------------------------------------------------------------------------------------------------------------------ suggestions
def suggestions(c):
    return {i["id"]: i["suggestion"] for i in c.get("/api/projects/1/requirements").json()["items"]}


def test_suggestions_on_the_seeded_workspace(c):
    s = suggestions(c)
    assert s["REQ-001"]["action"] == "edit" and "The wording is unclear." in s["REQ-001"]["reasons"] and any("REQ-002" in r for r in s["REQ-001"]["reasons"])
    assert s["REQ-002"]["action"] == "reject" and "REQ-001" in s["REQ-002"]["reasons"][0]  # the later copy; the reason names the earlier one
    assert s["REQ-003"]["action"] == "edit" and "2 follow-up questions to answer." in s["REQ-003"]["reasons"]  # the seeded draft asked two
    assert s["REQ-004"]["action"] == "accept" and len(s["REQ-004"]["reasons"]) == 1


def test_detail_carries_the_same_suggestion(c):
    for rid, listed in suggestions(c).items():
        assert c.get(f"/api/requirements/{rid}").json()["suggestion"] == listed


def test_a_conflict_or_high_risk_means_edit_and_a_clear_one_means_accept(c):
    db = c.app.state.db
    db.run("UPDATE requirements SET conflict_matches=? WHERE uid='p1-REQ-004'", (dumps([{"id": "REQ-003", "uid": "p1-REQ-003", "similarity": 0.8, "kind": "x", "reason": "r"}]),))
    s = suggestions(c)["REQ-004"]
    assert s["action"] == "edit" and s["reasons"] == ["May conflict with another requirement."]
    db.run("UPDATE requirements SET conflict_matches='[]', risk_level='MEDIUM' WHERE uid='p1-REQ-004'")
    assert suggestions(c)["REQ-004"]["reasons"] == ["Risk level is medium."]
    db.run("UPDATE requirements SET risk_level='LOW' WHERE uid='p1-REQ-004'")
    assert suggestions(c)["REQ-004"]["action"] == "accept"


def test_a_suggestion_is_not_stored_exported_or_published(c):
    cols = [r["name"] for r in c.app.state.db.all("PRAGMA table_info(requirements)")]
    assert not any("suggest" in name for name in cols)
    assert "suggestion" not in c.get("/api/projects/1/export?format=json").text and "suggest" not in c.get("/api/projects/1/export?format=csv").text.lower()


def test_the_rule_in_isolation():
    row = dict(ambiguity_label="clear", conflict_matches="[]", risk_level="NONE")
    assert suggest.suggest(row, [], [], 0)["action"] == "accept"
    assert suggest.suggest(dict(row, risk_level="LOW"), [], [], 0)["action"] == "accept"
    assert suggest.suggest(dict(row, risk_level="HIGH"), [], [], 0)["action"] == "edit"
    assert suggest.suggest(dict(row, ambiguity_label="defect"), [], [], 0)["action"] == "edit"
    assert suggest.suggest(row, [], [], 1)["reasons"] == ["1 follow-up question to answer."]
    assert suggest.suggest(row, [], ["REQ-9"], 0)["action"] == "edit"  # the earlier item of a pair is not rejected
    assert suggest.suggest(dict(row, ambiguity_label="defect"), ["REQ-1"], [], 3) == {"action": "reject", "reasons": [suggest.suggest(row, ["REQ-1"], [], 0)["reasons"][0]]}
