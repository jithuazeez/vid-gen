# Conversational Multilingual AI Video Platform — Architecture

> Complete, consolidated architecture document. Supersedes any earlier draft.

## 1. Overview

A platform that generates cinematic multilingual videos from a chat-driven brief. The user describes what they want, the system collects a structured spec conversationally, plans scenes, generates visuals + narration + (gated) lip-sync + subtitles + overlays + background music, and produces export-ready MP4s. Language can be switched without regenerating visual scenes.

**Target languages:** English, Hindi, Marathi, Tamil, Punjabi.

**Submission scope:** working end-to-end demo deployed on Modal (GPU) + Oracle Cloud Infrastructure Always-Free tier (Ampere A1 VM running API + Celery + Postgres + Redis) + S3-compatible object storage. The architecture supports the out-of-scope items in §16; they are deliberately not implemented in the MVP.

---

## 2. Scope

### In scope (MVP)

- Conversational requirement collection with slot-filling and suggestion chips
- Storyboard generation with cheap SDXL-Turbo thumbnails as a user approval gate
- Per-scene editing (script, visual prompt, subtitle text, subtitle position, speaker toggle)
- **Conversational edit on Screens 2 and 4** — same chat surface drives scene edits, overlay tweaks, and language switches via a LangGraph router that translates intent into PATCH / regenerate calls
- Full pipeline: image-to-video → multilingual TTS (primary language only on first render) → conditional lip-sync → subtitle alignment → composite
- On-demand language switching that triggers re-render of voice + subtitles + lip-sync + composite for the chosen language only
- Multilingual narration via Sarvam Bulbul-v2 (5 languages)
- Translation via Sarvam Translate
- Face-aware subtitle positioning (MediaPipe)
- Animated text overlays as a first-class timeline track
- AI-generated background music (**ACE-Step 1.5**, Apache-2.0), one track per project; Magenta RealTime wired as fallback behind the same `MusicProvider` Protocol
- Export to MP4 at 720p or 1080p, with burned-in or sidecar SRT
- Per-scene regeneration
- Render state tracking with SSE progress updates
- Deployment: **Celery worker (Oracle Cloud Always-Free Ampere A1 VM) orchestrating Modal GPU workers** + Postgres on the same VM (or OCI Autonomous DB) + S3-compatible object storage (AWS S3 or OCI Object Storage with S3-compat API)

### Out of scope (cut from MVP; architecture supports them)

- 4K export, chapter markers, MOV format
- Email notifications, share-preview links, save-draft, project list
- Drag-to-reorder scenes (use up/down buttons)
- Per-subtitle-entry font/colour/size (one global subtitle style)
- Mobile-optimised review screen (desktop only; chat + storyboard work on mobile)
- User accounts, multi-tenant auth
- Undo history (project versioning)
- Audio mixing beyond a single music volume slider

---

## 3. Architecture

Three services + shared infra. API is stateless and CPU-light. **Celery worker** (CPU-only, deployed alongside the API on an Oracle Cloud Always-Free Ampere A1 VM) owns pipeline orchestration — it runs the controller logic that fans out per-scene work via Modal `.spawn()` and tracks DAG state in Postgres. **Modal** is the pure GPU primitive layer — one function per model, no orchestration inside Modal. Redis serves two roles: Celery broker, and SSE pub/sub fan-out.

```
┌─────────────────────────────────────────────────────────┐
│            Frontend  (Next.js + React + TS)             │
│  Chat · Storyboard · Progress · Review · Export modal   │
└───────────────────────┬─────────────────────────────────┘
                        │ REST + SSE
┌───────────────────────▼─────────────────────────────────┐
│               API Service  (FastAPI on Fly.io)          │
│   /projects /chat /storyboard /scenes /jobs /assets     │
│         /regenerate-language /export /overlays          │
└───┬──────────────┬─────────────────┬───────────────┬────┘
    │              │                 │               │ enqueue
┌───▼──────────┐ ┌─▼──────────────┐ ┌▼────────────┐ ┌▼─────────────────┐
│Conversation  │ │ Scene engine   │ │Edit router   │ │ Celery worker    │
│orchestrator  │ │ (Gemini 3.1    │ │(LangGraph +  │ │ (CPU, Oracle     │
│(LangGraph +  │ │  Flash-Lite,   │ │ Gemini 3.1   │ │  Ampere A1 VM)   │
│ Gemini 3.1   │ │  structured    │ │ Flash-Lite;  │ │  controller      │
│ Flash-Lite)  │ │  output)       │ │ Screens 2+4) │ │  tasks:          │
└──────────────┘ └────────────────┘ └──────────────┘ │  render_project  │
                                                     │  regen_language  │
                                                     │  regen_scene     │
                                                     │  export          │
                                                     └────┬─────────────┘
                                                          │ .spawn() per stage
              ┌───────────────────────────────────────────┴─────────┐
              │                                                     │
       ┌──────▼────────────┐                       ┌────────────────▼──────────┐
       │ Sarvam APIs       │                       │  Modal worker functions    │
       │  (called from     │                       │  each = own GPU class      │
       │  Celery worker)   │                       │  (pure leaf workers; no    │
       │                   │                       │   orchestration in Modal)  │
       │  Translate        │                       │                            │
       │  Bulbul-v2 TTS    │                       │  ltx_render      A100 40GB │
       └───────────────────┘                       │  sdxl_image      A10G      │
                                                   │  musetalk_sync   A10G      │
                                                   │  acestep_music   A10G      │
                                                   │  whisper_align   T4        │
                                                   │  mediapipe_face  CPU       │
                                                   │  ffmpeg_composite CPU      │
                                                   └────────────┬───────────────┘
                                                                │
                              ┌─────────────────────────────────┴─────────────┐
                              ▼                                               ▼
                    ┌──────────────────┐                       ┌─────────────────────┐
                    │ Asset manifest   │                       │  Object store        │
                    │ Postgres 16 on   │                       │  S3 (AWS) or OCI     │
                    │ OCI Ampere A1    │                       │  Object Storage      │
                    │ VM (Always-Free) │                       │  (S3-compat API)     │
                    └──────────────────┘                       └─────────────────────┘

         Job state machine lives in Postgres `render_jobs` table.
         Redis (Upstash) plays two roles: Celery broker, and SSE pub/sub
         fan-out (workers PUBLISH; API subscribes per /jobs/:id/events).
```

**Why this split (vs. self-hosted A100, vs. fully-Modal everything).** A self-hosted A100 means the worker process holds all models in VRAM and runs one task at a time per GPU. That's simple but expensive ($1.49–$2.10/hr running continuously, even idle). Modal lets each model type run on the cheapest GPU it actually needs, scales to zero between renders, and bills per second. For a demo with $30 of credit, this is dramatically more efficient.

**Why Celery + Modal (the hybrid).** Earlier drafts of this doc swung between two extremes — pure Celery and pure Modal. The right answer is both, with a clean split:

- **Celery** is where the pipeline DAG, retries on transient transport failures, idempotency-key dedupe, and `render_jobs` state writes live. It's a regular Python process on the Oracle Cloud Ampere A1 VM (Always-Free, 4 OCPU / 24 GB RAM) — easy to attach a debugger to, easy to deploy, easy to test locally. Celery tasks call Modal functions via `.spawn()` (async) and `.get()` (await) and treat them like ordinary remote procedures.
- **Modal** is where the GPUs are. One Modal function per model, each pinned to the smallest GPU that fits. Modal handles container lifecycle, scale-to-zero, GPU-class routing, per-call cost telemetry, and concurrency *for the GPU itself*. It does *not* know about the pipeline DAG.

This split lets us debug controller logic without re-deploying Modal, and re-tune GPU concurrency without touching pipeline code. Modal handles GPU concurrency; Celery handles task concurrency.

