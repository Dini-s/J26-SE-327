from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
)
from xgboost import XGBClassifier

ROOT = Path(".")
INPUT = ROOT / "data/processed/hrim_exploratory_multimodal_candidate.csv"
OUT = ROOT / "data/evaluation/hrim_multimodal_exploratory"
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(INPUT)
semantic_cols = [c for c in df.columns if c.startswith("semantic_emb_")]

# Restrict both models to identical rows with available semantic features.
df = df[
    df["fused_package_match"].eq(True) & df["semantic_features_available"].eq(True)
].copy()

if len(df) < 20 or df["repository"].nunique() < 2:
    raise SystemExit("Not enough semantic-available data for grouped evaluation.")

target = "architecture_change_proxy_label"
y = df[target].astype(int)
groups = df["repository"]

structural_cols = [
    c
    for c in [
        "previous_java_files",
        "previous_nonempty_lines",
        "previous_fan_in",
        "previous_fan_out",
        "previous_total_coupling",
        "previous_instability",
    ]
    if c in df.columns
]

# Use only numeric non-semantic features, excluding IDs, target, and labels.
exclude = {
    target,
    "repository",
    "package_path",
    "feature_snapshot_date",
    "label_observation_snapshot_date",
    "feature_commit_hash",
    "fused_package_match",
    "semantic_features_available",
    "semantic_snapshot_alignment_verified",
    "dataset_status",
    "target_name",
    "semantic_embedding_nonzero_count",
}
metadata_cols = {
    "evolution_status",
    "evolution_activity_status",
    "package_origin",
    "model_name",
}
other_numeric = [
    c
    for c in df.select_dtypes(include=[np.number]).columns
    if c not in exclude
    and c not in semantic_cols
    and c not in structural_cols
    and c not in metadata_cols
]
structural_cols = list(dict.fromkeys(structural_cols + other_numeric))

if not structural_cols:
    raise SystemExit("No structural/numeric features found.")

X_struct = df[structural_cols].replace([np.inf, -np.inf], np.nan)
X_multi = pd.concat(
    [X_struct, df[semantic_cols].replace([np.inf, -np.inf], np.nan)], axis=1
)

n_splits = min(5, groups.nunique())
cv = GroupKFold(n_splits=n_splits)


def evaluate(X, name):
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
            random_state=42,
            n_jobs=2,
        ),
    )
    probabilities = cross_val_predict(
        model, X, y, groups=groups, cv=cv, method="predict_proba", n_jobs=1
    )[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "model": name,
        "samples": len(y),
        "repositories": int(groups.nunique()),
        "features": X.shape[1],
        "accuracy": accuracy_score(y, predictions),
        "precision": precision_score(y, predictions, zero_division=0),
        "recall": recall_score(y, predictions, zero_division=0),
        "f1": f1_score(y, predictions, zero_division=0),
        "roc_auc": roc_auc_score(y, probabilities),
        "pr_auc": average_precision_score(y, probabilities),
        "validation": f"{n_splits}-fold GroupKFold by repository",
        "target": target,
        "temporal_alignment_verified": False,
    }


results = [
    evaluate(X_struct, "structural_only_same_semantic_subset"),
    evaluate(X_multi, "exploratory_multimodal_unverified_alignment"),
]

pd.DataFrame(results).to_csv(OUT / "comparison_metrics.csv", index=False)
(OUT / "comparison_metrics.json").write_text(
    json.dumps(results, indent=2), encoding="utf-8"
)
print(pd.DataFrame(results).to_string(index=False))
print(f"\nSaved results to: {OUT.resolve()}")
print("WARNING: exploratory only; historical semantic alignment is unverified.")
