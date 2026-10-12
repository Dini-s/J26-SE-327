
from pathlib import Path
import pandas as pd
import re
import string

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_ROOT / "data" / "component1" / "processed"
RAW_DIR = PROJECT_ROOT / "data" / "component1" / "raw"
AUDIT_DIR = PROJECT_ROOT / "data" / "component1" / "audit_reports_component1"

TRAIN_FILE = PROCESSED_DIR / "nfr_labeled_parsed.csv"
TEST_FILE = PROCESSED_DIR / "test_labeled_parsed.csv"
PURE_FILE = RAW_DIR / "pure_subset.csv"
USER_STORIES_DIR = RAW_DIR / "user_stories"

REPORT_FILE = AUDIT_DIR / "user_story_existing_dataset_overlap.csv"


def normalize(text):
    """Normalize text for case-insensitive, whitespace-insensitive comparison."""
    if pd.isna(text):
        return ""

    text = str(text).casefold().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.translate(str.maketrans("", "", string.punctuation))

    return text.strip()


def find_text_column(df):
    """Find a likely requirement-text column, ignoring BOM and case."""
    candidates = [
        "requirement",
        "requirement_text",
        "sentence",
        "text",
        "user_story",
        "description",
    ]

    normalized_columns = {
        str(column).replace("\ufeff", "").strip().casefold(): column
        for column in df.columns
    }

    for candidate in candidates:
        if candidate in normalized_columns:
            return normalized_columns[candidate]

    return None


def read_csv_safely(file_path):
    """Read CSV while handling common encodings."""
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(file_path, encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Could not read CSV: {file_path}")


def load_existing_dataset(file_path, dataset_name):
    """Load a dataset and return normalized requirement records."""
    if not file_path.exists():
        print(f"WARNING: File not found: {file_path}")
        return pd.DataFrame()

    df = read_csv_safely(file_path)
    text_column = find_text_column(df)

    if text_column is None:
        print(
            f"WARNING: No recognized text column in {file_path.name}: "
            f"{list(df.columns)}"
        )
        return pd.DataFrame()

    df = df.copy()
    df["requirement_text"] = df[text_column].fillna("").astype(str)
    df["normalized"] = df["requirement_text"].map(normalize)
    df["dataset"] = dataset_name

    # Empty text cannot provide a meaningful overlap comparison.
    df = df[df["normalized"] != ""]

    print(
        f"Loaded {dataset_name}: {len(df)} records; "
        f"text column = {text_column}"
    )

    return df[["dataset", "requirement_text", "normalized"]]


def load_user_stories():
    """Read all TXT files in the user_stories folder."""
    records = []

    if not USER_STORIES_DIR.exists():
        print(f"WARNING: User stories folder not found: {USER_STORIES_DIR}")
        return pd.DataFrame(
            columns=["dataset", "requirement_text", "normalized"]
        )

    for file_path in sorted(USER_STORIES_DIR.glob("*.txt")):
        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="cp1252")

        for line_number, line in enumerate(text.splitlines(), start=1):
            line = line.strip()

            if not line:
                continue

            records.append(
                {
                    "dataset": "user_stories",
                    "requirement_text": line,
                    "normalized": normalize(line),
                    "source_file": file_path.name,
                    "source_line": line_number,
                }
            )

    stories = pd.DataFrame(records)

    if not stories.empty:
        stories = stories[stories["normalized"] != ""]

    print(f"Loaded user-story records: {len(stories)}")

    return stories


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing datasets.
    train = load_existing_dataset(TRAIN_FILE, "nfr_train")
    test = load_existing_dataset(TEST_FILE, "nfr_test")
    pure = load_existing_dataset(PURE_FILE, "PURE")

    # Load the 22 user-story TXT files.
    stories = load_user_stories()

    existing_parts = [df for df in [train, test, pure] if not df.empty]

    if not existing_parts or stories.empty:
        print("\nERROR: One or more required datasets could not be loaded.")
        print("Check the file paths and column names.")
        return

    existing = pd.concat(existing_parts, ignore_index=True)

    story_texts = set(stories["normalized"])
    existing_texts = set(existing["normalized"])
    shared_texts = story_texts & existing_texts

    print("\n" + "=" * 60)
    print("USER STORY OVERLAP AUDIT")
    print("=" * 60)

    print(f"User-story records: {len(stories)}")
    print(f"Unique normalized user stories: {len(story_texts)}")
    print(f"Existing dataset records: {len(existing)}")
    print(f"Unique existing dataset texts: {len(existing_texts)}")
    print(f"Exact normalized matches: {len(shared_texts)}")

    # Save matching records from both sides for manual inspection.
    if shared_texts:
        story_matches = stories[
            stories["normalized"].isin(shared_texts)
        ].copy()

        existing_matches = existing[
            existing["normalized"].isin(shared_texts)
        ].copy()

        story_matches["match_side"] = "user_story"
        existing_matches["match_side"] = "existing_dataset"

        report = pd.concat(
            [story_matches, existing_matches],
            ignore_index=True,
            sort=False,
        )

        report.to_csv(
            REPORT_FILE,
            index=False,
            encoding="utf-8-sig",
        )

        print(f"Overlap details saved to: {REPORT_FILE}")
    else:
        print("No exact normalized matches were found.")
        print("No overlap report with matching records was generated.")

    # Show overlaps separately for each existing dataset.
    print("\nOverlap by dataset:")

    for dataset_name, dataset_df in existing.groupby("dataset"):
        dataset_texts = set(dataset_df["normalized"])
        dataset_overlap = story_texts & dataset_texts

        print(
            f"  {dataset_name}: "
            f"{len(dataset_overlap)} unique matching texts"
        )

    print("\nExisting dataset sizes:")
    for dataset_name, dataset_df in existing.groupby("dataset"):
        print(f"  {dataset_name}: {len(dataset_df)} records")

    # Print label distributions for the labeled NFR datasets.
    for dataset_name, file_path in [
        ("NFR Training", TRAIN_FILE),
        ("NFR Test", TEST_FILE),
    ]:
        if not file_path.exists():
            continue

        df = read_csv_safely(file_path)

        if "label" in df.columns:
            print(f"\n{dataset_name} label distribution:")
            print(df["label"].value_counts(dropna=False).sort_index().to_string())


if __name__ == "__main__":
    main()
