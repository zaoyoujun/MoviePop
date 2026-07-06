# JMH-MoviePop 后端 API 文档

> 适用代码：`backend/api/routes.py`  
> 基础路径：所有接口均以 `/api` 开头  
> 响应格式：所有业务接口统一返回 `{ code, message, data }`

## 1. 通用约定

### 1.1 统一响应

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

## 8. Viewing statistics

### 8.1 Statistics dashboard

`GET /api/movies/stats`

This endpoint keeps the legacy flat counters and also returns structured data for the real statistics page.
All values are computed from local library records, playback progress, favorites, tags, categories, and source type.

Response `data` fields:

| Field | Type | Description |
| --- | --- | --- |
| `files`, `movies`, `series`, `anime`, `music`, `unmatched` | number | Legacy library counters. |
| `watched`, `inProgress`, `completed`, `watchSeconds` | number | Legacy playback counters. |
| `overview` | object | Aggregated dashboard summary. |
| `metrics` | array | Top metric cards for the frontend. |
| `categoryDistribution` | array | Library category distribution. |
| `watchedCategoryDistribution` | array | Watched-item category distribution. |
| `sourceDistribution` | array | Local/WebDAV/OpenList distribution. |
| `tagDistribution` | array | Genre/country/tag frequency distribution. |
| `timeDistribution` | array | 24-hour viewing distribution based on `last_play_time`. |
| `weekdayDistribution` | array | Weekday viewing distribution based on `last_play_time`. |
| `completionStats` | array | Completed / in-progress / unwatched distribution. |
| `recentHistory` | array | Recent watched movie items in `MovieItem` shape. |
| `personality` | object | Local MBTI-like viewing-personality result. |

Example:

```json
{
  "overview": {
    "total": 30,
    "watched": 6,
    "completed": 1,
    "inProgress": 1,
    "favorite": 0,
    "watchSeconds": 3642,
    "watchHours": 1.0,
    "completionRate": 16.7,
    "favoriteRate": 0.0,
    "avgProgress": 17.7,
    "avgRating": 8.3
  },
  "metrics": [
    { "key": "total", "label": "片库条目", "value": 30, "unit": "部", "description": "当前片库中可识别的影视条目" }
  ],
  "categoryDistribution": [
    { "label": "动漫", "value": 18, "percent": 60.0 }
  ],
  "timeDistribution": [
    { "hour": 0, "label": "00:00", "value": 0, "percent": 0.0 }
  ],
  "personality": {
    "code": "ENTJ",
    "title": "片单指挥官",
    "algorithmVersion": "moviepop-local-v1",
    "dimensions": [
      { "key": "energy", "left": "独享", "right": "分享", "score": 78.8, "winner": "分享" }
    ]
  }
}
```

## Manual Scrape APIs

These APIs are used by `frontend/src/views/Scrape.vue`.

### List Scrape Sources

`GET /api/scrape/sources`

Response `data`:

```json
[
  { "label": "Auto", "value": "auto" },
  { "label": "TMDB", "value": "tmdb" },
  { "label": "AniBK", "value": "anibk" },
  { "label": "Douban", "value": "douban" }
]
```

### Search Metadata

`POST /api/scrape/search`

Request:

```json
{
  "source": "auto",
  "keyword": "Dr. Stone"
}
```

Response `data` is an array. Important fields:

| Field | Type | Notes |
| --- | --- | --- |
| `title` | string | Matched title |
| `source` | string | `tmdb`, `anibk`, or `douban` |
| `sourceId` | string/number | Source-side id or URL |
| `year` | number | Release year if available |
| `genres` | string[] | Genre tags if available |
| `country` | string | Region/country display text |
| `score` | number | Rating if available |
| `description` | string | Overview/intro |
| `posterUrl` | string | Poster preview URL |
| `coverUrl` | string | Same semantic as poster URL |
| `backdropUrl` | string | Large backdrop URL if available |

### Submit Metadata

`POST /api/scrape/submit`

Request:

