# Screenflow — Conversational Multilingual AI Video Platform

> Companion to `architecture.md`. This doc is the source of truth for everything the user sees and touches. Read it before building any UI.

## 1. Flow overview

Five screens, one linear primary path. The conversation produces a brief; the brief produces a storyboard; the storyboard approval triggers generation; generation lands the user on a review/edit screen; from there they export.

```
┌─────────────┐    finishes brief     ┌─────────────────┐    approves   ┌─────────────────┐
│  Screen 1   │ ───────────────────▶ │   Screen 2      │ ─────────────▶│   Screen 3      │
│   Chat      │                       │  Storyboard     │                │  Generation     │
│             │                       │                 │                │  Progress       │
└─────────────┘                       └─────────────────┘                └────────┬────────┘
       ▲                                      ▲                                   │
       │  "edit via                            │  "back to                         │  on done
       │   chat" (cut)                         │   storyboard"                     │
       │                                      │                                   ▼
       │                                      │                          ┌─────────────────┐
       │                                      │   needs more scenes?     │   Screen 4      │
       │                                      └──────────────────────────│  Review & Edit  │
       │                                                                  │                 │
       └──────────────────────────────────────────────────────────────────┴────────┬────────┘
                                                                                   │
                                                              opens export modal   ▼
                                                                          ┌─────────────────┐
                                                                          │   Screen 5      │
                                                                          │  Export Modal   │
                                                                          │                 │
                                                                          └─────────────────┘
```

### State machine: `project.status` → which screen the user sees

| Status | Screen | Notes |
|---|---|---|
| `draft` / `collecting` | Screen 1 (Chat) | Brief still being assembled |
| `planning` | Screen 2 (Storyboard) | Thumbnails generating; show skeleton cards |
| `rendering` | Screen 3 (Progress) | Active job; SSE driving UI |
| `ready` | Screen 4 (Review) | First render done; user can edit, switch language, export |
| `completed` | Screen 4 (Review) | User has exported at least once; same UI, badge says "exported" |
| `failed` | Same screen they were on | Error banner + retry button |
| `cancelled` | Screen 2 (Storyboard) | They went back; they can re-trigger |

The frontend reads `project.status` on every project fetch and routes the user accordingly. Deep-linking is supported — `/projects/:id` always lands the user on the right screen.

---

## 2. Routes

| URL | Screen | Auth | Notes |
|---|---|---|---|
| `/` | Welcome (just a "Start a new video" button) | — | Single-action landing page |
| `/projects/:id/chat` | Screen 1 | — | Chat with the orchestrator |
| `/projects/:id/storyboard` | Screen 2 | — | Storyboard with thumbnails |
| `/projects/:id/progress/:job_id` | Screen 3 | — | Live render progress |
| `/projects/:id/review` | Screen 4 | — | Final review + edit |
| `/projects/:id/review` + modal flag | Screen 5 | — | Export modal overlays Screen 4 |

Routing convention: each screen is its own Next.js page; the `(project)` route group shares the project header/sidebar.

---

## 3. Screen 1 — Chat (Conversational Onboarding)

### Purpose
Collect the project brief through a one-question-at-a-time conversation. End state: all required slots filled, user clicks "Start planning."

### When user lands here
- New project (`/` → "Start" → creates project → routes to `/projects/:id/chat`)
- Existing project with `status ∈ {draft, collecting}`

