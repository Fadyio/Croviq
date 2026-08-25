# 0006: Creator Memory: Evidence-Backed Structured Lessons

## Context
Croviq's Data Science / Growth department evaluates post-release YouTube metrics (retention curves, CTR, traffic sources, watch time) to improve subsequent Missions. If memory is stored merely as unstructured conversational summaries, it quickly degrades into vague, untestable AI advice ("make videos more engaging"). Conversely, storing only raw numbers forces every subsequent agent run to perform complex retrospective data analysis from scratch.

## Decision
We separate performance memory into two distinct layers:
1. **Raw Metrics as Immutable Evidence**: Historical performance snapshots (e.g. 30-second retention percentage, CTR baseline comparisons, traffic breakdown) are stored as verifiable evidence records.
2. **Structured Lessons as Active Memory**: The Data Science agent distills evidence into structured, falsifiable `Lesson` records stored at the Workspace level. Each Lesson schema includes:
   - `directive`: A clear, actionable production instruction (e.g. "Show the final working demo within the first 12 seconds").
   - `target_department`: The specific department responsible for applying the lesson (`Director`, `Editor`, `Packaging`, or `Research`).
   - `evidence_summary`: Concrete quantitative metrics grounding the rule (e.g. "30s retention = 71% vs channel baseline = 56%").
   - `confidence`: A statistical or heuristic confidence score (0.0 to 1.0).
   - `status`: Lifecycle state (`ACTIVE`, `TESTING`, `RETIRED`).

When a new Run starts, the Director queries active Lessons matching target departments and injects them as structured constraints.

## Consequences
- Every creative constraint is grounded in demonstrable historical evidence.
- Lessons are modular, queryable by department, and can be activated or retired based on ongoing performance.
- Eliminates context drift and vague advisory summaries.
