from agents.quality_agent import (
    config,
)

from agents.quality_agent.adapters.junit_parser import (
    JUnitParser,
)

from agents.quality_agent.adapters.surefire_parser import (
    SurefireParser,
)

from agents.quality_agent.services.normalizer import (
    EvidenceNormalizer,
)


def test_petclinic_source_execution_mapping():

    artifacts = (
        JUnitParser()
        .parse_directory(
            config.JUNIT_ROOT
        )
    )

    executions = (
        SurefireParser()
        .parse_directory(
            config.SUREFIRE_ROOT
        )
    )

    assert len(artifacts) == 81
    assert len(executions) == 79

    evidence = (
        EvidenceNormalizer()
        .normalize(
            manual_path=(
                config
                .MANUAL_TESTS_PATH
            ),

            junit_root=(
                config.JUNIT_ROOT
            ),

            surefire_root=(
                config.SUREFIRE_ROOT
            ),

            performance_path=(
                config
                .PERFORMANCE_PATH
            ),
        )
    )

    automated = [
        item
        for item
        in evidence
        if (
            item.evidence_type
            == "AUTOMATED_TEST"
        )
    ]

    mapped = [
        item
        for item
        in automated
        if (
            item.execution_status
            is not None
        )
    ]

    assert len(automated) == 81
    assert len(mapped) == 79