### Layout

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  ◀ Back      Project · Untitled                                          ⋯ Menu │
├──────────────────────────────────────────────────────┬─────────────────────────┤
│                                                      │                         │
│  ┌─────────────────────────────────────────────────┐ │   ╭─ Your video ──────╮ │
│  │ AI: What kind of video do you want to create?  │ │   │                   │ │
│  │                                                 │ │   │  Type      —      │ │
│  │  [Explainer]  [Cinematic]  [Social reel]  [Ad] │ │   │  Style     —      │ │
│  └─────────────────────────────────────────────────┘ │   │  Duration  —      │ │
│                                                      │   │  Language  —      │ │
│                                                      │   │  Tone      —      │ │
│  ┌─────────────────────────────────────────────────┐ │   │  People?   —      │ │
│  │ You: A social reel about my coffee brand        │ │   │  Music?    —      │ │
│  └─────────────────────────────────────────────────┘ │   │  Subs?     —      │ │
│                                                      │   │  Aspect    —      │ │
│  ┌─────────────────────────────────────────────────┐ │   │                   │ │
│  │ AI: Got it — a social reel. What visual style? │ │   │  Topic     —      │ │
│  │                                                 │ │   │                   │ │
│  │  [Realistic]  [Animated]  [Documentary]         │ │   │  3 of 10 collected│ │
│  └─────────────────────────────────────────────────┘ │   ╰───────────────────╯ │
│                                                      │                         │
│                                                      │   [Start planning]       │
│                                                      │   disabled until ready   │
│                                                      │                         │
│  ┌─────────────────────────────────────────────────┐ │                         │
│  │ Type your message...                       (↑)  │ │                         │
│  └─────────────────────────────────────────────────┘ │                         │
└──────────────────────────────────────────────────────┴─────────────────────────┘
```

Two-column layout on desktop (chat 60%, summary 40%). On mobile, summary collapses into a sticky bar at the top, expandable on tap.

### Components

- `ChatPanel` — message list, auto-scrolls to bottom on new message
- `ChatMessage` — text bubble; AI messages may have a trailing `ChipRow`
- `ChipRow` — horizontal scrollable list of tappable suggestions; tap inserts text and submits
- `ChatComposer` — multi-line textarea with send button, supports Enter to submit and Shift+Enter for newline
- `BriefSummaryCard` — list of slots and their current values; muted dashes for missing; visible check ✓ for filled
- `ProgressLabel` — "3 of 10 collected"
- `StartPlanningButton` — primary CTA; disabled until all required slots filled

### State / API

State is driven by the chat SSE stream. The page subscribes once on load.

```
on mount:
  fetch GET /projects/:id           → get project, scenes, messages
  if status != draft|collecting:
    redirect to the right screen
  render existing messages
  prepare to send next message

on user submit (text or chip):
  append optimistic user message
  POST /projects/:id/chat { message } as SSE
    on event: token        append text to streaming AI message bubble
    on event: slot_update  merge into local brief state → update summary card
    on event: question     finalise bubble, render chips
    on event: ready        finalise bubble, enable [Start planning] CTA,
                            set project.status='collecting' (it should already be)
    on event: done         close stream

on [Start planning]:
  POST /projects/:id/storyboard/generate
  → 202 { job_id }
  navigate to /projects/:id/storyboard
  (we don't go through Screen 3 here — storyboard is fast, ~10s,
   the Storyboard screen shows skeletons while it generates)
