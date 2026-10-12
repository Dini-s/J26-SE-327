"""Tests for the evaluation metrics (pure logic, no agent or I/O)."""

import pytest

from agents.traceability_agent.evaluate import compute_metrics


def test_compute_metrics_perfect():
    gold = [("R1", "C1", True), ("R1", "C2", False)]
    m = compute_metrics({("R1", "C1")}, gold)
    assert (m["precision"], m["recall"], m["f1"]) == (1.0, 1.0, 1.0)


def test_compute_metrics_mixed():
    gold = [("R1", "C1", True), ("R1", "C2", True), ("R1", "C3", False)]
    m = compute_metrics({("R1", "C1"), ("R1", "C3")}, gold)  # 1 TP, 1 FP, 1 FN
    assert (m["tp"], m["fp"], m["fn"]) == (1, 1, 1)
    assert m["precision"] == pytest.approx(0.5)
    assert m["recall"] == pytest.approx(0.5)
    assert m["f1"] == pytest.approx(0.5)


def test_compute_metrics_ignores_unlabelled_predictions():
    m = compute_metrics({("R9", "C9")}, [("R1", "C1", True)])
    assert m["ignored"] == 1
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["f1"] == 0.0


def test_compute_metrics_no_predictions_no_division_error():
    m = compute_metrics(set(), [("R1", "C1", True)])
    assert m["precision"] == 0.0 and m["recall"] == 0.0
