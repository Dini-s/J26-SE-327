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
| demo | petclinic | 26 | 37 | none (demo requirements) |

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

26 demo requirements written from the code, 37 code files. Every candidate pair of both methods had already been judged by Llama 3.1 8B in earlier runs (expert prompt, temperature 0), so no new LLM calls were made. "Confirmed" = `is_linked` and confidence >= 0.5.

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

### 5.x Learning curve: does more training data help?

Same model trained on 1, 2, 3, 4 projects (order A: iTrust, eTour, SMOS, eANCI; order B, MiniLM only: eANCI, SMOS, eTour), always tested on the same unseen LibEST, CM-1, EBT. One seed, so the numbers are noisy. Raw data: `data/results/learning_curve_minilm.json`, `learning_curve_codebert.json`.

| Projects | MiniLM MRR alone (A / B) | MiniLM fused hits@5 gain (A / B) | CodeBERT MRR alone | CodeBERT fused hits@5 gain |
|---|---|---|---|---|
| 1 | 0.525 / 0.509 | +0.070 / +0.088 | 0.398 | +0.155 |
| 2 | 0.551 / 0.540 | +0.131 / +0.130 | 0.422 | +0.086 |
| 3 | 0.554 / 0.572 | +0.113 / +0.183 | 0.353 | +0.053 |
| 4 | 0.587 | +0.157 | 0.351 | +0.115 |

Reading:
* **MiniLM:** the model alone improves a little with more projects (MRR 0.51-0.53 to 0.59, same direction in both orders). The fused gain also tends upward, but the 95% intervals overlap almost completely (for example +0.070 [-0.017, 0.157] versus +0.157 [0.070, 0.252]), and an untrained MiniLM already gives +0.115. So a fourth project is about +0.04 over untrained, which is inside the noise. Not proven.
* **CodeBERT:** flat or falling (MRR 0.40 to 0.35) and far below MiniLM (0.35 versus 0.59). The fused gain jumps around with no trend and is negative on CM-1 in every run. Four times more data did not help it. Order B was not run for CodeBERT.
* **Decision:** the evidence does not justify collecting much more data for CodeBERT. For MiniLM, extra data might add a few points, but it is not shown. Keep stage 1 + (optional) MiniLM fusion; the bigger lever remains stage-1 recall.
* Limits: 4 points, one seed; data size and diversity grow together; the tiny validation sets make "valid AUC" unreliable.

### 5.y Hand-checking the links, and the evidence prompt (default for linking)

**How the links were checked.** 40 verified PetClinic links (a fixed random sample) were labelled correct / wrong / unsure by an **AI reviewer (Claude), not by a human**, reading the requirement and the code. Labels: `data/labels/spring-petclinic_claude.json`. A human should spot-check some of them (the dashboard page "Evaluate links" is for that).

| | Links kept | Precision | Share of the correct links kept |
|---|---|---|---|
| Expert prompt (old default, accepts all) | 36 | 58% (21/36) | 100% |
| Only confidence >= 0.85 ("trusted") | 11 | 91% (10/11) | 48% |
| **Evidence prompt (new default)** | 17 | **82% (14/17)** | 67% |
| Evidence prompt, full coverage only | 12 | 75% (9/12) | 43% |
| Evidence AND confidence >= 0.85 | 8 | 88% (7/8) | 33% |

Expert prompt precision by confidence: 0.85 and above 91% (10/11), 0.7 to 0.85 only 44% (11/25). Most wrong links were large controllers (`PetController`, `OwnerController`, `VisitController`) linked to unrelated requirements.

The evidence prompt makes the model quote code that satisfies the requirement, and the quote is checked against the code. It rejected 12 of the 15 wrong links, at the cost of 7 of the 21 correct ones (mostly requirements about validation rules in entities and templates). It was also faster (about 40 s per call against about 52 s). Script: `scripts/ab_evidence_mode.py`, raw rows: `data/results/evidence_ab_spring-petclinic.json`.

**Trade-off and decision.** Precision rises from 58% to 82% and recall falls to about two thirds: fewer wrong links, more missed ones. `link` now uses the evidence prompt by default (`--prompt expert` restores the old behaviour). Re-checking existing links (monitor, commit handling) still uses the expert prompt on purpose: it is more lenient, so links made earlier do not decay by accident, and the decay-injection results (69.6%) were measured with it.

Limits: 36 judged links, one project, one reviewer who is an AI; the 95% interval for 82% is roughly 59% to 94%. The 0.85 and 0.7-0.85 figures rest on 11 and 25 links.

