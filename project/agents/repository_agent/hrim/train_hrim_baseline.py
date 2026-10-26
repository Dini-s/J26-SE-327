from pathlib import Path
import json

import joblib
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

OUTPUT_DIR = ROOT / "data" / "evaluation" / "hrim_baseline"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "java_files",
    "nonempty_lines",
    "fan_in",
    "fan_out",
    "total_coupling",
    "instability",
    "outgoing_dependency_count",
    "incoming_dependency_count",
]

TARGET = "architecture_change_proxy_label"
GROUP = "repository"


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Training dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    required = FEATURES + [TARGET, GROUP]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.dropna(subset=required).copy()

    X = df[FEATURES].apply(pd.to_numeric, errors="raise")
    y = df[TARGET].astype(int)
    groups = df[GROUP]

    if groups.nunique() < 5:
        raise ValueError(
            "At least 5 distinct repositories are required for 5-fold GroupKFold."
        )

    model = xgb.XGBClassifier(
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

    cv = GroupKFold(n_splits=5)

    # Generate predictions only when each sample's repository
    # is excluded from the fold used to predict it.
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

    metrics = {
        "samples": int(len(df)),
        "repositories": int(groups.nunique()),
        "positive_rate": float(y.mean()),
        "accuracy": float(accuracy_score(y, predictions)),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, probabilities)),
        "pr_auc": float(average_precision_score(y, probabilities)),
        "validation": "5-fold GroupKFold grouped by repository",
        "target": TARGET,
    }

    with open(OUTPUT_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4)

    oof = df[["sample_id", GROUP, "package_path", TARGET]].copy()
    oof["predicted_probability"] = probabilities
    oof["predicted_label"] = predictions
    oof.to_csv(OUTPUT_DIR / "oof_predictions.csv", index=False)

    model.fit(X, y)
    joblib.dump(model, OUTPUT_DIR / "xgboost_structural_proxy.joblib")

    importance = pd.DataFrame(
        {
            "feature": FEATURES,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)
    importance.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False)

    with open(OUTPUT_DIR / "feature_schema.json", "w", encoding="utf-8") as f:
        json.dump({"features": FEATURES, "target": TARGET}, f, indent=4)

    print("\n=== HRIM Structural Baseline Results ===")
    for key, value in metrics.items():
        print(f"{key}: {value}")

    print(f"\nSaved outputs to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
