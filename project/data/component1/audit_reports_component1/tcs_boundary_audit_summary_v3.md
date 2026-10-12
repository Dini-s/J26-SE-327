# TCS SRS Boundary Audit v3 - Summary

Generated 2026-10-12 10:22:01 by `experiments/component1/audit_tcs_requirement_boundaries.py`.
Source: `1999 - tcs.pdf` (Microsoft Word -> Acrobat PDFWriter 3.0, 148 pages, text layer present) and its pypdf extraction `1999 - tcs.txt`.

**Basis of every finding below:** rule-based analysis of the extracted text plus a two-engine comparison of the PDF text layer
(pypdf vs. pdftotext). No page was rendered or visually inspected and no human has verified any boundary.

## Counts

- Markers detected: **528** (V2 report listed 511; it silently missed 17 markers: 8 with spaces inside the digits and 9 with 5-6 digits)
- Unique normalized IDs: **528** (duplicates: 0)
- Marker formats: CLEAN=500, WHITESPACE_IN_MARKER=19, EXTRA_DIGITS=9
- Markers where both text-layer engines agree on ID and preceding context: **528** / 528
- Rows eligible as provisional standalone candidates (valid boundary rules + resolved ID + two-engine agreement + not deleted + subject present): **350**
- Of those, rows with **no open MEDIUM or HIGH issue**: **336** (14 are eligible but carry an open Appendix A wording issue)
- Rows verified visually or by a human: **0**

### Boundary status

| boundary_status | rows |
|---|---|
| VALID_STANDALONE_CANDIDATE | 352 |
| LIST_ITEM_OR_CHILD_FRAGMENT | 65 |
| MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT | 46 |
| DELETED_REQUIREMENT | 25 |
| PARENT_REQUIREMENT | 23 |
| HEADING_OR_TABLE_CONTAMINATION | 10 |
| UNRESOLVED_MANUAL_REVIEW | 7 |

### Source verification status (text-layer only)

| status | rows |
|---|---|
| TEXT_LAYER_TWO_ENGINE_ID_AND_CONTEXT_AGREE | 528 |

### Heuristic flags (not mutually exclusive)

| flag | rows |
|---|---|
| NONE | 251 |
| HEADING_REMOVED_FROM_SPAN | 137 |
| UNMARKED_TEXT_BEFORE_HEADING | 54 |
| PAGE_FURNITURE_REMOVED | 49 |
| LIST_LINES_IN_SEGMENT | 41 |
| CLAUSE_CONTINUATION | 37 |
| DELETED_MARKER_TEXT | 25 |
| VERY_SHORT_SEGMENT | 21 |
| PERIOD_AFTER_MARKER | 14 |
| STRAY_LEADING_PUNCTUATION_REMOVED | 12 |
| LONG_SEGMENT | 11 |
| TABLE_OR_FIGURE_LINES_IN_SEGMENT | 9 |
| MULTIPLE_OBLIGATION_MODALS | 3 |
| MISSING_SUBJECT_IN_SOURCE_TEXT | 1 |

### Edge-case review coverage

Every row carries a `boundary_status`, `review_reason` and `review_evidence`; the table shows how many rows fall in each required edge-case group (groups overlap) and which column to filter.

| edge case | rows | where |
|---|---|---|
| Entries flagged MANUAL_REVIEW_REQUIRED in V2 | 205 | `v2_flag_disposition` |
| Deleted-status entries | 25 | `deleted_status`, `boundary_status` |
| Very short segments (<40 chars) | 21 | `heuristic_flags` |
| Long segments (>500 chars) | 11 | `heuristic_flags` |
| Heading context (heading inside the span) | 137 | `headings_removed` |
| List context | 41 | `heuristic_flags`, `requirement_type` |
| Table / figure context | 9 | `heuristic_flags` |
| Spaced or malformed marker IDs | 28 | `marker_format`, `normalization_status` |
| Several shall/must/should in one segment | 3 | `obligation_modal_count` |
| Parent / child relationships (children + parents) | 96 | `parent_requirement_id`, `child_marker_count`, `parent_composite_text` |
| Markers with no obvious requirement sentence | 28 | `requirement_type` |
| Duplicate, spaced, malformed or backward-stepping IDs | 62 | `id_sequence_note`, `marker_format` |

### Appendix A cross-check (in-document restatement; not a visual check)

