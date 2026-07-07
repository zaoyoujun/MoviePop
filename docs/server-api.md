# 服务器 API 文档

本文档描述前端服务器页和设置页需要对接的真实接口。接口统一使用 JSON，请求基础路径为 `/api`，Vite 开发环境会将 `/api` 代理到后端服务。

## 通用响应

所有接口返回统一结构：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

- `code`: `0` 表示成功，非 `0` 表示失败
- `message`: 失败原因或成功提示
- `data`: 业务数据

## 常用错误码

| code | 说明 |
| --- | --- |
| 0 | 成功 |
| 400 | 参数错误、前置条件未满足 |
| 40001 | 数据源连接校验失败 |
| 404 | 数据源或影片不存在 |
| 500 | 服务端错误 |

## 数据源类型

| 类型 | 说明 |
| --- | --- |
| `webdav` | WebDAV 服务器 |
| `openlist` | 内置 OpenList 网盘 |
| `local` | 本地目录 |

## Source 对象

```json
{
  "id": "src-webdav-1",
  "name": "夸克",
  "type": "webdav",
  "typeLabel": "WebDAV",
  "path": "https://dav.example.com/media",
  "username": "demo",
  "password": "******",
  "active": false,
  "mountPath": "/quark-movies",
  "selected_paths": ["/quark-movies"],
  "driver": "Quark",
  "cookie": "******",
  "tint": "rgba(98, 96, 126, 0.76)",
  "stats": {
    "files": 1497,
    "movies": 0,
    "series": 0,
    "anime": 0,
    "music": 0,
    "unmatched": 0
  },
  "scanError": "",
  "createdAt": "2026-06-06T10:00:00+08:00",
  "updatedAt": "2026-06-06T10:00:00+08:00"
}
```

## 一、配置接口

### 1.1 获取公开配置

```http
GET /api/config
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "openlist_enabled": false,
    "openlist_port": 5244,
    "openlist_auto_start": false,
    "openlist_auto_login": true,
    "openlist_auto_reset_password": true,
    "scan_max_depth": 2,
    "local_scan_max_depth": 3,
    "enable_auto_scrape": false,
    "scrape_source": "auto",
    "tmdb_api_key": "",
    "tmdb_api_base": "https://api.themoviedb.org/3",
    "tmdb_image_base": "https://image.tmdb.org/t/p/w500",
    "douban_cookie": ""
  }
}
```

### 1.2 更新配置

```http
POST /api/config
Content-Type: application/json
```

请求：

```json
{
  "openlist_enabled": true,
  "openlist_port": 5244,
  "openlist_auto_start": true,
  "openlist_auto_login": true,
  "openlist_auto_reset_password": true,
  "enable_auto_scrape": true
}
```

### 1.3 获取刮削设置

```http
GET /api/settings/scraper
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "enable_auto_scrape": true,
    "scrape_source": "auto",
    "scrapeSource": "auto",
    "tmdb_api_key": "xxxx",
    "tmdbApiKey": "xxxx",
    "tmdb_api_base": "https://api.themoviedb.org/3",
    "tmdb_image_base": "https://image.tmdb.org/t/p/w500",
    "douban_cookie": "bid=...",
    "doubanCookie": "bid=..."
  }
}
```

### 1.4 保存刮削设置

```http
POST /api/settings/scraper
Content-Type: application/json
```

请求：

```json
{
  "doubanCookie": "bid=...",
  "tmdbApiKey": "xxxx",
  "enable_auto_scrape": true,
  "scrape_source": "auto"
}
```

### 1.5 清空缓存

```http
POST /api/cache/clear
```

### 1.6 重置应用

```http
POST /api/reset
```

## 二、数据源接口

### 2.1 获取数据源列表

```http
GET /api/sources
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "src-webdav-1",
      "name": "夸克",
      "type": "webdav",
      "typeLabel": "WebDAV",
      "path": "https://dav.example.com/media",
      "username": "demo",
      "active": false,
      "mountPath": "/quark-movies",
      "selected_paths": ["/quark-movies"],
      "stats": {
        "files": 1497,
        "movies": 0,
        "series": 0,
        "anime": 0,
        "music": 0,
        "unmatched": 0
      },
      "scanError": ""
    }
  ]
}
```

### 2.2 验证数据源连接

```http
POST /api/sources/verify
Content-Type: application/json
```

#### WebDAV 请求

