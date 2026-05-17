# Infrastructure & Deployment Guide

This guide covers everything needed to run **vidplatform** — locally for development and in production on **AWS EC2**.

---

## Overview

The platform is a four-service monorepo. GPU-heavy work (video generation, lip-sync, speech alignment) is offloaded to [Modal](https://modal.com) serverless functions, so the EC2 host only needs to run CPU services.

```
┌────────────────────────────────────────────────────────────┐
│  Browser                                                   │
└──────────────────────┬─────────────────────────────────────┘
                       │ HTTPS (443)
               ┌───────▼────────┐
               │  nginx (TLS)   │  port 80 → 301 redirect
               └───────┬────────┘  SSE buffering off
                       │ proxy_pass :8000
               ┌───────▼────────┐
               │  FastAPI / API │  port 8000 (internal)
               └───────┬────────┘
          ┌────────────┼─────────────┐
          │            │             │
    Postgres        Redis        Gemini / Sarvam
    (port 5432)   (port 6379)   (external APIs)
          │            │
          │    ┌───────▼────────┐
          │    │ Celery worker  │
          └────┴───────┬────────┘
                       │ .spawn() / .get()
               ┌───────▼────────┐      ┌─────────────────┐
               │  Modal GPU fns │ ───► │  AWS S3 bucket  │
               └────────────────┘      └─────────────────┘
```

**Redis** serves two roles: Celery task broker and SSE pub/sub fan-out for real-time progress updates.  
**Postgres** is the single source of truth for projects, scenes, jobs, and assets.  
**Modal** runs all GPU inference (LTX-Video, SDXL, LatentSync, Whisper, ffmpeg composite).  
**S3** stores all generated assets (thumbnails, scene videos, voice clips, exports).

---

## Prerequisites

### Accounts & API keys

| Service | What for | Get it at |
|---------|----------|-----------|
| Google AI Studio | Gemini LLM (storyboard + chat) | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Sarvam AI | Multilingual TTS + translation | [sarvam.ai](https://www.sarvam.ai/) |
| Modal | Serverless GPU workers | [modal.com](https://modal.com) |
| AWS | S3 asset storage + EC2 (prod) | [aws.amazon.com](https://aws.amazon.com) |
| Hugging Face | Model downloads inside Modal | [huggingface.co](https://huggingface.co/settings/tokens) |

### Local tools

| Tool | Minimum version | Install |
|------|----------------|---------|
| Docker + Compose plugin | Docker 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Python | 3.11+ | [python.org](https://www.python.org/) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org/) |
| modal CLI | latest | `pip install modal && modal token new` |
| AWS CLI | v2 | [docs.aws.amazon.com/cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| git | any | — |

---

## Local Development

### Quick start

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd assesment

# 2. Copy the env template and fill in secrets
cp .env.example .env
# Edit .env — minimum required keys listed below

# 3. Build and start all local services
docker compose -f infra/docker-compose.dev.yml up --build

# 4. Run database migrations (first time only)
docker compose -f infra/docker-compose.dev.yml exec api alembic upgrade head

# 5. In a separate terminal — mount Modal GPU workers with hot-reload
modal serve apps/modal_app/app.py
```

Open **http://localhost:3000** once all containers are healthy.

> **No GPU required locally.** The Celery worker calls Modal via `.spawn()` / `.get()` — Modal runs the GPU containers on its own infrastructure. Set `MODAL_STUB=1` in `.env` to skip Modal entirely and use deterministic dummy assets (no credit spend).

---

### What the dev Compose stack includes

| Service | Image / Dockerfile | Port | Notes |
|---------|-------------------|------|-------|
| `redis` | `redis:7-alpine` | 6379 | Celery broker + SSE pub/sub |
| `api` | `infra/docker/api.Dockerfile` | 8000 | FastAPI + Uvicorn |
| `worker` | `infra/docker/worker.Dockerfile` | — | Celery; includes static ffmpeg |
| `web` | `infra/docker/web.Dockerfile` | 3000 | Next.js 14 |

**Not in the dev stack:**
- **Postgres** — provide your own via `DATABASE_URL` in `.env` (local install, Docker, or a free cloud tier)
- **nginx** — not needed locally; the Next.js dev server talks directly to the API
- **Modal GPU workers** — run via `modal serve` separately

---

### Minimum `.env` for local dev

```bash
# Google AI Studio
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.1-flash-lite

# Sarvam TTS + translation
SARVAM_API_KEY=your-key-here

# Modal (from `modal token new`)
MODAL_TOKEN_ID=your-token-id
MODAL_TOKEN_SECRET=your-token-secret
MODAL_STUB=1          # set to 0 to make real GPU calls

# Postgres — run locally or use a cloud instance
DATABASE_URL=postgresql+asyncpg://vidplatform:dev@localhost:5432/vidplatform

# AWS S3
S3_BUCKET=your-bucket-name
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Redis — overridden to redis://redis:6379/0 inside Compose
REDIS_URL=redis://localhost:6379/0
```

See [`.env.example`](../.env.example) for the full list with documentation comments.

---

### Running database migrations

```bash
# Apply all pending migrations
docker compose -f infra/docker-compose.dev.yml exec api alembic upgrade head

# Check current migration state
docker compose -f infra/docker-compose.dev.yml exec api alembic current

# Roll back one step
docker compose -f infra/docker-compose.dev.yml exec api alembic downgrade -1
```

---

### Modal stub mode vs real GPU

| `MODAL_STUB` | Behaviour | Cost |
|---|---|---|
| `1` (default) | Returns deterministic dummy asset IDs; skips all GPU calls | $0 |
| `0` | Makes real Modal GPU calls; produces real video output | ~$0.10–0.15 per full render |

Switch between them by editing `.env` and restarting the worker:
```bash
docker compose -f infra/docker-compose.dev.yml restart worker
```

---

### Useful dev commands

```bash
# Tail all logs
docker compose -f infra/docker-compose.dev.yml logs -f

# Tail a single service
docker compose -f infra/docker-compose.dev.yml logs -f api

# Open a shell in the API container
docker compose -f infra/docker-compose.dev.yml exec api bash

# Rebuild a single service after code changes
docker compose -f infra/docker-compose.dev.yml up -d --build api

# Stop everything and remove containers
docker compose -f infra/docker-compose.dev.yml down

# Stop and wipe volumes (⚠ deletes local redis data)
docker compose -f infra/docker-compose.dev.yml down -v
```

---

## Production — AWS EC2

All CPU services run inside Docker Compose on a single EC2 instance. GPU inference runs on Modal. Assets are stored in S3.

### Architecture

```
Internet
   │ 80 / 443
   ▼
┌─────────────────────────────────────────────────────┐
│  EC2 instance  (Ubuntu 22.04 LTS, t3.large)         │
│                                                     │
│  nginx:1.27-alpine                                  │
│   ├─ :80  → 301 HTTPS  (ACME challenge passthrough) │
│   └─ :443 → proxy_pass http://api:8000              │
│              SSE endpoints: proxy_buffering off     │
│                                                     │
│  api       (infra/docker/api.Dockerfile)            │
│  worker    (infra/docker/worker.Dockerfile)         │
│  postgres  postgres:16-alpine  /srv/vidplatform/data│
│  redis     redis:7-alpine      /srv/vidplatform/data│
└─────────────────────────────────────────────────────┘
         │  .spawn() / .get()
         ▼
  Modal serverless GPU functions
  (ltx_render · sdxl_image · musetalk_sync
   whisper_align · ffmpeg_composite)
         │  uploads / downloads
         ▼
  AWS S3 bucket  (same account, any region)
```

---

### Step 1 — AWS prerequisites

#### 1a. S3 bucket

```bash
# Create the bucket (pick a unique name and your preferred region)
aws s3 mb s3://your-vidplatform-bucket --region us-east-1

# Block all public access (assets are served via signed URLs)
aws s3api put-public-access-block \
  --bucket your-vidplatform-bucket \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

#### 1b. IAM user for S3 access

Create a dedicated IAM user (do **not** use your root credentials).

```bash
aws iam create-user --user-name vidplatform-s3

aws iam put-user-policy \
  --user-name vidplatform-s3 \
  --policy-name vidplatform-s3-policy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-vidplatform-bucket",
        "arn:aws:s3:::your-vidplatform-bucket/*"
      ]
    }]
  }'

# Generate access keys — save these; you won't see them again
aws iam create-access-key --user-name vidplatform-s3
```

#### 1c. EC2 key pair

```bash
# Create a key pair and save the .pem file
aws ec2 create-key-pair \
  --key-name vidplatform-ec2 \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/vidplatform-ec2.pem

chmod 400 ~/.ssh/vidplatform-ec2.pem
```

#### 1d. Security group

```bash
# Create the security group (replace vpc-xxxxxxxx with your VPC ID)
SG_ID=$(aws ec2 create-security-group \
  --group-name vidplatform-sg \
  --description "vidplatform production" \
  --vpc-id vpc-xxxxxxxx \
  --query GroupId --output text)

# SSH — restrict to your own IP in production
aws ec2 authorize-security-group-ingress --group-id $SG_ID \
  --protocol tcp --port 22 --cidr 0.0.0.0/0

# HTTP (needed for Let's Encrypt ACME challenge + redirect)
aws ec2 authorize-security-group-ingress --group-id $SG_ID \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

# HTTPS
aws ec2 authorize-security-group-ingress --group-id $SG_ID \
  --protocol tcp --port 443 --cidr 0.0.0.0/0
```

> Ports 5432 (Postgres), 6379 (Redis), and 8000 (API) are **not** opened — they are internal to the Docker network.

#### 1e. Launch the EC2 instance

**Recommended instance sizes:**

| Use case | Type | vCPU | RAM | Est. cost (us-east-1) |
|----------|------|------|-----|-----------------------|
| Staging / low traffic | t3.medium | 2 | 4 GB | ~$30/mo |
| Production | t3.large | 2 | 8 GB | ~$60/mo |
| Production + headroom | t3.xlarge | 4 | 16 GB | ~$120/mo |

```bash
# Launch a t3.large with Ubuntu 22.04 LTS (AMD64)
# Find the latest Ubuntu 22.04 AMI ID for your region:
#   aws ssm get-parameter \
#     --name /aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id \
#     --query Parameter.Value --output text

aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \   # Ubuntu 22.04 LTS us-east-1 (verify current AMI)
  --instance-type t3.large \
  --key-name vidplatform-ec2 \
  --security-group-ids $SG_ID \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=vidplatform-prod}]' \
  --count 1

# Get the public IP
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=vidplatform-prod" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text
```

Point your domain's A record at this IP before the next step.

---

### Step 2 — One-time server bootstrap

Run this once on a fresh EC2 instance. It installs Docker, sets up the directory structure, and installs the systemd unit.

```bash
# From the repo root on your laptop:
ssh -i ~/.ssh/vidplatform-ec2.pem ubuntu@<EC2-IP> 'bash -s' < infra/aws/bootstrap.sh
```

The script:
- Installs Docker Engine (official apt repo)
- Adds the `ubuntu` user to the `docker` group
- Opens UFW ports 22 / 80 / 443 (defense-in-depth alongside the EC2 security group)
- Creates `/srv/vidplatform/{data/postgres,data/redis}`
- Installs and enables the `vidplatform` systemd unit (auto-start on reboot)
- Installs `certbot` via snap

---

### Step 3 — TLS certificate

Issue a Let's Encrypt certificate **before** starting nginx (certbot needs port 80 free):

```bash
ssh -i ~/.ssh/vidplatform-ec2.pem ubuntu@<EC2-IP> \
  'sudo certbot certonly --standalone -d your.domain.com'
```

The certificate is written to `/etc/letsencrypt/live/your.domain.com/` and nginx mounts it read-only. Certbot installs a cron/systemd timer for automatic renewal.

---

### Step 4 — Prepare production `.env`

Create the production `.env` file locally, then copy it to the server.

**All required variables for production:**

```bash
# ── Postgres ───────────────────────────────────────────────────────────────
POSTGRES_USER=vidplatform
POSTGRES_PASSWORD=<strong-random-password>   # e.g. openssl rand -base64 32
POSTGRES_DB=vidplatform
DATABASE_URL=postgresql+asyncpg://vidplatform:<password>@postgres:5432/vidplatform

# ── Redis ──────────────────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── AWS S3 ─────────────────────────────────────────────────────────────────
S3_BUCKET=your-vidplatform-bucket
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=<from step 1b>
AWS_SECRET_ACCESS_KEY=<from step 1b>

# ── LLM ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.1-flash-lite

# ── Sarvam TTS + translation ───────────────────────────────────────────────
SARVAM_API_KEY=
SARVAM_TTS_MODEL=bulbul:v2
SARVAM_TRANSLATE_MODEL=sarvam-translate:v1

# ── Modal GPU workers ──────────────────────────────────────────────────────
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
MODAL_APP_NAME=vidplatform
MODAL_STUB=0                               # 0 = real GPU calls
MODAL_GLOBAL_COST_CAP_USD=25
MODAL_PER_PROJECT_COST_CAP_USD=1.5

# ── API service ────────────────────────────────────────────────────────────
ENVIRONMENT=production
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://api:8000
CORS_ORIGINS=["https://your.domain.com"]

# ── Frontend (baked into Next.js bundle at build time) ────────────────────
NEXT_PUBLIC_API_BASE_URL=https://your.domain.com

# ── Hugging Face (for Modal model downloads) ───────────────────────────────
HF_TOKEN=

# ── Music generation (parked; keep disabled) ──────────────────────────────
MUSIC_DISABLE=1

# ── EC2 deploy (used by infra/aws/deploy.sh on your laptop) ───────────────
EC2_HOST=<EC2-public-IP-or-domain>
EC2_USER=ubuntu
EC2_SSH_KEY_PATH=~/.ssh/vidplatform-ec2.pem
```

Copy it to the server:

```bash
scp -i ~/.ssh/vidplatform-ec2.pem .env ubuntu@<EC2-IP>:/srv/vidplatform/.env
```

---

### Step 5 — First deploy

```bash
# From the repo root on your laptop:
bash infra/aws/deploy.sh
```

This rsyncs the source tree to `/srv/vidplatform` and runs `docker compose up -d --build`.

Then run migrations once:

```bash
ssh -i ~/.ssh/vidplatform-ec2.pem ubuntu@<EC2-IP> \
  'cd /srv/vidplatform && docker compose -f infra/aws/docker-compose.prod.yml run --rm api alembic upgrade head'
```

---

### Step 6 — Deploy Modal GPU workers

Modal workers are deployed independently from the EC2 stack. Run this once (and again whenever `apps/modal_app/` changes):

```bash
# Deploy the GPU function app
modal deploy apps/modal_app/app.py

# Create Modal secrets (once — values are pulled from your local .env)
source .env
modal secret create gemini-api-key    GEMINI_API_KEY=$GEMINI_API_KEY
modal secret create sarvam-api-key    SARVAM_API_KEY=$SARVAM_API_KEY
modal secret create aws-s3            \
  AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  S3_BUCKET=$S3_BUCKET S3_REGION=$S3_REGION
modal secret create database-url      DATABASE_URL=$DATABASE_URL
modal secret create redis-url         REDIS_URL=$REDIS_URL
modal secret create hf-token          HF_TOKEN=$HF_TOKEN
```

---

### Routine deploys

After any code change, from the repo root on your laptop:

```bash
bash infra/aws/deploy.sh
```

The script rsyncs only changed files and restarts affected containers (Docker layer cache makes rebuilds fast). Zero-downtime: nginx keeps serving while the API container restarts.

If `apps/modal_app/` changed, also run:
```bash
modal deploy apps/modal_app/app.py
```

If database migrations were added, run:
```bash
ssh -i ~/.ssh/vidplatform-ec2.pem ubuntu@<EC2-IP> \
  'cd /srv/vidplatform && docker compose -f infra/aws/docker-compose.prod.yml run --rm api alembic upgrade head'
```

---

### Production services

| Service | Image / Dockerfile | Ports | Data |
|---------|-------------------|-------|------|
| `postgres` | `postgres:16-alpine` | internal | `/srv/vidplatform/data/postgres` |
| `redis` | `redis:7-alpine` | internal | `/srv/vidplatform/data/redis` |
| `api` | `infra/docker/api.Dockerfile` | internal (8000) | stateless |
| `worker` | `infra/docker/worker.Dockerfile` | none | stateless |
| `nginx` | `nginx:1.27-alpine` | **80, 443** | mounts `/etc/letsencrypt` |

---

### Maintenance

#### Tail logs

```bash
SSH="ssh -i ~/.ssh/vidplatform-ec2.pem ubuntu@<EC2-IP>"
COMPOSE="docker compose -f /srv/vidplatform/infra/aws/docker-compose.prod.yml"

# All services
$SSH "$COMPOSE logs -f --tail=100"

# Single service
$SSH "$COMPOSE logs -f --tail=100 api"
$SSH "$COMPOSE logs -f --tail=100 worker"
```

#### Restart a service

```bash
$SSH "$COMPOSE restart api"
$SSH "$COMPOSE restart worker"
```

#### Manual Postgres backup

```bash
ssh -i ~/.ssh/vidplatform-ec2.pem ubuntu@<EC2-IP> \
  'docker exec vidplatform-postgres-1 pg_dump -U vidplatform vidplatform | gzip' \
  > backup-$(date +%Y%m%d).sql.gz
```

#### Check health

```bash
# API health endpoint
curl https://your.domain.com/healthz

# Container status on the server
$SSH "$COMPOSE ps"
```

#### Certificate renewal

Certbot renews automatically. To test renewal:
```bash
ssh -i ~/.ssh/vidplatform-ec2.pem ubuntu@<EC2-IP> \
  'sudo certbot renew --dry-run'
```

---

### Upgrade path — managed AWS services

The all-in-one EC2 setup is straightforward but runs Postgres and Redis in containers on the same host. For higher availability, replace them with managed AWS services without changing application code:

| Current | Managed replacement | Change required |
|---------|--------------------|-|
| Postgres container | Amazon RDS for PostgreSQL | Update `DATABASE_URL` in `.env`; remove `postgres` service from `docker-compose.prod.yml` |
| Redis container | Amazon ElastiCache (Redis) | Update `REDIS_URL` in `.env`; remove `redis` service from `docker-compose.prod.yml` |

Both services use standard connection strings, so the swap is purely configuration.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `docker compose up` fails with "permission denied" | User not in `docker` group | Log out and back in after `bootstrap.sh` |
| API returns 502 Bad Gateway | API container not healthy | Check `docker compose logs api`; Postgres may still be starting |
| SSE events stop after ~60s | Nginx buffering or timeout | Verify nginx.conf has `proxy_buffering off` on SSE routes |
| S3 `AccessDenied` | IAM policy missing or wrong bucket name | Verify ARN in IAM policy matches exact bucket name |
| `alembic upgrade head` fails | DB not reachable or already migrated | Check `DATABASE_URL` and `docker compose ps postgres` |
| Modal calls hang | `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` wrong | Run `modal token new` and update `.env` |
| Certificate error on first nginx start | Cert path doesn't exist | Run certbot before `docker compose up` |
| `NEXT_PUBLIC_API_BASE_URL` shows `localhost` | Build arg not set | Rebuild web container after updating `.env` |

---

## File map

```
infra/
├── docker-compose.dev.yml           Local dev stack (redis · api · worker · web)
├── docker/
│   ├── api.Dockerfile               FastAPI + Uvicorn image
│   ├── worker.Dockerfile            Celery worker image (includes static ffmpeg)
│   └── web.Dockerfile               Next.js multi-stage image
└── aws/                             ◄ AWS EC2 production
    ├── bootstrap.sh                 One-shot EC2 provisioning script
    ├── deploy.sh                    rsync + compose up — run from your laptop
    ├── docker-compose.prod.yml      Production stack (postgres · redis · api · worker · nginx)
    ├── nginx.conf                   TLS reverse proxy with SSE-friendly settings
    └── vidplatform.service          systemd unit (auto-start on reboot)

docs/
├── infrastructure.md                This file
├── architecture.md                  System design, data flow, cost analysis
└── screenflow.md                    UI screens and state transitions

db/
└── migrations/versions/             Alembic migration scripts
    ├── 0001_initial_schema.py       Core tables
    └── 0002_async_editor.py         Async editor schema additions
```