### 5.z Decay detection, second measurement (ground-truth links, requirement edits added)

The first measurement (69.6%, 9 links) was too small. The harness now takes 10 ground-truth (CoEST) links from each of iTrust, eTour and CM-1 (seed 7, targets up to 3000 characters), first checks that the detector still accepts the unedited pair (a link the LLM rejects anyway cannot be "detected"), then edits the code or the requirement. Raw rows: `data/results/decay_injection_v2.json`.

| Edit | Flagged as decayed |
|---|---|
| Code replaced by unrelated text | 11 / 11 |
| Requirement replaced by unrelated text | 11 / 11 |
| Code cut to its first sentence | 8 / 11 |
| Requirement negated ("shall" to "shall not") | 5 / 8 |
| Code negated (flags, comparisons) | 0 / 2 |
| Numbers in the code changed | 0 / 3 |
| **All breaking edits** | **35 / 46 = 76.1%, 95% interval 62% to 86%** |
| Harmless edits (controls: code and requirement) | 0 / 22 flagged, interval 0% to 15% |

What this says:
* Gross breaks (unrelated text) are always caught and harmless edits are never flagged. That is the useful, solid part.
* Subtle breaks are not reliably caught: a changed number or a negated condition is missed (0 of 3 and 0 of 2, tiny counts), and a negated requirement is missed 3 times in 8. The 8B model reads topic, not exact values.
* The target of 85% is not reached; the interval (62% to 86%) only just reaches it.

Limits to say out loud:
* **Only 11 of the 30 links were usable.** The detector accepted 8 of 10 CM-1 links but only 3 of 20 iTrust and eTour links (17 skipped, 2 on CM-1). So the result is dominated by CM-1 (design text); code links are 3. This is the same weakness as in the linking results: the LLM rejects many true links.
* The 46 edits come from 11 links, so they are not independent and the real uncertainty is wider than the interval shown.
* Measured before the decay rule got its noise margin (a still-"linked" answer only decays a link if confidence fell by at least 0.2). Most edits here give "not linked", so the effect is expected to be small, but the run was not repeated.

### 5.w Self-check and ground truth on all stored links (iTrust)

`python -m agents.traceability_agent selfcheck --project iTrust` (no LLM) found no inconsistency: 9 of 9 checks passed (links point at existing requirements and files, no duplicates, scores agree with links, decayed links have flags). Against the ground truth of the 82 requirements processed so far (129 verified links, expert prompt): **precision 46%, recall 21%, F1 29%** (59 of 129 verified links are true; 59 of the 274 true links of those requirements were found). This is a larger sample than the earlier 10-requirement run (precision 37.5%, recall 17.1%) and points the same way: the shortlist misses most true links and the LLM accepts many wrong ones. Only the checks that need a code quote (evidence prompt) are not exercised on iTrust, because its links were written with the older prompt.

### 5.v Full pipeline on eTour (second dataset)

First 15 requirements of eTour, top-5 candidates each, 93 true links among them, evidence prompt (74 LLM calls, mean 34.8 s, p95 38.9 s). Log: `data/runs/20261017-113809-hybrid-top5-evidence/events.jsonl`.

| Method | Precision | Recall | F1 |
|---|---|---|---|
| Stage 1 only (hybrid, no LLM) | 49.3% | 39.8% | 44.0% |
| **Full pipeline (hybrid + Llama 3.1 8B, evidence prompt)** | **81.5%** | 23.7% | 36.7% |

The LLM step removes most wrong candidates (precision 49% to 82%) but also rejects many true ones (recall 40% to 24%), so F1 goes down. The same pattern as on iTrust (precision up, recall down) and the same lesson: the verification is precise but too strict, and recall is limited first by the shortlist and then by the LLM. 15 requirements only; the expert-prompt run on the same requirements was not done.

### 5.u Fine-tuning MiniLM on training pairs (stage-1 embedding model)

Question: does training the stage-1 embedding model (all-MiniLM-L6-v2) on LLM-written requirement/code pairs raise stage-1 recall? Training data: 2,271 hand-made training pairs in 4 languages (Java, JavaScript, C, SQL and JSP), 30+ domains, each with 2 hard negatives (similar-looking wrong code). Test data: LibEST, CM-1 and EBT, expert-labelled projects never used for training. Metric: recall of the true links in each requirement's top-k, averaged over the three test sets (macro). Colab T4, 3 seeds, 2 epochs, batch 16, in-batch negatives with the contrastive loss; the comparison arm trains on the same number of REAL expert-labelled pairs (iTrust, eTour, SMOS, eANCI). Raw numbers: `data/results/training_pairs_minilm_colab_log.txt`.

