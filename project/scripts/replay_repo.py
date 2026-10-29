"""Replay a real repository's commit history against the USKG (stand-in for C1 and C2).

In the full system C2 watches the repository and tells C4 what each commit changed, and C1 supplies the
requirements. Neither is available for the demo, so this script plays both using public data:

* the git repository (cloned under data/raw/, git-ignored) supplies the code, commit by commit,
* the SEOSS 33 database supplies the Jira issues (as requirements) and which commit belongs to which issue.

Usage (from the project root, Neo4j running locally):
    python scripts/replay_repo.py init   [--since 2017-03-25 --max-commits 12]   # load the starting state
    python scripts/replay_repo.py link                                            # C4 links the issues to code (LLM, slow)
    python scripts/replay_repo.py status
    python scripts/replay_repo.py next [-n 1]                                     # apply the next commit, tell C4

``next`` writes the commit's new file texts into the graph (what C2 would do) and then runs
``python -m agents.traceability_agent changed``, so only the links to files that commit touched are re-checked.
Only for a local Neo4j; the nodes get a ``dataset`` property so the dashboard's reset/undo can clean them up.
SEOSS links come from commit messages: this shows how decay detection behaves on real change, not accuracy.
"""

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from apps.api import demo  # noqa: E402  (its allowed() guard: local Neo4j only)
from apps.api.sources import _neo4j_driver  # noqa: E402

DEFAULT_REPO = PROJECT_ROOT / "data" / "raw" / "jbehave-core"
DEFAULT_DB = PROJECT_ROOT / "data" / "raw" / "seoss" / "jbehave.sqlite3"
STATE_DIR = PROJECT_ROOT / "data" / "runs" / "_replay"
CODE_PREFIX, CODE_SUFFIX = "jbehave-core/src/main/java/", ".java"  # the module whose files become CodeEntity nodes


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def is_code(path: str) -> bool:
    return path.startswith(CODE_PREFIX) and path.endswith(CODE_SUFFIX)


def state_path(project: str) -> Path:
    return STATE_DIR / f"{project}.json"


def pick_commits(db: Path, since: str, limit: int) -> list[dict[str, Any]]:
    """Issue-linked commits, oldest first, that modify or add 1-5 files of the code module."""
    con = sqlite3.connect(db)
    rows = con.execute(
        """SELECT c.commit_hash, substr(c.committed_date,1,10), c.message, l.issue_id
           FROM change_set c JOIN change_set_link l USING (commit_hash)
           WHERE c.is_merge = 0 AND c.committed_date >= ? ORDER BY c.committed_date""", (since,)).fetchall()
    commits = []
    for commit_hash, date, message, issue_id in rows:
        files = con.execute("SELECT file_path, change_type FROM code_change WHERE commit_hash = ?", (commit_hash,)).fetchall()
        code = [(p, t) for p, t in files if is_code(p)]
        if not 1 <= len(code) <= 5 or not any(t in ("MODIFY", "ADD") for _, t in code):
            continue
        if any(c["hash"] == commit_hash for c in commits):  # a commit linked to two issues is replayed once
            continue
        commits.append({"hash": commit_hash, "date": date, "message": message.strip().splitlines()[0][:100], "issue": issue_id,
                        "modified": [p for p, t in code if t == "MODIFY"], "added": [p for p, t in code if t == "ADD"],
                        "deleted": [p for p, t in code if t == "DELETE"], "done": False})
        if len(commits) == limit:
            break
    con.close()
    return commits


