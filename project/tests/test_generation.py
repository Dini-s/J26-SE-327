"""Optional Part B generation: output validation, retries, backends, the training prompt, and that Part A is unchanged when generation is off.

No test needs a running LLM server or model weights: backends are scripted (MockBackend), the replay backend reads a temporary file, and the Ollama
backend's HTTP call is replaced. Agent tests use a temporary embedding cache so models/ is never written.
"""
import json
import urllib.error
from pathlib import Path

import pandas as pd
import pytest

from agents.requirement_agent import agent as agent_mod
from agents.requirement_agent import config, features, generation, prompts, schemas
from agents.requirement_agent.generation import BackendError, MockBackend, OllamaBackend, ReplayBackend, ReplayMiss, generate_structured

ROOT = Path(__file__).resolve().parents[1]
SFT_TRAIN = ROOT / "data" / "component1" / "processed" / "llm_sft" / "sft_train.jsonl"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE = FIXTURES / "sample_srs.txt"  # the file name is the document name in the expected output
EXPECTED = FIXTURES / "requirement_agent_sample_expected.json"

MODELS_PRESENT = all((agent_mod.MODELS_DIR / f).exists() for f in agent_mod.MODEL_FILES.values()) and (agent_mod.MODELS_DIR / "duplicates_config.json").exists()
needs_models = pytest.mark.skipif(not MODELS_PRESENT, reason="saved models missing in models/component1/part_a_active")

REQ = "The system shall lock a user account after five failed login attempts."
OK = {
    "status": "ok",
    "user_story": "As a security officer, I want accounts locked after five failed logins, so that guessing attacks are slowed.",
    "technical_task": "Count failed logins and lock the account at the fifth failure.",
    "acceptance_criteria": ["Given five failed logins, when the fifth attempt fails, then the account is locked.",
                            "Given fewer than five failed logins, when the user signs in correctly, then access is granted."],
    "rationale": "Role assumed: security officer.",
}
NC = {"status": "needs_clarification", "clarification_questions": ["How is 'fast' measured?"], "rationale": "Not measurable."}


def reply(obj):
    return json.dumps(obj)


# ------------------------------------------------------------------------------------------------------------ schema and retries
def test_valid_ok_output():
    backend = MockBackend([reply(OK)])
    r = generate_structured(backend, REQ)
    assert (r.status, r.attempts, r.manual_review) == ("ok", 1, False)
    assert r.user_story == OK["user_story"] and len(r.acceptance_criteria) == 2 and r.clarification_questions == []
    cols = r.as_columns()
    assert list(cols) == generation.GENERATION_COLUMNS
    assert json.loads(cols["acceptance_criteria"]) == OK["acceptance_criteria"] and cols["gen_raw_output"] == ""


def test_valid_needs_clarification_output():
    r = generate_structured(MockBackend([reply(NC)]), "The system shall be fast.")
    assert (r.status, r.attempts, r.manual_review) == ("needs_clarification", 1, False)
    assert r.clarification_questions == NC["clarification_questions"] and r.user_story == "" and r.acceptance_criteria == []


def test_json_is_taken_from_first_brace_to_last_brace():
    wrapped = "Here is the answer:\n```json\n" + reply(OK) + "\n```\nHope this helps."
    assert generate_structured(MockBackend([wrapped]), REQ).status == "ok"


def test_invalid_json_then_valid_succeeds_on_second_attempt():
    backend = MockBackend(["this is not json", reply(OK)])
    r = generate_structured(backend, REQ)
    assert (r.status, r.attempts, r.manual_review) == ("ok", 2, False)
    assert len(backend.calls) == 2


def test_three_failures_set_manual_review_and_keep_the_last_raw_output():
    backend = MockBackend(["no json", '{"status": "ok"}', '{"status": "maybe", "rationale": "last"}'])
    r = generate_structured(backend, REQ)
    assert (r.status, r.attempts, r.manual_review) == ("invalid", 3, True)
    assert r.raw_output == '{"status": "maybe", "rationale": "last"}' and len(backend.calls) == 3
    cols = r.as_columns()
    assert cols["gen_manual_review"] is True and cols["gen_raw_output"] == r.raw_output and cols["gen_status"] == "invalid"


