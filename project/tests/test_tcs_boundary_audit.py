"""Tests for the TCS requirement-boundary audit.

Run from the project directory:
    ..\\.venv\\Scripts\\python.exe -m unittest tests.test_tcs_boundary_audit -v

Part 1 exercises the parser/classifier on a small synthetic document whose structure is known.
Part 2 re-derives invariants of the generated v3 table directly from the source text, so it
fails if the table drifts from the source rather than merely asserting expected counts.
"""
import hashlib
import importlib.util
import re
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "experiments" / "component1" / "audit_tcs_requirement_boundaries.py"
spec = importlib.util.spec_from_file_location("audit_tcs", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

SYNTHETIC = (
    "3.1 Heading Title\r\n"
    "The TCS shall do alpha. [SSS001]\r\n"
    "Startup shall include a [SSS002]\r\n"
    ", b [SSS003], and c. [SSS004]\r\n"
    "**DELETED** [SSS005]\r\n"
    "The shall do beta. [SSS006]\r\n"
    "The TCS shall support the following:\r\n"
    "1. first item. [SSS007]\r\n"
    "2. second item. [SSS008]\r\n"
    "Background fact is stated here. The TCS shall do gamma. [SSS009]\r\n"
    "The TCS will do delta. [SSS 010]\r\n"
    "The TCS shall do epsilon. [SSS01199]\r\n"
)


class MarkerParsing(unittest.TestCase):
    def test_marker_formats(self):
        self.assertEqual(audit.parse_marker_inner("004"), ("004", "CLEAN", "EXACT"))
        self.assertEqual(audit.parse_marker_inner("02 7"), ("027", "WHITESPACE_IN_MARKER", "WHITESPACE_REMOVED"))
        self.assertEqual(audit.parse_marker_inner(" 209"), ("209", "WHITESPACE_IN_MARKER", "WHITESPACE_REMOVED"))
        self.assertEqual(audit.parse_marker_inner("25405")[1:], ("EXTRA_DIGITS", "HYPOTHESIS_FIRST_3_DIGITS_UNVERIFIED"))
        self.assertEqual(audit.parse_marker_inner("12a")[1], "NON_NUMERIC_OR_SHORT")

    def test_markers_found_in_order_with_exact_offsets(self):
        markers = audit.find_markers(SYNTHETIC)
        self.assertEqual([m["source_order"] for m in markers], list(range(1, 12)))
        for m in markers:
            self.assertEqual(SYNTHETIC[m["marker_start_char"]:m["marker_end_char"]], m["original_marker"])
        spaced = markers[9]
        self.assertEqual((spaced["original_marker"], spaced["normalized_candidate_id"]), ("[SSS 010]", "SSS010"))
        self.assertEqual(markers[10]["normalized_candidate_id"], "SSS011")
        self.assertEqual(markers[10]["normalization_status"], "HYPOTHESIS_FIRST_3_DIGITS_UNVERIFIED")


class SyntheticClassification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        markers = audit.find_markers(SYNTHETIC)
        cls.rows, _ = audit.build_rows(SYNTHETIC, markers)

    def test_heading_is_removed_but_reported(self):
        row = self.rows[0]
        self.assertEqual(row["candidate_text"], "The TCS shall do alpha.")
        self.assertEqual(row["headings_removed"], "3.1 Heading Title")
        self.assertEqual(row["boundary_status"], "VALID_STANDALONE_CANDIDATE")

    def test_clause_chain_parent_and_children(self):
        parent, child_a, child_b = self.rows[1], self.rows[2], self.rows[3]
        self.assertEqual(parent["boundary_status"], "PARENT_REQUIREMENT")
        self.assertEqual(parent["child_marker_count"], 2)
        self.assertEqual(parent["parent_composite_text"], "Startup shall include a [SSS002] , b [SSS003], and c. [SSS004]")
        for child in (child_a, child_b):
            self.assertEqual(child["boundary_status"], "LIST_ITEM_OR_CHILD_FRAGMENT")
            self.assertEqual(child["parent_requirement_id"], "SSS002")

    def test_deleted_placeholder_is_excluded(self):
        row = self.rows[4]
        self.assertEqual((row["boundary_status"], row["deleted_status"]), ("DELETED_REQUIREMENT", "DELETED_PLACEHOLDER"))

    def test_missing_subject_is_flagged_and_text_is_not_repaired(self):
        row = self.rows[5]
        self.assertIn("MISSING_SUBJECT_IN_SOURCE_TEXT", row["heuristic_flags"])
        self.assertEqual(row["candidate_text"], "The shall do beta.")

    def test_list_lead_with_first_item_and_following_items(self):
        lead, item = self.rows[6], self.rows[7]
        self.assertEqual(lead["requirement_type"], "LIST_LEAD_PLUS_FIRST_ITEM")
        self.assertEqual(lead["child_marker_count"], 1)
        self.assertEqual((item["boundary_status"], item["parent_requirement_id"]), ("LIST_ITEM_OR_CHILD_FRAGMENT", "SSS007"))

    def test_unmarked_narrative_before_marked_sentence(self):
        row = self.rows[8]
        self.assertEqual(row["boundary_status"], "MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT")
        self.assertEqual(row["requirement_type"], "UNMARKED_NARRATIVE_BEFORE_MARKED_SENTENCE")
        self.assertEqual(row["proposed_marked_sentence"], "The TCS shall do gamma.")

    def test_will_alone_is_not_treated_as_a_requirement(self):
        row = self.rows[9]
        self.assertEqual((row["boundary_status"], row["requirement_type"]), ("UNRESOLVED_MANUAL_REVIEW", "NO_OBLIGATION_MODAL"))

    def test_shall_alone_does_not_make_a_segment_valid_when_structure_is_unclear(self):
        # a long multi-statement segment containing 'shall' must not be classed as a single valid requirement
        text = "Intro sentence one. Intro sentence two. The TCS shall do x. Another shall be y. [SSS001]\r\n"
        rows, _ = audit.build_rows(text, audit.find_markers(text))
        self.assertNotEqual(rows[0]["boundary_status"], "VALID_STANDALONE_CANDIDATE")


APPENDIX_TEXT = (
    "front matter\r\n"
    "APPENDIX A: Requirements Traceability Matrix\r\n"
    "ORD NUMBER ORD REQUIREMENT SSS REQIREMENT AND NUMBER\r\n"
    "ORD001 The TCS shall be small. SSS440\r\n"
    "SSS440\r\n"
    " TCS hardware flexibility shall be provided\r\n"
    "through use of GFE.\r\n"
    "TCS Block 0 TCS 102\r\n"
    "Version 2.0 2/12/99\r\n"
    "67\r\n"
    "SSS441\r\n"
    "(Deleted)\r\n"
    "ORD002 The TCS shall be fast. SSS442\r\n"
    "SSS442\r\n"
    "APPENDIX B: MAE Applicable Capability Criteria\r\n"
    "SSS999\r\n"
    "not in appendix a\r\n"
)


class AppendixCrossCheck(unittest.TestCase):
    def test_entries_are_taken_from_id_only_lines_and_ord_lines_are_ignored(self):
        entries = audit.parse_appendix_a(APPENDIX_TEXT)
        self.assertEqual(entries["SSS440"], ["TCS hardware flexibility shall be provided through use of GFE."])
        self.assertEqual(entries["SSS441"], ["(Deleted)"])
        self.assertEqual(entries["SSS442"], [""])
        self.assertNotIn("SSS999", entries)  # after APPENDIX B

    def _row(self, rid, candidate, proposed="", composite=""):
        return {"normalized_candidate_id": rid, "candidate_text": candidate,
                "proposed_marked_sentence": proposed, "parent_composite_text": composite}

    def test_crosscheck_categories(self):
        entries = {"SSS001": ["The TCS shall do alpha."], "SSS002": ["The TCS shall do beta."],
                   "SSS003": ["(Deleted)"], "SSS004": ["The TCS shall do delta."], "SSS005": [""],
                   "SSS006": ["Totally unrelated wording about something else entirely."]}
        rows = [self._row("SSS001", "the TCS shall do  alpha"),                       # case/space/punctuation insensitive
                self._row("SSS002", "Background. The TCS shall do beta.", proposed="The TCS shall do beta."),
                self._row("SSS003", "**DELETED**"),
                self._row("SSS004", "The TCS shall do delta. Plus more text follows here."),
                self._row("SSS005", "The TCS shall do epsilon."),
                self._row("SSS006", "The TCS shall do zeta."),
                self._row("SSS007", "No entry here."),
                self._row("SSS008", "The TCS shall provide alpha beta gamma delta epsilon zeta eta theta iota kappa lambda nu.")]
        entries["SSS008"] = ["The TCS shall provide alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu."]
        got = [r["appendix_a_crosscheck"] for r in audit.appendix_crosscheck(rows, entries)]
        self.assertEqual(got, ["APPENDIX_MATCHES_CANDIDATE", "APPENDIX_MATCHES_PROPOSED_SENTENCE_ONLY",
                               "APPENDIX_SAYS_DELETED", "APPENDIX_TEXT_CONTAINED_IN_CANDIDATE",
                               "APPENDIX_ENTRY_EMPTY", "APPENDIX_TEXT_DIFFERS", "NO_APPENDIX_ENTRY",
                               "APPENDIX_NEARLY_IDENTICAL"])


@unittest.skipUnless((audit.OUT_TABLE).exists(), "run the audit script first to create the v3 table")
class GeneratedTableInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = audit.SRC_TXT.read_bytes().decode("utf-8-sig")
        cls.df = pd.read_csv(audit.OUT_TABLE, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        cls.unresolved = pd.read_csv(audit.OUT_UNRESOLVED, encoding="utf-8-sig", dtype=str, keep_default_na=False)

    def test_every_bracketed_sss_marker_in_the_source_has_a_row(self):
        independent = [m.group(0) for m in re.finditer(r"\[[^\[\]]*SSS[^\[\]]*\]", self.text)]
        self.assertEqual(list(self.df.original_marker), independent)

    def test_offsets_locate_each_marker_in_the_source(self):
        for r in self.df.itertuples():
            self.assertEqual(self.text[int(r.marker_start_char):int(r.marker_end_char)], r.original_marker)

    def test_markers_are_in_source_order(self):
        starts = self.df.marker_start_char.astype(int).tolist()
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(self.df.source_order.astype(int).tolist(), list(range(1, len(self.df) + 1)))

    def test_candidate_text_comes_from_the_source_without_invented_words(self):
        for r in self.df.itertuples():
            window = audit.collapse(self.text[int(r.source_start_char):int(r.marker_start_char)])
            for token in re.findall(r"\S+", r.candidate_text):
                self.assertIn(token, window, f"{r.original_marker}: {token!r} not found in its source window")

    def test_ids_are_unique_and_match_marker_digits(self):
        self.assertFalse(self.df.normalized_candidate_id.duplicated().any())
        for r in self.df.itertuples():
            digits = re.sub(r"\D", "", r.original_marker)
            self.assertEqual(r.normalized_candidate_id, "SSS" + digits[:3])

    def test_no_row_is_marked_human_verified(self):
        self.assertTrue((self.df.review_basis == "RULE_BASED_AUTOMATED_TEXT_LAYER_CHECK_NOT_HUMAN_VERIFIED").all())
        self.assertTrue((self.df.visual_pdf_verification == "NOT_PERFORMED_NO_PAGE_RENDERER").all())

    def test_deleted_or_unresolved_rows_are_never_eligible(self):
        eligible = self.df[self.df.eligible_as_standalone_candidate == "True"]
        self.assertTrue((eligible.boundary_status == "VALID_STANDALONE_CANDIDATE").all())
        self.assertTrue((eligible.deleted_status == "NONE").all())
        self.assertTrue(eligible.normalization_status.isin(["EXACT", "WHITESPACE_REMOVED"]).all())
        self.assertFalse(eligible.heuristic_flags.str.contains("MISSING_SUBJECT_IN_SOURCE_TEXT").any())

    def test_eligible_rows_really_contain_a_single_obligation_sentence(self):
        eligible = self.df[self.df.eligible_as_standalone_candidate == "True"]
        for r in eligible.itertuples():
            self.assertRegex(r.candidate_text, r"\b(shall|must|should)\b")
            self.assertEqual(int(r.sentence_count), 1, r.original_marker)

    def test_deleted_rows_contain_only_the_placeholder(self):
        for r in self.df[self.df.boundary_status == "DELETED_REQUIREMENT"].itertuples():
            residue = re.sub(r"\*\*DELETED\*\*|[\d\s.,;:]", "", r.candidate_text)
            self.assertEqual(residue, "", r.original_marker)

    def test_parent_references_resolve_and_precede_the_child(self):
        order = dict(zip(self.df.normalized_candidate_id, self.df.source_order.astype(int)))
        for r in self.df[self.df.parent_requirement_id != ""].itertuples():
            self.assertIn(r.parent_requirement_id, order)
            self.assertLess(order[r.parent_requirement_id], int(r.source_order))
        parents = set(self.df[self.df.parent_requirement_id != ""].parent_requirement_id)
        listed = set(self.df[self.df.child_marker_count.astype(int) > 0].normalized_candidate_id)
        self.assertEqual(parents, listed)

    def test_status_counts_add_up_and_review_fields_are_present(self):
        self.assertEqual(self.df.boundary_status.value_counts().sum(), len(self.df))
        for column in ("boundary_status", "requirement_type", "review_reason", "review_evidence", "recommended_action"):
            self.assertTrue((self.df[column] != "").all(), column)

    def test_every_row_needing_review_is_in_the_unresolved_report(self):
        needs = self.df[self.df.boundary_status.isin(["UNRESOLVED_MANUAL_REVIEW", "MULTIPLE_REQUIREMENTS_OR_MIXED_CONTEXT",
                                                      "HEADING_OR_TABLE_CONTAMINATION"])
                        | ~self.df.normalization_status.isin(["EXACT", "WHITESPACE_REMOVED"])]
        covered = set(self.unresolved.source_order) - {""}
        self.assertTrue(set(needs.source_order) <= covered)

    def test_appendix_matches_recorded_in_table_are_really_equal_in_the_source(self):
        entries = audit.parse_appendix_a(self.text)
        self.assertGreater(len(entries), 250)
        matched = self.df[self.df.appendix_a_crosscheck == "APPENDIX_MATCHES_CANDIDATE"]
        self.assertGreater(len(matched), 100)
        for r in matched.itertuples():
            candidate = audit.normalise_alnum(r.candidate_text)
            self.assertTrue(any(audit.normalise_alnum(t) == candidate for t in entries[r.normalized_candidate_id]),
                            r.original_marker)
        # rows that claim no appendix entry must truly have none
        for r in self.df[self.df.appendix_a_crosscheck == "NO_APPENDIX_ENTRY"].itertuples():
            self.assertNotIn(r.normalized_candidate_id, entries)

    # ---- Phase C/D/F additions: issues, checklist, merge fields, page mapping, determinism -----------------
    def test_pdf_page_mapping_matches_an_independent_per_page_count(self):
        from pypdf import PdfReader
        reader = PdfReader(str(audit.SRC_PDF))
        expected = []
        for number, page in enumerate(reader.pages, start=1):
            expected += [number] * len(re.findall(r"\[[^\[\]]*SSS[^\[\]]*\]", page.extract_text() or ""))
        self.assertEqual(self.df.pdf_page.astype(int).tolist(), expected)

    def test_issue_records_carry_all_review_fields(self):
        for column in ("severity", "pdf_inspection_required", "uncertainty", "resolving_evidence", "excluded_until_resolved",
                       "source_location", "issue_type", "verification_needed"):
            self.assertTrue((self.unresolved[column] != "").all(), column)
        self.assertTrue(set(self.unresolved.severity) <= {"HIGH", "MEDIUM", "LOW", "INFO"})
        for r in self.unresolved[self.unresolved.source_order != ""].itertuples():
            self.assertTrue(r.context_before and r.context_after, r.original_marker)
        self.assertFalse(self.unresolved.duplicated(subset=["source_order", "normalized_candidate_id", "issue_type"]).any())

    def test_every_malformed_marker_and_spaced_marker_is_in_the_issue_report(self):
        malformed = {r.original_marker for r in self.df.itertuples() if len(re.sub(r"\D", "", r.original_marker)) > 3}
        spaced = {r.original_marker for r in self.df.itertuples()
                  if len(re.sub(r"\D", "", r.original_marker)) == 3 and not re.fullmatch(r"\[SSS\d{3}\]", r.original_marker)}
        got = lambda t: set(self.unresolved[self.unresolved.issue_type == t].original_marker)
        self.assertEqual(got("MARKER_ID_MALFORMED_EXTRA_DIGITS"), malformed)
        self.assertEqual(got("MARKER_SPACING_EXTRACTOR_DEPENDENT"), spaced)
        self.assertEqual(len(malformed), 9)

    def test_malformed_ids_are_never_eligible_and_never_inferred_as_resolved(self):
        bad = self.df[self.df.marker_format == "EXTRA_DIGITS"]
        self.assertTrue((bad.eligible_as_standalone_candidate == "False").all())
        self.assertTrue((bad.normalization_status == "HYPOTHESIS_FIRST_3_DIGITS_UNVERIFIED").all())

    def test_missing_subject_text_is_preserved_and_not_eligible(self):
        row = self.df[self.df.normalized_candidate_id == "SSS559"].iloc[0]
        self.assertTrue(row.candidate_text.startswith("The shall provide"))
        self.assertEqual(row.eligible_as_standalone_candidate, "False")

    def test_open_issue_columns_agree_with_the_issue_report(self):
        marker_issues = self.unresolved[self.unresolved.source_order != ""]
        rank = {"HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1}
        for r in self.df.itertuples():
            mine = marker_issues[marker_issues.source_order == r.source_order]
            self.assertEqual(r.open_issue_types, ";".join(sorted(set(mine.issue_type))) if len(mine) else "NONE", r.original_marker)
            top = max((rank[s] for s in mine.severity), default=0)
            clean = r.eligible_as_standalone_candidate == "True" and top < 3
            self.assertEqual(r.eligible_without_open_medium_or_high_issue == "True", clean, r.original_marker)

    def test_appendix_wording_differences_are_recorded_not_reconciled(self):
        rows = self.unresolved[self.unresolved.issue_type == "APPENDIX_A_WORDING_DIFFERS_FROM_BODY"]
        self.assertGreater(len(rows), 0)
        for r in rows.itertuples():
            row = self.df[self.df.source_order == r.source_order].iloc[0]
            self.assertNotEqual(audit.normalise_alnum(row.candidate_text), audit.normalise_alnum(row.appendix_a_text))
            self.assertNotIn(row.appendix_a_text, row.candidate_text)  # body text was not overwritten with the appendix wording

    def test_numbering_gaps_are_exactly_the_ids_without_a_marker(self):
        numbers = sorted(int(i[3:]) for i in self.df.normalized_candidate_id)
        expected = {f"SSS{n:03d}" for n in range(numbers[0], numbers[-1] + 1) if n not in set(numbers)}
        gaps = self.unresolved[self.unresolved.source_order == ""]
        self.assertEqual(set(gaps.normalized_candidate_id), expected)
        self.assertEqual(len(gaps), 36)

    def test_checklist_is_complete_and_contains_no_fabricated_review(self):
        checklist = pd.read_csv(audit.OUT_CHECKLIST, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        self.assertTrue(checklist.review_id.is_unique)
        self.assertTrue((checklist.human_decision == "PENDING").all())
        self.assertTrue((checklist.human_verified == "NO").all())
        for column in ("reviewer", "review_date", "human_evidence"):
            self.assertTrue((checklist[column] == "").all(), column)
        serious = self.unresolved[self.unresolved.severity.isin(["HIGH", "MEDIUM"])]
        markers = set(checklist.source_order) - {""}
        self.assertTrue(set(serious[serious.source_order != ""].source_order) <= markers)
        gaps = set(checklist[checklist.review_kind == "NUMBERING_GAP"].normalized_candidate_id)
        self.assertTrue(set(serious[serious.source_order == ""].normalized_candidate_id) <= gaps)
        self.assertTrue((checklist.what_to_verify != "").all() and (checklist.decision_options != "").all())
        pages = checklist.pdf_page_file_index.astype(int)
        self.assertTrue(pages.between(1, 148).all())
        order = list(zip(pages, checklist.source_order.map(lambda v: int(v) if v else 10 ** 6)))
        self.assertEqual(order, sorted(order))  # page-ordered so a reviewer can walk the PDF

    def test_merge_fields_follow_the_documented_policy(self):
        parents = self.df[self.df.merged_source_ids != ""]
        self.assertGreater(len(parents), 0)
        ids = set(self.df.normalized_candidate_id)
        for r in parents.itertuples():
            members = r.merged_source_ids.split(";")
            self.assertEqual(members[0], r.normalized_candidate_id)
            self.assertTrue(set(members) <= ids)
            self.assertEqual(len(members) - 1, int(r.child_marker_count))
            self.assertEqual(r.merge_status, "PROPOSED_PENDING_HUMAN_CONFIRMATION")
            self.assertIn(r.composite_rule, ("R1_CLAUSE_CHAIN_EXACT_SOURCE_SLICE", "R2_LIST_LEAD_PLUS_ITEMS_DERIVED_CONCATENATION"))
            self.assertNotEqual(r.parent_composite_text, "")
            # the original (non-derived) candidate text of the parent is untouched
            self.assertIn(r.candidate_text, r.parent_composite_text)
        children = self.df[self.df.parent_requirement_id != ""]
        self.assertTrue((children.eligible_as_standalone_candidate == "False").all())
        self.assertTrue(children.merge_status.isin(["FRAGMENT_OF_PARENT_SENTENCE_NOT_STANDALONE",
                                                    "LIST_ITEM_INDEPENDENCE_UNDECIDED"]).all())

    def test_r1_composite_is_an_exact_source_slice(self):
        furniture = re.compile(r"^(TCS 102Block 0 TCS102|Version 2\.0 2/12/99|\d{1,3})$")
        for r in self.df[self.df.composite_rule == "R1_CLAUSE_CHAIN_EXACT_SOURCE_SLICE"].itertuples():
            last = self.df[self.df.normalized_candidate_id == r.merged_source_ids.split(";")[-1]].iloc[0]
            window = self.text[int(r.source_start_char):int(last.marker_end_char)]
            stripped = audit.collapse(" ".join(l for l in window.split("\r\n") if not furniture.match(l.strip())))
            self.assertEqual(r.parent_composite_text, stripped, r.original_marker)

    def test_classification_is_deterministic(self):
        markers_a, markers_b = audit.find_markers(self.text), audit.find_markers(self.text)
        rows_a, _ = audit.build_rows(self.text, markers_a)
        rows_b, _ = audit.build_rows(self.text, markers_b)
        self.assertEqual(rows_a, rows_b)

    def test_source_files_match_the_hashes_recorded_in_the_validation_report(self):
        report = audit.OUT_VALIDATION.read_text(encoding="utf-8")
        for path in (audit.SRC_PDF, audit.SRC_TXT):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertIn(digest, report, f"{path.name} changed since the audit was generated")


if __name__ == "__main__":
    unittest.main()
