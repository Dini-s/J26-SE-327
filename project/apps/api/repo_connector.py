"""Repository connector: a STAND-IN for component C2 (the repository component).

In the full system C2 reads the repository and writes ``CodeEntity`` nodes, then tells C4 which files a
commit changed. C2 is not available for the demo, so this module does that job for the repositories users
connect in the web app. C4 itself is untouched: it only ever reads ``CodeEntity`` nodes and writes
``VERIFIED_TRACE`` / ``DecayFlag``. When the real C2 exists, this module is replaced and nothing else changes.

What it does
* checks the GitHub URL (public ``https://github.com/<owner>/<repo>`` only) and clones it with a sandboxed ``git``,
* scans the source files (extension allow-list, no tests, no vendored code, size limits, no symlinks),
* writes one ``CodeEntity`` per file with an id that is unique across the whole graph
  (``"<projectKey>:<path>"``), marked ``source = 'repo-connector'``,
* later fetches new commits and brings the nodes up to date (modified / added / deleted files).

Safety rules (each one is covered by a test)
* only ``https://github.com/...`` URLs reach ``git`` (never ssh, file, ext::, other hosts, options),
* ``git`` runs without hooks, without submodules, without prompts, with a timeout,
* files are read only if their real path stays inside the clone and they are not symlinks,
* the Neo4j statements below can only create or change nodes that carry ``source = 'repo-connector'``
  (they never touch another component's nodes), and only on a local Neo4j.
"""

from __future__ import annotations

import fnmatch
from datetime import datetime, timezone
import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLONE_ROOT = PROJECT_ROOT / "data" / "repos"

SOURCE = "repo-connector"
CLONE_TIMEOUT = 180
FETCH_TIMEOUT = 60
MAX_FILES = 3000
MAX_FILE_BYTES = 200_000
MAX_REPO_BYTES = 300 * 1024 * 1024
FETCH_DEPTH = 50
BATCH = 200

LANGUAGES = {
    ".java": "java", ".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".cs": "csharp", ".go": "go", ".rb": "ruby", ".php": "php", ".kt": "kotlin", ".rs": "rust", ".swift": "swift",
    ".scala": "scala", ".groovy": "groovy", ".jsp": "jsp", ".jspx": "jsp", ".html": "html", ".htm": "html",
    ".vue": "vue", ".dart": "dart", ".lua": "lua", ".sh": "shell",
}
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "build", "dist", "target", ".venv", "venv", "env", "__pycache__", ".idea",
    ".gradle", "out", "bin", "obj", "site-packages", ".next", ".tox", "third_party", "third-party", "Pods",
}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testing", "e2e"}
TEST_FILES = ("*Test.java", "*Tests.java", "*IT.java", "test_*.py", "*_test.py", "*.test.js", "*.test.jsx", "*.test.ts",
              "*.test.tsx", "*.spec.js", "*.spec.ts", "*_test.go", "*Test.kt", "*Tests.cs", "*Test.cs")

_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
_REPO = r"[A-Za-z0-9._-]{1,100}"
_URL = re.compile(rf"^https://github\.com/({_OWNER})/({_REPO}?)(?:\.git)?/?$")
_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/\-]{0,99}$")


class ConnectorError(Exception):
    """Something the user can understand and act on (bad URL, repository not found, too large ...)."""


# ------------------------------------------------------------------ validation
def parse_github_url(url: Any) -> tuple[str, str]:
    """Return ``("owner/repo", canonical_https_url)`` for a public GitHub repository URL.

    Raises:
        ConnectorError: for anything that is not exactly ``https://github.com/<owner>/<repo>`` (ssh, file,
        ``ext::``, other hosts, paths below the repo, query strings, spaces, option-like text ...).
    """
    if not isinstance(url, str):
        raise ConnectorError("Enter the repository address, for example https://github.com/owner/repo.")
    url = url.strip()
    if len(url) > 200 or not url.isprintable() or " " in url:
        raise ConnectorError("This is not a valid GitHub repository address.")
    m = _URL.match(url)
    if not m or m.group(2) in (".", "..") or m.group(2).endswith("."):
        raise ConnectorError("Only public GitHub repositories are supported: https://github.com/owner/repo")
    owner, repo = m.group(1), m.group(2)
    return f"{owner}/{repo}", f"https://github.com/{owner}/{repo}"


