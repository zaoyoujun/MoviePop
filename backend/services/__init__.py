"""
Services 模块
业务逻辑服务层，封装数据源管理、电影库管理、扫描服务等核心逻辑
"""
try:
    from . import source_service
    from . import library_service
    from . import scan_service
    from . import player_service
except ImportError:
    from services import source_service
    from services import library_service
    from services import scan_service
    from services import player_service

__all__ = [
    "source_service",
    "library_service",
    "scan_service",
    "player_service",
]
