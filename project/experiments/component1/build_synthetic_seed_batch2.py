"""Second batch of synthetic-generation seed inputs for Component 1 (no model calls, no LLM).

Reads (never modifies): processed/master_requirements.csv, processed/tasks/{generation_inputs, synthetic_seed_inputs, frozen_test_ids,
generation_eval_ids, classification_fr_nfr, classification_nfr_subtype, ambiguity, dependency_pairs}.csv and writes two NEW files
(never overwritten if different):
  processed/tasks/synthetic_seed_inputs_batch2.csv        id, source, requirement_text, requirement_type   (~400 rows, same format as batch 1)
  processed/tasks/synthetic_seed_inputs_batch2_report.md  counts, filter funnel, and the zero-overlap / similarity confirmations

Pool: master rows whose record is a `requirement_text` row of generation_inputs.csv with split == train (master_requirements.csv has no
split column; the split comes from the task file). Filters, in order: not in batch 1; 6-60 words; ends like a sentence; extraction-noise
checks; same normalized text as a batch-1 seed or any test/val text; MiniLM cosine >= 0.90 to a batch-1 seed or to ANY frozen-test text
(test texts are only embedded in memory for this guard and are never printed or written); then a seeded greedy stratified pick that also skips
rows with cosine >= 0.90 to an already selected row.
Quotas: FR_NFR 40 %, PROMISE 35 %, PURE 10 %, other train sources 15 %; FR/NFR about 50/50 where the label is known; about 15 % of the rows
carry weak words or are short/vague. Deterministic (seed 327).

Run from the project directory:  ..\\.venv\\Scripts\\python.exe experiments\\component1\\build_synthetic_seed_batch2.py
"""
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from build_master import PROCESSED, write_safe  # noqa: E402
from agents.requirement_agent.features import SEED, embed, normalize_for_models  # noqa: E402

TASKS = PROCESSED / "tasks"
OUT = TASKS / "synthetic_seed_inputs_batch2.csv"
OUT_REPORT = TASKS / "synthetic_seed_inputs_batch2_report.md"
N_TARGET = 400
COSINE_LIMIT = 0.90
# (label, source group) -> quota; shortfalls go to FR_NFR with the same label
QUOTAS = {("FR", "FR_NFR"): 110, ("NFR", "FR_NFR"): 50, ("FR", "PROMISE"): 60, ("NFR", "PROMISE"): 80, ("NFR", "PURE"): 40, ("", "other"): 60}
VAGUE_SHARE = 0.15
VAGUE_TERMS = re.compile(r"\b(etc\.?|and/or|as (?:appropriate|needed|required|necessary)|appropriate|adequate|sufficient|user[- ]friendly|easy to use|"
                         r"easily|flexible|fast|quick(?:ly)?|several|various|some|many|few|reasonable|normal|acceptable|if possible|where possible|tbd)\b", re.I)
SHORT_WORDS = 8


def h(*parts):
    return hashlib.sha256("|".join(str(p) for p in (SEED,) + parts).encode("utf-8")).hexdigest()


def key(text):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s+", " ", str(text).lower()))


def source_group(source):
    return source if source in ("FR_NFR", "PROMISE", "PURE") else "other"


# ----------------------------------------------------------------------------- filters
URL = re.compile(r"(?:https?://|www\.)\S+", re.I)


def noise_reason(text):
    """Why a text looks like extraction noise, or ''. Heuristic."""
    t = text.strip()
    letters = [c for c in t if c.isalpha()]
    if re.fullmatch(r"(?:page\s*)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?", t, re.I):
        return "page_number"
    if "|" in t or "\t" in t or re.search(r"(?:\.\s?){5,}", t) or re.search(r"(?:\b\d+(?:\.\d+)?\s+){4,}", t):
        return "table_fragment"
    if sum(c.isdigit() for c in t) / max(len(t), 1) > 0.30:
        return "table_fragment"
    if len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) >= 0.80:
        return "all_caps_heading"
    stripped = URL.sub(" ", t)
    if URL.search(t) and len(stripped.split()) < 4:
        return "url_only"
    if "�" in t or re.search(r"[ÃÂâ][\u0080-¿€‚-„]", t) or "â€" in t:
        return "encoding_noise"
    first = re.sub(r"^[\s(\[\d.)\]\-•·*]+", "", t)
    if first[:1].islower():
        return "starts_mid_sentence"
    return ""


