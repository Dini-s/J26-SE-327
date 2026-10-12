"""Extraction precision from the manual spot check.

    python -m evaluation.extraction_precision [--file path/to/srs_extraction_spot_check.csv] [--out-dir results]

Reads `processed/tasks/srs_extraction_spot_check.csv`, whose `is_requirement` column (yes/no) is filled in by a human reviewer. Precision =
yes / (yes + no) over the reviewed rows, with a 95 % percentile bootstrap CI (rows resampled; seed 327). Rows left empty or with another value are
not counted. This script never fills the column. If no row has been reviewed it writes a "not available" note instead of numbers.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation import data_access as da
from evaluation.metrics import N_BOOT, SEED

DEFAULT_FILE = da.TASKS / "srs_extraction_spot_check.csv"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "evaluation" / "component1" / "results"


def precision_with_ci(flags, n_boot=N_BOOT, seed=SEED):
    """flags: array of 1 (requirement) / 0 (not). Returns (precision, low, high)."""
    flags = np.asarray(flags, dtype=float)
    rng = np.random.default_rng(seed)
    draws = [flags[rng.integers(0, len(flags), len(flags))].mean() for _ in range(n_boot)]
    return float(flags.mean()), float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def summarise(df):
    answer = df.is_requirement.str.strip().str.lower()
    reviewed = df[answer.isin(["yes", "no"])]
    lines = ["# SRS extraction precision (manual spot check)", ""]
    if reviewed.empty:
        lines.append(f"NOT AVAILABLE: 0 of {len(df)} spot-check rows have `is_requirement` filled in (yes/no). Fill the column in "
                     "`processed/tasks/srs_extraction_spot_check.csv` and rerun `python -m evaluation.extraction_precision`.")
        return "\n".join(lines) + "\n", None
    flags = (reviewed.is_requirement.str.strip().str.lower() == "yes").astype(int).values
    p, lo, hi = precision_with_ci(flags)
    lines += [f"Reviewed rows: {len(reviewed)} of {len(df)}; documents covered: {reviewed.source_document.nunique()}.", "",
              f"**Precision {p:.3f}, 95 % bootstrap CI [{lo:.3f}, {hi:.3f}]** ({int(flags.sum())} yes, {int((1 - flags).sum())} no).", "",
              "Precision only: recall of the extraction cannot be estimated from this sample. Rows are at most 3 per document, so documents with few rows are over-represented.", "",
              "| extraction rule | reviewed | yes | precision |", "|---|---|---|---|"]
    for rule, g in reviewed.assign(y=flags).groupby("extraction_rule"):
        lines.append(f"| {rule} | {len(g)} | {int(g.y.sum())} | {g.y.mean():.3f} |")
    return "\n".join(lines) + "\n", (p, lo, hi)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--file", default=str(DEFAULT_FILE))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    a = ap.parse_args(argv)
    df = pd.read_csv(a.file, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    text, _ = summarise(df)
    Path(a.out_dir).mkdir(parents=True, exist_ok=True)
    (Path(a.out_dir) / "extraction_precision.md").write_text(text, encoding="utf-8")
    print(text.strip().splitlines()[2] if len(text.strip().splitlines()) > 2 else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