```json
{
  "movie_id": "movie-id",
  "source": "tmdb",
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

The backend writes metadata back to the movie library and returns the updated movie detail.

## Playback Progress APIs

### Update Playback Progress

`POST /api/movies/{movie_id}/playback`

Request:

```json
{
  "episodeId": "realMovieId::ep1",
  "episodeNumber": 1,
  "currentTime": 120,
  "duration": 1440
}
```

The backend accepts embedded episode ids in the form `realMovieId::ep1`.
It stores `last_play_time` and `percent`, so `/api/movies/history` and `/api/movies/stats` can reflect playback state.

## OpenList credentials fields

Frontend should read OpenList credentials from `GET /api/openlist/status` first.
The response `data` includes these equivalent fields:

```json
{
  "admin_username": "admin",
  "admin_password": "xxxx",
  "openlist_username": "admin",
  "openlist_password": "xxxx",
  "username": "admin",
  "password": "xxxx"
}
```

Recommended frontend mapping:

| UI field | Preferred API field | Fallback API fields |
| --- | --- | --- |
| username | `admin_username` | `openlist_username`, `username`, constant `admin` |
| password | `admin_password` | `openlist_password`, `password` |

`GET /api/config` also returns:

```json
{
  "openlist_admin_username": "admin",
  "openlist_admin_password": "xxxx",
  "openlist_username": "admin",
  "openlist_password": "xxxx"
}
```

The OpenList built-in admin username is always `admin`.

## OpenList storage cleanup

When deleting an OpenList data-source card, frontend should call:

```http
DELETE /api/sources/{source_id}
```

The backend will delete:

- the app data source record
- related library entries
- the matching OpenList storage by `storage_id` or `mount_path`
- the same driver's temporary preview mount, such as `/__preview_115`

`data.openlist.deleted === true` means the OpenList mount is no longer present.
This includes idempotent success when the mount had already been deleted.

Manual cleanup endpoint for old duplicated/orphan storages:

```http
POST /api/openlist/storages/cleanup
```

It removes `/__preview_*` storages and OpenList storages that are not referenced by any app data source.

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | number | `0` 表示成功，非 `0` 表示失败 |
| `message` | string | 可直接展示给用户的提示 |
| `data` | any | 业务数据，失败时可能为 `null` |

### 1.2 请求格式

后端同时支持：

- `application/json`
- `application/x-www-form-urlencoded`
- `multipart/form-data`

前端现有 `postForm()` 可以继续使用；新增接口也可以直接用 JSON。

### 1.3 常见错误码

| code | 说明 |
| --- | --- |
| `400` | 参数错误、前置条件未满足 |
| `40001` | 数据源连接校验失败 |
| `404` | 数据源或影片不存在 |
| `500` | 后端内部异常 |

## 2. 前端接入总流程

### 2.1 添加 WebDAV 数据源

1. 打开“添加数据源”弹窗。
2. 用户选择 `WebDAV`。
3. 用户填写地址、端口、协议、用户名、密码。
4. 可调用 `/api/sources/verify` 校验连接。
5. 可调用 `/api/sources/browse` 浏览目录。
6. 用户选择要扫描的目录后调用 `/api/sources` 保存。
7. 保存成功后，后端会自动后台扫描。
8. 前端轮询 `/api/sources/{source_id}/scan-status` 显示扫描进度。

### 2.2 添加普通 Web 数据源

当前后端把“web 数据源”按 WebDAV 数据源处理。前端类型请传：

```json
{
  "type": "webdav"
}
```

### 2.3 使用内置 OpenList 挂载网盘

前端必须按这个顺序做：

1. 设置页调用 `GET /api/config` 读取 `openlist_enabled`。
2. 用户打开“内置 OpenList”开关后，调用 `POST /api/config` 保存。
3. 调用 `POST /api/openlist/start` 启动内置 OpenList。
4. 调用 `GET /api/openlist/status` 确认：
   - `status === "running"`
   - `logged_in === true`
   - `enabled === true`
5. 挂载数据源弹窗里才显示“内置 OpenList”选项。
6. 调用 `GET /api/openlist/drivers` 获取可选网盘类型和字段。
7. 用户选择网盘，例如夸克网盘，填入 Cookie。
8. 调用 `POST /api/sources/openlist/mount` 创建 OpenList 存储并保存为数据源。
9. 后端会自动后台扫描。
10. 前端轮询 `/api/sources/{source_id}/scan-status` 显示扫描进度。

如果第 4 步前置条件未满足，挂载接口会返回 `code=400`，`message` 可直接提示用户。

## 3. 配置接口

### 3.1 获取公开配置

`GET /api/config`

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

### 3.2 更新配置

`POST /api/config`

请求示例：

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

说明：

- `openlist_enabled=true` 只是开启功能，不等于启动服务。
- 启动服务请继续调用 `POST /api/openlist/start`。
- `enable_auto_scrape=true` 后，扫描时会尝试自动刮削封面和简介。

### 3.3 刮削设置

#### 获取刮削设置

`GET /api/settings/scraper`

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "enable_auto_scrape": true,
    "scrape_source": "auto",
    "tmdb_api_key": "xxxx",
    "tmdbApiKey": "xxxx",
    "tmdb_api_base": "https://api.themoviedb.org/3",
    "tmdb_image_base": "https://image.tmdb.org/t/p/w500",
    "douban_cookie": "bid=...",
    "doubanCookie": "bid=..."
  }
}
```

