# Component 4 – Viva Cheat Sheet (AI Traceability Intelligence Agent)

எழுதியவர்: Thuverakan T. · படிக்கும் முறை: முதல்ல பகுதி 0 + 12 (எண்கள்) மனப்பாடம்; மீதி கேள்வி வந்தா பார்க்க.

---

## 0. 30-வினாடி அறிமுகம் (இதை மனப்பாடம் பண்ணுங்க)

"மென்பொருள்ல ஒரு **requirement** (என்ன செய்யணும்) எந்த **code file** அதை செய்யுதுன்னு இணைக்கிறது **traceability**. Code மாறும்போது இந்த இணைப்புகள் பொய்யாகிடும் (**decay**). என் component (C4) மூன்று வேலை செய்யுது:
1. Requirement–code இணைப்புகளை தானா **கண்டுபிடிச்சு சரிபார்க்குது**,
2. Code மாறினா எந்த இணைப்பு உடைஞ்சதுன்னு **கண்டுபிடிக்குது**,
3. எல்லாத்தையும் **அளந்து** (precision, recall, decay detection) நேர்மையா காட்டுது.
Pre-trained models-ஐ பயன்படுத்தினேன்; என் பங்களிப்பு அவற்றை சுற்றி வடிவமைச்ச **முறைகளும் அளவீடுகளும்**."

---

## 1. பிரச்சனை, ஏன் முக்கியம்

- Requirement ↔ code இணைப்பு இல்லன்னா: எந்த code எந்த requirement-க்காக என்று தெரியாது; மாற்றம் செய்தா என்ன உடையும் என்று தெரியாது; audit/QA கடினம்.
- கையால் இணைப்பு பராமரிப்பது மெதுவு, விரைவில் பழசாகும் (**traceability decay**).
- **Orphan** = link இல்லாத requirement. **Broken** = link உடைஞ்சது (decayed). **Weak** = குறைந்த confidence.

## 2. System architecture (4 components)

| Component | வேலை | நமக்கு |
|---|---|---|
| C1 Requirement Intelligence | requirements | நாங்க படிக்கிறோம் |
| C2 Repository Intelligence | code, commits | நாங்க படிக்கிறோம் |
| C3 Quality & Testing | tests, evidence | நாங்க **படிக்க மட்டும்** |
| **C4 Traceability (என்னுடையது)** | links, decay, completeness | **நாங்க எழுதுறோம்** |

எல்லாம் ஒரே **USKG** (Unified Software Knowledge Graph, **Neo4j**). **Write-ownership guard:** C4 தன் nodes/edges (`VERIFIED_TRACE`, `DecayFlag`) மட்டும் எழுதும்; மற்றவர்களுடையதை எழுத முடியாது (code-ல தடுக்கப்பட்டிருக்கு). Decay நடந்தா **Redis** `trace_decayed` message C3-க்கு போகும்.

## 3. Pipeline – படிப்படியா

**Link உருவாக்கம்:**
1. **Stage 1 – Retrieval (shortlist):** ஒவ்வொரு requirement-க்கும் அனைத்து code files-ல இருந்து top-k (3–10) தேர்வு.
   - **TF-IDF:** வார்த்தை பொருத்தம் (அரிய வார்த்தை = அதிக எடை). Classical IR; training இல்ல.
   - **MiniLM (all-MiniLM-L6-v2):** sentence embedding; அர்த்த ஒற்றுமை. Pre-trained transformer; fine-tune பண்ணல.
   - **Hybrid:** இரண்டின் scores-ஐ **z-score** (ஒவ்வொரு requirement-க்கும் mean 0, std 1) ஆக்கி கூட்டுறோம். காரணம்: scales வேறு.
   - **Chunking (60 words):** நீளமான file-ஐ துண்டுகளாக்கி, சிறந்த துண்டின் score எடுக்கிறோம். MiniLM முதல் ~256 tokens தான் பார்க்கும்.
   - **Preprocessing:** `import/package`, license comment நீக்கம்; `addPatientRecord` → "add patient record".
2. **Stage 2 – LLM verification (Gemma 2 9B, Ollama; ஆரம்பத்தில் Llama 3.1 8B):** ஒவ்வொரு (requirement, code) pair-க்கும் "இது உண்மையில் இணைப்பா?" என்று கேட்கிறோம்; `is_linked`, `confidence` தரும். Remote CPU server, ~35–50 வினாடி/call.
3. **Evidence prompt (என் புது முறை):** LLM code-ல இருந்து **ஒரு வரியை மேற்கோள்** காட்டணும்; அது file-ல உண்மையிலேயே இருக்கான்னு **நாங்க சரிபார்ப்போம்**; இல்லன்னா link நிராகரிப்பு. இது hallucination-ஐ குறைக்கும்.
4. **எழுதுதல்:** `VERIFIED_TRACE` edge (Neo4j), confidence, text hash, semantic fingerprint.

