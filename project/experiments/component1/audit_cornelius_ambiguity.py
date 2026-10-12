
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "component1" / "raw"
OUT = ROOT / "data" / "component1" / "audit_reports_component1"

FILES = [
    "Cornelius_2025_user_story_ambiguity_dataset.xlsx",
    "Cornelius_research_subsets.xlsx",
]

LABEL_COLUMNS = [
    "HasAmbiguity",
    "SemanticAmbiguity",
    "ScopeAmbiguity",
    "ActorAmbiguity",
    "AcceptanceAmbiguity",
    "DependencyAmbiguity",
    "PriorityAmbiguity",
    "TechnicalAmbiguity",
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    summaries = []
    distributions = []
    duplicate_reports = []

    for filename in FILES:
        path = RAW / filename
        if not path.exists():
            print(f"Missing: {filename}")
            continue

        df = pd.read_excel(path)
        print(f"\n{'=' * 60}")
        print(filename)
        print(f"Rows: {len(df)}")

        for column in LABEL_COLUMNS:
            if column not in df.columns:
                continue

            counts = df[column].value_counts(dropna=False)

            for value, count in counts.items():
                distributions.append({
                    "file": filename,
                    "column": column,
                    "value": str(value),
                    "count": int(count),
                })

            print(f"\n{column}:")
            print(counts.to_string())

        if "StoryText" in df.columns:
            text = df["StoryText"].fillna("").astype(str).str.strip()
            normalized = (
                text.str.casefold()
                .str.replace(r"\s+", " ", regex=True)
            )

            nonempty = normalized != ""
            duplicate_mask = (
                normalized.duplicated(keep=False) & nonempty
            )

            print(f"\nEmpty StoryText: {(~nonempty).sum()}")
            print(f"Duplicate text records: {duplicate_mask.sum()}")
            print(f"Unique non-empty stories: {normalized[nonempty].nunique()}")

            dup = df.loc[duplicate_mask].copy()
            if not dup.empty:
                dup.insert(0, "source_file", filename)
                duplicate_reports.append(dup)

        if {"CompanyID", "ProjectID"}.issubset(df.columns):
            print(f"Unique companies: {df['CompanyID'].nunique()}")
            print(f"Unique projects: {df['ProjectID'].nunique()}")

        summaries.append({
            "file": filename,
            "rows": len(df),
            "columns": len(df.columns),
            "missing_cells": int(df.isna().sum().sum()),
            "duplicate_full_rows": int(df.duplicated().sum()),
        })

    pd.DataFrame(summaries).to_csv(
        OUT / "cornelius_dataset_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(distributions).to_csv(
        OUT / "cornelius_label_distributions.csv",
        index=False,
        encoding="utf-8-sig",
    )

    if duplicate_reports:
        pd.concat(
            duplicate_reports,
            ignore_index=True,
        ).to_csv(
            OUT / "cornelius_duplicate_stories.csv",
            index=False,
            encoding="utf-8-sig",
        )

    print("\nAudit reports saved in:")
    print(OUT)


if __name__ == "__main__":
    main()
