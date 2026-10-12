"""Evidence-style verdicts: a link needs a real quote from the code."""

import pytest

from shared.llm.client import LLMResponseError


def test_evidence_reply_needs_a_quote_that_is_really_in_the_code():
    from shared.llm.client import parse_evidence_reply

    code = "public ParameterConverters() {\n    this(DEFAULT_STEP_MONITOR);\n}"
    good = {"coverage": "full", "evidence": "public ParameterConverters() {", "reasoning": "defines it"}
    out = parse_evidence_reply(good, code)
    assert out["is_linked"] and out["confidence"] == 0.9 and "Evidence:" in out["reasoning"]
    # whitespace-insensitive, and "..." joins separately checked pieces
    assert parse_evidence_reply({**good, "evidence": "public   ParameterConverters()  {  ...  this(DEFAULT_STEP_MONITOR);"}, code)["is_linked"]
    # invented, missing or too-short quotes are downgraded
    for quote in ("public ParameterConverters(Locale locale) {", "", "a;"):
        out = parse_evidence_reply({**good, "evidence": quote}, code)
        assert not out["is_linked"] and out["confidence"] == 0.1 and out["reasoning"].startswith("Rejected")
    # an honest "none" stays none; a bad category is an error
    assert not parse_evidence_reply({"coverage": "none", "evidence": "", "reasoning": "unrelated"}, code)["is_linked"]
    with pytest.raises(LLMResponseError):
        parse_evidence_reply({"coverage": "maybe"}, code)