**Decay கண்டுபிடிப்பு:**
1. **Text hash gate:** code text-ன் hash மாறினா மட்டும் மறுசோதனை (LLM நேரம் சேமிப்பு).
2. **Semantic fingerprint (என் புது முறை, `semdiff.py`):** எண்கள் (number words உட்பட), மறுப்புகள் (not/never), true/false, comparison operators – comments நீக்கிய பிறகு. இவை மாறினா LLM இல்லாமலேயே "Meaning-bearing text changed → Needs review". காரணம்: LLM சிறிய ஆனா முக்கிய மாற்றங்களை (`>= 18` → `>= 21`) தவறவிடும்.
3. **LLM மறுசோதனை:** confidence **0.2-க்கு மேல் இறங்கினா** (**hysteresis**, `DECAY_MIN_DROP=0.2`) decay; சிறு ஏற்ற இறக்கம் ignore.
4. **DecayFlag + `HAS_DECAY`:** வரலாறாக சேமிக்கப்படும் (அழியாது). Code **திரும்பினா** link தானா **மீளும்** (`resolvedAt`).
5. **Requirement மாறினாலும்** (requirement-changed event) அதே வழி.
6. **Redis `trace_decayed`** → C3.

**Completeness:** score = **0.6 × link confidence + 0.4 × C3 evidence coverage**. Evidence coverage = C3 RVC (இருந்தால்) அல்லது validated RVUs/total (evidence execution PASS). **C3 இணைப்பு:** `(Requirement)-[:HAS_RVU]->(RVU)-[:MATCHED_BY]->(ValidationEvidence)` – read-only.

## 4. Metrics – என்ன, எப்படி கணக்கிடுறது

Confusion matrix (யூகிச்ச links vs உண்மையான gold links):
- **TP** சரியான link கண்டது · **FP** தவறான link சொன்னது · **FN** உண்மையான link தவறவிட்டது · **TN** சரியா நிராகரிச்சது.

| Metric | சூத்திரம் | பொருள் |
|---|---|---|
| **Precision** | TP / (TP+FP) | நாம் சொன்ன links-ல எத்தனை சரி ("நம்பகத்தன்மை") |
| **Recall** | TP / (TP+FN) | உண்மையான links-ல எத்தனையை கண்டோம் ("முழுமை") |
| **F1** | 2PR/(P+R) | இரண்டின் சமநிலை |
| **Recall@k / hits@k** | top-k-ல உண்மையான link இருக்கா | Stage 1 shortlist தரம் |
| **MRR** | சரியான link-ன் rank-ன் தலைகீழ் சராசரி | எவ்வளவு மேலே வருது |
| **Decay detection rate** | கண்டுபிடிச்ச உடைவுகள் / ஊசி போட்ட உடைவுகள் | |
| **False decay rate** | மாறாத link-ஐ உடைந்ததுன்னு சொன்னது | |
| **Wilson 95% interval** | விகிதங்களுக்கு நம்பக வரம்பு | சிறிய n-ல நேர்மை |
| **Bootstrap 95% CI** | மாதிரியை மீள்தேர்வு செய்து வரம்பு | F1 போன்றவற்றுக்கு |
| **ECE** | சொன்ன நம்பிக்கைக்கும் உண்மையான சரிக்கும் வித்தியாசம் | Calibration |

**ஏன் Accuracy பயன்படுத்தல?** iTrust-ல 0.8% pairs தான் உண்மையான links. "எல்லாம் தவறு" என்றாலே 99.2% accuracy வரும் – பயனற்றது. அதனால precision/recall/F1.

## 5. ML / AI algorithms – எதெல்லாம் பயன்படுத்தினோம்