---

## 4. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js 14 (App Router) + React + TypeScript + Tailwind | Standard stack |
| Frontend video player | HTML5 `<video>` with signed S3 URLs | No HLS needed for MVP |
| API service | FastAPI + Pydantic v2 | Hosted on OCI Ampere A1 VM (Always-Free) or local for demo |
| Auth | None for MVP | Note as out-of-scope |
| LLM (slot-fill) | **Gemini 3.1 Flash-Lite** (Google AI Studio) with structured output | Cheap, fast, JSON-native; configurable via `GEMINI_MODEL` |
| LLM (scene planning) | **Gemini 3.1 Flash-Lite** with structured output | Same model, higher temperature for narrative structure |
| LLM (edit router) | **Gemini 3.1 Flash-Lite** with structured output | Same model, classification only |
| Conversation graph | LangGraph (compiled `StateGraph`) | One graph object with collect + edit subgraphs, selected at the entry router node by `project.status` |
| Pipeline orchestration | **Celery 5.x** (broker = Redis) | Controller tasks (`render_project`, `regen_language`, `regen_scene`, `export`) call Modal via `.spawn()` |
| Job state | Postgres `render_jobs` table | Celery owns the row; status reducer in API derives `project.status` |
| Redis | **Two roles**: Celery broker + SSE pub/sub | Local Redis on the OCI VM (or Upstash free tier — 10k cmds/day) |
| DB | Postgres 16 on the OCI Ampere A1 VM, or OCI Autonomous DB (Always-Free, 20 GB) | Single source of truth |
| Object store | AWS S3 free tier *or* OCI Object Storage with the S3-compatibility API (Always-Free 20 GB) | Code against `boto3`; S3-compat means a single client works for both |
| Translation + TTS | Sarvam Translate + Bulbul-v2 (cloud API) | SOTA for 5 Indian langs |
| Video gen | LTX-Video 13B distilled (FP8) in I2V mode | Fits A100 40 GB, fast |
| Image gen | SDXL-Turbo | Char refs + storyboard thumbnails |
| Lip-sync | MuseTalk | Modern, better than Wav2Lip |
| Subtitle alignment | Whisper large-v3 | Word-level forced alignment |
| Face detection | MediaPipe Face Detector | CPU, light |
| Music | **ACE-Step 1.5** (`ACE-Step/Ace-Step1.5` on HF, Apache-2.0, ~3.5B params) | Higher quality than Magenta; Magenta RealTime kept as `MusicProvider` fallback |
| Compositing | FFmpeg (system binary inside Modal CPU function) | Standard |
| GPU compute | Modal serverless functions | $30 credit covers MVP |
| API + Celery hosting | **Oracle Cloud Always-Free Ampere A1** (4 OCPU / 24 GB RAM ARM VM, plus 200 GB block storage) — API + Celery worker run as two `systemd` units in Docker | One VM, $0/month forever |
| CI | GitHub Actions | Lint + smoke test |

### Per-task GPU class on Modal

The key cost optimisation: each Modal function uses the smallest GPU that holds its model.

| Function | GPU | Approx VRAM | Modal $/hr (preemptible base) | Notes |
|---|---|---|---|---|
| `ltx_render` | A100 40GB | ~12 GB | $2.10 | LTX-Video I2V, ~10 s per clip |
| `sdxl_image` | A10G | ~7 GB | $1.10 | Char refs + thumbnails, ~1–2 s per image |
| `musetalk_sync` | A10G | ~4 GB | $1.10 | Gated; only runs when scene.has_speaker |
| `whisper_align` | T4 | ~3 GB | $0.59 | Forced alignment for subtitles |
| `acestep_music` | A10G | ~8 GB | $1.10 | ACE-Step 1.5 ~3.5B; once per project, ~30 s |
| `mediapipe_face` | CPU | — | ~$0.05 | Sampled face detection |
| `ffmpeg_composite` | CPU (4 cores) | — | ~$0.05 | Scene composite + final mux |

All functions use `min_containers=0` (scale to zero) during development. For the final demo render, optionally set `min_containers=1` on `ltx_render` and `sdxl_image` to avoid cold-start delays in front of the interviewer.

---

## 5. Project structure

```
video-platform/
├── apps/
│   ├── api/                          # FastAPI service
│   │   ├── main.py
│   │   ├── settings.py
│   │   ├── routes/
│   │   │   ├── projects.py
│   │   │   ├── chat.py               # SSE chat (Screen 1 collect + Screens 2/4 edit)
│   │   │   ├── storyboard.py
│   │   │   ├── scenes.py
│   │   │   ├── jobs.py               # SSE progress via Redis sub
│   │   │   ├── language.py           # /regenerate-language
│   │   │   ├── overlays.py
│   │   │   ├── assets.py
│   │   │   └── export.py
│   │   ├── orchestrators/
│   │   │   ├── conversation.py       # LangGraph + Gemini Flash — collect mode (Screen 1)
│   │   │   ├── edit_router.py        # LangGraph + Gemini Flash — edit mode (Screens 2+4)
│   │   │   └── scene_engine.py       # Gemini Pro structured output
│   │   ├── modal_client.py           # thin wrapper to .spawn() Modal fns from API + worker
│   │   ├── schemas/                  # Pydantic models
│   │   └── db/                       # SQLAlchemy 2.x async
│   │
│   ├── worker/                       # Celery worker — pipeline orchestration
│   │   ├── celery_app.py             # broker=Redis, result_backend=Redis
│   │   ├── tasks/
│   │   │   ├── render_project.py     # Phase B controller; fan out per-scene work via Modal
│   │   │   ├── regen_language.py     # Cheap language switch (reuses cached visuals + music)
│   │   │   ├── regen_scene.py        # Per-scene regen (script / prompt / has_speaker change)
│   │   │   ├── storyboard.py         # Phase A: scene plan + thumbnails fan-out
│   │   │   └── export.py             # Final encode with target quality/subtitles
│   │   ├── manifest.py               # Content-hash cache lookups against the assets table
│   │   └── sse.py                    # Redis PUBLISH helper for progress events
│   │
│   ├── modal_app/                    # Pure GPU leaf workers — no orchestration here
│   │   ├── __init__.py
│   │   ├── app.py                    # Modal App, Volume, secrets, shared images
│   │   ├── functions/
│   │   │   ├── thumbnails.py         # sdxl_image — thumbnails
│   │   │   ├── character_refs.py     # sdxl_image — char refs
│   │   │   ├── scene_video.py        # ltx_render — LTX-Video I2V
│   │   │   ├── voice.py              # Sarvam Bulbul (CPU; thin API wrapper)
│   │   │   ├── lipsync.py            # musetalk_sync (gated)
│   │   │   ├── subtitles.py          # whisper_align + mediapipe_face
│   │   │   ├── music.py              # acestep_music — ACE-Step 1.5 on A10G
│   │   │   ├── composite.py          # ffmpeg_composite per scene
│   │   │   └── export.py             # ffmpeg final mux
│   │   ├── models/                   # Model loaders (LTX, SDXL, MuseTalk, Whisper, ACE-Step)
│   │   ├── providers/                # External API adapters + music protocol
│   │   │   ├── sarvam.py
│   │   │   ├── llm.py                # Gemini wrapper for inside-Modal calls
│   │   │   ├── acestep.py            # ACE-Step 1.5 — primary MusicProvider
│   │   │   └── magenta.py            # Magenta RealTime — fallback MusicProvider
│   │   └── storage.py                # S3 / boto3 helpers
│   │
│   └── web/                          # Next.js
│       ├── app/
│       │   ├── (project)/
│       │   │   ├── chat/page.tsx       # Screen 1
│       │   │   ├── storyboard/page.tsx # Screen 2 (with edit chat drawer)
│       │   │   ├── progress/page.tsx   # Screen 3
│       │   │   └── review/page.tsx     # Screen 4 (with edit chat drawer)
│       │   └── layout.tsx
│       ├── components/
│       │   ├── Chat/                 # Reusable: collect mode + edit mode
│       │   ├── Storyboard/
│       │   ├── Timeline/
│       │   ├── SubtitleEditor/
│       │   ├── OverlayTrack/
│       │   ├── LanguageSwitch/
│       │   └── ExportModal/
│       └── lib/
│           ├── api.ts
│           └── sse.ts
│
├── infra/
│   ├── docker-compose.dev.yml        # local: postgres, redis, minio, api, celery worker
│   ├── docker/                       # Dockerfiles for api and worker images
│   │   ├── api.Dockerfile
│   │   └── worker.Dockerfile
│   └── oracle/                       # Oracle Cloud Always-Free deployment
│       ├── docker-compose.prod.yml   # api + worker + postgres + redis on the OCI VM
│       ├── README.md                 # one-shot bootstrap on a fresh OCI Ampere A1 VM
│       ├── deploy.sh                 # rsync + restart on the VM over SSH
│       ├── nginx.conf                # TLS termination + SSE-friendly proxy
│       └── vidplatform.service       # systemd unit pinning compose to the VM
│
├── db/
│   └── migrations/                   # Alembic
│
└── docs/
    ├── architecture.md               (this file)
    ├── screenflow.md
    └── prompts/
        ├── conversation_system.md
        ├── scene_engine_system.md
        └── edit_router_system.md
```

---

## 6. Data model (Postgres)

```sql
-- Projects: one per video the user is making
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'draft',
    -- draft         : just created
    -- collecting    : chat is in slot-filling mode
    -- planning      : storyboard being generated (thumbnails + scene plan)
    -- rendering     : full video pipeline running
    -- ready         : initial render complete, user is in review/edit
    -- completed     : user has exported at least one final video
    -- failed
    -- cancelled
  brief JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- slot-filling output (see §9)
  primary_language TEXT,                  -- en | hi | mr | ta | pa
  active_language TEXT,                   -- which language is currently rendered/visible
  available_languages TEXT[] DEFAULT '{}',-- languages rendered so far (cache hits)
  aspect_ratio TEXT,                      -- 16:9 | 9:16 | 1:1
  duration_seconds INT,
  has_characters BOOLEAN DEFAULT false,   -- project-level lipsync gate
  music_enabled BOOLEAN DEFAULT true
);
CREATE INDEX projects_status_idx ON projects(status);

-- Full chat transcript
CREATE TABLE conversation_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  role TEXT NOT NULL,                      -- user | assistant | system
  content TEXT NOT NULL,
  tool_calls JSONB,                        -- slot updates, edit commands
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX conv_msgs_project_idx ON conversation_messages(project_id, created_at);

-- Characters that recur across scenes
CREATE TABLE characters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  reference_image_asset_id UUID            -- FK to assets.id
);

-- Scenes
CREATE TABLE scenes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  scene_index INT NOT NULL,
  duration_seconds NUMERIC(5,2) NOT NULL,
  visual_prompt TEXT NOT NULL,
  narration_script TEXT NOT NULL,         -- in primary_language
  has_speaker BOOLEAN NOT NULL DEFAULT false,
    -- defaults from project.has_characters; auto-set by scene engine
    -- from script analysis; user-overridable per scene
  character_ids UUID[] NOT NULL DEFAULT '{}',
  subtitle_position TEXT NOT NULL DEFAULT 'auto',  -- auto | top | bottom | custom
  subtitle_custom_y NUMERIC(4,3),
  thumbnail_asset_id UUID,
  scene_video_asset_id UUID,               -- language-agnostic; reused across all langs
  UNIQUE(project_id, scene_index)
);
CREATE INDEX scenes_project_idx ON scenes(project_id, scene_index);

-- Animated text overlays: project-scoped, span the global timeline
CREATE TABLE overlays (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  overlay_type TEXT NOT NULL,              -- cta | lower_third | logo | animated_text
  text TEXT,
  start_seconds NUMERIC(6,2) NOT NULL,
  end_seconds NUMERIC(6,2) NOT NULL,
  position JSONB NOT NULL DEFAULT '{}'::jsonb,
  animation TEXT NOT NULL DEFAULT 'fade',  -- fade | slide_up | typewriter | none
  style JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Subtitles: language-keyed cue arrays
CREATE TABLE subtitles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scene_id UUID NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  language TEXT NOT NULL,
  cues JSONB NOT NULL,
    -- [{ start: float_s, end: float_s, text: str, position?: "top"|"bottom"|{x,y} }]
  generated_position TEXT,                 -- decided by face-detect heuristic
  UNIQUE(scene_id, language)
);

-- Every artifact produced by a worker
CREATE TABLE assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  scene_id UUID REFERENCES scenes(id) ON DELETE CASCADE,
  asset_type TEXT NOT NULL,
    -- thumbnail | character_ref | scene_video | voice | lipsync_video
    -- | subtitle_srt | music | composite | final_export
  language TEXT,                           -- null = language-agnostic
  storage_key TEXT NOT NULL,
  content_hash TEXT NOT NULL,              -- sha256 of inputs (idempotency)
  bytes BIGINT,
  mime_type TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX assets_content_hash_idx ON assets(content_hash);
CREATE INDEX assets_lookup_idx ON assets(project_id, scene_id, asset_type, language);

-- Render jobs (state machine)
CREATE TABLE render_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  job_type TEXT NOT NULL,
    -- storyboard | initial_render | language_render | scene_regen | export
  language TEXT,                           -- target for language_render / export
  scene_ids UUID[],                        -- null = all scenes
  status TEXT NOT NULL DEFAULT 'pending',
    -- pending | running | succeeded | failed | cancelled
  current_stage TEXT,
  progress JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- { scenes: { <scene_id>: { stage: 'voice', status: 'running' }, ... } }
  modal_call_ids JSONB,                    -- track spawned Modal calls for cancellation
  error TEXT,
  idempotency_key TEXT UNIQUE,             -- caller-provided
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX jobs_status_idx ON render_jobs(status);
CREATE INDEX jobs_project_idx ON render_jobs(project_id, created_at DESC);
```

**Content-addressed assets.** `content_hash` is sha256 of the canonical input bundle. Re-running the same task returns the cached asset, free. Critical for retries and partial regens. Example for a `scene_video`:

```python
content_hash = sha256(json.dumps({
    "visual_prompt": scene.visual_prompt,
    "character_ref_hashes": [c.content_hash for c in refs],
    "ltx_model_version": "ltxv-13b-0.9.7-distilled-fp8",
    "seed": project.seed,
    "duration_s": scene.duration_seconds,
}, sort_keys=True).encode()).hexdigest()
```

---

## 7. API contracts

All responses are JSON. SSE endpoints stream `event: <name>\ndata: <json>\n\n`. All write endpoints accept an `Idempotency-Key` header where listed.

### Why PATCH (not PUT)

Most edits in this app are partial — the user changes one field in a scene (`narration_script`, or `has_speaker`, or `subtitle_position`) without touching the rest. PUT would require the client to send the entire scene resource on every keystroke, which is wasteful and creates last-write-wins hazards if two fields are being edited concurrently. PATCH with field-level updates is the right shape. The trade-off is that PATCH bodies aren't fully idempotent by HTTP spec, but we paper over that with optimistic concurrency (`If-Match: <etag>`) on critical resources and with explicit `Idempotency-Key` headers on the few endpoints that trigger work.

### Endpoints

```
# Projects
POST   /projects                                        201 { project_id }
GET    /projects/:id                                    200 { project, scenes, overlays, latest_job }
PATCH  /projects/:id                                    200 (partial: brief, has_characters, music_enabled, ...)

# Chat (Screen 1)
POST   /projects/:id/chat
  Body: { message: string }
  Response: text/event-stream
    event: token        data: { text }
    event: slot_update  data: { slots: {...partial} }
    event: question     data: { prompt, chips: [string] }
    event: ready        data: { brief: {...complete} }
    event: done

# Storyboard (Screen 2)
POST   /projects/:id/storyboard/generate      [Idempotency-Key]   202 { job_id }
GET    /projects/:id/storyboard                                   200 { scenes: [...] }
PATCH  /scenes/:id                                                200 (partial)
POST   /scenes/:id/regenerate                                     202 { job_id }
POST   /scenes/:id/move           Body: { new_index: int }        200
DELETE /scenes/:id                                                204
POST   /scenes                                                    201 (add scene)

# Generation (Screen 3)
POST   /projects/:id/generate                 [Idempotency-Key]   202 { job_id }
GET    /jobs/:id                                                  200 { status, stage, progress }
GET    /jobs/:id/events                       text/event-stream
  event: stage_change   data: { stage, scene_id? }
  event: scene_ready    data: { scene_id, asset_url }
  event: progress       data: { percent }
  event: done           data: { language, final_export_asset_id }
  event: error          data: { message }

# Review + edit (Screen 4)
POST   /projects/:id/regenerate-language      [Idempotency-Key]
  Body: { language: "hi" }                                        202 { job_id }
  # Re-runs voice + (gated)lipsync + subtitles + composite for the target language.
  # If the language was already rendered (cache hit on assets table), returns 200 with no job.
PATCH  /subtitles/:id                         Body: { cues: [...]} 200
POST   /overlays                                                  201
PATCH  /overlays/:id                                              200
DELETE /overlays/:id                                              204
PATCH  /projects/:id/audio                    Body: { music_volume_db: number } 200

# Export (Screen 5)
POST   /projects/:id/export                   [Idempotency-Key]
  Body: { language: "en", quality: "1080p", subtitles: "burned" } 202 { job_id }
  # On success, advances project.status from 'ready' to 'completed'

# Assets
GET    /assets/:id                                                200 { signed_url, expires_at }
```

---

## 8. Worker pipeline

**The key change from the earlier draft: language-on-demand TTS.** Initial render produces visuals + primary-language audio + subtitles + composite. Other languages are generated only when the user picks them from the dropdown. Cached so switching back is instant.

### DAG (initial render, primary language only)

```
                    ┌────────────────────────────────────────┐
                    │  Phase A — storyboard (cheap, runs on  │
                    │  POST /storyboard/generate)            │
                    └──────────────────┬─────────────────────┘
                                       │
                       ┌───────────────▼───────────────┐
                       │  scene_engine_plan            │   Gemini Pro
                       │  Generates scenes + characters│   structured
                       └───────────────┬───────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
       ┌───────────────────┐                     ┌─────────────────────┐
       │ generate_         │                     │ generate_           │
       │ character_refs    │                     │ thumbnails          │
       │ (sdxl_image)      │                     │ (sdxl_image)        │
       └───────────────────┘                     └─────────────────────┘

                    ┌────────────────────────────────────────┐
                    │  Phase B — initial render (POST        │
                    │  /generate). Runs ONLY for             │
                    │  project.primary_language.             │
                    └──────────────────┬─────────────────────┘
                                       │
        ┌──────────────────────────────┼─────────────────────────────┐
        ▼                              ▼                             ▼
┌────────────────┐         ┌────────────────────┐       ┌────────────────────┐
│ render_scene_  │         │ generate_music     │       │ generate_voice     │
│ video          │         │ (acestep_music)    │       │ + subtitles        │
│ (ltx_render)   │ × N     │ once per project   │       │ per scene,         │
│ per scene      │         │                    │       │ primary_lang only  │
└───────┬────────┘         └──────────┬─────────┘       └─────────┬──────────┘
        │                             │                            │
        │                             │       per scene: voice → (gated)
        │                             │       lipsync → subtitles (parallel)
        │                             │                            │
        └─────────────┬───────────────┴────────────────────────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │ composite_scene     │  ← per scene, primary_language
            │ (ffmpeg_composite)  │
            └─────────────┬───────┘
                          │
                          ▼
            ┌─────────────────────┐
            │ final_export        │  ← project, primary_language
            │ (ffmpeg_composite)  │
            └─────────────────────┘
                          │
                          ▼
                  project.status = 'ready'
                  project.available_languages = [primary_language]
```

### DAG (language switch — runs on POST /regenerate-language)

```
For language L (where L != already-rendered):

   per scene S:
      ┌──────────────────────────────┐
      │ generate_voice(S, L)         │
      └──────────────┬───────────────┘
                     │
                     ▼  (only if S.has_speaker)
      ┌──────────────────────────────┐
      │ apply_lip_sync(S, L)         │   skipped if not has_speaker
      └──────────────┬───────────────┘
                     │
                     ▼
      ┌──────────────────────────────┐
      │ generate_subtitles(S, L)     │   reuses MediaPipe face data
      └──────────────┬───────────────┘
                     │
                     ▼
      ┌──────────────────────────────┐
      │ composite_scene(S, L)        │   reuses scene_video + music
      └──────────────┬───────────────┘
                     │
                     ▼
                final_export(L)

   On success:
     project.available_languages += L
     project.active_language = L
```

What's NOT regenerated on language switch:

- `scene_video` (LTX-Video output) — reused
- `character_ref` images — reused
- `thumbnails` — reused
- `music` — reused
- MediaPipe face-detection data — cached on the scene, reused

Roughly 10–20% of the cost of the initial render per language switch.

### Modal function signatures

```python
# modal_app/app.py
import modal

app = modal.App("vidplatform")
volume = modal.Volume.from_name("vidplatform-models", create_if_missing=True)

# Shared images per model family
ltx_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch==2.4.0", "diffusers", "transformers", "imageio[ffmpeg]"
)
sdxl_image_img = modal.Image.debian_slim(...).pip_install("diffusers", "transformers")
# ... etc

# Secrets
secrets = [
    modal.Secret.from_name("gemini-api-key"),
    modal.Secret.from_name("sarvam-api-key"),
    modal.Secret.from_name("aws-s3"),
    modal.Secret.from_name("database-url"),
    modal.Secret.from_name("redis-url"),
]
```

```python
# modal_app/functions/scene_video.py
@app.function(
    image=ltx_image,
    gpu="A100-40GB",
    volumes={"/models": volume},
    secrets=secrets,
    timeout=600,
    min_containers=0,        # scale to zero during dev
)
def ltx_render(scene_id: str) -> str:
    """Render scene_video for a scene. Returns asset_id."""
    scene = db_fetch_scene(scene_id)
    refs = load_character_refs(scene)
    video_path = ltx.run_i2v(
        prompt=scene.visual_prompt,
        conditioning_image=refs[0] if refs else last_frame_of_prev_scene(scene),
        duration_s=scene.duration_seconds,
    )
    return upload_and_register_asset(
        project_id=scene.project_id,
        scene_id=scene.id,
        asset_type="scene_video",
        language=None,
        local_path=video_path,
    )
```

```python
# modal_app/functions/lipsync.py
@app.function(image=musetalk_image, gpu="A10G", ...)
def apply_lip_sync(scene_id: str, language: str) -> str | None:
    """Returns asset_id, or None if the scene has no speaker."""
    scene = db_fetch_scene(scene_id)
    if not scene.has_speaker:
        return None  # GATING — no GPU consumed beyond container spin-up
    scene_video = load_asset(scene.scene_video_asset_id)
    voice = load_asset_by_type(scene.id, "voice", language)
    out = musetalk.sync(scene_video, voice)
    return upload_and_register_asset(...)
```

```python
# apps/worker/tasks/render_project.py
from celery import shared_task, group, chord
from app.modal_client import ltx_render, generate_music, generate_voice, \
    apply_lip_sync, generate_subtitles, composite_scene, final_export

@shared_task(bind=True, autoretry_for=(TransientError,), max_retries=3,
             retry_backoff=True, retry_jitter=True)
def render_project(self, project_id: str, language: str) -> str:
    """Phase B controller. Runs in the Celery worker on Fly.io; calls Modal
    functions via .spawn() (async submit) and .get() (await). One row in
    `render_jobs` tracks status; SSE events flow through Redis pub/sub.
    """
    job = db_create_job(project_id, "initial_render", language,
                        idempotency_key=self.request.id)
    project = db_fetch_project(project_id)
    scenes = db_list_scenes(project_id)

    # 1. Fan out visuals + music in parallel (Modal autoscales each GPU class).
    #    Each .spawn() returns a Modal FunctionCall; we record the call IDs on
    #    `render_jobs.modal_call_ids` so cancellation can reach Modal.
    visual_calls = [
        ltx_render.spawn(s.id) for s in scenes if not s.scene_video_asset_id
    ]
    music_call = generate_music.spawn(project_id) if project.music_enabled else None
    db_record_modal_calls(job.id, visual_calls + ([music_call] if music_call else []))
    publish_sse(project_id, "stage_change", {"stage": "scenes"})

    # 2. Wait for visuals + music — these are inputs to composite.
    for c in visual_calls:
        c.get()
        publish_sse(project_id, "scene_ready", {"scene_id": c.scene_id})
    if music_call:
        music_call.get()

    # 3. Per-scene language pipeline (voice → (lipsync) → subs → composite),
    #    parallel across scenes. We spawn from the worker thread; Modal
    #    handles GPU concurrency on its side.
    publish_sse(project_id, "stage_change", {"stage": "voice"})
    composite_calls = []
    for s in scenes:
        voice_id = generate_voice.remote(s.id, language)
        lipsync_id = apply_lip_sync.remote(s.id, language) if s.has_speaker else None
        generate_subtitles.spawn(s.id, language)         # parallel with composite below
        composite_calls.append(composite_scene.spawn(s.id, language))
    [c.get() for c in composite_calls]

    # 4. Final encode (CPU Modal fn).
    publish_sse(project_id, "stage_change", {"stage": "export"})
    export_asset_id = final_export.remote(project_id, language, "1080p", "burned")

    db_complete_job(job, final_export_asset_id=export_asset_id)
    db_update_project_status(project_id, "ready",
                             available_languages=[language],
                             active_language=language)
    publish_sse(project_id, "done",
                {"language": language, "final_export_asset_id": export_asset_id})
    return job.id
```

```python
# apps/worker/tasks/regen_language.py
@shared_task(bind=True, autoretry_for=(TransientError,), max_retries=3)
def regen_language(self, project_id: str, language: str) -> str | None:
    """Cheap language switch. Reuses all visuals + music."""
    project = db_fetch_project(project_id)
    if language in project.available_languages:
        # Already rendered. Just flip active_language and return — no Modal calls.
        db_update_project(project_id, active_language=language)
        return None

    job = db_create_job(project_id, "language_render", language,
                        idempotency_key=self.request.id)
    scenes = db_list_scenes(project_id)

    # Same per-scene pipeline as render_project, but visuals + music are skipped
    # because their content_hash is language-agnostic and already cached.
    composite_calls = []
    for s in scenes:
        generate_voice.remote(s.id, language)
        if s.has_speaker:
            apply_lip_sync.remote(s.id, language)
        generate_subtitles.spawn(s.id, language)
        composite_calls.append(composite_scene.spawn(s.id, language))
    [c.get() for c in composite_calls]

    export_asset_id = final_export.remote(project_id, language, "1080p", "burned")
    db_append_available_language(project_id, language)
    db_update_project(project_id, active_language=language)
    db_complete_job(job, final_export_asset_id=export_asset_id)
    publish_sse(project_id, "done",
                {"language": language, "final_export_asset_id": export_asset_id})
    return job.id
```

### Idempotency and caching

Two layers, complementary:

- **Celery `idempotency_key`** — the API issues an `Idempotency-Key` header on `/generate`, `/regenerate-language`, and `/export`. The worker writes it to `render_jobs.idempotency_key` (UNIQUE). A retry on the same key returns the in-flight or completed job rather than spawning a new pipeline.
- **Asset content-hash cache** — every Modal function computes a sha256 of its canonical input bundle and checks the `assets` table for a row with the same `content_hash`. On cache hit it returns the existing `asset_id` without doing GPU work. This is what makes retries free and language switches cheap (visuals reuse their hash; only audio + composite do real work).

---

## 9. Lip-sync gating

Two levels:

1. **Project-level** (`projects.has_characters`) — set during the chat in Screen 1 by an explicit question. If false, every scene defaults `has_speaker=false`, and MuseTalk is skipped throughout.

2. **Scene-level** (`scenes.has_speaker`) — defaults from `projects.has_characters`. Scene Engine auto-sets per scene by analysing the narration script (looks for quoted speech, dialogue verbs, character mentions). User can override via toggle on storyboard.

The `apply_lip_sync` function short-circuits when `scene.has_speaker = false`:

```python
if not scene.has_speaker:
    return None
```

`composite_scene` checks for the lip-sync asset and falls back to the raw `scene_video` when absent. No conditional branches in the DAG — just task-internal skips.

### Slot schema (collected during chat)

```python
{
  "video_type":         Literal["explainer", "cinematic", "social_reel", "ad"],
  "visual_style":       Literal["realistic", "animated", "documentary", "minimalist"],
  "duration_seconds":   int,                # 15, 30, 60, or custom
  "primary_language":   Literal["en", "hi", "mr", "ta", "pa"],
  "narration_tone":     Literal["energetic", "calm", "authoritative", "friendly"],
  "has_characters":     bool,               # → projects.has_characters → lipsync gate
  "music_enabled":      bool,               # default true
  "subtitles_enabled":  bool,               # default true
  "aspect_ratio":       Literal["16:9", "9:16", "1:1"],
  "topic":              str,                # what the video is about
}
```

Example chip question:

> "Will your video have people speaking on camera, or is it more voice-over with B-roll?"
> Chips: [`People speaking on camera`] [`Voice-over only`]

---

## 10. Language switching

Triggered by the dropdown on Screen 4 → `POST /projects/:id/regenerate-language { language: "hi" }`.

Flow:

1. API checks if `language ∈ project.available_languages`.
   - If yes → update `project.active_language`, return 200 immediately. Frontend re-fetches assets for that language and updates the player. **Instant switch for previously-rendered languages.**
   - If no → create a `render_jobs` row with `job_type='language_render'`, spawn `regen_language(project_id, language)` on Modal, return 202 with `job_id`. Frontend opens SSE to `/jobs/:id/events` and shows progress (typically 30–90 s).
2. On completion, `project.available_languages` is appended, `active_language` is updated, frontend re-fetches.

What's regenerated per scene:

- `generate_voice` (Sarvam Bulbul-v2 in the target language; uses Sarvam Translate first if script is in primary_language)
- `apply_lip_sync` (only if `scene.has_speaker`)
- `generate_subtitles` (Whisper alignment on the new voice; reuses cached MediaPipe face data)
- `composite_scene` (reuses cached `scene_video`, `character_refs`, `music`)
- `final_export` for the new language

What's reused: `scene_video`, `character_ref`, `thumbnail`, `music`, MediaPipe face data.

---

## 11. Music generation

