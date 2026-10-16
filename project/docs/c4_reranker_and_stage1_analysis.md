# C4 Traceability Intelligence: reranker and stage-1 analysis

Thuverakan T. (IT23281332), Component 4. This document records what was tried after the Colab experiments, with all results,
the limits of each result, and how to reproduce them (`scripts/reproduce_reranker_analysis.ipynb`).

## 1. Summary of findings

1. **Stage 1 (TF-IDF + MiniLM) is the bottleneck.** Its shortlist contains only part of the true links (top-10 hybrid recall: iTrust about 42%, eTour about 53%); the LLM cannot recover a link that was never shortlisted.
2. **A fine-tuned CodeBERT cross-encoder did not generalise.** On three unseen projects it is far worse than stage 1 alone (CM-1 MRR 0.211 versus 0.876); fused with stage 1 the results are inconsistent. It is not used.
3. **A MiniLM cross-encoder fused with stage 1 adds a small, measurable gain:** about 0.10 to 0.16 more true links per requirement in the top 5, pooled over 115 unseen requirements (95% bootstrap interval above 0), roughly 10%. The order of the top 1 to 3 is **not** reliably improved (MRR and hits@3 intervals include 0).
4. **Fine-tuning did not demonstrably help:** an untrained cross-encoder gives a similar gain.
5. **Code-specific embeddings did not beat MiniLM at stage 1** (code-search model and UniXcoder, 7 datasets, no training; UniXcoder only with plain mean pooling).
6. **On PetClinic with Llama 3.1 8B** the reranker yields 51 instead of 47 LLM-confirmed links in the top 5 for the same 130 LLM calls (no human gold, one project).
7. **Query expansion did not help:** letting the LLM write likely class and file names for each requirement left stage-1 recall unchanged on 20 iTrust requirements (top-10 0.441 before and after; top-20 0.544 to 0.529). The LLM invents names that are not in the code (section 5.7).
8. Open problems of the component itself remain: LLM verification precision, latency (about 52 s per call on the CPU server) and decay-detection accuracy are below their targets (section 5.8).

## 2. Where this fits in C4

```
requirement --> Stage 1: TF-IDF + all-MiniLM-L6-v2 (hybrid, z-score)  --> top-20 files
            --> [optional] cross-encoder second opinion, fused with stage 1 --> top-5
            --> Stage 2: Llama 3.1 8B verifies each pair (yes/no + reason + confidence)
            --> VERIFIED_TRACE edge in Neo4j; DecayFlag when a link later fails; Redis event to C3
```

* **Stage 1** is a fast search (`retrieval.py`). It turns requirement and code into word-count vectors (TF-IDF) and into sentence embeddings (all-MiniLM-L6-v2) and ranks files by similarity.
* **The cross-encoder** (`reranker/rerank.py`, off by default) reads requirement and code *together* and scores the pair; this is slower but more accurate than comparing separate vectors.
* **The LLM** (stage 2) is the judge; it is not changed by this work.
* None of these three models was built for code. Code-awareness comes only from pre-processing (`preprocess.py`: imports removed, identifiers split, JSP markup stripped). A code-specific model (CodeBERT) was tested and did worse.

## 3. Data

All datasets are public. SMOS and eANCI are Italian and were translated to English (requirements, code comments, plus an identifier glossary); eTour was already translated. Translations were produced by an LLM and were not checked by an Italian speaker.

| group | dataset | requirements | targets (code / design) | true links |
|---|---|---|---|---|
| train | itrust | 131 | 392 | 399 |
| train | smos | 67 | 100 | 1044 |
| train | eanci | 39 | 55 | 567 |
| train | etour | 58 | 116 | 308 |
| test | libest | 52 | 14 | 204 |
| test | cm1 | 22 | 53 | 45 |
| test | ebt | 41 | 50 | 98 |
| demo | petclinic | 26 | 37 | none (synthetic requirements) |