```

### Interactions

- Tap chip → inserts chip text, submits (single round-trip)
- Type free text → can override or extend chips
- Edit a previous answer? Cut from MVP. If user types "actually make it 60 seconds" mid-flow, slot-update naturally overwrites — no special UI needed
- Switch project mid-flow? Use ⋯ menu → "Start over"

### Edge cases

- **SSE drops** → reconnect with last-message-id; show a small "reconnecting…" indicator
- **First message empty** → don't send; placeholder remains
- **User reloads mid-conversation** → re-fetches messages, re-subscribes
- **User completes brief, walks away, comes back** → status is `collecting`, summary card is filled, [Start planning] is enabled
- **Slot inference conflict** (user says "social reel" then later "16:9") → newer value wins, summary card updates with a subtle highlight pulse

### Transitions out

- All slots filled → user clicks [Start planning] → POST storyboard/generate → push to `/projects/:id/storyboard`
- User clicks ⋯ → "Start over" → DELETE project + create new → `/projects/:new_id/chat`

---

## 4. Screen 2 — Storyboard

### Purpose
The approval gate. Show the user how the AI plans to break the video into scenes. Let them edit scripts, change visual prompts, toggle speakers, reorder/delete/add scenes — all *before* paying for full video generation.

### When user lands here
- From Screen 1 after [Start planning]
- From Screen 3 on cancellation
- Deep link with `status ∈ {planning, ready, completed}`

### Layout

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ◀ Back to chat   Coffee Brand · 30s · 9:16 · EN                  ⋯ Menu  Help   │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Scenes (5)                                          [Regenerate all]  [Generate]│
│                                                                                  │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────┐ │
│  │  Scene 1   0:00  │ │  Scene 2   0:06  │ │  Scene 3   0:12  │ │  Scene 4 ... │ │
│  │ ╭──────────────╮ │ │ ╭──────────────╮ │ │ ╭──────────────╮ │ │              │ │
│  │ │              │ │ │ │              │ │ │ │              │ │ │              │ │
│  │ │   thumbnail  │ │ │ │   thumbnail  │ │ │ │   thumbnail  │ │ │              │ │
│  │ │              │ │ │ │              │ │ │ │              │ │ │              │ │
│  │ ╰──────────────╯ │ │ ╰──────────────╯ │ │ ╰──────────────╯ │ │              │ │
│  │                  │ │                  │ │                  │ │              │ │
│  │ Hand pouring     │ │ Beans roasting   │ │ Steam rising     │ │ ...          │ │
│  │ espresso into a  │ │ in a brass drum, │ │ from a fresh cup │ │              │ │
│  │ tiny glass cup   │ │ warm light       │ │                  │ │              │ │
│  │                  │ │                  │ │                  │ │              │ │
│  │ "Crafted from..."│ │ "Sourced from..."│ │ "Served fresh..."│ │              │ │
│  │                  │ │                  │ │                  │ │              │ │
│  │ ☐ Speaking       │ │ ☐ Speaking       │ │ ☐ Speaking       │ │              │ │
│  │   on camera      │ │   on camera      │ │   on camera      │ │              │ │
│  │                  │ │                  │ │                  │ │              │ │
│  │ Subs: auto       │ │ Subs: auto       │ │ Subs: auto       │ │              │ │
│  │           ⋯ Menu │ │           ⋯ Menu │ │           ⋯ Menu │ │              │ │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────┘ │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘

Click any scene card → opens a right-side detail panel (slides in from right, ~480px wide):

  ╔══════════════════════════════════════════════════════════════════════════════╗
  ║   ✕                                                                          ║
  ║   Scene 1 · 6s                                                               ║
  ║   ─────────────────────────────────────────────────────────────────────────  ║
  ║                                                                              ║
  ║   Narration script                                                           ║
  ║   ┌─────────────────────────────────────────────────────────────────────┐    ║
  ║   │ Crafted from beans grown at 1,800 metres, every cup tells a story.  │    ║
  ║   └─────────────────────────────────────────────────────────────────────┘    ║
  ║                                                                              ║
  ║   Visual direction                                                           ║
  ║   ┌─────────────────────────────────────────────────────────────────────┐    ║
  ║   │ Hand pouring espresso into a tiny glass cup, warm overhead light,   │    ║
  ║   │ shallow depth of field, slow motion drop                            │    ║
  ║   └─────────────────────────────────────────────────────────────────────┘    ║
  ║                                                                              ║
  ║   Characters in scene                                                        ║
  ║   ( none — voice-over only )    [+ add character]                            ║
  ║                                                                              ║
  ║   ┌─ Speaking on camera ──────────────────────────────────────────────┐      ║
  ║   │ ◯ Off  (default)                                                  │      ║
  ║   │     Lip-sync will be skipped for this scene.                      │      ║
  ║   │ ◉ On                                                              │      ║
  ║   │     MuseTalk will sync mouth to narration audio.                  │      ║
  ║   └───────────────────────────────────────────────────────────────────┘      ║
  ║                                                                              ║
  ║   Subtitle position                                                          ║
  ║   ◉ Auto  ◯ Top  ◯ Bottom  ◯ Custom                                          ║
  ║                                                                              ║
  ║   ───────────────────────────────────────────────────────────────────────    ║
  ║                                                                              ║
  ║   [Regenerate scene]              [Save changes]   [Discard]                 ║
  ╚══════════════════════════════════════════════════════════════════════════════╝
```

### Components

- `StoryboardHeader` — project title, language/duration/aspect badges, [Regenerate all], [Generate] CTA
- `SceneGrid` — responsive grid (3 cols desktop, 1 col mobile)
- `SceneCard` — thumbnail + scene-index + duration + truncated description + truncated script + speaker toggle + ⋯ menu
- `SceneDetailPanel` — slide-in editor for the selected scene
- `SpeakerToggle` — explicit radio with explanation text, NOT a hidden checkbox (interview talking point: the user must consciously decide; lip-sync is expensive)
- `SubtitlePositionPicker` — radio group; "Custom" reveals a small preview thumbnail with a draggable horizontal line
- `SceneMenu` — popup: Edit / Regenerate / Delete / Add scene after / Move up / Move down