def test_story_regex_failure_is_rejected():
    bad = dict(OK, user_story="I want accounts locked, so that attacks are slowed.")
    assert any("user_story" in p for p in schemas.validate_output(bad))
    r = generate_structured(MockBackend([reply(bad)]), REQ)
    assert r.manual_review and r.attempts == 3
    # the closing period is optional, the other parts are not
    assert schemas.validate_output(dict(OK, user_story="As an admin, I want x, so that y")) == []
    assert schemas.validate_output(dict(OK, user_story="As an admin, I want x")) != []


@pytest.mark.parametrize("count", [1, 7])
def test_criteria_count_outside_2_to_6_is_rejected(count):
    crit = [f"Given case {i}, when it runs, then result {i} holds." for i in range(count)]
    problems = schemas.validate_output(dict(OK, acceptance_criteria=crit))
    assert any("acceptance_criteria must be a list of 2 to 6" in p for p in problems)
    assert generate_structured(MockBackend([reply(dict(OK, acceptance_criteria=crit))]), REQ).manual_review


@pytest.mark.parametrize("count", [2, 6])
def test_criteria_count_limits_are_accepted(count):
    crit = [f"Given case {i}, when it runs, then result {i} holds." for i in range(count)]
    assert schemas.validate_output(dict(OK, acceptance_criteria=crit)) == []


def test_criteria_must_be_given_when_then_case_insensitive():
    assert schemas.validate_output(dict(OK, acceptance_criteria=["GIVEN a user, WHEN they log in, THEN they see the home page.", "given x, when y, then z"])) == []
    bad = dict(OK, acceptance_criteria=["Given a user, then they see the home page.", "When they log in, then it works."])
    assert [p for p in schemas.validate_output(bad) if "criterion" in p] == ["acceptance criterion 1 is not 'Given ... when ... then ...'",
                                                                              "acceptance criterion 2 is not 'Given ... when ... then ...'"]


def test_required_fields_and_status():
    assert schemas.validate_output({"status": "other"})[0].startswith("status must be")
    assert schemas.validate_output(dict(OK, technical_task="  ")) != []
    assert schemas.validate_output(dict(OK, rationale="")) != []
    assert schemas.validate_output({"status": "needs_clarification", "clarification_questions": [], "rationale": "x"}) != []
    assert schemas.validate_output({"status": "needs_clarification", "rationale": "x"}) != []
    assert schemas.validate_output(dict(NC, extra_key=1)) == []  # extra keys are ignored


def test_extract_json_errors():
    assert schemas.extract_json("nothing here")[0] is None
    assert schemas.extract_json("{broken")[0] is None
    assert schemas.extract_json("[1, 2]")[0] is None
    assert schemas.extract_json('{"a": 1}')[0] == {"a": 1}