| Algorithm | எங்கே | Train பண்ணோமா? |
|---|---|---|
| TF-IDF + cosine | Stage 1 | இல்ல (classical) |
| MiniLM sentence embeddings | Stage 1 | இல்ல (pre-trained); fine-tune முயன்றோம் (பகுதி 7) |
| z-score fusion | Stage 1 | இல்ல (கணித சூத்திரம்) |
| **Gemma 2 9B (LLM)** | Verification | இல்ல; **prompt engineering** மட்டும் |
| Rule-based fingerprint | Decay | இல்ல; என் வடிவமைப்பு |
| Isotonic regression | Calibration | ஆமா (சிறிய, 525 verdicts) |
| Gradient boosting, logistic regression | Learned ranker சோதனை | ஆமா (தோற்றது) |
| Cross-encoder / CodeBERT fine-tune | Reranker சோதனை | ஆமா (தோற்றது) |
| Bootstrap, Wilson | புள்ளியியல் | — |

**நேர்மையா:** production pipeline-ல நாங்க எந்த model-ஐயும் புதுசா train பண்ணல. எங்க பங்களிப்பு: pipeline வடிவமைப்பு, evidence-verification, decay lifecycle, fingerprint, அளவீடு.

## 6. Dashboard (demo-க்கு)

Sidebar: repo switcher + service dots (Neo4j/Redis/LLM). Top bar: Refresh. C4 பக்கங்கள்: **Overview** (completeness வட்டம், Trace links / Health / How it works / Measured results), **Link requirements**, **Code changes** (decay), **Analytics** (Insights, Precision vs recall, Impact analysis), **Evaluate links** (கையால் label), **Traceability Graph**. Links filters: All / Trusted (≥0.85) / **Needs review** / Verified / Broken.

## 7. நாங்க முயற்சிச்சு தோற்றவை (இது பலம் – ஆய்வு ஆழம்)

| முயற்சி | முடிவு | காரணம் |
|---|---|---|
| **CodeBERT fine-tune** | தோல்வி | Training நிலையற்றது; stage 1-ஐ விட நல்லா வரல |
| **MiniLM cross-encoder reranker** | gain இல்ல | Recall தடை shortlist-ல, rerank-ல இல்ல |
| **Learning curve** (1→4 projects) | தட்டை | அதிக data உதவாது |
| **Extra training pairs (30 domains + extra batches)** | gain இல்ல | Real pairs +0.034 emb@5 ஆனா hybrid@5 +0.007 மட்டும் |
| **Hard-negative training** | gain இல்ல | அதே காரணம் |
| **Learned Link Ranker** (gradient boosting, 16 features, leave-one-project-out) | **recall@10: 0.494 vs 0.578 hybrid** (மோசம்) | 7 சிறிய projects; features hybrid-ஐ மீண்டும் கற்கிறது |
| **Query expansion** | gain இல்ல | `data/results/query_expansion_itrust.json` |
| **T-BERT** (traceability-க்கான CodeBERT; பொதுவில் கிடைத்த KIT கோப்பு, பயிற்சி இல்லாமல் கூடுதல் stage-1 signal) | **recall@10: 0.578 → 0.540** (7 projects சராசரி); T-BERT தனியா 0.24; 6/7 projects-ல் குறைவு, 4-ல் இழப்பு bootstrap-ல் உறுதி | அசல் weights Drive link 404; இந்தக் கோப்பு documentation↔code பணிக்கு; பயிற்சி இல்லாத முயற்சி மட்டும் (`data/results/tbert_stage1.json`, `scripts/tbert_stage1_test.ipynb`) |

**ஒரே வாக்கியத்தில்:** "Stage 1 recall தான் தடை; fine-tuning, extra training pairs, learned ranking எதுவும் அதை தீர்க்கல – அளந்து காட்டியிருக்கேன்."

## 8. என் புதுமை (Novelty) – "என்ன புதுசா செஞ்சீங்க?"

1. **Decay lifecycle:** flag வரலாறு + தானா மீளல் + text-hash gate + hysteresis.
2. **Meaning-change fingerprint:** LLM + rule கலப்பு; decay detection **76% → 96%**.
3. **Evidence-grounded verification:** மேற்கோள் சரிபார்ப்பு; precision **58% → 82%** (PetClinic கை-சோதனை, 14/17).
4. **Calibration + Needs-review band:** Llama-ன் "0.8" 36% தான் சரி; "0.9" 82% → மனிதன் பார்க்கும் band.
5. **Operating modes:** precision–recall வளைவு, High-precision mode.
6. **Write-ownership guard + C3 read-only integration.**
7. **Decay-injection harness:** gold links, baseline filtering, intervals – decay-ஐ அளக்கும் முறை.
8. **Self-check (9 சோதனைகள்)**, impact analysis, risk ranking, exports.
9. **நேர்மையான எதிர்மறை ஆய்வுகள்** (பகுதி 7).

