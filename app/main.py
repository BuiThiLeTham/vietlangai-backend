from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import get_session, init_db, shutdown_db
from app.routers import auth, catalog, community, learn, translate
from app.seed import seed


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    await init_db(settings.database_url)
    if settings.auto_seed:
        async for session in get_session():
            await seed(session)
    yield
    await shutdown_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Ngôn Sắc Việt", version="0.1.0", lifespan=lifespan)
    origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix="/v1")
    app.include_router(catalog.router, prefix="/v1")
    app.include_router(translate.router, prefix="/v1")
    app.include_router(learn.router, prefix="/v1")
    app.include_router(community.router, prefix="/v1")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "api"}

    return app


app = create_app()
