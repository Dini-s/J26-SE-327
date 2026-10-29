"""Load processed artifacts (from scripts/load_dataset.py) into Neo4j.

Usage (from the project root, with NEO4J_* set in .env):
    python scripts/load_to_neo4j.py [--artifacts data/processed/cm1/artifacts.json]

Idempotent (MERGE on id), so it is safe to re-run. Requirements become
(:Requirement {id, text}) and everything else (:CodeEntity {id, text, kind}), the
USKG labels C4 reads (see shared/uskg/client.py). This is dev seed data standing in
for C1/C2 output; do not run it against the team's shared graph. Ground-truth links are deliberately NOT loaded: they
belong only in the gold file, otherwise the agent could "find" them in the graph.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

from dotenv import load_dotenv
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARTIFACTS = PROJECT_ROOT / "data" / "processed" / "cm1" / "artifacts.json"

_REQUIREMENTS = """
UNWIND $rows AS row
MERGE (n:Requirement {id: row.id})
SET n.text = row.text, n.dataset = row.dataset
"""

_CODE_ENTITIES = """
UNWIND $rows AS row
MERGE (n:CodeEntity {id: row.id})
SET n.text = row.text, n.kind = row.type, n.dataset = row.dataset
"""


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Upsert every artifact in the JSON file as an :Artifact node."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not password:
        print("NEO4J_PASSWORD is empty; fill in .env first.", file=sys.stderr)
        return 1

    artifacts = json.loads(args.artifacts.read_text(encoding="utf-8"))
    rows = [
        {"id": a["id"], "type": a["type"], "text": a["text"], "dataset": a["metadata"].get("dataset")}
        for a in artifacts
    ]
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    with GraphDatabase.driver(uri, auth=(os.getenv("NEO4J_USERNAME", "neo4j"), password)) as driver:
        driver.execute_query(_REQUIREMENTS, rows=[r for r in rows if r["type"] == "requirement"])
        driver.execute_query(_CODE_ENTITIES, rows=[r for r in rows if r["type"] != "requirement"])
    print(f"upserted {len(rows)} nodes into {uri}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