Single instrumental track per project, generated once and reused across all language switches. **Primary model: ACE-Step 1.5** (`ACE-Step/Ace-Step1.5` on HuggingFace, Apache-2.0, ~3.5B params). Magenta RealTime kept wired as a fallback behind the same `MusicProvider` Protocol.

### Why ACE-Step 1.5 over Magenta RealTime

- Stronger musicality and instrumental depth at our duration target (15–60 s).
- Apache-2.0 weights with batch-friendly inference (Magenta RealTime is streaming-first; we always wanted a single MP3 anyway).
- Optional lyric conditioning if we ever want it (out of scope for MVP — instrumental only).
- Cost trade: ~3× larger than Magenta, runs on A10G ($1.10/hr) instead of T4 ($0.59/hr), ~30 s wall time vs ~35 s. ~$0.009 vs ~$0.006 per project. Negligible against the $30 cap.

### MusicProvider Protocol

```python
# apps/modal_app/providers/__init__.py
from typing import Protocol

class MusicProvider(Protocol):
    def synthesize(self, prompt: str, duration_s: float) -> Path:
        """Return a local MP3 path for a `duration_s`-second instrumental."""
```

Two impls:

- `apps/modal_app/providers/acestep.py` → primary, on `acestep_music` Modal fn (A10G).
- `apps/modal_app/providers/magenta.py` → fallback, on a swap-in `magenta_music` Modal fn (T4). Selected by env `MUSIC_PROVIDER=magenta` if ACE-Step weights or runtime become unstable.

The Modal worker `functions/music.py` resolves the provider at import time so the rest of the pipeline (composite, mixing, ducking) doesn't change.

### Prompt construction

```python
def music_prompt_from_brief(brief: dict) -> str:
    style = brief["visual_style"]              # e.g. "cinematic"
    tone = brief["narration_tone"]             # e.g. "energetic"
    video_type = brief["video_type"]
    return (
      f"Instrumental background music for a {video_type} video. "
      f"Style: {style}. Mood: {tone}. No vocals. Loopable."
    )
```

### Integration notes

- **ACE-Step**: load `ACE-Step/Ace-Step1.5` from HF cached on the Modal Volume; pin `ACESTEP_MODEL_REVISION` env so the demo is reproducible. Single forward pass → MP3 (no chunk concat).
- **Magenta** (fallback only): streaming loop emits 2-s chunks; concat to single MP3.
- Both write to `projects/{project_id}/music/main-{content_hash[:8]}.mp3`. `content_hash` includes `provider_name + revision + prompt + duration_s + seed`, so swapping providers invalidates the cache cleanly.

### FFmpeg mixing

- Music at –18 dB relative to voice.
- Sidechain ducking: when voice is present, music drops another 6 dB (smooth attack/release).
- Trim/loop music to project duration + 1 s fade-out.

If user disables music (`project.music_enabled = false`), `generate_music` is not invoked and `composite_scene` skips the music input.

---

## 12. Frontend screens

See `screenflow.md` for the full screen-by-screen specification, wireframes, state transitions, and API call patterns.

In summary, five screens:

1. **Chat** — slot-filling with chips, live summary card
2. **Storyboard** — scene grid with thumbnails, editable script + has_speaker toggle per scene
3. **Generation progress** — stepper + per-scene status + live preview
4. **Review & edit** — video player, timeline (scenes / waveform / subtitles / overlays / music), language dropdown, export CTA
5. **Export modal** — format + quality + subtitle option

---

## 13. Conversational edit (Screens 1, 2, and 4)

Conversation Orchestrator is a LangGraph state machine with **two modes wired from day one**. The same chat surface drives the whole product — collect on Screen 1, then edit on Screens 2 and 4 — so the user never has to hunt through menus.

### Collect mode (Screen 1)

Active while `project.status ∈ {draft, collecting}`. Three nodes:

- `extract_slots` — Gemini Flash structured output; merges any inferable slot values from the user message.
- `pick_next_question` — picks the next missing required slot; generates one question + 2-4 chips.
- `confirm_and_kickoff` — when all slots filled, emits a one-line summary + the "Start planning" CTA.

System prompt: `docs/prompts/conversation_system.md`.

### Edit mode (Screens 2 and 4)

Active while `project.status ∈ {planning, ready, completed}`. The chat drawer is collapsible and lives on the right edge of the storyboard / review screen. Five intents:

- `edit_scene(scene_index, field, new_value)` — script / visual_prompt / has_speaker / subtitle_position. Calls `PATCH /scenes/:id` then enqueues the appropriate Celery regen task if the field invalidates an asset (e.g., `visual_prompt` → re-run `ltx_render` for that scene).
- `regenerate_scene(scene_index, prompt_modifier?)` — calls `POST /scenes/:id/regenerate`.
- `edit_overlay(overlay_id?, action, args)` — add / move / delete / restyle CTA. Calls `POST/PATCH/DELETE /overlays`.
- `change_language(language)` — calls `POST /projects/:id/regenerate-language`. SSE forwards progress back into the chat as well as the player overlay.
- `ask_question(text)` — pure Q&A about the current project (uses brief + scene plan as context). No mutation.

Routing: `extract_intent` node classifies the user message via Gemini Flash structured output (`docs/prompts/edit_router_system.md`). On low confidence (< 0.6), the bot asks a clarifying question with chips suggesting the top-2 candidate intents.

### Shared concerns

- Both modes write to `conversation_messages` so the transcript persists across reloads.
- Tool calls go in `conversation_messages.tool_calls` (JSONB) so the chat panel can render an inline "✓ Updated scene 3" badge.
- Edit-mode tool calls are dry-run-able: the LLM emits the intent, the API echoes a one-line preview ("Will set scene 3 narration to '...'") and asks for confirmation via chips on destructive actions (`regenerate_scene`, `change_language`).

### Implementation note

Both modes share the same `POST /projects/:id/chat` SSE endpoint. The orchestrator picks mode by reading `project.status`. There is one LangGraph object with two compiled subgraphs — collect and edit — selected at the entry router node.

---

## 14. Asset storage layout (S3)

Single bucket `vidplatform`. Keys are content-addressed:

```
projects/{project_id}/
  thumbnails/{scene_index}-{content_hash[:8]}.jpg
  character_refs/{character_id}-{content_hash[:8]}.jpg
  scene_videos/{scene_index}-{content_hash[:8]}.mp4
  music/main-{content_hash[:8]}.mp3
  voices/{lang}/{scene_index}-{content_hash[:8]}.wav
  lipsync/{lang}/{scene_index}-{content_hash[:8]}.mp4
  subtitles/{lang}/{scene_index}-{content_hash[:8]}.srt
  composites/{lang}/{scene_index}-{content_hash[:8]}.mp4
  exports/{lang}/final-{content_hash[:8]}.mp4
```

**Signed URLs** issued on `GET /assets/:id` with 1-hour TTL via `boto3.generate_presigned_url`. The frontend never holds AWS credentials.

**Free tier budget.** AWS S3 free tier (12 months) gives 5 GB storage + 20k GET + 2k PUT/month. A typical 30-second video at 1080p is ~10 MB; 50 demo renders + assets fits well within 5 GB. Watch the PUT count — content addressing means we PUT once per unique artifact, so this is fine in practice.

---

## 15. Deployment

### Local development (Docker Compose)

```yaml
# infra/docker-compose.dev.yml — abbreviated
services:
  postgres:   { image: postgres:16, env: POSTGRES_PASSWORD=dev }
  redis:      { image: redis:7 }                               # Celery broker + SSE pub/sub
  minio:      { image: minio/minio, command: server /data }    # local S3 substitute
  api:        { build: ../apps/api, depends_on: [postgres, redis, minio] }
  worker:     { build: ../apps/worker, depends_on: [postgres, redis] }   # Celery worker
  web:        { build: ../apps/web, ports: ["3000:3000"] }
```

