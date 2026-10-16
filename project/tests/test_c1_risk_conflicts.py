"""Unit tests for the risk heuristic, the candidate-conflict rules, file-name safety and the segmenter's optional source reference. No models needed."""
import pytest

from agents.requirement_agent.api import conflicts, ingest, risk
from agents.requirement_agent.api.errors import ApiError
from agents.requirement_agent.segmenter import segment_document


# ------------------------------------------------------------------------------------------------------------------------- risk
def test_risk_constants_are_the_documented_ones():
    assert (risk.AMBIGUOUS_POINTS, risk.WEAK_WORD_POINTS, risk.WEAK_WORD_MAX, risk.SECURITY_POINTS, risk.DUPLICATE_POINTS, risk.CONFLICT_POINTS) == (2, 1, 2, 1, 1, 1)
    assert (risk.HIGH_AT, risk.MEDIUM_AT, risk.LOW_AT) == (4, 2, 1)
    assert "unvalidated heuristic" in risk.__doc__.lower() or "unvalidated heuristic" in risk.__doc__


@pytest.mark.parametrize("args,score", [
    ((False, 0, False, False, False), 0),
    ((True, 0, False, False, False), 2),
    ((False, 1, False, False, False), 1),
    ((False, 2, False, False, False), 2),
    ((False, 5, False, False, False), 2),       # weak words are capped at +2
    ((False, 0, True, False, False), 1),
    ((False, 0, False, True, False), 1),
    ((False, 0, False, False, True), 1),
    ((True, 2, True, True, True), 7),           # everything at once
])
def test_risk_score(args, score):
    assert risk.risk_score(*args) == score


@pytest.mark.parametrize("score,level", [(0, "NONE"), (1, "LOW"), (2, "MEDIUM"), (3, "MEDIUM"), (4, "HIGH"), (7, "HIGH")])
def test_risk_level_boundaries(score, level):
    assert risk.risk_level(score) == level


def test_risk_assess_combines_both():
    assert risk.assess(True, 2, False, False, False) == (4, "HIGH")
    assert risk.assess(True, 0, False, False, False) == (2, "MEDIUM")
    assert risk.assess(False, 0, False, False, False) == (0, "NONE")


# ---------------------------------------------------------------------------------------------------------------------- conflicts
def test_numeric_limit_conflict_is_found():
    kind, reason = conflicts.detect("The system shall return search results within 2 seconds.",
                                    "The system shall return search results within 5 seconds.", 0.93)
    assert kind == "numeric_limit" and "2 vs 5" in reason and "seconds" in reason and "needs human decision" in reason


def test_prohibition_conflict_is_found():
    kind, reason = conflicts.detect("The system shall allow users to export reports as PDF.",
                                    "The system shall not allow users to export reports as PDF.", 0.92)
    assert kind == "prohibition" and "needs human decision" in reason
    assert conflicts.detect("The application must never store card numbers in the database.",
                            "The application must store card numbers in the database.", 0.9)[0] == "prohibition"


def test_no_conflict_below_the_similarity_floor():
    assert conflicts.detect("The system shall respond within 2 seconds.", "The system shall respond within 5 seconds.", 0.79) is None


def test_no_conflict_for_the_same_limit():
    assert conflicts.detect("The system shall respond within 2 seconds.", "The service shall respond within 2 seconds.", 0.95) is None


def test_no_conflict_for_different_units():
    assert conflicts.detect("The system shall respond within 2 seconds.", "The system shall be available 99 percent of the time.", 0.85) is None


def test_no_conflict_when_both_prohibit():
    assert conflicts.detect("The system shall not store passwords in clear text.", "The system must never store passwords in clear text.", 0.9) is None


def test_prohibition_needs_the_same_action():
    # one prohibits, the other requires something unrelated: similarity alone is not enough
    assert conflicts.detect("The system shall not send marketing email to customers.", "The administrator shall configure backup schedules nightly.", 0.82) is None


def test_find_conflicts_over_index_pairs():
    texts = ["Response within 2 seconds.", "Response within 5 seconds.", "Unrelated requirement."]
    out = conflicts.find_conflicts(texts, [(0, 1, 0.95), (0, 2, 0.4)])
    assert [(c["i"], c["j"], c["kind"]) for c in out] == [(0, 1, "numeric_limit")]


# ---------------------------------------------------------------------------------------------------------------- file name safety
@pytest.mark.parametrize("raw,expected", [
    ("../../etc/passwd.txt", "passwd.txt"),
    ("..\\..\\windows\\evil.docx", "evil.docx"),
    ("C:\\Users\\x\\spec.pdf", "spec.pdf"),
    ("my spec (v2).txt", "my spec (v2).txt"),
    ("bad<>:|name?.md", "bad____name_.md"),
    ("", "upload"),
    (None, "upload"),
    ("...", "upload"),
])
def test_safe_filename(raw, expected):
    assert ingest.safe_filename(raw) == expected


def test_safe_filename_strips_control_characters_and_limits_length():
    assert "\x00" not in ingest.safe_filename("a\x00b.txt")
    assert len(ingest.safe_filename("x" * 500 + ".txt")) <= 120


def test_extension_allow_list():
    assert ingest.check_extension("a.TXT") == ".txt"
    for bad in ("a.exe", "a.doc", "a.html", "noext", "a.txt.exe"):
        with pytest.raises(ApiError) as e:
            ingest.check_extension(bad)
        assert e.value.status == 400 and e.value.code == "unsupported_file_type"


# ---------------------------------------------------------------------------------------------------------- segmenter source reference
SAMPLE = "3. Functional requirements\n\n3.1 The system shall lock a user account after five failed login attempts.\n3.2 The system shall log every login attempt.\n"


def test_segmenter_rows_are_unchanged_without_a_line_map():
    rows, _, _ = segment_document("doc", SAMPLE, "txt")
    assert rows and all("page" not in r and "paragraph" not in r for r in rows)


def test_segmenter_rows_carry_page_and_paragraph_with_a_line_map():
    plain, _, _ = segment_document("doc", SAMPLE, "txt")
    mapped, _, _ = segment_document("doc", SAMPLE, "txt", {3: (7, 2), 4: (7, 3)})
    assert [{k: v for k, v in r.items() if k not in ("page", "paragraph")} for r in mapped] == plain
    assert [(r["page"], r["paragraph"]) for r in mapped] == [(7, 2), (7, 3)]


def test_text_extraction_page_and_paragraph_numbers():
    out = ingest.extract(b"First paragraph line one.\nline two.\n\nSecond paragraph.\n", ".txt")
    assert [m[1] for m in out["line_map"]][:5] == [1, 1, 1, 2, 2] and all(m[0] is None for m in out["line_map"])
