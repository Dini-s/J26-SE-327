from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"

INPUT_FILE = PROCESSED / "hrim_historical_training_baseline.csv"
OUTPUT_FILE = PROCESSED / "hrim_historical_loro_predictions.csv"
REPORT_FILE = PROCESSED / "hrim_historical_loro_metrics.csv"

FEATURES = [
    "previous_java_files",
    "previous_nonempty_lines",
    "previous_fan_in",
    "previous_fan_out",
    "previous_total_coupling",
    "previous_instability",
]
TARGET = "structural_change_proxy"
GROUP = "repository"


def safe_auc(y_true, probabilities):
    if len(np.unique(y_true)) < 2:
        return np.nan
    return roc_auc_score(y_true, probabilities)


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing dataset: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)

    required = set(FEATURES + [TARGET, GROUP])
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns: {required - set(df.columns)}")

    if df[FEATURES + [TARGET, GROUP]].isna().any().any():
        raise ValueError("Missing values found in training data.")

    repositories = sorted(df[GROUP].unique())
    prediction_frames = []
    fold_metrics = []

    for held_out_repo in repositories:
        train = df[df[GROUP] != held_out_repo].copy()
        test = df[df[GROUP] == held_out_repo].copy()

        if train[TARGET].nunique() < 2:
            print(f"Skipping {held_out_repo}: training fold has one class.")
            continue

        # This weighting is estimated from the training fold only.
        negatives = int((train[TARGET] == 0).sum())
        positives = int((train[TARGET] == 1).sum())
        scale_pos_weight = negatives / max(positives, 1)

        model = xgb.XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            n_estimators=300,
            max_depth=3,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            n_jobs=-1,
        )

        model.fit(train[FEATURES], train[TARGET])

        probabilities = model.predict_proba(test[FEATURES])[:, 1]
        predictions = (probabilities >= 0.5).astype(int)
        y_true = test[TARGET].to_numpy()

        fold_metrics.append(
            {
                "held_out_repository": held_out_repo,
                "train_examples": len(train),
                "test_examples": len(test),
                "test_positive": int(y_true.sum()),
                "precision": precision_score(y_true, predictions, zero_division=0),
                "recall": recall_score(y_true, predictions, zero_division=0),
                "f1": f1_score(y_true, predictions, zero_division=0),
                "pr_auc": average_precision_score(y_true, probabilities),
                "roc_auc": safe_auc(y_true, probabilities),
                "confusion_matrix_tn_fp_fn_tp": ",".join(
                    str(v)
                    for v in confusion_matrix(
                        y_true, predictions, labels=[0, 1]
                    ).ravel()
                ),
            }
        )

        prediction_frames.append(
            pd.DataFrame(
                {
                    "repository": held_out_repo,
                    "package_path": test["package_path"].to_numpy(),
                    "previous_snapshot": test["previous_snapshot"].to_numpy(),
                    "current_snapshot": test["current_snapshot"].to_numpy(),
                    "actual": y_true,
                    "probability": probabilities,
                    "predicted": predictions,
                }
            )
        )

        print(
            f"{held_out_repo}: test={len(test)}, "
            f"positives={int(y_true.sum())}, "
            f"F1={fold_metrics[-1]['f1']:.3f}, "
            f"PR-AUC={fold_metrics[-1]['pr_auc']:.3f}"
        )

    if not fold_metrics:
        raise RuntimeError("No valid repository-held-out folds were evaluated.")

    metrics = pd.DataFrame(fold_metrics)
    predictions = pd.concat(prediction_frames, ignore_index=True)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(REPORT_FILE, index=False)
    predictions.to_csv(OUTPUT_FILE, index=False)

    print("\nPer-repository held-out results:")
    print(metrics.to_string(index=False))

    print("\nUnweighted mean across held-out repositories:")
    print(
        metrics[["precision", "recall", "f1", "pr_auc", "roc_auc"]].mean().to_string()
    )

    print("\nSaved metrics:", REPORT_FILE)
    print("Saved predictions:", OUTPUT_FILE)
    print(
        "\nResearch limitation: this evaluates a six-feature baseline against "
        "a structural-change proxy, not independently verified architecture drift."
    )


if __name__ == "__main__":
    main()
