import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = PROJECT_ROOT / "data" / "evaluation" / "hrim_shap_exploratory"

MODEL_PATH = MODEL_DIR / "hrim_a4_exploratory_model.json"
IMPUTER_PATH = MODEL_DIR / "hrim_a4_exploratory_imputer.joblib"
SCHEMA_PATH = MODEL_DIR / "feature_schema.json"

with SCHEMA_PATH.open("r", encoding="utf-8") as file:
    SCHEMA = json.load(file)

FEATURES = SCHEMA["features"]
TARGET = SCHEMA["target"]
FEATURE_GROUPS = SCHEMA["feature_groups"]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Required input not found: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _graph_features(
    packages: list[str],
    dependencies: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    """Calculate directed degree, PageRank and betweenness features."""
    nodes = list(dict.fromkeys(packages))
    node_set = set(nodes)
    adjacency = {node: set() for node in nodes}

    for _, row in dependencies.iterrows():
        source = str(row["source_package"])
        target = str(row["target_package"])

        if source in node_set and target in node_set:
            adjacency[source].add(target)

    incoming = {node: 0 for node in nodes}
    for source in nodes:
        for target in adjacency[source]:
            incoming[target] += 1

    outgoing = {node: len(adjacency[node]) for node in nodes}

    # PageRank with damping factor 0.85.
    n = len(nodes)
    ranks = {node: 1.0 / n for node in nodes} if n else {}

    for _ in range(100):
        dangling = sum(ranks[node] for node in nodes if not adjacency[node])
        updated = (
            {node: (1.0 - 0.85) / n + 0.85 * dangling / n for node in nodes}
            if n
            else {}
        )

        for source in nodes:
            if adjacency[source]:
                contribution = 0.85 * ranks[source] / len(adjacency[source])
                for target in adjacency[source]:
                    updated[target] += contribution

        if n and max(abs(updated[node] - ranks[node]) for node in nodes) < 1e-12:
            ranks = updated
            break
        ranks = updated

    # Brandes algorithm for directed, unweighted betweenness.
    centrality = {node: 0.0 for node in nodes}

    for source in nodes:
        stack = []
        predecessors = {node: [] for node in nodes}
        paths = {node: 0 for node in nodes}
        paths[source] = 1
        distance = {node: -1 for node in nodes}
        distance[source] = 0
        queue = [source]
        queue_index = 0

        while queue_index < len(queue):
            vertex = queue[queue_index]
            queue_index += 1
            stack.append(vertex)

            for neighbor in adjacency[vertex]:
                if distance[neighbor] < 0:
                    distance[neighbor] = distance[vertex] + 1
                    queue.append(neighbor)

                if distance[neighbor] == distance[vertex] + 1:
                    paths[neighbor] += paths[vertex]
                    predecessors[neighbor].append(vertex)

        dependency = {node: 0.0 for node in nodes}

        while stack:
            vertex = stack.pop()
            for predecessor in predecessors[vertex]:
                if paths[vertex]:
                    dependency[predecessor] += (paths[predecessor] / paths[vertex]) * (
                        1.0 + dependency[vertex]
                    )

            if vertex != source:
                centrality[vertex] += dependency[vertex]

    if n > 2:
        scale = 1.0 / ((n - 1) * (n - 2))
        centrality = {node: value * scale for node, value in centrality.items()}
    else:
        centrality = {node: 0.0 for node in nodes}

    return {
        node: {
            "graph_in_degree": incoming[node],
            "graph_out_degree": outgoing[node],
            "graph_total_degree": incoming[node] + outgoing[node],
            "graph_pagerank": ranks[node],
            "graph_betweenness": centrality[node],
        }
        for node in nodes
    }


def predict_multimodal_proxy_scores(
    repository_id: str,
    architecture_csv: Path,
    dependencies_csv: Path,
    semantic_csv: Path,
    repo_path: Path,
) -> list[dict]:
    """Generate exploratory multimodal proxy predictions per package."""
    for path in (MODEL_PATH, IMPUTER_PATH, SCHEMA_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required model artifact not found: {path}")

    architecture = _read_csv(architecture_csv)
    dependencies = _read_csv(dependencies_csv)
    semantic = _read_csv(semantic_csv)

    required_architecture = {
        "package_path",
        "java_files",
        "fan_in",
        "fan_out",
        "total_coupling",
        "instability",
    }
    required_semantic = {
        "package_path",
        *FEATURE_GROUPS["semantic"],
        *FEATURE_GROUPS["evolution"],
    }

    missing_arch = required_architecture - set(architecture.columns)
    missing_semantic = required_semantic - set(semantic.columns)

    if missing_arch:
        raise ValueError(f"Architecture CSV missing columns: {sorted(missing_arch)}")
    if missing_semantic:
        raise ValueError(f"Semantic CSV missing columns: {sorted(missing_semantic)}")
    if not {"source_package", "target_package"}.issubset(dependencies.columns):
        raise ValueError(
            "Dependency CSV must contain source_package and target_package."
        )

    if architecture["package_path"].duplicated().any():
        raise ValueError("Architecture CSV has duplicate package paths.")
    if semantic["package_path"].duplicated().any():
        raise ValueError("Semantic CSV has duplicate package paths.")

    architecture = architecture.set_index("package_path", drop=False)
    semantic = semantic.set_index("package_path", drop=False)

    # Only predict for packages present in both current analysis and
    # the precomputed semantic feature CSV.
    common_packages = [
        package for package in architecture.index if package in semantic.index
    ]

    if not common_packages:
        raise ValueError(
            "No package paths match between architecture and semantic CSVs. "
            "Generate aligned semantic features for this repository first."
        )

    graph = _graph_features(
        architecture.index.astype(str).tolist(),
        dependencies,
    )

    rows = []
    output_packages = []

    for package in common_packages:
        arch_row = architecture.loc[package]
        sem_row = semantic.loc[package]

        fan_in = int(float(arch_row["fan_in"]))
        fan_out = int(float(arch_row["fan_out"]))

        # Calculate non-empty lines from source files using package
        # declarations rather than assuming a Maven folder structure.
        nonempty_lines = 0
        for java_file in repo_path.rglob("*.java"):
            if any(
                part
                in {
                    ".git",
                    ".venv",
                    "venv",
                    "target",
                    "build",
                    "out",
                    "node_modules",
                }
                for part in java_file.parts
            ):
                continue

            try:
                source = java_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            declared_package = ""
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith("package ") and stripped.endswith(";"):
                    declared_package = stripped[8:-1].strip()
                    break

            if declared_package == package:
                nonempty_lines += sum(1 for line in source.splitlines() if line.strip())

        row = {
            "java_files": float(arch_row["java_files"]),
            "nonempty_lines": float(nonempty_lines),
            "fan_in": fan_in,
            "fan_out": fan_out,
            "total_coupling": float(arch_row["total_coupling"]),
            "instability": float(arch_row["instability"]),
            "outgoing_dependency_count": fan_out,
            "incoming_dependency_count": fan_in,
        }

        # Use evolution values from the supplied semantic feature table.
        for feature in FEATURE_GROUPS["evolution"]:
            row[feature] = pd.to_numeric(
                pd.Series([sem_row[feature]]), errors="coerce"
            ).iloc[0]

        row.update(graph[package])

        # Keep semantic feature names and values exactly as trained.
        for feature in FEATURE_GROUPS["semantic"]:
            row[feature] = pd.to_numeric(
                pd.Series([sem_row[feature]]), errors="coerce"
            ).iloc[0]

        rows.append(row)
        output_packages.append(package)

    X = pd.DataFrame(rows).reindex(columns=FEATURES)
    X = X.replace([np.inf, -np.inf], np.nan)

    if X.shape[1] != len(FEATURES):
        raise ValueError("Constructed feature count does not match schema.")

    imputer = joblib.load(IMPUTER_PATH)
    model = xgb.XGBClassifier()
    model.load_model(str(MODEL_PATH))

    if X.shape[1] != imputer.n_features_in_:
        raise ValueError("Feature count does not match saved imputer.")
    if X.shape[1] != model.get_booster().num_features():
        raise ValueError("Feature count does not match saved model.")

    X_imputed = imputer.transform(X)
    probabilities = model.predict_proba(X_imputed)
    classes = list(model.classes_)

    if 1 not in classes:
        raise ValueError("Model does not contain proxy class 1.")

    positive_index = classes.index(1)
    results = []

    for index, package in enumerate(output_packages):
        probability = float(probabilities[index, positive_index])

        results.append(
            {
                "repository_id": repository_id,
                "package_path": package,
                "proxy_probability": round(probability, 4),
                "predicted_proxy_label": int(probability >= 0.5),
                "target": TARGET,
                "model_type": "exploratory_multimodal_hrim",
                "feature_dimensions": len(FEATURES),
                "feature_groups": {
                    name: len(columns) for name, columns in FEATURE_GROUPS.items()
                },
                "temporal_alignment_verified": False,
                "interpretation": (
                    "Exploratory multimodal structural-change proxy prediction; "
                    "not validated architecture-drift detection."
                ),
            }
        )

    return results
