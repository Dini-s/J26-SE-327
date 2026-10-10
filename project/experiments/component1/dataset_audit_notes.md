# Component 1 — Dataset Audit Notes

## 1. Purpose

The purpose of this audit is to identify suitable datasets for the Requirement Intelligence Agent and assess their structure, labels, missing values, duplicates, and class balance before model training.

## 2. PURE Subset Dataset

- Total records: 11,440
- Columns: `id`, `sentence`, `security`, `reliability`, `NFR_boolean`
- Missing values: None
- Unique normalized sentences: 10,592
- Distinct repeated normalized sentences: 489
- Sentences with conflicting `NFR_boolean` labels: 6
- Sentences with conflicting `security` labels: 6
- Sentences with conflicting `reliability` labels: 0
- `NFR_boolean` positive records: 1,908
- `security` positive records: 1,882
- `reliability` positive records: 41

Note: The meanings and annotation rules for these labels must be confirmed from the dataset documentation.

## 3. PROMISE NFR Dataset

- Source file: `nfr.arff`
- Valid records: 625
- Recognized classes: 12
- Invalid or unrecognized records: 0
- Largest class: `F` — 255 records
- Smallest class: `PO` — 1 record

The dataset is imbalanced. Class-wise evaluation and an appropriate validation strategy will be required.

## 4. Initial Decisions

1. Do not modify the original datasets.
2. Investigate conflicting labels before removing or correcting records.
3. Prevent normalized duplicate requirements from appearing across training and test sets.
4. Verify label definitions and source documentation before training.
5. Establish a baseline model before considering fine-tuning.
6. Record dataset provenance and applicable licenses.

## 5. Next Actions

- Verify the label definitions in `pure_subset.csv`.
- Review the conflicting sentences and their source documents.
- Prepare a duplicate-aware train/test split.
- Train and evaluate a baseline NFR classifier.
- Report precision, recall, F1-score, and class-wise results.