from __future__ import annotations

from pydantic import (
    TypeAdapter,
)

from agents.quality_agent import (
    config,
)

from agents.quality_agent.schemas import (
    OverviewStats,
    RequirementValidationUnit,
    ValidationEvidence,
)

from agents.quality_agent.services.dataset_service import (
    DatasetService,
)

from agents.quality_agent.services.evidence_profile import (
    EvidenceProfileGenerator,
)

from agents.quality_agent.services.normalizer import (
    EvidenceNormalizer,
)

from agents.quality_agent.services.retrieval import (
    EvidenceRetrievalService,
)

from agents.quality_agent.services.rvu_extractor import (
    RVUExtractor,
)


class QualityAgent:
    def __init__(
        self,
    ):
        config.ensure_directories()

        self.dataset_service = (
            DatasetService()
        )

        self.rvu_extractor = (
            RVUExtractor()
        )

        self.profile_generator = (
            EvidenceProfileGenerator()
        )

        self.normalizer = (
            EvidenceNormalizer()
        )

        self.retrieval_service = (
            EvidenceRetrievalService(
                config.EMBEDDING_MODEL
            )
        )

    def process_requirements(
        self,
    ):
        requirements = (
            self.dataset_service
            .load_requirements(
                config
                .REQUIREMENTS_PATH
            )
        )

        rvus = (
            self.rvu_extractor
            .extract(
                requirements
            )
        )

        profiles = (
            self.profile_generator
            .generate(
                requirements,
                rvus,
            )
        )

        self.dataset_service.save_json(
            config.RVUS_PATH,
            [
                item.model_dump(
                    mode="json"
                )
                for item
                in rvus
            ],
        )

        self.dataset_service.save_json(
            config
            .EVIDENCE_PROFILES_PATH,
            [
                item.model_dump(
                    mode="json"
                )
                for item
                in profiles
            ],
        )

        return {
            "requirements":
            requirements,

            "rvus":
            rvus,

            "profiles":
            profiles,
        }

    def normalize_evidence(
        self,
    ) -> list[
        ValidationEvidence
    ]:

        evidence = (
            self.normalizer
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

        self.dataset_service.save_json(
            config
            .NORMALIZED_EVIDENCE_PATH,
            [
                item.model_dump(
                    mode="json"
                )
                for item
                in evidence
            ],
        )

        return evidence

    def retrieve(
        self,
        rvu_id: str,
        method: str,
        top_k: int | None = None,
    ):

        if not (
            config
            .RVUS_PATH
            .exists()
        ):
            self.process_requirements()

        if not (
            config
            .NORMALIZED_EVIDENCE_PATH
            .exists()
        ):
            self.normalize_evidence()

        rvus = TypeAdapter(
            list[
                RequirementValidationUnit
            ]
        ).validate_python(
            self.dataset_service
            .load_json(
                config.RVUS_PATH
            )
        )

        target_rvu = next(
            (
                item
                for item
                in rvus
                if (
                    item.rvu_id
                    == rvu_id
                )
            ),
            None,
        )

        if target_rvu is None:
            raise ValueError(
                f"RVU not found: "
                f"{rvu_id}"
            )

        evidence = TypeAdapter(
            list[
                ValidationEvidence
            ]
        ).validate_python(
            self.dataset_service
            .load_json(
                config
                .NORMALIZED_EVIDENCE_PATH
            )
        )

        matches = (
            self.retrieval_service
            .retrieve(
                target_rvu,
                evidence,
                method,
                (
                    top_k
                    or config.TOP_K
                ),
            )
        )

        output_path = (
            config.RETRIEVAL_ROOT
            / (
                f"{rvu_id}_"
                f"{method.lower()}.json"
            )
        )

        self.dataset_service.save_json(
            output_path,
            [
                item.model_dump(
                    mode="json"
                )
                for item
                in matches
            ],
        )

        return matches

    def overview(
        self,
    ) -> OverviewStats:

        requirements = (
            self.dataset_service
            .load_requirements(
                config
                .REQUIREMENTS_PATH
            )
        )

        acceptance_criteria = sum(
            len(
                item
                .acceptance_criteria
            )
            for item
            in requirements
        )

        rvus = (
            self._load_if_exists(
                config.RVUS_PATH
            )
        )

        profiles = (
            self._load_if_exists(
                config
                .EVIDENCE_PROFILES_PATH
            )
        )

        evidence = (
            self._load_if_exists(
                config
                .NORMALIZED_EVIDENCE_PATH
            )
        )

        return OverviewStats(
            requirements=(
                len(requirements)
            ),
            acceptance_criteria=(
                acceptance_criteria
            ),
            functional_requirements=(
                sum(
                    1
                    for item
                    in requirements
                    if (
                        item.type
                        == "FUNCTIONAL"
                    )
                )
            ),
            non_functional_requirements=(
                sum(
                    1
                    for item
                    in requirements
                    if (
                        item.type
                        == "NON_FUNCTIONAL"
                    )
                )
            ),
            rvus=len(
                rvus
            ),
            expected_profiles=(
                len(profiles)
            ),
            evidence_items=(
                len(evidence)
            ),
            automated_tests=(
                sum(
                    1
                    for item
                    in evidence
                    if (
                        item.get(
                            "evidence_type"
                        )
                        == "AUTOMATED_TEST"
                    )
                )
            ),
            manual_tests=(
                sum(
                    1
                    for item
                    in evidence
                    if (
                        item.get(
                            "evidence_type"
                        )
                        == "MANUAL_TEST"
                    )
                )
            ),
            performance_evidence=(
                sum(
                    1
                    for item
                    in evidence
                    if (
                        item.get(
                            "evidence_type"
                        )
                        == "PERFORMANCE_EVIDENCE"
                    )
                )
            ),
        )

    def _load_if_exists(
        self,
        path,
    ):
        if not path.exists():
            return []

        return (
            self.dataset_service
            .load_json(
                path
            )
        )