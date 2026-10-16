"""Requirement segmentation: turn the text of an SRS-like document into candidate requirement rows.

Moved unchanged from `experiments/component1/build_srs_requirements.py` so that the build script and the requirement agent share one
implementation (a parity test checks that both give the same rows as `processed/srs_requirements_extracted.csv`).

Rules (a rule name is stored on every row):
  dropped: table-of-contents lines, repeated headers/footers, page numbers, headings, notes/examples, entries marked deleted;
  kept:    sentences containing shall / must / should / will / is|are required to        -> modal_sentence
           numbered or ID-tagged clauses that contain such a modal                       -> numbered_clause_modal
           numbered or ID-tagged sentence-like clauses without any modal                 -> numbered_clause_no_modal
`candidate_type` is FR/NFR only when a clear cue exists, otherwise "unknown". Rows are unverified candidates (`auto_unverified`).
No file access, no models, no LLM calls.
"""
import re
from collections import Counter


def collapse(value):
    return re.sub(r"\s+", " ", str(value).replace(" ", " ")).strip()


MODAL = re.compile(r"\b(shall|must|should|will|(?:is|are) required to)\b", re.I)
LEADER = re.compile(r"(\.\s?){4,}|…{2,}|…\s*\d+\s*$|_{6,}")
PAGE_NUMBER = re.compile(r"^(page\s+)?\d{1,4}(\s+of\s+\d{1,4})?$", re.I)
NUMBERED = re.compile(r"^((?:\d+(?:\.\d+)+|\d+)[.)]?|\(?[a-z]\)|\([ivx]+\)|\([0-9]+\)|[A-Z]{1,5}[-_ ]?\d+(?:\.\d+)*[.:)])\s+(?=\S)")
BULLET = re.compile(r"^[•·▪●\-\*o]\s+(?=\S)")
MARKER = re.compile(r"\[[A-Z]{2,6}\s?\d{1,6}(?:\s?,\s?[A-Z]{2,6}\s?\d{1,6})*\]")
HEADING_NUM = re.compile(r"^\d+(\.\d+)*\.?\s+[A-Z]")
NOTE = re.compile(r"^\s*(notes?\b|(?:for\s+)?examples?\s*[:.\-]|e\.g\.\s*[:,]|rationale\s*[:.\-]|comments?\s*[:.\-]|remarks?\s*[:.\-])", re.I)
DELETED = re.compile(r"\*\*deleted\*\*|\(deleted\)|\[deleted\]|^\s*deleted\b|\bdeleted\.?\s*$", re.I)

NFR_CUES = re.compile(r"\b(response time|within \d+(?:\.\d+)?\s?(?:ms|milliseconds?|seconds?|secs?|minutes?)|availability|reliab\w*|"
                      r"uptime|throughput|latency|encrypt\w*|authenticat\w*|confidential\w*|maintainab\w*|portab\w*|scalab\w*|usab\w*|"
                      r"accessib\w*|mean time between)\b", re.I)
FR_CUES = re.compile(r"\b(?:shall|must|should|will)\s+(?:also\s+|then\s+)?(?:be able to\s+|allow\s+\w+\s+to\s+|enable\s+\w+\s+to\s+)?"
                     r"(?:display|calculate|generate|store|record|send|receive|accept|validate|print|search|create|delete|update|edit|add|remove|"
                     r"select|export|import|register|log\s?in|compute|transmit|report|notify)\b", re.I)
ABBREV = re.compile(r"(?:\b(?:e\.g|i\.e|etc|vs|no|fig|sec|inc|approx|cf|al)|\b[A-Za-z]|\d+(?:\.\d+)+)\.$", re.I)


# ----------------------------------------------------------------------------- text preparation
def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(\[])", text)
    merged = []
    for part in parts:
        if merged and ABBREV.search(merged[-1].rstrip()):
            merged[-1] += " " + part
        else:
            merged.append(part)
    return [p.strip() for p in merged if p.strip()]


def is_heading(block):
    words = block.split()
    if len(words) > 14 or block.endswith((".", ":", ";", ",")) and len(words) > 3:
        return False
    if HEADING_NUM.match(block):
        return not MODAL.search(block)
    if block.isupper() and len(words) <= 10 and len(block) > 3:
        return True
    return len(words) <= 6 and block[:1].isupper() and not block.endswith(".") and all(w[:1].isupper() or not w[:1].isalpha() for w in words if len(w) > 3) \
        and not MODAL.search(block)


