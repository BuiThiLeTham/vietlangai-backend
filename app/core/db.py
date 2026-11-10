from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None


def normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


def make_engine(url: str):
    settings = get_settings()
    url = normalize_db_url(url)
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" not in url and "///" in url:
            Path(url.split("///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
    elif url.startswith("postgres"):
        # Support both AWS RDS PostgreSQL and Supabase transaction pooler.
        url = url.split("?", 1)[0]
        connect_args: dict = {"statement_cache_size": settings.db_statement_cache_size}
        if settings.db_ssl_require:
            connect_args["ssl"] = "require"
        kwargs["connect_args"] = connect_args
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
    built = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(built.sync_engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return built


async def init_db(url: str) -> None:
    global engine, SessionLocal
    import app.models  # noqa: F401

    settings = get_settings()
    settings.validate_security()
    engine = make_engine(url)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    if url.startswith("sqlite") or (settings.auto_create_tables and settings.app_env.lower() != "production"):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)


async def check_db_health() -> bool:
    if SessionLocal is None:
        return False
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_session() -> AsyncIterator[AsyncSession]:
    if SessionLocal is None:
        raise RuntimeError("Database is not initialized")
    async with SessionLocal() as session:
        yield session


async def shutdown_db() -> None:
    global engine, SessionLocal
    if engine is not None:
        await engine.dispose()
    engine = None
    SessionLocal = None
