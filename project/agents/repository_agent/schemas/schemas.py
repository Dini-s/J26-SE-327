from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    service: str
    version: str


class RepositorySummary(BaseModel):
    repository: str
    total_packages: int = Field(ge=0)
    semantic_packages: int = Field(ge=0)
    graph_packages: int = Field(ge=0)
    evolution_packages: int = Field(ge=0)
    high_risk_packages: int = Field(ge=0)
    medium_risk_packages: int = Field(ge=0)
    low_risk_packages: int = Field(ge=0)


class PackageRiskResponse(BaseModel):
    repository: str
    package_path: str
    risk_score: float
    risk_level: Literal["Low", "Medium", "High"]
    evidence: list[str] = Field(default_factory=list)
    semantic_available: bool = False
    graph_available: bool = False
    evolution_available: bool = False


class FeatureAvailabilityResponse(BaseModel):
    repository: str
    package_path: str
    semantic_available: bool
    graph_available: bool
    evolution_available: bool
    available_feature_groups: int = Field(ge=0, le=3)
