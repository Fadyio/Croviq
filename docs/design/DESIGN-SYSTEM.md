# Croviq Design System Specification

**Design Philosophy**: Professional Creative Media Workstation.
Combines the information density of **Premiere Pro / DaVinci Resolve**, the layout precision of **Linear**, and the interaction polish of **Raycast**. Eliminates generic SaaS cards, empty hero areas, AI gradient soup, and developer status dashboards.

> **The Golden Rule**: The media must always be the most colorful element on screen. The application chrome and UI surfaces should disappear around it, ensuring zero visual contamination or distraction during video editing and review.

---

## 1. Brand Identity & Logo Usage

All logo files are located in `brandkit/`.

| Lockup | Asset File | Usage Rule |
|---|---|---|
| **Horizontal (Primary)** | `brandkit/croviq-logo-horizontal.svg` | Main application top-bar and navigation. Primary brand identity. |
| **Emblem (Symbol)** | `brandkit/croviq-symbol.svg` / `brandkit/croviq-symbol-on-graphite.svg` | Collapsed navigation, favicon, browser tabs, agent chips, and small badges. |
| **Stacked (Secondary)** | `brandkit/croviq-logo-stacked.svg` | Clean sign-in screen and centered presentation contexts. |

**Clearspace & Scaling**:
- Minimum horizontal logo height: `24px` in UI navigation.
- Minimum emblem size: `16px` for favicon; `28px` for avatar chips.
- Clearspace: Minimum padding equal to the height of the lowercase 'o' around all lockups.

---

## 2. Color System

### 2.1 Brand Palette (Derived from Emblem & Wordmark)

The 19-facet emblem contains a spectrum from warm amber to deep violet:
- **Warm Facets**: `#FF9F1C`, `#FFBD16`, `#FFB514`, `#FFD05A`, `#FF6B3D`, `#FF7A43`, `#F51B35`, `#F52B49`
- **Cool / Core Facets**: `#20A7D8`, `#18AEEA`, `#078ED8`, `#0798DE`, `#0D86D1`, `#14A9DF`, `#4B72D0`, `#2355C5` (Brand Primary), `#1452C5`
- **Violet Facets**: `#6C2BBF`, `#B527B7`
- **Wordmark Neutral**: `#22242B` (Graphite Black)

### 2.2 Application Neutral Graphite Theme (Creative Workspace)

High-density neutral graphite surfaces engineered for professional video editing (85–90% neutral grays so UI recedes):

| Token | HEX | Application |
|---|---|---|
| `bg-background` | `#101214` | Neutral deep graphite viewport base |
| `bg-surface-1` | `#16191C` | Primary sidebars, transcript bins, agent panels |
| `bg-surface-2` | `#1C2024` | Timeline track containers, video player frame, active panels |
| `bg-surface-3` | `#23282D` | Input fields, active toolbar buttons, hover layer |
| `bg-elevated` | `#2A3036` | Context menus, dropdowns, popovers, modals |
| `border-subtle` | `#2D3339` | Standard 1px panel boundaries and track dividers |
| `border-strong` | `#3B434B` | Focused elements, active track selection, timeline playhead line |

### 2.3 Typography Colors

| Token | HEX | Usage |
|---|---|---|
| `text-primary` | `#F2F4F5` | High-contrast headers, active transcript text, labels |
| `text-secondary` | `#B0B7BE` | Metadata, track names, secondary descriptions |
| `text-muted` | `#78828C` | Timestamps, timecodes, hotkey badges, disabled actions |

### 2.4 Primary Interaction & Semantic Colors

| Role | Token | HEX | Application |
|---|---|---|---|
| **Primary** | `primary` | `#2355C5` | Selected states, primary buttons, active playhead |
| **Success** | `success` | `#3E8063` | Master render complete, QA `PASS`, approved batch |
| **Warning** | `warning` | `#A77A32` | Suggested edit review, QA `REVISE` |
| **Danger** | `danger` | `#B85454` | Removed segment, QA `FAIL` |
| **Info / Processing** | `info` | `#5279B8` | Active agent processing, current working segment |

### 2.5 Editor Semantic States

| State | HEX | Transcript Treatment | Timeline Treatment |
|---|---|---|---|
| **Removed** | `#B85454` | Muted red strikethrough (`#B85454` at 15% bg) | Muted red cut overlay animating closed |
| **Suggested** | `#A77A32` | Muted amber underline (`#A77A32` at 15% bg) | Muted amber bracket overlay |
| **Preserved** | `#4F7F65` | Muted sage/green tint (`#4F7F65` at 15% bg) | Muted green marker outline |
| **Processing** | `#5279B8` | Active blue pulse highlight | Playhead pulse / active bracket |

---

## 3. Typography Scale & Fonts

