"""FastAPI entry point.

Routes:
  /healthz, /readyz       → app.routes.health
  /projects, /projects/:id → app.routes.projects
  /jobs/:id, /jobs/:id/events → app.routes.jobs
  /assets/:id             → app.routes.assets

Day 2+ adds: /chat, /storyboard, /scenes, /generate, /regenerate-language,
             /export, /overlays, /subtitles
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import (
    assets,
    audio,
    chat,
    export,
    health,
    jobs,
    language,
    overlays,
    projects,
    references,
    render,
    scenes,
    storyboard,
    subtitles,
)
from app.settings import get_settings

settings = get_settings()


def _configure_logging() -> None:
    logging.basicConfig(level=settings.log_level)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _configure_logging()
    log = structlog.get_logger()
    log.info("api_starting", env=settings.environment)
    yield
    log.info("api_stopping")


app = FastAPI(
    title="vidplatform-api",
    version="0.1.0",
    description="Conversational Multilingual AI Video Platform — API service",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(projects.router)
app.include_router(chat.router)
app.include_router(storyboard.router)
app.include_router(scenes.router)
app.include_router(render.router)
app.include_router(language.router)
app.include_router(overlays.router)
app.include_router(subtitles.router)
app.include_router(audio.router)
app.include_router(export.router)
app.include_router(jobs.router)
app.include_router(assets.router)
app.include_router(references.router)
