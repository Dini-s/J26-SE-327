from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd
import shap
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.impute import SimpleImputer
from xgboost import XGBClassifier


ROOT = Path(__file__).resolve().parents[3]

INPUT = ROOT / "data/processed/hrim_exploratory_multimodal_candidate.csv"

OUT = ROOT / "data/evaluation/hrim_shap_exploratory"
OUT.mkdir(parents=True, exist_ok=True)

TARGET = "architecture_change_proxy_label"
SEED = 42
MAX_EXPLAIN_ROWS = 500
TOP_FEATURES = 25
TOP_PACKAGE_FEATURES = 5


if not INPUT.exists():
    raise FileNotFoundError(f"Dataset not found: {INPUT}")

df = pd.read_csv(INPUT)

df = (
    df.loc[
        df["fused_package_match"].eq(True) & df["semantic_features_available"].eq(True)
    ]
    .copy()
    .reset_index(drop=True)
)

if df.empty:
    raise SystemExit("No eligible samples found.")

if df[TARGET].isna().any():
    raise SystemExit("Target contains missing values.")

y = df[TARGET].astype(int)

if set(y.unique()) != {0, 1}:
    raise SystemExit("Expected binary target labels 0 and 1.")


semantic_cols = [c for c in df.columns if c.startswith("semantic_emb_")]

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

feature_groups = {
    "structural": structural_cols,
    "evolution": evolution_cols,
    "graph": graph_cols,
    "semantic": semantic_cols,
}

feature_cols = list(
    dict.fromkeys(structural_cols + evolution_cols + graph_cols + semantic_cols)
)

feature_cols = [
    c for c in feature_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
]

if not feature_cols:
    raise SystemExit("No numeric model features found.")

X = df[feature_cols].replace([np.inf, -np.inf], np.nan)


imputer = SimpleImputer(strategy="median")
X_imputed_array = imputer.fit_transform(X)

# SimpleImputer can drop entirely empty columns.
if X_imputed_array.shape[1] != len(feature_cols):
    raise ValueError(
        "Imputation changed the feature count. "
        "Inspect features containing only missing values."
    )

X_imputed = pd.DataFrame(
    X_imputed_array,
    columns=feature_cols,
    index=df.index,
)

model = XGBClassifier(
    n_estimators=100,
    max_depth=3,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="binary:logistic",
    eval_metric="logloss",
    random_state=SEED,
    n_jobs=2,
)

print(f"Samples: {len(df)}")
print(f"Repositories: {df['repository'].nunique()}")
print(f"Features: {len(feature_cols)}")
print("Fitting exploratory A4 model...")

model.fit(X_imputed, y)

# Save the fitted model and preprocessing for reproducibility.
model.save_model(str(OUT / "hrim_a4_exploratory_model.json"))

import joblib

joblib.dump(imputer, OUT / "hrim_a4_exploratory_imputer.joblib")

# COMPUTE SHAP VALUES
rng = np.random.default_rng(SEED)
sample_size = min(MAX_EXPLAIN_ROWS, len(df))

sample_indices = np.sort(rng.choice(len(df), size=sample_size, replace=False))

X_explain = X_imputed.iloc[sample_indices].copy()

print(f"Computing SHAP values for {len(X_explain)} samples...")

explainer = shap.TreeExplainer(model)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    explanation = explainer(X_explain)

shap_values = np.asarray(explanation.values)

# Accommodate APIs that return one SHAP matrix per class.
if shap_values.ndim == 3:
    shap_values = shap_values[:, :, 1]

if shap_values.shape != X_explain.shape:
    raise ValueError(
        f"Unexpected SHAP shape {shap_values.shape}; expected {X_explain.shape}"
    )

# GLOBAL FEATURE IMPORTANCE
global_importance = pd.DataFrame(
    {
        "feature": feature_cols,
        "mean_absolute_shap": np.abs(shap_values).mean(axis=0),
        "mean_signed_shap": shap_values.mean(axis=0),
    }
)

global_importance["feature_group"] = "other"

for group_name, columns in feature_groups.items():
    global_importance.loc[
        global_importance["feature"].isin(columns), "feature_group"
    ] = group_name

global_importance = global_importance.sort_values("mean_absolute_shap", ascending=False)

global_importance.to_csv(OUT / "global_shap_importance.csv", index=False)

global_importance.head(TOP_FEATURES).to_csv(OUT / "top_shap_features.csv", index=False)
# FEATURE-GROUP SUMMARY

