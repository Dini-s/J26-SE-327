"""Reproducible requirement-boundary audit of the 1999 TCS System/Subsystem Specification.

Read-only on the source PDF and the extracted text. Writes versioned (v3) reports to
data/component1/audit_reports_component1/ and refuses to overwrite them without --overwrite.

Run from the project directory:
    ..\\.venv\\Scripts\\python.exe experiments\\component1\\audit_tcs_requirement_boundaries.py
    ..\\.venv\\Scripts\\python.exe experiments\\component1\\audit_tcs_requirement_boundaries.py --update-tracker

Everything in the output is a rule-based or text-layer finding. Nothing is human- or
visually-verified; no page renderer is used. See the validation report for the exact claims.
"""
import argparse
import hashlib
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = PROJECT_ROOT / "data" / "component1" / "audit_reports_component1"
SRC_PDF = PROJECT_ROOT / "data" / "component1" / "raw" / "documents" / "srs" / "1999 - tcs.pdf"
SRC_TXT = PROJECT_ROOT / "data" / "component1" / "processed" / "srs_extracted_text" / "1999 - tcs.txt"
V2_REPORT = REPORT_DIR / "tcs_boundary_review_v2.csv"
TRACKER = REPORT_DIR / "dataset_suitability_tracker.csv"

VERSION = "v3"
OUT_TABLE = REPORT_DIR / f"tcs_boundary_review_{VERSION}.csv"
OUT_UNRESOLVED = REPORT_DIR / f"tcs_unresolved_issues_{VERSION}.csv"
OUT_SUMMARY = REPORT_DIR / f"tcs_boundary_audit_summary_{VERSION}.md"
OUT_VALIDATION = REPORT_DIR / f"tcs_boundary_validation_report_{VERSION}.md"
OUT_CHECKLIST = REPORT_DIR / f"tcs_manual_review_checklist_{VERSION}.csv"
SOURCE_FILE = "1999 - tcs.txt"

# Thresholds (characters of whitespace-collapsed candidate text)
LONG_CHARS = 500
VERY_SHORT_CHARS = 40
CONTEXT_CHARS = 60

MARKER_RE = re.compile(r"\[\s*SSS([^\[\]]{0,12})\]")
OBLIGATION_RE = re.compile(r"\b(shall|must|should)\b", re.I)
WEAK_MODAL_RE = re.compile(r"\b(will|may|can)\b", re.I)
DELETED_TOKEN = "**DELETED**"
ABBREVIATIONS = {"u.s", "e.g", "i.e", "etc", "no", "vs", "inc", "fig", "approx"}

FURNITURE_RE = re.compile(r"^(TCS 102Block 0 TCS102|Version 2\.0 2/12/99)$")
PAGENUM_RE = re.compile(r"^\d{1,3}$")
HEADING_RE = re.compile(r"^\d+(?:\.\d+)+\.?\s+[A-Z][^\r\n]{0,110}$")
TOP_HEADING_RE = re.compile(r"^(\d+\s+[A-Z][A-Z0-9 \-/&,()]{3,60}|Chapter\s+\d+\s+[A-Z][A-Za-z ]{3,60})$")
BULLET_RE = re.compile(r"^[•·▪●]\s*\S")
ENUM_RE = re.compile(r"^(\(?\d{1,2}\)|\d{1,2}\.|\(?[a-z]\)|Level \d+:)\s")
CAPTION_RE = re.compile(r"^(Table|Figure)\s+[\d.]+(?:-\d+)?\s+[A-Z]")
SHORT_ROW_RE = re.compile(r"^[A-Za-z0-9/&,()\-+. ]{1,45}$")


# ----------------------------------------------------------------------------- helpers
def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collapse(value):
    return re.sub(r"\s+", " ", value).strip()


def alnum_tail(value, n=CONTEXT_CHARS):
    return re.sub(r"[^a-z0-9]", "", value.lower())[-n:]


def parse_marker_inner(inner):
    """Return (normalized_digits, marker_format, normalization_status)."""
    if re.fullmatch(r"\d{3}", inner):
        return inner, "CLEAN", "EXACT"
    digits = re.sub(r"\D", "", inner)
    if re.fullmatch(r"[\d\s]+", inner) and len(digits) == 3:
        return digits, "WHITESPACE_IN_MARKER", "WHITESPACE_REMOVED"
    if re.fullmatch(r"[\d\s]+", inner) and len(digits) > 3:
        return digits[:3], "EXTRA_DIGITS", "HYPOTHESIS_FIRST_3_DIGITS_UNVERIFIED"
    return digits[:3], "NON_NUMERIC_OR_SHORT", "UNRESOLVED"


def find_markers(text):
    markers = []
    for order, match in enumerate(MARKER_RE.finditer(text), start=1):
        inner = match.group(1)
        digits, fmt, norm_status = parse_marker_inner(inner)
        markers.append({
            "source_order": order,
            "marker_start_char": match.start(),
            "marker_end_char": match.end(),
            "original_marker": match.group(0),
            "marker_inner": inner,
            "id_digits_raw": re.sub(r"\D", "", inner),
            "normalized_candidate_id": f"SSS{digits}" if len(digits) == 3 else "",
            "marker_format": fmt,
            "normalization_status": norm_status,
        })
    return markers


def split_lines(text, start, end):
    lines, pos = [], start
    while pos < end:
        nl = text.find("\n", pos, end)
        line_end = end if nl == -1 else nl + 1
        lines.append((pos, line_end, text[pos:line_end].strip()))
        pos = line_end
    return lines


def classify_line(stripped):
    if not stripped:
        return "BLANK"
    if FURNITURE_RE.match(stripped):
        return "FURNITURE"
    if PAGENUM_RE.match(stripped):
        return "PAGENUM"
    if DELETED_TOKEN in stripped:
        return "DELETED"
    if (HEADING_RE.match(stripped) or TOP_HEADING_RE.match(stripped)) \
            and not OBLIGATION_RE.search(stripped) and not stripped.endswith((".", ":")):
        return "HEADING"
    if CAPTION_RE.match(stripped) and not stripped.endswith(".") and not OBLIGATION_RE.search(stripped):
        return "CAPTION"
    if BULLET_RE.match(stripped):
        return "BULLET"
    if ENUM_RE.match(stripped):
        return "ENUM"
    if SHORT_ROW_RE.match(stripped) and not stripped.endswith((".", ":")):
        return "SHORT_ROW"
    return "TEXT"


def split_sentences(value):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])", value)
    merged = []
    for part in parts:
        if merged and merged[-1].rstrip(".").split(" ")[-1].lower().rstrip(".") in ABBREVIATIONS:
            merged[-1] += " " + part
        else:
            merged.append(part)
    return [p for p in merged if p.strip()]


# ----------------------------------------------------------------------------- span analysis
def analyse_span(text, start, end):
    """Analyse the text between the previous marker and this one (markers trail their text)."""
    lines = split_lines(text, start, end)
    kinds = [classify_line(s) for _, _, s in lines]

    furniture = sum(k in ("FURNITURE", "PAGENUM") for k in kinds)
    heading_idx = [i for i, k in enumerate(kinds) if k == "HEADING"]
    last_heading = heading_idx[-1] if heading_idx else -1

    # a wrapped heading line directly after the last heading is still heading
    body_from = last_heading + 1
    while body_from < len(lines) and kinds[body_from] in ("BLANK", "FURNITURE", "PAGENUM"):
        body_from += 1
    if last_heading >= 0 and body_from < len(lines) and kinds[body_from] == "SHORT_ROW" \
            and not lines[body_from][2].endswith((".", ":", ",")):
        nxt = body_from + 1
        while nxt < len(lines) and kinds[nxt] in ("BLANK", "FURNITURE", "PAGENUM"):
            nxt += 1
        if nxt < len(lines) and kinds[nxt] in ("TEXT", "SHORT_ROW", "BULLET", "ENUM"):
            body_from = nxt

    pre_lines = [(i, lines[i]) for i in range(0, max(last_heading, 0))
                 if kinds[i] not in ("BLANK", "FURNITURE", "PAGENUM", "HEADING")]
    body_idx = [i for i in range(body_from if last_heading >= 0 else 0, len(lines))
                if kinds[i] not in ("BLANK", "FURNITURE", "PAGENUM")]

    body_text = collapse(" ".join(lines[i][2] for i in body_idx))
    pre_text = collapse(" ".join(l[2] for _, l in pre_lines))
    headings = [lines[i][2] for i in heading_idx]

    # leading stray punctuation e.g. "." left over after "[SSS567]."
    stray = False
    m = re.match(r"^[.]\s+", body_text)
    if m and len(body_text) > 2:
        body_text, stray = body_text[m.end():], True

    body_kinds = [kinds[i] for i in body_idx]
    cand_start = lines[body_idx[0]][0] if body_idx else end
    cand_end = end
    return {
        "lines": lines, "kinds": kinds, "furniture_lines": furniture,
        "headings": headings, "body_text": body_text, "body_kinds": body_kinds,
        "pre_heading_text": pre_text, "stray_punct": stray,
        "cand_start": cand_start, "cand_end": cand_end,
        "first_kind_in_span": next((k for k in kinds if k not in ("BLANK", "FURNITURE", "PAGENUM")), None),
    }


def short_row_runs(body_kinds):
    run = best = 0
    for kind in body_kinds:
        run = run + 1 if kind == "SHORT_ROW" else 0
        best = max(best, run)
    return best


# ----------------------------------------------------------------------------- PDF cross-check
def load_pdf_pages(pdf_path):
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def load_second_engine_pages(pdf_path):
    exe = shutil.which("pdftotext")
    if not exe:
        return None, "pdftotext not found on PATH"
    proc = subprocess.run([exe, "-raw", "-enc", "UTF-8", str(pdf_path), "-"], capture_output=True)
    if proc.returncode != 0:
        return None, f"pdftotext exit {proc.returncode}"
    pages = proc.stdout.decode("utf-8", errors="replace").split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages, f"{exe}"


def prefix_context(pages, page_no, pos):
    """Text before a marker, reaching into the previous page when the marker opens its page."""
    previous = pages[page_no - 2][-400:] if page_no > 1 else ""
    return previous + "\n" + pages[page_no - 1][:pos]


def cross_check_markers(markers, pypdf_pages, second_pages):
    """Attach page number and second-engine agreement to each marker (by page + in-page index)."""
    page_tokens = []
    for page in pypdf_pages:
        page_tokens.append([(m.group(0), m.group(1), m.start()) for m in MARKER_RE.finditer(page)])
    flat = [t for tokens in page_tokens for t in tokens]
    sequence_matches = [t[0] for t in flat] == [m["original_marker"] for m in markers]

    second_tokens = None
    if second_pages is not None and len(second_pages) == len(pypdf_pages):
        second_tokens = [[(m.group(0), m.group(1), m.start()) for m in MARKER_RE.finditer(p)] for p in second_pages]

    order = 0
    for page_no, tokens in enumerate(page_tokens, start=1):
        for k, (tok, inner, pos) in enumerate(tokens):
            marker = markers[order]
            order += 1
            marker["pdf_page"] = page_no
            ctx1 = alnum_tail(prefix_context(pypdf_pages, page_no, pos))
            if second_tokens is None:
                marker["source_verification_status"] = "UNVERIFIED_SECOND_ENGINE_UNAVAILABLE"
                marker["second_engine_marker"] = ""
                continue
            page2 = second_tokens[page_no - 1]
            if len(page2) != len(tokens):
                marker["source_verification_status"] = "TEXT_LAYER_ENGINES_DISAGREE_MARKER_COUNT_ON_PAGE"
                marker["second_engine_marker"] = ""
                continue
            tok2, inner2, pos2 = page2[k]
            marker["second_engine_marker"] = tok2
            ctx2 = alnum_tail(prefix_context(second_pages, page_no, pos2))
            n = min(len(ctx1), len(ctx2))
            digits_agree = re.sub(r"\D", "", inner) == re.sub(r"\D", "", inner2)
            if not digits_agree:
                status = "TEXT_LAYER_ENGINES_DISAGREE_ID"
            elif n < 15:
                status = "TEXT_LAYER_TWO_ENGINE_ID_AGREE_CONTEXT_TOO_SHORT"
            elif ctx1[-n:] == ctx2[-n:]:
                status = "TEXT_LAYER_TWO_ENGINE_ID_AND_CONTEXT_AGREE"
            else:
                status = "TEXT_LAYER_TWO_ENGINE_ID_AGREE_CONTEXT_DIFFERS"
            marker["source_verification_status"] = status
    return sequence_matches


