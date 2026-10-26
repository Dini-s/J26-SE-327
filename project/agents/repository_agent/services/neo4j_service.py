import os
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError


NEO4J_URI = os.getenv(
    "NEO4J_URI",
    "bolt://localhost:7687",
)
NEO4J_USERNAME = os.getenv(
    "NEO4J_USERNAME",
    "neo4j",
)
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


_driver = None


def get_driver():
    """Create the Neo4j driver once and reuse it."""
    global _driver

    if not NEO4J_PASSWORD:
        raise RuntimeError("NEO4J_PASSWORD is not configured.")

    if _driver is None:
        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
        )

    return _driver


def verify_connection() -> dict[str, Any]:
    """Verify connectivity and return the server response."""
    driver = get_driver()

    driver.verify_connectivity()

    with driver.session(database=NEO4J_DATABASE) as session:
        record = session.run("RETURN 1 AS connection_test").single()

    return {
        "status": "connected",
        "database": NEO4J_DATABASE,
        "test_value": record["connection_test"],
    }


def close_driver() -> None:
    """Close the driver when the application shuts down."""
    global _driver

    if _driver is not None:
        _driver.close()
        _driver = None