## 9. அளந்த முடிவுகள் (எண்கள்)

**Decay detection** (46 ஊசி மாற்றங்கள், gold links):
- LLM மட்டும்: **35/46 = 76.1%** (95% CI 62–86%)
- + fingerprint: **44/46 = 95.7%** (CI 85.5–98.8%); **false decay 0/22**
- கவனம்: 30 gold links-ல 11 தான் பயன்பட்டன; சில மாற்ற வகைகள் நாங்க உருவாக்கினவை.

**Link quality:**
| Dataset / நிலை | Precision | Recall | F1 |
|---|---|---|---|
| iTrust (gold), முழு pipeline | 47% | 15% | — (recomputed on current runs) |
| iTrust, confidence ≥0.9 | **92.3%** (24/26) | 6.0% (24/399) | — |
| CM-1, ≥0.9 | 66.7% (10/15) | — | — |
| eTour, முழு pipeline | 81.5% | 23.7% | 36.7% |
| eTour, Stage 1 மட்டும் | 49.3% | 39.8% | 44.0% |

- **Stage 1 recall (top-10):** iTrust ~42%, eTour ~53%.
- **Calibration** (525 verdicts, 143 உண்மை): "linked 0.9" → 82% சரி; "0.8" → 36%; "not linked" → 13% உண்மையில் links; ECE 0.194 → 0.008.
- **PetClinic கை-சோதனை:** evidence prompt 82% vs standard 58%.
- ⚠ PetClinic labels **AI reviewer** போட்டவை (human இல்ல) – உங்க சொந்த ~10 labels-ஓட ஒப்பிடுங்க.

## 10. நேர்மையான வரம்புகள் (Limitations) – கேட்கும் முன்பே சொல்லுங்க

1. **Recall 15–24%** – 85% இல்ல. காரணம்: shortlist-ல உண்மையான file வராதது + 8B CPU LLM.
2. LLM மெதுவு (~31 வினாடி/call focus mode-உடன்; முன்பு 35–50); remote CPU server. Model-ஐ memory-ல் நிரந்தரமா வைத்தா (OLLAMA_KEEP_ALIVE=-1) முதல் call-ன் 4–5 நிமிட தாமதம் போகும்.
3. Ground-truth datasets-ல dependency graph இல்ல.
4. Decay test பகுதி செயற்கை; 11 gold links.
5. C3 தரவு Neo4j-ல இன்னும் இல்ல; C2 `code_changed` message வடிவம் "assumed"; C1-க்கு decay அறிவிப்பு இல்ல.
6. Labels AI reviewer; சிறிய மாதிரிகள்.
7. UI mobile-ல responsive இல்ல (teammate shell).

**பதில் தந்திரம்:** வரம்பை நீங்களே முதல்ல சொல்லி, "இதை இப்படி அளந்தேன், இதை முயற்சித்தேன்" என்று தொடருங்க.

## 11. எதிர்கால வேலை

- பெரிய/hosted LLM (recall & precision உயர்வு); top-k 10 → 20 (recall ↑, செலவு ↑).
- Integration C1/C2/C3 (live data).
- Embedding snapshot pre-check; explainability report.
- மேலும் human labels.

## 12. மனப்பாடம் செய்ய வேண்டிய எண்கள்

**76% → 96%** decay · **0/22** false decay · **58% → 82%** evidence prompt · **92%** high-precision (iTrust) · **15–24%** recall (iTrust 15%, முந்தைய அளவு 21–24%) · **42% / 53%** stage-1 recall@10 · **36% vs 82%** calibration (0.8 vs 0.9) · **0.6/0.4** completeness · **0.2** hysteresis · **60 words** chunk · **0.85** trusted · **0.494 vs 0.578** learned ranker (LOPO); frozen test: @10 0.267 vs 0.271, @20 0.459 vs 0.433 · **0.8%** iTrust base rate.

## 13. கேள்வி–பதில்

**Q1. நீங்க என்ன புதுசா செஞ்சீங்க? Models-ஐ எடுத்து பயன்படுத்தினீங்களா?**
Models pre-trained தான். என் பங்களிப்பு: (பகுதி 8) decay lifecycle, fingerprint, evidence verification, calibration, அளவீடு. எந்த பகுதி எவ்வளவு உதவியது என்று எண்களோட நிரூபிச்சிருக்கேன்.