def parse_branch(branch: Any) -> Optional[str]:
    if branch in (None, ""):
        return None
    if not isinstance(branch, str) or not _BRANCH.match(branch) or ".." in branch or branch.endswith(("/", ".lock")):
        raise ConnectorError("The branch name is not valid.")
    return branch


def node_id(key: str, path: str) -> str:
    """Graph-wide unique id of a repository file: ``"aspire/shop:src/App.java"``."""
    return f"{key}:{path}"


# ------------------------------------------------------------------ git
def _git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="/usr/bin/true", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
    return env


def _safe_flags(allow_local: bool) -> list[str]:
    flags = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "submodule.recurse=false",
             "-c", "protocol.allow=never", "-c", "protocol.https.allow=always", "-c", "core.symlinks=false"]
    if allow_local:  # tests only: clone from a throw-away local repository
        flags += ["-c", "protocol.file.allow=always"]
    return flags


def run_git(args: list[str], cwd: Optional[Path] = None, timeout: int = 60, allow_local: bool = False, auth_token: Optional[str] = None) -> str:
    """Run git with the safety flags; return stdout. Raises ``ConnectorError`` on failure or timeout."""
    cmd = ["git", *_safe_flags(allow_local), *args]
    env = _git_env()
    redactions = []
    if auth_token:
        import base64
        credential = base64.b64encode(('x-access-token:' + auth_token).encode()).decode()
        env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
                   GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + credential)
        redactions = [auth_token, credential]
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise ConnectorError("The repository took too long to download. Try a smaller repository.")
    except FileNotFoundError:
        raise ConnectorError("git is not installed on this computer.")
    if out.returncode != 0:
        message = (out.stderr or out.stdout or "").strip().splitlines()
        text = message[-1] if message else "git failed"
        for value in redactions:
            text = text.replace(value, "[redacted]")
        if re.search(r"not found|could not read Username|Authentication failed|terminal prompts disabled", text, re.I):
            raise ConnectorError("The repository was not found or is not public.")
        raise ConnectorError(f"git failed: {text[:200]}")
    return out.stdout


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def clone(source: str, dest: Path, branch: Optional[str] = None, allow_local: bool = False, auth_token: Optional[str] = None) -> dict[str, str]:
    """Shallow, sandboxed clone into ``dest`` (which must be a new folder under ``CLONE_ROOT``).

    ``source`` must already have passed :func:`parse_github_url` (``allow_local`` is for the tests, which
    clone ``file://`` repositories). Returns ``{"head": sha, "branch": name}``.
    """
    if not allow_local and not source.startswith("https://github.com/"):
        raise ConnectorError("Only public GitHub repositories are supported.")
    root = CLONE_ROOT if not allow_local else dest.parent
    if not _inside(root, dest) or dest.exists():
        raise ConnectorError("Could not prepare the download folder.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = ["clone", "--depth", "1", "--single-branch", "--no-tags", "--no-recurse-submodules"]
    if branch:
        args += ["--branch", branch]
    try:
        run_git([*args, "--", source, str(dest)], timeout=CLONE_TIMEOUT, allow_local=allow_local, auth_token=auth_token)
        size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file() and not f.is_symlink())
        if size > MAX_REPO_BYTES:
            raise ConnectorError(f"The repository is too large ({size // 1_000_000} MB; the limit is {MAX_REPO_BYTES // 1_000_000} MB).")
        head = run_git(["rev-parse", "HEAD"], cwd=dest, allow_local=allow_local).strip()
        name = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=dest, allow_local=allow_local).strip()
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)   # our own download folder: never leave a half clone behind
        raise
    return {"head": head, "branch": name}


# ------------------------------------------------------------------ scanning
@dataclass
class SourceFile:
    path: str          # posix path relative to the repository root
    text: str
    language: str
    sha: str           # git blob sha (changes when the content changes)


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def is_source_path(path: str) -> bool:
    """Whether a repository-relative path should become a ``CodeEntity`` (extension, folders, tests)."""
    parts = path.split("/")
    name = parts[-1]
    if Path(name).suffix.lower() not in LANGUAGES:
        return False
    if any(p in SKIP_DIRS or p.startswith(".") for p in parts[:-1]) or any(p.lower() in TEST_DIRS for p in parts[:-1]):
        return False
    return not any(fnmatch.fnmatch(name, pat) for pat in TEST_FILES)


