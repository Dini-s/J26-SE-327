"""Synthetic-data experiment: metrics only (training and the LLM are not run in tests)."""

import numpy as np

from agents.traceability_agent.synthetic import bootstrap_diff, macro_bootstrap_diff, macro_recall, per_requirement_hits, pooled_recall
from shared.schemas.traceability import Artifact


def art(i, t="requirement"):
    return Artifact(id=i, type=t, text=i)


def test_hits_count_true_links_in_top_k_per_requirement():
    reqs, targets = [art("R1"), art("R2"), art("R3")], [art("A", "code"), art("B", "code"), art("C", "code")]
    scores = np.array([[0.9, 0.5, 0.1], [0.1, 0.2, 0.9], [0.3, 0.2, 0.1]])
    gold = {("R1", "A"), ("R1", "C"), ("R2", "A")}  # R3 has no true link: ignored
    rows = per_requirement_hits(scores, reqs, targets, gold, [1, 2])
    assert rows[1] == [(1, 2), (0, 1)] and rows[2] == [(1, 2), (0, 1)]
    assert pooled_recall(rows[1]) == 1 / 3


def test_bootstrap_difference_is_zero_for_identical_results_and_positive_for_better():
    same = [(1, 2), (0, 1), (2, 2)] * 5
    d, lo, hi = bootstrap_diff(same, same, n=200)
    assert d == 0 and lo == 0 and hi == 0
    better = [(2, 2), (1, 1), (2, 2)] * 5
    d, lo, hi = bootstrap_diff(better, same, n=200)
    assert d > 0 and lo >= 0


def test_macro_recall_weights_datasets_equally():
    big, small = [(1, 10)] * 10, [(1, 1)]
    assert macro_recall({"big": big, "small": small}) == (0.1 + 1.0) / 2
    d, lo, hi = macro_bootstrap_diff({"a": [(2, 2)] * 5, "b": [(1, 1)] * 5}, {"a": [(1, 2)] * 5, "b": [(0, 1)] * 5}, n=100)
    assert d == 0.75 and lo == 0.75 == hi


def test_hard_negative_given_as_a_string_is_one_text_not_its_letters():
    """Regression: the batch builder once iterated a string, producing thousands of one-letter texts."""
    import inspect

    from agents.traceability_agent import synthetic

    src = inspect.getsource(synthetic._train)
    assert "isinstance(x[2], str)" in src
