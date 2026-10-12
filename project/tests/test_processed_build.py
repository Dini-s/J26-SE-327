"""Tests for the Component 1 processed-data build (master table, task datasets, SRS extraction).

Run from the project directory:
    ..\\.venv\\Scripts\\python.exe -m pytest tests/test_processed_build.py -v
(the tests are plain unittest classes, so `python -m unittest tests.test_processed_build` also works)

Row-count reconciliation re-reads every raw input with separate code instead of trusting the build report.
Run build_master.py, build_srs_requirements.py and build_task_datasets.py first.
"""
import csv
import hashlib
import io
import json
import re
import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "component1"))
COMPONENT = PROJECT_ROOT / "data" / "component1"
RAW, PROCESSED, AUDIT = COMPONENT / "raw", COMPONENT / "processed", COMPONENT / "audit_reports_component1"
TASKS = PROCESSED / "tasks"
MIN_WORDS = 6
MAIN_TASKS = ["classification_fr_nfr", "classification_nfr_subtype", "ambiguity", "generation_inputs"]
ALL_TASKS = MAIN_TASKS + ["dependency_pairs"]

_CACHE = {}


def read(path):
    key = str(path)
    if key not in _CACHE:
        _CACHE[key] = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    return _CACHE[key].copy()


def task(name):
    return read(TASKS / f"{name}.csv")


