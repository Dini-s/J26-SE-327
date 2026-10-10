
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "component1" / "raw"
OUT = ROOT / "data" / "component1" / "audit_reports_component1"

FILE = RAW / "Cornelius_2025_user_story_ambiguity_dataset.xlsx"

LABELS = [
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
    df = pd.read_excel(FILE)

    df["normalized_story"] = (
        df["StoryText"]
        .fillna("")
        .astype(str)
        .str.casefold()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    df = df[df["normalized_story"] != ""].copy()

    grouped = df.groupby("normalized_story", dropna=False)

    duplicate_texts = grouped.filter(
        lambda group: len(group) > 1
    )

    conflict_groups = []

    for story, group in duplicate_texts.groupby("normalized_story"):
        conflicting_labels = {}

        for label in LABELS:
            values = group[label].dropna().unique()

            if len(values) > 1:
                conflicting_labels[label] = values.tolist()

        if conflicting_labels:
            conflict_groups.append({
                "normalized_story": story,
                "records": len(group),
                "conflicting_labels": str(conflicting_labels),
                "story_ids": str(group["StoryID"].tolist()),
                "company_ids": str(group["CompanyID"].tolist()),
                "project_ids": str(group["ProjectID"].tolist()),
            })

    conflicts = pd.DataFrame(conflict_groups)

    OUT.mkdir(parents=True, exist_ok=True)

    output = OUT / "cornelius_duplicate_label_conflicts.csv"
    conflicts.to_csv(output, index=False, encoding="utf-8-sig")

    print("=" * 60)
    print("CORNELIUS DUPLICATE LABEL CONFLICT AUDIT")
    print("=" * 60)
    print(f"Total records: {len(df)}")
    print(f"Unique normalized stories: {df['normalized_story'].nunique()}")
    print(f"Records in duplicate groups: {len(duplicate_texts)}")
    print(f"Duplicate groups with label conflicts: {len(conflicts)}")
    print(f"Report saved to: {output}")

    if not conflicts.empty:
        print("\nFirst 10 conflict groups:")
        print(conflicts.head(10).to_string(index=False))
    else:
        print("\nNo conflicting labels found in duplicate groups.")


if __name__ == "__main__":
    main()
