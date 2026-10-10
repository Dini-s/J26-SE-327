
from pathlib import Path

import pandas as pd
import torch
from sentence_transformers import SentenceTransformer, util

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "component1" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "component1" / "processed"
AUDIT_DIR = PROJECT_ROOT / "data" / "component1" / "audit_reports_component1"

USER_STORIES_DIR = RAW_DIR / "user_stories"

DATASETS = {
    "nfr_train": PROCESSED_DIR / "nfr_labeled_parsed.csv",
    "nfr_test": PROCESSED_DIR / "test_labeled_parsed.csv",
    "PURE": RAW_DIR / "pure_subset.csv",
}

MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"

# Initial screening threshold only; not a validated duplicate threshold.
SIMILARITY_THRESHOLD = 0.80
TOP_K = 3
BATCH_SIZE = 32


def normalize_column_name(name):
    return str(name).replace("\ufeff", "").strip().casefold()


def find_text_column(df):
    columns = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for candidate in (
        "requirement",
        "requirement_text",
        "sentence",
        "text",
        "user_story",
        "description",
    ):
        if candidate in columns:
            return columns[candidate]

    return None


def read_csv_safely(path):
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Unable to read CSV: {path}")


def load_user_stories():
    records = []

    if not USER_STORIES_DIR.exists():
        raise FileNotFoundError(
            f"User stories folder not found: {USER_STORIES_DIR}"
        )

    for path in sorted(USER_STORIES_DIR.glob("*.txt")):
        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            content = path.read_text(encoding="cp1252")

        for line_number, line in enumerate(content.splitlines(), start=1):
            text = line.strip()

            if text:
                records.append({
                    "story_text": text,
                    "story_file": path.name,
                    "story_line": line_number,
                })

    df = pd.DataFrame(records)

    if df.empty:
        raise ValueError("No user-story records were found.")

    # Remove repeated texts for efficiency, retaining the first source location.
    df["normalized"] = (
        df["story_text"]
        .str.casefold()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    df = df.drop_duplicates(subset="normalized").reset_index(drop=True)

    return df


def load_existing_datasets():
    frames = []

    for dataset_name, path in DATASETS.items():
        if not path.exists():
            print(f"WARNING: Missing dataset: {path}")
            continue

        df = read_csv_safely(path)
        text_column = find_text_column(df)

        if text_column is None:
            print(
                f"WARNING: No text column in {path.name}: "
                f"{df.columns.tolist()}"
            )
            continue

        records = pd.DataFrame({
            "dataset": dataset_name,
            "requirement_text": df[text_column].fillna("").astype(str),
        })

        records = records[
            records["requirement_text"].str.strip() != ""
        ].copy()

        # Preserve original row index for traceability to the source CSV.
        records["source_row"] = records.index
        frames.append(records)

        print(
            f"Loaded {dataset_name}: {len(records)} records "
            f"(text column: {text_column})"
        )

    if not frames:
        raise ValueError("No existing datasets could be loaded.")

    existing = pd.concat(frames, ignore_index=True)

    # Identical texts repeated across rows need not be embedded repeatedly.
    existing["normalized"] = (
        existing["requirement_text"]
        .str.casefold()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    existing = existing.drop_duplicates(
        subset=["dataset", "normalized"]
    ).reset_index(drop=True)

    return existing


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    stories = load_user_stories()
    existing = load_existing_datasets()

    print("\n" + "=" * 60)
    print("SEMANTIC OVERLAP AUDIT")
    print("=" * 60)
    print(f"Unique user stories: {len(stories)}")
    print(f"Unique existing dataset texts: {len(existing)}")
    print(f"Model: {MODEL_NAME}")
    print(f"Screening threshold: {SIMILARITY_THRESHOLD}")

    print("\nLoading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    story_texts = stories["story_text"].tolist()
    existing_texts = existing["requirement_text"].tolist()

    print("\nEncoding user stories...")
    story_embeddings = model.encode(
        story_texts,
        batch_size=BATCH_SIZE,
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    print("\nEncoding existing requirements...")
    existing_embeddings = model.encode(
        existing_texts,
        batch_size=BATCH_SIZE,
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    results = []

    # Process a small batch of stories at a time to limit memory usage.
    for start in range(0, len(stories), BATCH_SIZE):
        end = min(start + BATCH_SIZE, len(stories))

        scores = util.cos_sim(
            story_embeddings[start:end],
            existing_embeddings,
        )

        k = min(TOP_K, len(existing))

        top_scores, top_indices = torch.topk(
            scores,
            k=k,
            dim=1,
        )

        for local_idx in range(end - start):
            story_idx = start + local_idx

            for rank in range(k):
                score = float(top_scores[local_idx, rank].item())

                if score < SIMILARITY_THRESHOLD:
                    continue

                existing_idx = int(
                    top_indices[local_idx, rank].item()
                )

                story = stories.iloc[story_idx]
                requirement = existing.iloc[existing_idx]

                results.append({
                    "similarity_score": round(score, 4),
                    "rank_for_story": rank + 1,
                    "story_text": story["story_text"],
                    "story_file": story["story_file"],
                    "story_line": story["story_line"],
                    "matched_requirement": requirement["requirement_text"],
                    "matched_dataset": requirement["dataset"],
                    "matched_source_row": requirement["source_row"],
                })

        print(f"Compared user stories {start + 1}–{end}")

    report_path = AUDIT_DIR / "user_story_semantic_overlap.csv"

    columns = [
        "similarity_score",
        "rank_for_story",
        "story_text",
        "story_file",
        "story_line",
        "matched_requirement",
        "matched_dataset",
        "matched_source_row",
    ]

    report = pd.DataFrame(results, columns=columns)

    if not report.empty:
        report = report.sort_values(
            "similarity_score",
            ascending=False,
        )

    report.to_csv(
        report_path,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"Unique user stories checked: {len(stories)}")
    print(f"Existing dataset texts checked: {len(existing)}")
    print(f"Candidate pairs above threshold: {len(report)}")
    print(f"Report saved to: {report_path}")

    if not report.empty:
        print("\nTop 10 candidate pairs:")
        print(
            report[
                [
                    "similarity_score",
                    "matched_dataset",
                    "story_text",
                    "matched_requirement",
                ]
            ].head(10).to_string(index=False)
        )
    else:
        print(
            "\nNo candidate pairs exceeded the screening threshold. "
            "This does not prove semantic overlap is absent."
        )

    print(
        "\nIMPORTANT: Similarity scores are screening signals, "
        "not proof of duplicate requirements. Review candidate pairs "
        "manually before removing or relabeling any records."
    )


if __name__ == "__main__":
    main()