| appendix_a_crosscheck | all rows | valid segments |
|---|---|---|
| NO_APPENDIX_ENTRY | 241 | 152 |
| APPENDIX_MATCHES_CANDIDATE | 128 | 119 |
| APPENDIX_SIMILAR_NOT_IDENTICAL | 51 | 43 |
| APPENDIX_TEXT_DIFFERS | 43 | 14 |
| APPENDIX_NEARLY_IDENTICAL | 18 | 13 |
| CANDIDATE_CONTAINED_IN_APPENDIX_TEXT | 17 | 5 |
| APPENDIX_TEXT_CONTAINED_IN_CANDIDATE | 15 | 4 |
| APPENDIX_MATCHES_PROPOSED_SENTENCE_ONLY | 13 | 0 |
| APPENDIX_ENTRY_EMPTY | 2 | 2 |

### V2 flag reconciliation

| disposition | rows |
|---|---|
| V2_UNFLAGGED_V3_AGREES | 240 |
| V2_FLAG_NOT_REPRODUCED_UNDER_V3_RULES | 107 |
| V2_FLAG_CONFIRMED_AS_LIST_ITEM_OR_CHILD_FRAGMENT | 38 |
| V2_FLAG_CONFIRMED_AS_MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT | 26 |
| V2_UNFLAGGED_BUT_V3_FOUND_LIST_ITEM_OR_CHILD_FRAGMENT | 26 |
| V2_UNFLAGGED_BUT_V3_FOUND_MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT | 19 |
| V2_FLAG_CONFIRMED_AS_DELETED_REQUIREMENT | 17 |
| NOT_IN_V2_MARKER_NOT_DETECTED_BY_V2 | 17 |
| V2_UNFLAGGED_BUT_V3_FOUND_PARENT_REQUIREMENT | 13 |
| V2_FLAG_CONFIRMED_AS_PARENT_REQUIREMENT | 8 |
| V2_FLAG_CONFIRMED_AS_HEADING_OR_TABLE_CONTAMINATION | 8 |
| V2_UNFLAGGED_BUT_V3_FOUND_UNRESOLVED_MANUAL_REVIEW | 6 |
| V2_UNFLAGGED_BUT_V3_FOUND_HEADING_OR_TABLE_CONTAMINATION | 2 |
| V2_FLAG_CONFIRMED_AS_UNRESOLVED_MANUAL_REVIEW | 1 |

## Findings

1. **V2 under-counted markers.** The text and the PDF text layer both contain 528 bracketed `SSS` markers. V2 omitted 17: 8 whose digits are split by a space (`[SSS0 65]`, `[SSS1 32]`, ...) and 9 whose token has 5-6 digits (`[SSS126102]`, `[SSS25405]`, ...). No generator script for V2 exists in the repository, so its logic could not be inspected.
2. **The PDF is born-digital, so the anomalies are not OCR.** The extracted text equals pypdf's text-layer output. 19 markers contain whitespace; for 18 of them pdftotext renders a clean 3-digit marker (for example `[SSS02 7]` -> `[SSS027]`), so the spacing is extractor-dependent. Still spaced in both engines: [SSS 559].
3. **9 markers carry extra digits in the PDF text layer itself** (identical token in both engines for 9): 8 of them are `**DELETED**` placeholders with trailing digits [SSS25405] (+05), [SSS25506] (+06), [SSS25607] (+07), [SSS25708] (+08), [SSS27019] (+19), [SSS27120] (+20), [SSS27221] (+21), [SSS27322] (+22); the other 1 is an active requirement ([SSS126102] (+102) on PDF page 29). The 3-digit prefix fits the numeric sequence and is unused elsewhere in every case, but 0 of the 9 prefixes are cited in Appendix A, so the appendix gives no corroboration. The correct ID therefore stays a **hypothesis** until the printed marker is read on the page.
4. **Markers trail their text** and often tag clauses of one sentence. Example: `SSS542` heads *Initialization of the TCS HWCIs shall include startup of HWCIs*, continued by `SSS026`, `SSS027`, `SSS025` and `SSS028`. By sentence evidence the parent of `SSS026` is `SSS542`, not `SSS024` as guessed in `tcs_manual_review_examples.csv`; likewise the parent chain for `SSS097` is the list lead in `SSS096`, not `SSS535` (a map-scale requirement that precedes it). In 34 segments an unmarked narrative or definition sentence precedes the one sentence that contains shall/must/should.
5. **Deleted entries:** 25 markers consist only of the `**DELETED**` placeholder and are excluded from active candidates (V2 flagged 17).
6. **Missing subject:** 1 segment (`SSS559`) reads *The shall provide the functionality ...* in both engines. This is a source defect and was not repaired.
7. **Numbering gaps:** 36 IDs inside the observed range have no body marker. 2 of them (SSS296, SSS299) are listed as `(Deleted)` in Appendix A, which explains them; 34 appear nowhere in the body or the appendix (never assigned or removed without a trace).
8. **Appendix A is an independent in-document restatement.** It repeats the text of 287 marker IDs under an `SSS###` line. 119 of the 352 valid segments match it verbatim (after ignoring case, spacing and punctuation) and 152 have no appendix entry. For 13 of the 34 "narrative before marked sentence" segments the appendix text equals exactly the proposed last sentence, which supports excluding the preceding narrative. Differences are usually wording revisions (the appendix is a separately maintained copy), so a difference is a provenance/version note, not proof of a boundary error.
9. **Document-wide ID order is not numeric.** 35 markers step backwards numerically (requirements added later), so numeric order cannot validate boundaries.

