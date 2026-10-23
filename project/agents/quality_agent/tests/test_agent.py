from agents.quality_agent.agent import (
    QualityAgent,
)


def test_overview_uses_real_dataset():
    overview = QualityAgent().overview()

    assert overview.requirements == 30

    assert (
        overview.acceptance_criteria
        == 90
    )

    assert (
        overview
        .functional_requirements
        == 20
    )

    assert (
        overview
        .non_functional_requirements
        == 10
    )


def test_requirement_processing_produces_rvus():
    result = (
        QualityAgent()
        .process_requirements()
    )

    assert len(
        result["requirements"]
    ) == 30

    assert len(
        result["rvus"]
    ) > 0

    assert (
        len(result["rvus"])
        == len(
            result["profiles"]
        )
    )