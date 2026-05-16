# Infrastructure Guide

This document covers the local development and production infrastructure for the
`vidplatform` AI video generation platform.

---

## Overview

The platform runs as four Docker services orchestrated by Compose, with GPU work
offloaded to Modal serverless functions.

```
┌──────────────┐   REST/SSE   ┌─────────────┐
│  Next.js web │ ──────────── │  FastAPI     │
│  (port 3000) │              │  (port 8000) │
└──────────────┘              └──────┬───────┘
                                     │ enqueue
                               ┌─────▼───────┐
                               │ Celery      │
                               │ worker      │
                               └──────┬───────┘
                                      │ .spawn()
                               ┌──────▼───────┐    ┌──────────────┐
                               │ Modal GPU    │    │  S3 / OCI    │
                               │ functions    │    │  Object Store│
                               └──────────────┘    └──────────────┘
```

Redis plays two roles: Celery task broker and SSE pub/sub fan-out.
Postgres is the single source of truth for project, scene, and job state.

---

## Development

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- `modal` CLI (`pip install modal && modal token new`)
- AWS credentials with S3 access **or** any S3-compatible store

### Quick start

```bash
cp .env.example .env
# Fill in GEMINI_API_KEY, SARVAM_API_KEY, AWS_*, MODAL_TOKEN_*

docker compose -f infra/docker-compose.dev.yml up --build
```

Open `http://localhost:3000` once all containers are healthy.

In a separate terminal, mount Modal GPU workers with hot reload:

```bash
modal serve apps/modal_app/app.py
```

The Celery worker calls Modal via `.spawn()` / `.get()` — the same path as
production. No GPU is needed locally; Modal handles container lifecycle.

### Services (dev)

| Service | Image / build | Port | Notes |
|---------|--------------|------|-------|
| `redis` | `redis:7-alpine` | 6379 | Celery broker + SSE pub/sub |
| `api` | `infra/docker/api.Dockerfile` | 8000 | FastAPI + Uvicorn |
| `worker` | `infra/docker/worker.Dockerfile` | — | Celery; `MODAL_STUB=0` disables real Modal calls |
| `web` | `infra/docker/web.Dockerfile` | 3000 | Next.js |

**Database** in dev uses `DATABASE_URL` from `.env` — typically a local or
cloud-hosted Postgres 16 instance (not managed by this Compose file).
**Object storage** uses the AWS credentials from `.env` — point at AWS S3 or
any S3-compatible endpoint via `S3_ENDPOINT_URL`.

### Key environment variables (dev)

See `.env.example` for the full list. Minimum set for a working local dev
environment:

```
GEMINI_API_KEY=          # Google AI Studio key
SARVAM_API_KEY=          # Sarvam API key (TTS + translate)
MODAL_TOKEN_ID=          # from `modal token new`
MODAL_TOKEN_SECRET=
DATABASE_URL=postgresql+asyncpg://vidplatform:dev@<host>:5432/vidplatform
S3_BUCKET=vidplatform
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
REDIS_URL=redis://redis:6379/0   # overridden inside Compose
```

Set `MODAL_STUB=1` to stub out all Modal GPU calls (returns dummy asset IDs).
Useful for iterating on API logic without spending Modal credits.

### Running migrations

```bash
docker compose -f infra/docker-compose.dev.yml run --rm api alembic upgrade head
```

---

## Production

Production runs on a single **Oracle Cloud Infrastructure Always-Free Ampere A1**
VM (4 OCPU / 24 GB RAM, ARM64, Ubuntu 22.04). All services are Docker containers
behind an Nginx TLS proxy. Modal GPU workers run on Modal's infrastructure.

### Architecture

```
Internet
   │ 80 / 443
   ▼
┌──────────────────────────────────────────────┐
│  OCI Ampere A1 VM  (ap-mumbai-1 or similar)  │
│                                              │
│  nginx:1.27-alpine                           │
│   ├─ HTTP → 301 HTTPS (+ ACME passthrough)   │
│   └─ HTTPS → proxy_pass http://api:8000      │
│              (SSE endpoints: buffering off)  │
│                                              │
│  api          (infra/docker/api.Dockerfile)  │
│  worker       (infra/docker/worker.Dockerfile│
│  postgres:16-alpine  /srv/vidplatform/data/  │
│  redis:7-alpine      /srv/vidplatform/data/  │
└──────────────────────────────────────────────┘
         │  .spawn() / .get()
         ▼
  Modal serverless GPU functions
  (ltx_render · sdxl_image · musetalk_sync
   acestep_music · whisper_align · ffmpeg_composite)
         │
         ▼
  S3 / OCI Object Storage  (s3-compat API)
```

TLS certificates are issued by Let's Encrypt via `certbot --standalone` and
stored at `/etc/letsencrypt` on the host; Nginx mounts them read-only.

### One-time bootstrap

Run once on a fresh VM:

```bash
ssh ubuntu@$OCI_VM_PUBLIC_IP 'bash -s' < infra/oracle/bootstrap.sh
```

This installs Docker Engine, opens firewall ports 80/443 via UFW, creates
`/srv/vidplatform/{data/postgres,data/redis}`, and installs the `vidplatform`
systemd unit so the Compose stack auto-starts on reboot.

Then issue a TLS certificate (before starting Nginx):

```bash
ssh ubuntu@$OCI_VM_PUBLIC_IP \
  'certbot certonly --standalone -d <your-domain>'
```