def normalize_key(text):
    """Independent re-implementation of the text key (lower case, alphanumerics only)."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


@unittest.skipUnless((PROCESSED / "master_requirements.csv").exists() and (TASKS / "manifest.json").exists(),
                     "run the three build scripts first")
class MasterTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master = read(PROCESSED / "master_requirements.csv")

    def test_no_empty_text(self):
        self.assertTrue((self.master.requirement_text_original.str.strip() != "").all())
        self.assertTrue((self.master.requirement_text_normalized != "").all())
        self.assertTrue((self.master.text_key != "").all())

    def test_record_ids_unique_and_required_columns_present(self):
        self.assertTrue(self.master.record_id.is_unique)
        for column in ("record_id", "source_dataset", "source_file", "source_record_id", "source_project_or_document",
                       "requirement_text_original", "requirement_text_normalized", "requirement_type", "nfr_subtype",
                       "ambiguity_label", "security_label", "review_status", "is_synthetic", "license_note", "provenance"):
            self.assertIn(column, self.master.columns)

    def test_nothing_synthetic(self):
        self.assertEqual(set(self.master.is_synthetic), {"False"})

    def test_no_duplicate_normalized_text_within_a_source(self):
        dup = self.master.duplicated(["source_dataset", "requirement_text_normalized"])
        self.assertEqual(int(dup.sum()), 0)

    def test_unknown_labels_stay_empty_not_zero(self):
        fr_nfr = self.master[self.master.source_dataset == "FR_NFR"]
        raw = pd.read_excel(RAW / "FR_NFR_Dataset.xlsx", sheet_name="datasetFR_NFR_full", dtype=str)
        self.assertGreaterEqual(int(raw["Type"].isna().sum()), 31)
        missing = fr_nfr[fr_nfr.review_status == "label_missing"]
        self.assertGreaterEqual(len(missing), 25)
        self.assertEqual(set(missing.requirement_type), {""})
        self.assertTrue(set(self.master.requirement_type) <= {"FR", "NFR", ""})
        self.assertTrue(set(self.master.security_label) <= {"0", "1", ""})
        stray = self.master[self.master.source_dataset == "security_requirements"]
        self.assertTrue((stray[stray.source_label_raw == "xyz"].security_label == "").all())

    def test_original_text_is_untouched(self):
        promise = pd.read_csv(RAW / "promise.csv", encoding="utf-8-sig", dtype=str)
        raw_texts = set(promise.requirement)
        mine = self.master[self.master.source_dataset == "PROMISE"].requirement_text_original
        self.assertTrue(set(mine) <= raw_texts)
        fr = pd.read_excel(RAW / "FR_NFR_Dataset.xlsx", sheet_name="datasetFR_NFR_full", dtype=str)["Requirement Text"].dropna()
        self.assertTrue(set(self.master[self.master.source_dataset == "FR_NFR"].requirement_text_original) <= set(fr))
        qure = pd.read_csv(RAW / "QuRE.csv", encoding="utf-8-sig", dtype=str).requirement
        self.assertTrue(set(self.master[self.master.source_dataset == "QuRE"].requirement_text_original) <= set(qure))

    def test_tcs_rows_are_held(self):
        tcs = self.master[self.master.source_project_or_document.str.contains("tcs", case=False)
                          & self.master.source_dataset.str.startswith("DS")]
        self.assertGreater(len(tcs), 0)
        self.assertEqual(set(tcs.boundary_status), {"auto_unverified"})
        self.assertTrue(tcs.exclusion_reason.str.contains("tcs_hold").all())

    def test_conflicts_are_not_resolved_and_are_flagged(self):
        conflicts = read(PROCESSED / "master_label_conflicts.csv")
        self.assertGreater(len(conflicts), 0)
        self.assertTrue((conflicts.excluded_from == "all_tasks").all())
        cross = conflicts[conflicts.scope == "cross_source"]
        ids = set(";".join(cross.master_record_ids).split(";")) - {""}
        flagged = self.master[self.master.record_id.isin(ids)]
        self.assertTrue(flagged.exclusion_reason.str.contains("label_conflict").all())
        within = conflicts[conflicts.scope == "within_source"]
        # the strictly identical conflicting duplicates were moved out of the master; a punctuation variant of the same text
        # may remain, and then it must be flagged and excluded from tasks rather than silently kept
        for key, src in zip(within.text_key, within.source_datasets):
            left = self.master[(self.master.text_key == key) & (self.master.source_dataset == src)]
            self.assertTrue(left.exclusion_reason.str.contains("label_conflict").all(), key)
            normalized_in_conflict = set(within[within.text_key == key].example_text)
            self.assertFalse(set(left.requirement_text_normalized) & normalized_in_conflict, key)

    def test_pure_encoding_decoded_without_mojibake_introduced(self):
        pure = self.master[self.master.source_dataset == "PURE"]
        self.assertGreater(int((pure.encoding_fix_applied != "").sum()), 1000)
        self.assertLess(int(pure.requirement_text_original.str.contains("Â§").sum()), 5)


@unittest.skipUnless((TASKS / "manifest.json").exists(), "run the three build scripts first")
class TaskFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master = read(PROCESSED / "master_requirements.csv")
        cls.tasks = {n: task(n) for n in ALL_TASKS}

    def test_held_out_project_groups_have_no_train_or_val_rows(self):
        """A PROMISE project that sits in the test split must not also have rows in train or val (the P15 case)."""
        for name in ("classification_fr_nfr", "classification_nfr_subtype", "generation_inputs"):
            t = self.tasks[name]
            projects = t[t.group_id.str.match(r"^PROMISE_P\d+$")]
            spans = projects.groupby("group_id").split.agg(lambda s: set(s))
            bad = {g: v for g, v in spans.items() if "test" in v and len(v) > 1}
            self.assertEqual(bad, {}, f"{name}: held-out projects span splits")

    def test_no_empty_text_in_tasks(self):
        for name in MAIN_TASKS:
            t = self.tasks[name]
            self.assertTrue((t.requirement_text_original.str.strip() != "").all(), name)
            self.assertTrue((t.requirement_text_normalized != "").all(), name)
        d = self.tasks["dependency_pairs"]
        self.assertTrue((d.fr_text.str.strip() != "").all() and (d.nfr_text.str.strip() != "").all())

    def test_every_split_value_is_valid(self):
        for name, t in self.tasks.items():
            self.assertTrue(set(t.split) <= {"train", "val", "test"}, name)
            self.assertEqual(len(set(t.split)), 3, f"{name} should have all three splits")

    def test_no_duplicate_normalized_text_within_a_split(self):
        for name in MAIN_TASKS:
            t = self.tasks[name]
            keys = t.requirement_text_normalized.map(normalize_key)
            self.assertFalse(pd.DataFrame({"s": t.split, "k": keys}).duplicated().any(), name)
            self.assertTrue(t.record_id.is_unique, name)
        d = self.tasks["dependency_pairs"]
        self.assertTrue(d.record_id.is_unique)

    def test_zero_text_overlap_between_splits_per_task(self):
        for name in MAIN_TASKS:
            t = self.tasks[name]
            keys = {s: set(t[t.split == s].requirement_text_normalized.map(normalize_key)) for s in ("train", "val", "test")}
            self.assertEqual(keys["train"] & keys["test"], set(), name)
            self.assertEqual(keys["train"] & keys["val"], set(), name)
            self.assertEqual(keys["val"] & keys["test"], set(), name)
        d = self.tasks["dependency_pairs"]
        sets = {s: set(d[d.split == s].fr_text.map(normalize_key)) | set(d[d.split == s].nfr_text.map(normalize_key)) for s in ("train", "val", "test")}
        self.assertEqual(sets["train"] & sets["test"], set())
        self.assertEqual(sets["train"] & sets["val"], set())
        self.assertEqual(sets["val"] & sets["test"], set())

    def test_zero_text_overlap_across_all_tasks_too(self):
        # the split is global: a text is in the same split in every task file
        split_of = {}
        for name in MAIN_TASKS:
            for text, split in zip(self.tasks[name].requirement_text_normalized.map(normalize_key), self.tasks[name].split):
                self.assertEqual(split_of.setdefault(text, split), split)

    def test_every_task_row_exists_in_master(self):
        ids = set(self.master.record_id)
        for name in MAIN_TASKS + ["dependency_spot_check"][:0]:
            self.assertTrue(set(self.tasks[name].record_id) <= ids, name)
        self.assertTrue(set(read(TASKS / "pipeline_test_cornelius.csv").record_id) <= ids)
        d = self.tasks["dependency_pairs"]
        linked = d[(d.fr_master_record_id != "") & (d.nfr_master_record_id != "")]
        self.assertEqual(len(linked), len(d), "every dependency pair text must exist in the master")
        self.assertTrue(set(d.fr_master_record_id) <= ids and set(d.nfr_master_record_id) <= ids)

    def test_task_rows_match_master_text_and_labels(self):
        by_id = self.master.set_index("record_id")
        for name in MAIN_TASKS:
            t = self.tasks[name]
            self.assertTrue((t.requirement_text_original.values == by_id.loc[t.record_id, "requirement_text_original"].values).all(), name)
        fr = self.tasks["classification_fr_nfr"]
        self.assertTrue((fr.requirement_type.values == by_id.loc[fr.record_id, "requirement_type"].values).all())
        self.assertTrue(set(fr.requirement_type) <= {"FR", "NFR"})
        amb = self.tasks["ambiguity"]
        self.assertTrue((amb.ambiguity_label.values == by_id.loc[amb.record_id, "ambiguity_label"].values).all())
        self.assertTrue(set(amb.ambiguity_label) <= {"defect", "ok"})

    def test_short_texts_never_enter_task_files(self):
        for name in MAIN_TASKS:
            self.assertTrue((self.tasks[name].requirement_text_normalized.str.split().str.len() >= MIN_WORDS).all(), name)

    def test_excluded_rows_never_enter_task_files(self):
        excluded = self.master[self.master.exclusion_reason != ""]
        keys_excluded = set(excluded.record_id)
        for name in MAIN_TASKS:
            self.assertEqual(set(self.tasks[name].record_id) & keys_excluded, set(), name)
        tcs = self.master[self.master.exclusion_reason.str.contains("tcs_hold")]
        self.assertEqual(set(tcs.record_id) & set().union(*[set(self.tasks[n].record_id) for n in MAIN_TASKS]), set())
        cornelius = set(self.master[self.master.source_dataset == "Cornelius"].record_id)
        self.assertEqual(cornelius & set().union(*[set(self.tasks[n].record_id) for n in MAIN_TASKS]), set())

    def test_conflicting_texts_are_out_of_every_task(self):
        conflicts = read(PROCESSED / "master_label_conflicts.csv")
        bad = set(conflicts.text_key)
        for name in MAIN_TASKS:
            keys = set(self.tasks[name].text_key)
            self.assertEqual(keys & bad, set(), name)

    def test_ambiguity_sources_stay_identifiable(self):
        amb = self.tasks["ambiguity"]
        self.assertTrue((amb.ambiguity_label_basis != "").all())
        bases = set(amb.ambiguity_label_basis)
        self.assertIn("QuRE_defect", bases)
        self.assertTrue(any(b.startswith("ARTA_DS") for b in bases))
        self.assertFalse(any("Cornelius" in b for b in bases))
        self.assertFalse(amb.source_dataset.isin(["Cornelius"]).any())

    def test_subtype_reliability_is_marked_too_sparse(self):
        sub = self.tasks["classification_nfr_subtype"]
        rel = sub[sub.reliability_label != ""]
        self.assertGreater(len(rel), 0)
        self.assertEqual(set(rel.reliability_eval_status), {"too_sparse_to_evaluate"})
        self.assertEqual(set(sub.metrics_include_reliability), {"False"})

    def test_promise_keeps_group_ids_and_real_validation_test_rows(self):
        fr = self.tasks["classification_fr_nfr"]
        promise = fr[fr.source_dataset == "PROMISE"]
        self.assertGreaterEqual(promise.group_id.nunique(), 10)
        self.assertTrue(promise.group_id.str.startswith("PROMISE_").all())
        self.assertGreater(int((promise.split == "val").sum()), 20)
        self.assertGreater(int((promise.split == "test").sum()), 20)

    def test_dependency_pairs_are_flagged_unconfirmed_and_split_by_project(self):
        d = self.tasks["dependency_pairs"]
        self.assertEqual(set(d.semantics), {"unconfirmed"})
        self.assertEqual(set(d.text_join_status), {"inferred_unverified"})
        per_project = d.groupby("project").split.nunique()
        self.assertTrue((per_project == 1).all(), "a project must not span splits")
        counts = d.groupby("split").project.nunique().to_dict()
        self.assertEqual(counts, {"train": 7, "val": 1, "test": 2})
        raw = read(PROCESSED / "promise_trace_relationships.csv")
        pairs = set(zip(raw.project, raw.fr_id, raw.nfr_id, raw.relationship))
        self.assertTrue(set(zip(d.project, d.fr_id, d.nfr_id, d.relationship)) <= pairs)

    def test_dependency_spot_check_has_twenty_joined_pairs(self):
        spot = read(TASKS / "dependency_spot_check.csv")
        self.assertEqual(len(spot), 20)
        self.assertTrue(set(spot.record_id) <= set(self.tasks["dependency_pairs"].record_id))
        self.assertTrue((spot.manual_check_text_matches_id == "").all(), "the manual-check column must stay blank")

    def test_cornelius_pipeline_file_is_small_and_flagged(self):
        c = read(TASKS / "pipeline_test_cornelius.csv")
        self.assertTrue(180 <= len(c) <= 220)
        self.assertEqual(set(c.pipeline_test_only), {"True"})
        self.assertEqual(set(c.source_dataset), {"Cornelius"})

    def test_no_duplicate_candidates_file_without_real_pairs(self):
        self.assertFalse((TASKS / "duplicate_candidates.csv").exists())
        manifest = json.loads((TASKS / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("no real labeled duplicate pairs", manifest["duplicate_candidates"])


@unittest.skipUnless((TASKS / "manifest.json").exists(), "run the three build scripts first")
class FrozenTestIds(unittest.TestCase):
    def test_manifest_hash_matches_frozen_file(self):
        manifest = json.loads((TASKS / "manifest.json").read_text(encoding="utf-8"))
        actual = hashlib.sha256((TASKS / "frozen_test_ids.csv").read_bytes()).hexdigest()
        self.assertEqual(actual, manifest["frozen_test_ids_sha256"])
        for name, digest in manifest["file_sha256"].items():
            self.assertEqual(hashlib.sha256((TASKS / name).read_bytes()).hexdigest(), digest, name)

    def test_frozen_ids_are_exactly_the_test_rows_of_each_task(self):
        frozen = read(TASKS / "frozen_test_ids.csv")
        for name in ALL_TASKS:
            t = task(name)
            self.assertEqual(set(frozen[frozen.task == name].record_id), set(t[t.split == "test"].record_id), name)

    def test_frozen_ids_unchanged_when_the_whole_build_is_recomputed(self):
        import build_task_datasets as bt
        *_, tasks, _, _, _ = bt.compute()
        recomputed = bt.bm.to_bytes(bt.frozen_test(tasks))
        self.assertEqual(hashlib.sha256(recomputed).hexdigest(), hashlib.sha256((TASKS / "frozen_test_ids.csv").read_bytes()).hexdigest())
        for name in ALL_TASKS:
            self.assertEqual(bt.bm.to_bytes(tasks[name]), (TASKS / f"{name}.csv").read_bytes(), name)

    def test_test_rows_never_appear_in_train_of_another_task(self):
        frozen = read(TASKS / "frozen_test_ids.csv")
        test_texts = set()
        for name in MAIN_TASKS:
            t = task(name)
            test_texts |= set(t[t.split == "test"].requirement_text_normalized.map(normalize_key))
        for name in MAIN_TASKS:
            t = task(name)
            self.assertEqual(test_texts & set(t[t.split == "train"].requirement_text_normalized.map(normalize_key)), set(), name)
        self.assertGreater(len(frozen), 1000)


def count_pure_records(path):
    """Independent row count of pure_subset.csv (decoded as latin-1, which never fails)."""
    text = Path(path).read_bytes().decode("latin-1")
    return sum(1 for _ in csv.DictReader(io.StringIO(text)))


@unittest.skipUnless((AUDIT / "processed_build_report.csv").exists(), "run the three build scripts first")
class RowCountReconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = read(AUDIT / "processed_build_report.csv")
        cls.master = read(PROCESSED / "master_requirements.csv")

    def independent_counts(self):
        r = lambda f: len(pd.read_csv(RAW / f, encoding="utf-8-sig", dtype=str, keep_default_na=False))
        p = lambda f: len(pd.read_csv(PROCESSED / f, encoding="utf-8-sig", dtype=str, keep_default_na=False))
        counts = {
            "promise.csv": r("promise.csv"), "PROMISE-relabeled-NICE.csv": r("PROMISE-relabeled-NICE.csv"),
            "nfr_labeled_parsed.csv": p("nfr_labeled_parsed.csv"), "test_labeled_parsed.csv": p("test_labeled_parsed.csv"),
            "software_requirements_extended_normalized.csv": p("software_requirements_extended_normalized.csv"),
            "FR_NFR_Dataset.xlsx": len(pd.read_excel(RAW / "FR_NFR_Dataset.xlsx", sheet_name="datasetFR_NFR_full")),
            "pure_subset.csv": count_pure_records(RAW / "pure_subset.csv"), "security_requirements.csv": r("security_requirements.csv"),
            "QuRE.csv": r("QuRE.csv"), "user_stories.csv": r("user_stories.csv"),
            "cornelius_conflict_free_unique.csv": p("cornelius_conflict_free_unique.csv"),
            "basic.csv": r("basic.csv"), "context.csv": r("context.csv"), "context_role.csv": r("context_role.csv"),
        }
        for n in ("DS1", "DS2", "DS3", "DS4"):
            counts[f"{n}.xlsx"] = len(pd.read_excel(RAW / f"{n}.xlsx"))
        return counts

    def test_rows_in_equals_an_independent_recount_of_each_input(self):
        master_stage = self.report[self.report.stage == "master"].set_index("input_file")
        for name, expected in self.independent_counts().items():
            self.assertEqual(int(master_stage.loc[name, "rows_in"]), expected, name)

    def test_every_input_row_is_accounted_for(self):
        for r in self.report[self.report.stage == "master"].itertuples():
            total = (int(r.rows_dropped_empty) + int(r.rows_dropped_duplicates) + int(r.rows_moved_to_conflicts)
                     + int(r.rows_collapsed_into_canonical) + int(r.rows_out))
            self.assertEqual(total, int(r.rows_in), r.input_file)

    def test_rows_out_equals_master_rows_per_file(self):
        per_file = self.master.groupby("source_file").size().to_dict()
        for r in self.report[self.report.stage == "master"].itertuples():
            self.assertEqual(int(r.rows_out), per_file.get(r.input_file, 0), r.input_file)
        self.assertEqual(int(self.report[self.report.stage == "master"].rows_out.astype(int).sum()), len(self.master))

    def test_task_membership_counts_reconcile_with_task_files(self):
        in_tasks = set()
        for name in MAIN_TASKS:
            in_tasks |= set(task(name).record_id)
        by_file = self.master[self.master.record_id.isin(in_tasks)].groupby("source_file").size().to_dict()
        for r in self.report[self.report.stage == "master"].itertuples():
            self.assertEqual(int(r.rows_in_task_files), by_file.get(r.input_file, 0), r.input_file)

    def test_dependency_stage_reconciles(self):
        row = self.report[self.report.stage == "dependency_pairs"].iloc[0]
        raw = len(pd.read_csv(PROCESSED / "promise_trace_relationships.csv"))
        self.assertEqual(int(row.rows_in), raw)
        dropped = (int(row.rows_dropped_empty) + int(row.rows_dropped_other) + int(row.rows_short_text_dropped_from_tasks)
                   + int(row.rows_removed_for_text_overlap))
        self.assertEqual(int(row.rows_out), raw - dropped)
        self.assertEqual(int(row.rows_out), len(task("dependency_pairs")))


@unittest.skipUnless((PROCESSED / "srs_requirements_extracted.csv").exists(), "run build_srs_requirements.py first")
class SrsExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srs = read(PROCESSED / "srs_requirements_extracted.csv")
        cls.counts = read(AUDIT / "srs_requirements_per_document_counts.csv")

    def test_no_empty_text_and_all_unverified(self):
        self.assertTrue((self.srs.cleaned_text.str.strip() != "").all())
        self.assertTrue((self.srs.original_text.str.strip() != "").all())
        self.assertEqual(set(self.srs.boundary_status), {"auto_unverified"})
        self.assertEqual(set(self.srs.excluded_from_splits), {"True"})
        self.assertEqual(set(self.srs.is_synthetic), {"False"})

    def test_every_srs_text_file_is_covered_and_counted(self):
        files = sorted(p.stem for p in (PROCESSED / "srs_extracted_text").glob("*.txt"))
        self.assertEqual(len(files), 76)
        txt = self.counts[self.counts.source_format == "txt"].source_document
        self.assertEqual(sorted(txt), files)
        self.assertEqual(int(self.counts.rows_extracted.astype(int).sum()), len(self.srs))
        self.assertTrue((self.counts.rows_extracted.astype(int) > 0).all(), "a document with 0 rows must be investigated")

    def test_removed_content_types_do_not_leak_into_rows(self):
        text = self.srs.cleaned_text
        self.assertFalse(text.str.contains(r"\.{4,}").any(), "table-of-contents leaders")
        self.assertFalse(text.str.fullmatch(r"(?i)(page\s+)?\d{1,4}(\s+of\s+\d{1,4})?").any(), "page numbers")
        self.assertFalse(text.str.contains(r"\*\*DELETED\*\*|\(deleted\)", case=False).any(), "deleted entries")
        self.assertFalse(text.str.match(r"(?i)^(notes?\b|example\s*:)").any(), "notes and examples")

    def test_documents_without_shall_still_yield_rows(self):
        zero_shall = self.counts[self.counts.shall_in_text.astype(int) == 0]
        self.assertGreaterEqual(len(zero_shall), 20)
        self.assertTrue((zero_shall.rows_extracted.astype(int) > 0).all())

    def test_extraction_rules_and_types_are_the_documented_ones(self):
        self.assertTrue(set(self.srs.extraction_rule) <= {"modal_sentence", "numbered_clause_modal", "numbered_clause_no_modal"})
        self.assertTrue(set(self.srs.candidate_type) <= {"FR", "NFR", "unknown"})
        modal = self.srs[self.srs.extraction_rule.isin(["modal_sentence", "numbered_clause_modal"])]
        self.assertTrue(modal.cleaned_text.str.contains(r"\b(shall|must|should|will|is required to|are required to)\b", case=False).all())

    def test_tcs_rows_are_on_hold(self):
        tcs = self.srs[self.srs.source_document == "1999 - tcs"]
        self.assertGreater(len(tcs), 0)
        self.assertEqual(set(tcs.review_hold), {"tcs_manual_review_on_hold"})
        self.assertEqual(set(self.srs[self.srs.source_document != "1999 - tcs"].review_hold), {""})

    def test_srs_text_never_enters_a_task_split(self):
        srs_keys = set(self.srs.cleaned_text.map(normalize_key))
        ids = set(self.srs.srs_record_id)
        for name in MAIN_TASKS:
            self.assertFalse(ids & set(task(name).record_id))


if __name__ == "__main__":
    unittest.main()


class GenerationSeedAndEvalIds(unittest.TestCase):
    """synthetic_seed_inputs.csv (train, with text) and generation_eval_ids.csv (test, ids only) must stay separate from each other and from val/test."""

    @classmethod
    def setUpClass(cls):
        cls.seeds = read(TASKS / "synthetic_seed_inputs.csv")
        cls.eval_ids = read(TASKS / "generation_eval_ids.csv")
        gen = read(TASKS / "generation_inputs.csv")
        cls.gen = gen[gen.record_type == "requirement_text"]
        cls.by_id = cls.gen.set_index("record_id")

    @staticmethod
    def key(text):
        import re
        return re.sub(r"[^a-z0-9]", "", re.sub(r"\s+", " ", str(text).lower()))

    def test_eval_ids_file_has_no_text_column(self):
        self.assertEqual(list(self.eval_ids.columns), ["id"])
        self.assertTrue((self.eval_ids.id.str.len() < 40).all() and not self.eval_ids.id.str.contains(" ").any())

    def test_eval_ids_are_100_test_rows_stratified_and_6_to_60_words(self):
        ids = list(self.eval_ids.id)
        self.assertEqual((len(ids), len(set(ids))), (100, 100))
        rows = self.by_id.loc[ids]  # raises KeyError if an id is not a requirement_text row
        self.assertEqual(set(rows.split), {"test"})
        self.assertEqual(rows.requirement_type.value_counts().to_dict(), {"FR": 50, "NFR": 50})
        self.assertGreaterEqual(rows.source_dataset.nunique(), 3)
        words = rows.requirement_text_normalized.str.split().str.len()
        self.assertTrue(((words >= 6) & (words <= 60)).all())

    def test_seed_inputs_shape_split_and_labels(self):
        s = self.seeds
        self.assertEqual(list(s.columns), ["id", "source", "requirement_text", "requirement_type"])
        self.assertEqual((len(s), s.id.nunique()), (150, 150))
        src = self.by_id.loc[list(s.id)]
        self.assertEqual(set(src.split), {"train"})
        self.assertEqual(list(src.source_dataset), list(s.source))
        self.assertEqual(list(src.requirement_type), list(s.requirement_type))
        self.assertEqual(list(src.requirement_text_original), list(s.requirement_text))
        self.assertEqual(s.requirement_type.value_counts().to_dict(), {"FR": 75, "NFR": 75})
        self.assertGreaterEqual(s.source.nunique(), 3)
        self.assertTrue((s.requirement_text.str.split().str.len() >= 6).all())

    def test_seed_inputs_have_no_duplicate_or_near_identical_texts(self):
        keys = [self.key(t) for t in self.seeds.requirement_text]
        self.assertEqual(len(keys), len(set(keys)))
        words = [set(__import__("re").findall(r"[a-z0-9]+", t.lower())) for t in self.seeds.requirement_text]
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                self.assertLess(len(words[i] & words[j]) / len(words[i] | words[j]), 0.9)

    def test_no_seed_text_appears_in_eval_ids_rows_or_any_val_or_test_row(self):
        seed_keys = {self.key(t) for t in self.seeds.requirement_text}
        eval_keys = {self.key(t) for t in self.by_id.loc[list(self.eval_ids.id)].requirement_text_original}
        self.assertFalse(seed_keys & eval_keys)
        # the val sample used by generation_eval is a subset of the val split, so checking every val and test row (all task files) covers it
        held_out = set()
        for name in ALL_TASKS:
            t = task(name)
            if "split" in t and "requirement_text_normalized" in t:
                held_out |= {self.key(x) for x in t[t.split.isin(["val", "test"])].requirement_text_normalized}
        held_out |= {self.key(x) for x in self.gen[self.gen.split.isin(["val", "test"])].requirement_text_original}
        self.assertFalse(seed_keys & held_out)

    def test_generation_eval_sample_if_present_is_disjoint_from_seeds(self):
        try:
            from evaluation import generation_eval as ge
        except ImportError:
            self.skipTest("evaluation.generation_eval does not exist yet")
        sample = ge.sample_val_rows()
        seed_keys = {self.key(t) for t in self.seeds.requirement_text}
        self.assertFalse(seed_keys & {self.key(t) for t in sample.requirement_text_original})

    def test_data_card_records_both_files(self):
        card = (PROCESSED / "DATA_CARD.md").read_text(encoding="utf-8")
        self.assertIn("synthetic_seed_inputs.csv", card)
        self.assertIn("generation_eval_ids.csv", card)
        self.assertIn("ids only", card)