- **Primary UI Font**: `Inter`, `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Monospace Technical Font**: `JetBrains Mono`, `ui-monospace, "SF Mono", monospace` (Timestamps, timecodes, token metrics)
- **Type Scale**:
  - `text-xs`: `11px` / `14px` (Timecode labels, badges, hotkeys)
  - `text-sm`: `13px` / `18px` (Standard dense UI, transcript, table rows)
  - `text-base`: `14px` / `20px` (Primary controls, property labels)
  - `text-md`: `16px` / `24px` (Panel headers, agent names)
  - `text-lg`: `18px` / `28px` (Modal headers, production titles)
  - `text-xl`: `22px` / `30px` (Page headings)

---

## 4. Spacing, Radii & Elevation

- **Spacing Scale (4px Base)**: `4px` (`space-1`), `8px` (`space-2`), `12px` (`space-3`), `16px` (`space-4`), `20px` (`space-5`), `24px` (`space-6`), `32px` (`space-8`).
- **Border Radii**:
  - `radius-sm`: `4px` (Badges, timecode chips, track segments)
  - `radius-md`: `6px` (Buttons, inputs, dropdown items, toolbars)
  - `radius-lg`: `8px` (Panels, video player canvas, modal dialogs)
  - `radius-full`: `9999px` (Avatars, status dots)
  *(Strictly avoid bubbly >12px radii on rectangular editing surfaces).*
- **Borders & Elevation**:
  - Crisp `1px solid #2D3339` everywhere. Strong borders use `#3B434B`.
  - Shadows: subtle dark elevation (`shadow-sm`, `shadow-md`, `shadow-lg`).

---

## 5. Screen Layouts

### 5.1 Sign-In Page
Minimal and professional:
- Croviq logo
- Sign in to Croviq
- Email & Password fields
- [ Sign in ] button
- Subtle Motion transitions for errors and entrance. No marketing fluff, no pipeline diagrams.

### 5.2 Production Home (First-Use & Channel Selection)
Clear, uncluttered creator entry point:
- "What are we making?"
- **Connect YouTube Channel** (Primary action for real channels)
- **Use Sample Channel** (Deterministic sample AI engineering channel)
- Drag-and-drop raw video dropzone (`[ Upload video ]`)
- Recent productions list
- *Strictly removed from creator UI*: Workspace IDs, Owner User IDs, Git SHAs, API health banners, and milestone labels.

### 5.3 Hero Editor Workspace (80 / 20 Layout Split)

```text
┌─────────────────────────────────────────────────────────────┬───────────────────────────┐
│                                                             │ Maya · Director           │
│                                                             │ [Avatar Chip]             │
│                      VIDEO PLAYER                           │ "The opening is too slow. │
│                                                             │ Handing off to Leo..."    │
│                                                             ├───────────────────────────┤
│                                                             │ SYNCHRONIZED TRANSCRIPT   │
│                                                             │                           │
│                                                             │ 00:04 ~~Um, so basically~~│
│                                                             │ 00:12 In this video, we'll│
│                                                             │       build a custom CI/CD│
│                                                             │ 00:28 ~~[repeated take]~~ │
├─────────────────────────────────────────────────────────────┤                           │
│ TWICK MULTI-TRACK TIMELINE                                  │                           │
│ V1 [=============================] [======================] │                           │
│ A1 [~~~~~~~~~~~~~~~~~~~~~~~~~~~~~] [~~~~~~~~~~~~~~~~~~~~~~] │                           │
│ TX [Intro] [Removed Filler] [Screen Demo]                   │                           │
└─────────────────────────────────────────────────────────────┴───────────────────────────┘
```

- **Left ~80%**:
  - Video Player Canvas with synchronized playback.
  - Twick multi-track timeline (video V1, audio A1, annotations TX, cut markers).
  - Playhead movement reflecting live agent progress.
- **Right ~20%**:
  - **Top**: Active agent card (Avatar, Name, Role, concise action summary & reasoning).
  - **Bottom**: Synchronized transcript with real-time strike-through, review amber, preserved green, and active processing blue.

---

## 6. Visible Production Team Identities

| Agent | Name | Role | Canonical Icon | Responsibility |
|---|---|---|---|---|
| **Director** | Maya | Senior Production Lead | `Clapperboard` | Editorial strategy, memory reading, batch review, approval |
| **Editor** | Leo | Video Editor | `Scissors` | Video editing, false-start & filler removal, pacing, Short extraction |
| **Data Scientist** | Alex | Statistical Intelligence | `TrendingUp` | Retention change-points, baseline analysis, memory lessons |
| **Packaging** | Nina | Packaging & Presentation | `Sparkles` | Titles, descriptions, chapters, thumbnail concepts |
| **Quality Assurance** | Iris | QA & Compliance | `ShieldCheck` | Truthfulness, claims, caption alignment, publishing readiness |

---

## 7. Motion Language (Motion for React)

All animations must express real application state and obey `@media (prefers-reduced-motion: reduce)`.

- `duration-fast`: `120ms` (Button presses, hover highlights)
- `duration-standard`: `220ms` (Playhead jumps, transcript state updates, agent transitions)
- `duration-major`: `350ms` (Timeline cut gap closing, master render completion, Short generation)
