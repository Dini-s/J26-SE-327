"""Component 1: rule-based vague terms, numbers-not-in-source, and the "asked by AI" count. None of these touch Part A.

The vague-term and number tests need no models; the API tests are skipped if the saved Part A models are missing.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from agents.requirement_agent import generation
from agents.requirement_agent.api import vague
from agents.requirement_agent.generation import MockBackend
from tests.test_c1_api import MODELS_PRESENT, analyze, client, make_client, reqs  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parents[2]
SRS = ROOT / "scripts" / "fixtures" / "live_check_srs.txt"


def terms(text):
    return [t["term"].lower() for t in vague.vague_term_spans(text)]


def srs_requirements():
    """The six requirement sentences of the live-check fixture (lines starting with a clause number)."""
    out = []
    for line in SRS.read_text(encoding="utf-8").splitlines():
        head, _, rest = line.partition(" ")
        if rest and head.replace(".", "").isdigit() and head.count(".") == 1 and rest.startswith("The "):
            out.append(rest)
    return out


# ------------------------------------------------------------------------------------------------------------------ vague terms
def test_the_fixture_has_six_requirements():
    assert len(srs_requirements()) == 6


def test_vague_terms_found_in_the_two_vague_fixture_texts():
    texts = srs_requirements()
    quick = next(t for t in texts if "quickly" in t)
    friendly = next(t for t in texts if "user-friendly" in t)
    assert terms(quick) == ["quickly"] and terms(friendly) == ["user-friendly"]
    span = vague.vague_term_spans(quick)[0]
    assert quick[span["start"]:span["end"]] == "quickly"


def test_measurable_fixture_texts_get_no_highlights():
    for t in srs_requirements():
        if "quickly" in t or "user-friendly" in t:
            continue
        assert vague.vague_term_spans(t) == [], t


def test_matching_is_case_insensitive_and_whole_word_only():
    assert terms("Reports must load FAST. Be Easy, EASILY and Robust.") == ["fast", "easy", "easily", "robust"]
    assert vague.vague_term_spans("A fastener, a faster car, easygoing, uneasy, robustness, intuitively") == []
    assert terms("Use it as needed, and so on, etc. Also As Appropriate.") == ["as needed", "and so on", "etc.", "as appropriate"]
    assert vague.vague_term_spans("") == [] and vague.vague_term_spans(None) == []


def test_the_documented_list_is_the_one_in_use():
    assert set(vague.VAGUE_TERMS) == {
        "quickly", "fast", "rapidly", "promptly", "user-friendly", "easy", "easily", "efficient", "efficiently", "intuitive", "flexible",
        "robust", "seamless", "as appropriate", "as needed", "etc.", "and so on", "minimal", "adequate", "reasonable"}


# ------------------------------------------------------------------------------------------------------------------ numbers
def test_numbers_not_in_source_is_strict():
    src = "The system shall respond to 95% of requests within 2 seconds."
    assert generation.numbers_not_in_source(src, {"rationale": "95% within 2 seconds", "user_story": "As a user, I want 2 seconds, so that x."}) == []
    assert generation.numbers_not_in_source(src, {"rationale": "fewer than 5% are slower"}) == ["5"]  # no arithmetic is allowed for
    assert generation.numbers_not_in_source(src, {"acceptance_criteria": ["Given a, when b, then 10 seconds."], "rationale": "r"}) == ["10"]
    assert generation.numbers_not_in_source("up to 1,000 users", {"rationale": "1000 users"}) == []


def test_numbers_rule_equals_the_sft_validator_rule():
    sys.path.insert(0, str(ROOT / "project" / "experiments" / "component1"))
    try:
        import validate_sft_pairs as v
    finally:
        sys.path.pop(0)
    for text in ["95% of 1,000 users in 2.5 s", "section 3.1, item 4.", "no numbers", "v2 and 10,5 and 7."]:
        assert generation.numbers_in(text) == v.numbers_in(text), text
    row = {"rationale": "r 5", "user_story": "As a x, I want 7, so that y.", "technical_task": "t 8", "acceptance_criteria": ["c 9"], "clarification_questions": ["q 4"]}
    assert sorted(generation.output_strings(row)) == sorted(v.output_strings(row))


def load_checker():
    spec = importlib.util.spec_from_file_location("check_c1_live", ROOT / "scripts" / "check_c1_live.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_checker_95_to_5_warns_invented_10_fails_present_numbers_pass():
    check = load_checker()
    src = "The system shall respond to 95% of balance enquiries within 2 seconds under a load of 500 concurrent users."
    assert check.classify_numbers(src, ["5"]) == (["5"], [])  # 100 - 95: warning
    assert check.classify_numbers(src, ["10"]) == ([], ["10"])  # invented: failure
    assert check.classify_numbers(src, ["5", "10"]) == (["5"], ["10"])
    assert check.classify_numbers(src, []) == ([], [])  # numbers present in the source never reach this function
    assert check.classify_numbers("within 99.5% of cases", ["0.5"]) == (["0.5"], [])
    assert check.classify_numbers("no percentages here, 2 seconds", ["98"]) == ([], ["98"])


def test_live_checker_end_to_end_counts_and_exit_code(monkeypatch, capsys):
    """validate_draft: warn for 95 -> 5, fail for an invented 10, silent when every number is in the source."""
    check = load_checker()
    base = {"state": "done", "message": "", "status": "ok", "user_story": "As a user, I want fast answers, so that I can work.",
            "technical_task": "Answer in 2 seconds.", "acceptance_criteria": ["Given load, when asked, then 95% in 2 seconds.", "Given a, when b, then c."],
            "rationale": "r", "clarification_questions": [], "attempts": 1, "manual_review": False, "raw_output": "", "updated_at": None,
            "backend": "ollama", "model": "c1-req", "numbers_not_in_source": []}
    src = "Answer 95% of requests within 2 seconds."
    check.failures.clear(), check.warnings.clear()
    check.validate_draft("REQ-1", src, dict(base))
    assert not check.failures and not check.warnings
    check.validate_draft("REQ-2", src, dict(base, rationale="fewer than 5% are slower", numbers_not_in_source=["5"]))
    assert not check.failures and len(check.warnings) == 1
    check.validate_draft("REQ-3", src, dict(base, technical_task="Answer in 10 seconds.", numbers_not_in_source=["10"]))
    assert len(check.failures) == 1 and "10" in check.failures[0] and len(check.warnings) == 1
    check.validate_draft("REQ-4", src, dict(base, technical_task="Answer in 10 seconds."))  # API field missing the number: inconsistent
    assert len(check.failures) == 3
    check.failures.clear(), check.warnings.clear()


# ------------------------------------------------------------------------------------------------------------------ API
pytestmark_api = pytest.mark.skipif(not MODELS_PRESENT, reason="saved models missing in models/component1/part_a_active")


@pytestmark_api
def test_detail_has_vague_terms_separate_from_part_a(make_client):
    c = make_client()
    text = "The system should process payments quickly."
    c.post("/api/projects/1/sources", files=[("files", ("a.txt", (text + "\n").encode(), "text/plain"))])
    assert c.post("/api/projects/1/analyze").status_code == 202
    assert c.app.state.manager.wait_idle(120)
    d = c.get("/api/requirements/REQ-001").json()
    assert d["vague_terms"] == [{"term": "quickly", "start": text.index("quickly"), "end": text.index("quickly") + 7}]
    # re-reading changes nothing in Part A, and the vague list is never copied into the Part A fields
    assert set(d["ambiguity"]) == {"label", "probability_defect", "weak_words", "weak_word_spans"}
    again = c.get("/api/requirements/REQ-001").json()
    assert again["ambiguity"] == d["ambiguity"]
    summary = c.get("/api/projects/1/summary").json()
    assert summary["ambiguities"]["count"] == (1 if d["ambiguity"]["label"] == "defect" else 0)


@pytestmark_api
def test_draft_payload_lists_numbers_not_in_source(make_client):
    reply = json.dumps({"status": "ok", "user_story": "As a user, I want accounts locked after 5 attempts, so that guessing is slowed.",
                        "technical_task": "Lock the account after 5 failed attempts for 10 minutes.",
                        "acceptance_criteria": ["Given 5 failures, when the fifth fails, then the account is locked.", "Given a lock, when 10 minutes pass, then it opens."],
                        "rationale": "Role assumed."})
    c = make_client(backend=MockBackend([reply]))
    text = "The system shall lock a customer account after 5 failed login attempts."
    c.post("/api/projects/1/sources", files=[("files", ("a.txt", (text + "\n").encode(), "text/plain"))])
    c.post("/api/projects/1/analyze")
    assert c.app.state.manager.wait_idle(120)
    g = c.get("/api/requirements/REQ-001").json()["generation"]
    assert g["state"] == "done" and g["numbers_not_in_source"] == ["10"]  # 5 is in the source, 10 is not
    # nothing generated -> no list
    c2 = make_client(backend=MockBackend(["not json"]), workspace=Path(c.app.state.workspace).parent / "ws2")
    c2.post("/api/projects/1/sources", files=[("files", ("a.txt", (text + "\n").encode(), "text/plain"))])
    c2.post("/api/projects/1/analyze")
    assert c2.app.state.manager.wait_idle(120)
    assert c2.get("/api/requirements/REQ-001").json()["generation"]["numbers_not_in_source"] == []


@pytestmark_api
def test_numbers_present_in_the_source_pass_silently(client):
    analyze(client)  # the mock reply repeats the requirement text, so it adds no numbers of its own
    for item in reqs(client)["items"]:
        assert client.get(f"/api/requirements/{item['uid']}").json()["generation"]["numbers_not_in_source"] == []


@pytestmark_api
def test_asked_by_ai_counts_part_a_ok_that_the_model_questioned(make_client):
    # N = 0: no draft asks for clarification
    c0 = make_client()
    analyze(c0)
    s0 = c0.get("/api/projects/1/summary").json()["ambiguities"]
    assert s0["asked_by_ai"] == 0
    # N > 0: the model asks about every requirement; only those Part A did NOT label as defect are counted, and `count` stays Part A's
    reply = json.dumps({"status": "needs_clarification", "clarification_questions": ["What does it mean?"], "rationale": "Vague."})
    c1 = make_client(backend=MockBackend([reply]), workspace=Path(c0.app.state.workspace).parent / "ws_ai")
    analyze(c1)
    items = reqs(c1)["items"]
    expected = sum(1 for i in items if not i["flags"]["ambiguity"])
    s1 = c1.get("/api/projects/1/summary").json()["ambiguities"]
    assert expected > 0 and s1["asked_by_ai"] == expected
    assert s1["count"] == s0["count"] and s1["high_risk"] == s0["high_risk"]  # Part A numbers do not move
