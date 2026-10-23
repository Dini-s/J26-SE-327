import re
from pathlib import Path
from urllib.parse import urlparse
import httpx

from fastapi import APIRouter, HTTPException, status

from agents.repository_agent.schemas.repository_schema import (
    RepositoryCreateRequest,
    RepositoryRegistrationResponse,
)
from agents.repository_agent.services.repository_service import (
    list_repositories,
    register_repository,
    clone_registered_repository,
    update_repository_status,
)
from agents.repository_agent.services.analysis_service import (
    analyze_registered_repository,
)
from agents.repository_agent.services.evolution_service import (
    get_evolution_summary,
    get_file_evolution,
)
from agents.repository_agent.hrim.inference_service import (
    predict_package_proxy_scores,
)
from agents.repository_agent.hrim.multimodal_inference_service import (
    predict_multimodal_proxy_scores,
)
from agents.repository_agent.services.recommendation_service import (
    get_package_recommendations,
)

from services.llama_recommendation_service import (
    generate_recommendations,
)

router = APIRouter()
#router = APIRouter(prefix="/api/ai", tags=["AI recommendations"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SEMANTIC_DIR = PROJECT_ROOT / "data" / "processed" / "semantic"


def _normalize_repository_key(value: str) -> str:
    """Normalize a repository name or URL slug for exact matching."""
    slug = value.strip().lower()
    slug = re.sub(r"\.git$", "", slug)
    slug = re.sub(r"[^a-z0-9]", "", slug)
    slug = re.sub(r"^r\d+", "", slug)
    return slug


def _find_semantic_csv(repository: dict) -> Path | None:
    """Find precomputed embeddings only when the repository key matches."""
    url_path = urlparse(repository["url"]).path.rstrip("/")
    url_slug = url_path.split("/")[-1] if url_path else ""

    possible_keys = {
        _normalize_repository_key(repository["name"]),
        _normalize_repository_key(url_slug),
    }
    possible_keys.discard("")

    if not SEMANTIC_DIR.is_dir():
        return None

    for csv_path in SEMANTIC_DIR.glob("*_aligned_semantic_features.csv"):
        dataset_key = csv_path.name.removesuffix("_aligned_semantic_features.csv")
        normalized_dataset_key = _normalize_repository_key(dataset_key)

        if normalized_dataset_key in possible_keys:
            return csv_path

    return None


@router.get("", response_model=list[RepositoryRegistrationResponse])
def get_repositories():
    return list_repositories()


@router.post(
    "",
    response_model=RepositoryRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_repository(request: RepositoryCreateRequest):
    try:
        return register_repository(request)
    except ValueError as exc:
        message = str(exc)
        status_code = (
            status.HTTP_409_CONFLICT
            if "already registered" in message
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc


@router.post("/{repository_id}/clone")
def clone_repository_endpoint(repository_id: str):
    try:
        return clone_registered_repository(repository_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{repository_id}/evolution/summary")
def get_repository_evolution_summary(repository_id: str):
    """Return repository-wide Git evolution metrics."""
    try:
        if not any(item.id == repository_id for item in list_repositories()):
            raise HTTPException(
                status_code=404, detail="Registered repository not found."
            )
        return get_evolution_summary(repository_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{repository_id}/evolution/files")
def get_repository_file_evolution(repository_id: str, limit: int = 500):
    """Return per-file evolution metrics; limit defaults to 500 rows."""
    try:
        if not any(item.id == repository_id for item in list_repositories()):
            raise HTTPException(
                status_code=404, detail="Registered repository not found."
            )
        return get_file_evolution(repository_id, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{repository_id}/analyze")
def analyze_repository_endpoint(repository_id: str):
    try:
        result = analyze_registered_repository(repository_id)

        repository_path = PROJECT_ROOT / "data" / "user_repositories" / repository_id
        architecture_csv = (
            PROJECT_ROOT / "data" / "architecture" / f"{repository_id}_architecture.csv"
        )
        dependencies_csv = (
            PROJECT_ROOT / "data" / "dependencies" / f"{repository_id}_dependencies.csv"
        )

        # Existing structural baseline: preserved.
        result["proxy_predictions"] = predict_package_proxy_scores(
            repository_id=repository_id,
            architecture_csv=architecture_csv,
            repo_path=repository_path,
        )

        # Multimodal HRIM: run only when matching precomputed embeddings exist.
        registered_repository = next(
            (
                item.model_dump(mode="json")
                for item in list_repositories()
                if item.id == repository_id
            ),
            None,
        )

        semantic_csv = (
            _find_semantic_csv(registered_repository) if registered_repository else None
        )

        if semantic_csv is None:
            result["multimodal_proxy_predictions"] = {
                "status": "unavailable",
                "model_type": "exploratory_multimodal_hrim",
                "reason": (
                    "No matching precomputed semantic feature CSV was found. "
                    "Generate and validate GraphCodeBERT embeddings for this "
                    "repository before using multimodal HRIM."
                ),
            }
        else:
            try:
                predictions = predict_multimodal_proxy_scores(
                    repository_id=repository_id,
                    architecture_csv=architecture_csv,
                    dependencies_csv=dependencies_csv,
                    semantic_csv=semantic_csv,
                    repo_path=repository_path,
                )
                result["multimodal_proxy_predictions"] = {
                    "status": "exploratory",
                    "model_type": "exploratory_multimodal_hrim",
                    "feature_dimensions": 787,
                    "temporal_alignment_verified": False,
                    "predictions": predictions,
                    "caveat": (
                        "Predictions use a proxy target and are exploratory. "
                        "Historical feature-to-label alignment has not been "
                        "verified."
                    ),
                }
            except (ValueError, FileNotFoundError) as exc:
                result["multimodal_proxy_predictions"] = {
                    "status": "unavailable",
                    "model_type": "exploratory_multimodal_hrim",
                    "reason": str(exc),
                }

        update_repository_status(repository_id, "Analysis Complete")
        return result

    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{repository_id}/packages/{package_path:path}/recommendations")
def get_repository_package_recommendations(
    repository_id: str,
    package_path: str,
):
    try:
        return get_package_recommendations(
            repository_id=repository_id,
            package_path=package_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.post("/{repository_id}/llama-recommendations")
async def create_package_llama_recommendations(
    repository_id: str,
    package_path: str,
):
    # Retrieve package-level prediction and SHAP evidence.
    try:
        evidence = get_package_recommendations(
            repository_id=repository_id,
            package_path=package_path,
        )

        if evidence.get("status") == "not_found":
            raise HTTPException(
                status_code=404,
                detail=evidence.get(
                    "message", "No SHAP evidence found for this package."
                ),
            )

        # Generate natural-language recommendations from that evidence.
        return await generate_recommendations(evidence)

    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="The local Llama service could not be reached.",
        ) from exc