Sources: SMOS, eANCI, EasyClinic from CoEST; iTrust, eTour, LibEST, EBT from the COMET replication package (SEMERU). EasyClinic was inspected but not used (its targets are class descriptions, not code). In eANCI only the 39 requirements that appear in the gold links were used.

**Split:** by dataset, never by pair. Train = iTrust, SMOS, eANCI, eTour. Test = LibEST, CM-1, EBT (never used in training, tuning or model choice, except the fusion weights, see limits).

## 4. Method

* **Training pairs** (`reranker/data.py`, seed 13): every true link (positive) plus hard negatives (files that stage 1 ranks highly but are not true links, up to 6 per requirement) plus 3 random negatives. 4,356 train pairs (2,124 positive / 2,232 negative), 419 validation pairs (10% of the training requirements).
* **Pair input:** requirement text (cut to 160 tokens) and the two chunks of the code file that look most like the requirement (80 words each), 512 tokens in total.
* **Test candidates:** the stage-1 top-20 of every requirement of the three unseen datasets (1,988 pairs) with their gold label.
* **Metrics:** P@k, R@k, F1@k, MRR. "Top-k" is the k best of the 20 candidates, i.e. what would be sent to the LLM. Recall is against **all** true links of the dataset, so a link missed by stage 1 counts as missed by every method.
* **Fusion:** `fused = z(stage-1 score) + w * z(cross-encoder score)`, z-scored over the requirement's candidate pool.
* **Paired bootstrap** over requirements (2,000 resamples, seed 13) of (fused minus stage 1). `hits@k` = true links in the top k per requirement. An interval that excludes 0 means the difference is supported.
* **Training:** cross-encoders on a Colab T4: 3 epochs, batch 16, learning rate 2e-5, binary cross-entropy.

## 5. Results

### 5.1 Stage-1 baseline on the unseen datasets

| dataset | P@1 | R@1 | F1@1 | P@3 | R@3 | F1@3 | P@5 | R@5 | F1@5 | P@10 | R@10 | F1@10 | MRR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CM-1 | 0.682 | 0.333 | 0.448 | 0.455 | 0.667 | 0.541 | 0.327 | 0.800 | 0.465 | 0.195 | 0.956 | 0.325 | 0.876 |
| EBT | 0.268 | 0.112 | 0.158 | 0.203 | 0.255 | 0.226 | 0.161 | 0.337 | 0.218 | 0.154 | 0.643 | 0.248 | 0.536 |
| LibEST | 0.558 | 0.142 | 0.227 | 0.526 | 0.402 | 0.456 | 0.454 | 0.578 | 0.509 | 0.377 | 0.961 | 0.541 | 0.767 |

(LibEST has only 14 code files, so its top-20 contains every file; recall@20 is trivially 1.0.)

### 5.2 Stage-1 recall with three embedding models (no training)

