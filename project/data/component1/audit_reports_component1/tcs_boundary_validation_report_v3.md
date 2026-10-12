# TCS SRS Boundary Audit v3 - Validation Report

Generated 2026-10-12 10:22:01.

## Source integrity (files are never written by this script)

- Original PDF: `data/component1/raw/documents/srs/1999 - tcs.pdf` size=588229 sha256=16c34d404c8f9de2d72b6ccfca3a0e1392a14f821b7a625e71f05b3897dac9b0
- Extracted text: `data/component1/processed/srs_extracted_text/1999 - tcs.txt` size=264605 sha256=391dfdf339ee3f9b53cfe0b0f033ad32aeca253940ea5c21bab33666fa017e39
- Both hashes were identical before and after the run (asserted).

- Offsets are character offsets into the text decoded as UTF-8 with the BOM removed and CRLF preserved.
- Second engine: C:\Program Files\Git\mingw64\bin\pdftotext.EXE

## Automated checks

| check | result | detail |
|---|---|---|
| markers_detected_equals_rows | PASS | 528 markers, 528 rows |
| source_order_contiguous_from_1 | PASS | 1..N in text order |
| marker_offsets_strictly_increasing | PASS |  |
| original_marker_matches_source_slice | PASS | text[start:end] == original_marker for every row |
| candidate_offsets_inside_gap_before_marker | PASS | candidate begins after previous marker and before this one |
| candidate_text_matches_slice_when_no_furniture_removed | PASS | candidate_text is an unmodified (whitespace-collapsed) slice |
| all_rows_have_normalized_id | PASS | 0 blank |
| no_duplicate_normalized_ids | PASS | 0 duplicates; unique=528 |
| no_duplicate_rows | PASS |  |
| required_fields_non_empty | PASS | boundary_status, requirement_type, review_reason, source_verification_status, recommended_action, review_evidence |
| marker_sequence_identical_in_pdf_text_layer_and_txt | PASS | pypdf page-wise tokens == txt tokens |
| txt_equals_pypdf_text_layer_modulo_whitespace | PASS | whitespace-normalised equality |
| extracted_text_unchanged_since_earlier_quality_audit | PASS | characters match=True, words match=True, sha256(whitespace-collapsed text) match=True |
| every_deleted_row_excluded_from_eligible | PASS |  |
| eligible_rows_have_no_unresolved_marker | PASS |  |
| parents_with_children_have_composite_text | PASS |  |
| fragment_children_reference_existing_parent | PASS |  |
| all_v2_manual_review_entries_have_v3_disposition | PASS | 205 v2-flagged rows dispositioned |
| every_row_needing_review_appears_in_unresolved_report | PASS | 73 rows needing review, 0 not covered |
| unresolved_report_references_only_known_markers | PASS |  |
| every HIGH/MEDIUM issue is on the manual-review checklist | PASS | 122 serious issue records; checklist rows=159 |
| checklist carries no fabricated review (all PENDING, reviewer/date/evidence blank, human_verified=NO) | PASS |  |
| checklist review ids unique | PASS |  |
| eligible_without_open_medium_or_high_issue is a subset of eligible and excludes serious issues | PASS |  |
| every proposed merge lists existing source ids | PASS |  |
| every_row_states_review_basis_not_human_verified | PASS | no row claims human verification |

**26 / 26 checks passed.**

## Counts requested for the audit

1. Markers detected: 528
2. Unique normalized IDs: 528
3. Duplicate normalized IDs: 0
4. Malformed marker IDs: 9; spaced: 19; non-numeric: 0
5. Source order preserved: see check `source_order_contiguous_from_1`
6. Every row has a source location and a status: see checks above
7. Boundary status counts:

   - VALID_STANDALONE_CANDIDATE: 352
   - LIST_ITEM_OR_CHILD_FRAGMENT: 65
   - MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT: 46
   - DELETED_REQUIREMENT: 25
   - PARENT_REQUIREMENT: 23
   - HEADING_OR_TABLE_CONTAMINATION: 10
   - UNRESOLVED_MANUAL_REVIEW: 7
8. Verified vs unresolved:
   - two-engine text-layer ID+context agreement: 528
   - visually / human verified: 0
   - unresolved-issue records: 143 (103 distinct markers; 36 numbering-gap IDs)
9. Deleted entries excluded from active candidates: 25
10. Entries with unresolved marker/extraction problems: 9 unresolved ID; 0 without full two-engine agreement
11. Duplicate rows: 0; missing required fields: see check `required_fields_non_empty`
12. Every final inclusion/exclusion decision carries `review_reason`, `review_evidence` and `review_basis` (rule-based, not human-verified).

## Traceability appendix cross-check

