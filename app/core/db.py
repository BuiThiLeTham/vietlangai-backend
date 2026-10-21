from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None


def make_engine(url: str):
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" not in url and "///" in url:
            Path(url.split("///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
    elif url.startswith("postgres"):
        # Supabase transaction pooler rejects asyncpg prepared statements.
        url = url.split("?", 1)[0]
        kwargs["connect_args"] = {"statement_cache_size": 0, "ssl": "require"}
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

    engine = make_engine(url)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


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