```json
{
  "type": "webdav",
  "host": "dav.example.com",
  "port": "443",
  "protocol": "https",
  "username": "user",
  "password": "password"
}
```

#### 本地目录请求

```json
{
  "type": "local",
  "path": "D:/Videos"
}
```

#### OpenList 请求

```json
{
  "type": "openlist"
}
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "ok": true
  }
}
```

### 2.3 浏览目录

```http
POST /api/sources/browse
Content-Type: application/json
```

#### 按连接信息浏览

```json
{
  "type": "webdav",
  "host": "dav.example.com",
  "port": "443",
  "protocol": "https",
  "username": "user",
  "password": "password",
  "path": "/Movies"
}
```

#### 浏览已保存的数据源

```json
{
  "source_id": "abc123",
  "path": "/Movies"
}
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "path": "/Movies",
    "ok": true,
    "items": [
      {
        "name": "Anime",
        "type": "folder",
        "path": "/Movies/Anime",
        "isDir": true
      },
      {
        "name": "movie.mkv",
        "type": "file",
        "path": "/Movies/movie.mkv",
        "isDir": false
      }
    ]
  }
}
```

### 2.4 添加数据源

```http
POST /api/sources
Content-Type: application/json
```

#### WebDAV 请求

```json
{
  "name": "我的 WebDAV",
  "type": "webdav",
  "host": "dav.example.com",
  "port": "443",
  "protocol": "https",
  "username": "user",
  "password": "password",
  "selected_paths": ["/Movies", "/Anime"],
  "auto_scan": true
}
```

#### 本地目录请求

```json
{
  "name": "本地视频",
  "type": "local",
  "path": "D:/Videos",
  "selected_paths": ["D:/Videos/Movies"],
  "auto_scan": true
}
```

响应：

```json
{
  "code": 0,
  "message": "Data source added successfully, scanning in background",
  "data": {
    "source": {
      "id": "abc123",
      "name": "我的 WebDAV",
      "type": "webdav"
    },
    "scanStatus": {
      "scanning": true,
      "stage": "queued"
    }
  }
}
```

### 2.5 更新数据源

```http
POST /api/sources/{id}
PUT /api/sources/{id}
Content-Type: application/json
```

请求字段同新增接口。

### 2.6 删除数据源

```http
DELETE /api/sources/{id}
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "deleted": true,
    "openlist": {
      "deleted": true
    }
  }
}
```

### 2.7 查询扫描状态

```http
GET /api/sources/{id}/scan-status
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "scanning": true,
    "stage": "scan",
    "current": "/Movies/Anime",
    "processed": 10,
    "total": 120,
    "error": "",
    "startedAt": "2026-06-24T09:40:00",
    "finishedAt": ""
  }
}
```

`stage` 可能值：

| stage | 说明 |
| --- | --- |
| `idle` | 空闲 |
| `queued` | 已排队 |
| `scan` | 正在扫描目录 |
| `parse` | 正在识别影片 |
| `scrape` | 正在刮削封面和简介 |
| `done` | 完成 |
| `error` | 失败 |

### 2.8 重新扫描

```http
POST /api/sources/{id}/rescan
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "source": {},
    "scanStatus": {
      "scanning": true,
      "stage": "queued"
    }
  }
}
```

## 三、内置 OpenList 接口

### 3.1 获取 OpenList 状态

```http
GET /api/openlist/status
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "running",
    "port": 5244,
    "pid": 1234,
    "uptime_seconds": 60,
    "error_message": "",
    "version": "v3.42.0",
    "binary_available": true,
    "auto_start": true,
    "auto_login": true,
    "auto_reset_password": true,
    "enabled": true,
    "base_url": "http://127.0.0.1:5244",
    "logged_in": true,
    "token_expires_in": 3600,
    "admin_username": "admin",
    "admin_password": "******",
    "openlist_username": "admin",
    "openlist_password": "******"
  }
}
```

### 3.2 启动内置 OpenList

```http
POST /api/openlist/start
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "success": true,
    "status": "running",
    "port": 5244,
    "logged_in": true
  }
}
```

### 3.3 停止内置 OpenList

```http
POST /api/openlist/stop
```

### 3.4 获取支持的网盘类型

```http
GET /api/openlist/drivers
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "driver": "Quark",
      "label": "夸克网盘",
      "fields": [
        {
          "key": "cookie",
          "label": "Cookie",
          "type": "textarea",
          "required": true
        }
      ]
    }
  ]
}
```