- Unbracketed `SSS###` references: 326, all after the last marker (offset >= 141474); distinct IDs referenced: 325.
- IDs referenced in the appendix but with no marker: 2 ['SSS296', 'SSS299']
- Marker IDs absent from the appendix: 205 ['SSS010', 'SSS014', 'SSS015', 'SSS016', 'SSS017', 'SSS019', 'SSS020', 'SSS029', 'SSS030', 'SSS031', 'SSS032', 'SSS033', 'SSS035', 'SSS037', 'SSS038', 'SSS039', 'SSS040', 'SSS041', 'SSS042', 'SSS043', 'SSS044', 'SSS048', 'SSS050', 'SSS052', 'SSS057', 'SSS068', 'SSS069', 'SSS071', 'SSS072', 'SSS073']
- IDs inside the observed numeric range with no marker: 36 ['SSS005', 'SSS006', 'SSS007', 'SSS018', 'SSS034', 'SSS049', 'SSS077', 'SSS078', 'SSS094', 'SSS123', 'SSS150', 'SSS156', 'SSS166', 'SSS169', 'SSS181', 'SSS183', 'SSS199', 'SSS204', 'SSS205', 'SSS216', 'SSS217', 'SSS221', 'SSS229', 'SSS266', 'SSS284', 'SSS296', 'SSS299', 'SSS333', 'SSS433', 'SSS451', 'SSS460', 'SSS483', 'SSS498', 'SSS530', 'SSS562', 'SSS566']
- Of those, cited in the appendix: ['SSS296', 'SSS299']
- shall/must/should occurrences outside the marker-bearing region (not audited here): 2 before the first segment, 513 after the last marker

## Coverage of the requested verification items

Each item is enforced by an automated test in `tests/test_tcs_boundary_audit.py` (run it after any change). The tests re-derive their expectations from the source text, the PDF and the generated files rather than from hard-coded counts.

| item | enforced by |
|---|---|
| 1 every bracketed SSS marker has exactly one row | `test_every_bracketed_sss_marker_in_the_source_has_a_row` |
| 2 IDs unique, original marker strings preserved | `test_ids_are_unique_and_match_marker_digits; test_offsets_locate_each_marker_in_the_source` |
| 3 offsets locate each marker | `test_offsets_locate_each_marker_in_the_source` |
| 4 source order preserved | `test_markers_are_in_source_order` |
| 5 parent references resolve to preceding markers | `test_parent_references_resolve_and_precede_the_child` |
| 6 deleted entries never eligible | `test_deleted_or_unresolved_rows_are_never_eligible; test_deleted_rows_contain_only_the_placeholder` |
| 7 unresolved entries never eligible | `test_deleted_or_unresolved_rows_are_never_eligible; test_malformed_ids_are_never_eligible_and_never_inferred_as_resolved` |
| 8 every row needing review is in the issue report | `test_every_row_needing_review_is_in_the_unresolved_report; test_every_malformed_marker_and_spaced_marker_is_in_the_issue_report` |
| 9 candidate text traceable to the source | `test_candidate_text_comes_from_the_source_without_invented_words` |
| 10 Appendix A comparisons computed from real text | `test_appendix_matches_recorded_in_table_are_really_equal_in_the_source; AppendixCrossCheck` |
| 11 categories and eligibility follow the rules | `SyntheticClassification; test_eligible_rows_really_contain_a_single_obligation_sentence` |
| 12 status counts reconcile | `test_status_counts_add_up_and_review_fields_are_present` |
| 13 nothing marked human-verified | `test_no_row_is_marked_human_verified; test_checklist_is_complete_and_contains_no_fabricated_review` |
| 14 mandatory fields non-empty | `test_status_counts_add_up_and_review_fields_are_present; test_issue_records_carry_all_review_fields` |
| 15 no duplicate records | `test_ids_are_unique_and_match_marker_digits; test_issue_records_carry_all_review_fields` |
| 16 page mapping used by the checklist | `test_pdf_page_mapping_matches_an_independent_per_page_count` |
| numbering gaps | `test_numbering_gaps_are_exactly_the_ids_without_a_marker` |
| merge policy and derived text | `test_merge_fields_follow_the_documented_policy; test_r1_composite_is_an_exact_source_slice` |
| wording differences recorded, not reconciled | `test_appendix_wording_differences_are_recorded_not_reconciled` |
| determinism and source integrity | `test_classification_is_deterministic; test_source_files_match_the_hashes_recorded_in_the_validation_report` |

## Discrepancies and observations

1. **Eligible does not mean clean.** 350 rows pass the mechanical eligibility rules, but 14 of them carry an open Appendix A wording issue (MEDIUM). `eligible_without_open_medium_or_high_issue` counts 336. Nothing was reconciled automatically.
2. **Issue-record count.** Earlier runs listed fewer issue records. The 19 spaced/extractor-dependent markers are now listed explicitly as LOW severity; this changes the issue report only, not any classification or eligibility decision.
3. **Wording differences.** 15 body/Appendix A wording differences are recorded (14 valid segments, 1 parent). Appendix A is a separately maintained copy and is not ground truth.
4. **Appendix A matches are exact after normalisation** (case, spacing and punctuation ignored); anything with a word-level difference is reported as nearly identical, similar or different, never as a match.
5. **Page references are file page indexes** (1-based, from the PDF's own page tree). The printed page number is only a hint from the text layer; numbering-gap rows use the numeric neighbour's page.
6. **No human or visual verification exists.** `pdftoppm` is not installed, so pages could not be rendered; both text-layer engines read the same embedded text, so their agreement does not prove the printed marker or wording.
