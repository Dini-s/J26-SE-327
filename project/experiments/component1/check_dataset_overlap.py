
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "component1" / "processed"

TRAIN_FILE = PROCESSED_DIR / "nfr_labeled_parsed.csv"
TEST_FILE = PROCESSED_DIR / "test_labeled_parsed.csv"


def normalize(text):
    return " ".join(str(text).casefold().split())


def main():
    train = pd.read_csv(TRAIN_FILE)
    test = pd.read_csv(TEST_FILE)

    train["normalized"] = train["requirement"].map(normalize)
    test["normalized"] = test["requirement"].map(normalize)

    train_texts = set(train["normalized"])
    test_texts = set(test["normalized"])

    overlap = train_texts & test_texts

    print("=" * 55)
    print("DATASET OVERLAP AUDIT")
    print("=" * 55)
    print(f"Training records: {len(train)}")
    print(f"Test records: {len(test)}")
    print(f"Unique training requirements: {len(train_texts)}")
    print(f"Unique test requirements: {len(test_texts)}")
    print(f"Shared normalized requirements: {len(overlap)}")

    if overlap:
        train_overlap = train[train["normalized"].isin(overlap)]
        test_overlap = test[test["normalized"].isin(overlap)]

        output = pd.concat([train_overlap, test_overlap])
        output = output.drop(columns=["normalized"])
        output_path = PROCESSED_DIR / "dataset_overlap_report.csv"
        output.to_csv(output_path, index=False, encoding="utf-8-sig")

        print(f"Overlap details saved to: {output_path}")

    print("\nTraining label distribution:")
    print(train["label"].value_counts().sort_index().to_string())

    print("\nTest label distribution:")
    print(test["label"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