#### 保存刮削设置

`POST /api/settings/scraper`

前端现有字段：

```json
{
  "doubanCookie": "bid=...",
  "tmdbApiKey": "xxxx"
}
```

后端同时兼容 snake_case：

```json
{
  "douban_cookie": "bid=...",
  "tmdb_api_key": "xxxx",
  "enable_auto_scrape": true,
  "scrape_source": "auto"
}
```

说明：

- 保存成功后写入 `backend/data/config.json`。
- `GET /api/config` 也会返回 `tmdb_api_key`、`douban_cookie` 等字段，方便设置页初始化。

## 4. 数据源接口

### 4.1 获取数据源列表

`GET /api/sources`

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "abc123",
      "name": "我的 WebDAV",
      "type": "webdav",
      "typeLabel": "WebDAV",
      "path": "https://dav.example.com",
      "username": "user",
      "active": true,
      "mountPath": "/Movies",
      "selected_paths": ["/Movies"],
      "stats": {
        "files": 0,
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

注意：

- OpenList 的 `cookie` 不会明文返回，会显示为 `******`。
- 如果前端需要重新编辑 Cookie，请让用户重新填写。

### 4.2 校验数据源

`POST /api/sources/verify`

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

也可以直接传完整地址：

```json
{
  "type": "webdav",
  "path": "https://dav.example.com/dav",
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

OpenList 校验只检查内置服务是否已启动并登录。

成功响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "ok": true
  }
}
```

### 4.3 浏览目录

`POST /api/sources/browse`

#### 按连接信息浏览 WebDAV

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

### 4.4 添加 WebDAV 数据源

`POST /api/sources`

请求：

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

响应：

```json
{
  "code": 0,
  "message": "数据源添加成功，正在后台扫描",
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

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | 否 | 显示名称，不传后端自动生成 |
| `type` | 是 | 固定传 `webdav` |
| `host` / `path` | 是 | `host` 可传域名，`path` 可传完整 URL |
| `port` | 否 | 端口 |
| `protocol` | 否 | `http` 或 `https`，默认 `http` |
| `username` | 否 | WebDAV 用户名 |
| `password` | 否 | WebDAV 密码 |
| `selected_paths` | 否 | 用户选择要扫描的目录 |
| `auto_scan` | 否 | 默认 `true`，保存后自动扫描 |

### 4.5 添加本地数据源

`POST /api/sources`

请求：

```json
{
  "name": "本地视频",
  "type": "local",
  "path": "D:/Videos",
  "selected_paths": ["D:/Videos/Movies"],
  "auto_scan": true
}
```

### 4.6 更新数据源

`POST /api/sources/{source_id}`  
`PUT /api/sources/{source_id}`

请求字段同新增接口。

注意：

- `password` 为空时，后端保留原密码。
- 更新成功后默认重新扫描。

### 4.7 删除数据源

`DELETE /api/sources/{source_id}`

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "deleted": true
  }
}
```

### 4.8 查询扫描状态

`GET /api/sources/{source_id}/scan-status`

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

### 4.9 重新扫描

`POST /api/sources/{source_id}/rescan`

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

## 5. 内置 OpenList 接口

### 5.1 获取 OpenList 状态

`GET /api/openlist/status`

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
    "token_expires_in": 3600
  }
}
```

前端判断是否允许选择“内置 OpenList”：

```js
const canUseBuiltinOpenList =
  status.enabled === true &&
  status.status === 'running' &&
  status.logged_in === true
