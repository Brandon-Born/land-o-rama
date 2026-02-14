from __future__ import annotations

from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.db.session import get_session_local
from app.models import SyncRun
from app.services.pipeline import run_daily_pipeline
from app.services.personalization import train_if_threshold_met
from app.services.settings import ensure_default_settings


def create_app(
    *,
    enable_startup_tasks: bool = True,
    enable_scheduler: bool = True,
    bootstrap_pipeline: bool = True,
) -> FastAPI:
    settings = get_settings()
    scheduler = BackgroundScheduler()

    def _run_job_wrapper() -> None:
        with get_session_local()() as db:
            run_daily_pipeline(db)

    def _run_personalization_job_wrapper() -> None:
        with get_session_local()() as db:
            train_if_threshold_met(db)

    def _schedule_jobs() -> None:
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
        retrain_time = settings.personalization_retrain_time
        retrain_hour, retrain_minute = [int(part) for part in retrain_time.split(":", maxsplit=1)]
        scheduler.add_job(
            _run_personalization_job_wrapper,
            trigger="cron",
            hour=retrain_hour,
            minute=retrain_minute,
            id="personalization_retrain",
            replace_existing=True,
        )
        scheduler.start()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with get_session_local()() as db:
            try:
                ensure_default_settings(db)
            except OperationalError as exc:  # pragma: no cover - startup guardrail
                raise RuntimeError(
                    "Database schema is not initialized. Run `alembic upgrade head` in /backend first."
                ) from exc

            if bootstrap_pipeline:
                existing_run = db.scalar(
                    select(SyncRun.id).where(SyncRun.status.in_(["success", "degraded"])).limit(1)
                )
                if not existing_run:
                    run_daily_pipeline(db)
            train_if_threshold_met(db)
        if enable_scheduler:
            _schedule_jobs()
        yield
        if enable_scheduler and scheduler.running:
            scheduler.shutdown(wait=False)

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan if enable_startup_tasks else None,
    )
    app.state.scheduler_enabled = enable_scheduler and enable_startup_tasks
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

    return app


app = create_app()
