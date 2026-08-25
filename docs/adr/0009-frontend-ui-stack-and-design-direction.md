# 0009: Frontend UI Stack, Design System, and Motion Discipline

## Context
Video creators expect dense, responsive, high-precision creative tooling (reminiscent of Premiere Pro or DaVinci Resolve) combined with the modern speed and polish of tools like Linear and Raycast. Proliferation of redundant animation libraries, unstructured styling, or generic SaaS dashboard templates undermines product coherence and performance.

## Decision
1. **Core UI Technology Stack**:
   - **Foundation**: React + Vite + TypeScript
   - **Styling**: Tailwind CSS with CSS variables for dark/light creative themes
   - **Components & Primitives**: shadcn/ui + Radix UI
   - **Iconography**: Lucide React (strictly one consistent icon set)
   - **Animation Engine**: Motion for React (single authorized animation library; no GSAP)
   - **Video Timeline & Canvas**: Twick React SDK
   - **Audio Waveform**: WaveSurfer.js
   - **State & Data Fetching**: TanStack Query (server state / caching) + Zustand (client timeline/editor state)
   - **Interactive Overlays**: Sonner (toasts), Vaul (drawers/sheets), cmdk (command palette `⌘K`)
2. **Selective Specialized Additions**:
   - `@xyflow/react` for workflow DAG visualization if needed.
   - `Recharts` or `Visx` for Data Science analytics charts.
   - `Rive` for custom branded system loading states.
3. **Prohibited Dependencies**:
   - Three.js / React Three Fiber (no 3D canvas distraction).
   - GSAP (avoid dual animation runtimes).
   - Multiple icon packs or ad-hoc animation packages.
4. **Design & Motion Direction**:
   - Dense, professional creative workspace layout: high information density, dark-mode first, zero "AI gradient soup" or generic SaaS cards.
   - Purposeful Motion: Animations must represent tangible system events (timeline segment closing, transcript cut strike-through, playhead jumping, QA state transitions, approval lock releasing).
   - Strict `prefers-reduced-motion` compliance.

## Consequences
- Single, predictable UI architecture across the entire application.
- Fast compile times and small client bundles with Vite.
- Coherent, professional creative software aesthetic that builds user trust.
