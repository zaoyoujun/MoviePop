"""
API 请求/响应模型
使用 Pydantic 定义请求体和响应体结构
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


# ==================== 数据源相关 ====================

class SourcePayload(BaseModel):
    """数据源请求体"""
    name: str = ""
    type: str = ""           # webdav / local
    path: str = ""           # WebDAV 地址或本地路径
    username: str = ""
    password: str = ""
    selected_paths: list = Field(default_factory=list)  # 用户选中的目录/文件路径


class SourceBrowsePayload(BaseModel):
    """目录浏览请求体"""
    type: str = ""
    host: str = ""
    port: str = ""
    protocol: str = "http"
    username: str = ""
    password: str = ""
    path: str = "/"          # 当前路径


# ==================== 通用响应 ====================

def api_response(code: int = 0, message: str = "ok", data: Any = None) -> dict:
    """构造统一 API 响应格式 { code, message, data }"""
    return {"code": code, "message": message, "data": data}
