# 0002: Human-in-the-Loop Approval Gate for External Side Effects

## Context
Croviq produces public-facing media assets (videos, thumbnails, titles, metadata) destined for platforms like YouTube. LLM-driven pipelines can hallucinate claims, produce off-brand cuts, or generate inappropriate metadata. Fully autonomous publishing directly to public channels without human verification presents severe brand risk, terms-of-service exposure, and irreversible external side effects.

## Decision
1. **Publisher is a Deterministic Engine Service**, not an autonomous agent or department. It has no authority to alter creative decisions or bypass rules.
2. **Mandatory Approval Gate**: The Workflow Engine strictly prohibits the Publisher service from executing external mutations (e.g. YouTube uploads, metadata publishing) until:
   - QA evaluates all upstream artifacts and outputs a `PASS` status.
   - The creator explicitly grants human approval on the exact release package.
   - An idempotency key verifies the action has not already executed.
3. For automated testing and initial deployments, publication defaults to `private` status on YouTube.

## Consequences
- Prevents accidental, hallucinated, or unauthorized external broadcasts.
- Establishes a verifiable chain of custody (Director → Editor → Packaging → QA → Human Approval → Publisher).
- Autonomous runs pause deterministically at the approval gate, waiting for user interaction.
