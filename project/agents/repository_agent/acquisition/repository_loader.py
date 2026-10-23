import argparse
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLONE_ROOT = PROJECT_ROOT / "data" / "user_repositories"

ALLOWED_HOSTS = {
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "dev.azure.com",
}


def load_repository(repo_path: str) -> dict:
    """Load basic information about an existing local Git repository."""
    path = Path(repo_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    if not (path / ".git").exists():
        raise ValueError(f"Not a Git repository: {repo_path}")

    files = [
        file for file in path.rglob("*") if file.is_file() and ".git" not in file.parts
    ]

    return {
        "repository_path": str(path),
        "file_count": len(files),
    }


def clone_repository(
    repository_url: str,
    repository_id: str,
    branch: str = "main",
) -> dict:
    """Clone a public HTTPS Git repository into a controlled workspace."""
    parsed = urlparse(repository_url)
    host = (parsed.hostname or "").lower().rstrip(".")

    if (
        parsed.scheme != "https"
        or host not in ALLOWED_HOSTS
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not parsed.path.strip("/")
    ):
        raise ValueError("Unsupported or invalid repository URL.")

    if not repository_id or any(
        char not in "0123456789abcdef-" for char in repository_id.lower()
    ):
        raise ValueError("Invalid repository ID.")

    if (
        not branch.strip()
        or branch.startswith("-")
        or branch.startswith("/")
        or "\\" in branch
        or any(part in {".", ".."} for part in branch.split("/"))
        or any(ord(char) < 32 for char in branch)
    ):
        raise ValueError("Invalid branch name.")

    CLONE_ROOT.mkdir(parents=True, exist_ok=True)
    destination = (CLONE_ROOT / repository_id).resolve()

    if destination.parent != CLONE_ROOT.resolve():
        raise ValueError("Invalid clone destination.")

    if destination.exists():
        if not destination.is_dir():
            raise FileExistsError(
                "The repository destination exists but is not a directory."
            )

        information = load_repository(str(destination))

        return {
            "repository_id": repository_id,
            "local_path": str(destination),
            "file_count": information["file_count"],
            "status": "Cloned",
            "reused_existing": True,
        }

    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=NUL",
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--branch",
                branch,
                "--",
                repository_url,
                str(destination),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            shell=False,
        )

        if result.returncode != 0:
            raise RuntimeError("Cloning failed. Check the URL, branch, and Git access.")

        information = load_repository(str(destination))

        return {
            "repository_id": repository_id,
            "local_path": str(destination),
            "file_count": information["file_count"],
            "status": "Cloned",
        }

    except Exception:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Inspect an existing local Git repository"
    )
    parser.add_argument("repo_path", help="Path to the Git repository")
    args = parser.parse_args()

    information = load_repository(args.repo_path)
    print("Repository:", information["repository_path"])
    print("File count:", information["file_count"])