### State / API

```
on mount:
  fetch GET /projects/:id          → project + scenes + brief
  if status == planning:
    poll GET /jobs/:storyboard_job_id every 2s (or SSE)
    show skeleton cards until thumbnails arrive
    on each scene_ready event: update card
  if status >= ready:
    show "Already generated — go to review" banner with CTA
    (user can still edit and re-generate, but warn that current render will be replaced)

on edit script / prompt / has_speaker / subtitle_position:
  optimistic UI update
  PATCH /scenes/:id { <field>: <value> }
  on error: revert + toast

on [Regenerate scene]:
  POST /scenes/:id/regenerate { prompt_modifier?: string }
  card shows spinner over thumbnail
  on done: thumbnail swaps in

on [Regenerate all]:
  confirm dialog
  POST /projects/:id/storyboard/generate
  return to planning state

on [Generate]:
  confirm dialog if status == ready (will replace existing render)
  POST /projects/:id/generate
  navigate to /projects/:id/progress/:job_id

on Add scene after:
  POST /scenes { project_id, after_index }
  optimistic insert with skeleton

on Move up/down:
  POST /scenes/:id/move { new_index }
  optimistic reorder

on Delete:
  confirm
  DELETE /scenes/:id
  optimistic remove
```

### Interactions

- **Click scene card** → opens detail panel; clicking outside or ✕ closes
- **Edit any field** in detail panel → autosave on blur or after 800ms debounce
- **Speaker toggle** → updates immediately; if turning ON for a scene with no character, a small inline prompt asks "Add a character description for the speaker?" (cut from MVP if time-tight; just let the scene have a generic speaker)
- **[Generate]** → primary CTA; disabled until all scenes have non-empty script + visual prompt
- **Mobile** → detail panel becomes a bottom sheet (slide up); scene cards stack 1-col

### Edge cases

- **Thumbnails still generating** → skeleton card with shimmer animation; "Generating preview…" subtitle
- **Single scene fails** → red badge on card, [Retry] button on the card
- **All scenes failed** → top-level error banner: "Storyboard generation failed. Retry?"
- **User has unsaved edits in detail panel and clicks [Generate]** → modal: "Save changes before generating?" → [Save and generate] / [Discard and generate] / [Cancel]
- **Browser back from Screen 3** → returns here; scenes still visible

### Transitions out

- [Generate] → Screen 3 with the new job_id
- ◀ Back to chat → Screen 1 (note: edits in chat may now invalidate the storyboard; for MVP just allow it and let the user click [Regenerate all])

---

## 5. Screen 3 — Generation Progress

### Purpose
Keep the user oriented during the 60–180 s render. Show what's happening, surface partial results as they land, allow cancellation.

### When user lands here
- From Screen 2 after [Generate]
- Deep-linked from Screen 2 banner if `status == rendering`
- From Screen 4 after triggering [Regenerate scene]

### Layout

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ◀ Back to storyboard   Coffee Brand · 30s · 9:16 · EN              ⋯ Menu       │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Generating your video                                                           │
│  Estimated time remaining: ~1 min 20 s                            [Cancel]       │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                                                                          │    │
│  │   ✓ Storyboard      ⟳ Scenes       ○ Voice       ○ Subtitles      ○ ... │    │
│  │   ─────────────────●────────────────○──────────────○─────────────○──    │    │
│  │                                                                          │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  Per-scene progress                                                              │
│                                                                                  │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐    │
│  │ Scene 1        │ │ Scene 2        │ │ Scene 3        │ │ Scene 4        │    │
│  │ ┌────────────┐ │ │ ┌────────────┐ │ │ ┌────────────┐ │ │ ┌────────────┐ │    │
│  │ │            │ │ │ │            │ │ │ │   thumb    │ │ │ │   thumb    │ │    │
│  │ │   ▶ video  │ │ │ │   ▶ video  │ │ │ │            │ │ │ │            │ │    │
│  │ │            │ │ │ │            │ │ │ │  Scene gen │ │ │ │  Waiting   │ │    │
│  │ └────────────┘ │ │ └────────────┘ │ │ │   45%      │ │ │ │            │ │    │
│  │  ✓ Composited  │ │  ⟳ Lip-sync    │ │ │            │ │ │ │            │ │    │
│  └────────────────┘ └────────────────┘ └────────────────┘ └────────────────┘    │
│                                                                                  │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Components

- `PipelineStepper` — horizontal list of stages with state per stage (pending/active/done/failed)
- `ETALabel` — rough estimate, updates as stages complete
- `CancelButton` — confirms then cancels
- `SceneProgressGrid` — one card per scene, showing current stage of that scene
- `ScenePreviewPlayer` — when a scene's composite asset is ready, show an inline `<video>` autoplay loop muted

### State / API

```
on mount:
  job_id = route param
  fetch GET /jobs/:job_id
  open SSE GET /jobs/:job_id/events

on event: stage_change
  update PipelineStepper state

on event: scene_ready { scene_id, asset_url }
  swap that scene's preview from thumbnail to <video src={asset_url} autoplay loop muted />

on event: progress { percent }
  update ETALabel

on event: done { final_export_asset_id }
  close SSE
  navigate to /projects/:id/review

on event: error { message }
  show error banner with [Retry] [Back to storyboard]
  do NOT auto-navigate

on [Cancel]:
  confirm modal: "Cancel rendering? You'll lose progress on this run."
  PATCH /jobs/:job_id { status: 'cancelled' }
  navigate to /projects/:id/storyboard
```

### Interactions

- Hover a scene's video preview → pause/play indicator
- Tap a scene to expand it (mobile)
- Step in stepper is clickable when it's `done` and that stage has an asset (e.g., scenes after scene_gen is done → opens a quick lightbox of all scene videos)

### Edge cases

- **Cold start** of first Modal function takes ~30–60 s → stepper shows "Warming up GPU…" instead of a stage name
- **User reloads** → reconnect SSE with `Last-Event-ID`; re-render current state from `GET /jobs/:id`
- **Browser tab backgrounded** → SSE may pause; on visibility change, re-fetch full job state
- **Job already done** when user lands → navigate immediately to Review
- **Job failed before any scene completed** → no per-scene previews; just the error banner

### Transitions out

- `done` event → Review (Screen 4)
- [Cancel] → Storyboard (Screen 2)
- Error → stay on screen until [Retry] or [Back]

---

## 6. Screen 4 — Review & Edit

### Purpose
The main editing workspace. User watches the rendered video, makes per-cue subtitle edits, adjusts overlays, switches languages, and exports.

### When user lands here
- From Screen 3 on `done`
- Deep-link with `status ∈ {ready, completed}`

### Layout

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ◀ Back   Coffee Brand · 30s · 9:16        Language: [EN ▼]     [Export ▶]       │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│                  ┌──────────────────────────────────┐                            │
│                  │                                  │                            │
│                  │                                  │     ╭──────────────────╮   │
│                  │       video player               │     │  Subtitles       │   │
│                  │       9:16 aspect                │     │  Overlays        │   │
│                  │                                  │     │  Audio           │   │
│                  │                                  │     │  Scenes          │   │
│                  │                                  │     ╰──────────────────╯   │
│                  │                                  │                            │
│                  │  ▶  ──○──────────  00:08 / 00:30 │     ─── content panel ─    │
│                  └──────────────────────────────────┘     (depends on tab)        │
│                                                                                  │
│  Timeline                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │ Scenes:    ╱S1╱╱S2╱╱S3╱╱S4╱╱S5╱                                          │    │
│  │ Voice:     ▁▂▅▆▅▃▁▁▂▄▆▅▃▂▁▁▂▃▅▆▄▂▁▁▂▅▆▄▂▁ (waveform)                     │    │
│  │ Subs:      [Crafted...][From beans...][Every cup...][...]                │    │
│  │ Overlays:  [    Buy now →    ]            [Try free        ]              │    │
│  │ Music:     ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔  Vol: ───●─── -18 dB           │    │
│  │            ▲ playhead                                                     │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Right-panel tabs

#### Subtitles tab

```
Subtitles · EN                                              [Regenerate all subs]

0:00 ─ 0:02   "Crafted from beans"                                            ⋯
0:02 ─ 0:05   "grown at 1,800 metres"                                         ⋯
0:05 ─ 0:08   "every cup tells a story"                                       ⋯
...

Click any row to inline-edit text + timecode.
⋯ menu: Move up / Move down / Delete / Position: auto/top/bottom
```

#### Overlays tab

```
Overlays                                                    [+ Add overlay]

Buy now →            0:08 ─ 0:13   fade        ⋯
Try free             0:21 ─ 0:28   slide_up    ⋯

Click overlay to open inline editor: text, time range, animation, position.
```

#### Audio tab

```
Background music
  Vol: ─────────●──── -18 dB
  ☑ Enabled (uncheck to remove music)
  [Regenerate music]

Voice (per scene)
  Disabled in MVP — kept fixed at master level.
```

#### Scenes tab

```
Quick scene actions:

Scene 1   [Regenerate]
Scene 2   [Regenerate]
Scene 3   [Regenerate]
...

(Useful if user notices one bad scene in review and wants to fix it without
 going back to storyboard.)
```

### Components

- `VideoPlayer` — HTML5 `<video>` with controls; source is the current language's `final_export` asset
- `LanguageDropdown` — top-right; shows all 5 supported languages; ✓ on rendered ones, ⌛ on not-yet-rendered
- `TimelineCanvas` — scrollable timeline with multiple tracks; the playhead syncs with the video player's currentTime
- `WaveformTrack` — pre-rendered from the voice audio (use wavesurfer.js or render server-side and serve as image)
- `SceneStrip` — colour-coded blocks for each scene's time range; click to jump playhead
- `SubtitleTrack` — clickable cue blocks; opens inline editor
- `OverlayTrack` — separate row from subtitles; draggable to reposition in time
- `MusicTrack` — single bar with a volume slider inline
- `RightPanel` — tab switcher: Subtitles / Overlays / Audio / Scenes
- `SubtitleEditor` (Subtitles tab) — list editor for cues
- `OverlayEditor` (Overlays tab) — list editor for overlays
- `AudioControls` (Audio tab)
- `ScenesActions` (Scenes tab) — per-scene regenerate buttons
- `ExportCTA` — top-right primary button; opens Export Modal

### State / API

```
on mount:
  fetch GET /projects/:id    → project, scenes, overlays, subtitles per active_language
  fetch /assets/<final_export_asset_id>   → signed video URL
  fetch /assets/<voice_asset_id> for each scene → waveform data
  render timeline + player

on language change:
  setSelectedLang(L)
  if L in project.available_languages:
    fetch /projects/:id?lang=L  → returns subtitles for L, final_export for L
    swap video src to new signed URL
    instant switch
  else:
    POST /projects/:id/regenerate-language { language: L }
    show inline progress overlay on the player (NOT navigate away)
    on done event from SSE: swap video src, dismiss overlay

on edit subtitle cue:
  optimistic update
  PATCH /subtitles/:id { cues: [...] }
  side effect: composite needs regeneration → enqueue a re-composite for the affected scene
  show small "Re-compositing scene 2…" toast

on add/edit/delete overlay:
  POST/PATCH/DELETE /overlays...
  side effect: re-mux final_export (cheap, no LTX involved)
  show "Re-rendering export…" toast; player updates when done

on regenerate scene:
  POST /scenes/:id/regenerate
  open Screen 3 (Progress) scoped to that scene
  on done: come back here

on [Export]:
  open Export Modal (Screen 5)
```

### Interactions

- **Click subtitle cue on timeline** → opens inline edit popover
- **Click overlay on timeline** → opens overlay editor
- **Drag playhead** → seeks the video
- **Click scene strip** → jumps player to scene start
- **Right-click anywhere in overlay row** → "Add overlay at this time"
- **Spacebar** → play/pause (when no input focused)
- **L key** → focus language dropdown
- **E key** → open export modal

### Edge cases

- **Language switch in flight** → dropdown shows ⌛ on the target language; clicking another language during this is queued (or disabled — pick one for simplicity, recommend "disable other clicks")
- **User edits a subtitle while a language switch is running** → defer the edit until switch done; show subtle "queued" badge on the cue
- **Final export not yet available** → show "Generating final export…" overlay on the player
- **Out-of-sync state** between video and timeline → reset on next play
- **Asset signed URL expires** mid-session → on 403 from video element, re-fetch the asset

### Transitions out

- [Export] → Screen 5 (modal overlays current screen)
- Language dropdown → may trigger an inline render but no navigation
- [Regenerate scene] → Screen 3 → returns here

---

## 7. Screen 5 — Export Modal

### Purpose
Configure and trigger the final export. Show download link when done. Lightweight; not a full page.

### When user lands here
- From Screen 4 [Export] button only

### Layout

```
                        ┌──────────────────────────────────────────────────┐
                        │  Export                                       ✕  │
                        │                                                  │
                        │  Language:        English                        │
                        │                   (current selection from        │
                        │                    Screen 4 — read-only here)    │
                        │                                                  │
                        │  Format:          ◉ MP4                          │
                        │                                                  │
                        │  Quality:         ◯ 720p                         │
                        │                   ◉ 1080p                        │
                        │                                                  │
                        │  Aspect ratio:    9:16  (locked from brief)      │
                        │                                                  │
                        │  Subtitles:       ◉ Burned in                    │
                        │                   ◯ Sidecar .srt                 │
                        │                   ◯ Both                         │
                        │                                                  │
                        │  Estimated size:  ~14 MB                         │
                        │                                                  │
                        │  ─────────────────────────────────────────────   │
                        │                                                  │
                        │  [Cancel]                          [Start export]│
                        └──────────────────────────────────────────────────┘

While exporting:

                        ┌──────────────────────────────────────────────────┐
                        │  Exporting...                                 ✕  │
                        │                                                  │
                        │  ████████████░░░░░░░░░░░░  42%                   │
                        │                                                  │
                        │  Muxing audio and burning subtitles...           │
                        │                                                  │
                        └──────────────────────────────────────────────────┘

When done:

                        ┌──────────────────────────────────────────────────┐
                        │  ✓ Export ready                               ✕  │
                        │                                                  │
                        │  coffee_brand_en_1080p.mp4   14.2 MB             │
                        │                                                  │
                        │  [Download]                  [Copy link]          │
                        └──────────────────────────────────────────────────┘
```

### Components

- `ExportModal` (controlled component; closed by default)
- `FormatPicker` — single radio (MP4 only in MVP)
- `QualityPicker` — radio: 720p, 1080p
- `SubtitlePicker` — radio: burned-in, sidecar, both
- `SizeEstimate` — computed from bitrate × duration
- `ExportButton` / `CancelButton`
- `ProgressBar` for in-flight
- `DownloadActions` when done

### State / API

```
on [Start export]:
  POST /projects/:id/export { language, quality, subtitles }
  → 202 { job_id }
  open SSE on /jobs/:job_id/events
  show progress bar

on event: progress
  update bar

on event: done { asset_id }
  fetch /assets/:asset_id  → signed URL
  swap modal to download view
  PATCH /projects/:id { status: 'completed' }  (server-side, automatic on export done)

on event: error
  show error inside modal; [Retry] [Cancel]

on [Download]:
  trigger browser download from signed URL
  (signed URL has Content-Disposition: attachment)

on [Copy link]:
  copy signed URL to clipboard (note: it expires in 1 hour;
  if the user wants a permanent link, that's out of scope — show a hint)

on ✕ / [Cancel]:
  close modal; if export in flight, PATCH /jobs/:id { status: cancelled }
```

### Edge cases

- **Modal closed mid-export** → don't cancel; keep job running; user can re-open from a status pill on Screen 4: "Export in progress…"
- **Multiple exports** of the same project at different quality → each is its own asset; track latest in UI; older ones not shown but still accessible by job_id
- **Cancel during burn-in subtitle pass** → may take a few seconds to actually stop ffmpeg

### Transitions out

- ✕ → close modal, return to Screen 4
- [Download] → triggers download; modal stays open

---

## 8. Cross-cutting UI elements

### Header

Every project screen has the same header:

```
◀ Back   <Project title> · <duration> · <aspect> · <active language>          ⋯ Menu
```

- ◀ Back navigates one step up in the flow
- ⋯ menu: Rename project / Start over / Export current (Screen 4 only) / Delete

### Toasts

- Success: green, 3s
- Info: blue, 4s
- Error: red, 8s with [Dismiss]
- Persistent (e.g., re-rendering after edit): until done, with inline spinner

### Loading states

- **Initial page load** → full-page skeleton (header outline + content blocks)
- **In-place** → component-level skeletons (shimmer)
- **Streaming** (chat, progress) → typing dots / progress indicators
- Never block the whole UI with a spinner if part of the page is already useful

### Error states

- **Network error** → top toast "Couldn't reach server. Retrying…" + auto-retry with backoff
- **API 4xx** → toast with the server's error message
- **API 5xx** → toast "Something went wrong. Please try again." + log to console
- **Job failed** → show inline error on the relevant screen with [Retry] and [Back to storyboard]

### Empty states

- `/` with no projects → just the [Start a new video] button (no list to be empty)
- Storyboard with zero scenes → "AI is planning your scenes…" skeleton; never a true empty state in MVP

### Keyboard shortcuts

- Chat: Enter = send, Shift+Enter = newline
- Storyboard: arrow keys navigate scenes, Enter opens detail
- Review: Space = play/pause, arrows = seek 5s, L = language dropdown, E = export

---

## 9. Component inventory

Build these once; reuse everywhere.

| Component | Used on | Notes |
|---|---|---|
| `Button` (primary / secondary / ghost) | All | Variants, sizes |
| `IconButton` | All | For ⋯ menus, ✕, etc. |
| `TextInput`, `Textarea` | 1, 2, 4, 5 | With error state |
| `Radio`, `Checkbox`, `Toggle` | 2, 4, 5 | |
| `Dropdown` | 4 (language), 2 (subtitle position) | Searchable variant for language |
| `Modal` | 5, confirm dialogs | Backdrop, escape to close |
| `Toast` | All | Top-right stack |
| `Skeleton` | All | Loading state |
| `Chip` | 1 | Tappable |
| `ChatMessage`, `ChatComposer` | 1 | |
| `BriefSummaryCard` | 1 | |
| `SceneCard`, `SceneDetailPanel` | 2 | |
| `SpeakerToggle` | 2 | Explicit radio, not silent checkbox |
| `PipelineStepper` | 3 | |
| `SceneProgressGrid` | 3 | |
| `VideoPlayer` | 3, 4 | |
| `TimelineCanvas` | 4 | |
| `WaveformTrack` | 4 | |
| `SubtitleEditor`, `OverlayEditor` | 4 | |
| `ExportModal` | 5 | |
| `ProgressBar` | 5 | |
| `Header` | All | |

### Suggested library choices

- `wavesurfer.js` for waveform rendering
- `react-aria` for accessible components (Modal, Dropdown, Radio)
- `lucide-react` for icons
- `framer-motion` for the slide-in detail panel
- `clsx` + `tailwind-variants` for class composition

---

## 10. Responsive / mobile

| Screen | Mobile treatment |
|---|---|
| 1 — Chat | Summary card collapses to top sticky bar (expandable on tap); chat full-width below |
| 2 — Storyboard | Scene grid → 1 column; detail panel → bottom sheet |
| 3 — Progress | Pipeline stepper stays horizontal but smaller; scene grid → 1 column |
| 4 — Review | **Cut from MVP for mobile.** Show "Best viewed on desktop" message. Architecture supports it but timeline UX requires real work. |
| 5 — Export | Modal works as-is |

---

## 11. Accessibility notes (minimum bar)

- All interactive elements reachable by keyboard
- Focus visible (rings) on all focusable elements
- Modal traps focus, restores to trigger on close
- `aria-live="polite"` on chat AI bubbles for screen readers
- `aria-live="assertive"` for error toasts
- All form inputs have associated labels
- Video player exposes native controls
- Don't rely on colour alone for state (use icons + text)

---

## 12. Out of scope (mirrored from architecture.md)

UI surface for the following is deliberately not built:

- Conversational edit drawer on Screens 2 and 4
- Drag-to-reorder scenes (use up/down buttons in ⋯ menu)
- Per-cue subtitle font/colour/size pickers
- Multiple background music tracks / detailed audio mixing
- Project list / multi-project view
- Save draft button (everything autosaves)
- Share preview link
- Email notifications
- Mobile review screen
- Undo history UI

Each of these has a clear slot in the architecture if added later.

---

*End of screenflow.md*
