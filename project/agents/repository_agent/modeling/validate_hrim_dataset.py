import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA_FILE = ROOT / "data" / "processed" / "hrim_semantic_fused_features.csv"
REPORT_FILE = ROOT / "data" / "processed" / "hrim_validation_report.json"

KEYS = ["repository", "package_path"]


def main():
    df = pd.read_csv(DATA_FILE)

    semantic_cols = [
        c for c in df.columns if c.startswith("semantic_emb_")
    ]

    report = {
        "dataset": str(DATA_FILE.relative_to(ROOT)),
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "repositories": int(df["repository"].nunique()),
        "duplicate_package_keys": int(df.duplicated(KEYS).sum()),
        "semantic_dimensions": len(semantic_cols),
        "packages_with_semantic_embeddings": int(
            df["semantic_features_available"].sum()
        ),
        "packages_without_semantic_embeddings": int(
            (~df["semantic_features_available"]).sum()
        ),
        "missing_semantic_values": int(
            df[semantic_cols].isna().sum().sum()
        ),
        "missing_nonsemantic_columns": {
            str(k): int(v)
            for k, v in df.drop(
                columns=semantic_cols, errors="ignore"
            ).isna().sum().items()
            if v > 0
        },
        "target_columns_found": [
            c for c in df.columns
            if any(word in c.lower() for word in ("label", "target", "drift"))
        ],
    }

    report["validation_passed"] = (
        report["rows"] > 0
        and report["duplicate_package_keys"] == 0
        and report["semantic_dimensions"] == 768
        and report["packages_with_semantic_embeddings"]
        + report["packages_without_semantic_embeddings"]
        == report["rows"]
    )

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nValidation report saved to: {REPORT_FILE}")
    print(
        "\nNote: structural validation does not establish valid drift labels."
    )


if __name__ == "__main__":
    main()