| Training data | Embeddings only, recall@5 | @10 | Hybrid (the pipeline's stage 1), @5 | @10 |
|---|---|---|---|---|
| None (untrained MiniLM) | 0.584 | 0.846 | 0.572 | 0.853 |
| Training pairs only | 0.590 (+0.006) | 0.838 (-0.007) | 0.576 (+0.005) | 0.841 (-0.012) |
| Training pairs + hard negatives | 0.583 (-0.001) | 0.821 (-0.025) | 0.587 (+0.015) | 0.855 (+0.001) |
| **Real expert pairs (same number)** | **0.618 (+0.034)** | 0.856 (+0.010) | 0.579 (+0.007) | 0.857 (+0.003) |
| Real + training pairs + hard negatives | 0.612 (+0.028) | 0.834 (-0.012) | 0.596 (+0.025) | 0.858 (+0.005) |

Seed-to-seed spread is about 0.005 to 0.009, so differences under about 0.02 are noise.

Reading:
* **The extra training pairs did not help** (changes between -0.025 and +0.015, inside the noise), with or without hard negatives. Doubling the data (1,000 to 2,271 pairs) did not change this.
* **Real expert pairs give a small gain for the embedding alone** (+0.034 at recall@5) but almost nothing for the hybrid that C4 uses (+0.007 at recall@5, +0.003 at recall@10), because TF-IDF already supplies most of the signal.
* Nothing here moves the pipeline's stage-1 recall materially. The shortlist bottleneck is not a lack of training data for MiniLM; further fine-tuning is not worth the effort. Larger gains would need a stronger retrieval model or a larger top-k.
* Limits: three small test sets (LibEST has only 14 files, so recall@10 is nearly saturated there); one model; training pairs written by LLMs in one style.

### 5.t Decay detection with the meaning-change check

Same 30 ground-truth links, same seed, same harness as 5.z, but the detector now also compares a fingerprint of each text (numbers, negations, true/false, comparison operators) with the fingerprint stored when the link was verified (`semdiff.py`). Raw rows: `data/results/decay_injection_v3.json` (the LLM-only run is `decay_injection_v2.json`).

| Edit | LLM only (5.z) | With the meaning-change check |
|---|---|---|
| Code replaced by unrelated text | 11 / 11 | 11 / 11 |
| Requirement replaced by unrelated text | 11 / 11 | 11 / 11 |
| Code cut to its first sentence | 8 / 11 | 10 / 11 |
| Requirement negated | 5 / 8 | 8 / 8 |
| Numbers in the code changed | 0 / 3 | 3 / 3 |
| Code negated | 0 / 2 | 1 / 2 |
| **All breaking edits** | **35 / 46 = 76.1%** (62% to 86%) | **44 / 46 = 95.7%** (86% to 99%) |
| Harmless edits (controls) | 0 / 22 | 0 / 22 (0% to 15%) |

Why it helps: a changed number or a negation is exactly what a small LLM reading topics misses; the check reports it directly with the change ("numbers changed: [3] -> [300]") and spends no LLM call. Harmless edits (comments, whitespace, "no functional change") are not flagged, and reverting an edit lets the link recover.

Limits to say out loud:
* **The check was designed around these kinds of edits**, so this number is favourable. It catches numbers, negations, boolean flips and operator changes; it does not catch a rename, a changed method call or a logic change that keeps the same numbers and operators. Real edits are more varied than these test edits.
* Still only 11 usable links (19 of 30 were skipped because the LLM rejected them before any edit), 46 related edits, so the interval is wide and the edits are not independent.
* The check needs a fingerprint stored at verification time. Links made before it existed have none and still rely on the LLM alone.
* A harmless edit that changes a number (a version number in code, say) would be flagged for review; that is the price of the check.

## 6. Limits of every result above

* **Fusion weights were chosen after seeing the test results** (w = 0.5 and 1.0 both reported, same direction).
* **Small test sets:** CM-1 22, EBT 41, LibEST 52 requirements; LibEST has 14 code files; CM-1 is a design document, not code.
* **SMOS** has "hub" classes (`User`, `Role`) linked to almost every requirement, which can be memorised in training.
* **Hard negatives** are chosen by stage 1 and may contain true links missing from the gold standard.
* **eTour code is Italian** (identifiers untranslated).
* **Translations** were made by an LLM and not verified by a speaker of Italian.
* **PetClinic** has no human gold: "confirmed" means an 8B LLM said yes, and it makes false positives (for example `vetList.html` for owner pagination). The requirements are made up for the demo.
* **Colab results are replayed, not recomputed:** the Colab model folders and score files were not downloaded. Re-training locally on different hardware gives slightly different numbers.
* **UniXcoder** was tested with plain mean pooling only; its recommended pooling mode was not tried.
* Nothing here was run end to end with the LLM and the graph on the benchmark datasets; the PetClinic comparison replays earlier verdicts.

## 7. Reproducing the results

> **Note (archived code).** The experiment code and bundles behind sections 5.3 to 5.u (the cross-encoder reranker, the learned ranker, the MiniLM fine-tuning on training pairs, the Colab notebooks, and the training bundles in `data/reranker`, `data/codebert_run`, `data/training_pairs`) were moved out of the project into `J26-SE-327-removed-files/c4-experiments-*/` (same relative paths) and are no longer part of the pipeline. The result files in `data/results/` and the numbers in this document were not changed. The commands below that name those files only work after the archive is put back.

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

## 9a. Proposal versus what was built (say this in the viva)

| Proposal said | What C4 actually does | Why |
|---|---|---|
| CodeBERT embeddings | all-MiniLM-L6-v2 + TF-IDF, fused by z-score | Fine-tuned CodeBERT did not generalise (CM-1 MRR 0.21 versus 0.88 for stage 1) and more data did not help it (learning curve, section 5.x). Code-specific embedding models (code-search, UniXcoder) did not beat MiniLM. |
| ChromaDB vector store | in-memory matrices per run | The corpora are small (hundreds of files); a vector database adds nothing here. |
| Fine-tuned model as the verifier | Llama 3.1 8B prompted yes/no with a reason | Honest limits: precision 37.5% on iTrust (target 90%), 52 s per call on a CPU-only server. |
| Decay detection | text-hash change, then LLM re-check; decayed edges kept with a DecayFlag; a decayed link is watched and becomes verified again when its text changes and the check passes | Decay detection 95.7% on 46 edits of 11 links with the meaning-change check (95% interval 86% to 99%); 76.1% with the LLM alone; 69.6% on 9 links earlier (sections 5.z, 5.t). |

The weakest point is stage-1 recall (iTrust top-10 about 42%): the LLM cannot recover a link the shortlist missed.

## 10. Glossary

* **Stage 1:** the fast search that shortlists candidate files for a requirement.
* **Cross-encoder:** a model that reads two texts together and returns one score; slower and more accurate than comparing two separate vectors.
* **Fusion:** adding the standardised (z-score) scores of two methods.
* **P@k / R@k / F1@k:** precision, recall, F1 of the k best candidates. **MRR:** mean of 1/rank of the first correct link.
* **hits@k:** true links in the top k per requirement.
* **Paired bootstrap:** resampling the requirements many times to see how much a difference could vary by chance.
* **Hard negative:** a wrong candidate that the retrieval ranks high.
* **Silver label:** a label from a model (here the LLM) instead of a human.

### 5.s Learned Link Ranker (leave-one-project-out, no LLM)

A gradient-boosting model (`ranker.py`, 16 features: TF-IDF, MiniLM, hybrid scores, ranks, gap to the top candidate, column z-score, file-name word overlap, rare-word overlap, lengths) re-ranks the top-50 hybrid candidates. Trained on 6 projects, tested on the 7th (never seen). Result `data/results/ranker.json`.

| recall@10 | LibEST | CM-1 | EBT | eANCI | SMOS | eTour | iTrust | mean |
|---|---|---|---|---|---|---|---|---|
| fixed hybrid (current) | .96 | .96 | .64 | .23 | .31 | .53 | .42 | **.578** |
| learned (gradient boosting, pre-chosen) | .53 | .93 | .59 | .22 | .30 | .47 | .41 | .494 |

**Negative result:** the learned ranker does not beat the fixed hybrid formula. Post-hoc variants (logistic regression, fewer features; explored on the same test projects, so only indicative) gave mean .49–.55; the best (LR with rank-gap features) was better on the three large projects (eTour .61, iTrust .45, eANCI .25) and worse on the small ones (LibEST .82, EBT .47), still below the hybrid mean. Most important features: gap to the top candidate and hybrid rank, i.e. the model mostly re-learns the hybrid formula; the extra signals add little. Conclusion: with 7 small projects, learning the stage-1 ranking from these features is not worth it; the bottleneck is the information in the text, not the fusion formula.

### 5.r Confidence calibration and abstain mode

`calibration.py` pools the 525 Llama verdicts stored from earlier runs whose requirement has gold links (iTrust 393, eTour 74, CM-1 58; 143 true). Result in `data/results/calibration.json` (5-fold cross-validated isotonic regression).

| Llama says | n | actually correct |
|---|---|---|
| not linked | 338 | 13% |
| linked, confidence 0.8 | 119 | **36%** |
| linked, confidence 0.9 | 67 | **82%** |

Findings: (1) the confidence is badly calibrated: 0.8 is right only about a third of the time, so "kept if >= 0.5" gives precision 53% while "0.9 only" gives 82% (ECE 0.194 raw; isotonic calibration brings it to 0.008, but the LLM emits only three distinct levels, so this mostly re-labels them). (2) Abstain mode therefore has three outcomes: accept (0.9: 82% right), **needs review** (0.8: 36% right, a human decides) and reject (13% of these are actually true: missed links). Recall in the table is the share of the true links *that reached the LLM* that were accepted (38.5% at 0.9), not recall over the whole project. Caveats: verdicts come from several runs and prompts (expert prompt mostly), three datasets, small n.


### 5.q Frozen hold-out test (learned ranker, one run)

Split fixed before any result was read (`data/results/test_projects_frozen.json`, seed 42): train = eTour, EBT, iTrust, LibEST; test = eANCI, SMOS. The model is trained on the train projects and measured once on the test projects (`scripts/ranker_frozen_test.py`, output `data/results/ranker_frozen_test.json`).

| recall | @5 | @10 | @20 |
|---|---|---|---|
| hybrid (current stage 1), macro over eANCI and SMOS | 0.152 | 0.271 | 0.433 |
| learned ranker, same candidates | 0.150 | 0.267 | 0.459 |

No meaningful gain at @5 or @10; a small gain at @20 from two projects only. Caveat: the ranker's features and settings were chosen earlier while looking at leave-one-project-out results that included these two projects, so this is not a clean hold-out. Conclusion: stage 1 recall is limited by the information in the text, not by the fusion formula.


### 5.p Frozen test of the other stage-1 and reranker ideas (one run each, validation chosen first)

Split (fixed before any result was read, `data/results/test_projects_frozen.json`): validation = libest, test = eANCI and SMOS. Each idea was chosen only on libest; eANCI and SMOS were read once, after the choice was written. Baseline = current stage 1 (TF-IDF + MiniLM z-score fusion).

| Idea | What was chosen on libest | Test (eANCI / SMOS), recall@5 / @10 | Verdict |
|---|---|---|---|
| Learned ranker (gradient boosting, 16 features) | trained on eTour, EBT, iTrust, LibEST | 0.150 / 0.267 macro vs hybrid 0.152 / 0.271 | no gain |
| CodeBERT (fine-tuned on eTour, EBT, iTrust; validation libest) | epoch 1 (valid AUC 0.556) | AUC 0.43 (eANCI), 0.55 (SMOS); recall@10 0.16 / 0.10 | worse; overfits after epoch 1 |
| Pre-trained cross-encoder MiniLM fused with hybrid (pool 20) | w = 0.5 (libest recall@5 0.578 → 0.618) | @5 0.127 / 0.197, @10 0.236 / 0.309 vs hybrid 0.115 / 0.189, 0.228 / 0.313 | gain under 0.01; not material |
| BM25 (60-word chunks, best chunk) and BM25 fused with MiniLM / TF-IDF | none beat hybrid on libest (recall@10: hybrid 0.961, BM25 0.838, BM25+MiniLM 0.931, BM25+hybrid 0.961) | not measured (hybrid kept as the tie-break winner) | no gain |

Reading: every stage-1 or reranker idea stayed within about one point of the current hybrid on held-out projects, or lost. The ceiling is the shortlist (recall@10 about 0.23 on eANCI and 0.31 on SMOS). Only a larger candidate pool (top-20 gives 0.41 and 0.45) moves recall, and that costs about twice the LLM calls. The pipeline therefore keeps the current hybrid and TOP_K = 10 unless a larger pool is accepted.

Scripts: `scripts/ranker_frozen_test.py`, `scripts/codebert_stage1.py` (leave-one-out run on iTrust, eTour, CM-1), `scripts/crossencoder_frozen_test.py`, `scripts/bm25_frozen_test.py`. Outputs in `data/results/`.
