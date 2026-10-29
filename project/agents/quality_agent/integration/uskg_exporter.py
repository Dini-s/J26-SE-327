from __future__ import annotations

from typing import Any

from agents.quality_agent import (
    config,
)

from agents.quality_agent.integration.contracts import (
    USKG_OWNERSHIP,
)

from agents.quality_agent.services.dataset_service import (
    DatasetService,
)


class C3USKGExporter:
    def __init__(
        self,
    ):
        self.dataset_service = (
            DatasetService()
        )

        self.nodes: dict[
            str,
            dict[str, Any],
        ] = {}

        self.relationships: list[
            dict[str, Any]
        ] = []

        self._relationship_keys: set[
            tuple
        ] = set()

    def build(
        self,
    ) -> dict[str, Any]:
        self.nodes = {}
        self.relationships = []
        self._relationship_keys = set()

        requirements = (
            self.dataset_service
            .load_requirements(
                config.REQUIREMENTS_PATH
            )
        )

        rvus = self._load(
            config.RVUS_PATH
        )

        profiles = self._load(
            config
            .EVIDENCE_PROFILES_PATH
        )

        evidence = self._load(
            config
            .NORMALIZED_EVIDENCE_PATH
        )

        assessments = self._load(
            config
            .ADEQUACY_ASSESSMENTS_PATH
        )

        adequacy = self._load(
            config
            .RVU_ADEQUACY_PATH
        )

        validations = self._load(
            config
            .RVU_VALIDATION_PATH
        )

        intelligence = self._load(
            config
            .REQUIREMENT_INTELLIGENCE_PATH
        )

        gaps = self._load(
            config.GAPS_PATH
        )

        recommendations = (
            self._load(
                config
                .RECOMMENDATIONS_PATH
            )
        )

        revalidation = self._load(
            config
            .REVALIDATION_RESULTS_PATH
        )

        for requirement in (
            requirements
        ):
            self._add_node(
                requirement.requirement_id,
                "Requirement",
                "C1",
                {
                    "title":
                        requirement.title,

                    "text":
                        requirement.text,

                    "type":
                        requirement.type,

                    "subtype":
                        requirement.subtype,

                    "risk":
                        requirement.risk,

                    "version":
                        requirement.version,

                    "source":
                        requirement.source,

                    "reference_only":
                        True,
                },
            )

            for ac in (
                requirement
                .acceptance_criteria
            ):
                self._add_node(
                    ac.ac_id,
                    "AcceptanceCriterion",
                    "C1",
                    {
                        "text":
                            ac.text,

                        "reference_only":
                            True,
                    },
                )

                self._add_edge(
                    requirement
                    .requirement_id,

                    ac.ac_id,

                    "HAS_CRITERION",
                )

        for rvu in rvus:
            rvu_id = rvu[
                "rvu_id"
            ]

            self._add_node(
                rvu_id,
                "RequirementValidationUnit",
                "C3",
                rvu,
            )

            self._add_edge(
                rvu[
                    "requirement_id"
                ],

                rvu_id,

                "HAS_RVU",
            )

            self._add_edge(
                rvu["ac_id"],
                rvu_id,
                "DERIVED_FROM_AC",
            )

        for profile in profiles:
            profile_id = (
                profile[
                    "profile_id"
                ]
            )

            self._add_node(
                profile_id,
                "ExpectedEvidenceProfile",
                "C3",
                profile,
            )

            self._add_edge(
                profile[
                    "rvu_id"
                ],

                profile_id,

                "EXPECTS_EVIDENCE",
            )

        for item in evidence:
            self._add_node(
                item[
                    "evidence_id"
                ],

                "ValidationEvidence",
                "C3",
                item,
            )

        for assessment in (
            assessments
        ):
            self._add_edge(
                assessment[
                    "rvu_id"
                ],

                assessment[
                    "evidence_id"
                ],

                "MATCHED_BY",

                {
                    "profile_id":
                        assessment[
                            "profile_id"
                        ],

                    "relevance_status":
                        assessment[
                            "relevance_status"
                        ],

                    "relevance_score":
                        assessment[
                            "relevance_score"
                        ],

                    "adequacy_status":
                        assessment[
                            "adequacy_status"
                        ],

                    "adequacy_score":
                        assessment[
                            "adequacy_score"
                        ],

                    "retrieval_rank":
                        assessment.get(
                            "retrieval_rank"
                        ),
                },
            )

        for item in adequacy:
            node_id = (
                "ADEQ::"
                + item["rvu_id"]
            )

            self._add_node(
                node_id,
                "RVUAdequacySummary",
                "C3",
                item,
            )

            self._add_edge(
                item["rvu_id"],
                node_id,
                "SUMMARIZED_AS",
            )

        for item in validations:
            node_id = (
                "VALID::"
                + item["rvu_id"]
            )

            self._add_node(
                node_id,
                "RVUValidationResult",
                "C3",
                item,
            )

            self._add_edge(
                item["rvu_id"],
                node_id,
                "HAS_VALIDATION",
            )

        for item in intelligence:
            node_id = (
                "REQINT::"
                + item[
                    "requirement_id"
                ]
            )

            self._add_node(
                node_id,
                "RequirementIntelligence",
                "C3",
                item,
            )

            self._add_edge(
                item[
                    "requirement_id"
                ],

                node_id,

                "SUMMARIZED_AS",
            )

        for gap in gaps:
            self._add_node(
                gap["gap_id"],
                "QAGap",
                "C3",
                gap,
            )

            self._add_edge(
                gap["rvu_id"],
                gap["gap_id"],
                "HAS_GAP",
            )

        for item in recommendations:
            self._add_node(
                item[
                    "recommendation_id"
                ],

                "Recommendation",
                "C3",
                item,
            )

            self._add_edge(
                item["gap_id"],

                item[
                    "recommendation_id"
                ],

                "RECOMMENDS",
            )

        for report in revalidation:
            change_id = (
                report[
                    "change_id"
                ]
            )

            self._add_node(
                change_id,
                "RevalidationCase",
                "C3",
                report,
            )

            self._add_edge(
                report[
                    "requirement_id"
                ],

                change_id,

                "IMPACTED_BY",
            )

            for rvu_id in (
                report.get(
                    "affected_rvu_ids",
                    [],
                )
            ):
                if (
                    rvu_id
                    in self.nodes
                ):
                    self._add_edge(
                        change_id,
                        rvu_id,
                        "AFFECTS_RVU",
                    )

        return {
            "schema_version":
                "1.0",

            "component":
                "C3",

            "name":
                (
                    "Quality & Testing "
                    "Intelligence"
                ),

            "ownership":
                USKG_OWNERSHIP,

            "nodes":
                sorted(
                    self.nodes.values(),
                    key=lambda item:
                    item["id"],
                ),

            "relationships":
                sorted(
                    self.relationships,
                    key=lambda item: (
                        item["type"],
                        item["source"],
                        item["target"],
                    ),
                ),

            "summary": {
                "node_count":
                    len(
                        self.nodes
                    ),

                "relationship_count":
                    len(
                        self.relationships
                    ),
            },
        }

    def export(
        self,
    ) -> dict[str, Any]:
        graph = self.build()

        self.dataset_service.save_json(
            config.USKG_EXPORT_PATH,
            graph,
        )

        return graph

    def _load(
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

    def _add_node(
        self,
        node_id: str,
        label: str,
        owner: str,
        properties: dict[
            str,
            Any,
        ],
    ) -> None:
        self.nodes[
            node_id
        ] = {
            "id":
                node_id,

            "label":
                label,

            "owner":
                owner,

            "properties":
                properties,
        }

    def _add_edge(
        self,
        source: str,
        target: str,
        relationship_type: str,
        properties: dict[
            str,
            Any,
        ] | None = None,
    ) -> None:
        key = (
            source,
            target,
            relationship_type,
        )

        if key in (
            self._relationship_keys
        ):
            return

        self._relationship_keys.add(
            key
        )

        self.relationships.append(
            {
                "source":
                    source,

                "target":
                    target,

                "type":
                    relationship_type,

                "properties":
                    properties
                    or {},
            }
        )