# Celery worker — pipeline controller (CPU-only; the GPU work runs on Modal)
# Build context: repo root.
# Build: docker build -f infra/docker/worker.Dockerfile -t vidplatform-worker .

# Static ffmpeg binary (~80 MB) avoids apt installing 771 MB of dependencies
FROM mwader/static-ffmpeg:latest AS ffmpeg

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /ffprobe /usr/local/bin/ffprobe

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY apps/worker ./apps/worker
COPY apps/modal_app ./apps/modal_app
COPY docs/prompts ./docs/prompts

WORKDIR /app/apps/worker

CMD ["celery", "-A", "worker.celery_app", "worker", "--concurrency=4", "--loglevel=INFO"]
