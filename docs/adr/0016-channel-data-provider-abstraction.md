# 0016: Channel Data Provider Abstraction (Real YouTube vs Deterministic Sample Channel)

*Status: Historical Context (Active agents consuming provider: Alex, Leo)*

## Context
Croviq's agents (Alex, Maya, Nina) analyze historical channel performance, retention curves, click-through rates, and audience trends to guide editing and packaging decisions. Hackathon judges and developers exploring the platform may not possess a mature YouTube channel with thousands of historical videos. Hardcoding fake numbers into UI components produces untestable, brittle demo code and prevents downstream agents from exercising real statistical analysis.

## Decision
We implement a clean provider boundary interface (`ChannelDataProvider`):

```text
ChannelDataProvider (Interface)
        │
        ├── YouTubeChannelDataProvider
        │      -> Real Google YouTube Data API & Analytics API
        │      -> Incremental OAuth authorization
        │
        └── SampleChannelDataProvider
               -> Deterministic synthetic dataset
               -> ~50,000 subscribers, 100 historical videos, ~18 months
               -> Mathematical coherence across duration, views, CTR, retention
               -> Deliberate discoverable retention patterns for Alex
```

1. **Identical Downstream Contracts**: All domain models, agent prompts, and analytics routines consume identical canonical Pydantic schemas regardless of the active provider.
2. **Deterministic Seed**: The sample dataset uses a deterministic version/seed (`ai-engineering-v1`) to guarantee 100% reproducible demo and test runs.
3. **Transparent Disclosure**: The application UI and README clearly disclose the sample mode ("Sample AI engineering channel loaded") without misleading judges or pretending synthetic data belongs to a real creator.

## Consequences
- Enables realistic, deep statistical analysis and agent reasoning during hackathon judging without requiring mature personal YouTube channels.
- Provides a clean cutover to real YouTube API execution when creator channels are connected.
- Prevents UI component hardcoding and ensures 100% testable domain logic.
