"""
文件缓存服务 - 将远程文件缓存到本地
"""
import os
import sys
import urllib.request
import urllib.parse
import tempfile
import shutil
import threading
import logging

try:
    from backend.config import AppConfig
except ImportError:
    from config import AppConfig

logger = logging.getLogger(__name__)

class FileCacheService:
    def __init__(self):
        """初始化文件缓存服务"""
        # 将缓存目录放在项目 data 目录下，而不是系统临时目录
        self.cache_dir = str(AppConfig().DATA_DIR / 'cache')
        self.downloading_files = set()
        self.download_locks = {}
        
        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
        logger.info(f'文件缓存目录: {self.cache_dir}')
    
    def get_cached_path(self, url):
        """获取缓存文件路径"""
        # 使用URL的哈希作为文件名
        import hashlib
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        
        # 获取原始文件名
        parsed = urllib.parse.urlparse(url)
        filename = os.path.basename(parsed.path)
        if not filename:
            filename = f'{url_hash}.tmp'
        
        return os.path.join(self.cache_dir, filename)
    
    def is_cached(self, url):
        """检查文件是否已缓存"""
        cached_path = self.get_cached_path(url)
        return os.path.exists(cached_path)
    
    def download_file(self, url, progress_callback=None):
        """下载文件到缓存目录"""
        # 确保 URL 路径部分已编码
        parsed = urllib.parse.urlparse(url)
        
        # 重新构建编码后的 URL
        encoded_path = urllib.parse.quote(parsed.path)
        encoded_url = urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, encoded_path, 
             parsed.params, parsed.query, parsed.fragment)
        )
        
        cached_path = self.get_cached_path(encoded_url)
        
        # 检查是否正在下载
        url_hash = hash(encoded_url)
        if url_hash in self.downloading_files:
            logger.info(f'文件正在下载中: {encoded_url}')
            return cached_path
        
        # 获取锁
        if url_hash not in self.download_locks:
            self.download_locks[url_hash] = threading.Lock()
        
        with self.download_locks[url_hash]:
            # 再次检查是否已缓存
            if os.path.exists(cached_path):
                logger.info(f'文件已缓存: {cached_path}')
                return cached_path
            
            # 标记为正在下载
            self.downloading_files.add(url_hash)
            
            try:
                logger.info(f'开始下载: {encoded_url}')
                
                # 创建请求（处理认证）
                parsed_url = urllib.parse.urlparse(encoded_url)
                req = urllib.request.Request(encoded_url)
                
                # 处理认证信息（如果 URL 中包含认证信息）
                if parsed_url.username and parsed_url.password:
                    import base64
                    auth = f"{parsed_url.username}:{parsed_url.password}"
                    req.add_header('Authorization', f'Basic {base64.b64encode(auth.encode()).decode()}')
                    # 移除 URL 中的认证信息，避免重复发送
                    clean_url = urllib.parse.urlunparse(
                        (parsed_url.scheme, 
                         parsed_url.hostname + (f":{parsed_url.port}" if parsed_url.port else ""), 
                         parsed_url.path, 
                         parsed_url.params, parsed_url.query, parsed_url.fragment)
                    )
                    req = urllib.request.Request(clean_url)
                    req.add_header('Authorization', f'Basic {base64.b64encode(auth.encode()).decode()}')
                
                # 添加范围请求支持
                req.add_header('Accept-Ranges', 'bytes')
                
                with urllib.request.urlopen(req, timeout=60) as response:
                    # 获取文件大小
                    content_length = int(response.headers.get('Content-Length', 0))
                    downloaded = 0
                    chunk_size = 8192
                    
                    with open(cached_path, 'wb') as f:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback and content_length > 0:
                                progress = (downloaded / content_length) * 100
                                progress_callback(progress)
                
                logger.info(f'下载完成: {cached_path}')
                return cached_path
                
            except Exception as e:
                logger.error(f'下载失败: {e}')
                # 清理不完整的文件
                if os.path.exists(cached_path):
                    os.remove(cached_path)
                raise
            finally:
                # 移除下载标记
                self.downloading_files.discard(url_hash)
    
    def play_cached(self, url):
        """获取缓存文件路径，如果未缓存则下载"""
        try:
            if self.is_cached(url):
                return self.get_cached_path(url)
            else:
                return self.download_file(url)
        except Exception as e:
            logger.error(f'缓存失败: {e}')
            return None
    
    def clear_cache(self):
        """清空所有缓存"""
        try:
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
                os.makedirs(self.cache_dir)
                logger.info('缓存已清空')
                return True
            return False
        except Exception as e:
            logger.error(f'清空缓存失败: {e}')
            return False
    
    def get_cache_size(self):
        """获取缓存大小（字节）"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.cache_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size


# 全局实例
_cache_instance = None

def get_cache():
    """获取全局缓存服务实例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = FileCacheService()
    return _cache_instance
