
from pathlib import Path
import re
import pandas as pd

ROOT = Path("project/data/component1/raw")
OUT = Path("project/data/component1/audit_reports_component1")

# Canonical category -> source column name
SCHEMA = {
    "DS1.xlsx": {
        "text": "Requirement_text",
        "subjective": "Subjective_lang.",
        "ambiguous": "Ambiguous_adv._adj.",
        "loophole": "Loophole",
        "open_ended": "Nonverifiable_term",
        "superlative": "Superlative",
        "comparative": "Comparative",
        "negative": "Negative",
        "vague_pronoun": "Vague_pron.",
        "uncertain_verb": "Uncertain_verb",
        "polysemy": "Polysemy",
    },
    "DS2.xlsx": {
        "text": "text",
        "subjective": "subjective_language",
        "ambiguous": "ambiguous_adverbs_adjectives",
        "loophole": "loopholes",
        "open_ended": "open_ended",
        "superlative": "superlatives",
        "comparative": "comparatives",
        "negative": "negative_statements",
        "vague_pronoun": "vague_pronouns",
    },
    "DS3.xlsx": {
        "text": "text",
        "subjective": "subjective_language",
        "ambiguous": "ambiguous_adverbs_adjectives",
        "loophole": "loopholes",
        "open_ended": "open_ended",
        "superlative": "superlatives",
        "comparative": "comparatives",
        "negative": "negative_statements",
        "vague_pronoun": "vague_pronouns",
    },
    "DS4.xlsx": {
        "text": "Requirement",
        "subjective": "Subjective Language",
        "ambiguous": "Ambiguouse_adverb_and_adjective",
        "loophole": "looples",
        "open_ended": "Open ended NonVarifiable",
        "superlative": "superlative",
        "comparative": "Compratives",
        "negative": "negative_sentence",
        "vague_pronoun": "vague_pronuns",
    },
}


def normalize(text):
    text = str(text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def annotation_present(value):
    """Provisional interpretation: '-' / blank = no annotation."""
    if pd.isna(value):
        return pd.NA

    value = str(value).strip()

    if value in {"", "-"}:
        return 0

    return 1


frames = []

for filename, mapping in SCHEMA.items():
    df = pd.read_excel(ROOT / filename)

    out = pd.DataFrame({
        "source_file": filename,
        "source_row": range(2, len(df) + 2),
        "requirement": df[mapping["text"]].fillna("").astype(str),
    })

    out["normalized_requirement"] = out["requirement"].map(normalize)

    for category, column in mapping.items():
        if category == "text":
            continue

        out[f"{category}_raw"] = df[column]
        out[category] = df[column].map(annotation_present)

    out = out[out["normalized_requirement"] != ""].copy()
    frames.append(out)

all_data = pd.concat(frames, ignore_index=True, sort=False)

# Compare only requirements appearing in different source files.
source_counts = all_data.groupby(
    "normalized_requirement"
)["source_file"].nunique()

duplicate_texts = source_counts[source_counts > 1].index

duplicates = all_data[
    all_data["normalized_requirement"].isin(duplicate_texts)
].copy()

duplicates.to_csv(
    OUT / "arta_standardized_duplicate_records.csv",
    index=False,
    encoding="utf-8-sig",
)

# Compare labels only where at least two available annotations exist.
categories = list(dict.fromkeys(
    category
    for mapping in SCHEMA.values()
    for category in mapping
    if category != "text"
))

conflicts = []

for requirement, group in duplicates.groupby("normalized_requirement"):
    for category in categories:
        available = group.dropna(subset=[category])

        # Need at least two rows from different datasets.
        if available["source_file"].nunique() < 2:
            continue

        values = sorted(available[category].astype(int).unique())

        if len(values) > 1:
            conflicts.append({
                "normalized_requirement": requirement,
                "category": category,
                "sources": "; ".join(
                    sorted(available["source_file"].unique())
                ),
                "values_found": "; ".join(map(str, values)),
                "records_compared": len(available),
                "details": " | ".join(
                    f"{row.source_file}, row {row.source_row}: "
                    f"{getattr(row, category + '_raw', '')}"
                    for row in available.itertuples(index=False)
                ),
            })

conflict_df = pd.DataFrame(conflicts)

conflict_df.to_csv(
    OUT / "arta_standardized_label_conflicts.csv",
    index=False,
    encoding="utf-8-sig",
)

print("Total source rows:", len(all_data))
print("Cross-dataset duplicate requirement groups:", len(duplicate_texts))
print("Duplicate records:", len(duplicates))
print("Potential label conflicts:", len(conflict_df))
print("\nReports saved:")
print(OUT / "arta_standardized_duplicate_records.csv")
print(OUT / "arta_standardized_label_conflicts.csv")
print("\nNote: Label presence is a provisional interpretation.")
