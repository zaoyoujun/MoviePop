"""
本地目录扫描器
递归扫描本地目录，查找视频文件
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 视频文件扩展名
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"}


class LocalScanner:
    """本地文件系统扫描器"""

    def __init__(self, max_depth: int = 3):
        """
        初始化本地扫描器
        :param max_depth: 最大递归深度，默认 3 层
        """
        self.max_depth = max_depth

    def scan_directory(self, dir_path: str) -> list:
        """
        递归扫描目录，收集所有视频文件
        :param dir_path: 要扫描的目录路径
        :return: 视频文件的绝对路径列表
        """
        root_path = Path(dir_path)
        if not root_path.exists():
            logger.warning(f"本地目录不存在: {dir_path}")
            return []

        if not root_path.is_dir():
            # 如果是单个文件，直接检查
            if root_path.suffix.lower() in VIDEO_EXTENSIONS:
                return [str(root_path.resolve())]
            return []

        # 递归扫描
        video_files = []
        self._scan_recursive(root_path, 0, video_files)
        return video_files

    def _scan_recursive(self, current_path: Path, depth: int, result: list) -> None:
        """递归扫描辅助方法"""
        if depth > self.max_depth:
            return

        try:
            for child in sorted(current_path.iterdir(), key=lambda x: x.name.lower()):
                if child.is_dir():
                    # 跳过隐藏目录
                    if child.name.startswith("."):
                        continue
                    self._scan_recursive(child, depth + 1, result)
                elif child.is_file():
                    # 检查是否为视频文件
                    if child.suffix.lower() in VIDEO_EXTENSIONS:
                        result.append(str(child.resolve()))
        except PermissionError:
            logger.warning(f"无权访问目录: {current_path}")
        except Exception as e:
            logger.error(f"扫描目录失败 {current_path}: {e}")

    def list_directory(self, dir_path: str) -> list:
        """
        列出目录内容（用于浏览界面）
        :param dir_path: 目录路径
        :return: 条目列表 [{name, type, path, size?}]
        """
        target = Path(dir_path)
        if not target.exists() or not target.is_dir():
            return []

        entries = []
        try:
            for child in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                entry = {
                    "name": child.name,
                    "type": "folder" if child.is_dir() else "file",
                    "path": str(child.resolve()),
                }
                if child.is_file():
                    entry["size"] = child.stat().st_size
                entries.append(entry)
        except PermissionError:
            pass

        return entries
