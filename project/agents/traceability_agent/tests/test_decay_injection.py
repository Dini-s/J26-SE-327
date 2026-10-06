"""Decay-injection harness: mutations and detection accounting (LLM is a deterministic fake)."""

from agents.traceability_agent.decay_injection import (
    UNRELATED,
    change_numbers,
    cosmetic_change,
    negate_behavior,
    run_injection,
    strip_to_first_sentence,
    unrelated_replacement,
)
from agents.traceability_agent.utils import content_hash
from shared.schemas.traceability import Artifact, TraceabilityLink

REQ = Artifact(id="R1", type="requirement", text="The unit shall retry 3 times.")
TARGET = Artifact(id="D1", type="design", text="Retries 3 times. Logs each failure. Then gives up.")
LINK = TraceabilityLink(
    source_id="R1", target_id="D1", link_type="requirement_to_design", confidence=0.9,
    justification="j", text_hash=content_hash(REQ, TARGET),
)


def test_mutations_change_text_as_intended():
    assert unrelated_replacement("x") == UNRELATED
    assert "shall not" in negate_behavior("It shall retry.")
    assert negate_behavior("a == b") == "a != b"
    assert "307" in change_numbers("retry 3 times")
    assert strip_to_first_sentence("One. Two. Three.") == "One."
    assert cosmetic_change("x").startswith("x")


class FakeLLM:
    """Says 'linked' only while the target still looks like the original (retry + 3 times)."""

    def verify_link(self, source, target):
        ok = "3 times" in target.text and "UNRELATED" not in target.text and "cafeteria" not in target.text
        return {"is_linked": ok, "confidence": 0.9 if ok else 0.1, "reasoning": "fake"}


def test_run_injection_counts_detections_and_false_decays():
    report = run_injection([LINK], [REQ, TARGET], FakeLLM())
    per = report["per_mutation"]
    assert per["unrelated_replacement"] == {"injected": 1, "detected": 1}
    assert per["change_numbers"] == {"injected": 1, "detected": 1}  # "3 times" gone
    assert per["negate_behavior"]["injected"] == 0  # nothing to negate in this text -> skipped
    assert per["strip_to_first_sentence"] == {"injected": 1, "detected": 0}  # still says 3 times
    assert report["decay_detection_accuracy"] == 2 / 3
    assert report["false_decay_rate"] == 0.0  # cosmetic change was not flagged


def test_llm_client_truncates_long_artifacts():
    from unittest.mock import MagicMock

    from shared.llm.client import LLMClient

    fake = MagicMock()
    fake.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"is_linked": true, "confidence": 0.9, "reasoning": "r"}'))
    ]
    llm = LLMClient(client=fake, max_artifact_chars=50)
    long_art = Artifact(id="C", type="code", text="x" * 500)
    llm.verify_link(REQ, long_art)
    prompt = fake.chat.completions.create.call_args[1]["messages"][1]["content"]
    assert "x" * 50 in prompt and "x" * 51 not in prompt and "[truncated]" in prompt


def test_llm_client_uses_self_hosted_endpoint(monkeypatch):
    from unittest.mock import patch

    from shared.llm.client import LLMClient

    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "llama3.1-8k")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = LLMClient()
    assert llm.model == "llama3.1-8k"
    with patch("openai.OpenAI") as ctor:
        llm.client
    kwargs = ctor.call_args[1]
    assert kwargs["base_url"] == "http://localhost:11434/v1" and kwargs["api_key"] == "not-needed"
