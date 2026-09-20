"""
JMH-MoviePop FastAPI 应用入口
所有业务逻辑已拆分到 services/ 和 api/ 模块
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

try:
    from .config import AppConfig
    from .core import scheduler
    from .services import scan_service, source_service
    from .api.routes import restore_openlist_sources, router
except ImportError:
    from config import AppConfig
    from core import scheduler
    from services import scan_service, source_service
    from api.routes import restore_openlist_sources, router

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 路径
CONFIG = AppConfig()
COVERS_DIR = CONFIG.COVERS_DIR
STATIC_DIR = CONFIG.BASE_DIR / "static"


def _get_openlist_manager():
    try:
        from .core.openlist_manager import openlist_manager
    except ImportError:
        from core.openlist_manager import openlist_manager
    return openlist_manager

# 创建 FastAPI 应用
app = FastAPI(
    title="JMH-MoviePop",
    version="1.0.0",
    description="JMH-MoviePop 电影库后端 API",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保封面目录存在并挂载静态文件服务
COVERS_DIR.mkdir(exist_ok=True)
app.mount("/covers", StaticFiles(directory=str(COVERS_DIR)), name="covers")

# 挂载播放器静态文件服务
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 注册所有 API 路由
app.include_router(router)


# ==================== 生命周期事件 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化配置、清理无效数据源、自动启动 OpenList"""
    config = AppConfig()
    config.load_config()
    source_service.cleanup_on_startup()
    scan_service.log_scraper_source_availability()
    
    # 如果启用了内置 OpenList 并且设置了自动启动，则启动 OpenList
    if config.OPENLIST_ENABLED and config.OPENLIST_AUTO_START:
        openlist_manager = _get_openlist_manager()
        try:
            result = openlist_manager.start()
            if result.get("success"):
                logger.info(f"OpenList 自动启动成功，端口: {result.get('port', 5244)}")
                if result.get("logged_in"):
                    logger.info("OpenList 自动登录成功")
            else:
                logger.warning(f"OpenList 自动启动失败: {result.get('message', '')}")
        except Exception as e:
            logger.error(f"OpenList 自动启动异常: {e}")
    
    logger.info(f"JMH-MoviePop API 启动成功，端口: {config.SERVER_PORT}")

    # 启动后台调度器（每日 trending 刷新 + 首次下载检查）
    try:
        scheduler.start_scheduler()
        logger.info("后台任务调度器已启动")
    except Exception as e:
        logger.error(f"启动后台调度器异常: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时停止 OpenList 服务"""
    openlist_manager = _get_openlist_manager()
    try:
        result = openlist_manager.stop()
        if result.get("success"):
            logger.info("OpenList 服务已停止")
        else:
            logger.warning(f"停止 OpenList 服务失败: {result.get('message', '')}")
    except Exception as e:
        logger.error(f"停止 OpenList 服务异常: {e}")


# ==================== 根路径重定向 ====================

@app.get("/")
async def root():
    """根路径重定向到 API 文档"""
    return RedirectResponse(url="/docs")


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    config = AppConfig()
    config.load_config()
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=config.SERVER_PORT,
        reload=False,
    )
