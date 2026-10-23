import json
from pathlib import Path
from threading import Lock
from uuid import uuid4
from datetime import datetime, timezone
from urllib.parse import urlparse

from agents.repository_agent.schemas.repository_schema import (
    RepositoryCreateRequest,
    RepositoryRegistrationResponse,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_DIR = PROJECT_ROOT / "apps" / "api" / "data"
REGISTRY_FILE = REGISTRY_DIR / "repositories.json"

_registry_lock = Lock()

PROVIDER_HOSTS = {
    "GitHub": {"github.com"},
    "GitLab": {"gitlab.com"},
    "Bitbucket": {"bitbucket.org"},
    "Azure DevOps": {"dev.azure.com"},
}


def _read_registry() -> list[dict]:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)

    if not REGISTRY_FILE.exists():
        return []

    try:
        with REGISTRY_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Repository registry contains invalid JSON.") from exc

    if not isinstance(data, list):
        raise RuntimeError("Repository registry must contain a JSON list.")

    return data


def _write_registry(repositories: list[dict]) -> None:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    temporary_file = REGISTRY_FILE.with_suffix(".tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(repositories, file, indent=2)

    temporary_file.replace(REGISTRY_FILE)


def list_repositories() -> list[RepositoryRegistrationResponse]:
    with _registry_lock:
        return [RepositoryRegistrationResponse(**item) for item in _read_registry()]


def register_repository(
    request: RepositoryCreateRequest,
) -> RepositoryRegistrationResponse:
    parsed = urlparse(request.url)
    host = (parsed.hostname or "").lower().rstrip(".")

    if host not in PROVIDER_HOSTS[request.provider]:
        raise ValueError("Repository URL does not match the selected provider.")

    with _registry_lock:
        repositories = _read_registry()

        duplicate = any(
            item["url"].rstrip("/").lower() == request.url.lower()
            and item["branch"] == request.branch
            for item in repositories
        )

        if duplicate:
            raise ValueError("This repository and branch are already registered.")

        repository = RepositoryRegistrationResponse(
            id=str(uuid4()),
            name=request.name,
            url=request.url,
            provider=request.provider,
            branch=request.branch,
            status="Registered",
            created_at=datetime.now(timezone.utc),
        )

        # Save only the response fields, never the access token.
        repositories.append(repository.model_dump(mode="json"))
        _write_registry(repositories)

        return repository


from agents.repository_agent.acquisition.repository_loader import (
    clone_repository,
)


def clone_registered_repository(repository_id: str) -> dict:
    """Clone a previously registered repository."""

    with _registry_lock:
        repositories = _read_registry()

        repository = next(
            (item for item in repositories if item["id"] == repository_id),
            None,
        )

        if repository is None:
            raise LookupError("Registered repository not found.")

        if repository["status"] in {"Cloned", "Analyzing", "Analysis Complete"}:
            raise ValueError(
                f"Repository cannot be cloned again while status is "
                f"{repository['status']}."
            )

        if repository["status"] == "Cloning":
            raise ValueError("Repository is already being cloned.")

        repository["status"] = "Cloning"
        _write_registry(repositories)

        url = repository["url"]
        branch = repository["branch"]

    try:
        result = clone_repository(url, repository_id, branch)
    except Exception:
        with _registry_lock:
            repositories = _read_registry()
            for item in repositories:
                if item["id"] == repository_id:
                    item["status"] = "Failed"
                    break
            _write_registry(repositories)
        raise

    with _registry_lock:
        repositories = _read_registry()
        for item in repositories:
            if item["id"] == repository_id:
                item["status"] = "Cloned"
                break
        _write_registry(repositories)

    return result


# update repo status
def update_repository_status(repository_id: str, new_status: str) -> None:
    """Update the status of a registered repository."""
    allowed_statuses = {
        "Registered",
        "Cloning",
        "Cloned",
        "Analyzing",
        "Analysis Complete",
        "Failed",
    }

    if new_status not in allowed_statuses:
        raise ValueError("Invalid repository status.")

    with _registry_lock:
        repositories = _read_registry()

        repository = next(
            (item for item in repositories if item["id"] == repository_id),
            None,
        )

        if repository is None:
            raise LookupError("Registered repository not found.")

        repository["status"] = new_status
        _write_registry(repositories)
