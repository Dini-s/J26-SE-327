
from pathlib import Path
import difflib

ROOT = Path(__file__).resolve().parents[2]

source = Path(
    r"C:\Users\shero\OneDrive - Sri Lanka Institute of Information Technology"
    r"\Research Project\DataSets\nfr\nfr.arff"
)
project = ROOT / "data" / "component1" / "raw" / "nfr.arff"

source_lines = source.read_text(
    encoding="utf-8-sig", errors="replace"
).splitlines()

project_lines = project.read_text(
    encoding="utf-8-sig", errors="replace"
).splitlines()

print("Source lines:", len(source_lines))
print("Project lines:", len(project_lines))
print("Source header:")
print("\n".join(source_lines[:15]))
print("\nProject header:")
print("\n".join(project_lines[:15]))

diff = list(difflib.unified_diff(
    source_lines,
    project_lines,
    fromfile="SOURCE nfr.arff",
    tofile="PROJECT nfr.arff",
    lineterm="",
))

print("\nDifferences (first 100 lines):")
print("\n".join(diff[:100]) if diff else "No line differences found.")
