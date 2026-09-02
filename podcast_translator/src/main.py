import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.v1.auth import router as auth_router
from src.api.v1.tasks import router as tasks_router
from src.api.v1.users import router as users_router
from src.config import settings
from src.core.redis import get_redis_sync
from src.core.migrations import run_startup_migrations
from src.dependencies import get_db_session
from src.services.storage_service import StorageService

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.PCT_AUTO_MIGRATE_ON_STARTUP:
        await asyncio.to_thread(run_startup_migrations)
    yield


app = FastAPI(title="Podcast Translator API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")


@app.get("/health")
async def health_check(db=Depends(get_db_session)):
    import sqlalchemy as sa

    storage_service = StorageService()
    redis_client = get_redis_sync()
    db_ok = False
    db_error = None

    try:
        await db.execute(sa.text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)

    try:
        redis_ok = bool(redis_client and redis_client.ping())
    except Exception:
        redis_ok = False

    try:
        storage_ok = await storage_service.check_connection()
    except Exception:
        storage_ok = False

    if db_ok and redis_ok and storage_ok:
        return {"status": "ok", "db": "ok", "redis": "ok", "storage": "ok"}

    return {
        "status": "degraded",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "storage": "ok" if storage_ok else "error",
        "error": db_error,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )
