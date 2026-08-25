# Croviq Design System Specification

**Design Philosophy**: Professional Creative Workspace.
Combines the information density of **Premiere Pro / DaVinci Resolve**, the layout precision of **Linear**, and the interaction polish of **Raycast**. Eliminates generic SaaS cards, empty hero areas, and artificial AI gradients.

> **The Golden Rule**: The media must always be the most colorful element on screen. The application chrome and UI surfaces should disappear around it, ensuring zero visual contamination or distraction during video editing and review.

---

## 1. Brand Identity & Logo Usage

All logo files are located in `brandkit/`.

| Lockup | Asset File | Usage Rule |
|---|---|---|
| **Horizontal (Primary)** | `brandkit/croviq-logo-horizontal.svg` | Main application header and top-bar navigation. Represents the primary brand identity. |
| **Emblem (Symbol)** | `brandkit/croviq-symbol.svg` / `brandkit/croviq-symbol-on-graphite.svg` | Collapsed sidebar, favicon, browser tabs, agent avatars, and small badges. |
| **Stacked (Secondary)** | `brandkit/croviq-logo-stacked.svg` | Splash screens, standalone onboarding modals, and centered presentation decks. |

**Clearspace & Scaling**:
- Minimum horizontal logo height: `24px` in UI navigation.
- Minimum emblem size: `16px` for favicon/status indicators; `28px` for avatar chips.
- Clearspace: Minimum padding equal to the height of the lowercase 'o' around all lockups.

---

## 2. Color System

### 2.1 Brand Palette (Derived from Real Emblem & Wordmark)

The 19-facet emblem contains a spectrum from warm amber to deep violet:

```
Warm Facets:
  #FF9F1C  (Amber Orange)
  #FFBD16  (Gold)
  #FFB514  (Amber)
  #FFD05A  (Yellow Accent)
  #FF6B3D  (Coral)
  #FF7A43  (Orange Red)
  #F51B35  (Crimson)
  #F52B49  (Ruby)

Cool / Core Facets:
  #20A7D8  (Cyan)
  #18AEEA  (Sky Blue)
  #078ED8  (Azure)
  #0798DE  (Cobalt Light)
  #0D86D1  (Cerulean)
  #14A9DF  (Vivid Blue)
  #4B72D0  (Periwinkle Blue)
  #2355C5  (Electric Cobalt - Brand Primary)
  #1452C5  (Deep Blue)

Violet Facets:
  #6C2BBF  (Deep Violet)
  #B527B7  (Magenta Purple)

Canonical Wordmark Neutral:
  #22242B  (Graphite Black)
### 2.2 Application Neutral Graphite Theme (Creative Workspace)

High-density neutral graphite surfaces engineered for professional video editing. Neutral grays dominate (85–90%) so the interface recedes and does not visually contaminate the video footage being edited:

| Token | HEX | Description / Application |
|---|---|---|
| `bg-background` | `#101214` | Neutral deep graphite foundation (viewport base) |
| `bg-surface-1` | `#16191C` | Primary sidebars, asset bins, inspector drawers |
| `bg-surface-2` | `#1C2024` | Timeline track containers, video player wrapper, active cards |
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

One single brand interaction color; semantic colors are restrained, muted, and paired with icons/text:

| Role | Token | HEX | Application |
|---|---|---|---|
| **Primary** | `primary` | `#2355C5` | Selected states, primary buttons, active playhead |
| **Success** | `success` | `#3E8063` | QA `PASS`, publishing complete |
| **Warning** | `warning` | `#A77A32` | QA `REVISE`, suggested edit review |
| **Danger** | `danger` | `#B85454` | QA `FAIL`, removed segment |
| **Info / Processing** | `info` | `#5279B8` | Active job processing, claim citation |

> **Department Rule**: Departments are differentiated strictly by **icon + label**, never by rainbow colors. The full multicolor brand palette belongs exclusively to the Croviq logo marks.


### 3.1 Primary UI Font
- **Family**: `Inter`, `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Fallback / Alternative**: `Geist Sans`
- **Weights**:
  - `400` (Regular): Body, transcript sentences, descriptions
  - `500` (Medium): Buttons, track labels, input text, table headers
  - `600` (SemiBold): Panel headings, modal titles, department badges
  - `800` (ExtraBold): Brand wordmark lockup only

### 3.2 Monospace Technical Font
- **Family**: `JetBrains Mono`, `ui-monospace, "SF Mono", Menlo, Consolas, monospace`
- **Fallback / Alternative**: `Geist Mono`
- **Weights**: `400` (Regular), `500` (Medium)
- **Usage**: Timestamps (`00:04:12.18`), timecodes, Run/Job IDs (`run_a9b1c2`), log entries, token counts, JSON EDL inspection.

### 3.3 Type Scale
- `text-xs`: `11px` / `line-height: 14px` (Timecode labels, badges, hotkeys)
- `text-sm`: `13px` / `line-height: 18px` (Standard dense UI, transcript, table rows)
- `text-base`: `14px` / `line-height: 20px` (Primary controls, inspector property names)
- `text-md`: `16px` / `line-height: 24px` (Panel headers, section titles)
- `text-lg`: `18px` / `line-height: 28px` (Modal headers, Mission title)
- `text-xl`: `22px` / `line-height: 30px` (Page title)

---

## 4. Spacing, Radii & Elevation

### 4.1 Spacing Scale (4px Base)
`4px` (`space-1`), `8px` (`space-2`), `12px` (`space-3`), `16px` (`space-4`), `20px` (`space-5`), `24px` (`space-6`), `32px` (`space-8`).

### 4.2 Border Radius Scale
- `radius-sm`: `4px` (Badges, timecode chips, track segments)
- `radius-md`: `6px` (Buttons, inputs, dropdown items, toolbars)
- `radius-lg`: `8px` (Panels, video player frame, modal windows)
- `radius-full`: `9999px` (Avatars, status indicator dots)
*(Strictly avoid bubbly >12px radii on rectangular editing surfaces).*

### 4.3 Borders & Elevation
- **Borders**: Crisp `1px solid #2D3339` everywhere. Strong borders use `#3B434B`. No borderless ambiguous floating panels.
- **Elevation**:
  - `shadow-sm`: `0 1px 2px rgba(0,0,0,0.5)` (Toolbar buttons)
  - `shadow-md`: `0 4px 12px rgba(0,0,0,0.7)` (Dropdown menus, tooltips)
  - `shadow-lg`: `0 12px 32px rgba(0,0,0,0.85)` (Modals, command palette `⌘K`)

---

## 5. Editor Workspace Layout & Visual Semantics

### 5.1 Quad-Pane Architecture
```
┌─────────────────┬───────────────────────────────┬─────────────────┐
│ ASSETS & MEDIA  │ VIDEO PLAYER & TRANSCRIPT     │ INSPECTOR &     │
│                 │                               │ AGENT ACTIVITY  │
│ [Raw Footage]   │  ┌─────────────────────────┐  │                 │
│ [Cuts / Audio]  │  │      Player Canvas      │  │ Director: Idle  │
│ [Shorts]        │  └─────────────────────────┘  │ QA: PASS        │
│ [Thumbnails]    │  Transcript:                   │ Packaging: Done │
│                 │  ~~[um]~~ I wanted to explain │ Approval: Ready │
├─────────────────┴───────────────────────────────┴─────────────────┤
│ TWICK MULTI-TRACK TIMELINE                                        │
│ V1 [============================] [=======]                       │
│ A1 [~~~~~~~~~~~~~~~~~~~~~~~~~~~~] [~~~~~~~]                       │
│ TX [Intro] [Removed Gap] [Key Point]                              │
└───────────────────────────────────────────────────────────────────┘
```

### 5.2 Timeline & Transcript Semantic Color Treatment
- **Removed Segment (Cut / Deleted)**:
  - Text Transcript: Muted red strikethrough with subtle tint (`#B85454` at 15% opacity background, text strike).
  - Timeline: Muted red striped cut overlay (`#B85454` at 30% opacity) that animates to zero width as gap closes.
- **Suggested Edit (Review / Low Confidence)**:
  - Text Transcript: Muted amber underline / badge (`#A77A32` at 15% opacity background).
  - Timeline: Muted amber track bracket (`#A77A32`).
- **Preserved Key Segment (Highlight)**:
  - Text Transcript: Muted sage/emerald tint (`#4F7F65` at 15% opacity background, `#82B399` text).
  - Timeline: Muted green marker pin / segment outline (`#4F7F65`).
- **Playhead / Active Processing**:
  - Timeline Playhead: `#2355C5` with `#F2F4F5` line.
  - Active processing pulse: `#5279B8`.


## 6. Motion Language (Motion for React)

All motion must represent tangible, physical changes in workflow state. Decorative floating or generic spinning animations are strictly prohibited.

### 6.1 Timing Tokens
- `duration-fast`: `120ms` (`ease-out`) — Button presses, hover highlights, tooltip fades.
- `duration-standard`: `220ms` (`cubic-bezier(0.2, 0, 0, 1)`) — Drawer sliding, playhead jumps, panel reveals.
- `duration-major`: `350ms` (`cubic-bezier(0.16, 1, 0.3, 1)`) — Timeline cut gap closing, modal presentation, approval gate unlocking.

### 6.2 Event-Driven Animations
1. **Cut Removal**: Segment dissolves (opacity `1 → 0`, scale `1 → 0.96` in 120ms), following segment slides left to close the gap (`320ms spring`).
2. **Transcript Cut**: Word strikes through with a red line swipe (`150ms`).
3. **Agent Status Change**: Department indicator badge transitions cleanly between idle (gray), active (cobalt pulse), revise (amber), pass (emerald).
4. **Approval Gate Unlock**: Lock icon transitions to checkmark with an emerald subtle glow (`300ms`).

*Strictly obeys `@media (prefers-reduced-motion: reduce)` by bypassing positional translations.*

---

## 7. Icon System (Lucide React)

One unified icon library. Consistent `16px` (standard UI) and `20px` (panel headers) icon sizing with `strokeWidth={1.75}`.

| Concept | Canonical Lucide Icon | Usage |
|---|---|---|
| **Director** | `Clapperboard` | Top-level coordinator agent indicator |
| **Editor** | `Scissors` | Media analysis, cuts, and dialogue editing |
| **Packaging** | `Sparkles` | Titles, descriptions, chapters, and thumbnail generation |
| **QA** | `ShieldCheck` | Truthfulness, verification, and compliance checks |
| **Research** | `Compass` | Pre-production topic and demand analysis |
| **Data Science / Growth**| `TrendingUp` | Post-release analytics, retention curves, and lessons |
| **Workspace** | `Building2` | Top-level creator account / brand kit |
| **Mission** | `Film` | Content production container |
| **Run** | `PlayCircle` | Single execution run |
| **Artifact** | `FileVideo` / `Image` | Generated media artifacts |
| **Publisher** | `UploadCloud` | External YouTube distribution |
| **Approval Gate** | `Lock` / `Unlock` | Human sign-off barrier |
| **Timeline** | `SlidersHorizontal` | Multi-track editor timeline view |
| **Logs / Terminal** | `Terminal` | Cloud Logging and Trace events |
| **Settings** | `Settings` | Workspace preferences & channel keys |