# ----------------------------------------------------------------------------- classification
def build_rows(text, markers):
    spans = []
    for i, m in enumerate(markers):
        start = markers[i - 1]["marker_end_char"] if i else max(0, m["marker_start_char"] - 6000)
        spans.append(analyse_span(text, start, m["marker_start_char"]))

    # continuation (clause-chain) detection
    continuation = []
    for i, sp in enumerate(spans):
        first_line = next((l[2] for l, k in zip(sp["lines"], sp["kinds"])
                           if k not in ("BLANK", "FURNITURE", "PAGENUM")), "")
        prev_body = spans[i - 1]["body_text"] if i else ""
        lower_cont = bool(re.match(r"^[a-z]", first_line)) and not prev_body.endswith((".", ":", "?", "!"))
        cont = sp["first_kind_in_span"] not in ("HEADING",) and (bool(re.match(r"^[,;]", first_line)) or lower_cont)
        continuation.append(cont if i else False)

    head_of = {}
    for i, cont in enumerate(continuation):
        if cont:
            head_of[i] = head_of[i - 1] if continuation[i - 1] else i - 1

    rows, parent_idx = [], {}
    list_parent = None
    for i, (m, sp) in enumerate(zip(markers, spans)):
        body = sp["body_text"]
        deleted_residue = re.sub(r"\*\*DELETED\*\*|[\d\s.,;:]", "", body)
        deleted_all = DELETED_TOKEN in body and deleted_residue == ""
        deleted_partial = DELETED_TOKEN in body and not deleted_all
        deleted_status = "DELETED_PLACEHOLDER" if deleted_all else ("DELETED_TEXT_PRESENT_WITH_OTHER_TEXT" if deleted_partial else "NONE")

        after = text[m["marker_end_char"]:m["marker_end_char"] + 3]
        period_after_marker = bool(re.match(r"^\.(\s|$)", after))
        sentences = split_sentences(body)
        oblig = OBLIGATION_RE.findall(body)
        weak = WEAK_MODAL_RE.findall(body)
        modal_flags = [bool(OBLIGATION_RE.search(s)) for s in sentences]
        modal_sentences = sum(modal_flags)
        runs = short_row_runs(sp["body_kinds"])
        has_caption = "CAPTION" in sp["body_kinds"]
        has_list = any(k in ("BULLET", "ENUM") for k in sp["body_kinds"])
        starts_with_list = bool(sp["body_kinds"]) and sp["body_kinds"][0] in ("BULLET", "ENUM")
        n = len(body)
        ends_ok = body.endswith((".", "?", "!")) or period_after_marker
        starts_ok = bool(re.match(r"^[A-Z0-9\"“(]", body))
        ends_with_lead = body.rstrip().endswith(":")
        first_item = re.search(r"\s(?:1\.|\(1\)|1\)|a\.|a\)|\(a\))\s", body)
        lead_plus_item = bool(first_item) and (body[:first_item.start()].rstrip().endswith(":")
                                               or "following" in body[:first_item.start()].lower())
        next_starts_list = (i + 1 < len(spans) and bool(spans[i + 1]["body_kinds"])
                            and spans[i + 1]["body_kinds"][0] in ("BULLET", "ENUM")
                            and not spans[i + 1]["headings"])
        last_sentence = ""
        reasons, flags = [], []

        if sp["headings"]:
            flags.append("HEADING_REMOVED_FROM_SPAN")
        if sp["pre_heading_text"]:
            flags.append("UNMARKED_TEXT_BEFORE_HEADING")
        if has_list:
            flags.append("LIST_LINES_IN_SEGMENT")
        if has_caption or runs >= 3:
            flags.append("TABLE_OR_FIGURE_LINES_IN_SEGMENT")
        if not deleted_all and n > LONG_CHARS:
            flags.append("LONG_SEGMENT")
        if not deleted_all and 0 < n < VERY_SHORT_CHARS:
            flags.append("VERY_SHORT_SEGMENT")
        if len(oblig) >= 2:
            flags.append("MULTIPLE_OBLIGATION_MODALS")
        if deleted_all or deleted_partial:
            flags.append("DELETED_MARKER_TEXT")
        if continuation[i]:
            flags.append("CLAUSE_CONTINUATION")
        if re.match(r"^(The|A|An)\s+(shall|must|should|will)\b", body):
            flags.append("MISSING_SUBJECT_IN_SOURCE_TEXT")
        if sp["stray_punct"]:
            flags.append("STRAY_LEADING_PUNCTUATION_REMOVED")
        if period_after_marker:
            flags.append("PERIOD_AFTER_MARKER")
        if sp["furniture_lines"]:
            flags.append("PAGE_FURNITURE_REMOVED")
        if sp["headings"]:
            list_parent = None

        # ---- boundary status (precedence order is part of the documented method)
        if deleted_all:
            status, rtype = "DELETED_REQUIREMENT", "DELETED_PLACEHOLDER"
            reasons.append("Segment contains only the **DELETED** placeholder; excluded from active candidates.")
        elif deleted_partial:
            status, rtype = "UNRESOLVED_MANUAL_REVIEW", "MIXED_DELETED_AND_OTHER_TEXT"
            reasons.append("**DELETED** appears together with other text; cannot tell what the marker covers.")
        elif not body:
            status, rtype = "UNRESOLVED_MANUAL_REVIEW", "MARKER_WITHOUT_TEXT"
            reasons.append("No text between the previous marker and this one after removing page furniture and headings.")
        elif continuation[i]:
            head = head_of[i]
            parent_idx[i] = head
            status, rtype = "LIST_ITEM_OR_CHILD_FRAGMENT", "CLAUSE_FRAGMENT_OF_PARENT_SENTENCE"
            reasons.append(f"Segment continues a sentence that begins at the segment ending in {markers[head]['original_marker']}; "
                           "it is a clause of that parent sentence, not a standalone requirement.")
        elif starts_with_list:
            status, rtype = "LIST_ITEM_OR_CHILD_FRAGMENT", "LIST_ITEM"
            if list_parent is not None:
                parent_idx[i] = list_parent
                reasons.append(f"Numbered/bulleted item; parent is the list-introducing segment ending in {markers[list_parent]['original_marker']}.")
            else:
                reasons.append("Numbered/bulleted item but no list-introducing segment was found before it; parent unknown.")
            if len(sentences) >= 2 and modal_sentences >= 1:
                reasons.append("Item also contains further sentences; scope of the marker is uncertain.")
        elif lead_plus_item:
            status = "MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT"
            if next_starts_list:
                rtype = "LIST_LEAD_PLUS_FIRST_ITEM"
                reasons.append("Segment holds a list-introducing sentence together with the first list item under one marker; "
                               "later items have their own markers and point here as parent.")
            else:
                rtype = "INLINE_ENUMERATION_IN_SENTENCE"
                reasons.append("Sentence contains an inline enumeration (1)/(2)/... under a single marker; "
                               "the items do not have separate markers.")
            last_sentence = sentences[-1] if sentences else ""
        elif has_caption or runs >= 3 or (has_list and modal_sentences == 0):
            status, rtype = "HEADING_OR_TABLE_CONTAMINATION", "SEGMENT_CONTAINS_TABLE_FIGURE_OR_LIST_ROWS"
            reasons.append("Segment includes table/figure caption, list or short-row lines; sentence boundary unreliable.")
        elif ends_with_lead and len(sentences) == 1 and modal_sentences >= 1:
            if next_starts_list:
                status, rtype = "PARENT_REQUIREMENT", "LIST_LEAD"
                reasons.append("Sentence introduces a list whose items sit in the next segment(s).")
            else:
                status, rtype = "UNRESOLVED_MANUAL_REVIEW", "LIST_LEAD_WITHOUT_LIST_ITEMS_IN_NEXT_SEGMENT"
                reasons.append("Sentence ends with ':' but the next segment does not start with list items (table, figure or text follows).")
        elif len(sentences) >= 2 and modal_sentences >= 1:
            status = "MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT"
            if modal_sentences == 1 and modal_flags[-1]:
                rtype = "UNMARKED_NARRATIVE_BEFORE_MARKED_SENTENCE"
                last_sentence = sentences[-1]
                reasons.append(f"{len(sentences)} sentences between markers; only the last contains shall/must/should. "
                               "The marker plausibly tags the last sentence (see proposed_marked_sentence), not confirmed.")
            elif modal_sentences == 1:
                rtype = "REQUIREMENT_WITH_FOLLOW_ON_TEXT"
                reasons.append(f"{len(sentences)} sentences between markers; the shall/must/should sentence is not last, "
                               "so the marker may cover follow-on elaboration.")
            else:
                rtype = "MULTIPLE_OBLIGATION_SENTENCES"
                reasons.append(f"{modal_sentences} sentences with shall/must/should under one marker.")
        elif len(sentences) >= 2:
            status, rtype = "UNRESOLVED_MANUAL_REVIEW", "MULTI_SENTENCE_NO_OBLIGATION_MODAL"
            reasons.append("Several sentences, none with shall/must/should.")
        elif len(oblig) >= 2:
            status, rtype = "MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT", "COMPOUND_OBLIGATIONS_IN_ONE_SENTENCE"
            reasons.append("Single sentence with two or more shall/must/should; may be a compound requirement.")
        elif not oblig:
            status, rtype = "UNRESOLVED_MANUAL_REVIEW", "NO_OBLIGATION_MODAL"
            reasons.append("No shall/must/should in segment; may be informational text or an implicit requirement.")
        elif not (ends_ok and starts_ok):
            status, rtype = "UNRESOLVED_MANUAL_REVIEW", "INCOMPLETE_SENTENCE_FORM"
            reasons.append("Segment does not both start like a sentence and end with sentence punctuation (including a period placed after the marker).")
        elif n > LONG_CHARS:
            status, rtype = "UNRESOLVED_MANUAL_REVIEW", "UNUSUAL_LENGTH"
            reasons.append(f"Single sentence of {n} chars exceeds {LONG_CHARS}; likely several statements.")
        elif len(body.split()) < 4:
            status, rtype = "UNRESOLVED_MANUAL_REVIEW", "UNUSUAL_LENGTH"
            reasons.append("Fewer than four words; too short to be a self-contained requirement.")
        else:
            status, rtype = "VALID_STANDALONE_CANDIDATE", "SINGLE_SENTENCE_WITH_OBLIGATION_MODAL"
            reasons.append("Single complete sentence with an obligation modal and no structural flags (rule-based only).")
            if n < VERY_SHORT_CHARS:
                reasons.append(f"Short ({n} chars) but complete.")
            if period_after_marker and not body.endswith("."):
                reasons.append("Sentence-ending period is printed after the marker.")

        # list-parent state for following items
        if rtype in ("LIST_LEAD", "LIST_LEAD_PLUS_FIRST_ITEM") or (
                ends_with_lead and next_starts_list and rtype not in ("LIST_ITEM", "DELETED_PLACEHOLDER")):
            list_parent = i
        elif rtype not in ("LIST_ITEM", "DELETED_PLACEHOLDER"):
            list_parent = None

        if "MISSING_SUBJECT_IN_SOURCE_TEXT" in flags:
            reasons.append("Sentence starts 'The shall'; subject missing in the PDF text layer itself. Not repaired.")
        if m["marker_format"] != "CLEAN":
            reasons.append(f"Marker format {m['marker_format']}: {m['original_marker']!r} -> {m['normalization_status']}.")

        rows.append({
            "source_file": SOURCE_FILE, "source_order": m["source_order"],
            "source_start_char": sp["cand_start"], "source_end_char": sp["cand_end"],
            "marker_start_char": m["marker_start_char"], "marker_end_char": m["marker_end_char"],
            "pdf_page": m.get("pdf_page", ""),
            "original_marker": m["original_marker"], "normalized_candidate_id": m["normalized_candidate_id"],
            "marker_format": m["marker_format"], "normalization_status": m["normalization_status"],
            "id_digits_raw": m["id_digits_raw"],
            "candidate_text": body, "candidate_chars": n,
            "boundary_status": status, "requirement_type": rtype,
            "parent_requirement_id": "", "child_marker_count": 0,
            "deleted_status": deleted_status,
            "sentence_count": len(sentences), "obligation_modal_count": len(oblig), "weak_modal_count": len(weak),
            "heuristic_flags": ";".join(flags) if flags else "NONE",
            "headings_removed": " | ".join(sp["headings"]),
            "unmarked_text_before_heading": sp["pre_heading_text"],
            "proposed_marked_sentence": last_sentence,
            "ocr_or_extraction_issue": "NONE" if m["marker_format"] == "CLEAN" else m["marker_format"],
            "source_verification_status": m.get("source_verification_status", ""),
            "second_engine_marker": m.get("second_engine_marker", ""),
            "visual_pdf_verification": "NOT_PERFORMED_NO_PAGE_RENDERER",
            "review_reason": " ".join(reasons),
        })

    # parents: clause-chain heads and list leads
    children = defaultdict(list)
    for child, head in parent_idx.items():
        children[head].append(child)
        rows[child]["parent_requirement_id"] = markers[head]["normalized_candidate_id"]
    for head, kids in children.items():
        row = rows[head]
        row["child_marker_count"] = len(kids)
        clause_kids = [k for k in kids if rows[k]["requirement_type"] == "CLAUSE_FRAGMENT_OF_PARENT_SENTENCE"]
        if clause_kids:
            end_marker = markers[kids[-1]]
            composite = collapse(" ".join(s for (_, _, s) in split_lines(text, spans[head]["cand_start"], end_marker["marker_end_char"])
                                          if classify_line(s) not in ("FURNITURE", "PAGENUM", "BLANK")))
            if row["boundary_status"] not in ("DELETED_REQUIREMENT",):
                row["boundary_status"], row["requirement_type"] = "PARENT_REQUIREMENT", "CLAUSE_CHAIN_HEAD"
                row["review_reason"] += (f" Followed by {len(clause_kids)} clause marker(s): "
                                         + ", ".join(markers[c]["original_marker"] for c in clause_kids)
                                         + "; the full requirement is the composite of the chain.")
        else:
            composite = collapse(" ".join([row["candidate_text"]] + [rows[k]["candidate_text"] for k in kids]))
            row["review_reason"] += f" {len(kids)} list item marker(s) point here as parent; composite text concatenates candidate_text values."
        row["parent_composite_text"] = composite
    for r in rows:
        r.setdefault("parent_composite_text", "")
    return rows, spans


