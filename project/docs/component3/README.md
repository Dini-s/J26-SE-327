# ASPIRE Component 3

## Quality & Testing Intelligence

Component 3 implements requirement-centric QA evidence and test adequacy intelligence.

## Research Pipeline

The processing chain is:

Acceptance Criteria
→ Requirement Validation Units
→ Expected QA Evidence Profiles
→ Heterogeneous QA Evidence
→ Normalized ValidationEvidence
→ Candidate Evidence Retrieval
→ Type-Aware Adequacy
→ Execution-Aware Validation
→ RVC / Experimental RVES
→ QA Gaps
→ Grounded Recommendations
→ Targeted Revalidation
→ USKG / API / Dashboard

## Current Experimental Corpus

The current standalone Component 3 corpus contains:

- 30 requirements
- 90 acceptance criteria
- 91 RVUs
- automated Spring PetClinic tests
- Maven Surefire execution results
- structured manual QA evidence
- controlled performance evidence
- controlled functional and non-functional revalidation cases

Controlled research fixtures are explicitly labelled and must never be presented as genuine production observations.

## Core Principle

Component 3 keeps three concepts independent:

1. Evidence relevance
2. Evidence adequacy
3. Execution success

A semantically related test is not automatically adequate.

A passing test is not automatically adequate.

Adequacy must be established against the Expected QA Evidence Profile for the exact RVU.

## RVC

Requirement Validation Coverage is calculated as:

RVC = Adequate RVUs / Total RVUs × 100

Execution-confirmed coverage is reported separately.

## RVES

RVES remains experimental.

The current transparent baseline uses:

- R: semantic relevance
- A: adequacy strength
- C: completeness
- E: execution strength

with equal baseline weights.

RVES must remain labelled Experimental until expert-rating correlation, sensitivity and ablation evaluation is complete.

## Component Ownership

C3 owns:

- RVUs
- Expected Evidence Profiles
- ValidationEvidence
- adequacy assessments
- validation results
- RVC/RVES
- QA gaps
- recommendations
- evidence revalidation decisions

C3 does not own:

- C1 requirement anchors
- C2 repository intelligence
- C4 Requirement/RVU-to-code verified trace relationships
- C4 decay detection

## Main Commands

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```
