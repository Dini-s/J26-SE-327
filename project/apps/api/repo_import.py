"""Add a project to the dashboard: a public GitHub repository or a folder on this computer.

This is the C2 stand-in from the web app, without the login part (no accounts, no MongoDB):

* a **GitHub URL** (``https://github.com/owner/repo``, public only) is cloned with a sandboxed ``git``,
* a **local folder** must lie inside the home folder of the user running the server; it is read in place
  (never changed, never copied),

then every source file becomes a ``CodeEntity`` node of the new project in the local Neo4j, marked
``source = 'repo-connector'``. C4 itself is untouched.

The project key is ``aspire/<name>`` for GitHub, and ``local/<name>`` for a folder; a name that is already used
gets ``-2``, ``-3`` ... appended. A project key that is already in the graph is never overwritten.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from apps.api import repo_connector as rc

HOME = Path.home().resolve()
KEY_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,59}")
MAX_NAME = 60


class ImportError_(ValueError):
    """A user-facing problem with an import request (the server answers 400)."""


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9._-]+", "-", text.lower()).strip("-.")
    return (s or "project")[:MAX_NAME]


def unique_key(prefix: str, name: str, taken: set[str]) -> str:
    base = f"{prefix}/{slug(name)}"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    return key


def taken_keys() -> set[str]:
    """Project keys already in the graph (so a new import never merges into an existing project)."""
    from apps.api import sources

    return {p["project"] for p in sources.neo4j_projects()}


def check_local_folder(path_text: Any) -> Path:
    """The folder must exist, be a directory, and lie inside the home folder (symlinks are followed and then checked)."""
    if not isinstance(path_text, str) or not path_text.strip():
        raise ImportError_("Enter the folder path, for example /Users/you/Desktop/my-project.")
    folder = Path(path_text.strip()).expanduser()
    try:
        resolved = folder.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ImportError_("This folder does not exist.")
    if not resolved.is_dir():
        raise ImportError_("The path is not a folder.")
    if resolved != HOME and HOME not in resolved.parents:
        raise ImportError_(f"Only folders inside your home folder ({HOME}) can be imported.")
    return resolved


def browse_folders(path_text: Any = None) -> dict[str, Any]:
    """List selectable child folders, confined to the importer's home directory."""
    folder = check_local_folder(str(HOME) if path_text is None else path_text)
    children = []
    try:
        entries = list(folder.iterdir())
    except OSError as exc:
        raise ImportError_("This folder cannot be opened. Choose another folder.") from exc
    for entry in entries:
        if entry.name.startswith("."):
            continue
        try:
            resolved = check_local_folder(str(entry))
        except (ImportError_, OSError):
            continue
        children.append({"name": entry.name, "path": str(resolved)})
    return {"path": str(folder), "parent": None if folder == HOME else str(folder.parent),
            "folders": sorted(children, key=lambda item: item["name"].casefold())}


def scan_folder(folder: Path) -> list[rc.SourceFile]:
    """The same source-file rules as the GitHub import, applied to a folder in place."""
    return rc.scan(folder)


def ingest_files(key: str, files: list[rc.SourceFile], driver: Any = None) -> int:
    """Write the files as CodeEntity nodes of ``key`` (the connector's own write path and guards)."""
    if not files:
        raise ImportError_("No source files were found (supported: Java, Python, JavaScript, TypeScript, C, C++, C#, Go, PHP, JSP, HTML ...).")
    return rc.write_files(key, files, driver)


def import_github(url: Any, name: Optional[str], branch: Optional[str], driver: Any = None, use_app: bool = False) -> dict[str, Any]:
    """Clone a public GitHub repository and ingest it. Returns the new project's key, name and file count."""
    try:
        owner_repo, canonical = rc.parse_github_url(url)
        branch = rc.parse_branch(branch)
    except rc.ConnectorError as exc:
        raise ImportError_(str(exc)) from exc
    repo = owner_repo.split("/", 1)[1]
    display = (name or "").strip() or f"Aspire/{repo}"
    key = unique_key("aspire", display.split("/")[-1] if "/" in display else display, taken_keys())
    dest = rc.CLONE_ROOT / slug(key.replace("/", "-"))
    installation = None
    auth = {}
    if use_app:
        from apps.api import github_app
        try:
            installation = github_app.repository_access(canonical)
            auth['auth_token'] = github_app.installation_token(installation)
        except github_app.GitHubError as exc:
            raise ImportError_(str(exc)) from exc
    try:
        info = rc.clone(canonical, dest, branch, **auth)
        files = rc.scan(dest)
        count = ingest_files(key, files, driver)
    except rc.ConnectorError as exc:
        raise ImportError_(str(exc)) from exc
    from apps.api import repo_sync
    repo_sync.register(key, canonical, dest, info, installation_id=installation)
    return {"key": key, "name": display, "files": count, "source": canonical, "head": info["head"]}


def import_folder(path_text: Any, name: Optional[str], driver: Any = None) -> dict[str, Any]:
    """Read a local folder (inside the home folder) and ingest its source files under a ``local/`` key."""
    folder = check_local_folder(path_text)
    display = (name or "").strip() or folder.name
    key = unique_key("local", display, taken_keys())
    try:
        files = scan_folder(folder)
        count = ingest_files(key, files, driver)
    except rc.ConnectorError as exc:
        raise ImportError_(str(exc)) from exc
    return {"key": key, "name": display, "files": count, "source": str(folder)}