def cmd_init(args: argparse.Namespace) -> int:
    commits = pick_commits(args.db, args.since, args.max_commits)
    if not commits:
        print("No suitable commits found.", file=sys.stderr)
        return 1
    base = git(args.repo, "rev-parse", commits[0]["hash"] + "^").strip()
    paths = [p for p in git(args.repo, "ls-tree", "-r", "--name-only", base).splitlines() if is_code(p)]
    code_rows = [{"id": p, "text": git(args.repo, "show", f"{base}:{p}")} for p in paths]
    con = sqlite3.connect(args.db)
    issues = sorted({c["issue"] for c in commits})
    req_rows = []
    for issue_id in issues:
        summary, description = con.execute("SELECT summary, coalesce(description,'') FROM issue WHERE issue_id = ?", (issue_id,)).fetchone()
        req_rows.append({"id": issue_id, "text": " ".join(f"{summary}. {description}".split())[:2000]})
    con.close()
    with _neo4j_driver() as driver:
        driver.execute_query("UNWIND $rows AS r MERGE (n:Requirement {id: r.id}) SET n.text = r.text, n.dataset = $p", rows=req_rows, p=args.project)
        driver.execute_query("UNWIND $rows AS r MERGE (n:CodeEntity {id: r.id}) SET n.text = r.text, n.kind = 'code', n.dataset = $p", rows=code_rows, p=args.project)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path(args.project).write_text(json.dumps({"project": args.project, "repo": str(args.repo), "base": base, "issues": issues,
                                                    "commits": commits}, indent=1))
    print(f"project '{args.project}': {len(req_rows)} issues as requirements, {len(code_rows)} Java files as code (state of {base[:8]}), "
          f"{len(commits)} commits queued ({commits[0]['date']} to {commits[-1]['date']}).\n"
          f"Next: python scripts/replay_repo.py link")
    return 0


def _load(project: str) -> dict[str, Any]:
    path = state_path(project)
    if not path.exists():
        raise SystemExit(f"No replay for '{project}'. Run: python scripts/replay_repo.py init")
    return json.loads(path.read_text())


def _run_c4(args_list: list[str]) -> int:
    return subprocess.run([sys.executable, "-W", "ignore", "-m", "agents.traceability_agent", *args_list], cwd=PROJECT_ROOT).returncode


def cmd_link(args: argparse.Namespace) -> int:
    state = _load(args.project)
    cmd = ["link", "--project", args.project, "--top-k", str(args.top_k)]
    for issue in state["issues"]:
        cmd += ["--requirement", issue]
    return _run_c4(cmd)


def cmd_status(args: argparse.Namespace) -> int:
    state = _load(args.project)
    for i, c in enumerate(state["commits"], 1):
        print(f"{i:2}. {'done' if c['done'] else 'next' if c is next((x for x in state['commits'] if not x['done']), None) else '    '} "
              f"{c['date']} {c['hash'][:8]} {c['issue']}  {len(c['modified'])} changed, {len(c['added'])} added  {c['message']}")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    state = _load(args.project)
    repo = Path(state["repo"])
    for _ in range(args.n):
        commit = next((c for c in state["commits"] if not c["done"]), None)
        if commit is None:
            print("Every queued commit has been replayed.")
            return 0
        print(f"\n== {commit['date']} {commit['hash'][:8]} {commit['issue']}: {commit['message']}")
        with _neo4j_driver() as driver:
            for path in commit["modified"]:
                text = git(repo, "show", f"{commit['hash']}:{path}")
                driver.execute_query("MATCH (c:CodeEntity {id: $id}) SET c.original_text = coalesce(c.original_text, c.text), c.text = $t",
                                     id=path, t=text)
            for path in commit["added"]:
                driver.execute_query("MERGE (c:CodeEntity {id: $id}) SET c.text = $t, c.kind = 'code', c.dataset = $p",
                                     id=path, t=git(repo, "show", f"{commit['hash']}:{path}"), p=args.project)
        cmd = ["changed", "--project", args.project, "--top-k", str(args.top_k)]
        for path in commit["modified"]:
            cmd += ["--code-changed", path]
        for path in commit["added"]:
            cmd += ["--code-added", path]
        if _run_c4(cmd) != 0:
            print("C4 failed on this commit; it stays queued.", file=sys.stderr)
            return 1
        commit["done"] = True
        state_path(args.project).write_text(json.dumps(state, indent=1))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", default="jbehave")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init", help="load the starting state")
    p.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--since", default="2017-03-25")
    p.add_argument("--max-commits", type=int, default=12)
    p.set_defaults(func=cmd_init)
    p = sub.add_parser("link", help="C4 links the issues to code")
    p.add_argument("--top-k", type=int, default=3)
    p.set_defaults(func=cmd_link)
    sub.add_parser("status", help="show the queue").set_defaults(func=cmd_status)
    p = sub.add_parser("next", help="apply the next commit(s) and tell C4")
    p.add_argument("-n", type=int, default=1)
    p.add_argument("--top-k", type=int, default=3)
    p.set_defaults(func=cmd_next)
    args = parser.parse_args(argv)
    state = demo.allowed()
    if not state["allowed"]:
        print(state["reason"], file=sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
