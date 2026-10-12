"""Guards for the grown Component 1 SFT dataset: the validator rules (toy rows, one mutation per rule), the merge/split, and no test-data leakage."""
import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "experiments" / "component1"))
import build_sft_dataset as bsd  # noqa: E402
import validate_sft_pairs as vsp  # noqa: E402

SFT = PROJECT / "data" / "component1" / "processed" / "llm_sft"
TASKS = PROJECT / "data" / "component1" / "processed" / "tasks"


def read(name):
    return pd.read_csv(TASKS / name, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def key(text):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s+", " ", str(text).lower()))


def ok_row(**kw):
    row = {"id": "FR_NFR:0000000001", "source": "FR_NFR", "requirement_text": "The system shall lock an account after 5 failed logins.",
           "synthetic": True, "generator": "test", "review_status": "unreviewed", "status": "ok",
           "user_story": "As a security officer, I want accounts locked after repeated failed sign-ins, so that guessing attacks are slowed.",
           "technical_task": "Count consecutive failed sign-ins and lock the account once the count reaches 5.",
           "acceptance_criteria": ["Given 5 failed logins, when the fifth attempt fails, then the account is locked.",
                                   "Given fewer than 5 failed logins, when the user signs in correctly, then access is granted."],
           "rationale": "Role assumed: security officer.", "reviewer_note": ""}
    row.update(kw)
    return row


def nc_row(**kw):
    row = {"id": "FR_NFR:0000000002", "source": "FR_NFR", "requirement_text": "The system shall be user friendly.",
           "synthetic": True, "generator": "test", "review_status": "unreviewed", "status": "needs_clarification",
           "user_story": None, "technical_task": None, "acceptance_criteria": [],
           "clarification_questions": ["How is user friendly measured?"], "rationale": "Not measurable.", "reviewer_note": ""}
    row.update(kw)
    return row


class ValidatorRules(unittest.TestCase):
    def test_good_rows_pass(self):
        self.assertEqual(vsp.check_row(ok_row()), [])
        self.assertEqual(vsp.check_row(nc_row()), [])

    def assert_reason(self, row, prefix):
        reasons = vsp.check_row(row)
        self.assertTrue(any(r.startswith(prefix) for r in reasons), f"{prefix} not in {reasons}")

    def test_story_pattern(self):
        self.assert_reason(ok_row(user_story="Accounts get locked."), "story_pattern")
        self.assert_reason(ok_row(user_story="As a user, I want locking, so that it is safe"), "story_pattern")  # no final period

    def test_criteria_count_and_pattern(self):
        self.assert_reason(ok_row(acceptance_criteria=["Given 5 failed logins, when it fails, then the account is locked."]), "criteria_count")
        seven = [f"Given case {i}, when it runs, then result {i} holds." for i in range(7)]
        self.assert_reason(ok_row(acceptance_criteria=seven), "criteria_count")
        bad = ["Given 5 failed logins, when it fails, then the account is locked.", "The account is locked."]
        self.assert_reason(ok_row(acceptance_criteria=bad), "criterion_pattern_2")

    def test_numbers_must_come_from_the_requirement(self):
        self.assert_reason(ok_row(technical_task="Lock the account after 7 failed sign-ins and log the event."), "numbers_not_in_requirement")

    def test_copied_story_and_task(self):
        req = "The system shall lock an account after 5 failed logins."
        self.assert_reason(ok_row(technical_task=req), "copied_technical_task")
        self.assert_reason(ok_row(user_story=f"As a user, I want {req[:-1]}, so that it is safe."), "copied_story")

    def test_schema(self):
        self.assert_reason(ok_row(synthetic=False), "schema_synthetic_not_true")
        row = ok_row()
        del row["rationale"]
        self.assert_reason(row, "schema_keys")
        self.assert_reason(dict(ok_row(), surprise=1), "schema_keys")
        self.assert_reason(ok_row(status="maybe"), "schema_status")

    def test_seed_mismatch(self):
        reasons = vsp.check_row(ok_row(), {"source": "FR_NFR", "requirement_text": "something else"})
        self.assertIn("seed_mismatch", reasons)

    def test_needs_clarification_shape(self):
        self.assert_reason(nc_row(user_story="As a user, I want x, so that y."), "nc_story_or_task_not_null")
        self.assert_reason(nc_row(acceptance_criteria=["Given a, when b, then c."]), "nc_criteria_not_empty")
        self.assert_reason(nc_row(clarification_questions=[]), "nc_clarification_questions")

    def test_validate_all_rejects_near_duplicate_outputs_and_keeps_first(self):
        seeds = pd.DataFrame([{"id": f"FR_NFR:000000000{i}", "source": "FR_NFR", "requirement_text": "The system shall lock an account after 5 failed logins."} for i in (1, 2)])
        first, second = ok_row(id="FR_NFR:0000000001"), ok_row(id="FR_NFR:0000000002")
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "batch_001.jsonl"
            p.write_text("".join(json.dumps(r) + "\n" for r in (first, second)), encoding="utf-8")
            passed, rejected = vsp.validate_all(seeds, [], [p])
        self.assertEqual([r["id"] for r in passed], ["FR_NFR:0000000001"])
        self.assertEqual(passed[0]["review_status"], "auto_validated")
        self.assertTrue(rejected[0]["reasons"][0].startswith("near_duplicate_output"))

    def test_a_retry_replaces_a_rejected_first_attempt_but_never_a_pass(self):
        seeds = pd.DataFrame([{"id": "FR_NFR:0000000001", "source": "FR_NFR", "requirement_text": "The system shall lock an account after 5 failed logins."}])
        bad = ok_row(technical_task="The system shall lock an account after 5 failed logins.")
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            a, b, c = Path(d) / "batch_001.jsonl", Path(d) / "retry_001.jsonl", Path(d) / "retry_002.jsonl"
            a.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            b.write_text(json.dumps(ok_row()) + "\n", encoding="utf-8")
            c.write_text(json.dumps(ok_row()) + "\n", encoding="utf-8")
            passed, rejected = vsp.validate_all(seeds, [], [a, b])
            self.assertEqual(len(passed), 1)
            self.assertEqual([r["attempt"] for r in rejected], [1])
            passed, rejected = vsp.validate_all(seeds, [], [b, c])
            self.assertEqual(len(passed), 1)
            self.assertEqual(rejected[0]["reasons"], ["duplicate_id_in_batches"])


class MergeAndSplit(unittest.TestCase):
    def test_merge_drops_repeated_requirement_text_and_keeps_originals(self):
        orig = [{"id": "a", "requirement_text": "The  system SHALL log in."}]
        new = [{"id": "b", "requirement_text": "The system shall log in!"}, {"id": "c", "requirement_text": "Another one."}]
        merged, dropped = bsd.merge(orig, new)
        self.assertEqual([r["id"] for r in merged], ["a", "c"])
        self.assertEqual(dropped, ["b"])

    def test_split_is_deterministic_and_stratified(self):
        rows = [{"id": f"{s}:{i}", "source": s, "status": st} for s in ("A", "B") for st in ("ok", "needs_clarification") for i in range(40 if st == "ok" else 10)]
        t1, v1 = bsd.split(rows)
        t2, v2 = bsd.split(list(rows))
        self.assertEqual(([r["id"] for r in t1], [r["id"] for r in v1]), ([r["id"] for r in t2], [r["id"] for r in v2]))
        self.assertEqual(Counter((r["source"], r["status"]) for r in v1), {("A", "ok"): 4, ("B", "ok"): 4, ("A", "needs_clarification"): 1, ("B", "needs_clarification"): 1})
        self.assertEqual(len(t1) + len(v1), len(rows))


class BuiltFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.merged = bsd.load_jsonl(SFT / "synthetic_pairs_all.jsonl")
        cls.train = bsd.load_jsonl(SFT / "sft_train.jsonl")
        cls.val = bsd.load_jsonl(SFT / "sft_val.jsonl")
        cls.originals = bsd.load_jsonl(SFT / "synthetic_pairs_all_550.jsonl")

    def test_sizes(self):
        self.assertGreaterEqual(len(self.merged), 2500)
        self.assertGreaterEqual(len(self.train), 2250)
        self.assertEqual(len(self.train) + len(self.val), len(self.merged))
        self.assertAlmostEqual(len(self.val) / len(self.merged), 0.10, delta=0.01)

    def test_ids_and_texts_are_unique_and_split_is_disjoint(self):
        self.assertEqual(len({r["id"] for r in self.merged}), len(self.merged))
        self.assertEqual(len({key(r["requirement_text"]) for r in self.merged}), len(self.merged))
        self.assertEqual({r["id"] for r in self.train} & {r["id"] for r in self.val}, set())

    def test_originals_keep_their_review_status(self):
        by_id = {r["id"]: r for r in self.merged}
        for r in self.originals:
            self.assertEqual(by_id[r["id"]]["review_status"], r["review_status"])
        self.assertTrue(all(r["review_status"] == "auto_validated" for r in self.merged if r["id"] not in {o["id"] for o in self.originals}))

    def test_chat_format_and_system_prompt_are_identical_to_the_550_files(self):
        system = bsd.load_jsonl(SFT / "sft_train_550.jsonl")[0]["messages"][0]["content"]
        by_id = {r["id"]: r for r in self.merged}
        for row in self.train + self.val:
            self.assertEqual([m["role"] for m in row["messages"]], ["system", "user", "assistant"])
            self.assertEqual(row["messages"][0]["content"], system)
            src = by_id[row["id"]]
            self.assertEqual(row["messages"][1]["content"], f"Requirement: {src['requirement_text']}")
            self.assertEqual(json.loads(row["messages"][2]["content"])["status"], src["status"])

    def test_old_550_files_are_still_there_and_unchanged_in_size(self):
        self.assertEqual(len(bsd.load_jsonl(SFT / "sft_train_550.jsonl")), 495)
        self.assertEqual(len(bsd.load_jsonl(SFT / "sft_val_550.jsonl")), 55)

    def test_every_new_row_passes_the_validator_rules(self):
        for r in self.merged:
            if r["review_status"] == "auto_validated":
                self.assertEqual(vsp.check_row({k: v for k, v in r.items()}), [], r["id"])

    def test_needs_clarification_share_is_in_range(self):
        new = [r for r in self.merged if r["review_status"] == "auto_validated"]
        share = sum(r["status"] == "needs_clarification" for r in new) / len(new)
        self.assertTrue(0.12 <= share <= 0.20, share)


class NoTestDataLeakage(unittest.TestCase):
    def test_no_train_or_val_row_is_test_or_eval_data(self):
        frozen = set(read("frozen_test_ids.csv").record_id)
        eval_ids = set(read("generation_eval_ids.csv").id)
        eval_texts = {key(t) for t in read("generation_eval_inputs.csv").requirement_text}
        for name in ("sft_train.jsonl", "sft_val.jsonl", "synthetic_pairs_all.jsonl"):
            rows = bsd.load_jsonl(SFT / name)
            ids = {r["id"] for r in rows}
            self.assertEqual(ids & frozen, set(), name)
            self.assertEqual(ids & eval_ids, set(), name)
            texts = {key(r["requirement_text"]) if "requirement_text" in r else key(r["messages"][1]["content"].removeprefix("Requirement: ")) for r in rows}
            self.assertEqual(texts & eval_texts, set(), name)


if __name__ == "__main__":
    unittest.main()