def finish_rows(rows, v2, appendix_ids, markers):
    ids = [r["normalized_candidate_id"] for r in rows]
    counts = Counter(ids)
    prev_num = None
    for r in rows:
        nid = r["normalized_candidate_id"]
        num = int(nid[3:]) if nid else None
        if prev_num is None or num is None:
            note = "FIRST_OR_UNPARSED"
        elif num == prev_num + 1:
            note = "IN_SEQUENCE"
        elif num < prev_num:
            note = "OUT_OF_SEQUENCE_BACKWARD"
        else:
            note = f"OUT_OF_SEQUENCE_FORWARD_GAP_{num - prev_num}"
        r["id_sequence_note"] = note
        r["duplicate_normalized_id"] = counts[nid] > 1
        r["in_traceability_appendix"] = nid in appendix_ids
        prev_num = num if num is not None else prev_num

        v2row = v2.get(nid) if v2 is not None else None
        r["v2_present"] = v2row is not None
        r["v2_review_status"] = v2row["review_status"] if v2row is not None else ""
        r["v2_review_flags"] = v2row["review_flags"] if v2row is not None else ""

        # sequence-fit evidence for malformed IDs: is the 3-digit prefix otherwise unused?
        if r["marker_format"] == "EXTRA_DIGITS":
            others = [x for x in ids if x == nid]
            r["id_sequence_note"] += f";PREFIX_UNUSED_ELSEWHERE_IN_MARKERS={len(others) == 1}"

        # v2 flag disposition for the previously-flagged entries
        if v2row is not None and v2row["review_status"] == "MANUAL_REVIEW_REQUIRED":
            if r["boundary_status"] == "VALID_STANDALONE_CANDIDATE":
                r["v2_flag_disposition"] = "V2_FLAG_NOT_REPRODUCED_UNDER_V3_RULES"
            else:
                r["v2_flag_disposition"] = "V2_FLAG_CONFIRMED_AS_" + r["boundary_status"]
        elif v2row is not None:
            r["v2_flag_disposition"] = ("V2_UNFLAGGED_BUT_V3_FOUND_" + r["boundary_status"]
                                        if r["boundary_status"] != "VALID_STANDALONE_CANDIDATE" else "V2_UNFLAGGED_V3_AGREES")
        else:
            r["v2_flag_disposition"] = "NOT_IN_V2_MARKER_NOT_DETECTED_BY_V2"

        unresolved_marker = r["normalization_status"] not in ("EXACT", "WHITESPACE_REMOVED")
        engines_ok = r["source_verification_status"] == "TEXT_LAYER_TWO_ENGINE_ID_AND_CONTEXT_AGREE"
        r["eligible_as_standalone_candidate"] = (
            r["boundary_status"] == "VALID_STANDALONE_CANDIDATE" and not unresolved_marker
            and r["deleted_status"] == "NONE" and engines_ok
            and "MISSING_SUBJECT_IN_SOURCE_TEXT" not in r["heuristic_flags"])

        status = r["boundary_status"]
        if status == "DELETED_REQUIREMENT":
            action = "EXCLUDE_FROM_ACTIVE_CANDIDATES_DELETED"
        elif status == "PARENT_REQUIREMENT":
            action = "USE_COMPOSITE_PARENT_TEXT_NOT_SINGLE_SEGMENT_AFTER_SPOT_CHECK"
        elif status == "LIST_ITEM_OR_CHILD_FRAGMENT":
            action = "DO_NOT_USE_AS_STANDALONE_MERGE_WITH_PARENT_OR_EXCLUDE"
        elif status == "VALID_STANDALONE_CANDIDATE":
            action = ("PROVISIONAL_CANDIDATE_AFTER_SPOT_CHECK" if r["eligible_as_standalone_candidate"]
                      else "VERIFY_MARKER_AND_SOURCE_BEFORE_USE")
        elif status == "MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT":
            action = "MANUAL_SPLIT_OR_CONFIRM_MARKER_SCOPE"
        elif status == "HEADING_OR_TABLE_CONTAMINATION":
            action = "MANUAL_REVIEW_AGAINST_PDF_PAGE"
        else:
            action = "MANUAL_REVIEW_REQUIRED"
        r["recommended_action"] = action
        r["review_evidence"] = (
            f"pdf_page={r['pdf_page']}; verification={r['source_verification_status']}; "
            f"marker_chars={r['marker_start_char']}-{r['marker_end_char']}; "
            f"candidate_chars={r['source_start_char']}-{r['marker_start_char']}; id_sequence={r['id_sequence_note']}; "
            f"in_traceability_appendix={r['in_traceability_appendix']}")
        r["review_basis"] = "RULE_BASED_AUTOMATED_TEXT_LAYER_CHECK_NOT_HUMAN_VERIFIED"
    return rows


def parse_appendix_a(text):
    """Appendix A restates requirement text under an `SSS###` line of its own (ORD lines are skipped)."""
    start = text.find("APPENDIX A: Requirements Traceability Matrix")
    end = text.find("APPENDIX B: MAE Applicable", start) if start != -1 else -1
    if start == -1 or end == -1:
        return {}
    entries, current, buffer = defaultdict(list), None, []

    def flush():
        if current is not None:
            entries[current].append(collapse(" ".join(buffer)))

    for raw_line in text[start:end].split("\r\n"):
        line = raw_line.strip()
        if re.fullmatch(r"SSS\d{3}", line):
            flush()
            current, buffer = line, []
        elif re.match(r"ORD\d{3}\b", line) or line.startswith("ORD NUMBER") or re.match(r"^NUMBER\s+ORD", line):
            flush()
            current, buffer = None, []
        elif current is not None and line and not FURNITURE_APPENDIX_RE.match(line) and not PAGENUM_RE.match(line):
            buffer.append(line)
    flush()
    return dict(entries)


FURNITURE_APPENDIX_RE = re.compile(r"^(TCS Block 0 TCS 102|Version 2\.0 2/12/99)$")