group_rows = []

for group_name, columns in feature_groups.items():
    positions = [i for i, col in enumerate(feature_cols) if col in columns]

    if not positions:
        continue

    group_values = shap_values[:, positions]

    group_rows.append(
        {
            "feature_group": group_name,
            "feature_count": len(positions),
            "mean_absolute_shap_sum_per_sample": float(
                np.abs(group_values).sum(axis=1).mean()
            ),
            "mean_signed_shap_sum_per_sample": float(group_values.sum(axis=1).mean()),
        }
    )

group_summary = pd.DataFrame(group_rows).sort_values(
    "mean_absolute_shap_sum_per_sample",
    ascending=False,
)

group_summary.to_csv(OUT / "shap_feature_group_summary.csv", index=False)

# PACKAGE-LEVEL EXPLANATIONS

metadata_cols = [
    c
    for c in [
        "repository",
        "package_path",
        "package_origin",
    ]
    if c in df.columns
]

package_records = []

for local_i, original_i in enumerate(sample_indices):
    row = df.iloc[original_i]

    ranked_positions = np.argsort(np.abs(shap_values[local_i]))[::-1][
        :TOP_PACKAGE_FEATURES
    ]

    probability = float(model.predict_proba(X_imputed.iloc[[original_i]])[0, 1])

    for rank, position in enumerate(ranked_positions, start=1):
        feature = feature_cols[position]
        contribution = float(shap_values[local_i, position])

        record = {
            "repository": row.get("repository", ""),
            "package_path": row.get("package_path", ""),
            "target": int(y.iloc[original_i]),
            "predicted_probability": probability,
            "predicted_class": int(probability >= 0.5),
            "feature": feature,
            "feature_group": next(
                (
                    name
                    for name, columns in feature_groups.items()
                    if feature in columns
                ),
                "other",
            ),
            "feature_value": float(X_imputed.iloc[original_i][feature]),
            "shap_value": contribution,
            "direction": (
                "increases model output"
                if contribution > 0
                else "decreases model output"
            ),
            "rank": rank,
            "temporal_alignment_verified": False,
        }

        package_records.append(record)

package_explanations = pd.DataFrame(package_records)

package_explanations.to_csv(OUT / "package_shap_explanations.csv", index=False)
# VISUALIZATIONS
print("Creating SHAP plots...")

shap.summary_plot(
    shap_values,
    X_explain,
    max_display=TOP_FEATURES,
    show=False,
)
plt.tight_layout()
plt.savefig(
    OUT / "shap_summary.png",
    dpi=160,
    bbox_inches="tight",
)
plt.close()

shap.summary_plot(
    shap_values,
    X_explain,
    plot_type="bar",
    max_display=TOP_FEATURES,
    show=False,
)
plt.tight_layout()
plt.savefig(
    OUT / "shap_global_importance.png",
    dpi=160,
    bbox_inches="tight",
)
plt.close()

# REPORT
report = {
    "model": "XGBoost A4 exploratory HRIM",
    "input_dataset": str(INPUT.relative_to(ROOT)),
    "samples_in_dataset": int(len(df)),
    "samples_explained": int(len(X_explain)),
    "repositories": int(df["repository"].nunique()),
    "feature_count": int(len(feature_cols)),
    "target": TARGET,
    "target_interpretation": "Structural-change proxy; not verified architecture drift.",
    "training_scope": "Model fitted on the complete exploratory subset for explanation; "
    "these are not held-out explanations.",
    "temporal_alignment_verified": False,
    "warning": "Exploratory explanations only. Semantic embeddings have not been "
    "verified against the exact historical commits used for labels.",
    "top_features": global_importance.head(10).to_dict("records"),
    "feature_groups": group_summary.to_dict("records"),
    "outputs": [
        "hrim_a4_exploratory_model.json",
        "hrim_a4_exploratory_imputer.joblib",
        "global_shap_importance.csv",
        "top_shap_features.csv",
        "shap_feature_group_summary.csv",
        "package_shap_explanations.csv",
        "shap_summary.png",
        "shap_global_importance.png",
    ],
}

(OUT / "shap_report.json").write_text(
    json.dumps(report, indent=2, default=str),
    encoding="utf-8",
)

print("\nSHAP analysis completed.")
print("\nTop 10 features:")
print(global_importance.head(10).to_string(index=False))

print("\nFeature-group summary:")
print(group_summary.to_string(index=False))

print(f"\nResults saved to: {OUT}")
