"""Report how the new ingestion module compares with the existing pre-extracted SRS text files.

Reads (never modifies) raw/documents/srs/*.{pdf,rtf,doc} and processed/srs_requirements_extracted.csv and writes one new file
(never overwritten if different):
  audit_reports_component1/srs_ingestion_pdf_rtf_vs_txt.csv   per original document: format, supported?, words and candidate rows from
  the new ingestion path (pypdf / striprtf) versus the existing txt-based rows, and the share of identical cleaned texts.
Legacy .doc files are listed as unsupported (no extraction code); their pre-extracted text files remain the source for those documents.

Run from the project directory:  ..\.venv\Scripts\python.exe experiments\component1\report_srs_ingestion_formats.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from build_master import AUDIT, PROCESSED, RAW, write_safe  # noqa: E402
from agents.requirement_agent.ingestion import UnsupportedFormat, load_document  # noqa: E402
from agents.requirement_agent.segmenter import segment_document  # noqa: E402

OUT = AUDIT / "srs_ingestion_pdf_rtf_vs_txt.csv"


def key(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def main():
    srs = pd.read_csv(PROCESSED / "srs_requirements_extracted.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    rows = []
    for path in sorted((RAW / "documents" / "srs").iterdir()):
        name, suffix = path.stem, path.suffix.lower()
        ref = srs[srs.source_document == name]
        ref_keys = [key(t) for t in ref.cleaned_text]
        rec = {"document": name, "original_format": suffix.lstrip("."), "txt_rows": len(ref), "supported": "", "new_words": "", "new_rows": "",
               "rows_identical_to_txt_path": "", "share_of_txt_rows_found": "", "note": ""}
        try:
            text, fmt, warnings = load_document(path)
        except UnsupportedFormat as exc:
            rec.update(supported="no", note=str(exc).split(": ", 1)[-1][:120])
            rows.append(rec)
            continue
        new_rows, _, _ = segment_document(name, text, fmt)
        new_keys = [key(r["cleaned_text"]) for r in new_rows]
        found = len(set(ref_keys) & set(new_keys))
        rec.update(supported="yes", new_words=len(text.split()), new_rows=len(new_rows), rows_identical_to_txt_path=found,
                   share_of_txt_rows_found=round(found / max(len(set(ref_keys)), 1), 3), note="; ".join(warnings))
        rows.append(rec)
    df = pd.DataFrame(rows)
    write_safe(OUT, df)
    print(df.groupby(["original_format", "supported"]).size().to_string())
    ok = df[df.supported == "yes"]
    print("share of the existing txt-path rows reproduced by the new path: median", ok.share_of_txt_rows_found.astype(float).median(),
          "| documents with >=0.9:", int((ok.share_of_txt_rows_found.astype(float) >= 0.9).sum()), "of", len(ok))


if __name__ == "__main__":
    main()
