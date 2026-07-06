"""
视频流服务
提供视频文件的流式传输，支持断点续传（Range请求）
"""
import os
import re
import logging
import urllib.parse
from typing import Optional, Tuple, Dict, Any
from fastapi import HTTPException, status, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# 支持的视频扩展名
SUPPORTED_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}

# 支持的MIME类型
MIME_TYPES = {
    '.mp4': 'video/mp4',
    '.mkv': 'video/x-matroska',
    '.avi': 'video/x-msvideo',
    '.mov': 'video/quicktime',
    '.wmv': 'video/x-ms-wmv',
    '.flv': 'video/x-flv',
    '.webm': 'video/webm',
    '.m4v': 'video/mp4',
}


def get_mime_type(file_path: str) -> str:
    """根据文件扩展名获取MIME类型"""
    ext = os.path.splitext(file_path)[1].lower()
    return MIME_TYPES.get(ext, 'application/octet-stream')


def parse_range_header(range_header: Optional[str], file_size: int) -> Tuple[int, int]:
    """解析Range请求头"""
    if not range_header:
        return 0, file_size - 1
    
    match = re.match(r'bytes=(\d+)-(\d+)?', range_header)
    if not match:
        raise HTTPException(status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE, detail="Invalid Range header")
    
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1
    
    if start > end or start >= file_size:
        raise HTTPException(status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE, detail="Range not satisfiable")
    
    return start, end


def stream_local_file(file_path: str, range_header: Optional[str] = None) -> StreamingResponse:
    """流式传输本地文件"""
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a file")
    
    file_size = os.path.getsize(file_path)
    start, end = parse_range_header(range_header, file_size)
    
    def file_iterator():
        with open(file_path, 'rb') as f:
            f.seek(start)
            remaining = end - start + 1
            chunk_size = 64 * 1024  # 64KB chunks
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                yield chunk
                remaining -= len(chunk)
    
    mime_type = get_mime_type(file_path)
    content_length = end - start + 1
    
    headers = {
        'Content-Type': mime_type,
        'Content-Length': str(content_length),
        'Content-Range': f'bytes {start}-{end}/{file_size}',
        'Accept-Ranges': 'bytes',
        'Connection': 'keep-alive',
        'Content-Disposition': 'inline',
        'Access-Control-Expose-Headers': 'Content-Range,Content-Length,Content-Type',
    }
    
    return StreamingResponse(
        file_iterator(),
        status_code=status.HTTP_206_PARTIAL_CONTENT if range_header else status.HTTP_200_OK,
        headers=headers
    )


def stream_webdav_file(webdav_client, file_path: str, range_header: Optional[str] = None) -> StreamingResponse:
    """流式传输WebDAV文件"""
    try:
        # 直接开始流式传输，不预先获取文件大小（避免服务器不返回 Content-Length 的问题）
        url = webdav_client._build_url(file_path)
        logger.info(f"WebDAV 流请求: {url}, Range: {range_header}")
        
        def webdav_iterator():
            # 使用 Range 请求头获取指定范围的内容
            headers = {}
            if range_header:
                headers['Range'] = range_header
            
            response = webdav_client.session.get(
                url,
                auth=webdav_client.auth,
                headers=headers,
                timeout=60,
                stream=True
            )
            
            # 检查响应状态
            if response.status_code not in [200, 206]:
                logger.error(f"WebDAV 请求失败: {response.status_code} - {response.text[:200]}")
                raise HTTPException(status_code=response.status_code, detail=f"WebDAV 请求失败: {response.status_code}")
            
            chunk_size = 64 * 1024  # 64KB chunks
            bytes_read = 0
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    bytes_read += len(chunk)
                    yield chunk
            
            logger.info(f"WebDAV 流传输完成: {bytes_read} bytes")
        
        mime_type = get_mime_type(file_path)
        
        # 获取响应头信息（从实际响应中获取）
        response = webdav_client.session.head(url, auth=webdav_client.auth, timeout=30)
        file_size = int(response.headers.get('Content-Length', 0))
        
        headers = {
            'Content-Type': mime_type,
            'Accept-Ranges': 'bytes',
            'Connection': 'keep-alive',
            'Content-Disposition': 'inline',
            'Access-Control-Expose-Headers': 'Content-Range,Content-Length,Content-Type',
        }
        
        # 如果能获取到文件大小，添加相关头
        if file_size > 0:
            if range_header:
                try:
                    start, end = parse_range_header(range_header, file_size)
                    headers['Content-Length'] = str(end - start + 1)
                    headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                    status_code = status.HTTP_206_PARTIAL_CONTENT
                except Exception:
                    # Range 请求解析失败，回退到普通请求
                    headers['Content-Length'] = str(file_size)
                    status_code = status.HTTP_200_OK
            else:
                headers['Content-Length'] = str(file_size)
                status_code = status.HTTP_200_OK
        else:
            # 如果不知道文件大小，使用分块传输（浏览器仍然可以播放）
            headers['Transfer-Encoding'] = 'chunked'
            status_code = status.HTTP_200_OK
        
        return StreamingResponse(
            webdav_iterator(),
            status_code=status_code,
            headers=headers
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebDAV 流传输失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


def stream_file(source_type: str, file_path: str, range_header: Optional[str] = None, 
               webdav_client=None) -> StreamingResponse:
    """统一的文件流接口"""
    if source_type == 'local':
        return stream_local_file(file_path, range_header)
    elif source_type == 'webdav' and webdav_client:
        return stream_webdav_file(webdav_client, file_path, range_header)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported source type")


def get_stream_info(file_path: str) -> Dict[str, Any]:
    """获取文件流信息"""
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        mime_type = get_mime_type(file_path)
        return {
            'exists': True,
            'size': file_size,
            'mime_type': mime_type,
            'extension': os.path.splitext(file_path)[1].lower()
        }
    return {
        'exists': False,
        'size': 0,
        'mime_type': '',
        'extension': ''
    }