def read_source(root: Path, rel: str) -> Optional[SourceFile]:
    """Read one file if it is safe and small enough: inside the clone, not a symlink, text, <= 200 KB."""
    full = root / rel
    if full.is_symlink() or not full.is_file() or not _inside(root, full):
        return None
    try:
        if full.stat().st_size > MAX_FILE_BYTES:
            return None
        data = full.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8000]:
        return None
    text = data.decode("utf-8", errors="replace")
    return SourceFile(path=rel, text=text, language=LANGUAGES[Path(rel).suffix.lower()], sha=git_blob_sha(data))


def scan(root: Path) -> list[SourceFile]:
    """All source files of a clone (sorted by path).

    Raises:
        ConnectorError: if there are more than ``MAX_FILES`` source files.
    """
    found: list[SourceFile] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".") and d.lower() not in TEST_DIRS
                             and not (Path(dirpath) / d).is_symlink())
        for name in sorted(filenames):
            rel = (Path(dirpath) / name).relative_to(root).as_posix()
            if not is_source_path(rel):
                continue
            item = read_source(root, rel)
            if item:
                found.append(item)
                if len(found) > MAX_FILES:
                    raise ConnectorError(f"The repository has more than {MAX_FILES} source files; choose a smaller one.")
    return sorted(found, key=lambda f: f.path)


# ------------------------------------------------------------------ Neo4j (only nodes this module owns)
_UPSERT = """
UNWIND $rows AS row
MERGE (c:CodeEntity {id: row.id})
  ON CREATE SET c.source = 'repo-connector'
WITH c, row
WHERE c.source = 'repo-connector'
SET c.text = row.text, c.kind = 'code', c.project = $project, c.language = row.language,
    c.path = row.path, c.blobSha = row.sha, c.deleted = false
RETURN count(c) AS n
"""

_UPDATE = """
UNWIND $rows AS row
MATCH (c:CodeEntity {id: row.id})
WHERE c.source = 'repo-connector' AND c.project = $project
SET c.text = row.text, c.blobSha = row.sha, c.deleted = false
RETURN count(c) AS n
"""

_DELETE = """
UNWIND $ids AS id
MATCH (c:CodeEntity {id: id})
WHERE c.source = 'repo-connector' AND c.project = $project AND coalesce(c.deleted, false) = false
SET c.deleted_text = c.text, c.text = '', c.deleted = true
RETURN count(c) AS n
"""


_PURGE = """
MATCH (c:CodeEntity)
WHERE c.source = 'repo-connector' AND c.project = $project
DETACH DELETE c
RETURN count(*) AS n
"""


def _guard_local() -> None:
    from apps.api import demo

    state = demo.allowed()
    if not state["allowed"]:
        raise ConnectorError(state["reason"])


def _chunks(items: list[Any]) -> Iterable[list[Any]]:
    for i in range(0, len(items), BATCH):
        yield items[i:i + BATCH]


def _run(query: str, driver: Any = None, **params: Any) -> int:
    from apps.api.sources import _neo4j_driver

    own = driver is None
    driver = driver or _neo4j_driver()
    try:
        records, _, _ = driver.execute_query(query, **params)
        return int(records[0]["n"]) if records else 0
    except Exception as exc:
        raise ConnectorError(f"The knowledge graph (Neo4j) did not accept the files: {type(exc).__name__}") from exc
    finally:
        if own:
            driver.close()


def write_files(key: str, files: list[SourceFile], driver: Any = None) -> int:
    """Create or refresh the ``CodeEntity`` nodes for these files; returns how many were written."""
    _guard_local()
    rows = [{"id": node_id(key, f.path), "text": f.text, "language": f.language, "path": f.path, "sha": f.sha} for f in files]
    return sum(_run(_UPSERT, driver, rows=chunk, project=key) for chunk in _chunks(rows))


def update_files(key: str, files: list[SourceFile], driver: Any = None) -> int:
    """New text for files that changed in a commit (only nodes of this project and this module)."""
    _guard_local()
    rows = [{"id": node_id(key, f.path), "text": f.text, "sha": f.sha} for f in files]
    return sum(_run(_UPDATE, driver, rows=chunk, project=key) for chunk in _chunks(rows))


def mark_deleted(key: str, paths: list[str], driver: Any = None) -> int:
    """A deleted file keeps its node but gets empty text (its old text is kept in ``deleted_text``),
    so C4's empty-content guard marks the links to it decayed without asking the AI."""
    _guard_local()
    ids = [node_id(key, p) for p in paths]
    return sum(_run(_DELETE, driver, ids=chunk, project=key) for chunk in _chunks(ids))


