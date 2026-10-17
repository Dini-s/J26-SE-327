import numpy as np

from agents.traceability_agent.ranker import FEATURES, POOL, build_features, recall_at


def test_build_features_shape_and_pool():
    rng = np.random.default_rng(0)
    tf, em = rng.random((3, 8)), rng.random((3, 8))
    X, ri, ci = build_features(tf, em, ["add patient record"] * 3, [f"Code{i}.java" for i in range(8)], ["patient record add"] * 8, pool=4)
    assert X.shape == (12, len(FEATURES)) and len(ri) == len(ci) == 12
    assert POOL >= 4 and set(ri) == {0, 1, 2}


def test_recall_at_counts_true_links_in_top_k():
    scores = {0: [(0.9, 1), (0.5, 2), (0.1, 3)]}
    assert recall_at(scores, {0: {1, 3}}, 1) == 0.5
    assert recall_at(scores, {0: {1, 3}}, 3) == 1.0
