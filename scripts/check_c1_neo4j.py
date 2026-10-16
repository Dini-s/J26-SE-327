"""Check the Neo4j connection of Component 1. Publishes NOTHING.

    .venv\\Scripts\\python.exe scripts\\check_c1_neo4j.py [--no-env-file]

Settings are read exactly like the API reads them: C1_NEO4J_URI / C1_NEO4J_USER / C1_NEO4J_PASSWORD / C1_NEO4J_DATABASE, then NEO4J_URI /
NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE, from the environment and (only these keys) from the shared .env file. The script prints the server
version, the database and the host name, runs `RETURN 1`, and creates the constraints and indexes (idempotent). It never prints the password or the
full address. Exit code 0 = everything worked, 1 = a plain-language problem was printed.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "project"))

from agents.requirement_agent.api import neo4j_config  # noqa: E402
from agents.requirement_agent.api.errors import ApiError  # noqa: E402
from agents.requirement_agent.api.neo4j_store import Neo4jStore  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--no-env-file", action="store_true", help="read the environment only, not the .env file")
    args = parser.parse_args(argv)
    env_files = [] if args.no_env_file else None
    cfg = neo4j_config.load_config(env_files=env_files)
    print(f"Configured: {'yes' if cfg.configured else 'no'}  host: {cfg.host or '-'}  database: {cfg.database}")
    store = Neo4jStore(None, config_loader=lambda: neo4j_config.load_config(env_files=env_files))
    try:
        info = store.check()
    except ApiError as exc:
        print(f"FAIL ({exc.code}): {exc.message}")
        return 1
    print(f"Server version: {info['server_version'] or 'unknown'}")
    print(f"Database: {info['database']}   Host: {info['host']}")
    print(f"RETURN 1 -> {info['return_one']}")
    print(f"Constraints and indexes ensured ({info['statements']} statements, IF NOT EXISTS). Nothing was published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
