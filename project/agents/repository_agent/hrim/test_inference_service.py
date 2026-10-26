import sys
from pathlib import Path

# Add the project root to Python's module search path.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.repository_agent.hrim.inference_service import (
    predict_package_proxy_scores,
)

repository_id = "8db60cb6-9543-4731-9cc2-60a4b8524715"

repository_path = PROJECT_ROOT / "data" / "user_repositories" / repository_id

architecture_csv = (
    PROJECT_ROOT / "data" / "architecture" / f"{repository_id}_architecture.csv"
)

predictions = predict_package_proxy_scores(
    repository_id=repository_id,
    architecture_csv=architecture_csv,
    repo_path=repository_path,
)

print(f"\nPackages predicted: {len(predictions)}")

for prediction in predictions:
    print(prediction)