def normalise_alnum(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def appendix_crosscheck(rows, entries):
    """Compare each segment with Appendix A's restatement of the same ID (in-document evidence, not visual)."""
    from difflib import SequenceMatcher
    for r in rows:
        texts = entries.get(r["normalized_candidate_id"], [])
        r["appendix_a_text"] = " || ".join(texts)
        if not texts:
            r["appendix_a_crosscheck"], r["appendix_a_similarity"] = "NO_APPENDIX_ENTRY", ""
            continue
        if not any(texts):
            r["appendix_a_crosscheck"], r["appendix_a_similarity"] = "APPENDIX_ENTRY_EMPTY", ""
            continue
        if all(re.fullmatch(r"\(?deleted\)?\.?", t, re.I) for t in texts):
            r["appendix_a_crosscheck"], r["appendix_a_similarity"] = "APPENDIX_SAYS_DELETED", ""
            continue
        options = {"candidate": r["candidate_text"], "proposed_sentence": r["proposed_marked_sentence"],
                   "parent_composite": r["parent_composite_text"]}
        best = ("", 0.0)
        for label, value in options.items():
            if not value:
                continue
            for t in texts:
                a, b = normalise_alnum(t), normalise_alnum(re.sub(r"\[\s*SSS[^\]]*\]", "", value))
                ratio = 1.0 if a == b else SequenceMatcher(None, a, b, autojunk=False).ratio()
                if ratio > best[1]:
                    best = (label, ratio)
        label, ratio = best
        r["appendix_a_similarity"] = f"{ratio:.3f}"
        cand = normalise_alnum(r["candidate_text"])
        app = [normalise_alnum(t) for t in texts]
        if ratio == 1.0:
            r["appendix_a_crosscheck"] = {"candidate": "APPENDIX_MATCHES_CANDIDATE",
                                          "proposed_sentence": "APPENDIX_MATCHES_PROPOSED_SENTENCE_ONLY",
                                          "parent_composite": "APPENDIX_MATCHES_PARENT_COMPOSITE"}[label]
        elif ratio >= 0.97:
            r["appendix_a_crosscheck"] = "APPENDIX_NEARLY_IDENTICAL"
        elif any(a and a in cand for a in app):
            r["appendix_a_crosscheck"] = "APPENDIX_TEXT_CONTAINED_IN_CANDIDATE"
        elif any(cand and cand in a for a in app):
            r["appendix_a_crosscheck"] = "CANDIDATE_CONTAINED_IN_APPENDIX_TEXT"
        elif ratio >= 0.85:
            r["appendix_a_crosscheck"] = "APPENDIX_SIMILAR_NOT_IDENTICAL"
        else:
            r["appendix_a_crosscheck"] = "APPENDIX_TEXT_DIFFERS"
    return rows


COLUMNS = [
    "source_file", "source_order", "source_start_char", "source_end_char", "marker_start_char", "marker_end_char",
    "pdf_page", "original_marker", "normalized_candidate_id", "marker_format", "normalization_status",
    "id_digits_raw", "candidate_text", "candidate_chars", "boundary_status", "requirement_type",
    "parent_requirement_id", "child_marker_count", "parent_composite_text", "deleted_status",
    "sentence_count", "obligation_modal_count", "weak_modal_count", "heuristic_flags", "headings_removed",
    "unmarked_text_before_heading", "proposed_marked_sentence", "ocr_or_extraction_issue",
    "source_verification_status", "second_engine_marker", "visual_pdf_verification",
    "id_sequence_note", "duplicate_normalized_id", "in_traceability_appendix",
    "appendix_a_crosscheck", "appendix_a_similarity", "appendix_a_text",
    "v2_present", "v2_review_status", "v2_review_flags", "v2_flag_disposition",
    "eligible_as_standalone_candidate", "open_issue_types", "open_issue_max_severity",
    "eligible_without_open_medium_or_high_issue",
    "composite_rule", "merged_source_ids", "merge_status",
    "review_reason", "review_evidence", "review_basis", "recommended_action",
]

SEVERITY_RANK = {"": 0, "INFO": 1, "LOW": 2, "MEDIUM": 3, "HIGH": 4}

# issue_type -> (severity, pdf_inspection_required, uncertainty, evidence that would resolve it, excluded_until_resolved)
ISSUE_POLICY = {
    "MARKER_ID_MALFORMED_EXTRA_DIGITS": (
        "HIGH", "YES",
        "The 5-6 digit token is identical in both text-layer engines, so the intended ID cannot be derived from the text layer. "
        "The first three digits fit the numeric sequence, but sequence alone is not accepted as proof.",
        "Read the printed marker on the PDF page; decide whether the trailing digits belong to the ID, are a stray counter or a footnote; record the ID.",
        "YES - row is never eligible while the ID is unverified"),
    "MISSING_SUBJECT_IN_SOURCE": (
        "HIGH", "YES",
        "The sentence begins 'The shall' in both engines. The original wording is preserved; no subject was inserted.",
        "Check the printed sentence. If the PDF shows the same gap it is a source defect; a person decides whether to exclude or annotate it.",
        "YES - row is never eligible while the wording defect is open"),
    "BOUNDARY_MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT": (
        "HIGH", "YES",
        "More than one statement, or narrative plus a requirement, sits between two markers; which part the trailing marker tags is not known.",
        "On the page, see which sentence(s) the marker follows and whether the narrative is a separate paragraph; compare with Appendix A where an entry exists.",
        "YES - status is not VALID_STANDALONE_CANDIDATE"),
    "BOUNDARY_HEADING_OR_TABLE_CONTAMINATION": (
        "HIGH", "YES",
        "Table, figure or list rows are inside the segment; extracted text order may differ from the visual layout.",
        "View the page layout and decide where the requirement sentence starts and ends.",
        "YES - status is not VALID_STANDALONE_CANDIDATE"),
    "BOUNDARY_UNRESOLVED_MANUAL_REVIEW": (
        "HIGH", "YES",
        "The rules could not classify the segment as a complete requirement (no obligation modal, incomplete sentence form or list lead without items).",
        "Read the passage on the page and decide whether it is a requirement, a lead-in or informational text.",
        "YES - status is not VALID_STANDALONE_CANDIDATE"),
    "FRAGMENT_PARENT_UNKNOWN": (
        "HIGH", "YES", "A list item or clause fragment has no identified parent.",
        "Identify the sentence the fragment belongs to on the page.", "YES"),
    "UNMARKED_OBLIGATION_TEXT_BEFORE_HEADING": (
        "HIGH", "YES", "Text with shall/must/should sits before a heading without any marker.",
        "Decide whether it is an unmarked requirement.", "NO row exclusion; candidate for a missing requirement"),
    "TEXT_LAYER_ENGINES_NOT_FULLY_AGREEING": (
        "HIGH", "YES", "The two text-layer engines disagree about this marker or its context.",
        "Read the marker on the page.", "YES - row is never eligible"),
    "DUPLICATE_NORMALIZED_ID": (
        "HIGH", "YES", "Two markers normalise to the same ID.", "Read both markers on the pages.", "YES"),
    "APPENDIX_A_WORDING_DIFFERS_FROM_BODY": (
        "MEDIUM", "OPTIONAL",
        "The body and Appendix A word this ID differently. Appendix A is a separately maintained copy, not ground truth; neither text is chosen automatically.",
        "Read both printed passages; a person decides which wording is canonical for this dataset or keeps both with provenance.",
        "NO - still mechanically eligible; the open issue is exposed in open_issue_types and eligible_without_open_medium_or_high_issue"),
    "ID_IN_APPENDIX_BUT_NO_BODY_MARKER": (
        "MEDIUM", "YES",
        "The ID is cited in Appendix A (not as Deleted) but no body marker carries it.",
        "Look for a lost or differently printed marker near the neighbouring IDs.", "N/A - no body row exists"),
    "ID_ABSENT_FROM_BODY_AND_APPENDIX": (
        "MEDIUM", "YES",
        "The ID lies inside the observed numeric range but has no body marker and no Appendix A entry. Absence from the appendix is not proof "
        "that a requirement never existed; it may be an unassigned number, a deleted item, a marker missing from the text layer, or content in an image.",
        "Inspect the neighbouring pages for a printed marker or content that the text layer lacks.", "N/A - no body row exists"),
    "ID_DELETED_PER_APPENDIX_NO_BODY_MARKER": (
        "INFO", "OPTIONAL",
        "Appendix A lists this ID as (Deleted) and the body has no marker; the two sources are consistent.",
        "Optional: confirm that the page shows no requirement for this ID.", "N/A - no body row exists"),
    "MARKER_SPACING_EXTRACTOR_DEPENDENT": (
        "LOW", "OPTIONAL",
        "The marker contains whitespace in the pypdf text layer. The ID is the digits with whitespace removed; where the second engine renders a clean marker "
        "it corroborates this, but both engines are reading the same text layer.",
        "Optionally confirm the printed marker on the page.", "NO - eligible when otherwise valid"),
}


def printed_page_hints(pages):
    """Lone 1-3 digit lines in a page's text layer; a hint only (never treated as verified)."""
    hints = {}
    for number, page in enumerate(pages, start=1):
        found = [line.strip() for line in page.splitlines() if re.fullmatch(r"\d{1,3}", line.strip())]
        hints[number] = "" if not found else (found[0] if len(found) == 1 else "AMBIGUOUS:" + "/".join(found[:4]))
    return hints


def add_merge_fields(rows):
    """Record how fragments relate to parents; derived composites stay separate from source text."""
    by_id = {r["normalized_candidate_id"]: r for r in rows}
    children = defaultdict(list)
    for r in rows:
        if r["parent_requirement_id"]:
            children[r["parent_requirement_id"]].append(r["normalized_candidate_id"])
    for r in rows:
        nid = r["normalized_candidate_id"]
        r["composite_rule"], r["merged_source_ids"], r["merge_status"] = "", "", "NOT_APPLICABLE"
        if nid in children:
            clause = r["requirement_type"] == "CLAUSE_CHAIN_HEAD"
            r["composite_rule"] = ("R1_CLAUSE_CHAIN_EXACT_SOURCE_SLICE" if clause
                                   else "R2_LIST_LEAD_PLUS_ITEMS_DERIVED_CONCATENATION")
            r["merged_source_ids"] = ";".join([nid] + children[nid])
            r["merge_status"] = "PROPOSED_PENDING_HUMAN_CONFIRMATION"
        elif r["requirement_type"] == "CLAUSE_FRAGMENT_OF_PARENT_SENTENCE":
            r["merge_status"] = "FRAGMENT_OF_PARENT_SENTENCE_NOT_STANDALONE"
        elif r["requirement_type"] == "LIST_ITEM":
            r["merge_status"] = "LIST_ITEM_INDEPENDENCE_UNDECIDED"
        elif r["boundary_status"] == "DELETED_REQUIREMENT":
            r["merge_status"] = "EXCLUDED_DELETED"
    return rows


def attach_open_issues(rows, issues):
    marker_issues = issues[issues.source_order.astype(str) != ""]
    by_order = defaultdict(list)
    for item in marker_issues.itertuples():
        by_order[int(item.source_order)].append((item.issue_type, item.severity))
    for r in rows:
        found = by_order.get(int(r["source_order"]), [])
        r["open_issue_types"] = ";".join(sorted({t for t, _ in found})) if found else "NONE"
        top = max((s for _, s in found), key=lambda s: SEVERITY_RANK[s], default="")
        r["open_issue_max_severity"] = top or "NONE"
        r["eligible_without_open_medium_or_high_issue"] = bool(r["eligible_as_standalone_candidate"]) and SEVERITY_RANK[top] < 3
    return rows


# ----------------------------------------------------------------------------- unresolved issues
def build_unresolved(rows, missing_ids, appendix_ids, appendix_entries, text, hints):
    issues = []

    def add(r, issue, needed):
        issues.append({
            "source_order": r["source_order"] if r else "", "original_marker": r["original_marker"] if r else "",
            "normalized_candidate_id": r["normalized_candidate_id"] if r else "", "pdf_page": r["pdf_page"] if r else "",
            "issue_type": issue, "boundary_status": r["boundary_status"] if r else "",
            "detail": (r["review_reason"] if r else ""), "verification_needed": needed,
            "candidate_text_excerpt": (r["candidate_text"][:240] if r else ""),
        })

    for r in rows:
        if r["normalization_status"] in ("HYPOTHESIS_FIRST_3_DIGITS_UNVERIFIED", "UNRESOLVED"):
            add(r, "MARKER_ID_MALFORMED_EXTRA_DIGITS",
                f"Open PDF page {r['pdf_page']} and read the printed marker; PDF text layer from two engines shows the same token.")
        if r["source_verification_status"] not in ("TEXT_LAYER_TWO_ENGINE_ID_AND_CONTEXT_AGREE",):
            add(r, "TEXT_LAYER_ENGINES_NOT_FULLY_AGREEING", "Compare engines output on the page: " + r["source_verification_status"])
        if "MISSING_SUBJECT_IN_SOURCE_TEXT" in r["heuristic_flags"]:
            add(r, "MISSING_SUBJECT_IN_SOURCE", "Check the PDF page; do not insert 'TCS' without a human decision.")
        if r["unmarked_text_before_heading"] and OBLIGATION_RE.search(r["unmarked_text_before_heading"]):
            add(r, "UNMARKED_OBLIGATION_TEXT_BEFORE_HEADING", "Decide whether this shall/must text is a requirement without a marker.")
        if r["boundary_status"] in ("UNRESOLVED_MANUAL_REVIEW", "MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT",
                                    "HEADING_OR_TABLE_CONTAMINATION"):
            add(r, "BOUNDARY_" + r["boundary_status"], "Human review of the PDF page to set the true requirement boundary.")
        if r["boundary_status"] == "LIST_ITEM_OR_CHILD_FRAGMENT" and not r["parent_requirement_id"]:
            add(r, "FRAGMENT_PARENT_UNKNOWN", "Identify the parent statement for this list item/fragment.")
        if r["normalization_status"] == "WHITESPACE_REMOVED" and r["source_verification_status"] != "TEXT_LAYER_TWO_ENGINE_ID_AND_CONTEXT_AGREE":
            add(r, "SPACED_MARKER_NOT_CORROBORATED", "Spaced marker not corroborated by second engine.")
        if r["duplicate_normalized_id"]:
            add(r, "DUPLICATE_NORMALIZED_ID", "Two markers normalise to the same ID.")
        if r["marker_format"] == "WHITESPACE_IN_MARKER":
            add(r, "MARKER_SPACING_EXTRACTOR_DEPENDENT",
                f"Marker {r['original_marker']!r} contains whitespace; second engine reads {r['second_engine_marker']!r}.")
        if r["appendix_a_crosscheck"] == "APPENDIX_TEXT_DIFFERS" and r["boundary_status"] in (
                "VALID_STANDALONE_CANDIDATE", "PARENT_REQUIREMENT"):
            add(r, "APPENDIX_A_WORDING_DIFFERS_FROM_BODY",
                f"Appendix A restates this ID with different wording (similarity {r['appendix_a_similarity']}); decide which text is canonical.")
    for mid in missing_ids:
        in_appendix = mid in appendix_ids
        appendix_deleted = bool(appendix_entries.get(mid)) and all(
            re.fullmatch(r"\(?deleted\)?\.?", t, re.I) for t in appendix_entries[mid])
        if appendix_deleted:
            issue, detail = ("ID_DELETED_PER_APPENDIX_NO_BODY_MARKER",
                             "Appendix A lists this ID as (Deleted) and the body has no marker: consistent, recorded for completeness.")
        elif in_appendix:
            issue, detail = ("ID_IN_APPENDIX_BUT_NO_BODY_MARKER",
                             "ID is cited in the traceability appendix but no marker carries it in the body text; a marker may be lost or the appendix stale.")
        else:
            issue, detail = ("ID_ABSENT_FROM_BODY_AND_APPENDIX",
                             "ID inside the observed numeric range has no marker in the body text and is not cited in the appendix; likely unassigned or removed.")
        issues.append({
            "source_order": "", "original_marker": "", "normalized_candidate_id": mid, "pdf_page": "",
            "issue_type": issue, "boundary_status": "",
            "detail": detail,
            "verification_needed": "Check the neighbouring PDF pages for a missing or renumbered requirement.", "candidate_text_excerpt": "",
        })
    frame = pd.DataFrame(issues)
    frame["_order"] = pd.to_numeric(frame["source_order"], errors="coerce").fillna(10 ** 9)
    frame = frame.sort_values(["_order", "normalized_candidate_id", "issue_type"]).drop(columns="_order").reset_index(drop=True)
    return enrich_issues(frame, rows, text, hints)


def enrich_issues(frame, rows, text, hints):
    """Add the per-issue fields a reviewer needs: location, context, uncertainty, evidence, exclusion."""
    by_order = {int(r["source_order"]): r for r in rows}
    by_num = {int(r["normalized_candidate_id"][3:]): r for r in rows if r["normalization_status"] in ("EXACT", "WHITESPACE_REMOVED")}
    extra = defaultdict(list)
    for column in ("severity", "pdf_inspection_required", "uncertainty", "resolving_evidence", "excluded_until_resolved",
                   "source_location", "printed_page_hint", "context_before", "context_after", "pdf_page"):
        extra[column] = []
    for item in frame.itertuples():
        severity, inspect_pdf, uncertainty, evidence, excluded = ISSUE_POLICY[item.issue_type]
        if item.source_order != "":
            r = by_order[int(item.source_order)]
            page = int(r["pdf_page"])
            before = collapse(text[max(0, r["marker_start_char"] - 260):r["marker_start_char"]])
            after = collapse(text[r["marker_end_char"]:r["marker_end_char"] + 160])
            location = (f"txt chars {r['marker_start_char']}-{r['marker_end_char']}; PDF page {page} "
                        f"(file index; printed-number hint {hints.get(page) or 'none'})")
        else:
            num = int(item.normalized_candidate_id[3:])
            lower = next((by_num[n] for n in range(num - 1, 0, -1) if n in by_num), None)
            upper = next((by_num[n] for n in range(num + 1, num + 40) if n in by_num), None)
            page = int(lower["pdf_page"]) if lower else (int(upper["pdf_page"]) if upper else 0)
            before = ("numeric neighbour below: " + lower["normalized_candidate_id"] + " ... "
                      + collapse(text[max(0, lower["marker_start_char"] - 120):lower["marker_end_char"]])) if lower else ""
            after = ("numeric neighbour above: " + upper["normalized_candidate_id"] + " ... "
                     + collapse(text[max(0, upper["marker_start_char"] - 120):upper["marker_end_char"]])) if upper else ""
            location = (f"no body marker; numeric neighbours {lower['normalized_candidate_id'] if lower else '-'} / "
                        f"{upper['normalized_candidate_id'] if upper else '-'}; nearest PDF page {page or 'unknown'} (neighbours may sit on other pages)")
        for column, value in (("severity", severity), ("pdf_inspection_required", inspect_pdf), ("uncertainty", uncertainty),
                              ("resolving_evidence", evidence), ("excluded_until_resolved", excluded),
                              ("source_location", location), ("printed_page_hint", hints.get(page, "")),
                              ("context_before", before), ("context_after", after), ("pdf_page", str(page) if page else "")):
            extra[column].append(value)
    for column, values in extra.items():
        frame[column] = values
    return frame



CHECKLIST_COLUMNS = [
    "review_id", "review_kind", "pdf_page_file_index", "printed_page_hint", "page_mapping_note", "source_order",
    "original_marker", "normalized_candidate_id", "group_ids", "issue_types", "max_severity", "automated_classification",
    "automated_proposal", "candidate_text", "appendix_a_text", "context_before", "context_after", "what_to_verify",
    "decision_options", "human_decision", "human_evidence", "reviewer", "review_date", "human_verified",
]

DECISION_OPTIONS = {
    "MARKER_ID_MALFORMED_EXTRA_DIGITS": "CONFIRM_ID:<printed id> | ID_UNREADABLE | OTHER:<note>",
    "MISSING_SUBJECT_IN_SOURCE": "SOURCE_DEFECT_CONFIRMED | PDF_SHOWS_SUBJECT:<text> | OTHER:<note>",
    "BOUNDARY_": "MARKER_COVERS_WHOLE_SEGMENT | MARKER_COVERS_LAST_SENTENCE_ONLY | SPLIT_NEEDED | NOT_A_REQUIREMENT | OTHER:<note>",
    "APPENDIX_A_WORDING_DIFFERS_FROM_BODY": "BODY_CANONICAL | APPENDIX_CANONICAL | KEEP_BOTH_WITH_PROVENANCE",
    "MARKER_SPACING_EXTRACTOR_DEPENDENT": "MARKER_CONFIRMED_AS:<printed id> | OTHER:<note>",
    "ID_": "NOTHING_PRINTED | REQUIREMENT_FOUND:<id and text> | OTHER:<note>",
    "MERGE_DECISION": "MERGE_AS_COMPOSITE | KEEP_ITEMS_INDEPENDENT | EXCLUDE | OTHER:<note>",
}


def decision_options_for(types):
    chosen = []
    for key, value in DECISION_OPTIONS.items():
        if any(t.startswith(key) or t == key for t in types) and value not in chosen:
            chosen.append(value)
    return " || ".join(chosen) or "OTHER:<note>"


def build_checklist(rows, issues, hints):
    """One row per marker needing a decision (issue or merge group) plus one per numbering gap. All decisions start PENDING."""
    by_order = {int(r["source_order"]): r for r in rows}
    marker_issues = issues[issues.source_order.astype(str) != ""]
    parent_orders = {int(r["source_order"]) for r in rows if int(r["child_marker_count"]) > 0}
    wanted = sorted(set(int(o) for o in marker_issues.source_order) | parent_orders)
    items = []
    for order in wanted:
        r = by_order[order]
        mine = marker_issues[marker_issues.source_order.astype(str) == str(order)]
        types = sorted(set(mine.issue_type))
        severities = list(mine.severity)
        steps = [ISSUE_POLICY[t][3] for t in types]
        kind = "MARKER_ISSUE"
        group = ""
        if order in parent_orders:
            kind = "MARKER_ISSUE+PARENT_MERGE_GROUP" if types else "PARENT_MERGE_GROUP"
            types = types + ["MERGE_DECISION"]
            severities.append("MEDIUM")
            group = r["merged_source_ids"]
            steps.append(f"Decide whether {r['composite_rule']} is acceptable for {group}; list items may be independent obligations, "
                         "clause fragments belong to one sentence.")
        page = int(r["pdf_page"])
        proposal = r["proposed_marked_sentence"] or r["parent_composite_text"]
        items.append({
            "review_kind": kind, "pdf_page_file_index": page, "printed_page_hint": hints.get(page, ""),
            "page_mapping_note": "File page index (pypdf, 1-based). The printed page number is only a text-layer hint; confirm on the page.",
            "source_order": r["source_order"], "original_marker": r["original_marker"],
            "normalized_candidate_id": r["normalized_candidate_id"], "group_ids": group, "issue_types": ";".join(types),
            "max_severity": max(severities, key=lambda v: SEVERITY_RANK[v]),
            "automated_classification": f"{r['boundary_status']} / {r['requirement_type']}",
            "automated_proposal": proposal, "candidate_text": r["candidate_text"], "appendix_a_text": r["appendix_a_text"],
            "context_before": collapse(AUDIT_TEXT[max(0, r["marker_start_char"] - 260):r["marker_start_char"]]),
            "context_after": collapse(AUDIT_TEXT[r["marker_end_char"]:r["marker_end_char"] + 160]),
            "what_to_verify": " ".join(dict.fromkeys(steps)), "decision_options": decision_options_for(types),
        })
    for gap in issues[issues.source_order.astype(str) == ""].itertuples():
        page = int(gap.pdf_page) if str(gap.pdf_page).isdigit() else 0
        items.append({
            "review_kind": "NUMBERING_GAP", "pdf_page_file_index": page, "printed_page_hint": gap.printed_page_hint,
            "page_mapping_note": "No marker exists: the page is the numeric neighbour's page; the gap may lie on an adjacent page.",
            "source_order": "", "original_marker": "", "normalized_candidate_id": gap.normalized_candidate_id, "group_ids": "",
            "issue_types": gap.issue_type, "max_severity": gap.severity, "automated_classification": "NO_BODY_MARKER",
            "automated_proposal": "", "candidate_text": "", "appendix_a_text": "", "context_before": gap.context_before,
            "context_after": gap.context_after, "what_to_verify": gap.resolving_evidence,
            "decision_options": decision_options_for([gap.issue_type]),
        })
    items.sort(key=lambda i: (i["pdf_page_file_index"] or 10 ** 6, int(i["source_order"]) if i["source_order"] != "" else 10 ** 6,
                              i["normalized_candidate_id"]))
    for number, item in enumerate(items, start=1):
        item["review_id"] = f"R{number:03d}"
        item.update({"human_decision": "PENDING", "human_evidence": "", "reviewer": "", "review_date": "", "human_verified": "NO"})
    return pd.DataFrame(items)[CHECKLIST_COLUMNS]


AUDIT_TEXT = ""  # set by main(); used for context excerpts


# ----------------------------------------------------------------------------- validation
def validate(rows, markers, text, seq_matches, issues, sources):
    df = pd.DataFrame(rows)
    checks = []

    def check(name, ok, detail):
        checks.append((name, bool(ok), detail))

    n = len(df)
    check("markers_detected_equals_rows", n == len(markers), f"{len(markers)} markers, {n} rows")
    check("source_order_contiguous_from_1", list(df.source_order) == list(range(1, n + 1)), "1..N in text order")
    check("marker_offsets_strictly_increasing",
          all(markers[i]["marker_start_char"] < markers[i + 1]["marker_start_char"] for i in range(n - 1)), "")
    check("original_marker_matches_source_slice",
          all(text[r["marker_start_char"]:r["marker_end_char"]] == r["original_marker"] for r in rows),
          "text[start:end] == original_marker for every row")
    check("candidate_offsets_inside_gap_before_marker",
          all(r["source_start_char"] <= r["marker_start_char"] and (r["source_start_char"] >= (rows[i - 1]["marker_end_char"] if i else 0))
              for i, r in enumerate(rows)), "candidate begins after previous marker and before this one")
    check("candidate_text_matches_slice_when_no_furniture_removed",
          all(collapse(text[r["source_start_char"]:r["marker_start_char"]]).lstrip(". ").strip() == r["candidate_text"]
              or "PAGE_FURNITURE_REMOVED" in r["heuristic_flags"] or "STRAY_LEADING_PUNCTUATION_REMOVED" in r["heuristic_flags"]
              for r in rows), "candidate_text is an unmodified (whitespace-collapsed) slice")
    nid = df.normalized_candidate_id
    check("all_rows_have_normalized_id", (nid != "").all(), f"{int((nid == '').sum())} blank")
    check("no_duplicate_normalized_ids", not df.duplicate_normalized_id.any(),
          f"{int(nid.duplicated().sum())} duplicates; unique={nid.nunique()}")
    check("no_duplicate_rows", not df.duplicated(subset=["source_order"]).any() and not df.duplicated(subset=["marker_start_char"]).any(), "")
    required = ["boundary_status", "requirement_type", "review_reason", "source_verification_status", "recommended_action", "review_evidence"]
    check("required_fields_non_empty", all((df[c].astype(str).str.len() > 0).all() for c in required), ", ".join(required))
    check("marker_sequence_identical_in_pdf_text_layer_and_txt", seq_matches, "pypdf page-wise tokens == txt tokens")
    check("txt_equals_pypdf_text_layer_modulo_whitespace", sources["txt_equals_pypdf"], "whitespace-normalised equality")
    earlier = sources["earlier_audit"]
    check("extracted_text_unchanged_since_earlier_quality_audit",
          earlier is None or all(earlier),
          "SKIPPED: no row for this file in srs_extracted_text_quality_audit.csv" if earlier is None else
          f"characters match={earlier[0]}, words match={earlier[1]}, sha256(whitespace-collapsed text) match={earlier[2]}")
    check("every_deleted_row_excluded_from_eligible",
          not df[(df.deleted_status != "NONE") & df.eligible_as_standalone_candidate].shape[0], "")
    check("eligible_rows_have_no_unresolved_marker",
          df[df.eligible_as_standalone_candidate].normalization_status.isin(["EXACT", "WHITESPACE_REMOVED"]).all(), "")
    check("parents_with_children_have_composite_text",
          (df[df.child_marker_count > 0].parent_composite_text.str.len() > 0).all(), "")
    check("fragment_children_reference_existing_parent",
          set(df[df.parent_requirement_id != ""].parent_requirement_id) <= set(nid), "")
    v2_flagged = df[df.v2_review_status == "MANUAL_REVIEW_REQUIRED"]
    check("all_v2_manual_review_entries_have_v3_disposition",
          len(v2_flagged) == 205 and (v2_flagged.v2_flag_disposition != "").all(), f"{len(v2_flagged)} v2-flagged rows dispositioned")
    needs_review = df[df.boundary_status.isin(["UNRESOLVED_MANUAL_REVIEW", "MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT",
                                               "HEADING_OR_TABLE_CONTAMINATION"])
                      | ~df.normalization_status.isin(["EXACT", "WHITESPACE_REMOVED"])
                      | df.heuristic_flags.str.contains("MISSING_SUBJECT_IN_SOURCE_TEXT")]
    covered = set(pd.to_numeric(issues.source_order, errors="coerce").dropna().astype(int))
    check("every_row_needing_review_appears_in_unresolved_report",
          set(needs_review.source_order.astype(int)) <= covered,
          f"{len(needs_review)} rows needing review, {len(set(needs_review.source_order.astype(int)) - covered)} not covered")
    check("unresolved_report_references_only_known_markers",
          covered <= set(df.source_order.astype(int)), "")
    checklist = sources["checklist"]
    serious = issues[issues.severity.isin(["HIGH", "MEDIUM"])]
    listed_orders = set(checklist.source_order.astype(str)) - {""}
    listed_gaps = set(checklist[checklist.review_kind == "NUMBERING_GAP"].normalized_candidate_id)
    missing_marker_items = {str(o) for o in serious[serious.source_order.astype(str) != ""].source_order} - listed_orders
    missing_gap_items = set(serious[serious.source_order.astype(str) == ""].normalized_candidate_id) - listed_gaps
    check("every HIGH/MEDIUM issue is on the manual-review checklist", not missing_marker_items and not missing_gap_items,
          f"{len(serious)} serious issue records; checklist rows={len(checklist)}")
    check("checklist carries no fabricated review (all PENDING, reviewer/date/evidence blank, human_verified=NO)",
          (checklist.human_decision == "PENDING").all() and (checklist.reviewer == "").all() and (checklist.review_date == "").all()
          and (checklist.human_evidence == "").all() and (checklist.human_verified == "NO").all(), "")
    check("checklist review ids unique", checklist.review_id.is_unique, "")
    check("eligible_without_open_medium_or_high_issue is a subset of eligible and excludes serious issues",
          (~df.eligible_without_open_medium_or_high_issue | df.eligible_as_standalone_candidate).all()
          and not df[df.eligible_without_open_medium_or_high_issue].open_issue_max_severity.isin(["HIGH", "MEDIUM"]).any(), "")
    check("every proposed merge lists existing source ids",
          all(set(m.split(";")) <= set(nid) for m in df[df.merged_source_ids != ""].merged_source_ids), "")
    check("every_row_states_review_basis_not_human_verified",
          (df.review_basis == "RULE_BASED_AUTOMATED_TEXT_LAYER_CHECK_NOT_HUMAN_VERIFIED").all(), "no row claims human verification")
    return checks


VERIFICATION_MAP = [
    ("1 every bracketed SSS marker has exactly one row", "test_every_bracketed_sss_marker_in_the_source_has_a_row"),
    ("2 IDs unique, original marker strings preserved", "test_ids_are_unique_and_match_marker_digits; test_offsets_locate_each_marker_in_the_source"),
    ("3 offsets locate each marker", "test_offsets_locate_each_marker_in_the_source"),
    ("4 source order preserved", "test_markers_are_in_source_order"),
    ("5 parent references resolve to preceding markers", "test_parent_references_resolve_and_precede_the_child"),
    ("6 deleted entries never eligible", "test_deleted_or_unresolved_rows_are_never_eligible; test_deleted_rows_contain_only_the_placeholder"),
    ("7 unresolved entries never eligible", "test_deleted_or_unresolved_rows_are_never_eligible; test_malformed_ids_are_never_eligible_and_never_inferred_as_resolved"),
    ("8 every row needing review is in the issue report", "test_every_row_needing_review_is_in_the_unresolved_report; test_every_malformed_marker_and_spaced_marker_is_in_the_issue_report"),
    ("9 candidate text traceable to the source", "test_candidate_text_comes_from_the_source_without_invented_words"),
    ("10 Appendix A comparisons computed from real text", "test_appendix_matches_recorded_in_table_are_really_equal_in_the_source; AppendixCrossCheck"),
    ("11 categories and eligibility follow the rules", "SyntheticClassification; test_eligible_rows_really_contain_a_single_obligation_sentence"),
    ("12 status counts reconcile", "test_status_counts_add_up_and_review_fields_are_present"),
    ("13 nothing marked human-verified", "test_no_row_is_marked_human_verified; test_checklist_is_complete_and_contains_no_fabricated_review"),
    ("14 mandatory fields non-empty", "test_status_counts_add_up_and_review_fields_are_present; test_issue_records_carry_all_review_fields"),
    ("15 no duplicate records", "test_ids_are_unique_and_match_marker_digits; test_issue_records_carry_all_review_fields"),
    ("16 page mapping used by the checklist", "test_pdf_page_mapping_matches_an_independent_per_page_count"),
    ("numbering gaps", "test_numbering_gaps_are_exactly_the_ids_without_a_marker"),
    ("merge policy and derived text", "test_merge_fields_follow_the_documented_policy; test_r1_composite_is_an_exact_source_slice"),
    ("wording differences recorded, not reconciled", "test_appendix_wording_differences_are_recorded_not_reconciled"),
    ("determinism and source integrity", "test_classification_is_deterministic; test_source_files_match_the_hashes_recorded_in_the_validation_report"),
]


def file_integrity_line(label, path):
    return f"- {label}: `{path.relative_to(PROJECT_ROOT).as_posix()}` size={path.stat().st_size} sha256={sha256(path)}"


def write_reports(df, issues, checks, info):
    status_counts = df.boundary_status.value_counts()
    ver_counts = df.source_verification_status.value_counts()
    fmt_counts = df.marker_format.value_counts()
    flag_counts = Counter(f for s in df.heuristic_flags for f in s.split(";"))
    v2_counts = df.v2_flag_disposition.value_counts()
    eligible = int(df.eligible_as_standalone_candidate.sum())
    two_engine = int((df.source_verification_status == "TEXT_LAYER_TWO_ENGINE_ID_AND_CONTEXT_AGREE").sum())
    missed = df[~df.v2_present]
    missed_spaced = int((missed.marker_format == "WHITESPACE_IN_MARKER").sum())
    missed_extra = int((missed.marker_format == "EXTRA_DIGITS").sum())
    spaced = df[df.marker_format == "WHITESPACE_IN_MARKER"]
    spaced_clean_second = int(spaced.second_engine_marker.str.fullmatch(r"\[SSS\d{3}\]").sum())
    spaced_still_spaced = ", ".join(spaced[~spaced.second_engine_marker.str.fullmatch(r"\[SSS\d{3}\]")].original_marker)
    extra = df[df.marker_format == "EXTRA_DIGITS"]
    extra_same_token = int((extra.original_marker == extra.second_engine_marker).sum())
    extra_deleted = int((extra.deleted_status == "DELETED_PLACEHOLDER").sum())
    extra_del = extra[extra.deleted_status == "DELETED_PLACEHOLDER"]
    extra_active = extra[extra.deleted_status != "DELETED_PLACEHOLDER"]
    extra_tails = ", ".join(f"{o} (+{t})" for o, t in zip(extra_del.original_marker, extra_del.id_digits_raw.str[3:]))
    extra_active_text = ", ".join(f"{o} (+{t}) on PDF page {pg}" for o, t, pg in
                                  zip(extra_active.original_marker, extra_active.id_digits_raw.str[3:], extra_active.pdf_page))
    extra_in_appendix = int(extra.in_traceability_appendix.sum())
    marker_issues = issues[issues.source_order.astype(str) != ""]
    id_gap_issues = issues[issues.source_order.astype(str) == ""]
    gap_deleted = id_gap_issues[id_gap_issues.issue_type == "ID_DELETED_PER_APPENDIX_NO_BODY_MARKER"].normalized_candidate_id.tolist()
    gap_unexplained_cited = id_gap_issues[id_gap_issues.issue_type == "ID_IN_APPENDIX_BUT_NO_BODY_MARKER"].normalized_candidate_id.tolist()
    gap_absent = id_gap_issues[id_gap_issues.issue_type == "ID_ABSENT_FROM_BODY_AND_APPENDIX"]
    valid = df[df.boundary_status == "VALID_STANDALONE_CANDIDATE"]
    valid_match = int((valid.appendix_a_crosscheck == "APPENDIX_MATCHES_CANDIDATE").sum())
    eligible_exact = int(((df.eligible_as_standalone_candidate) & (df.appendix_a_crosscheck == "APPENDIX_MATCHES_CANDIDATE")).sum())
    valid_no_entry = int((valid.appendix_a_crosscheck == "NO_APPENDIX_ENTRY").sum())
    narrative_rows = df[df.requirement_type == "UNMARKED_NARRATIVE_BEFORE_MARKED_SENTENCE"]
    narrative_confirmed = int((narrative_rows.appendix_a_crosscheck == "APPENDIX_MATCHES_PROPOSED_SENTENCE_ONLY").sum())
    distinct_issue_markers = marker_issues.source_order.nunique()
    n_missing_subject = int(df.heuristic_flags.str.contains("MISSING_SUBJECT_IN_SOURCE_TEXT").sum())

    def flag_rows(name):
        return int(df.heuristic_flags.str.contains(name).sum())

    no_sentence = ((df.deleted_status != "NONE") | df.requirement_type.isin(["NO_OBLIGATION_MODAL", "MARKER_WITHOUT_TEXT",
                                                                              "MULTI_SENTENCE_NO_OBLIGATION_MODAL"]))
    suspicious_ids = (df.duplicate_normalized_id | (df.marker_format != "CLEAN")
                      | df.id_sequence_note.str.startswith("OUT_OF_SEQUENCE_BACKWARD"))
    coverage = [
        ("Entries flagged MANUAL_REVIEW_REQUIRED in V2", int((df.v2_review_status == "MANUAL_REVIEW_REQUIRED").sum()), "`v2_flag_disposition`"),
        ("Deleted-status entries", int((df.deleted_status != "NONE").sum()), "`deleted_status`, `boundary_status`"),
        (f"Very short segments (<{VERY_SHORT_CHARS} chars)", flag_rows("VERY_SHORT_SEGMENT"), "`heuristic_flags`"),
        (f"Long segments (>{LONG_CHARS} chars)", flag_rows("LONG_SEGMENT"), "`heuristic_flags`"),
        ("Heading context (heading inside the span)", flag_rows("HEADING_REMOVED_FROM_SPAN"), "`headings_removed`"),
        ("List context", flag_rows("LIST_LINES_IN_SEGMENT"), "`heuristic_flags`, `requirement_type`"),
        ("Table / figure context", flag_rows("TABLE_OR_FIGURE_LINES_IN_SEGMENT"), "`heuristic_flags`"),
        ("Spaced or malformed marker IDs", int((df.marker_format != "CLEAN").sum()), "`marker_format`, `normalization_status`"),
        ("Several shall/must/should in one segment", flag_rows("MULTIPLE_OBLIGATION_MODALS"), "`obligation_modal_count`"),
        ("Parent / child relationships (children + parents)", int((df.parent_requirement_id != "").sum() + (df.child_marker_count.astype(int) > 0).sum()),
         "`parent_requirement_id`, `child_marker_count`, `parent_composite_text`"),
        ("Markers with no obvious requirement sentence", int(no_sentence.sum()), "`requirement_type`"),
        ("Duplicate, spaced, malformed or backward-stepping IDs", int(suspicious_ids.sum()), "`id_sequence_note`, `marker_format`"),
    ]
    coverage_table = "\n".join(f"| {a} | {b} | {c} |" for a, b, c in coverage)
    eligible_clean = int(df.eligible_without_open_medium_or_high_issue.sum())
    checklist = info["checklist"]
    pages = sorted({int(p) for p in checklist.pdf_page_file_index if int(p) > 0})
    checklist_pages = len(pages)
    checklist_page_list = ", ".join(map(str, pages))
    appendix_all = df.appendix_a_crosscheck.value_counts()
    appendix_valid = df[df.boundary_status == "VALID_STANDALONE_CANDIDATE"].appendix_a_crosscheck.value_counts()
    appendix_table = "\n".join(f"| {k} | {v} | {int(appendix_valid.get(k, 0))} |" for k, v in appendix_all.items())

    def table(series):
        return "\n".join(f"| {k} | {v} |" for k, v in series.items())

    summary = f"""# TCS SRS Boundary Audit {VERSION} - Summary

Generated {info['timestamp']} by `experiments/component1/audit_tcs_requirement_boundaries.py`.
Source: `1999 - tcs.pdf` (Microsoft Word -> Acrobat PDFWriter 3.0, 148 pages, text layer present) and its pypdf extraction `1999 - tcs.txt`.

**Basis of every finding below:** rule-based analysis of the extracted text plus a two-engine comparison of the PDF text layer
(pypdf vs. pdftotext). No page was rendered or visually inspected and no human has verified any boundary.

## Counts

- Markers detected: **{len(df)}** (V2 report listed 511; it silently missed {len(missed)} markers: {missed_spaced} with spaces inside the digits and {missed_extra} with 5-6 digits)
- Unique normalized IDs: **{df.normalized_candidate_id.nunique()}** (duplicates: {int(df.duplicate_normalized_id.sum())})
- Marker formats: {', '.join(f'{k}={v}' for k, v in fmt_counts.items())}
- Markers where both text-layer engines agree on ID and preceding context: **{two_engine}** / {len(df)}
- Rows eligible as provisional standalone candidates (valid boundary rules + resolved ID + two-engine agreement + not deleted + subject present): **{eligible}**
- Of those, rows with **no open MEDIUM or HIGH issue**: **{eligible_clean}** ({eligible - eligible_clean} are eligible but carry an open Appendix A wording issue)
- Rows verified visually or by a human: **0**

### Boundary status

| boundary_status | rows |
|---|---|
{table(status_counts)}

### Source verification status (text-layer only)

| status | rows |
|---|---|
{table(ver_counts)}

### Heuristic flags (not mutually exclusive)

| flag | rows |
|---|---|
{table(pd.Series(flag_counts).sort_values(ascending=False))}

### Edge-case review coverage

Every row carries a `boundary_status`, `review_reason` and `review_evidence`; the table shows how many rows fall in each required edge-case group (groups overlap) and which column to filter.

| edge case | rows | where |
|---|---|---|
{coverage_table}

### Appendix A cross-check (in-document restatement; not a visual check)

| appendix_a_crosscheck | all rows | valid segments |
|---|---|---|
{appendix_table}

### V2 flag reconciliation

| disposition | rows |
|---|---|
{table(v2_counts)}

## Findings

1. **V2 under-counted markers.** The text and the PDF text layer both contain {len(df)} bracketed `SSS` markers. V2 omitted {len(missed)}: {missed_spaced} whose digits are split by a space (`[SSS0 65]`, `[SSS1 32]`, ...) and {missed_extra} whose token has 5-6 digits (`[SSS126102]`, `[SSS25405]`, ...). No generator script for V2 exists in the repository, so its logic could not be inspected.
2. **The PDF is born-digital, so the anomalies are not OCR.** The extracted text equals pypdf's text-layer output. {len(spaced)} markers contain whitespace; for {spaced_clean_second} of them pdftotext renders a clean 3-digit marker (for example `[SSS02 7]` -> `[SSS027]`), so the spacing is extractor-dependent. Still spaced in both engines: {spaced_still_spaced}.
3. **{len(extra)} markers carry extra digits in the PDF text layer itself** (identical token in both engines for {extra_same_token}): {extra_deleted} of them are `**DELETED**` placeholders with trailing digits {extra_tails}; the other {len(extra_active)} is an active requirement ({extra_active_text}). The 3-digit prefix fits the numeric sequence and is unused elsewhere in every case, but {extra_in_appendix} of the {len(extra)} prefixes are cited in Appendix A, so the appendix gives no corroboration. The correct ID therefore stays a **hypothesis** until the printed marker is read on the page.
4. **Markers trail their text** and often tag clauses of one sentence. Example: `SSS542` heads *Initialization of the TCS HWCIs shall include startup of HWCIs*, continued by `SSS026`, `SSS027`, `SSS025` and `SSS028`. By sentence evidence the parent of `SSS026` is `SSS542`, not `SSS024` as guessed in `tcs_manual_review_examples.csv`; likewise the parent chain for `SSS097` is the list lead in `SSS096`, not `SSS535` (a map-scale requirement that precedes it). In {int((df.requirement_type == 'UNMARKED_NARRATIVE_BEFORE_MARKED_SENTENCE').sum())} segments an unmarked narrative or definition sentence precedes the one sentence that contains shall/must/should.
5. **Deleted entries:** {int((df.deleted_status == 'DELETED_PLACEHOLDER').sum())} markers consist only of the `**DELETED**` placeholder and are excluded from active candidates (V2 flagged 17).
6. **Missing subject:** {n_missing_subject} segment (`SSS559`) reads *The shall provide the functionality ...* in both engines. This is a source defect and was not repaired.
7. **Numbering gaps:** {len(id_gap_issues)} IDs inside the observed range have no body marker. {len(gap_deleted)} of them ({', '.join(gap_deleted)}) are listed as `(Deleted)` in Appendix A, which explains them; {len(gap_absent)} appear nowhere in the body or the appendix (never assigned or removed without a trace){' and ' + str(len(gap_unexplained_cited)) + ' are cited in the appendix without an explanation (' + ', '.join(gap_unexplained_cited) + ')' if gap_unexplained_cited else ''}.
8. **Appendix A is an independent in-document restatement.** It repeats the text of {int((df.appendix_a_crosscheck != 'NO_APPENDIX_ENTRY').sum())} marker IDs under an `SSS###` line. {valid_match} of the {len(valid)} valid segments match it verbatim (after ignoring case, spacing and punctuation) and {valid_no_entry} have no appendix entry. For {narrative_confirmed} of the {len(narrative_rows)} "narrative before marked sentence" segments the appendix text equals exactly the proposed last sentence, which supports excluding the preceding narrative. Differences are usually wording revisions (the appendix is a separately maintained copy), so a difference is a provenance/version note, not proof of a boundary error.
9. **Document-wide ID order is not numeric.** {int(df.id_sequence_note.str.startswith('OUT_OF_SEQUENCE_BACKWARD').sum())} markers step backwards numerically (requirements added later), so numeric order cannot validate boundaries.

## Recommendation

**Provisional candidate source - not approved for training or evaluation use.**

The document is a real, structured requirements specification with a consistent marker convention (markers trail their text; {len(df)} markers were located and matched in two text-layer engines),
and the text is unchanged since the earlier extraction audit. But the evidence does not yet justify treating its segments as clean requirements:

- Only **{eligible} of {len(df)}** segments pass every automated criterion for standalone use ({eligible_exact} of those also match Appendix A verbatim). None is visually or human verified.
- {int((df.boundary_status == 'LIST_ITEM_OR_CHILD_FRAGMENT').sum())} segments are clause or list fragments and {int((df.boundary_status == 'PARENT_REQUIREMENT').sum())} are parents; they must be merged into their parent's composite text, never used one by one.
- {int((df.boundary_status == 'MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT').sum())} segments mix narrative or several statements under one marker and {int((df.boundary_status == 'HEADING_OR_TABLE_CONTAMINATION').sum())} contain table, figure or list rows.
- {distinct_issue_markers} markers plus {len(id_gap_issues)} numbering gaps need human or PDF-page verification ({len(issues)} issue records in `tcs_unresolved_issues_{VERSION}.csv`), including {len(extra)} marker IDs whose extra digits cannot be resolved from the text layer.

**What would raise the status:** a human check of the flagged pages against the PDF (especially the {len(extra)} extra-digit IDs and the mixed-context segments), and a decision on the fragment/parent merge rule. Until then, if TCS segments are used at all, restrict them to the {eligible} eligible rows and exclude deleted placeholders.

## Merge and canonical-wording policy

1. Original markers, source offsets, `candidate_text` and `appendix_a_text` are never altered. Derived text exists only in `parent_composite_text`, with its rule in `composite_rule` and its members in `merged_source_ids`.
2. **R1 clause chain.** A segment that continues a sentence (starts with `,` / `;` / lowercase after another marker's text) is a clause of that sentence. The head's composite is the exact source slice from the head to the last clause marker, page furniture removed. Clause rows keep their own IDs, point to the head in `parent_requirement_id`, and are never eligible alone.
3. **R2 list lead.** Items that start with a list label (`1.`, `(1)`, `Level n:`, a bullet) after a lead sentence ending in `:` or containing "following" point to the lead's marker. The composite is a *derived concatenation* of the lead segment and the item `candidate_text` values in source order. Items are **not** merged automatically because each may be an independent obligation; their `merge_status` is `LIST_ITEM_INDEPENDENCE_UNDECIDED` and they stay ineligible.
4. Every proposed merge has `merge_status = PROPOSED_PENDING_HUMAN_CONFIRMATION`; nothing is final until a person decides on the checklist.
5. Deleted placeholders are excluded (`EXCLUDED_DELETED`). Uncertain fragments stay ineligible.
6. Body text is preserved as `candidate_text`; Appendix A wording is kept beside it. Differences are recorded as `APPENDIX_A_WORDING_DIFFERS_FROM_BODY` (MEDIUM) and are not reconciled. Such rows remain mechanically eligible but are visible through `open_issue_types` and `eligible_without_open_medium_or_high_issue`.

## Human review status

**No human review has been performed.** `tcs_manual_review_checklist_{VERSION}.csv` lists {len(checklist)} items ({int((checklist.review_kind == 'NUMBERING_GAP').sum())} numbering gaps, {int((checklist.review_kind != 'NUMBERING_GAP').sum())} markers/merge groups) on {checklist_pages} distinct PDF file pages, sorted by page. Every `human_decision` is `PENDING` and `reviewer`, `review_date`, `human_evidence` are blank. Page numbers are the file's page index; the printed page number is only a text-layer hint.

Pages to inspect (file index): {checklist_page_list}

## Limitations

- Boundary rules are heuristics (sentence splitting, heading regex, list/table patterns); false positives and negatives are expected.
- No rendered-page comparison was possible (no page renderer installed); both engines read the same PDF text layer, so they are not independent of encoding defects in the document itself.
- Requirement type (functional / non-functional) was deliberately not assigned.
- `source_verification_status` verifies marker ID and preceding context in the text layer only, not requirement meaning.

## Reproduce

```powershell
cd project
..\\.venv\\Scripts\\python.exe experiments\\component1\\audit_tcs_requirement_boundaries.py --overwrite
..\\.venv\\Scripts\\python.exe -m unittest tests.test_tcs_boundary_audit -v
```
Requires `pdftotext` (poppler/xpdf) on PATH for the second-engine check; without it all rows are marked `UNVERIFIED_SECOND_ENGINE_UNAVAILABLE`.
"""
    OUT_SUMMARY.write_text(summary, encoding="utf-8")

    lines = [f"# TCS SRS Boundary Audit {VERSION} - Validation Report", "", f"Generated {info['timestamp']}.", "",
             "## Source integrity (files are never written by this script)", ""]
    lines += info["integrity"]
    lines += ["", f"- Offsets are character offsets into the text decoded as UTF-8 with the BOM removed and CRLF preserved.",
              f"- Second engine: {info['second_engine']}", "",
              "## Automated checks", "", "| check | result | detail |", "|---|---|---|"]
    lines += [f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |" for name, ok, detail in checks]
    lines += ["", f"**{sum(ok for _, ok, _ in checks)} / {len(checks)} checks passed.**", "",
              "## Counts requested for the audit", "",
              f"1. Markers detected: {len(df)}", f"2. Unique normalized IDs: {df.normalized_candidate_id.nunique()}",
              f"3. Duplicate normalized IDs: {int(df.duplicate_normalized_id.sum())}",
              f"4. Malformed marker IDs: {int((df.marker_format == 'EXTRA_DIGITS').sum())}; spaced: {int((df.marker_format == 'WHITESPACE_IN_MARKER').sum())}; non-numeric: {int((df.marker_format == 'NON_NUMERIC_OR_SHORT').sum())}",
              "5. Source order preserved: see check `source_order_contiguous_from_1`",
              "6. Every row has a source location and a status: see checks above",
              "7. Boundary status counts:", ""]
    lines += [f"   - {k}: {v}" for k, v in status_counts.items()]
    lines += ["8. Verified vs unresolved:",
              f"   - two-engine text-layer ID+context agreement: {two_engine}",
              f"   - visually / human verified: 0",
              f"   - unresolved-issue records: {len(issues)} ({distinct_issue_markers} distinct markers; {len(id_gap_issues)} numbering-gap IDs)",
              f"9. Deleted entries excluded from active candidates: {int((df.deleted_status == 'DELETED_PLACEHOLDER').sum())}",
              f"10. Entries with unresolved marker/extraction problems: {int((~df.normalization_status.isin(['EXACT', 'WHITESPACE_REMOVED'])).sum())} unresolved ID; "
              f"{int((df.source_verification_status != 'TEXT_LAYER_TWO_ENGINE_ID_AND_CONTEXT_AGREE').sum())} without full two-engine agreement",
              f"11. Duplicate rows: {int(df.duplicated(subset=['source_order']).sum())}; missing required fields: see check `required_fields_non_empty`",
              "12. Every final inclusion/exclusion decision carries `review_reason`, `review_evidence` and `review_basis` (rule-based, not human-verified).",
              "", "## Traceability appendix cross-check", "", info["appendix_text"], "",
              "## Coverage of the requested verification items", "",
              "Each item is enforced by an automated test in `tests/test_tcs_boundary_audit.py` (run it after any change). "
              "The tests re-derive their expectations from the source text, the PDF and the generated files rather than from hard-coded counts.", "",
              "| item | enforced by |", "|---|---|"]
    lines += [f"| {item} | `{tests}` |" for item, tests in VERIFICATION_MAP]
    eligible_n = int(df.eligible_as_standalone_candidate.sum())
    clean_n = int(df.eligible_without_open_medium_or_high_issue.sum())
    low_n = int((issues.severity == "LOW").sum())
    wording = issues[issues.issue_type == "APPENDIX_A_WORDING_DIFFERS_FROM_BODY"]
    lines += ["", "## Discrepancies and observations", "",
              f"1. **Eligible does not mean clean.** {eligible_n} rows pass the mechanical eligibility rules, but {eligible_n - clean_n} of them carry an open "
              f"Appendix A wording issue (MEDIUM). `eligible_without_open_medium_or_high_issue` counts {clean_n}. Nothing was reconciled automatically.",
              f"2. **Issue-record count.** Earlier runs listed fewer issue records. The {low_n} spaced/extractor-dependent markers are now listed explicitly as LOW "
              "severity; this changes the issue report only, not any classification or eligibility decision.",
              f"3. **Wording differences.** {len(wording)} body/Appendix A wording differences are recorded "
              f"({int((wording.boundary_status == 'VALID_STANDALONE_CANDIDATE').sum())} valid segments, "
              f"{int((wording.boundary_status == 'PARENT_REQUIREMENT').sum())} parent). Appendix A is a separately maintained copy and is not ground truth.",
              "4. **Appendix A matches are exact after normalisation** (case, spacing and punctuation ignored); anything with a word-level difference is "
              "reported as nearly identical, similar or different, never as a match.",
              "5. **Page references are file page indexes** (1-based, from the PDF's own page tree). The printed page number is only a hint from the text layer; "
              "numbering-gap rows use the numeric neighbour's page.",
              "6. **No human or visual verification exists.** `pdftoppm` is not installed, so pages could not be rendered; both text-layer engines read the same "
              "embedded text, so their agreement does not prove the printed marker or wording.", ""]
    OUT_VALIDATION.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------------- tracker update
def update_tracker(df, issues):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TRACKER.with_name(f"dataset_suitability_tracker_backup_before_tcs_boundary_{stamp}.csv")
    shutil.copy2(TRACKER, backup)
    raw_bytes = TRACKER.read_bytes()
    tracker = pd.read_csv(TRACKER, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    mask = tracker.file_name.str.contains("tcs", case=False)
    assert mask.sum() == 1, f"expected exactly one TCS row, found {int(mask.sum())}"
    before = tracker.copy()
    eligible = int(df.eligible_as_standalone_candidate.sum())
    parents = int((df.boundary_status == "PARENT_REQUIREMENT").sum())
    frags = int((df.boundary_status == "LIST_ITEM_OR_CHILD_FRAGMENT").sum())
    deleted = int((df.boundary_status == "DELETED_REQUIREMENT").sum())
    bad_ids = int((~df.normalization_status.isin(["EXACT", "WHITESPACE_REMOVED"])).sum())
    idx = tracker.index[mask][0]
    serious = issues[issues.severity.isin(["HIGH", "MEDIUM"])]
    flagged_markers = serious[serious.source_order.astype(str) != ""].source_order.nunique()
    id_gaps = int((issues.source_order.astype(str) == "").sum())
    id_gaps_open = int((serious.source_order.astype(str) == "").sum())
    eligible_clean = int(df.eligible_without_open_medium_or_high_issue.sum())
    multi = int((df.boundary_status == "MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT").sum())
    contam = int((df.boundary_status == "HEADING_OR_TABLE_CONTAMINATION").sum())
    gap_deleted = issues[issues.issue_type == "ID_DELETED_PER_APPENDIX_NO_BODY_MARKER"].normalized_candidate_id.tolist()
    valid_match = int(((df.boundary_status == "VALID_STANDALONE_CANDIDATE") & (df.appendix_a_crosscheck == "APPENDIX_MATCHES_CANDIDATE")).sum())
    extra_pages = sorted({int(p) for p in df[df.marker_format == "EXTRA_DIGITS"].pdf_page})
    no_subject = df[df.heuristic_flags.str.contains("MISSING_SUBJECT_IN_SOURCE_TEXT")].normalized_candidate_id.tolist()
    tracker.loc[idx, "audit_status"] = "BOUNDARY_AUDIT_COMPLETED_AUTOMATED_NOT_HUMAN_VERIFIED"
    tracker.loc[idx, "suitability"] = "CANDIDATE_PENDING_MANUAL_BOUNDARY_REVIEW"
    tracker.loc[idx, "known_issues"] = (
        f"{len(df)} markers found; the earlier V2 report listed 511 and missed {int((~df.v2_present).sum())}. "
        f"Boundaries are rule-based and corroborated only against the PDF text layer; nothing is visually or human verified. "
        f"Of {len(df)} segments, {eligible} pass all automated standalone criteria ({eligible_clean} without an open Appendix A wording issue); {frags} are clause or list fragments, "
        f"{parents} are parents needing composite text, {multi} mix narrative or several statements, {contam} contain table/figure/list rows, "
        f"{deleted} are deleted placeholders. {bad_ids} marker IDs have extra digits in the source text layer (prefix is an unverified hypothesis), "
        f"{len(no_subject)} sentence ({', '.join(no_subject)}) lacks its subject in the source, and {id_gaps} numbering gaps exist "
        f"({', '.join(gap_deleted)} are listed as (Deleted) in Appendix A). {valid_match} valid segments match Appendix A's restatement verbatim.")
    kept = [e for e in tracker.loc[idx, "supporting_evidence"].split("; ") if e and not (e.startswith("tcs_") and f"_{VERSION}." in e)]
    tracker.loc[idx, "supporting_evidence"] = "; ".join(
        kept + [OUT_TABLE.name, OUT_SUMMARY.name, OUT_UNRESOLVED.name, OUT_VALIDATION.name, OUT_CHECKLIST.name])
    tracker.loc[idx, "next_action"] = (
        f"Complete {OUT_CHECKLIST.name} (no human review done yet): {flagged_markers} markers with HIGH/MEDIUM issues and {id_gaps_open} open numbering gaps against the PDF pages; "
        f"read the {bad_ids} extra-digit IDs on PDF pages {', '.join(map(str, extra_pages))}; confirm or reject the proposed parent/fragment merges and the 15 Appendix A wording differences before any train/test split or training.")
    changed_cols = [c for c in tracker.columns if (before.loc[idx, c] != tracker.loc[idx, c])]
    others_equal = before.drop(index=idx).equals(tracker.drop(index=idx))
    assert others_equal and list(before.columns) == list(tracker.columns), "unrelated tracker data changed"
    tracker.to_csv(TRACKER, index=False, encoding="utf-8-sig", lineterminator="\r\n" if b"\r\n" in raw_bytes else "\n")
    return backup, changed_cols


# ----------------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--overwrite", action="store_true", help=f"overwrite existing {VERSION} outputs")
    parser.add_argument("--update-tracker", action="store_true", help="after validation passes, update the TCS tracker row (backup first)")
    args = parser.parse_args()

    outputs = [OUT_TABLE, OUT_UNRESOLVED, OUT_SUMMARY, OUT_VALIDATION, OUT_CHECKLIST]
    existing = [p.name for p in outputs if p.exists()]
    if existing and not args.overwrite and not args.update_tracker:
        raise SystemExit(f"Refusing to overwrite existing outputs: {existing}. Use --overwrite.")

    hashes_before = {p: sha256(p) for p in (SRC_PDF, SRC_TXT)}
    text = SRC_TXT.read_bytes().decode("utf-8-sig")
    markers = find_markers(text)

    pypdf_pages = load_pdf_pages(SRC_PDF)
    second_pages, second_note = load_second_engine_pages(SRC_PDF)
    seq_matches = cross_check_markers(markers, pypdf_pages, second_pages)
    txt_equals = collapse(text) == collapse("\n".join(pypdf_pages))

    earlier = None
    quality_audit = REPORT_DIR / "srs_extracted_text_quality_audit.csv"
    if quality_audit.exists():
        qa = pd.read_csv(quality_audit, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        hit = qa[qa.File == SOURCE_FILE]
        if len(hit) == 1:
            lf_text = text.replace("\r\n", "\n")
            earlier = (int(hit.iloc[0].Characters) == len(lf_text), int(hit.iloc[0].Words) == len(lf_text.split()),
                       hit.iloc[0].UniqueTextHash == hashlib.sha256(collapse(lf_text).encode("utf-8")).hexdigest())

    last_end = markers[-1]["marker_end_char"]
    appendix_ids = {"SSS" + m.group(1) for m in re.finditer(r"(?<!\[)\bSSS\s?(\d{3})\b", text[last_end:])}
    appendix_count = len(re.findall(r"(?<!\[)\bSSS\s?\d{3}\b", text))

    rows, _ = build_rows(text, markers)
    v2 = None
    if V2_REPORT.exists():
        v2df = pd.read_csv(V2_REPORT, encoding="utf-8-sig", dtype=str)
        v2 = {r.requirement_id: r._asdict() for r in v2df.itertuples(index=False)}
    rows = finish_rows(rows, v2, appendix_ids, markers)
    appendix_entries = parse_appendix_a(text)
    rows = appendix_crosscheck(rows, appendix_entries)
    rows = add_merge_fields(rows)
    global AUDIT_TEXT
    AUDIT_TEXT = text
    hints = printed_page_hints(pypdf_pages)

    nums = sorted({int(r["normalized_candidate_id"][3:]) for r in rows if r["normalized_candidate_id"]})
    missing = [f"SSS{n:03d}" for n in range(nums[0], nums[-1] + 1) if n not in set(nums)]
    marker_id_set = {r["normalized_candidate_id"] for r in rows}
    appendix_only = sorted(appendix_ids - marker_id_set)
    markers_not_in_appendix = sorted(marker_id_set - appendix_ids)

    issues = build_unresolved(rows, missing, appendix_ids, appendix_entries, text, hints)
    rows = attach_open_issues(rows, issues)
    df = pd.DataFrame(rows)[COLUMNS]
    checklist = build_checklist(rows, issues, hints)
    checks = validate(rows, markers, text, seq_matches, issues,
                      {"txt_equals_pypdf": txt_equals, "earlier_audit": earlier, "checklist": checklist})

    assert hashes_before == {p: sha256(p) for p in (SRC_PDF, SRC_TXT)}, "source file changed during audit"
    failed = [c for c in checks if not c[1]]
    appendix_text = (f"- Unbracketed `SSS###` references: {appendix_count}, all after the last marker "
                     f"(offset >= {last_end}); distinct IDs referenced: {len(appendix_ids)}.\n"
                     f"- IDs referenced in the appendix but with no marker: {len(appendix_only)} {appendix_only[:20]}\n"
                     f"- Marker IDs absent from the appendix: {len(markers_not_in_appendix)} {markers_not_in_appendix[:30]}\n"
                     f"- IDs inside the observed numeric range with no marker: {len(missing)} {missing}\n"
                     f"- Of those, cited in the appendix: {sorted(set(missing) & appendix_ids)}\n"
                     f"- shall/must/should occurrences outside the marker-bearing region (not audited here): "
                     f"{len(OBLIGATION_RE.findall(text[:rows[0]['source_start_char']]))} before the first segment, "
                     f"{len(OBLIGATION_RE.findall(text[last_end:]))} after the last marker")
    info = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "second_engine": second_note, "checklist": checklist,
            "appendix_text": appendix_text,
            "integrity": [file_integrity_line("Original PDF", SRC_PDF), file_integrity_line("Extracted text", SRC_TXT),
                          "- Both hashes were identical before and after the run (asserted)."]}

    df.to_csv(OUT_TABLE, index=False, encoding="utf-8-sig")
    issues.to_csv(OUT_UNRESOLVED, index=False, encoding="utf-8-sig")
    checklist.to_csv(OUT_CHECKLIST, index=False, encoding="utf-8-sig")
    write_reports(df, issues, checks, info)

    print(f"markers={len(df)} unique_ids={df.normalized_candidate_id.nunique()} issues={len(issues)}")
    print(df.boundary_status.value_counts().to_string())
    print(f"checks passed: {sum(ok for _, ok, _ in checks)}/{len(checks)}")
    for name, ok, detail in checks:
        if not ok:
            print("FAILED:", name, detail)
    if args.update_tracker:
        if failed:
            raise SystemExit("Validation failed; tracker not updated.")
        backup, changed = update_tracker(df, issues)
        print(f"tracker updated; backup={backup.name}; changed columns={changed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