**Q2. Gemma 2 9B ஏன்?**
local (data வெளியே போகாது), இலவசம். Llama, Qwen, Gemma-வை 120 labelled pairs-ல (2 test sets) அளந்தேன்: pooled F1 Gemma 0.70, Llama 0.63, Qwen 0.61; focus mode-உடன் Gemma 0.75. வரிசை dataset-ஐப் பொறுத்து மாறியது (n சிறியது) → *(பகுதி 14)*.

**Q3. Recall ஏன் குறைவு?**
LLM சரிபார்க்கும் முன்பே shortlist-ல உண்மையான file இல்ல (top-10: 42–53%). Fine-tuning, extra training pairs, learned ranker, reranker எல்லாம் முயற்சித்து அளந்தேன்; எதுவும் உதவல. Precision-ஐ முன்னுரிமையா வச்சேன்.

**Q4. Precision எப்படி 92% ஆனது?**
Confidence ≥0.9 மட்டும் எடுக்கும் "High-precision mode". விலை: recall 6.0%. இது operating-point தேர்வு, சூழலுக்கேற்ப மாற்றலாம்.

**Q5. Decay 96% நம்பலாமா?**
46 ஊசி மாற்றங்கள், 95% CI 85.5–98.8%, false decay 0/22. வரம்பு: செயற்கை மாற்றங்கள், 11 gold links. Fingerprint "test-க்காக வடிவமைக்கப்பட்டது" என்ற விமர்சனம் வரலாம் – அதனால LLM-only baseline (76%)-ஐயும் காட்டுறேன்.

**Q6. Hash gate ஏன்?**
மாறாத code-க்கு LLM call (40 வினாடி) வீண். Hash மாறினா மட்டும் மறுசோதனை.

**Q7. Hysteresis ஏன்?**
LLM ஒரே pair-க்கு சிறிய அளவு மாறலாம்; 0.2-க்கு மேல் இறங்கினா மட்டும் decay → false alarm குறையும்.

**Q8. Decay history ஏன் அழிக்கல?**
Audit/பகுப்பாய்வுக்கு (எந்த file அடிக்கடி உடையுது); மீண்டா `resolvedAt`.

**Q9. Evidence prompt எப்படி precision உயர்த்துது?**
LLM மேற்கோள் தரணும்; அது code-ல இல்லன்னா நிராகரிப்பு → "நம்பிக்கையா சொல்லி தவறான" links குறையும் (58→82%). வரம்பு: n=17, AI labels.

**Q10. Calibration என்றால்?**
Model "0.8" சொன்னா அது உண்மையில் 80% சரியாக இருக்கணும். இல்ல – 36% தான். அதனால் isotonic regression + "Needs review" band.

**Q11. F1/Precision/Recall ஏன், Accuracy ஏன் இல்ல?**
பகுதி 4 (0.8% base rate).

**Q12. Datasets எவை?**
iTrust, eTour, CM-1, EBT, eANCI, SMOS, LibEST (gold links உள்ள public traceability datasets) + Spring PetClinic (நம் demo repo, labels AI). 

**Q13. Overfitting / data leakage?**
Pre-trained models production-ல; Learned ranker சோதனை leave-one-project-out (பார்க்காத project). Calibration 5-fold cross-validated.

**Q14. C1/C2/C3 எப்படி இணைகிறது?**
ஒரே Neo4j. C4 தன் edges மட்டும் எழுதும் (guard). C3 evidence படிக்கும் (RVU/Evidence). Decay → Redis. இன்னும் "assumed": C2 message வடிவம், C3 property பெயர்கள்.

**Q15. Scalability?**
Stage 1 கணித (வினாடிகள்); LLM தடை. Hash gate + top-k கட்டுப்பாடு + hosted/GPU LLM மூலம் அளவிடலாம்.

**Q16. தனியுரிமை?**
LLM (Gemma) local/remote சொந்த server; code வெளி API-க்கு போகாது.

**Q17. Hallucination?**
Evidence மேற்கோள் சரிபார்ப்பு + Needs-review band.

**Q18. இது முழு தானியங்கியா?**
இல்ல; high-confidence தானா, இடைப்பட்டது மனிதன் (human-in-the-loop).

**Q19. Commercial tools (Jira, DOORS) vs?**
அவை கையால் இணைப்பு; நாங்க தானா கண்டுபிடிப்பு + decay + அளவீடு. (இங்க குறிப்பிட்ட tool claims தவிர்க்கவும்.)

**Q20. உங்க பெரிய தோல்வி என்ன?**
Recall. அதை மறைக்கவில்லை; ஏன் என்று அளந்து காட்டினேன்.