# ------------------------------------------------------------------------------------------------------------------------ prompt
def test_system_prompt_matches_the_training_data():
    assert SFT_TRAIN.exists(), "sft_train.jsonl is missing"
    systems, users = set(), []
    with open(SFT_TRAIN, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            assert [m["role"] for m in row["messages"]] == ["system", "user", "assistant"]
            systems.add(row["messages"][0]["content"])
            users.append(row["messages"][1]["content"])
    assert systems == {prompts.SYSTEM_PROMPT}
    assert all(u.startswith("Requirement: ") for u in users)


def test_the_backend_receives_the_training_prompt_format():
    backend = MockBackend([reply(OK)])
    generate_structured(backend, REQ)
    system, user = backend.calls[0]
    assert system == prompts.SYSTEM_PROMPT and user == "Requirement: " + REQ


# ----------------------------------------------------------------------------------------------------------------------- backends
def test_replay_backend_hit_and_miss(tmp_path):
    path = tmp_path / "out.json"
    path.write_text(json.dumps([{"id": "A:1", "requirement_text": REQ, "output": reply(OK)}]), encoding="utf-8")
    backend = ReplayBackend(path)
    assert backend.generate("sys", "Requirement: " + REQ) == reply(OK)
    assert backend.generate("sys", "Requirement: " + REQ.upper().replace(".", " .")) == reply(OK)  # same text up to case and punctuation
    with pytest.raises(ReplayMiss, match="no stored output"):
        backend.generate("sys", "Requirement: The system shall do something else.")
    with pytest.raises(ReplayMiss):
        generate_structured(backend, "The system shall do something else.")  # a miss is not retried or guessed


def test_replay_backend_rejects_a_bad_file(tmp_path):
    with pytest.raises(BackendError, match="not found"):
        ReplayBackend(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "a list"}', encoding="utf-8")
    with pytest.raises(BackendError, match="JSON list"):
        ReplayBackend(bad)
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(BackendError, match="not valid JSON"):
        ReplayBackend(bad)


@pytest.mark.skipif(not (ROOT / "evaluation" / "component1" / "generation" / "ft_outputs.json").exists(), reason="ft_outputs.json not present")
def test_replay_backend_reads_the_stored_fine_tuned_outputs():
    records = json.loads((ROOT / "evaluation" / "component1" / "generation" / "ft_outputs.json").read_text(encoding="utf-8"))
    backend = ReplayBackend(records)
    first = records[0]
    assert backend.generate(prompts.SYSTEM_PROMPT, prompts.user_message(first["requirement_text"])) == first["output"]


def test_make_backend():
    assert isinstance(generation.make_backend("ollama"), OllamaBackend)
    with pytest.raises(BackendError, match="--replay-file"):
        generation.make_backend("replay")
    with pytest.raises(BackendError, match="unknown"):
        generation.make_backend("gpt")


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_ollama_backend_builds_the_request_without_a_server(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["url"], seen["timeout"] = request.full_url, timeout
        seen["auth"] = request.get_header("Authorization")
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"choices": [{"message": {"content": reply(OK)}}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = OllamaBackend({"base_url": "http://host:11434/v1", "model": "my-model", "api_key": "k", "timeout": 7.0})
    r = generate_structured(backend, REQ)
    assert r.status == "ok"
    assert seen["url"] == "http://host:11434/v1/chat/completions" and seen["timeout"] == 7.0 and seen["auth"] == "Bearer k"
    assert seen["body"]["model"] == "my-model" and seen["body"]["stream"] is False
    assert seen["body"]["messages"] == [{"role": "system", "content": prompts.SYSTEM_PROMPT}, {"role": "user", "content": "Requirement: " + REQ}]


def test_ollama_backend_errors_are_backend_errors(monkeypatch):
    with pytest.raises(BackendError, match="LLM_MODEL"):
        OllamaBackend({"base_url": "http://x/v1", "model": "", "api_key": "", "timeout": 1.0}).generate("s", "u")

    def refuse(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    with pytest.raises(BackendError, match="could not get a reply"):
        generate_structured(OllamaBackend({"base_url": "http://x/v1", "model": "m", "api_key": "", "timeout": 1.0}), REQ)  # not retried

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=None: FakeResponse({"unexpected": 1}))
    with pytest.raises(BackendError, match="unexpected reply format"):
        OllamaBackend({"base_url": "http://x/v1", "model": "m", "api_key": "", "timeout": 1.0}).generate("s", "u")


def test_ollama_retry_uses_a_higher_temperature(monkeypatch):
    temps = []

    def fake_urlopen(request, timeout=None):
        temps.append(json.loads(request.data.decode("utf-8"))["temperature"])
        return FakeResponse({"choices": [{"message": {"content": "not json" if len(temps) == 1 else reply(OK)}}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    r = generate_structured(OllamaBackend({"base_url": "http://x/v1", "model": "m", "api_key": "", "timeout": 1.0}), REQ)
    assert r.attempts == 2 and temps == [0.0, 0.3]


def test_llm_settings_from_environment():
    s = config.llm_settings({"LLM_BASE_URL": "http://h:1/v1/", "LLM_MODEL": "m", "LLM_API_KEY": "k", "LLM_TIMEOUT": "5"})
    assert s == {"base_url": "http://h:1/v1", "model": "m", "api_key": "k", "timeout": 5.0}
    d = config.llm_settings({})
    assert d["base_url"] == "http://localhost:11434/v1" and d["model"] == "" and d["timeout"] == 120.0
    assert config.llm_settings({"LLM_TIMEOUT": "abc"})["timeout"] == 120.0


# ------------------------------------------------------------------------------------------------------- agent: Part A unchanged
@pytest.fixture
def temp_cache(tmp_path, monkeypatch):
    """Keep the real embedding cache untouched: embed into a temporary one."""
    monkeypatch.setattr(features, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(features, "CACHE_FILE", tmp_path / "cache" / "cache.joblib")
    monkeypatch.setattr(features, "_CACHE", None)


def same_rows(actual, expected):
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected):
        assert list(a) == list(e)
        for k in e:
            if isinstance(e[k], float):
                assert a[k] == pytest.approx(e[k], abs=1e-6), k
            else:
                assert a[k] == e[k], k


@needs_models
def test_generation_off_gives_the_stored_part_a_output(temp_cache):
    df = agent_mod.run(str(SAMPLE))
    assert list(df.columns) == agent_mod.COLUMNS
    same_rows(json.loads(df.to_json(orient="records")), json.loads(EXPECTED.read_text(encoding="utf-8")))


@needs_models
def test_cli_without_generate_has_exactly_the_part_a_columns(temp_cache, tmp_path):
    out = tmp_path / "out.csv"
    assert agent_mod.main([str(SAMPLE), "--out", str(out)]) == 0
    assert list(pd.read_csv(out, encoding="utf-8-sig").columns) == agent_mod.COLUMNS


@needs_models
def test_generation_on_appends_columns_and_leaves_part_a_unchanged(temp_cache):
    plain = agent_mod.run(str(SAMPLE))
    backend = MockBackend([reply(OK)])
    df = agent_mod.run(str(SAMPLE), generator=backend)
    assert list(df.columns) == agent_mod.COLUMNS + generation.GENERATION_COLUMNS
    pd.testing.assert_frame_equal(df[agent_mod.COLUMNS], plain)
    assert len(backend.calls) == len(df) == 3
    assert set(df.gen_status) == {"ok"} and set(df.gen_attempts) == {1} and not df.gen_manual_review.any()
    assert json.loads(df.acceptance_criteria.iloc[0]) == OK["acceptance_criteria"] and json.loads(df.clarification_questions.iloc[0]) == []


@needs_models
def test_cli_generate_with_replay_backend(temp_cache, tmp_path):
    texts = [r["text"] for r in json.loads(EXPECTED.read_text(encoding="utf-8"))]
    outputs = [reply(OK), reply(OK), reply(NC)]
    replay = tmp_path / "ft.json"
    replay.write_text(json.dumps([{"id": f"S:{i}", "requirement_text": t, "output": o} for i, (t, o) in enumerate(zip(texts, outputs))]), encoding="utf-8")
    out = tmp_path / "out.csv"
    assert agent_mod.main([str(SAMPLE), "--out", str(out), "--generate", "--generation-backend", "replay", "--replay-file", str(replay)]) == 0
    df = pd.read_csv(out, encoding="utf-8-sig", keep_default_na=False)
    assert list(df.columns) == agent_mod.COLUMNS + generation.GENERATION_COLUMNS
    assert list(df.gen_status) == ["ok", "ok", "needs_clarification"]
    assert json.loads(df.clarification_questions.iloc[2]) == NC["clarification_questions"]


@needs_models
def test_cli_generate_with_a_replay_miss_stops_with_a_message(temp_cache, tmp_path, capsys):
    replay = tmp_path / "ft.json"
    replay.write_text(json.dumps([{"id": "S:0", "requirement_text": "Something unrelated.", "output": reply(OK)}]), encoding="utf-8")
    out = tmp_path / "out.csv"
    assert agent_mod.main([str(SAMPLE), "--out", str(out), "--generate", "--generation-backend", "replay", "--replay-file", str(replay)]) == 2
    assert "no stored output" in capsys.readouterr().err and not out.exists()


def test_cli_generate_with_replay_needs_a_file(tmp_path, capsys):
    assert agent_mod.main([str(SAMPLE), "--out", str(tmp_path / "o.csv"), "--generate", "--generation-backend", "replay"]) == 2
    assert "--replay-file" in capsys.readouterr().err
