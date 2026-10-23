from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]

SHAP_FILE = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "hrim_shap_exploratory"
    / "package_shap_explanations.csv"
)


RECOMMENDATION_RULES = {
    "total_coupling": {
        "title": "Review package coupling",
        "action": (
            "Inspect the package's incoming and outgoing dependencies. "
            "Identify unnecessary dependencies before considering refactoring."
        ),
    },
    "fan_out": {
        "title": "Review outgoing dependencies",
        "action": (
            "Inspect the packages this module depends on and assess whether "
            "its responsibilities can be separated."
        ),
    },
    "fan_in": {
        "title": "Assess change impact",
        "action": (
            "Identify dependent packages and check whether changes to this "
            "module require coordinated modifications elsewhere."
        ),
    },
    "total_churn": {
        "title": "Inspect repository change history",
        "action": (
            "Review the files and commits contributing to this change volume. "
            "Check whether repeated changes indicate unstable responsibilities."
        ),
    },
    "files_changed": {
        "title": "Review frequently changed files",
        "action": (
            "Inspect the affected files and their change history to determine "
            "whether changes are concentrated in a small number of modules."
        ),
    },
    "graph_betweenness": {
        "title": "Inspect dependency-graph centrality",
        "action": (
            "Review this package's dependency-graph position and assess "
            "whether changes could affect multiple parts of the repository."
        ),
    },
}


def get_package_recommendations(
    repository_id: str,
    package_path: str,
    limit: int = 5,
) -> dict:
    if not SHAP_FILE.exists():
        raise FileNotFoundError(f"SHAP results not found: {SHAP_FILE}")

    df = pd.read_csv(SHAP_FILE)

    required = {
        "repository",
        "package_path",
        "feature",
        "feature_value",
        "shap_value",
        "direction",
        "rank",
    }

    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"SHAP file is missing columns: {sorted(missing)}")

    matches = df[
        df["repository"].astype(str).eq(str(repository_id))
        & df["package_path"].astype(str).eq(str(package_path))
    ].copy()

    if matches.empty:
        return {
            "repository": repository_id,
            "package_path": package_path,
            "status": "unavailable",
            "message": (
                "No matching package explanation exists in the current "
                "SHAP output. Generate explanations for this package first."
            ),
            "recommendations": [],
        }

    matches["shap_value"] = pd.to_numeric(matches["shap_value"], errors="coerce")
    matches = matches.dropna(subset=["shap_value"])

    recommendations = []

    for _, row in matches.sort_values("shap_value", ascending=False).iterrows():
        feature = str(row["feature"])
        shap_value = float(row["shap_value"])

        # This rule applies to the binary target used by the
        # uploaded script: architecture_change_proxy_label.
        if shap_value <= 0:
            continue

        rule = RECOMMENDATION_RULES.get(feature)

        # Do not fabricate explanations for embedding dimensions
        # or features that have no validated recommendation rule.
        if rule is None:
            continue

        recommendations.append(
            {
                "title": rule["title"],
                "priority": "High" if shap_value >= 0.1 else "Medium",
                "action": rule["action"],
                "evidence": {
                    "feature": feature,
                    "feature_value": float(row["feature_value"]),
                    "shap_value": shap_value,
                    "direction": row["direction"],
                    "rank": int(row["rank"]),
                },
                "source": "SHAP",
                "validation_status": "candidate",
            }
        )

        if len(recommendations) >= limit:
            break

    return {
        "repository": repository_id,
        "package_path": package_path,
        "status": "available",
        "target": "architecture_change_proxy_label",
        "recommendations": recommendations,
    }
