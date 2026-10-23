from agents.traceability_agent.candidates import LADDER, estimate_minutes, options_for, suggest_top_k


def test_small_projects_check_every_file():
    assert [suggest_top_k(n) for n in (1, 3, 5)] == [1, 3, 5]


def test_suggestion_is_capped_so_the_default_stays_affordable():
    values = [suggest_top_k(n) for n in (6, 30, 31, 392, 5000)]
    assert values == [10, 10, 20, 20, 20]
    assert all(v in LADDER for v in values)


def test_options_never_offer_more_candidates_than_files():
    assert options_for(3) == [1, 3]
    assert options_for(0) == [1]
    assert options_for(392) == list(LADDER)


def test_estimate_is_requirements_times_k_times_seconds():
    assert estimate_minutes(134, 10, 52) == 1161  # 1340 calls x 52 s, in minutes
