from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.settings import get_settings

settings = get_settings()

_engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    echo=False,
)

_SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    type_annotation_map: dict[Any, Any] = {}


def sessionmaker_factory() -> async_sessionmaker[AsyncSession]:
    return _SessionLocal


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session and closes on request end."""
    async with _SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
