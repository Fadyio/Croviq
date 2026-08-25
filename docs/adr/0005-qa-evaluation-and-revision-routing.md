# 0005: QA Evaluation States and Bounded Revision Routing

## Context
Quality Assurance (QA) is responsible for verifying factual accuracy, metadata consistency, timestamp alignment, and caption integrity across upstream artifacts produced by the Editor and Packaging departments. If QA were permitted to silently rewrite artifacts directly, it would violate separation of concerns and bypass auditability. Conversely, halting the entire workflow on every minor flaw forces unnecessary human intervention.

## Decision
1. **Independent Verification**: QA is an evaluator, not a writer. It generates an immutable `QA Report` assessing upstream artifacts against objective verification criteria.
2. **Four Canonical Evaluation States**:
   - `PASS`: All checks satisfy quality thresholds. The Workflow Engine transitions the Run to the `Approval Gate`.
   - `REVISE`: Actionable, high-confidence defect detected (e.g. mismatched timestamp in chapters, broken title formatting). The Workflow Engine routes structured feedback back to the originating department (Editor or Packaging) for a bounded auto-revision (strictly capped at 1 retry per job).
   - `CREATOR_REQUIRED`: Ambiguous, unverified, or low-confidence issue detected (e.g. disputed factual claim, potential copyright/brand sensitivity). The Run proceeds to the `Approval Gate` with explicit warning flags requiring manual creator resolution.
   - `FAIL`: Severe irrecoverable defect (e.g. corrupted media, complete policy violation). The Run is terminated.
3. **Loop Bounding**: If a department fails QA after its single allowed auto-revision attempt, the engine automatically escalates the state to `CREATOR_REQUIRED` to prevent infinite loops.

## Consequences
- Preserves distinct departmental accountability and a clear audit trail.
- Prevents infinite agent revision loops while automating self-correction of trivial errors.
- Ensures the creator is explicitly notified of any unverified claims before publication.