# ------------------------------------------------------------------ the project set-up job
def ingest(clone_dir: Path, key: str, driver: Any = None) -> int:
    """Scan a clone and write its files to the graph. Returns the number of files."""
    files = scan(clone_dir)
    if not files:
        raise ConnectorError("No source files were found (supported: " + ", ".join(sorted({v for v in LANGUAGES.values()})) + ").")
    write_files(key, files, driver)
    return len(files)


# ------------------------------------------------------------------ new commits
@dataclass
class CommitBatch:
    """What changed between the commit we last analyzed and the repository's current head."""

    base: str
    head: str
    commits: list[dict[str, str]] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.modified or self.added or self.deleted)


def fetch_new(clone_dir: Path, base: str, branch: str, allow_local: bool = False, auth_token: Optional[str] = None) -> Optional[CommitBatch]:
    """Fetch the branch and describe what is new since ``base`` (``None`` if nothing is new).

    The clone is moved to the new head, so later scans read the current files. The diff is between the two
    trees, so it also works when the old commit is outside the shallow history.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", base) or not _BRANCH.match(branch):
        raise ConnectorError("Invalid repository state.")
    run_git(["fetch", "--depth", str(FETCH_DEPTH), "--no-tags", "origin", branch], cwd=clone_dir, timeout=FETCH_TIMEOUT, allow_local=allow_local, auth_token=auth_token)
    head = run_git(["rev-parse", "FETCH_HEAD"], cwd=clone_dir, allow_local=allow_local).strip()
    if head == base:
        return None
    batch = CommitBatch(base=base, head=head)
    try:
        log = run_git(["log", "--format=%H%x1f%an%x1f%aI%x1f%s", f"{base}..{head}"], cwd=clone_dir, allow_local=allow_local)
        for line in log.splitlines():
            sha, author, date, subject = (line.split("\x1f") + ["", "", "", ""])[:4]
            batch.commits.append({"sha": sha, "author": author, "date": date, "message": subject[:200]})
        batch.commits.reverse()                                  # oldest first
    except ConnectorError:
        pass
    if not batch.commits:                                        # base outside the fetched history: one summary entry
        subject = run_git(["log", "-1", "--format=%s", head], cwd=clone_dir, allow_local=allow_local).strip()
        batch.commits.append({"sha": head, "author": "", "date": "", "message": subject[:200]})
    diff = run_git(["diff", "--name-status", "--no-renames", "-z", base, head], cwd=clone_dir, allow_local=allow_local)
    tokens = diff.split("\0")
    for status, path in zip(tokens[0::2], tokens[1::2]):
        if not is_source_path(path):
            continue
        (batch.added if status == "A" else batch.deleted if status == "D" else batch.modified).append(path)
    run_git(["reset", "--hard", "-q", head], cwd=clone_dir, allow_local=allow_local)
    return batch


def apply_batch(clone_dir: Path, key: str, batch: CommitBatch, driver: Any = None) -> dict[str, list[str]]:
    """Bring the graph's ``CodeEntity`` nodes up to date with a batch. Returns the node ids by kind
    (``modified`` / ``added`` / ``deleted``) in the form C4's ``changed`` command expects."""
    modified = [f for f in (read_source(clone_dir, p) for p in batch.modified) if f]
    added = [f for f in (read_source(clone_dir, p) for p in batch.added) if f]
    if modified:
        update_files(key, modified, driver)
    if added:
        write_files(key, added, driver)
    if batch.deleted:
        mark_deleted(key, batch.deleted, driver)
    return {
        "modified": [node_id(key, f.path) for f in modified],
        "added": [node_id(key, f.path) for f in added],
        "deleted": [node_id(key, p) for p in batch.deleted],
    }


# ------------------------------------------------------------------ project set-up (runs in a background thread)
def purge(key: str, driver: Any = None) -> int:
    """Delete the ``CodeEntity`` nodes this module created for a project (never another component's nodes).
    C4's own links, flags and dashboard-typed requirements are removed by ``demo.reset`` before this."""
    _guard_local()
    return _run(_PURGE, driver, project=key)


def remove_clone(path: Any) -> bool:
    """Delete a project's download folder, only if it really is a folder inside ``CLONE_ROOT``."""
    if not path:
        return False
    folder = Path(path)
    if folder.is_symlink() or not folder.is_dir() or folder.resolve().parent != CLONE_ROOT.resolve():
        return False
    shutil.rmtree(folder, ignore_errors=True)
    return True
