# JMH-MoviePop 后端 API 文档

## 基础约定

- Base URL: `/api`
- Content-Type: `application/json`
- 所有接口返回统一结构：
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
| 404 | 资源不存在 |
| 500 | 服务端错误 |

---

## 一、健康检查

### GET /api/health

检查服务是否运行正常。

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "running",
    "version": "1.0.0"
  }
}
```

---

## 二、配置接口

### GET /api/config

获取公开配置。

**响应：**
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

### POST /api/config

更新配置。

**请求：**
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

**响应：** 返回更新后的配置。

### GET /api/settings/scraper

获取刮削设置。

**响应：**
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

### POST /api/settings/scraper

保存刮削设置。

**请求：**
```json
{
  "doubanCookie": "bid=...",
  "tmdbApiKey": "xxxx",
  "enable_auto_scrape": true,
  "scrape_source": "auto"
}
```

### POST /api/cache/clear

清空缓存。

### POST /api/cache/clear-all

清空所有缓存（同 `/api/cache/clear`）。

### POST /api/reset

重置应用。

### POST /api/data/clear-all

清空所有数据（同 `/api/reset`）。

---

## 三、数据源接口

### GET /api/sources

获取数据源列表。

**响应：**
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

### POST /api/sources/verify

验证数据源连接。

**WebDAV 请求：**
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

**本地目录请求：**
```json
{
  "type": "local",
  "path": "D:/Videos"
}
```

**OpenList 请求：**
```json
{
  "type": "openlist"
}
```

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "ok": true
  }
}
```

### POST /api/sources/browse

浏览目录（按连接信息）。

**请求：**
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

或浏览已保存的数据源：
```json
{
  "source_id": "abc123",
  "path": "/Movies"
}
```

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "path": "/Movies",
    "items": [
      {
        "name": "Anime",
        "type": "folder",
        "path": "/Movies/Anime",
        "isDir": true
      }
    ],
    "ok": true
  }
}
```

### GET /api/sources/{source_id}/browse

浏览已保存数据源的目录。

**Query：**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| path | string | 否 | 路径，默认 `/` |

### POST /api/sources

添加数据源。

**WebDAV 请求：**
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

**本地目录请求：**
```json
{
  "name": "本地视频",
  "type": "local",
  "path": "D:/Videos",
  "selected_paths": ["D:/Videos/Movies"],
  "auto_scan": true
}
```

**响应：**
```json
{
  "code": 0,
  "message": "Data source added successfully, scanning in background",
  "data": {
    "source": {...},
    "scanStatus": {
      "scanning": true,
      "stage": "queued"
    }
  }
}
```

### POST /api/sources/{source_id}

更新数据源。

### PUT /api/sources/{source_id}

更新数据源（同 POST）。

### DELETE /api/sources/{source_id}

删除数据源。

**响应：**
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

### GET /api/sources/{source_id}/scan-status

查询扫描状态。

**响应：**
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

`stage` 可能值：`idle`, `queued`, `scan`, `parse`, `scrape`, `done`, `error`

### POST /api/sources/{source_id}/rescan

重新扫描数据源。

---

## 四、内置 OpenList 接口

### GET /api/openlist/status

获取 OpenList 状态。

**响应：**
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

### POST /api/openlist/start

启动内置 OpenList。

**响应：**
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

### POST /api/openlist/stop

停止内置 OpenList。

### GET /api/openlist/drivers

获取支持的网盘类型。

**响应：**
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

### GET /api/openlist/storages

获取 OpenList 存储列表。

### POST /api/openlist/storages/cleanup

清理 OpenList 存储。

### POST /api/openlist/browse

浏览 OpenList 目录。

**请求：**
```json
{
  "path": "/",
  "page": 1,
  "per_page": 100
}
```

### POST /api/sources/openlist/mount

挂载 OpenList 网盘并添加为数据源。

**夸克网盘请求：**
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

**阿里云盘 Open 请求：**
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

---

## 五、影视接口

### GET /api/movies/home

获取首页数据。

**Query：**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| category | string | 否 | 当前分类，不传表示全部 |
| limit | number | 否 | 首页列表数量，默认 `12` |

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "stats": {
      "total": 7,
      "remote": 7,
      "local": 0,
      "favorite": 0
    },
    "hero": [...],
    "items": [...]
  }
}
```

### GET /api/movies

获取影视列表。

