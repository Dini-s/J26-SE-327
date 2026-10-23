from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
)
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from xgboost import XGBClassifier


INPUT = Path("data/processed/hrim_exploratory_multimodal_candidate.csv")
OUT = Path("data/evaluation/hrim_ablation_exploratory")
OUT.mkdir(parents=True, exist_ok=True)

TARGET = "architecture_change_proxy_label"
SEED = 42

# Read existing data only.
df = pd.read_csv(INPUT)

semantic_cols = [c for c in df.columns if c.startswith("semantic_emb_")]


df = (
    df.loc[
        df["fused_package_match"].eq(True) & df["semantic_features_available"].eq(True)
    ]
    .copy()
    .reset_index(drop=True)
)

if df.empty:
    raise SystemExit("No rows with available semantic features.")

if df[TARGET].isna().any():
    raise SystemExit("Target contains missing values.")

y = df[TARGET].astype(int)
groups = df["repository"]

n_splits = min(5, groups.nunique())
if n_splits < 2:
    raise SystemExit("At least two repositories are required.")

# Define feature groups explicitly to avoid accidental label leakage.
structural_cols = [
    c
    for c in [
        "java_files",
        "nonempty_lines",
        "fan_in",
        "fan_out",
        "total_coupling",
        "instability",
        "outgoing_dependency_count",
        "incoming_dependency_count",
    ]
    if c in df.columns
]

evolution_cols = [
    c
    for c in [
        "commit_count",
        "contributor_count",
        "files_changed",
        "total_insertions",
        "total_deletions",
        "total_churn",
    ]
    if c in df.columns
]

graph_cols = [
    c
    for c in [
        "graph_in_degree",
        "graph_out_degree",
        "graph_total_degree",
        "graph_pagerank",
        "graph_betweenness",
    ]
    if c in df.columns
]

if not structural_cols:
    raise SystemExit("Expected historical structural columns were not found.")

# Exclude package/repository IDs, component IDs, availability flags,
# metadata, labels, and all semantic columns from non-semantic groups.
feature_sets = {
    "A1_structural": structural_cols,
    "A2_structural_semantic": structural_cols + semantic_cols,
    "A3_structural_evolution_graph": structural_cols + evolution_cols + graph_cols,
    "A4_full_exploratory_hrim": structural_cols
    + evolution_cols
    + graph_cols
    + semantic_cols,
}

# Ensure feature columns exist and have numeric data.
for name, cols in feature_sets.items():
    feature_sets[name] = list(
        dict.fromkeys(
            c for c in cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
        )
    )
    if not feature_sets[name]:
        raise SystemExit(f"No numeric features for {name}.")

# Materialize the exact same repository-grouped folds for every model.
cv = GroupKFold(n_splits=n_splits)
splits = list(cv.split(df, y, groups=groups))

results = []
all_predictions = []

print(f"Rows used: {len(df)}")
print(f"Repositories: {groups.nunique()}")
print(f"Folds: {n_splits}")
print(f"Structural features: {len(structural_cols)}")
print(f"Evolution features: {len(evolution_cols)}")
print(f"Graph features: {len(graph_cols)}")
print(f"Semantic dimensions: {len(semantic_cols)}")
print("\nRunning ablation experiments...")

for experiment, cols in feature_sets.items():
    X = df[cols].replace([np.inf, -np.inf], np.nan)

    model = make_pipeline(
        SimpleImputer(strategy="median"),
        XGBClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=SEED,
            n_jobs=2,
        ),
    )

    probabilities = cross_val_predict(
        model,
        X,
        y,
        groups=groups,
        cv=splits,
        method="predict_proba",
        n_jobs=1,
    )[:, 1]

    predictions = (probabilities >= 0.5).astype(int)

    metrics = {
        "experiment": experiment,
        "samples": len(df),
        "repositories": int(groups.nunique()),
        "features": len(cols),
        "accuracy": accuracy_score(y, predictions),
        "precision": precision_score(y, predictions, zero_division=0),
        "recall": recall_score(y, predictions, zero_division=0),
        "f1": f1_score(y, predictions, zero_division=0),
        "roc_auc": roc_auc_score(y, probabilities),
        "pr_auc": average_precision_score(y, probabilities),
        "validation": f"{n_splits}-fold GroupKFold by repository",
        "target": TARGET,
        "temporal_alignment_verified": False,
    }
    results.append(metrics)

    pred_frame = pd.DataFrame(
        {
            "experiment": experiment,
            "repository": groups.to_numpy(),
            "target": y.to_numpy(),
            "probability": probabilities,
            "prediction": predictions,
        }
    )
    # Include package identity for auditing, not as a model feature.
    if "package_path" in df.columns:
        pred_frame["package_path"] = df["package_path"].to_numpy()
    all_predictions.append(pred_frame)

    print(
        f"{experiment}: F1={metrics['f1']:.4f}, "
        f"ROC-AUC={metrics['roc_auc']:.4f}, "
        f"PR-AUC={metrics['pr_auc']:.4f}"
    )

results_df = pd.DataFrame(results)
results_df.to_csv(OUT / "ablation_metrics.csv", index=False)

pd.concat(all_predictions, ignore_index=True).to_csv(
    OUT / "ablation_oof_predictions.csv", index=False
)

(OUT / "ablation_report.json").write_text(
    json.dumps(
        {
            "dataset": str(INPUT),
            "rows": len(df),
            "repositories": int(groups.nunique()),
            "folds": n_splits,
            "feature_groups": {
                "structural": structural_cols,
                "evolution": evolution_cols,
                "graph": graph_cols,
                "semantic_dimensions": len(semantic_cols),
            },
            "results": results,
            "temporal_alignment_verified": False,
            "target_interpretation": "architecture-change proxy, not verified architecture drift",
            "warning": "Exploratory results: semantic embedding alignment to historical "
            "commits has not been verified.",
        },
        indent=2,
    ),
    encoding="utf-8",
)

print("\n=== Ablation results ===")
print(results_df.to_string(index=False))
print(f"\nSaved results to: {OUT.resolve()}")
