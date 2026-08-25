# 0001: Deterministic Workflow Engine with Coordinator Director Agent

## Context
Croviq requires multi-step creator workflows (video understanding, timeline editing, packaging, QA verification, external publishing) that must be reliable, auditable, and resilient to hallucinations, while still adapting intelligently to diverse video content and creative intent. Unconstrained LLM agents risk skipping required checks, hallucinating workflow states, or violating external safety gates (e.g. publishing without human approval). Pure hardcoded orchestration lacks the flexibility to reason over unstructured footage and contextual creator preferences.

## Decision
We separate the execution system into two distinct layers:
1. **Deterministic Workflow Engine**: An immutable, code-driven state machine that owns job states, validates DAG dependency order, enforces retry limits, manages idempotency keys, records structured audit logs, and strictly locks human-approval gates before external side effects.
2. **Director Agent**: A top-level coordinator agent that interprets the creator's creative objective, configures structured parameters for downstream department jobs, evaluates intermediate artifact quality, and routes context between specialized agents within the engine's strict legality boundaries.

The Director Agent cannot bypass engine constraints, create unauthorized state transitions, or trigger side effects without engine validation.

## Consequences
- Guarantees fail-safe execution, verifiable audit trails, and strict human approval enforcement.
- Department agents and tools operate within bounded, type-safe inputs and outputs.
- Adds an explicit contract layer between agent reasoning and engine state mutations.
