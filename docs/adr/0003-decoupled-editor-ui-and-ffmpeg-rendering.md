# 0003: Decoupled Editor UI (Twick) and Cloud Run FFmpeg Rendering

## Context
Croviq requires an interactive, professional multi-track timeline UI in the browser where creators can watch agents edit footage in real time. The Twick SDK provides a rich React-based timeline, canvas, and synchronized player under the Sustainable Use License v1.0 (which permits development/self-hosting, but requires a commercial license for hosted commercial SaaS). Additionally, Twick's built-in cloud exporter is tailored for AWS infrastructure, whereas Croviq's deployment target is Google Cloud (Cloud Run, Vertex AI, Cloud Storage).

## Decision
1. **Frontend Timeline**: We use the Twick React SDK strictly as a client-side presentation and interaction layer for displaying tracks, playback, cut intervals, and visual agent annotations. For the post-hackathon commercial SaaS launch, a commercial license will be acquired for Twick or the UI layer will be abstracted.
2. **Backend Rendering Engine**: We implement media rendering deterministically using FFmpeg running on Google Cloud Run, reading source video from Cloud Storage and writing rendered masters back to Cloud Storage.
3. **Decoupling via EDL (Edit Decision List)**: The contract between the Editor Agent, the frontend timeline UI, and the backend FFmpeg renderer is a standard, typed JSON Edit Decision List (EDL). The backend has zero runtime dependency on Twick SDK code or external AWS services.

## Consequences
- Preserves full portability and Google Cloud native execution on Cloud Run.
- Mitigates commercial licensing lock-in by maintaining an open, vendor-neutral EDL contract between agent reasoning and video rendering.
- Enables creators to inspect and scrub edits in the browser before triggering Cloud Run render jobs.
