"""Guards for synthetic_seed_inputs_batch2.csv: it must never contain a frozen-test id, a generation-eval id or a batch-1 id."""
import re
import unittest
from pathlib import Path

import pandas as pd

TASKS = Path(__file__).resolve().parents[1] / "data" / "component1" / "processed" / "tasks"


def read(name):
    return pd.read_csv(TASKS / name, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def key(text):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s+", " ", str(text).lower()))


class SyntheticSeedBatch2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b2 = read("synthetic_seed_inputs_batch2.csv")
        cls.gen = read("generation_inputs.csv")

    def test_no_id_in_frozen_test_ids(self):
        frozen = set(read("frozen_test_ids.csv").record_id)
        self.assertEqual(sorted(set(self.b2.id) & frozen), [])

    def test_no_id_in_generation_eval_ids(self):
        self.assertEqual(sorted(set(self.b2.id) & set(read("generation_eval_ids.csv").id)), [])

    def test_no_id_in_batch_1(self):
        self.assertEqual(sorted(set(self.b2.id) & set(read("synthetic_seed_inputs.csv").id)), [])

    def test_columns_ids_and_size(self):
        self.assertEqual(list(self.b2.columns), ["id", "source", "requirement_text", "requirement_type"])
        self.assertEqual(self.b2.id.nunique(), len(self.b2))
        self.assertTrue(380 <= len(self.b2) <= 420)

    def test_rows_are_train_requirement_texts_matching_the_task_file(self):
        rows = self.gen[self.gen.record_type == "requirement_text"].set_index("record_id").loc[list(self.b2.id)]
        self.assertEqual(set(rows.split), {"train"})
        self.assertEqual(list(rows.source_dataset), list(self.b2.source))
        self.assertEqual(list(rows.requirement_type), list(self.b2.requirement_type))
        self.assertEqual([t.strip() for t in rows.requirement_text_original], list(self.b2.requirement_text))

    def test_no_text_shared_with_val_test_or_batch_1(self):
        held = set()
        for name in ("classification_fr_nfr", "classification_nfr_subtype", "ambiguity", "generation_inputs"):
            d = read(f"{name}.csv")
            held |= {key(t) for t in d[d.split.isin(["val", "test"])].requirement_text_original}
        dp = read("dependency_pairs.csv")
        for col in ("fr_text", "nfr_text"):
            held |= {key(t) for t in dp[dp.split.isin(["val", "test"])][col]}
        held |= {key(t) for t in read("synthetic_seed_inputs.csv").requirement_text}
        texts = [key(t) for t in self.b2.requirement_text]
        self.assertEqual(len(texts), len(set(texts)))
        self.assertFalse(set(texts) & held)

    def test_word_count_and_sentence_ending(self):
        words = self.b2.requirement_text.str.split().str.len()
        self.assertTrue(((words >= 6) & (words <= 60)).all())
        self.assertTrue(self.b2.requirement_text.str.contains(r"[.!?][\"'\u201d\u2019)\]]*\s*$").all())

    def test_label_and_source_mix(self):
        known = self.b2[self.b2.requirement_type != ""]
        fr, nfr = (known.requirement_type == "FR").sum(), (known.requirement_type == "NFR").sum()
        self.assertLess(abs(fr - nfr), 0.1 * len(known))
        share = self.b2.source.value_counts(normalize=True)
        self.assertTrue(0.35 <= share["FR_NFR"] <= 0.45 and 0.30 <= share["PROMISE"] <= 0.40 and 0.05 <= share["PURE"] <= 0.15)

    def test_report_states_zero_overlap_and_similarity_below_limit(self):
        text = (TASKS / "synthetic_seed_inputs_batch2_report.md").read_text(encoding="utf-8")
        for label in ("ids overlapping frozen_test_ids.csv", "ids overlapping generation_eval_ids.csv", "ids overlapping batch 1"):
            self.assertRegex(text, re.escape(label) + r"[^\n]*\*\*0\*\*")
        m = re.search(r"frozen-test texts: \*\*(\d\.\d+)\*\*", text)
        self.assertIsNotNone(m)
        self.assertLess(float(m.group(1)), 0.90)


if __name__ == "__main__":
    unittest.main()
