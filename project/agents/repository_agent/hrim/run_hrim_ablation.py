from pathlib import Path
import json

import pandas as pd
import xgboost as xgb

from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
)

ROOT = Path(__file__).resolve().parents[3]

DATA_PATH = ROOT / "data" / "labels" / "hrim_historical_training_table_v1.csv"

OUTPUT_DIR = ROOT / "data" / "evaluation" / "hrim_ablation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALL_FEATURES = [
    "java_files",
    "nonempty_lines",
    "fan_in",
    "fan_out",
    "total_coupling",
    "instability",
    "outgoing_dependency_count",
    "incoming_dependency_count",
]

ABLATION_FEATURES = [
    feature
    for feature in ALL_FEATURES
    if feature
    not in {
        "outgoing_dependency_count",
        "fan_out",
    }
]

TARGET = "architecture_change_proxy_label"
GROUP = "repository"


def create_model():
    return xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )


def evaluate_model(df, features, experiment_name):
    X = df[features].apply(pd.to_numeric, errors="raise")
    y = df[TARGET].astype(int)
    groups = df[GROUP]

    model = create_model()
    cv = GroupKFold(n_splits=5)

    probabilities = cross_val_predict(
        model,
        X,
        y,
        groups=groups,
        cv=cv,
        method="predict_proba",
        n_jobs=1,
    )[:, 1]

    predictions = (probabilities >= 0.5).astype(int)

    results = {
        "experiment": experiment_name,
        "feature_count": len(features),
        "features": features,
        "samples": len(df),
        "repositories": int(groups.nunique()),
        "accuracy": float(accuracy_score(y, predictions)),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, probabilities)),
        "pr_auc": float(average_precision_score(y, probabilities)),
    }

    pred_df = df[["sample_id", GROUP, "package_path", TARGET]].copy()
    pred_df["predicted_probability"] = probabilities
    pred_df["predicted_label"] = predictions

    pred_df.to_csv(
        OUTPUT_DIR / f"{experiment_name}_oof_predictions.csv",
        index=False,
    )

    return results


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    required = ALL_FEATURES + [TARGET, GROUP, "sample_id", "package_path"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df = df.dropna(subset=required).copy()

    if df[GROUP].nunique() < 5:
        raise ValueError("At least five repositories are required.")

    results = [
        evaluate_model(df, ALL_FEATURES, "full_baseline"),
        evaluate_model(df, ABLATION_FEATURES, "without_top_two"),
    ]

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_DIR / "comparison.csv", index=False)

    with open(OUTPUT_DIR / "comparison.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    display_columns = [
        "experiment",
        "feature_count",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "pr_auc",
    ]

    print("\n=== HRIM Feature Ablation Comparison ===")
    print(results_df[display_columns].to_string(index=False))
    print(f"\nResults saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
