import pytest

from agents.quality_agent.services.evaluation import (
    EvaluationService,
)


def test_set_f1_exact_match():
    result = (
        EvaluationService
        ._set_f1(
            [
                "RVU-001",
                "RVU-002",
                "RVU-003",
            ],
            [
                "RVU-001",
                "RVU-002",
                "RVU-003",
            ],
        )
    )

    assert result == pytest.approx(
        1.0,
        abs=1e-12,
    )


def test_classification_metrics():
    result = (
        EvaluationService
        ._classification_metrics(
            [
                "ADEQUATE",
                "PARTIAL",
                "INADEQUATE",
            ],
            [
                "ADEQUATE",
                "ADEQUATE",
                "INADEQUATE",
            ],
            (
                "ADEQUATE",
                "PARTIAL",
                "INADEQUATE",
            ),
        )
    )

    assert (
        result["accuracy"]
        == pytest.approx(
            0.6667,
            abs=1e-4,
        )
    )

    assert (
        0.0
        <= result["macro_f1"]
        <= 1.0
    )


def test_spearman_perfect_order():
    result = (
        EvaluationService
        ._spearman(
            [
                1,
                2,
                3,
                4,
            ],
            [
                10,
                20,
                30,
                40,
            ],
        )
    )

    assert result == pytest.approx(
        1.0,
        abs=1e-12,
    )


def test_cohen_kappa_perfect_agreement():
    result = (
        EvaluationService
        ._cohen_kappa(
            [
                "A",
                "B",
                "A",
                "C",
            ],
            [
                "A",
                "B",
                "A",
                "C",
            ],
        )
    )

    assert result == pytest.approx(
        1.0,
        abs=1e-12,
    )


def test_weighted_rves_score():
    factors = {
        "R_relevance": 0.8,
        "A_adequacy": 0.6,
        "C_completeness": 0.8,
        "E_execution": 0.6,
    }

    weights = {
        "R_relevance": 0.25,
        "A_adequacy": 0.25,
        "C_completeness": 0.25,
        "E_execution": 0.25,
    }

    result = (
        EvaluationService
        ._weighted_score(
            factors,
            weights,
        )
    )

    assert result == pytest.approx(
        0.7,
        abs=1e-12,
    )