from __future__ import annotations

from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models import Base, SyncRun
from app.services.pipeline import run_daily_pipeline
from app.services.settings import ensure_default_settings

settings = get_settings()
scheduler = BackgroundScheduler()


def _schedule_daily_job() -> None:
    refresh_time = settings.refresh_time
    hour, minute = [int(part) for part in refresh_time.split(":", maxsplit=1)]
    scheduler.add_job(
        _run_job_wrapper,
        trigger="cron",
        hour=hour,
        minute=minute,
        id="daily_pipeline",
        replace_existing=True,
    )
    scheduler.start()


def _run_job_wrapper() -> None:
    with SessionLocal() as db:
        run_daily_pipeline(db)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_default_settings(db)
        existing_run = db.scalar(select(SyncRun.id).where(SyncRun.status == "success").limit(1))
        if not existing_run:
            run_daily_pipeline(db)
    _schedule_daily_job()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