Copy your filled `.env` to the VM:

```bash
scp -i $OCI_SSH_KEY_PATH .env ubuntu@$OCI_VM_PUBLIC_IP:/srv/vidplatform/.env
```

Run database migrations (once):

```bash
ssh ubuntu@$OCI_VM_PUBLIC_IP \
  'cd /srv/vidplatform && docker compose -f infra/oracle/docker-compose.prod.yml run --rm api alembic upgrade head'
```

Deploy Modal GPU workers (once, then on every `apps/modal_app` change):

```bash
modal deploy apps/modal_app/app.py
```

Create Modal secrets (once):

```bash
modal secret create gemini-api-key   GEMINI_API_KEY=...
modal secret create sarvam-api-key   SARVAM_API_KEY=...
modal secret create aws-s3           AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... S3_ENDPOINT_URL=...
modal secret create database-url     DATABASE_URL=postgresql+asyncpg://vidplatform:<pw>@postgres:5432/vidplatform
modal secret create redis-url        REDIS_URL=redis://redis:6379/0
```

### Deploying an update

From the repo root on your laptop:

```bash
bash infra/oracle/deploy.sh
```

This rsyncs the source tree to `/srv/vidplatform` on the VM (excluding `.venv`,
`node_modules`, `.next`, `.git`, `__pycache__`, `.DS_Store`, and
`video generation platform/`) then runs
`docker compose -f infra/oracle/docker-compose.prod.yml up -d --build`.

### Services (prod)

| Service | Image / build | Exposed | Notes |
|---------|--------------|---------|-------|
| `postgres` | `postgres:16-alpine` | internal | Data at `/srv/vidplatform/data/postgres` |
| `redis` | `redis:7-alpine` | internal | Data at `/srv/vidplatform/data/redis` |
| `api` | `infra/docker/api.Dockerfile` | internal (8000) | Depends on postgres health-check |
| `worker` | `infra/docker/worker.Dockerfile` | — | Depends on postgres + api started |
| `nginx` | `nginx:1.27-alpine` | 80, 443 | TLS termination; mounts Let's Encrypt certs |

Postgres and Redis data is written to host paths under `/srv/vidplatform/data/`
so it survives container restarts and upgrades.

### Nginx notes

- Plain HTTP on port 80 → 301 HTTPS redirect (ACME-challenge passthrough for
  certificate renewals).
- `client_max_body_size 100m` — supports asset PUTs up to 100 MB (~30s 1080p).
- SSE endpoints (`/jobs/*/events`, `/projects/*/chat`) have `proxy_buffering off`
  and a 3600s `proxy_read_timeout` so frames flush immediately and long-running
  renders stay connected.
- Default `proxy_read_timeout` for other endpoints is 600s to cover slow LLM
  calls.

### Systemd unit

`infra/oracle/vidplatform.service` is installed by `bootstrap.sh` and set to
`enable` so the Compose stack comes up automatically after a VM reboot.

Tail logs:

```bash
ssh -i $OCI_SSH_KEY_PATH ubuntu@$OCI_VM_PUBLIC_IP \
  'cd /srv/vidplatform && docker compose -f infra/oracle/docker-compose.prod.yml logs -f --tail=100'
```

### Production environment variables

These live in `/srv/vidplatform/.env` on the VM (never committed to git):

```
DATABASE_URL=postgresql+asyncpg://vidplatform:<pw>@postgres:5432/vidplatform
REDIS_URL=redis://redis:6379/0
S3_BUCKET=vidplatform
S3_REGION=us-east-1          # or OCI region
S3_ENDPOINT_URL=             # blank for AWS; set for OCI S3-compat
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.1-flash-lite
SARVAM_API_KEY=
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
MODAL_STUB=0                 # 0 = real Modal GPU calls
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ORIGINS=["https://<your-domain>"]
NEXT_PUBLIC_API_BASE_URL=https://<your-domain>
OCI_VM_PUBLIC_IP=<ip>
OCI_SSH_KEY_PATH=~/.ssh/oci_vidplatform
```

---

## File map

```
infra/
├── docker-compose.dev.yml          Local dev stack (redis · api · worker · web)
├── docker/
│   ├── api.Dockerfile              FastAPI + Uvicorn image (build ctx: repo root)
│   ├── worker.Dockerfile           Celery worker image
│   └── web.Dockerfile              Next.js image
└── oracle/
    ├── bootstrap.sh                One-shot VM provisioning script
    ├── deploy.sh                   rsync + compose up — run from laptop
    ├── docker-compose.prod.yml     Production stack (adds postgres · nginx)
    ├── nginx.conf                  TLS proxy config with SSE-friendly settings
    └── vidplatform.service         systemd unit (auto-start on reboot)
```

---

## Cost summary

All infrastructure tiers used are free or within the demo budget.

| Component | Provider | Cost |
|-----------|----------|------|
| API + worker + Postgres + Redis | OCI Always-Free Ampere A1 | $0/month |
| Object storage | AWS S3 free tier (5 GB / 12 mo) or OCI Always-Free (20 GB) | $0 |
| Redis (alternative) | Upstash free tier (10k cmds/day) | $0 |
| GPU workers | Modal ($30 starter credit; ~$0.13/full render) | ~$0 for demo |
| Frontend | Vercel free tier | $0 |
| LLM | Google AI Studio (Gemini Flash-Lite) | Pay-per-token |
| TTS + translate | Sarvam API | Pay-per-request |