## Recommendation

**Provisional candidate source - not approved for training or evaluation use.**

The document is a real, structured requirements specification with a consistent marker convention (markers trail their text; 528 markers were located and matched in two text-layer engines),
and the text is unchanged since the earlier extraction audit. But the evidence does not yet justify treating its segments as clean requirements:

- Only **350 of 528** segments pass every automated criterion for standalone use (119 of those also match Appendix A verbatim). None is visually or human verified.
- 65 segments are clause or list fragments and 23 are parents; they must be merged into their parent's composite text, never used one by one.
- 46 segments mix narrative or several statements under one marker and 10 contain table, figure or list rows.
- 103 markers plus 36 numbering gaps need human or PDF-page verification (143 issue records in `tcs_unresolved_issues_v3.csv`), including 9 marker IDs whose extra digits cannot be resolved from the text layer.

**What would raise the status:** a human check of the flagged pages against the PDF (especially the 9 extra-digit IDs and the mixed-context segments), and a decision on the fragment/parent merge rule. Until then, if TCS segments are used at all, restrict them to the 350 eligible rows and exclude deleted placeholders.

## Merge and canonical-wording policy

1. Original markers, source offsets, `candidate_text` and `appendix_a_text` are never altered. Derived text exists only in `parent_composite_text`, with its rule in `composite_rule` and its members in `merged_source_ids`.
2. **R1 clause chain.** A segment that continues a sentence (starts with `,` / `;` / lowercase after another marker's text) is a clause of that sentence. The head's composite is the exact source slice from the head to the last clause marker, page furniture removed. Clause rows keep their own IDs, point to the head in `parent_requirement_id`, and are never eligible alone.
3. **R2 list lead.** Items that start with a list label (`1.`, `(1)`, `Level n:`, a bullet) after a lead sentence ending in `:` or containing "following" point to the lead's marker. The composite is a *derived concatenation* of the lead segment and the item `candidate_text` values in source order. Items are **not** merged automatically because each may be an independent obligation; their `merge_status` is `LIST_ITEM_INDEPENDENCE_UNDECIDED` and they stay ineligible.
4. Every proposed merge has `merge_status = PROPOSED_PENDING_HUMAN_CONFIRMATION`; nothing is final until a person decides on the checklist.
5. Deleted placeholders are excluded (`EXCLUDED_DELETED`). Uncertain fragments stay ineligible.
6. Body text is preserved as `candidate_text`; Appendix A wording is kept beside it. Differences are recorded as `APPENDIX_A_WORDING_DIFFERS_FROM_BODY` (MEDIUM) and are not reconciled. Such rows remain mechanically eligible but are visible through `open_issue_types` and `eligible_without_open_medium_or_high_issue`.

## Human review status

**No human review has been performed.** `tcs_manual_review_checklist_v3.csv` lists 159 items (36 numbering gaps, 123 markers/merge groups) on 45 distinct PDF file pages, sorted by page. Every `human_decision` is `PENDING` and `reviewer`, `review_date`, `human_evidence` are blank. Page numbers are the file's page index; the printed page number is only a text-layer hint.

Pages to inspect (file index): 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 43, 44, 45, 46, 47, 48, 51, 52, 53, 54, 55, 56, 57, 58, 59, 61, 63, 64, 65, 66, 67

## Limitations

- Boundary rules are heuristics (sentence splitting, heading regex, list/table patterns); false positives and negatives are expected.
- No rendered-page comparison was possible (no page renderer installed); both engines read the same PDF text layer, so they are not independent of encoding defects in the document itself.
- Requirement type (functional / non-functional) was deliberately not assigned.
- `source_verification_status` verifies marker ID and preceding context in the text layer only, not requirement meaning.

## Reproduce

```powershell
cd project
..\.venv\Scripts\python.exe experiments\component1\audit_tcs_requirement_boundaries.py --overwrite
..\.venv\Scripts\python.exe -m unittest tests.test_tcs_boundary_audit -v
```
Requires `pdftotext` (poppler/xpdf) on PATH for the second-engine check; without it all rows are marked `UNVERIFIED_SECOND_ENGINE_UNAVAILABLE`.