```

### 5.2 启动内置 OpenList

`POST /api/openlist/start`

前置条件：

- 必须先调用 `POST /api/config` 设置 `openlist_enabled=true`。

失败示例：

```json
{
  "code": 400,
  "message": "请先在设置中开启内置 OpenList 功能",
  "data": null
}
```

成功响应：

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

### 5.3 停止内置 OpenList

`POST /api/openlist/stop`

### 5.4 获取支持的网盘类型

`GET /api/openlist/drivers`

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
        },
        {
          "key": "root_folder_id",
          "label": "根目录 ID",
          "placeholder": "0"
        }
      ]
    }
  ]
}
```

前端建议：

- 用 `label` 显示给用户。
- 提交时传 `driver`。
- 根据 `fields` 动态渲染输入项。

### 5.5 浏览 OpenList 目录

`POST /api/openlist/browse`

请求：

```json
{
  "path": "/",
  "page": 1,
  "per_page": 100
}
```

响应结构同 `/api/sources/browse`。

### 5.6 挂载 OpenList 网盘并添加为数据源

`POST /api/sources/openlist/mount`

前置条件：

- `openlist_enabled=true`
- 内置 OpenList 已启动
- OpenList 已自动登录

#### 夸克网盘请求示例

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

#### 115 网盘请求示例

```json
{
  "name": "115 影视",
  "driver": "115 Cloud",
  "mount_path": "/115-movies",
  "cookie": "复制来的 Cookie 字符串",
  "root_folder_id": "0",
  "selected_paths": ["/115-movies"],
  "auto_scan": true
}
```

#### 阿里云盘 Open 请求示例

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

成功响应：

```json
{
  "code": 0,
  "message": "OpenList 数据源挂载成功，正在后台扫描",
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

常见失败：

```json
{
  "code": 400,
  "message": "请先在设置中开启内置 OpenList 功能",
  "data": null
}
```

```json
{
  "code": 400,
  "message": "请先启动内置 OpenList 服务",
  "data": null
}
```

```json
{
  "code": 400,
  "message": "OpenList 未登录，请先启动并完成自动登录",
  "data": null
}
```

## 6. 前端实现建议

### 6.1 设置页

设置页需要提供：

- “启用内置 OpenList”开关：保存到 `openlist_enabled`
- “OpenList 端口”：保存到 `openlist_port`
- “开机自动启动”：保存到 `openlist_auto_start`
- “自动登录”：保存到 `openlist_auto_login`
- “启动服务”按钮：调用 `POST /api/openlist/start`
- “停止服务”按钮：调用 `POST /api/openlist/stop`
- 状态区：轮询 `GET /api/openlist/status`

启动按钮逻辑：

```js
await post('/config', {
  openlist_enabled: true,
  openlist_port: 5244,
  openlist_auto_start: true,
  openlist_auto_login: true,
  openlist_auto_reset_password: true
})

await post('/openlist/start')