Same TF-IDF part, same data; only the embedding model changes. "embedding" is the embedding alone, "hybrid" is TF-IDF + embedding (the pipeline's choice).
Models: `all-MiniLM-L6-v2` (general English), `flax-sentence-embeddings/st-codesearch-distilroberta-base` (code search), `microsoft/unixcoder-base` (code and comments; plain mean pooling).

Hybrid recall@10:

| dataset | MiniLM | code-search | UniXcoder |
|---|---|---|---|
| EBT (test) | 0.643 | 0.622 | 0.561 |
| LibEST (test) | 0.961 | 0.966 | 0.951 |
| CM-1 (test) | 0.956 | 0.933 | 0.911 |
| eTour (train) | 0.529 | 0.552 | 0.474 |
| SMOS (train) | 0.313 | 0.296 | 0.311 |
| eANCI (train) | 0.228 | 0.228 | 0.212 |
| iTrust (train) | 0.419 | 0.401 | 0.411 |

Embedding alone, recall@10:

| dataset | MiniLM | code-search | UniXcoder |
|---|---|---|---|
| EBT (test) | 0.633 | 0.633 | 0.449 |
| LibEST (test) | 0.971 | 0.961 | 0.941 |
| CM-1 (test) | 0.933 | 0.889 | 0.689 |
| eTour (train) | 0.510 | 0.455 | 0.331 |
| SMOS (train) | 0.259 | 0.249 | 0.266 |
| eANCI (train) | 0.236 | 0.220 | 0.213 |
| iTrust (train) | 0.333 | 0.328 | 0.331 |

Hybrid recall@5:

| dataset | MiniLM | code-search | UniXcoder |
|---|---|---|---|
| EBT (test) | 0.337 | 0.378 | 0.337 |
| LibEST (test) | 0.578 | 0.574 | 0.578 |
| CM-1 (test) | 0.800 | 0.733 | 0.733 |
| eTour (train) | 0.360 | 0.351 | 0.321 |
| SMOS (train) | 0.189 | 0.187 | 0.192 |
| eANCI (train) | 0.115 | 0.122 | 0.129 |
| iTrust (train) | 0.288 | 0.278 | 0.286 |

Hybrid recall@20:

| dataset | MiniLM | code-search | UniXcoder |
|---|---|---|---|
| EBT (test) | 0.878 | 0.867 | 0.837 |
| LibEST (test) | 1.000 | 1.000 | 1.000 |
| CM-1 (test) | 0.978 | 1.000 | 0.978 |
| eTour (train) | 0.692 | 0.692 | 0.653 |
| SMOS (train) | 0.452 | 0.441 | 0.482 |
| eANCI (train) | 0.414 | 0.395 | 0.388 |
| iTrust (train) | 0.554 | 0.546 | 0.536 |

Embedding alone, recall@5 and recall@20:

| dataset | MiniLM | code-search | UniXcoder |
|---|---|---|---|
| EBT (test) | 0.357 | 0.398 | 0.255 |
| LibEST (test) | 0.618 | 0.593 | 0.603 |
| CM-1 (test) | 0.778 | 0.622 | 0.578 |
| eTour (train) | 0.341 | 0.282 | 0.185 |
| SMOS (train) | 0.172 | 0.157 | 0.148 |
| eANCI (train) | 0.129 | 0.118 | 0.118 |
| iTrust (train) | 0.216 | 0.203 | 0.221 |

| dataset | MiniLM | code-search | UniXcoder |
|---|---|---|---|
| EBT (test) | 0.847 | 0.837 | 0.684 |
| LibEST (test) | 1.000 | 1.000 | 1.000 |
| CM-1 (test) | 0.978 | 0.978 | 0.889 |
| eTour (train) | 0.672 | 0.656 | 0.500 |
| SMOS (train) | 0.396 | 0.406 | 0.434 |
| eANCI (train) | 0.392 | 0.390 | 0.379 |
| iTrust (train) | 0.434 | 0.441 | 0.464 |

TF-IDF alone (does not depend on the embedding model):

| dataset | TF-IDF recall@5 | @10 | @20 |
|---|---|---|---|
| EBT (test) | 0.347 | 0.520 | 0.827 |
| LibEST (test) | 0.569 | 0.956 | 1.000 |
| CM-1 (test) | 0.622 | 0.822 | 0.956 |
| eTour (train) | 0.315 | 0.464 | 0.682 |
| SMOS (train) | 0.172 | 0.291 | 0.432 |
| eANCI (train) | 0.104 | 0.212 | 0.407 |
| iTrust (train) | 0.271 | 0.373 | 0.516 |

Reading: neither code-specific model beats MiniLM; TF-IDF carries much of the hybrid. SMOS and eANCI recall is structurally low because a requirement has about 15 true links there, so a top-10 can reach at most about 0.64.

### 5.3 Cross-encoders on the unseen datasets

Training log (colab):

| model | epoch | train loss | valid AUC | seconds |
|---|---|---|---|---|
| codebert | 1 | 0.6422 | 0.7344 | 447 |
| codebert | 2 | 0.5503 | 0.8074 | 451 |
| codebert | 3 | 0.4748 | 0.8419 | 451 |
| minilm_finetuned | 1 | 0.812 | 0.7677 | 91 |
| minilm_finetuned | 2 | 0.5303 | 0.8209 | 91 |
| minilm_finetuned | 3 | 0.4657 | 0.8233 | 91 |

The validation AUC uses requirements from the same projects as training; it does **not** measure transfer to new projects.

CM-1:

| method | F1@3 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| stage 1 only | 0.541 | 0.800 | 0.956 | 0.876 |
| CodeBERT fine-tuned, alone | 0.054 | 0.156 | 0.444 | 0.211 |
| CodeBERT fine-tuned, fused w=0.5 | 0.523 | 0.756 | 0.889 | 0.762 |
| CodeBERT fine-tuned, fused w=1.0 | 0.414 | 0.711 | 0.822 | 0.596 |
| CodeBERT fine-tuned, fused w=2.0 | 0.252 | 0.489 | 0.756 | 0.442 |
| MiniLM fine-tuned, alone | 0.450 | 0.733 | 0.822 | 0.787 |
| MiniLM fine-tuned, fused w=0.5 | 0.505 | 0.867 | 0.956 | 0.902 |
| MiniLM fine-tuned, fused w=1.0 | 0.505 | 0.844 | 0.956 | 0.876 |
| MiniLM fine-tuned, fused w=2.0 | 0.486 | 0.800 | 0.956 | 0.860 |
| MiniLM untrained, alone | 0.414 | 0.756 | 0.867 | 0.736 |
| MiniLM untrained, fused w=0.5 | 0.523 | 0.911 | 0.956 | 0.904 |
| MiniLM untrained, fused w=1.0 | 0.541 | 0.867 | 0.956 | 0.851 |

EBT:

| method | F1@3 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| stage 1 only | 0.226 | 0.337 | 0.643 | 0.536 |
| CodeBERT fine-tuned, alone | 0.136 | 0.265 | 0.541 | 0.367 |
| CodeBERT fine-tuned, fused w=0.5 | 0.262 | 0.367 | 0.663 | 0.583 |
| CodeBERT fine-tuned, fused w=1.0 | 0.244 | 0.388 | 0.673 | 0.540 |
| CodeBERT fine-tuned, fused w=2.0 | 0.199 | 0.337 | 0.633 | 0.450 |
| MiniLM fine-tuned, alone | 0.199 | 0.347 | 0.602 | 0.549 |
| MiniLM fine-tuned, fused w=0.5 | 0.226 | 0.378 | 0.653 | 0.559 |
| MiniLM fine-tuned, fused w=1.0 | 0.281 | 0.388 | 0.622 | 0.584 |
| MiniLM fine-tuned, fused w=2.0 | 0.244 | 0.378 | 0.622 | 0.569 |
| MiniLM untrained, alone | 0.244 | 0.398 | 0.561 | 0.517 |
| MiniLM untrained, fused w=0.5 | 0.226 | 0.388 | 0.663 | 0.574 |
| MiniLM untrained, fused w=1.0 | 0.281 | 0.398 | 0.673 | 0.579 |

LibEST:

| method | F1@3 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| stage 1 only | 0.456 | 0.578 | 0.961 | 0.767 |
| CodeBERT fine-tuned, alone | 0.278 | 0.343 | 0.706 | 0.582 |
| CodeBERT fine-tuned, fused w=0.5 | 0.483 | 0.672 | 0.966 | 0.785 |
| CodeBERT fine-tuned, fused w=1.0 | 0.461 | 0.613 | 0.926 | 0.828 |
| CodeBERT fine-tuned, fused w=2.0 | 0.411 | 0.475 | 0.794 | 0.775 |
| MiniLM fine-tuned, alone | 0.417 | 0.559 | 0.897 | 0.744 |
| MiniLM fine-tuned, fused w=0.5 | 0.489 | 0.632 | 0.971 | 0.804 |
| MiniLM fine-tuned, fused w=1.0 | 0.489 | 0.623 | 0.971 | 0.792 |
| MiniLM fine-tuned, fused w=2.0 | 0.456 | 0.608 | 0.956 | 0.771 |
| MiniLM untrained, alone | 0.389 | 0.598 | 0.907 | 0.702 |
| MiniLM untrained, fused w=0.5 | 0.467 | 0.593 | 0.966 | 0.767 |
| MiniLM untrained, fused w=1.0 | 0.478 | 0.583 | 0.961 | 0.776 |

(All 13 metric columns for every row are in `data/results/colab_results.json`. The untrained model has no w=2.0 run.)

### 5.4 Is the gain real? Paired bootstrap against stage 1

Fine-tuned MiniLM, fused (mean [95% interval], \* = interval excludes 0):

| fusion | scope | MRR | hits@3 | hits@5 |
|---|---|---|---|---|
| fuse_0.5 | ALL | +0.026 [-0.004, +0.058] | +0.035 [-0.052, +0.122] | +0.157 [+0.070, +0.252] \* |
| fuse_0.5 | CM-1 | +0.022 [-0.045, +0.091] | -0.090 [-0.273, +0.091] | +0.137 [+0.000, +0.273] |
| fuse_0.5 | EBT | +0.018 [+0.002, +0.046] \* | +0.000 [-0.098, +0.098] | +0.098 [+0.000, +0.220] |
| fuse_0.5 | LibEST | +0.035 [-0.018, +0.093] | +0.118 [-0.038, +0.288] | +0.213 [+0.077, +0.365] \* |
| fuse_1.0 | ALL | +0.024 [-0.014, +0.065] | +0.086 [-0.026, +0.200] | +0.138 [+0.017, +0.261] \* |
| fuse_1.0 | CM-1 | -0.001 [-0.114, +0.114] | -0.090 [-0.318, +0.136] | +0.092 [-0.091, +0.273] |
| fuse_1.0 | EBT | +0.038 [+0.001, +0.082] \* | +0.147 [+0.000, +0.293] | +0.123 [-0.049, +0.293] |
| fuse_1.0 | LibEST | +0.024 [-0.047, +0.097] | +0.118 [-0.096, +0.346] | +0.176 [-0.038, +0.404] |

Untrained MiniLM, fused:

| fusion | scope | MRR | hits@3 | hits@5 |
|---|---|---|---|---|
| fuse_0.5 | ALL | +0.015 [-0.021, +0.053] | +0.009 [-0.070, +0.087] | +0.115 [+0.026, +0.209] \* |
| fuse_0.5 | CM-1 | +0.023 [-0.045, +0.094] | -0.045 [-0.182, +0.091] | +0.228 [+0.045, +0.455] \* |
| fuse_0.5 | EBT | +0.029 [+0.001, +0.065] \* | +0.000 [-0.098, +0.098] | +0.123 [+0.000, +0.244] |
| fuse_0.5 | LibEST | +0.001 [-0.065, +0.070] | +0.040 [-0.115, +0.192] | +0.058 [-0.077, +0.192] |
| fuse_1.0 | ALL | +0.012 [-0.032, +0.056] | +0.086 [-0.009, +0.183] | +0.088 [-0.017, +0.200] |
| fuse_1.0 | CM-1 | -0.023 [-0.114, +0.070] | +0.000 [-0.136, +0.136] | +0.137 [-0.091, +0.409] |
| fuse_1.0 | EBT | +0.033 [-0.016, +0.089] | +0.148 [+0.000, +0.293] | +0.148 [-0.024, +0.317] |
| fuse_1.0 | LibEST | +0.010 [-0.064, +0.088] | +0.080 [-0.096, +0.269] | +0.019 [-0.154, +0.212] |

Reading: the only robust effect is **more true links in the top 5** (hits@5, pooled). MRR and hits@3 are not distinguishable from noise. The fine-tuned and untrained models are not distinguishable from each other (their intervals overlap; they were not compared directly with `--versus` because the Colab score files were not kept).

### 5.5 Stage 1 versus stage 1 + reranker, with the LLM (PetClinic)

26 synthetic requirements written from the code, 37 code files. Every candidate pair of both methods had already been judged by Llama 3.1 8B in earlier runs (expert prompt, temperature 0), so no new LLM calls were made. "Confirmed" = `is_linked` and confidence >= 0.5.

| shortlist | LLM calls | stage 1 only: confirmed | stage 1 + reranker: confirmed |
|---|---|---|---|
| top-3 | 78 | 38 | 39 |
| top-5 | 130 | 47 | 51 |

In the top 5, the reranker dropped 12 pairs (the LLM had rejected all 12) and added 12 (the LLM confirmed 4: `findOwners.html` for the owner search, `createOrUpdateVisitForm.html` for new visits, `ownerDetails.html` for the visit list, `welcome.html` for the welcome page). Scoring 520 pairs (26 x 20) took about 4 s on an Apple GPU, against 25 to 50 s per LLM call.

### 5.6 CodeBERT versus MiniLM, short

CodeBERT is a 125M-parameter encoder pre-trained on code and comments; it is not instruction-following and gives nothing useful until it is fine-tuned. With 4,356 pairs from four projects the fine-tuned CodeBERT learned the training projects (validation AUC 0.84) but not the task across projects. The ms-marco MiniLM cross-encoder is already trained for "is this passage relevant to this query", which probably explains why it transfers better (not tested).

### 5.7 Query expansion with the LLM

LLM: `llama3.1-8k`. 20 iTrust requirements that have at least one true link (68 true links); one LLM call per requirement (mean 29 s). Stage-1 recall (hybrid) on exactly these requirements:

| shortlist | plain requirement | requirement + LLM words |
|---|---|---|
| top-5 | 0.338 | 0.338 |
| top-10 | 0.441 | 0.441 |
| top-20 | 0.544 | 0.529 |

Example answers: `UC10E1` -> MedicalIdentificationService, validateMedicalId, tryAgain, MedicalIdentificationValidator, invalidIdPrompt; `UC10E2` -> PatientDAO, confirmPatient, selectPatient, PatientService, verifyPatient; `UC10S1` -> PatientService, ConfirmPatientSelection, PersonalHealthInfo, EditHistoricalValues, Immunizations

Reading: no gain. The answers look plausible but are guesses (for example `PatientService`, `ConfirmPatientSelection`); iTrust's real classes are named differently (`...Action`, `...DAO`), so the added words rarely match. The test is small (20 requirements, 68 links), so a small effect cannot be excluded, but there is no sign of one.

### 5.8 Existing C4 evaluation (from `data/results/summary.json`)

| dataset | requirements | targets | true links | language | base rate |
|---|---|---|---|---|---|
| iTrust | 131 | 392 | 399 | Java/JSP | 0.008 |
| eTour | 58 | 116 | 308 | Java | 0.046 |
| LibEST | 52 | 14 | 204 | C | 0.28 |
| CM-1 | 22 | 53 | 45 | text (design) | 0.039 |

Precision, recall and F1 (small samples, see the dataset column):

| dataset | method | precision | recall | F1 |
|---|---|---|---|---|
| iTrust (10 requirements, top-5) | Embeddings only | 0.06 | 0.086 | 0.071 |
| iTrust (10 requirements, top-5) | TF-IDF only | 0.12 | 0.171 | 0.141 |
| iTrust (10 requirements, top-5) | Hybrid, no LLM | 0.14 | 0.2 | 0.165 |
| iTrust (10 requirements, top-5) | Full pipeline (hybrid + Llama 3.1 8B) | 0.375 | 0.171 | 0.235 |
| eTour (top-10) | TF-IDF only | 0.248 | 0.468 | 0.324 |
| eTour (top-10) | Embeddings only | 0.271 | 0.51 | 0.354 |
| eTour (top-10) | Hybrid, no LLM | 0.283 | 0.532 | 0.369 |
| LibEST (top-5) | TF-IDF only | 0.454 | 0.578 | 0.509 |
| LibEST (top-5) | Embeddings only | 0.481 | 0.613 | 0.539 |
| LibEST (top-5) | Hybrid, no LLM | 0.462 | 0.588 | 0.517 |

Non-functional requirements:

| requirement | target | measured | met |
|---|---|---|---|
| Scale: 10,000 nodes, queries under 2 s | < 2 s | write 8 ms, read traces 4 ms, read all code entities 0.48 s | True |
| LLM verification latency | <= 5 s | typical 52 s, p95 80 s (CPU-only server, no GPU) | False |
| Precision | >= 90% | 37.5% (iTrust sample, full pipeline) | False |
| Recall | >= 80% | stage 1: 41.6% at top-10 on iTrust, 91% at top-50 on eTour | False |

Decay injection (9 known-good links, model `llama3.1-8k`):

| mutation | injected | detected |
|---|---|---|
| unrelated_replacement | 9 | 9 |
| negate_behavior | 0 | 0 |
| change_numbers | 5 | 1 |
| strip_to_first_sentence | 9 | 6 |
| cosmetic_control | 9 | 1 |

Decay detection accuracy 0.696 (target >= 0.85), false-decay rate on the control 0.111. The sample is 9 links, so these rates are very uncertain.

## 6. Limits of every result above

* **Fusion weights were chosen after seeing the test results** (w = 0.5 and 1.0 both reported, same direction).
* **Small test sets:** CM-1 22, EBT 41, LibEST 52 requirements; LibEST has 14 code files; CM-1 is a design document, not code.
* **SMOS** has "hub" classes (`User`, `Role`) linked to almost every requirement, which can be memorised in training.
* **Hard negatives** are chosen by stage 1 and may contain true links missing from the gold standard.
* **eTour code is Italian** (identifiers untranslated).
* **Translations** were made by an LLM and not verified by a speaker of Italian.
* **PetClinic** has no human gold: "confirmed" means an 8B LLM said yes, and it makes false positives (for example `vetList.html` for owner pagination). The requirements are synthetic.
* **Colab results are replayed, not recomputed:** the Colab model folders and score files were not downloaded. Re-training locally on different hardware gives slightly different numbers.
* **UniXcoder** was tested with plain mean pooling only; its recommended pooling mode was not tried.
* Nothing here was run end to end with the LLM and the graph on the benchmark datasets; the PetClinic comparison replays earlier verdicts.

## 7. Reproducing the results

Open `scripts/reproduce_reranker_analysis.ipynb` with the project's `.venv` kernel (Python 3.9). It prints every table in this document that can be recomputed.

| Notebook section | Reproduced exactly here? | Needs |
|---|---|---|
| 1 data and split | yes | `data/processed`, `data/reranker` |
| 2 stage-1 baseline | yes (differences < 0.002) | nothing else |
| 3 three embedding models | yes | models in the Hugging Face cache (MiniLM in `models/`, code-search about 330 MB, UniXcoder 505 MB). Without them that model is skipped. |
| 4 untrained MiniLM cross-encoder + bootstrap | yes (differences vs Colab are small: CUDA vs local float arithmetic) | `cross-encoder/ms-marco-MiniLM-L-6-v2` in the cache (about 90 MB) |
| 5 fine-tuned CodeBERT / MiniLM | **replayed** from `data/results/colab_results.json` | optional: put the Colab `test_scores.jsonl` files in `data/reranker/colab_scores/`; optional re-training switch |
| 6 PetClinic + LLM | yes | stored verdicts in `data/results/petclinic_verdicts.json` |
| 7 query expansion | yes (replays stored LLM answers) | `data/results/query_expansion_itrust.json` |
| 8 C4 evaluation | replayed from the stored result files | optional live Neo4j section |

Time: sections 1, 2, 5, 8 take seconds; section 3 a few minutes (set `C4_FULL=1` to run all seven datasets, about 15 minutes); section 4 and 6 about a minute each on an Apple GPU.
The notebook sets `HF_HUB_OFFLINE=1`, so it uses only models that are already downloaded.

**To rebuild the data from scratch (deterministic, seed 13):**

```bash
python -m agents.traceability_agent.reranker.data prepare            # SMOS, eANCI, EBT -> data/processed
python -m agents.traceability_agent.reranker.data pairs              # train / valid / test files
python agents/traceability_agent/reranker/evaluate.py --data data/reranker      # stage-1 baseline
```

**To re-train on Colab:** the training and test pair files and the Colab bundle are not kept in the repository (they are regenerated identically, checked by hash). Run `python -m agents.traceability_agent.reranker.data pairs` and then `python -m agents.traceability_agent.reranker.data bundle`, upload `data/reranker_colab.zip` to Colab and run `scripts/train_reranker_colab.ipynb` (T4 GPU; CodeBERT about 24 minutes, MiniLM about 5). `train.jsonl` and `valid.jsonl` (about 10 MB) are only needed for training.
**To use the reranker in the pipeline:** `python -m agents.traceability_agent link --project <p> --top-k 5 --reranker cross-encoder/ms-marco-MiniLM-L-6-v2` (off by default; the first run downloads the model).

## 8. Files

New: `agents/traceability_agent/reranker/` (`data.py`, `train.py`, `evaluate.py`, `rerank.py`, `query_expansion.py`), `tests/test_rerank.py`, `scripts/train_reranker_colab.ipynb`, `scripts/reproduce_reranker_analysis.ipynb`, `data/translated_en/`, `data/processed/{smos,eanci,ebt,petclinic}`, `data/reranker/` (`meta.json`, `test_candidates.jsonl`), `data/results/{colab_results,reranker,petclinic_verdicts,stage1_embeddings,query_expansion_itrust}.json`, this document.
Changed: `agent.py` (optional `reranker`, `rerank_pool`), `cli.py` (`--reranker`, `--rerank-pool`, `--rerank-weight`). Defaults are unchanged.

## 9. What to do next

1. Gold labels for PetClinic (or a second reviewer for a sample of the translated data) so that the LLM comparison does not rely on LLM verdicts.
2. A direct comparison of fine-tuned versus untrained MiniLM (needs the Colab score files), and a leave-one-dataset-out training run.
3. Replace or complement the 8B LLM verifier (for example a code LLM that fits the 8 GB server, or a larger model on a GPU) and measure precision and latency.
4. Decay-risk prediction and a larger decay-injection test (more than 9 links) for the main novelty of the component.
5. Update the methodology document: it still lists CodeBERT/GraphCodeBERT and ChromaDB, which are not used.

## 10. Glossary

* **Stage 1:** the fast search that shortlists candidate files for a requirement.
* **Cross-encoder:** a model that reads two texts together and returns one score; slower and more accurate than comparing two separate vectors.
* **Fusion:** adding the standardised (z-score) scores of two methods.
* **P@k / R@k / F1@k:** precision, recall, F1 of the k best candidates. **MRR:** mean of 1/rank of the first correct link.
* **hits@k:** true links in the top k per requirement.
* **Paired bootstrap:** resampling the requirements many times to see how much a difference could vary by chance.
* **Hard negative:** a wrong candidate that the retrieval ranks high.
* **Silver label:** a label from a model (here the LLM) instead of a human.
