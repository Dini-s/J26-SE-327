"""Fingerprint of meaning-bearing text and the differences it reports."""

from agents.traceability_agent.semdiff import changes, fingerprint, fingerprint_pair, pair_changes
from shared.schemas.traceability import Artifact

CODE = "if (retries == 3 && enabled) { return true; }  // issue 42"


def test_numbers_and_flags_are_counted_but_comments_are_ignored():
    fp = fingerprint(CODE)
    assert fp["numbers"] == ["3"] and fp["true"] == 1 and fp["operators"] == {"==": 1, "&&": 1}


def test_changed_number_is_reported_with_both_values():
    d = changes(fingerprint(CODE), fingerprint(CODE.replace("== 3", "== 300")))
    assert d == ["numbers changed: ['3'] -> ['300']"]


def test_negated_condition_and_flipped_boolean_are_reported():
    new = "if (retries != 3 && enabled) { return false; }"
    d = changes(fingerprint(CODE), fingerprint(new))
    assert any("negations" in x for x in d) and any("'true'" in x for x in d) and any("'false'" in x for x in d)
    assert any("operators" in x for x in d)


def test_shall_becomes_shall_not():
    d = changes(fingerprint("The unit shall retry three times."), fingerprint("The unit shall not retry three times."))
    assert d == ["negations changed: 0 -> 1"]  # "three" is still 3, so the number is unchanged


def test_harmless_edits_report_nothing():
    base = fingerprint("Retries 3 times and logs the failure.")
    assert changes(base, fingerprint("Retries 3 times and logs the failure.\n(Reformatted; no functional change.)")) == []
    assert changes(fingerprint(CODE), fingerprint(CODE.replace("issue 42", "issue 99"))) == []  # comment only
    assert changes(fingerprint(CODE), fingerprint("  " + CODE + "\n\n")) == []


def test_pair_changes_needs_a_stored_fingerprint():
    req = Artifact(id="R", type="requirement", text="Retry 3 times.")
    tgt = Artifact(id="C", type="code", text="retries = 3")
    stored = fingerprint_pair(req, tgt)
    assert pair_changes(stored, req, tgt) == []
    edited = tgt.model_copy(update={"text": "retries = 300"})
    assert pair_changes(stored, req, edited) == ["code numbers changed: ['3'] -> ['300']"]
    assert pair_changes(None, req, edited) == [] and pair_changes("not json", req, edited) == []
