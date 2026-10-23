from dotenv import load_dotenv

load_dotenv()

from agents.repository_agent.services.neo4j_service import (
    verify_connection,
)

if __name__ == "__main__":
    print(verify_connection())