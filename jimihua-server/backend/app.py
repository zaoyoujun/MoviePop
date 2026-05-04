from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.jobs import JobManager
from backend.routers import (
    bootstrap,
    cache,
    config,
    directories,
    jobs,
    library,
    movies,
    openlist,
    recommendations,
    report,
    tags,
)
from backend.services import (
    ConfigService,
    LibraryService,
    OpenListService,
    PlaybackService,
    RecommendationService,
    ReportService,
    ScraperService,
)
from config.app_config import AppConfig
from core.openlist_manager import openlist_manager
from utils.logger import get_logger

logger = get_logger()

BASE_DIR = Path(__file__).resolve().parent.parent
COVERS_DIR = BASE_DIR / "covers"

# 服务实例（延迟初始化，由 create_app 控制）
config_service: ConfigService | None = None
library_service: LibraryService | None = None
playback_service: PlaybackService | None = None
scraper_service: ScraperService | None = None
recommendation_service: RecommendationService | None = None
report_service: ReportService | None = None
openlist_service: OpenListService | None = None
job_manager: JobManager | None = None


def _init_services():
    global config_service, library_service, playback_service
    global scraper_service, recommendation_service, report_service
    global openlist_service, job_manager

    config_service = ConfigService()
    library_service = LibraryService()
    playback_service = PlaybackService(library_service)
    scraper_service = ScraperService(library_service)
    recommendation_service = RecommendationService(library_service)
    report_service = ReportService(library_service, recommendation_service)
    openlist_service = OpenListService()
    job_manager = JobManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = AppConfig()
    if config.OPENLIST_ENABLED and config.OPENLIST_AUTO_START:
        try:
            openlist_manager.start()
        except Exception as exc:
            logger.warning("OpenList 自动启动失败: %s", exc)
    yield
    openlist_manager.stop()


def create_app(serve_frontend: str | None = None) -> FastAPI:
    """创建 FastAPI 应用实例。

    Args:
        serve_frontend: 如果提供，将指定目录作为前端静态文件挂载到根路径。
    """
    _init_services()

    app = FastAPI(title="鸡米花", version="3.0.0", lifespan=lifespan)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 封面图片
    if COVERS_DIR.exists():
        app.mount("/covers", StaticFiles(directory=str(COVERS_DIR)), name="covers")

    # 注册路由
    app.include_router(bootstrap.router)
    app.include_router(config.router)
    app.include_router(directories.router)
    app.include_router(library.router)
    app.include_router(movies.router)
    app.include_router(tags.router)
    app.include_router(recommendations.router)
    app.include_router(report.router)
    app.include_router(jobs.router)
    app.include_router(cache.router)
    app.include_router(openlist.router)

    # 前端静态文件（可选）
    if serve_frontend:
        frontend_path = Path(serve_frontend)
        if frontend_path.exists():
            app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

    return app


# 默认应用实例（兼容 uvicorn 直接引用 backend.app:app）
app = create_app()