### 3.5 浏览 OpenList 目录

```http
POST /api/openlist/browse
Content-Type: application/json
```

请求：

```json
{
  "path": "/",
  "page": 1,
  "per_page": 100
}
```

响应结构同 `/api/sources/browse`。

### 3.6 挂载 OpenList 网盘并添加为数据源

```http
POST /api/sources/openlist/mount
Content-Type: application/json
```

#### 夸克网盘请求

```json
{
  "name": "夸克电影",
  "driver": "Quark",
  "mount_path": "/quark-movies",
  "cookie": "复制来的 Cookie 字符串",
  "root_folder_id": "0",
  "selected_paths": ["/quark-movies"],
  "auto_scan": true
}
```

#### 阿里云盘 Open 请求

```json
{
  "name": "阿里云盘",
  "driver": "AliyundriveOpen",
  "mount_path": "/aliyun",
  "refresh_token": "refresh token",
  "root_folder_id": "root",
  "drive_type": "default",
  "selected_paths": ["/aliyun"],
  "auto_scan": true
}
```

响应：

```json
{
  "code": 0,
  "message": "OpenList data source mounted successfully, scanning in background",
  "data": {
    "source": {
      "id": "abc123",
      "name": "夸克电影",
      "type": "openlist",
      "driver": "Quark",
      "mountPath": "/quark-movies",
      "selected_paths": ["/quark-movies"]
    },
    "storage": {
      "id": 1
    },
    "scanStatus": {
      "scanning": true,
      "stage": "queued"
    }
  }
}
```

### 3.7 获取 OpenList 存储列表

```http
GET /api/openlist/storages
```

### 3.8 清理 OpenList 存储

```http
POST /api/openlist/storages/cleanup
```

## 四、手动刮削接口

### 4.1 获取刮削源列表

```http
GET /api/scrape/sources
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {"label": "Auto", "value": "auto"},
    {"label": "TMDB", "value": "tmdb"},
    {"label": "AniBK", "value": "anibk"},
    {"label": "Douban", "value": "douban"}
  ]
}
```

### 4.2 搜索元数据

```http
POST /api/scrape/search
Content-Type: application/json
```

请求：

```json
{
  "source": "auto",
  "keyword": "Dr. Stone"
}
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "title": "Dr. Stone",
      "source": "tmdb",
      "sourceId": "77597",
      "year": 2019,
      "genres": ["Animation", "Sci-Fi"],
      "country": "日本",
      "score": 8.4,
      "description": "...",
      "posterUrl": "https://...",
      "coverUrl": "https://...",
      "backdropUrl": "https://..."
    }
  ]
}
```

### 4.3 提交元数据

```http
POST /api/scrape/submit
Content-Type: application/json
```

请求：

```json
{
  "movie_id": "movie-id",
  "source": "tmdb",
  "applyMode": "all",
  "data": {
    "title": "Matched Title",
    "year": 2024,
    "score": 8.4,
    "description": "...",
    "coverUrl": "https://...",
    "backdropUrl": "https://..."
  }
}
```

## 五、前端实现建议

### 5.1 设置页

设置页需要提供：

- “启用内置 OpenList”开关：保存到 `openlist_enabled`
- “OpenList 端口”：保存到 `openlist_port`
- “开机自动启动”：保存到 `openlist_auto_start`
- “自动登录”：保存到 `openlist_auto_login`
- “启动服务”按钮：调用 `POST /api/openlist/start`
- “停止服务”按钮：调用 `POST /api/openlist/stop`
- 状态区：轮询 `GET /api/openlist/status`

### 5.2 添加数据源弹窗

数据源类型建议：

- WebDAV
- 本地目录
- 内置 OpenList

“内置 OpenList”选项显示条件：

```js
const status = await get('/openlist/status')
const showBuiltinOpenList =
  status.enabled &&
  status.status === 'running' &&
  status.logged_in
```

### 5.3 扫描进度轮询

建议每 1 到 2 秒轮询一次：

```js
async function pollScanStatus(sourceId) {
  const timer = setInterval(async () => {
    const status = await get(`/sources/${sourceId}/scan-status`)
    updateScanUI(status)

    if (!status.scanning) {
      clearInterval(timer)
      refreshSourceList()
      refreshHomeData()
    }
  }, 1500)
}
```
