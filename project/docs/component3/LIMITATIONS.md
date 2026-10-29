# Component 3: Limitations and Research Boundaries

Read alongside the [operating guide](README.md). These boundaries apply to demonstrations, reports, and integration claims.

## Dataset representativeness

Spring PetClinic supplies the primary integration corpus, but not a complete industrial SRS. Upstream sources and stored execution reports are combined with controlled requirements, manual evidence, performance fixtures, and change cases. Retain controlled-source labels; do not describe the corpus as entirely production-derived.

Corpus counts and coverage describe a development snapshot. They depend on requirements, acceptance criteria, evidence, retrieval settings, and code revision.

## Execution provenance

Relevance, adequacy, and execution success are independent. A related test is a candidate; adequate evidence is not proof of execution; controlled or synthetic PASS is not observed PASS. Blocked, skipped, unexecuted, and failed execution do not establish successful validation.

Aggregate recorded-result counts may contain controlled outcomes. Inspect underlying provenance before presenting counts as observed execution. Controlled performance evidence is not genuine production JMeter or k6 execution.

Stored upstream reports describe the recorded run, not fresh execution against all later revisions. Two PostgresIntegrationTests source methods in the documented corpus lack matching Surefire execution results and remain unresolved.

## Automated extraction and adequacy

RVUs and Expected Evidence Profiles approximate acceptance intent. Compound behaviors and review flags need human inspection. Extracting checks cannot establish specification completeness or remove ambiguity.

Semantic retrieval can miss relevant evidence or rank unsuitable artifacts highly. Similar wording does not establish matching preconditions, assertions, workload, duration, metric, percentile, or threshold.

Automated adequacy is strongest for functional and measurable performance evidence in supported formats. Reliability, scalability, security, accessibility, maintainability, availability, and usability need specialist evidence or human review where unsupported. A functional security behavior does not establish comprehensive security assurance. Unsupported checks remain explicitly not assessed.

## Metric interpretation

RVC is adequate-check coverage, not code coverage, product correctness, or defect detection rate. Its denominator and RVU granularity affect the result.

Execution-confirmed coverage uses supported checks and must be read with not-assessed counts. Full requirement validation requires every check to satisfy evidence and qualifying execution conditions.

RVES is an experimental equal-weight composite, not a calibrated confidence probability or release-readiness measure. Expert-rating correlation, sensitivity analysis, and ablation remain necessary.

## Empirical evaluation

The saved evaluation snapshot inspected for this documentation reports INCOMPLETE readiness and no labels in required sections. Evaluation scripts and metric fields do not establish completed independent evaluation.

Reference labels must be independent of the implementation. Record reviewer identity, dates, rationale, disagreements, and adjudication where expert review is required. Do not derive gold labels from the evaluated system's own output.

Passing tests or non-strict release checks does not establish empirical accuracy or generalization. Report numeric evaluation claims only with populated reference labels, provenance, configuration, and reproducible results.

## Revalidation and integration

Controlled changes demonstrate KEEP, UPDATE, REPLACE, and CREATE decisions from supplied contexts. They do not prove live C4 change detection, automatic test repair, successful reruns, or correct behavior after code changes.

Contract endpoints validate payload shape; they do not establish live orchestration across components. C3 evidence links do not replace C4-owned verified requirement/RVU-to-code trace relationships. USKG export does not establish deployment or synchronization of a shared production graph.

## Reproducibility and deployment

Source pins and manifests help identify runs. Dependency ranges, model downloads, caches, hardware, and code changes can affect reproduction. Preserve inputs, settings, manifests, and outputs with reported results.

Analysis commands write generated artifacts. Associate outputs with the relevant source revision and configuration. Local server startup does not establish production security, capacity, availability, or operational readiness.

Defects4J remains an external-validity extension and does not justify current C3 outputs. No Defects4J result is claimed without an executed, recorded experiment.

## Next validation work

1. Complete independent gold labels and adjudicate disagreements.
2. Evaluate retrieval, adequacy, aggregation, and revalidation against those labels.
3. Test sensitivity to RVU granularity, retrieval thresholds, and RVES weights.
4. Add provenance-backed observed performance runs.
5. Validate live cross-component integrations and change contexts.
6. Replicate on additional repositories and requirement sets.

## Appropriate demonstration claim

“C3 demonstrates requirement-centric evidence assessment, execution-aware validation reporting, and targeted evidence revalidation on a mixed upstream and controlled research corpus.”

This supports a prototype demonstration, not a claim of production certification, completed empirical evaluation, or verified live integration.
