"""Extract candidate requirements from the 76 extracted SRS text files (+ the 3 HTML documents when extraction is clean).

Writes (never overwrites a differing file):
  processed/srs_requirements_extracted.csv                     one row per candidate requirement
  audit_reports_component1/srs_requirements_per_document_counts.csv   per-document counts and suspicious-count flags

Extraction rules (a rule name is stored on every row):
  dropped: table-of-contents lines (dot leaders), repeated headers/footers, page numbers, headings, notes/examples,
           entries marked deleted;
  kept:    sentences containing shall / must / should / will / is|are required to        -> modal_sentence
           numbered or ID-tagged clauses that contain such a modal                       -> numbered_clause_modal
           numbered or ID-tagged sentence-like clauses without any modal (documents that
           never say "shall")                                                            -> numbered_clause_no_modal
The word "shall" is NOT required. candidate_type is FR/NFR only when a clear cue exists, otherwise "unknown".

Every row has boundary_status="auto_unverified"; the TCS document is additionally marked review_hold and, like all SRS rows,
is excluded from train/val/test splits (this table is not a labelled dataset). Originals are never altered: original_text is the
joined source lines, cleaned_text removes only markers/numbering labels and extra whitespace.

Deterministic and idempotent. Run from the project directory:
    ..\\.venv\\Scripts\\python.exe experiments\\component1\\build_srs_requirements.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root, for agents.requirement_agent
from build_master import AUDIT, COMPONENT, PROCESSED, RAW, collapse, write_safe  # noqa: E402

SRS_TEXT_DIR = PROCESSED / "srs_extracted_text"
HTML_DIR = RAW / "documents" / "html"
OUT_SRS = PROCESSED / "srs_requirements_extracted.csv"
OUT_COUNTS = AUDIT / "srs_requirements_per_document_counts.csv"
TCS_DOCUMENT = "1999 - tcs"

SRS_COLUMNS = ["srs_record_id", "source_document", "source_format", "position", "line_start", "clause_label", "source_marker",
               "original_text", "cleaned_text", "word_count", "candidate_type", "type_rule", "extraction_rule",
               "length_flag", "boundary_status", "review_hold", "excluded_from_splits", "is_synthetic"]

# Segmentation rules and regexes live in agents/requirement_agent/segmenter.py (shared with the requirement agent); HTML text extraction
# lives in agents/requirement_agent/ingestion.py.
from agents.requirement_agent.ingestion import html_to_text  # noqa: E402
from agents.requirement_agent.segmenter import extract_document, segment_document  # noqa: E402


def run():
    documents = []
    for path in sorted(SRS_TEXT_DIR.glob("*.txt")):
        documents.append((path.stem, path.read_bytes().decode("utf-8-sig", errors="replace"), "txt"))
    html_notes = []
    for path in sorted(HTML_DIR.glob("*")):
        if path.suffix.lower() in (".htm", ".html"):
            documents.append((path.stem, html_to_text(path), "html"))
    all_rows, count_rows = [], []
    for name, text, fmt in documents:
        rows, dropped, n_blocks = extract_document(name, text, fmt)
        words = len(text.split())
        modal_n = sum(r["extraction_rule"] in ("modal_sentence", "numbered_clause_modal") for r in rows)
        count_rows.append({
            "source_document": name, "source_format": fmt, "words": words, "blocks_examined": n_blocks, "rows_extracted": len(rows),
            "rows_modal": modal_n, "rows_numbered_no_modal": len(rows) - modal_n,
            "shall_in_text": len(re.findall(r"\bshall\b", text, re.I)), "rows_per_1000_words": round(len(rows) / max(words, 1) * 1000, 2),
            "dropped_toc_lines": dropped["toc_line"], "dropped_header_footer_lines": dropped["header_footer"],
            "dropped_page_numbers": dropped["page_number"], "dropped_headings": dropped["heading"],
            "dropped_notes_examples": dropped["note_or_example"], "dropped_deleted": dropped["deleted"],
            "dropped_no_cue": dropped["no_requirement_cue"] + dropped["numbered_not_sentence_like"] + dropped["too_short"],
            "over_20k_words": words > 20000, "review_hold": "tcs_manual_review_on_hold" if name == TCS_DOCUMENT else ""})
        for position, r in enumerate(rows, start=1):
            r["position"] = position
            r["review_hold"] = "tcs_manual_review_on_hold" if name == TCS_DOCUMENT else ""
            r["srs_record_id"] = f"SRS:{re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')}:{position:04d}"
            all_rows.append(r)
    counts = pd.DataFrame(count_rows)
    dens = counts[counts.rows_extracted > 0].rows_per_1000_words
    q1, q3 = dens.quantile(0.25), dens.quantile(0.75)
    fence = q3 + 3 * (q3 - q1)
    flags = []
    for _, c in counts.iterrows():
        notes = []
        if c.rows_extracted == 0:
            notes.append("zero_rows")
        if c.rows_per_1000_words > fence:
            notes.append(f"very_high_density(>{fence:.1f}/1k words)")
        if c.rows_extracted > 1500:
            notes.append("very_many_rows")
        if c.shall_in_text == 0 and c.rows_extracted > 0:
            notes.append("no_shall_in_document")
        if c.words < 2000:
            notes.append("very_short_document")
        if c.words >= 2000 and c.rows_per_1000_words < 3:
            notes.append("very_low_density(<3/1k words)")
        flags.append(";".join(notes))
    counts["suspicious_count_flags"] = flags
    srs = pd.DataFrame(all_rows)
    srs["boundary_status"] = "auto_unverified"
    srs["excluded_from_splits"] = True
    srs["is_synthetic"] = False
    srs = srs[SRS_COLUMNS]
    return srs, counts


def main():
    srs, counts = run()
    write_safe(OUT_SRS, srs)
    write_safe(OUT_COUNTS, counts)
    print(counts[["source_document", "source_format", "words", "rows_extracted", "rows_modal", "rows_numbered_no_modal",
                  "shall_in_text", "suspicious_count_flags"]].to_string())
    print("total rows:", len(srs), "| documents:", len(counts), "| flagged:", int((counts.suspicious_count_flags != "").sum()))


if __name__ == "__main__":
    main()
