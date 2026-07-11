"""
WebDAV 客户端
用于连接远程 WebDAV 服务器，浏览目录和获取文件流地址
参考核心代码参考目录中的 webdav_client.py 实现
"""
import os
import logging
from urllib.parse import quote, unquote, urlparse
from xml.etree import ElementTree as ET

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

# 视频文件扩展名
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"}


class WebDAVClient:
    """WebDAV 客户端，支持目录浏览和连接验证"""

    def __init__(self, host: str = "", username: str = "", password: str = ""):
        """
        初始化 WebDAV 客户端
        :param host: WebDAV 服务器地址，如 https://dav.example.com
        :param username: 用户名
        :param password: 密码
        """
        self.host = (host or "").strip().rstrip("/")
        # 提取 base_path（host 中可能包含的路径部分）
        self.base_path = urlparse(self.host).path.rstrip("/")
        if self.base_path:
            # 如果 host 包含路径，提取纯主机地址
            parsed = urlparse(self.host)
            self.host = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port:
                self.host += f":{parsed.port}"
        
        self.username = username.strip()
        self.password = password.strip()

        # 创建 HTTP 会话
        self.session = requests.Session()
        self.session.verify = False  # 忽略 SSL 证书验证
        self.session.headers.update({"User-Agent": "JMH-MoviePop/1.0"})
        
        # 禁用系统代理，避免连接被路由到代理服务器
        self.session.trust_env = False
        self.session.proxies = {}

        # 基本认证
        self.auth = None
        if self.username and self.password:
            self.auth = HTTPBasicAuth(self.username, self.password)

        # 抑制 SSL 警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _normalize_path(self, path: str = "/") -> str:
        """标准化路径，确保以 / 开头"""
        value = str(path or "/").strip() or "/"
        if not value.startswith("/"):
            value = "/" + value
        return value

    def _encode_path(self, path: str) -> str:
        """编码路径中的特殊字符，避免重复编码"""
        normalized = self._normalize_path(path)
        segments = []
        for segment in normalized.lstrip("/").split("/"):
            if not segment:
                continue
            # 检查是否已经编码过（如果包含 % 则认为已编码）
            if '%' in segment:
                # 已编码，直接使用
                segments.append(segment)
            else:
                # 未编码，进行编码
                segments.append(quote(segment, safe=''))
        return "/" + "/".join(segments) if segments else "/"

    def _build_url(self, path: str = "/") -> str:
        """构建完整的 WebDAV URL"""
        if not self.host:
            raise ValueError("WebDAV host is empty")
        encoded_path = self._encode_path(path)
        # 将 base_path 添加到 URL 中
        full_path = self.base_path + encoded_path if self.base_path else encoded_path
        return f"{self.host}{full_path if full_path != '/' else ''}"

    def _request(self, method: str, path: str = "/", *, headers: dict = None, data: str = None):
        """发送 HTTP 请求"""
        response = self.session.request(
            method.upper(),
            self._build_url(path),
            headers=headers or {},
            data=data,
            timeout=20,
            auth=self.auth,
            allow_redirects=True,
        )
        return response

    def _propfind(self, path: str = "/", depth: int = 1):
        """发送 PROPFIND 请求"""
        body = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype /></d:prop></d:propfind>"""
        return self._request(
            "PROPFIND",
            path,
            headers={
                "Depth": str(depth),
                "Content-Type": "application/xml; charset=utf-8",
            },
            data=body,
        )

    def _href_to_path(self, href: str) -> str:
        """从 href 提取路径"""
        parsed = urlparse(str(href or ""))
        href_path = unquote(parsed.path or "/")
        if self.base_path and href_path.startswith(self.base_path):
            href_path = href_path[len(self.base_path):] or "/"
        if not href_path.startswith("/"):
            href_path = "/" + href_path
        return href_path.rstrip("/") or "/"

    def _parse_entries(self, response_text: str, current_path: str) -> list:
        """解析 PROPFIND 响应中的条目"""
        entries = []
        normalized_current = self._normalize_path(current_path).rstrip("/") or "/"
        try:
            root = ET.fromstring(response_text)
        except ET.ParseError as exc:
            logger.error("WebDAV XML parse failed: %s", exc)
            raise RuntimeError("WebDAV 响应不是有效的 XML，请确认地址是否为 WebDAV 入口")

        if not str(root.tag).endswith("multistatus"):
            raise RuntimeError("WebDAV 响应不是 DAV multistatus，请确认地址是否为 WebDAV 入口")

        ns = {"d": "DAV:"}
        for item in root.findall("d:response", ns):
            href_text = item.findtext("d:href", default="", namespaces=ns)
            entry_path = self._href_to_path(href_text)
            # 跳过当前目录自身
            if (entry_path.rstrip("/") or "/") == normalized_current:
                continue
            prop = item.find("d:propstat/d:prop", ns)
            resource_type = prop.find("d:resourcetype", ns) if prop is not None else None
            is_dir = resource_type is not None and resource_type.find("d:collection", ns) is not None
            # 回退判断：href 以 / 结尾也视为目录
            if not is_dir and href_text.rstrip().endswith("/"):
                is_dir = True
            name = os.path.basename(entry_path.rstrip("/")) or entry_path.strip("/") or "/"
            entries.append({
                "name": name,
                "full_path": entry_path.rstrip("/") if is_dir else entry_path,
                "is_dir": is_dir,
            })
        return entries

    def _raise_for_webdav_status(self, response, path: str) -> None:
        """Validate a WebDAV response before XML parsing."""
        status = response.status_code
        if status in (200, 207):
            return
        if status in (401, 403):
            raise PermissionError("WebDAV 认证失败，请检查用户名或密码")
        if status == 404:
            raise FileNotFoundError(f"WebDAV 目录不存在: {path}")
        raise RuntimeError(f"WebDAV 请求失败，HTTP 状态码: {status}")

    def verify_connection(self) -> bool:
        """
        验证 WebDAV 连接是否有效
        :return: True 表示连接成功
        """
        if not self.host:
            logger.error("WebDAV host 为空")
            return False

        try:
            response = self._propfind("/", depth=0)
            self._raise_for_webdav_status(response, "/")
            self._parse_entries(response.text, "/")
            status = response.status_code
            logger.info(f"WebDAV 连接验证成功，状态码: {status}")
            return True
        except requests.exceptions.RequestException as exc:
            logger.error(f"WebDAV 连接验证失败 (网络错误): {exc}")
            return False
        except Exception as exc:
            logger.error(f"WebDAV 连接验证失败: {exc}")
            return False

    def list_directory(self, path: str = "/") -> list:
        """
        列出指定目录的内容
        :param path: 目录路径
        :return: 条目列表 [{name, type, path, size?, modifiedAt?}]
        """
        if not self.host:
            return []

        normalized = self._normalize_path(path)
        try:
            response = self._propfind(normalized, depth=1)
            self._raise_for_webdav_status(response, normalized)
            entries = self._parse_entries(response.text, normalized)

            result = []
            for item in entries:
                result.append({
                    "name": item["name"],
                    "type": "folder" if item["is_dir"] else "file",
                    "path": item["full_path"],
                })

            # 排序：文件夹在前，按名称排序
            result.sort(key=lambda x: (x["type"] != "folder", x["name"].lower()))
            return result

        except Exception as e:
            logger.error(f"WebDAV 目录浏览失败 {path}: {e}")
            raise

    def list_files_recursive(self, path: str = "/", max_depth: int = 2, progress_cb=None, should_cancel=None) -> list:
        """
        递归列出所有视频文件（BFS 方式）
        :param path: 起始目录路径
        :param max_depth: 最大递归深度
        :param progress_cb: 进度回调 (dirs_done, files_found, current_path)
        :return: 视频文件路径列表
        """
        videos = []
        try:
            root_path = self._normalize_path(path)
            scan_queue = [(root_path, 0)]
            processed_dirs = set()

            while scan_queue:
                if should_cancel and should_cancel():
                    logger.info("远程扫描已取消")
                    break
                current_path, current_depth = scan_queue.pop(0)
                if current_path in processed_dirs:
                    continue
                processed_dirs.add(current_path)

                if progress_cb:
                    progress_cb(len(processed_dirs), len(videos), f"正在扫描: {current_path}")

                try:
                    response = self._propfind(current_path, depth=1)
                    self._raise_for_webdav_status(response, current_path)
                    entries = self._parse_entries(response.text, current_path)
                except Exception as exc:
                    logger.warning("目录不存在或无法访问: %s", current_path)
                    continue

                for item in entries:
                    full_path = item["full_path"]
                    if item["is_dir"]:
                        if current_depth < max_depth:
                            scan_queue.append((full_path, current_depth + 1))
                        continue

                    ext = os.path.splitext(full_path)[1].lower()
                    if ext in VIDEO_EXTENSIONS:
                        videos.append(full_path)

            logger.info("[完成] 远程扫描完成 | 视频文件总数: %s 个", len(videos))
            return videos
        except Exception as exc:
            logger.error("远程扫描失败: %s", exc)
            return videos

    def get_stream_url(self, file_path: str) -> tuple:
        """
        获取媒体文件的流地址和认证头
        :param file_path: 文件在 WebDAV 上的路径
        :return: (stream_url, headers) 元组
        """
        if not self.host:
            return file_path, {}

        # 构建完整 URL
        url = self._build_url(file_path)

        # 构建认证头（供 mpv 等播放器使用）
        headers = {}
        if self.username and self.password:
            import base64
            credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"

        return url, headers

    def stat(self, file_path: str) -> dict:
        """
        获取文件信息
        :param file_path: 文件路径
        :return: 文件信息字典，包含 size 等字段
        """
        url = self._build_url(file_path)
        logger.info(f"获取文件信息: {url}")
        
        try:
            # 首先尝试 HEAD 请求（更高效）
            response = self.session.head(url, auth=self.auth, timeout=30)
            response.raise_for_status()
            
            size = int(response.headers.get('Content-Length', 0))
            logger.info(f"文件大小: {size} bytes")
            return {
                'size': size,
                'modified': response.headers.get('Last-Modified', ''),
                'content_type': response.headers.get('Content-Type', '')
            }
        except requests.exceptions.HTTPError as e:
            # 如果 HEAD 请求失败（如 500 错误），尝试用 GET 请求获取 headers（不下载内容）
            if response.status_code == 500:
                logger.warning(f"HEAD 请求失败 (500)，尝试 GET 请求获取文件信息: {file_path}")
                try:
                    response = self.session.get(url, auth=self.auth, timeout=30, stream=True)
                    response.raise_for_status()
                    
                    size = int(response.headers.get('Content-Length', 0))
                    response.close()  # 不读取内容，直接关闭连接
                    logger.info(f"GET 请求获取文件大小: {size} bytes")
                    return {
                        'size': size,
                        'modified': response.headers.get('Last-Modified', ''),
                        'content_type': response.headers.get('Content-Type', '')
                    }
                except Exception as e2:
                    logger.error(f"GET 请求也失败 {file_path}: {e2}")
                    return {'size': 0}
            else:
                logger.error(f"获取文件信息失败 {file_path}: {e}")
                return {'size': 0}
        except Exception as e:
            logger.error(f"获取文件信息失败 {file_path}: {e}")
            return {'size': 0}

    def open(self, file_path: str, mode: str = 'rb') -> requests.Response:
        """
        打开文件流
        :param file_path: 文件路径
        :param mode: 打开模式（仅支持 rb）
        :return: 文件流响应对象
        """
        if mode != 'rb':
            raise ValueError("WebDAVClient 仅支持 rb 模式")
        
        url = self._build_url(file_path)
        response = self.session.get(
            url, 
            auth=self.auth, 
            timeout=30,
            stream=True  # 流式传输
        )
        response.raise_for_status()
        return response