**Query：**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| category | string | 否 | 分类，`all` 表示全部 |
| keyword | string | 否 | 按标题搜索 |
| source_type | string | 否 | `webdav` / `openlist` / `local` |
| favorite | boolean | 否 | 是否只看收藏 |
| page | number | 否 | 页码，默认 `1` |
| page_size | number | 否 | 每页数量，默认 `24` |

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [],
    "items": [],
    "pagination": {
      "page": 1,
      "pageSize": 24,
      "total": 100
    }
  }
}
```

### GET /api/movies/favorites

获取收藏列表。

**Query：**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| category | string | 否 | 分类 |
| keyword | string | 否 | 搜索关键词 |
| source_type | string | 否 | 数据源类型 |
| page | number | 否 | 页码，默认 `1` |
| page_size | number | 否 | 每页数量，默认 `24` |

### GET /api/movies/history

获取观影历史。

**Query：**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| page | number | 否 | 页码，默认 `1` |
| page_size | number | 否 | 每页数量，默认 `24` |

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": "farewell-lily",
        "title": "葬送的芙莉莲",
        "coverUrl": "...",
        "playback": {
          "currentEpisode": 1,
          "currentTime": 120,
          "duration": 1440,
          "percent": 8,
          "lastPlayTime": "...",
          "watchSeconds": 120
        },
        "lastPlayTime": "...",
        "watchSeconds": 120,
        "resumePosition": 120
      }
    ],
    "pagination": {...}
  }
}
```

### GET /api/movies/stats

获取观影统计。

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "overview": {...},
    "metrics": [...],
    "categoryDistribution": [...],
    "personality": {...}
  }
}
```

### GET /api/movies/{movie_id}

获取影视详情。

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "farewell-lily",
    "title": "葬送的芙莉莲",
    "category": "anime",
    "year": 2023,
    "coverUrl": "...",
    "backdropUrl": "...",
    "score": 8.9,
    "genres": ["动画", "奇幻"],
    "isFavorite": false,
    "episodes": [...],
    "progress": {...}
  }
}
```

### POST /api/movies/{movie_id}/favorite

收藏影视。

### DELETE /api/movies/{movie_id}/favorite

取消收藏。

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "farewell-lily",
    "isFavorite": true
  }
}
```

### POST /api/movies/{movie_id}/playback

更新播放进度。

**请求：**
```json
{
  "episodeId": "realMovieId::ep1",
  "episodeNumber": 1,
  "currentTime": 120,
  "duration": 1440,
  "watchSecondsDelta": 60
}
```

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "farewell-lily",
    "episodeId": "realMovieId::ep1",
    "episodeNumber": 1,
    "currentTime": 120,
    "duration": 1440,
    "percent": 8,
    "watchSeconds": 120,
    "episodeProgress": {...}
  }
}
```

### GET /api/movies/{movie_id}/play

获取播放信息。

**Query：**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| episode_id | string | 否 | 剧集 ID |
| player_type | string | 否 | 播放器类型，默认 `web` |

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "farewell-lily",
    "episodeId": "ep-1",
    "playUrl": "...",
    "headers": {...},
    "sourceType": "webdav",
    "playerType": "web",
    "resumePosition": 120
  }
}
```

### GET /api/movies/{movie_id}/stream

获取视频流（支持 Range 请求）。

**Query：**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| episode_id | string | 否 | 剧集 ID |

### POST /api/movies/{movie_id}/metadata/custom

更新自定义资料。

**请求：**
```json
{
  "data": {
    "title": "自定义标题",
    "description": "自定义简介",
    "coverUrl": "...",
    "backdropUrl": "...",
    "score": 9.0
  },
  "applyMode": "all",
  "metadataLocked": true
}
```

### POST /api/movies/{movie_id}/metadata/lock

锁定/解锁资料。

**请求：**
```json
{
  "locked": true
}
```

---

## 六、手动刮削接口

### GET /api/scrape/sources

获取刮削源列表。

**响应：**
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

### POST /api/scrape/search

搜索元数据。

**请求：**
```json
{
  "source": "auto",
  "keyword": "Dr. Stone"
}
```

**响应：**
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
      "posterUrl": "...",
      "coverUrl": "...",
      "backdropUrl": "..."
    }
  ]
}
```

### POST /api/scrape/submit

提交元数据。

**请求：**
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
    "coverUrl": "...",
    "backdropUrl": "..."
  }
}
```

---

## 七、分析接口

### GET /api/analytics/personality

获取观影人格画像。

**Query：**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| days | number | 否 | 天数，默认 `90`，范围 `7-365` |

### POST /api/analytics/events

记录分析事件。

**请求：**
```json
{
  "event_type": "play",
  "movie_id": "farewell-lily",
  "episode_id": "ep-1"
}
```

### POST /api/analytics/event

记录分析事件（同 `/api/analytics/events`）。

---

## 八、播放器接口

### POST /api/player/play

启动播放器。

**Query：**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| movie_id | string | 是 | 影视 ID |
| episode_id | string | 否 | 剧集 ID |
| position | number | 否 | 播放位置（秒），默认从上次播放位置继续 |

### POST /api/player/stop

停止播放器。

### POST /api/player/pause

暂停播放器（空操作）。

### POST /api/player/resume

恢复播放器（空操作）。

### POST /api/player/next

播放下一集。

### POST /api/player/previous

播放上一集。

### POST /api/player/seek

跳转播放位置（空操作）。

### POST /api/player/seek_relative

相对跳转（空操作）。

### POST /api/player/volume

设置音量（空操作）。

### POST /api/player/mute

静音/取消静音（空操作）。