def ends_like_sentence(text):
    return bool(re.search(r"[.!?][\"'”’)\]]*\s*$", text.strip()))


def vague_flag(text, weak_words):
    low = text.lower()
    if any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", low) for w in weak_words):
        return "weak_word"
    if VAGUE_TERMS.search(text):
        return "vague_term"
    if len(text.split()) <= SHORT_WORDS:
        return "short"
    return ""


# ----------------------------------------------------------------------------- data
def read(name):
    return pd.read_csv(TASKS / name, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def held_out_texts():
    """Every val/test text of the task files (for exact-match removal) and every frozen-test text (for the cosine guard). Never printed."""
    test, val = set(), set()
    for name in ("classification_fr_nfr", "classification_nfr_subtype", "ambiguity", "generation_inputs"):
        d = read(f"{name}.csv")
        test |= set(d[d.split == "test"].requirement_text_original)
        val |= set(d[d.split == "val"].requirement_text_original)
    dp = read("dependency_pairs.csv")
    for col in ("fr_text", "nfr_text"):
        test |= set(dp[dp.split == "test"][col])
        val |= set(dp[dp.split == "val"][col])
    return sorted(t for t in test if t.strip()), sorted(t for t in val if t.strip())


def max_cosine(a, b, block=2000):
    """For every row of `a`, the largest cosine to any row of `b` (both L2-normalised)."""
    out = np.zeros(len(a), dtype=np.float32)
    for s in range(0, len(a), block):
        out[s:s + block] = (a[s:s + block] @ b.T).max(axis=1)
    return out


def build():
    gen, master = read("generation_inputs.csv"), pd.read_csv(PROCESSED / "master_requirements.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    batch1 = read("synthetic_seed_inputs.csv")
    frozen_ids, eval_ids = set(read("frozen_test_ids.csv").record_id), set(read("generation_eval_ids.csv").id)
    funnel = []

    pool = gen[(gen.record_type == "requirement_text") & (gen.split == "train")]
    pool = pool[pool.record_id.isin(set(master.record_id))]
    pool = pool.assign(source=pool.source_dataset, text=pool.requirement_text_original.str.strip(), group=pool.source_dataset.map(source_group))
    funnel.append(("train requirement_text rows that are in master_requirements.csv", len(pool)))

    def step(label, mask):
        nonlocal pool
        funnel.append((label, int((~mask).sum())))
        pool = pool[mask]

    step("removed: id in batch 1 / frozen test ids / generation_eval ids", ~pool.record_id.isin(set(batch1.id) | frozen_ids | eval_ids))
    wc = pool.text.str.split().str.len()
    step("removed: fewer than 6 or more than 60 words", (wc >= 6) & (wc <= 60))
    step("removed: does not end like a sentence", pool.text.map(ends_like_sentence))
    noise = pool.text.map(noise_reason)
    for reason in ("page_number", "table_fragment", "all_caps_heading", "url_only", "encoding_noise", "starts_mid_sentence"):
        n = int((noise == reason).sum())
        funnel.append((f"removed: extraction noise ({reason})", n))
    pool = pool[noise == ""]
    step("removed: no FR/NFR label and not an 'other' source row (unlabeled rows of labelled sources)", ~((pool.requirement_type == "") & (pool.group != "other")))
    test_texts, val_texts = held_out_texts()
    held_keys = {key(t) for t in test_texts} | {key(t) for t in val_texts} | {key(t) for t in batch1.requirement_text}
    pool = pool.assign(nkey=pool.text.map(key))
    step("removed: same normalized text as a batch-1 seed or any val/test text", ~pool.nkey.isin(held_keys))
    step("removed: same normalized text as another pool row (kept the first by hash order)",
         ~pool.assign(_o=pool.record_id.map(lambda r: h("dedupe", r))).sort_values("_o", kind="stable").duplicated("nkey", keep="first").reindex(pool.index))

    cand = pool.copy()
    emb_c = embed([normalize_for_models(t) for t in cand.text])
    emb_b1 = embed([normalize_for_models(t) for t in batch1.requirement_text])
    emb_test = embed([normalize_for_models(t) for t in test_texts])
    emb_val = embed([normalize_for_models(t) for t in val_texts])
    cand = cand.assign(cos_b1=max_cosine(emb_c, emb_b1), cos_test=max_cosine(emb_c, emb_test), cos_val=max_cosine(emb_c, emb_val))
    keep = cand.cos_b1 < COSINE_LIMIT
    funnel.append((f"removed: cosine >= {COSINE_LIMIT} to a batch-1 seed", int((~keep).sum())))
    cand, emb_c = cand[keep], emb_c[keep.values]
    keep = cand.cos_test < COSINE_LIMIT
    funnel.append((f"removed: cosine >= {COSINE_LIMIT} to a frozen test text", int((~keep).sum())))
    cand, emb_c = cand[keep], emb_c[keep.values]

    # weak words: QuRE weak words from train rows of the ambiguity task
    amb = read("ambiguity.csv")
    weak = sorted({p.split("=", 1)[1].strip().lower() for v in amb[(amb.split == "train") & amb.ambiguity_label_basis.str.startswith("QuRE")].smell_evidence
                   for p in v.split(";") if p.startswith("weak_word=")})
    cand = cand.assign(vague=cand.text.map(lambda t: vague_flag(t, weak)))
    funnel.append(("candidates left for the stratified pick", len(cand)))

    # ---- greedy stratified pick (hash order, cosine guard against already selected rows)
    order = cand.assign(_o=cand.record_id.map(lambda r: h("batch2", r))).sort_values("_o", kind="stable")
    pos = {rid: i for i, rid in enumerate(cand.record_id)}
    chosen, chosen_vec, skipped_near = [], [], 0

    def take(frame, n, want_vague):
        nonlocal skipped_near
        got = []
        for r in frame.itertuples():
            if len(got) >= n:
                break
            if bool(r.vague) != want_vague:
                continue
            v = emb_c[pos[r.record_id]]
            if chosen_vec and float(np.max(np.stack(chosen_vec) @ v)) >= COSINE_LIMIT:
                skipped_near += 1
                continue
            got.append(r.record_id)
            chosen.append(r.record_id)
            chosen_vec.append(v)
        return got

    shortfall = Counter()
    for (label, group), quota in QUOTAS.items():
        sub = order[(order.requirement_type == label) & (order.group == group)] if label else order[order.group == group]
        n_vague = round(VAGUE_SHARE * quota)
        got = take(sub, n_vague, True) + take(sub, quota - n_vague, False)
        # top up from the other kind if one kind ran out
        if len(got) < quota:
            got += take(sub, quota - len(got), True) + take(sub, quota - len(got), False)
        if len(got) < quota:
            shortfall[label] += quota - len(got)
    for label, missing in shortfall.items():
        if label:
            sub = order[(order.requirement_type == label) & (order.group == "FR_NFR") & ~order.record_id.isin(chosen)]
            take(sub, missing, False)
    sel = cand[cand.record_id.isin(chosen)].copy()
    funnel.append((f"skipped during the pick: cosine >= {COSINE_LIMIT} to an already selected row", skipped_near))
    out = pd.DataFrame({"id": sel.record_id, "source": sel.source, "requirement_text": sel.text, "requirement_type": sel.requirement_type})
    out = out.sort_values("id", kind="stable").reset_index(drop=True)
    return out, sel, funnel, dict(batch1=batch1, frozen_ids=frozen_ids, eval_ids=eval_ids, emb_sel=emb_c[[pos[r] for r in sel.record_id]], emb_b1=emb_b1,
                                  emb_test=emb_test, n_test=len(test_texts), n_val=len(val_texts), weak=weak, held_keys=held_keys, shortfall=dict(shortfall))


def report(out, sel, funnel, ctx):
    ids = set(out.id)
    em = ctx["emb_sel"]
    sims = em @ em.T
    np.fill_diagonal(sims, 0)
    lines = ["# Synthetic seed inputs, batch 2: report", "",
             f"File: `processed/tasks/synthetic_seed_inputs_batch2.csv` ({len(out)} rows; target {N_TARGET}). Seed {SEED}. No model or LLM calls; test texts were embedded "
             "in memory only for the similarity guard and are not printed or written anywhere.", "",
             "## Counts", "", "Split: all rows are `train` (selected only from rows with split == train in `generation_inputs.csv`; "
             "`master_requirements.csv` has no split column).", "",
             "| source | FR | NFR | unlabeled | total | target share |", "|---|---|---|---|---|---|"]
    targets = {"FR_NFR": "40 %", "PROMISE": "35 %", "PURE": "10 %", "other": "15 %"}
    grp = out.source.map(source_group)
    for g in ("FR_NFR", "PROMISE", "PURE", "other"):
        s = out[grp == g]
        lines.append(f"| {g} | {int((s.requirement_type == 'FR').sum())} | {int((s.requirement_type == 'NFR').sum())} | {int((s.requirement_type == '').sum())} | {len(s)} | {targets[g]} (actual {len(s) / len(out):.0%}) |")
    lines.append(f"| **all** | {int((out.requirement_type == 'FR').sum())} | {int((out.requirement_type == 'NFR').sum())} | {int((out.requirement_type == '').sum())} | {len(out)} | |")
    lines += ["", "Sources inside \"other\": " + ", ".join(f"{k}={v}" for k, v in out[grp == "other"].source.value_counts().items()) + ".", "",
              f"FR/NFR among labelled rows: {int((out.requirement_type == 'FR').sum())} FR / {int((out.requirement_type == 'NFR').sum())} NFR.",
              f"Words per text: min {out.requirement_text.str.split().str.len().min()}, median {int(out.requirement_text.str.split().str.len().median())}, max {out.requirement_text.str.split().str.len().max()}.", "",
              "## Weak-word / vague / short rows (for needs_clarification cases)", ""]
    v = sel.set_index("record_id").loc[out.id].vague
    lines.append(f"{int((v != '').sum())} of {len(out)} rows ({(v != '').mean():.0%}): " + ", ".join(f"{k}={n}" for k, n in v[v != ''].value_counts().items()) +
                 f". Weak words are the {len(ctx['weak'])} QuRE weak words from train rows; vague terms are a small fixed list (etc., and/or, as appropriate, adequate, user-friendly, ...); short = at most {SHORT_WORDS} words.")
    lines += ["", "## Filter funnel (rows removed by each filter, applied in this order)", "", "| step | rows |", "|---|---|"]
    lines += [f"| {a} | {n} |" for a, n in funnel]
    lines += ["", "## Confirmations (computed from the written file)", ""]
    checks = [
        ("ids overlapping frozen_test_ids.csv", len(ids & ctx["frozen_ids"])),
        ("ids overlapping generation_eval_ids.csv", len(ids & ctx["eval_ids"])),
        ("ids overlapping batch 1 (synthetic_seed_inputs.csv)", len(ids & set(ctx["batch1"].id))),
        ("texts with the same normalized text as a batch-1 seed or any val/test text", len({key(t) for t in out.requirement_text} & ctx["held_keys"])),
    ]
    lines += [f"- {a}: **{n}**" for a, n in checks]
    mc_test = float(max_cosine(em, ctx["emb_test"]).max())
    mc_b1 = float(max_cosine(em, ctx["emb_b1"]).max())
    lines += [f"- max cosine similarity of any batch-2 row to any of the {ctx['n_test']} frozen-test texts: **{mc_test:.3f}** (limit {COSINE_LIMIT}; {'OK' if mc_test < COSINE_LIMIT else 'VIOLATION'})",
              f"- max cosine similarity to any batch-1 seed: {mc_b1:.3f}",
              f"- max cosine similarity between two batch-2 rows: {float(sims.max()):.3f}",
              f"- split of every selected row in generation_inputs.csv: train ({len(out)} of {len(out)})", "",
              "Notes: similarity uses all-MiniLM-L6-v2 embeddings of the normalized text; the noise filters are heuristics; the quota shortfalls, if any: "
              f"{ctx['shortfall'] or 'none'}."]
    return "\n".join(lines) + "\n"


def main():
    out, sel, funnel, ctx = build()
    if (out.id.isin(ctx["frozen_ids"] | ctx["eval_ids"] | set(ctx["batch1"].id))).any():
        raise SystemExit("STOP: a selected id overlaps frozen test / eval / batch 1 ids")
    text = report(out, sel, funnel, ctx)
    if "VIOLATION" in text:
        raise SystemExit("STOP: similarity limit violated")
    write_safe(OUT, out)
    if OUT_REPORT.exists() and OUT_REPORT.read_text(encoding="utf-8") != text:
        raise SystemExit(f"STOP: {OUT_REPORT} exists and differs. Not overwriting.")
    OUT_REPORT.write_text(text, encoding="utf-8")
    print(f"batch 2: {len(out)} rows")


if __name__ == "__main__":
    main()
