# Conversational Multilingual AI Video Platform

Chat-driven platform that produces cinematic multilingual videos with lip-sync, subtitles, animated overlays, music, and export-ready rendering. Five supported languages: English, Hindi, Marathi, Tamil, Punjabi. Language switching reuses visual scenes (only voice + lip-sync + subtitles + composite re-render per added language).

## Read first

- **[docs/architecture.md](docs/architecture.md)** — system design, data model, worker pipeline, deployment. Source of truth.
- **[docs/screenflow.md](docs/screenflow.md)** — UI screens, components, state transitions. Source of truth for the frontend.
- **[task.md](task.md)** — the candidate brief.
- **[docs/prompts/](docs/prompts/)** — system prompts for the conversation orchestrator, scene engine, and edit router.

## Layout

```
apps/
  api/         FastAPI service — chat, scene plan, REST + SSE
  worker/      Celery pipeline orchestrator (CPU)
  modal_app/   Modal serverless GPU workers
                ├── functions/    leaf workers per model
                ├── models/       model loaders (LTX, SDXL, MuseTalk, Whisper, ACE-Step, MediaPipe)
                └── providers/    Sarvam + Gemini + MusicProvider Protocol (ACE-Step + Magenta)
  web/         Next.js 14 frontend (5 screens)
infra/
  docker/                    api/worker/web Dockerfiles
  docker-compose.dev.yml     Local: postgres + redis + minio + api + worker + web
  oracle/                    Oracle Cloud Always-Free VM deployment
db/migrations/               Alembic
docs/
  prompts/                   Committed LLM system prompts
```

## Quick start (local dev)

Prereqs: Docker, Node 20+, Python 3.11+, [Modal CLI](https://modal.com/docs/guide/setup) authenticated.

```bash
# 1. Setup Python env + install requirements
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure secrets
cp .env.example .env                # fill GEMINI_API_KEY, SARVAM_API_KEY, MODAL_*

# 3. Bring up the full stack (postgres + redis + minio + api + worker + web)
docker compose -f infra/docker-compose.dev.yml up --build

# 4. Run migrations once
docker compose -f infra/docker-compose.dev.yml exec api alembic upgrade head

# 5. (Separate terminal) GPU workers — `modal serve` hot-reloads
modal serve apps/modal_app/app.py
```

Open `http://localhost:3000`, click "Start a new video", and walk through Chat → Storyboard → Generate → Review → Export.

For an offline / no-Modal-credentials run, set `MODAL_STUB=1` in `.env` — every Modal call returns a deterministic stub instead of touching GPUs.

## Production deployment (Oracle Cloud Always-Free)

The API + Celery worker + Postgres + Redis run as Docker containers on a single Oracle Cloud Always-Free **Ampere A1 VM** (4 OCPU / 24 GB RAM, ARM64 — $0/month forever). GPU workers run on Modal. Object storage is AWS S3 (free tier) or OCI Object Storage with the S3-compat API.

```bash
# One-time bootstrap of a fresh OCI VM
ssh ubuntu@$OCI_VM_PUBLIC_IP 'bash -s' < infra/oracle/bootstrap.sh

# Routine deploys (rsync source + docker compose up)
bash infra/oracle/deploy.sh

# Modal GPU workers (one-time + on changes)
modal deploy apps/modal_app/app.py
```

Full step-by-step in **[infra/oracle/README.md](infra/oracle/README.md)** including TLS issuance with Let's Encrypt, systemd auto-start, and database migrations.

## Tech highlights

| Layer | Choice | Why |
|---|---|---|
| LLM (chat + scene plan + edit router) | **Gemini 3.1 Flash-Lite** via Google AI Studio | Cheap, fast, JSON-native; one model across all three roles |
| Conversation graph | **LangGraph** `StateGraph` | One graph object, two compiled subgraphs (collect + edit), selected by `project.status` |
| Pipeline orchestration | **Celery** (broker = Redis) | Fans per-scene work out via Modal `.spawn()`; full DAG in regular Python — debuggable, deployable, mockable |
| GPU compute | **Modal** | One Modal function per model, each pinned to the smallest GPU class. Scale-to-zero between renders |
| Music | **ACE-Step 1.5** (Apache-2.0); Magenta RealTime fallback behind a `MusicProvider` Protocol | Higher quality at our duration target; provider swap is one env var |
| Multilingual narration | Sarvam **Bulbul-v2** TTS + Sarvam **Translate** | SOTA for the five Indian languages |
| Lip-sync | **MuseTalk** (gated by `scene.has_speaker`) | Modern, A10G-friendly |
| Subtitle alignment | **Whisper large-v3** word-level forced alignment | Powers the in-app subtitle editor |
| Subtitle position | **MediaPipe** face detection (5-frame sample) | Auto-flips between top / bottom to avoid faces |
| Compositing | FFmpeg with sidechain ducking | Music drops 6 dB under voice |
| Asset cache | sha256 content-hash on every artifact | Retries free; language switches cheap (only audio + composite re-render) |

See `architecture.md` §3, §4, §11, §13 for the full rationale.

## What's not in scope (and where it would slot in)

See `architecture.md` §16. Notable cuts: auth, project list, undo history, mobile review screen, drag-to-reorder scenes (POST /scenes/:id/move exists for arrow buttons), per-cue subtitle styling (one global style), multi-track audio mixing beyond music volume.

**In scope and shipping**: conversational edit on Screens 2 + 4 — the same chat surface drives slot-fill on Screen 1 and edit-intent routing on Screens 2 and 4 via the LangGraph router.

## Cost (Modal $30 starter credit)

A 30 s, 5-scene video (English) costs ~$0.10 to render initially; each language switch costs ~$0.015–0.02. ~230 full demos within the credit. See `architecture.md` §20.
