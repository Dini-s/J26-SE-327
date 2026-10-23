from pathlib import Path

from agents.repository_agent.hrim.multimodal_inference_service import (
    predict_multimodal_proxy_scores,
)

root = Path(__file__).resolve().parent

results = predict_multimodal_proxy_scores(
    repository_id="R01_spring_petclinic",
    architecture_csv=(root / "data/architecture/R01_spring_petclinic_architecture.csv"),
    dependencies_csv=(root / "data/dependencies/R01_spring_petclinic_dependencies.csv"),
    semantic_csv=(
        root / "data/processed/semantic/"
        "R01_spring_petclinic_aligned_semantic_features.csv"
    ),
    repo_path=root / "data/raw/R01_spring_petclinic",
)

print("Predicted packages:", len(results))
for result in results:
    print(
        result["package_path"],
        result["proxy_probability"],
        result["predicted_proxy_label"],
        result["model_type"],
    )