## 14. LLM ஒப்பீடு

| Model | Precision | Recall | F1 (95% CI) | வினாடி/call |
|---|---|---|---|---|
| Llama 3.1 8B | 61.9% | 43.3% | 0.51 (0.32–0.66) | 30.8 |
| Qwen 2.5 Coder 7B | **81.8%** | 30.0% | 0.44 (0.24–0.62) | **29.1** |
| Gemma 2 9B (4 server errors, 56 pairs scored) | 52.9% | **62.1%** | **0.57** (0.42–0.70) | 43.9 |

**வாசிப்பு (நேர்மையா):** F1 intervals மூன்றும் பெருமளவு மேற்பொருந்துது → **மூன்றுக்கும் இடையே புள்ளியியல் ரீதியா வேறுபாடு நிரூபிக்கப்படல** (n=60). Qwen கண்டிப்பானது (precision அதிகம், recall குறைவு); Gemma தாராளம் (recall அதிகம், precision குறைவு, மெதுவு, server errors); Llama நடுவில், errors இல்ல. 56 பொதுவான pairs-ல மூன்றின் சரியான விகிதமும் 52–59% (Llama 31, Qwen 33, Gemma 29) – சமநிலையான கடினமான மாதிரியில் மூன்றும் தற்செயலை விட சற்று மேல் மட்டுமே. Gold labels-ல சத்தம் இருக்கலாம் (iTrust/eTour).
**2-வது test set (PetClinic, 60 pairs; labels நானே கையால் எழுதியவை) + இணைந்த 120 pairs:**

| Model | PetClinic P / R / F1 | 120 pairs pooled P / R / F1 | வினாடி/call |
|---|---|---|---|
| Llama 3.1 8B | 0.90 / 0.63 / 0.75 | 0.76 / 0.53 / 0.63 | 34 |
| Qwen 2.5 Coder 7B | 1.00 / 0.60 / 0.75 | 0.93 / 0.45 / 0.61 | 34 |
| Gemma 2 9B | 0.92 / 0.80 / 0.86 | 0.70 / 0.70 / 0.70 | 51 |
| **Gemma + focus mode + குறுகிய reason** | — | **0.70 / 0.82 / 0.75** | **31** |

**தேர்வு (இப்போதைய):** Gemma 2 9B + focus mode (`LLM_FOCUS_CHARS=1500`, `LLM_SHORT_REASONING=1`). காரணம்: pooled F1 அதிகம், வேகம் ~1.6× அதிகம். **எச்சரிக்கை:** (1) வரிசை dataset-ஐப் பொறுத்து மாறியது, (2) focus mode-ல recall உயர்வின் ஒரு பகுதி காலி பதில்கள் 5→1 ஆனதால், (3) prompt/confidence/decay அளவீடுகள் Llama-வுடன் எடுத்தவை. DeepSeek (hosted) PetClinic-ல் F1 0.95, ஆனா code வெளியே போகும். Precision-முன்னுரிமை mode-க்கு Qwen ஒரு மாற்று.

சோதனை: iTrust/eTour/CM-1-ல இருந்து 60 pairs (30 உண்மை, 30 shortlist-ல வந்த தவறு), evidence prompt, temperature 0, context 8192. கட்டளை (அட்டவணை அச்சிட): `python scripts/show_llm_results.py`; மீண்டும் ஓட்ட: `python scripts/llm_compare_projects.py petclinic`. முடிவு: `data/results/llm_compare.json`.

## 15. Demo மீள்பார்வை (8–10 நிமிடம்)

Overview → Link requirements (முன்னாடி செய்ததை காட்டுங்க) → Trace links (Needs review filter) → Code changes (decay; Redis tab-ஓட) → Analytics (Precision vs recall, Impact) → Evaluate links → Measured results.
முன்னாடி: Neo4j, Redis, API, web இயக்கம்; decay run முன்கூட்டியே; ஏதாவது உடைந்தா "Measured results" tab.

## 16. செய்ய வேண்டிய மீதி (உங்க பக்கம்)

- [ ] Evaluate links-ல ~10 links கையால் label.
- [ ] Slides: CodeBERT/ChromaDB → TF-IDF + MiniLM + Gemma; புது எண்கள்.
- [ ] LLM ஒப்பீடு முடிவை பகுதி 14-ல நிரப்பு.
- [ ] C3 holder-கிட்ட assumptions உறுதி செய்.
- [ ] Demo rehearsal (கடிகாரம் வச்சு).
