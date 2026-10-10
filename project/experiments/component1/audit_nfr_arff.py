
from pathlib import Path
from collections import Counter

file_path = Path(
    r"C:\Users\shero\OneDrive - Sri Lanka Institute of Information Technology\Research Project\DataSets\nfr\nfr.arff"
)

counts = Counter()
total = 0
invalid_rows = 0

in_data_section = False

with file_path.open("r", encoding="cp1252") as file:
    for line in file:
        line = line.strip()

        if not line or line.startswith("%"):
            continue

        if line.lower() == "@data":
            in_data_section = True
            continue

        if not in_data_section:
            continue

        try:
            # The class label is the final comma-separated value.
            label = line.rsplit(",", 1)[-1].strip()

            if label not in {
                "F", "A", "L", "LF", "MN", "O",
                "PE", "SC", "SE", "US", "FT", "PO"
            }:
                invalid_rows += 1
                continue

            counts[label] += 1
            total += 1

        except Exception:
            invalid_rows += 1

print("=" * 50)
print("PROMISE NFR ARFF - CLASS DISTRIBUTION")
print("=" * 50)
print("Valid records:", total)
print("Invalid/unrecognized records:", invalid_rows)

print("\nClass counts and percentages:")

for label, count in sorted(counts.items()):
    percentage = count / total * 100 if total else 0
    print(f"{label:>3}: {count:>5} ({percentage:.2f}%)")

print("\nClasses found:", len(counts))
print("Original ARFF file was not modified.")