def prepare_blocks(text):
    """Return (blocks, stats). A block is [line_start, raw_text] of joined wrapped lines."""
    raw_lines = [collapse(l.replace("\f", " ")) for l in text.replace("\r", "").split("\n")]
    # repeated header/footer lines
    norm = [re.sub(r"\d+", "#", l.lower()) for l in raw_lines]
    counts = Counter(n for n, l in zip(norm, raw_lines) if l and len(l) <= 100)
    repeated = {n for n, c in counts.items() if c >= 6 and not n.endswith((".", ";", ":")) and not MODAL.search(n)}
    stats = Counter()
    blocks, current, start = [], [], 0

    def flush():
        nonlocal current, start
        if current:
            blocks.append((start, " ".join(current)))
        current = []

    for number, line in enumerate(raw_lines, start=1):
        if not line:
            flush()
            continue
        if PAGE_NUMBER.match(line):
            stats["page_number"] += 1
            flush()
            continue
        if LEADER.search(line):
            stats["toc_line"] += 1
            flush()
            continue
        if norm[number - 1] in repeated:
            stats["header_footer"] += 1
            flush()
            continue
        heading_line = is_heading(line)
        starts_new = bool(NUMBERED.match(line) or BULLET.match(line) or MARKER.match(line) or heading_line)
        if starts_new:
            flush()
        if not current:
            start = number
        current.append(line)
        if heading_line:
            flush()
    flush()
    return blocks, stats


# ----------------------------------------------------------------------------- extraction
def candidate_type(text):
    nfr, fr = bool(NFR_CUES.search(text)), bool(FR_CUES.search(text))
    if nfr and not fr:
        return "NFR", "nfr_cue:" + NFR_CUES.search(text).group(0).lower()
    if fr and not nfr:
        return "FR", "fr_cue:" + FR_CUES.search(text).group(0).lower()
    return "unknown", ""


def extract_document(name, text, fmt, line_map=None):
    blocks, stats = prepare_blocks(text)
    rows, dropped = [], Counter(stats)
    for line_start, block in blocks:
        if DELETED.search(block):
            dropped["deleted"] += 1
            continue
        label_match = NUMBERED.match(block) or BULLET.match(block)
        label = label_match.group(0).strip() if label_match else ""
        body = block[label_match.end():].strip() if label_match else block
        if NOTE.match(block) or NOTE.match(body):
            dropped["note_or_example"] += 1
            continue
        markers = MARKER.findall(block)
        marker_text = ",".join(m.strip("[]") for m in markers)
        if is_heading(block) and not MODAL.search(block):
            dropped["heading"] += 1
            continue
        sentences = split_sentences(MARKER.sub("", body))
        has_modal = bool(MODAL.search(body))
        numbered = bool(label_match and not BULLET.match(block)) or bool(markers)
        if numbered and len(sentences) <= 3 and len(body.split()) >= 5:
            if has_modal:
                rule = "numbered_clause_modal"
            elif body[:1].isupper() and (body.endswith((".", "!", "?")) or markers):
                rule = "numbered_clause_no_modal"
            else:
                dropped["numbered_not_sentence_like"] += 1
                continue
            units = [(block, MARKER.sub("", body), rule)]
        else:
            units = [(s, s, "modal_sentence") for s in sentences if MODAL.search(s) and len(s.split()) >= 4 and not NOTE.match(s)]
            if not units:
                dropped["no_requirement_cue"] += 1
                continue
        for original, cleaned, rule in units:
            cleaned = collapse(MARKER.sub("", cleaned))
            if len(cleaned.split()) < 4:
                dropped["too_short"] += 1
                continue
            ctype, trule = candidate_type(cleaned)
            rows.append({"source_document": name, "source_format": fmt, "line_start": line_start, "clause_label": label,
                         "source_marker": marker_text, "original_text": original, "cleaned_text": cleaned,
                         "word_count": len(cleaned.split()), "candidate_type": ctype, "type_rule": trule,
                         "extraction_rule": rule, "length_flag": ("long_over_120_words" if len(cleaned.split()) > 120 else "")})
            if line_map is not None:
                # optional source reference (used by the API): line_map[line_number] = (page or None, paragraph); rows are unchanged without it
                rows[-1]["page"], rows[-1]["paragraph"] = line_map.get(line_start, (None, None))
    return rows, dropped, len(blocks)


def segment_document(name, text, fmt, line_map=None):
    """Rows (dicts) for one document, each with `position` and `srs_record_id`. Also returns the dropped-line counter and block count.
    With `line_map` ({line_number: (page, paragraph)}) every row also carries `page` and `paragraph`; without it the rows are exactly as before."""
    rows, dropped, n_blocks = extract_document(name, text, fmt, line_map)
    for position, r in enumerate(rows, start=1):
        r["position"] = position
        r["srs_record_id"] = f"SRS:{re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')}:{position:04d}"
    return rows, dropped, n_blocks