GPU worker functions run on Modal even during dev — `modal serve modal_app/app.py` mounts the local code into Modal containers with hot reload. No GPU needed locally. The Celery worker calls them via `.spawn()` exactly the same way it will in production.

### Production / demo deployment (Oracle Cloud Always-Free)

| Component | Where | Cost |
|---|---|---|
| Frontend | Vercel free tier or served from the same OCI VM via nginx | $0 |
| API service + Celery worker | **OCI Ampere A1 Always-Free VM** (4 OCPU / 24 GB RAM, ARM64), two Docker containers behind nginx (TLS via Let's Encrypt) | $0 |
| Postgres | Same VM (`postgres:16-alpine` container) — or OCI Autonomous DB Always-Free (20 GB) | $0 |
| Object store | AWS S3 free tier *or* OCI Object Storage with the S3-compatibility API (Always-Free 20 GB) | $0 |
| Redis (broker + SSE pubsub) | Same VM (`redis:7-alpine`) — or Upstash free tier (10k cmds/day) | $0 |
| GPU workers | Modal Starter plan ($30 free credit/month) | $0 within credit |
| Sarvam API | Pay-as-you-go | Charged per TTS request |
| Gemini API | Pay-as-you-go (Gemini 3.1 Flash-Lite is cheap) | Charged per token |

### Required environment variables

```
# API + worker (running on the OCI VM)
DATABASE_URL=postgresql+asyncpg://vidplatform:<pw>@postgres:5432/vidplatform
REDIS_URL=redis://redis:6379/0      # or rediss://...@upstash
S3_ENDPOINT_URL=                    # blank for AWS S3; set for OCI S3-compat
S3_BUCKET=vidplatform
S3_REGION=us-ashburn-1              # or us-east-1 for AWS
AWS_ACCESS_KEY_ID=...               # OCI customer-secret access key works here
AWS_SECRET_ACCESS_KEY=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.1-flash-lite
SARVAM_API_KEY=...
MODAL_TOKEN_ID=...
MODAL_TOKEN_SECRET=...

# Modal functions get secrets via `modal.Secret.from_name("...")`. Create once:
modal secret create gemini-api-key GEMINI_API_KEY=...
modal secret create sarvam-api-key SARVAM_API_KEY=...
modal secret create aws-s3 AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... S3_ENDPOINT_URL=...
modal secret create database-url DATABASE_URL=...
modal secret create redis-url REDIS_URL=...

# Frontend
NEXT_PUBLIC_API_BASE_URL=https://<your-domain>
```

### Deployment commands

```bash
# 1. Provision a free OCI Ampere A1 VM (Ubuntu 22.04 ARM64, 4 OCPU / 24 GB).
#    Open ports 80 and 443 in the VCN security list.
# 2. Bootstrap (once, on the VM):
ssh ubuntu@$OCI_VM_PUBLIC_IP 'bash -s' < infra/oracle/bootstrap.sh

# 3. Push code + restart (every deploy):
bash infra/oracle/deploy.sh

# 4. Run migrations on the VM (one-shot):
ssh ubuntu@$OCI_VM_PUBLIC_IP 'cd /srv/vidplatform && docker compose -f infra/oracle/docker-compose.prod.yml run --rm api alembic upgrade head'

# 5. Deploy Modal GPU workers:
modal deploy apps/modal_app/app.py

# Deploy frontend
cd apps/web && vercel deploy --prod
```

---

## 16. Out of scope (deliberate cuts)

| Item | Where it would slot in |
|---|---|
| 4K export, chapter markers, MOV | `final_export` task — quality preset + ffmpeg flags |
| Email notifications | Modal function emits to SES on `done` event |
| Share preview links | Public-read signed URLs with longer TTL behind feature flag |
| Save draft / multi-project | Already in DB; needs auth + project list UI |
| Drag-to-reorder scenes | Use up/down buttons; `POST /scenes/:id/move` exists |
| Per-entry subtitle styling | `subtitles.cues[i].style` is in the schema, just not surfaced |
| Mobile review screen | Timeline collapses to bottom sheet; not built |
| User accounts | API has no auth middleware in MVP |
| Undo history | `project_versions` table snapshotting scenes/overlays |
| Audio mixing controls beyond music volume | FFmpeg composite already mixes — surface more knobs |

---

## 17. Open implementation questions

1. **LTX-Video variant.** Default to `ltxv-13b-0.9.7-distilled-fp8` on A100 40GB. If quality of motion is poor, fall back to `ltxv-13b-dev` (FP16). Decide after first end-to-end render test.
2. **ACE-Step 1.5 batch wrapper.** Single-pass forward inference is the goal. If the HF model card's example pipeline is unstable on Modal A10G, fall back to Magenta RealTime (already wired behind `MusicProvider` Protocol — flip `MUSIC_PROVIDER=magenta`).
3. **Scene continuity.** Default to last-frame conditioning for scene N+1. Fall back to explicit character refs if identity preservation degrades across >3 consecutive scenes.
4. **Speech detection in Scene Engine.** Heuristics first (quoted speech, dialogue verbs). Upgrade to Gemini returning `has_speaker: bool` per scene as part of structured output.
5. **Sarvam rate limits.** Confirm Bulbul-v2 concurrency; batch TTS calls if low.
6. **FFmpeg concat.** Use the `concat` demuxer with re-encode for safety (mismatched timestamps cause issues with stream-copy concat). Accept the extra encode time.
7. **Subtitle position auto-decision.** MediaPipe runs on N=5 sampled frames per scene. If face bbox vertical centre is in bottom 33% of frame for ≥3 of 5 frames, choose `top`; else `bottom`.
8. **Modal cold starts.** A100 cold start is ~30–60 s. For the demo, `modal warm vidplatform` before the interview to pre-spin containers.
9. **Edit-mode intent confidence threshold.** Empirically tune the < 0.6 cutoff after dogfooding. Too aggressive → annoying clarifications; too loose → wrong action taken.
10. **Celery worker concurrency.** Start at `--concurrency=4` on the Fly.io shared-cpu-1x. Scene fan-out runs on Modal so Celery is mostly I/O-bound (waiting on `.get()`); 4 in-flight projects fits.

---

## 18. Implementation order

Build vertically, not horizontally. Get one scene rendering end-to-end before adding language switching, music, or any UI polish.

| Day | Goal | Test |
|---|---|---|
| 1 | Scaffolding: Postgres, Redis, S3, Modal app, FastAPI, **Celery worker**, Next.js — all wired end-to-end with a "hello world" Modal function the Celery worker spawns and that writes to S3 + DB + Redis SSE | Browser → API → Celery task → Modal fn → asset row in DB → SSE event to browser |
| 2 | Storyboard path: chat collects brief → Gemini scene plan → SDXL thumbnails (Phase A) | Storyboard renders with 3+ thumbnails from a single chat |
| 3 | Single-scene full render (English): LTX I2V → Sarvam TTS → Whisper subs → FFmpeg composite | Watch a 6-second video with narration + subs |
| 4 | Multi-scene + final export, driven by `render_project` Celery task fanning out via Modal `.spawn()` | 30-second multi-scene video plays end-to-end |
| 5 | Lip-sync (gated): MuseTalk integration + Screen 2 speaker toggle | Toggle a scene; lipsync runs only when on |
| 6 | Language switch: `/regenerate-language` Celery task + dropdown + content-hash cache + edit-mode chat for "switch to Hindi" intent | Switch to Hindi via dropdown AND via chat; second switch instant |
| 7 | **ACE-Step music** + sidechain ducking + overlays + subtitle editor + edit-mode chat for scene/overlay edits in Screens 2 + 4 | All 5 screens working; chat can edit a scene script and trigger regen |
| 8 | Polish: README, ARCHITECTURE.md cross-links, Modal warm script, Loom recording, deploy on Fly + Modal | Live URL for reviewer + recorded demo |

Cut features aggressively if it slips — the architecture supports them, the submission doesn't have to include them. Recommended cut order if needed: (i) edit-mode chat in Screen 4 (keep in Screen 2), (ii) overlays editor (keep schema, ship one CTA from Timeline), (iii) lip-sync (gating already lets us skip cleanly), (iv) language switch beyond one alt language. Never cut: chat → storyboard → single-scene render → export.

---

## 19. System prompts (sketches)

The three LLM-driven nodes need explicit, committed system prompts. Stored in `docs/prompts/`.

### conversation_system.md

```
You are the requirement-gathering host for an AI video generation platform. Your goal:
collect a complete brief from the user via a friendly, one-question-at-a-time conversation.

REQUIRED SLOTS (collect in any order, infer where possible):
- video_type:     explainer | cinematic | social_reel | ad
- visual_style:   realistic | animated | documentary | minimalist
- duration_seconds: int (15, 30, 60, or custom)
- primary_language: en | hi | mr | ta | pa
- narration_tone: energetic | calm | authoritative | friendly
- has_characters: bool (people speaking on camera?)
- music_enabled:  bool
- subtitles_enabled: bool
- aspect_ratio:   16:9 | 9:16 | 1:1
- topic:          free-text description

INFERENCE RULES:
- "Instagram reel" / "TikTok" → aspect_ratio=9:16, video_type=social_reel
- "YouTube ad" → aspect_ratio=16:9, video_type=ad
- "presenter talking to camera" → has_characters=true
- "drone footage" / "B-roll" / "voice-over only" → has_characters=false
- Numeric duration in user message → fill duration_seconds directly

OUTPUT FORMAT (structured):
On every turn, emit JSON:
{
  "slot_updates": {<slot>: <value>, ...},
  "next_question": "<one short question for the user>",
  "chips": ["<chip 1>", "<chip 2>", "..."]  // 2-4 short tappable options
  "ready": false   // true only when all required slots filled
}

CONSTRAINTS:
- Ask at most ONE question per turn
- Always provide chips (mobile-friendly); user can also type
- When ready, output ready=true and a one-sentence summary in next_question
- Never invent slot values the user didn't provide
```

### scene_engine_system.md

```
You are the scene planner for an AI video generation platform.

INPUT: a project brief (video_type, visual_style, duration_seconds, narration_tone,
       has_characters, topic, ...).

OUTPUT (structured JSON):
{
  "scenes": [
    {
      "scene_index": 1,
      "duration_seconds": 5,
      "visual_prompt": "<detailed cinematographic prompt for LTX-Video, 1 paragraph,
                        chronological, include camera angle and lighting>",
      "narration_script": "<the words the narrator will say in primary_language>",
      "has_speaker": true | false,
      "character_names": ["<name>", ...],  // if has_speaker, who speaks
      "subtitle_position": "auto"  // default; user can override
    },
    ...
  ],
  "characters": [
    {
      "name": "<name>",
      "description": "<detailed visual description for SDXL-Turbo>"
    },
    ...
  ]
}

RULES:
- Total scenes ≈ duration_seconds / 6 (i.e., ~6s per scene, range 4-10s).
- visual_prompt MUST follow LTX-Video conventions: chronological, ≤200 words,
  start with the action, literal/precise, include camera + lighting.
- narration_script word count should target ~2.5 words/second.
- has_speaker = true only if a person is visible on camera AND speaking in this scene.
  Pure voice-over with B-roll = has_speaker false.
- If the brief's has_characters=false, every scene's has_speaker must be false.
- Reuse character names across scenes for continuity.
```

### edit_router_system.md (stubbed for future)

```
You are the edit-intent router for an AI video generation platform.
Classify the user's message into ONE of: edit_scene | change_language | regenerate_scene
| edit_overlay | ask_question | unknown.

OUTPUT (structured JSON):
{
  "intent": "<one of above>",
  "args": {<intent-specific args>}
}

For MVP, this is wired but not exposed in the UI — feature flag EDIT_MODE_ENABLED.
```

---

## 20. Cost budget (Modal $30 credit)

Estimated GPU-seconds per *initial* render of a 30-second, 5-scene video, English only:

| Stage | Function | GPU | Time per call | Calls | Total GPU-s | $ at base rate |
|---|---|---|---|---|---|---|
| Thumbnails | sdxl_image | A10G | 2 s | 5 | 10 | $0.003 |
| Char refs | sdxl_image | A10G | 2 s | 2 | 4 | $0.001 |
| Scene videos | ltx_render | A100 40GB | 10 s | 5 | 50 | $0.029 |
| Music (ACE-Step 1.5) | acestep_music | A10G | 30 s | 1 | 30 | $0.009 |
| Voice | sarvam (cloud) | — | — | 5 | — | ~$0.05 (Sarvam) |
| Subtitles | whisper_align | T4 | 3 s | 5 | 15 | $0.002 |
| Lip-sync (gated) | musetalk_sync | A10G | 8 s | 2 | 16 | $0.005 |
| Composite | ffmpeg_composite | CPU | 4 s | 5 | 20 | $0.001 |
| Final export | ffmpeg_composite | CPU | 6 s | 1 | 6 | $0.000 |
| **Total per render** | | | | | | **~$0.10** |

Plus container cold-start time (~30–60s on A100, ~10s on smaller GPUs) and the 1.25× US-region multiplier → ~$0.12–0.15 per full demo. **$30 ÷ ~$0.13 ≈ 230 full renders.** Plenty for development + demo, with budget headroom for ACE-Step quality experiments.

Each language switch is ~10–20% of the above (only voice + optional lipsync + subs + composite + final export, since visuals + music are content-hash cache hits) → ~$0.015–0.020. Adding all 4 alternative languages costs ~$0.06 per project — trivial.

### Cost-saving rules of thumb

- `min_containers=0` for everything during development
- For the live demo, set `min_containers=1` only on `ltx_render` and `sdxl_image` 30 minutes before the interview
- Use the Modal dashboard to confirm idle containers shut down after a run
- Don't render the full 30-second video on every test — test individual stages in isolation first

---

## 21. Testing approach

For an interview project, full test coverage is overkill, but you want enough confidence that the demo doesn't break live. Recommended:

- **Smoke tests** (pytest, in `apps/api/tests/`): one test per endpoint hitting the happy path with mocked Modal calls
- **Pipeline unit tests** for the Scene Engine (assert structure of Gemini's JSON output across 3-5 sample briefs)
- **One end-to-end test** with real Modal calls but a tiny scene (1 scene, 2-second video) — gated behind an env flag so it doesn't run on every push
- **Manual demo script** in `docs/demo.md` — exact prompts to type, expected screens, fallback if something fails (e.g., "if storyboard generation times out, refresh page; cached state survives")

Don't write tests for the LLM-driven nodes' output content. Their behaviour is non-deterministic; test the *plumbing* (does the right function get called with the right args, does the DB get updated) rather than the *outputs*.

---

## 22. Submission checklist

Before handing in:

- [ ] Architecture diagram (rendered SVG) embedded in the doc
- [ ] README with one-command local dev (`docker compose up` + `modal serve`)
- [ ] `architecture.md` (this file)
- [ ] `screenflow.md` (companion doc)
- [ ] System prompts checked in under `docs/prompts/`
- [ ] Loom recording (~5 min) walking through the demo end-to-end, in one language and showing the language switch
- [ ] Honest "what I didn't get to" section in README — out-of-scope list mirrors §16

---
*End of architecture.md*
