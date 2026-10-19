"""Compare, per project and per document, what the Component 1 workspace holds with what the Neo4j graph holds. READ-ONLY, counts only.

    .venv\\Scripts\\python.exe scripts\\c1_graph_counts.py [--workspace DIR] [--no-env-file]

For every project of the workspace database and every document in it, one line with the requirement, issue and draft counts from the workspace and from
the graph side by side ("ok" when they are equal). The workspace is opened through a copy made with sqlite's read-only backup, so the real file is never
written; the graph is only queried with MATCH/RETURN. Only counts, project ids and document numbers are printed: no requirement text, no file names, no
address and no credentials. A document that is not analysed is not published, so its graph side is expected to be 0 (it is marked "not analysed").
Exit code 0 = the script ran (differences are printed, not an error), 1 = the workspace could not be read, 2 = the graph could not be reached.
"""
import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "project"))

from agents.requirement_agent.api import neo4j_config, neo4j_store, settings  # noqa: E402
from agents.requirement_agent.api import service  # noqa: E402
from agents.requirement_agent.api.db import Database  # noqa: E402
from agents.requirement_agent.api.errors import ApiError  # noqa: E402

KINDS = ("requirements", "issues", "drafts")


def workspace_counts(db_file, tmp_dir):
    """{(project key, source id): {"state", "requirements", "issues", "drafts"}} from a copy of the workspace file (the real file is only read)."""
    src = sqlite3.connect(f"file:{Path(db_file).resolve().as_posix()}?mode=ro", uri=True)
    copy_path = Path(tmp_dir) / "c1_copy.db"
    try:
        dst = sqlite3.connect(copy_path)
        src.backup(dst)
        dst.close()
    finally:
        src.close()
    db = Database(copy_path)
    out = {}
    for p in db.all("SELECT * FROM projects ORDER BY id"):
        key = service.project_key(db, p)
        bundle = neo4j_store.build_bundle(db, p["id"], key, p["name"], all_documents=True)
        states = {neo4j_store.source_graph_id(key, s["id"]): (s["id"], s.get("analysis_state") or "not_analyzed") for s in db.all("SELECT * FROM sources WHERE project_id=?", (p["id"],))}
        for sb in bundle.sources:
            sid, state = states[sb.source_id]
            out[(key, sid)] = {"state": state, "requirements": len(sb.requirements), "issues": len(sb.issues), "drafts": len(sb.drafts)}
    return out


def graph_counts(session_run, project_keys):
    """{(project key, source id): {kind: n}} of the active nodes in the graph. `session_run(query, **params)` returns the rows as dicts."""
    out = {}
    for key in project_keys:
        prefix = f"{key}:src"
        for kind in KINDS:
            for row in session_run(neo4j_store.Q_COUNT[kind], project_id=key):
                sid = str(row["source_id"])
                if sid.startswith(prefix) and sid[len(prefix):].isdigit():
                    out.setdefault((key, int(sid[len(prefix):])), dict.fromkeys(KINDS, 0))[kind] = int(row["n"])
    return out


def table(ws, graph):
    """Printable lines and the number of documents whose counts differ."""
    lines, different = [], 0
    for key in sorted({k for k, _ in ws}):
        lines.append(f"project {key}")
        lines.append(f"  {'document':<10}{'state':<14}{'requirements':>18}{'issues':>16}{'drafts':>16}   result")
        lines.append(f"  {'':<10}{'':<14}{'db / graph':>18}{'db / graph':>16}{'db / graph':>16}")
        for (_, sid), w in sorted((k, v) for k, v in ws.items() if k[0] == key):
            g = graph.get((key, sid), dict.fromkeys(KINDS, 0)) if graph is not None else None
            cells = [f"{w[k]:>6} / {('-' if g is None else g[k]):<5}" for k in KINDS]
            if g is None:
                note = ""
            elif w["state"] != "analyzed":
                note = "not analysed" if all(g[k] == 0 for k in KINDS) else "not analysed (graph keeps older data)"
            elif all(w[k] == g[k] for k in KINDS):
                note = "ok"
            else:
                note, different = "DIFFERENT", different + 1
            lines.append(f"  src{sid:<7}{w['state']:<14}{cells[0]:>18}{cells[1]:>16}{cells[2]:>16}   {note}")
    return lines, different


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--workspace", help="the workspace directory (default: C1_WORKSPACE or outputs/c1_workspace)")
    parser.add_argument("--no-env-file", action="store_true", help="read the environment only, not the .env file")
    args = parser.parse_args(argv)
    db_file = settings.workspace_dir(args.workspace) / "c1.db"
    if not db_file.exists():
        print("The workspace database was not found; nothing to compare.")
        return 1
    try:
        with tempfile.TemporaryDirectory() as tmp:
            ws = workspace_counts(db_file, tmp)
    except (sqlite3.Error, OSError):
        print("The workspace database could not be read.")
        return 1
    graph, code = None, 0
    cfg = neo4j_config.load_config(env_files=[] if args.no_env_file else None)
    store = neo4j_store.Neo4jStore(None, config_loader=lambda: cfg)
    try:
        driver = store.open(cfg)
    except ApiError as exc:
        print(f"The graph database cannot be reached ({exc.code}), so only the workspace side is shown.")
        code = 2
    else:
        try:
            with driver.session(database=cfg.database) as session:
                graph = graph_counts(lambda q, **p: [r.data() for r in session.run(q, **p)], sorted({k for k, _ in ws}))
        except Exception as exc:  # noqa: BLE001
            print(f"The graph could not be read ({neo4j_store.translate(exc).code}), so only the workspace side is shown.")
            code = 2
        finally:
            driver.close()
    lines, different = table(ws, graph)
    print("\n".join(lines) if lines else "The workspace has no documents.")
    if graph is not None:
        print(f"{different} document(s) with different counts." if different else "All analysed documents have equal counts.")
    return code


if __name__ == "__main__":
    sys.exit(main())
