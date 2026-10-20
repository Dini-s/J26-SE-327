from functools import lru_cache

import pandas as pd

from agents.repository_agent.config import (
    ARCHITECTURE_RISK_FILE,
    FEATURE_AVAILABILITY_FILE,
    HRIM_FEATURES_FILE,
)
from agents.repository_agent.schemas.schemas import (
    FeatureAvailabilityResponse,
    PackageRiskResponse,
    RepositorySummary,
)


class RepositoryIntelligenceAgent:
    """Loads HRIM data and returns explainable package-risk information."""

    def __init__(self):
        self.reload_data()

    def reload_data(self):
        required = {
            "risk": ARCHITECTURE_RISK_FILE,
            "availability": FEATURE_AVAILABILITY_FILE,
            "features": HRIM_FEATURES_FILE,
        }

        missing = [str(path) for path in required.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Required repository-agent data files are missing: "
                + ", ".join(missing)
            )

        self.risk_df = pd.read_csv(required["risk"])
        self.availability_df = pd.read_csv(required["availability"])
        self.features_df = pd.read_csv(required["features"])

        for name, frame in (
            ("risk", self.risk_df),
            ("availability", self.availability_df),
            ("features", self.features_df),
        ):
            expected = {"repository", "package_path"}
            if not expected.issubset(frame.columns):
                raise ValueError(
                    f"{name} dataset must contain {sorted(expected)}"
                )

        self.risk_df = self.risk_df.drop_duplicates(
            subset=["repository", "package_path"]
        )
        self.availability_df = self.availability_df.drop_duplicates(
            subset=["repository", "package_path"]
        )
        self.features_df = self.features_df.drop_duplicates(
            subset=["repository", "package_path"]
        )

    @staticmethod
    def _boolean(value):
        return False if pd.isna(value) else bool(value)

    def list_repositories(self):
        return sorted(
            set(self.features_df["repository"].dropna().astype(str))
        )

    def get_repository_summary(self, repository: str):
        features = self.features_df[
            self.features_df["repository"] == repository
        ]
        if features.empty:
            return None

        availability = self.availability_df[
            self.availability_df["repository"] == repository
        ]
        risk = self.risk_df[self.risk_df["repository"] == repository]

        counts = risk["risk_level"].value_counts().to_dict()

        return RepositorySummary(
            repository=repository,
            total_packages=int(features["package_path"].nunique()),
            semantic_packages=int(
                availability.loc[
                    availability["semantic_available"].fillna(False),
                    "package_path",
                ].nunique()
            ),
            graph_packages=int(
                availability.loc[
                    availability["graph_available"].fillna(False),
                    "package_path",
                ].nunique()
            ),
            evolution_packages=int(
                availability.loc[
                    availability["evolution_available"].fillna(False),
                    "package_path",
                ].nunique()
            ),
            high_risk_packages=int(counts.get("High", 0)),
            medium_risk_packages=int(counts.get("Medium", 0)),
            low_risk_packages=int(counts.get("Low", 0)),
        )

    def get_feature_availability(
        self, repository: str, package_path: str
    ):
        rows = self.availability_df[
            (self.availability_df["repository"] == repository)
            & (self.availability_df["package_path"] == package_path)
        ]
        if rows.empty:
            return None

        row = rows.iloc[0]
        return FeatureAvailabilityResponse(
            repository=repository,
            package_path=package_path,
            semantic_available=self._boolean(row["semantic_available"]),
            graph_available=self._boolean(row["graph_available"]),
            evolution_available=self._boolean(row["evolution_available"]),
            available_feature_groups=int(row["available_feature_groups"]),
        )

    def get_package_risk(self, repository: str, package_path: str):
        rows = self.risk_df[
            (self.risk_df["repository"] == repository)
            & (self.risk_df["package_path"] == package_path)
        ]
        if rows.empty:
            return None

        row = rows.iloc[0]
        availability = self.get_feature_availability(repository, package_path)
        feature_row = self.features_df[
            (self.features_df["repository"] == repository)
            & (self.features_df["package_path"] == package_path)
        ]

        evidence = [
            f"Total coupling: {row['total_coupling']}",
            f"Fan-in: {row['fan_in']}",
            f"Fan-out: {row['fan_out']}",
            f"Instability: {row['instability']}",
        ]

        if not feature_row.empty:
            features = feature_row.iloc[0]
            if "commit_count" in features.index:
                value = features["commit_count"]
                evidence.append(
                    "Commit count: unavailable"
                    if pd.isna(value)
                    else f"Commit count: {value}"
                )
            if "total_churn" in features.index:
                value = features["total_churn"]
                evidence.append(
                    "Total churn: unavailable"
                    if pd.isna(value)
                    else f"Total churn: {value}"
                )

        return PackageRiskResponse(
            repository=repository,
            package_path=package_path,
            risk_score=float(row["risk_score"]),
            risk_level=str(row["risk_level"]),
            evidence=evidence,
            semantic_available=(
                availability.semantic_available if availability else False
            ),
            graph_available=(
                availability.graph_available if availability else False
            ),
            evolution_available=(
                availability.evolution_available if availability else False
            ),
        )


@lru_cache(maxsize=1)
def get_agent():
    """Create one reusable agent instance."""
    return RepositoryIntelligenceAgent()
