from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]

INPUT_FILE = PROJECT_ROOT / "data" / "processed" / "hrim_package_features.csv"

OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "architecture_risk_baseline.csv"


def main():
    df = pd.read_csv(INPUT_FILE)

    # Rank packages relative to other packages in the dataset.
    # These are heuristic indicators, not learned predictions.
    df["coupling_percentile"] = df["total_coupling"].rank(pct=True)

    df["fan_out_percentile"] = df["fan_out"].rank(pct=True)

    df["instability_percentile"] = df["instability"].rank(pct=True)

    df["risk_score"] = (
        0.40 * df["coupling_percentile"]
        + 0.35 * df["fan_out_percentile"]
        + 0.25 * df["instability_percentile"]
    )

    df["risk_level"] = pd.cut(
        df["risk_score"],
        bins=[-0.001, 0.50, 0.80, 1.00],
        labels=["Low", "Medium", "High"],
        include_lowest=True,
    )

    columns = [
        "repository",
        "package_path",
        "total_coupling",
        "fan_in",
        "fan_out",
        "instability",
        "risk_score",
        "risk_level",
    ]

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df[columns].to_csv(OUTPUT_FILE, index=False)

    print(f"Packages analyzed: {len(df)}")
    print(f"Saved results to: {OUTPUT_FILE}")
    print("\nRisk-level counts:")
    print(df["risk_level"].value_counts().to_string())


if __name__ == "__main__":
    main()