const status = await get('/openlist/status')
```

### 6.2 添加数据源弹窗

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

如果条件不满足，可以禁用选项并显示后端 `message`。

### 6.3 OpenList 挂载弹窗

流程：

```js
const drivers = await get('/openlist/drivers')
```

用户选择驱动后，根据 `fields` 渲染表单。

提交：

```js
await post('/sources/openlist/mount', {
  name,
  driver,
  mount_path,
  selected_paths: [mount_path],
  auto_scan: true,
  ...fieldValues
})
```

提交成功后：

```js
const { source } = result
pollScanStatus(source.id)
refreshSourceList()
```

### 6.4 扫描进度轮询

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

## 7. 影片接口

### 7.1 首页数据

`GET /api/movies/home`

Query：

| 字段 | 说明 |
| --- | --- |
| `category` | 可选，分类 |
| `limit` | 可选，默认 `12` |

说明：

- 首页轮播中的影片对象会返回 `backdropUrl`。
- 后端刮削到 TMDB 横向大图时，`backdropUrl` 优先使用 TMDB `backdrop_path` 下载后的本地图片。
- 没有横向大图时，`backdropUrl` 会退回 `coverUrl`。
- 首页会按同一作品聚合展示；明确版本目录不会生成多张首页卡片，例如 `原版` 和 `黑白原色版` 只显示一张作品卡。

影片对象新增/推荐使用字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | string | 展示标题；刮削成功时优先返回匹配到的片名 |
| `localTitle` | string | 扫描目录/文件清洗出的本地标题 |
| `matchedTitle` | string | 刮削源匹配到的标题，未匹配时为空 |
| `versionTitle` | string | 明确版本目录名，如 `黑白原色版`；没有版本目录时为空 |
| `variantCount` | number | 同一作品聚合后的条目数量 |
| `hasVersions` | boolean | 同一作品是否存在明确版本目录 |
| `seasonCount` | number | 同一作品聚合后的季/篇章数量 |
| `coverUrl` | string | 竖版海报，本地 `/covers/...` 地址 |
| `posterUrl` | string | `coverUrl` 的语义化别名 |
| `backdropUrl` | string | 横向大背景图，优先来自 TMDB 大尺寸 backdrop |
| `score` | number | 真实评分，来自 TMDB 或豆瓣；不会使用内部匹配分 |
| `genres` | string[] | 类型，如 `剧情`、`科幻` |
| `countries` | string[] | 地区/制片国家 |
| `region` | string | 地区展示文本，由 `countries` 拼接 |
| `languages` | string[] | 语言 |
| `metadataSource` | string | 命中的主刮削源，如 `tmdb`、`douban`、`anibk` |
| `originalTitle` | string | 原始标题 |
| `tmdbId` | string | TMDB ID |
| `tmdbMediaType` | string | `movie` / `tv` |
| `doubanUrl` | string | 豆瓣详情页地址 |
| `voteCount` | number | 评分人数/投票数 |
| `quality` | string | 从文件名识别出的清晰度 |
| `videoCodec` | string | 视频编码 |
| `audioInfo` | string | 音频信息 |
| `subtitleInfo` | string | 字幕信息 |

### 7.2 影片列表

`GET /api/movies`

Query：

| 字段 | 说明 |
| --- | --- |
| `category` | 分类，`all` 表示全部 |
| `keyword` | 搜索关键词 |
| `source_type` | `local` / `webdav` / `openlist` |
| `favorite` | 是否只看收藏 |
| `page` | 页码 |
| `page_size` | 每页数量 |

### 7.3 影片详情

`GET /api/movies/{movie_id}`

说明：

- 详情页返回的影片对象同样包含 `coverUrl` 和 `backdropUrl`。
- 前端大封面背景应优先使用 `backdropUrl`，普通竖版海报继续使用 `coverUrl`。
- 详情页可直接复用 7.1 中的 `genres`、`countries`、`region`、`languages`、`metadataSource` 等字段展示更多元数据。
- 同一作品的多季/篇章/分段会聚合到 `seasons` 数组中；季号、季标题、Part 不会被后端猜成版本。
- 类似《石纪元 NEW WORLD#1（第三季）》会作为 `seasons[]` 中的一个篇章返回，不进入 `versions`。
- 只有目录层级中明确存在版本目录时，才会生成多 `versions`。例如 `/quark/电视剧/暗影蜘蛛侠/黑白原色版/SpiderNoir.S01E01.mkv` 会生成 `versionTitle=黑白原色版`。
- `versions[]` 只表示真实版本目录切换；没有其他版本时返回空数组，前端不要显示版本切换区。
- 聚合版本中的分集 `episodeId` 可能是 `真实movieId::ep1` 这种格式；前端播放时应原样传回后端，不要截断 `::` 前缀。
- 分集对象会额外返回 `movieId`，如果前端播放逻辑支持按分集切换 movieId，可优先使用该字段；否则保持当前详情页 `movieId` 并原样传 `episodeId`，后端也能解析。

### 7.4 播放地址

`GET /api/movies/{movie_id}/play`

Query：

| 字段 | 说明 |
| --- | --- |
| `episode_id` | 可选，剧集 ID |
| `player_type` | 可选，默认 `web` |

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "movie-id",
    "episodeId": "episode-id",
    "playUrl": "https://example.com/movie.mkv",
    "headers": {},
    "sourceType": "webdav",
    "playerType": "web"
  }
}
```
