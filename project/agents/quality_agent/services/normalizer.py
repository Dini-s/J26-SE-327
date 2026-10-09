from pathlib import Path

from agents.quality_agent.adapters.junit_parser import (
    JUnitParser,
)
from agents.quality_agent.adapters.manual_test_parser import (
    ManualTestParser,
)
from agents.quality_agent.adapters.performance_parser import (
    PerformanceEvidenceParser,
)
from agents.quality_agent.adapters.surefire_parser import (
    SurefireParser,
)

from agents.quality_agent.schemas import (
    ExecutionResult,
    TestArtifact,
    ValidationEvidence,
)


class EvidenceNormalizer:
    def __init__(
        self,
    ):
        self.manual_parser = (
            ManualTestParser()
        )

        self.junit_parser = (
            JUnitParser()
        )

        self.surefire_parser = (
            SurefireParser()
        )

        self.performance_parser = (
            PerformanceEvidenceParser()
        )

    def normalize(
        self,
        manual_path: Path,
        junit_root: Path,
        surefire_root: Path,
        performance_path: Path,
    ) -> list[ValidationEvidence]:

        manual_evidence = (
            self.manual_parser.parse(
                manual_path
            )
        )

        test_artifacts = (
            self.junit_parser
            .parse_directory(
                junit_root
            )
        )

        execution_results = (
            self.surefire_parser
            .parse_directory(
                surefire_root
            )
        )

        automated_evidence = (
            self
            ._normalize_test_artifacts(
                test_artifacts
            )
        )

        performance_evidence = (
            self.performance_parser
            .parse(
                performance_path
            )
        )

        self._attach_execution_results(
            automated_evidence,
            execution_results,
        )

        return (
            automated_evidence
            + manual_evidence
            + performance_evidence
        )

    @staticmethod
    def _normalize_test_artifacts(
        artifacts: list[
            TestArtifact
        ],
    ) -> list[
        ValidationEvidence
    ]:

        return [
            ValidationEvidence(
                evidence_id=(
                    artifact
                    .artifact_id
                ),
                evidence_type=(
                    artifact
                    .artifact_type
                ),
                title=(
                    artifact.title
                ),
                description=(
                    artifact.description
                ),
                assertions=(
                    artifact.assertions
                ),
                class_name=(
                    artifact.class_name
                ),
                method_name=(
                    artifact.method_name
                ),
                source_path=(
                    artifact.source_path
                ),
                source_tool=(
                    artifact.source_tool
                ),
                source_version=(
                    artifact
                    .source_version
                ),
                raw_reference=(
                    artifact
                    .raw_reference
                ),
                synthetic=False,
                metadata={
                    "annotations":
                    artifact.annotations,
                    "normalization_source":
                    "TestArtifact",
                },
            )
            for artifact
            in artifacts
        ]

    @staticmethod
    def _attach_execution_results(
        automated_evidence: list[
            ValidationEvidence
        ],
        execution_results: list[
            ExecutionResult
        ],
    ) -> None:

        execution_index: dict[
            tuple[str, str],
            ExecutionResult,
        ] = {}

        for result in (
            execution_results
        ):
            if (
                not result.class_name
                or not result.method_name
            ):
                continue

            key = (
                result
                .class_name
                .lower(),
                result
                .method_name
                .lower(),
            )

            execution_index[
                key
            ] = result

        for evidence in (
            automated_evidence
        ):
            if (
                not evidence.class_name
                or not evidence.method_name
            ):
                evidence.metadata[
                    "execution_mapping"
                ] = "UNRESOLVED"

                continue

            key = (
                evidence
                .class_name
                .lower(),
                evidence
                .method_name
                .lower(),
            )

            execution = (
                execution_index.get(
                    key
                )
            )

            if execution is None:
                evidence.metadata[
                    "execution_mapping"
                ] = "UNRESOLVED"

                continue

            evidence.execution_status = (
                execution.status
            )

            evidence.execution_duration_ms = (
                execution.duration_ms
            )

            evidence.execution_run_id = (
                execution.run_id
            )

            evidence.metadata[
                "execution_mapping"
            ] = "MATCHED"

            evidence.metadata[
                "surefire_source_path"
            ] = execution.source_path