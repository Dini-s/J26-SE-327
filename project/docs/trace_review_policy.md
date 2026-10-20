# Trace approval and review

Positive AI verdicts at confidence >= 0.85 are automatically approved. Positive
verdicts at 0.50–0.84 are stored as pending candidates and require human approval.
Lower-confidence and negative verdicts are not approved. These are workflow
thresholds, not a claim that confidence equals measured correctness.

USKG keeps the relationship for auditability with `status`:

- `verified`: approved, contributes to completeness and coverage.
- `pending_review`: awaiting a decision; contributes no coverage.
- `rejected`: rejected by a person or recheck; contributes no coverage.
- `decayed`: a previously approved connection broke after a source change.

Human review writes directly to the same Neo4j relationship: `correct` approves,
`wrong` rejects, `unsure` leaves pending. AI confidence is never changed by review.
Graph views, approved counts and completeness all use this status. Consumers of
`VERIFIED_TRACE` must filter `status = 'verified'` for approved connections.

Decisions include a hash of both inspected texts. A stale review fails and the
user must reload. Rechecking unchanged text preserves the human decision. New
text invalidates the old decision and is routed through verification again.
Exact reverts restore the last approved version unless that version has a human
rejection. Resolved decay flags remain historical records.

Legacy low-confidence automatic links enter the review queue at startup. Legacy
file reviews are imported only if their timestamp is newer than the last check
and the current texts still match the checked hash. Original files remain intact.
