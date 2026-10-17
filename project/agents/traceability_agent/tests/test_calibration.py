import numpy as np

from agents.traceability_agent.calibration import abstain, cross_validated, ece, raw_score


def test_raw_score_zero_when_not_linked():
    assert raw_score(False, 0.9) == 0.0 and raw_score(True, 0.8) == 0.8


def test_ece_perfect_and_overconfident():
    assert ece(np.array([1.0, 0.0]), np.array([1, 0])) == 0.0
    assert ece(np.array([0.9, 0.9]), np.array([1, 0])) > 0.3


def test_abstain_bands():
    assert [abstain(p, 0.3, 0.7) for p in (0.9, 0.5, 0.1)] == ["accept", "review", "reject"]


def test_cross_validated_fixes_overconfidence():
    rows = [{"score": 0.9, "label": int(i % 4 == 0)} for i in range(40)] + [{"score": 0.0, "label": 0} for i in range(40)]
    s, cal, y = cross_validated(rows)
    assert ece(cal, y) < ece(s, y)
