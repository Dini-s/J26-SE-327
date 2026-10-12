
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "component1" / "raw"

files = {
    "Original source": RAW / "nfr_source_original.txt",
    "Existing project copy": RAW / "nfr_labeled.txt",
}

for name, path in files.items():
    counts = Counter()
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line and ":" in line:
                label = line.split(":", 1)[0].strip()
                counts[label] += 1

    print(f"\n{name}")
    print("File:", path.name)
    print("Non-empty labelled records:", sum(counts.values()))
    print("Label distribution:")
    for label, count in sorted(counts.items()):
        print(f"  {label}: {count}")
