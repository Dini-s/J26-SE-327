"""Precision / recall by threshold."""

from agents.traceability_agent.pr_curve import pr_curve
from shared.schemas.traceability import TraceabilityLink


def link(r, c, conf, status="verified"):
    return TraceabilityLink(source_id=r, target_id=c, link_type="requirement_to_code", confidence=conf, status=status, justification="x")


GOLD = [("R1", "A"), ("R1", "B"), ("R2", "C"), ("R3", "D")]  # R3 was never processed
TRACES = [link("R1", "A", 0.9), link("R1", "X", 0.8), link("R2", "C", 0.8), link("R2", "Y", 0.8), link("R2", "Z", 0.3, "decayed")]


def test_precision_rises_and_recall_falls_with_the_threshold():
    c = pr_curve(TRACES, GOLD)
    low, high = c["rows"][0], c["rows"][-1]
    assert (low["threshold"], low["kept"], low["correct"]) == (0.8, 4, 2) and low["precision"] == 0.5 and low["recall"] == round(2 / 3, 3)
    assert (high["threshold"], high["kept"], high["correct"]) == (0.9, 1, 1) and high["precision"] == 1.0 and high["recall"] == round(1 / 3, 3)
    assert c["gold_links"] == 3  # R3's true link does not count: R3 has no link yet


def test_operating_point_is_the_loosest_threshold_that_meets_the_target():
    c = pr_curve(TRACES, GOLD, target_precision=0.85)
    assert c["operating_point"]["threshold"] == 0.9
    assert pr_curve(TRACES, GOLD, target_precision=0.4)["operating_point"]["threshold"] == 0.8
    assert pr_curve(TRACES, [("R9", "Q")], target_precision=0.9)["operating_point"] is None


def test_requirements_added_after_the_dataset_stay_out_of_the_numbers():
    # NEW-1 was typed into the dashboard later: it has no answer key, so its links must not count as wrong
    traces = TRACES + [link("NEW-1", "Q", 0.9), link("NEW-1", "W", 0.9)]
    with_extra = pr_curve(traces, GOLD)
    clean = pr_curve(traces, GOLD, known_requirements={"R1", "R2", "R3"})
    assert with_extra["rows"][-1]["kept"] == 3 and with_extra["processed_requirements"] == 3
    assert clean["rows"][-1]["kept"] == 1 and clean["processed_requirements"] == 2
    assert clean["rows"] == pr_curve(TRACES, GOLD)["rows"]
