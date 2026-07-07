# 影视 API 文档

本文档描述前端影视相关页面需要对接的真实接口。接口统一使用 JSON，请求基础路径为 `/api`，Vite 开发环境会将 `/api` 代理到后端服务。

## 基础约定

- Base URL: `/api`
- Content-Type: `application/json`
- 时间字段统一使用 ISO 8601 字符串，例如 `2026-06-05T12:00:00+08:00`
- 图片地址可以是完整 URL，也可以是后端可访问的相对地址
- `sourceType` 可选值：
  - `webdav`
  - `openlist`
  - `local`
- `category` 可选值：
  - `movie`
  - `series`
  - `anime`
  - `variety`
  - `music`
  - `shorts`
  - `documentary`
  - `other`

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
| 400 | 参数错误 |
| 404 | 资源不存在 |
| 500 | 服务端错误 |

## 通用数据结构

### MovieItem

```json
{
  "id": "farewell-lily",
  "title": "葬送的芙莉莲",
  "localTitle": "葬送的芙莉莲",
  "matchedTitle": "",
  "versionTitle": "",
  "category": "anime",
  "year": 2023,
  "sourceType": "webdav",
  "sourceName": "WebDAV",
  "durationText": "10 集",
  "coverUrl": "https://example.com/cover.jpg",
  "posterUrl": "https://example.com/cover.jpg",
  "backdropUrl": "https://example.com/backdrop.jpg",
  "score": 8.9,
  "genres": ["动画", "奇幻", "冒险"],
  "countries": ["日本"],
  "region": "日本",
  "languages": ["日语"],
  "metadataSource": "tmdb",
  "originalTitle": "葬送のフリーレン",
  "tmdbId": "1105238",
  "tmdbMediaType": "tv",
  "doubanUrl": "https://movie.douban.com/subject/36142824/",
  "voteCount": 12580,
  "quality": "1080p",
  "videoCodec": "H.265",
  "audioInfo": "DTS-HD MA 5.1",
  "subtitleInfo": "中文字幕",
  "isFavorite": false,
  "hasVersions": false,
  "variantCount": 1,
  "seasonCount": 1,
  "progress": {
    "currentEpisode": 1,
    "totalEpisodes": 10,
    "percent": 12
  },
  "updatedAt": "2026-06-05T12:00:00+08:00"
}
```

### EpisodeItem

```json
{
  "id": "ep-1",
  "episodeId": "realMovieId::ep1",
  "title": "第 1 集",
  "episodeNumber": 1,
  "durationText": "24 分钟",
  "playUrl": "/api/movies/farewell-lily/play?episode_id=ep-1",
  "sourceType": "webdav",
  "movieId": "realMovieId"
}
```

## 1. 获取首页数据

用于首页一次性渲染大海报轮播、统计条和默认影视列表。

### Request

`GET /api/movies/home`

### Query

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| category | string | 否 | 当前分类，不传表示全部 |
| limit | number | 否 | 首页列表数量，默认 `12` |

### Response

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
    "hero": [
      {
        "id": "farewell-lily",
        "title": "葬送的芙莉莲",
        "category": "anime",
        "year": 2023,
        "sourceType": "webdav",
        "sourceName": "WebDAV",
        "durationText": "10 集",
        "backdropUrl": "https://example.com/frieren-backdrop.jpg",
        "tags": ["动画", "2023", "WebDAV", "10 集"]
      }
    ],
    "items": [
      {
        "id": "farewell-lily",
        "title": "葬送的芙莉莲",
        "category": "anime",
        "year": 2023,
        "sourceType": "webdav",
        "sourceName": "WebDAV",
        "coverUrl": "https://example.com/frieren-cover.jpg",
        "backdropUrl": "https://example.com/frieren-backdrop.jpg",
        "score": 8.9,
        "genres": ["动画", "奇幻", "冒险"],
        "isFavorite": false,
        "progress": {
          "currentEpisode": 1,
          "totalEpisodes": 10,
          "percent": 12
        },
        "updatedAt": "2026-06-05T12:00:00+08:00"
      }
    ]
  }
}
```

## 2. 获取影视列表

用于分类页、搜索、分页加载。

### Request

`GET /api/movies`

### Query

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| category | string | 否 | 分类，`all` 表示全部 |
| keyword | string | 否 | 按标题搜索 |
| source_type | string | 否 | `webdav` / `openlist` / `local` |
| favorite | boolean | 否 | 是否只看收藏 |
| page | number | 否 | 页码，默认 `1` |
| page_size | number | 否 | 每页数量，默认 `24` |

### Response

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

## 3. 获取收藏列表

### Request

`GET /api/movies/favorites`

### Query

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| category | string | 否 | 分类 |
| keyword | string | 否 | 搜索关键词 |
| source_type | string | 否 | 数据源类型 |
| page | number | 否 | 页码，默认 `1` |
| page_size | number | 否 | 每页数量，默认 `24` |

### Response

同 `GET /api/movies`

## 4. 获取观影历史

### Request

`GET /api/movies/history`

### Query

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| page | number | 否 | 页码，默认 `1` |
| page_size | number | 否 | 每页数量，默认 `24` |

### Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": "farewell-lily",
        "title": "葬送的芙莉莲",
        "coverUrl": "https://example.com/cover.jpg",
        "playback": {
          "currentEpisode": 1,
          "currentTime": 120,
          "duration": 1440,
          "percent": 8,
          "lastPlayTime": "2026-06-05T12:00:00+08:00",
          "watchSeconds": 120
        },
        "lastPlayTime": "2026-06-05T12:00:00+08:00",
        "watchSeconds": 120,
        "resumePosition": 120
      }
    ],
    "pagination": {
      "page": 1,
      "pageSize": 24,
      "total": 100
    }
  }
}
```

## 5. 获取影视详情

用于详情页。

### Request

`GET /api/movies/:id`

### Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "farewell-lily",
    "title": "葬送的芙莉莲",
    "localTitle": "葬送的芙莉莲",
    "matchedTitle": "葬送のフリーレン",
    "versionTitle": "",
    "category": "anime",
    "year": 2023,
    "sourceType": "webdav",
    "sourceName": "WebDAV",
    "durationText": "10 集",
    "coverUrl": "https://example.com/frieren-cover.jpg",
    "posterUrl": "https://example.com/frieren-cover.jpg",
    "backdropUrl": "https://example.com/frieren-backdrop.jpg",
    "score": 8.9,
    "genres": ["动画", "奇幻", "冒险"],
    "countries": ["日本"],
    "region": "日本",
    "languages": ["日语"],
    "metadataSource": "tmdb",
    "originalTitle": "葬送のフリーレン",
    "description": "勇者一行击败魔王后的漫长旅途故事。",
    "isFavorite": false,
    "hasVersions": false,
    "versions": [],
    "seasons": [],
    "episodes": [
      {
        "id": "ep-1",
        "episodeId": "realMovieId::ep1",
        "title": "第 1 集",
        "episodeNumber": 1,
        "durationText": "24 分钟",
        "playUrl": "/api/movies/farewell-lily/play?episode_id=ep-1",
        "sourceType": "webdav",
        "movieId": "realMovieId"
      }
    ],
    "progress": {
      "currentEpisode": 1,
      "totalEpisodes": 10,
      "percent": 12
    },
    "metadataLocked": false,
    "updatedAt": "2026-06-05T12:00:00+08:00"
  }
}
```

## 6. 获取播放地址

用于点击“立即播放”。

### Request

`GET /api/movies/:id/play`

### Query

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| episode_id | string | 否 | 剧集 ID |
| player_type | string | 否 | 播放器类型，默认 `web` |

### Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "farewell-lily",
    "episodeId": "ep-1",
    "playUrl": "https://example.com/video.mp4",
    "headers": {
      "x-moviepop-prefetch": "parallel"
    },
    "sourceType": "webdav",
    "playerType": "web",
    "resumePosition": 120
  }
}
```

## 7. 获取视频流

用于 Web 播放器流式播放。

### Request

`GET /api/movies/:id/stream`

### Query

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| episode_id | string | 否 | 剧集 ID |

### Response

返回视频流（支持 Range 请求）。

## 8. 更新播放进度

### Request

`POST /api/movies/:id/playback`

### Body

```json
{
  "episodeId": "realMovieId::ep1",
  "episodeNumber": 1,
  "currentTime": 120,
  "duration": 1440,
  "watchSecondsDelta": 60
}
```

### Response

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
    "episodeProgress": {
      "currentTime": 120,
      "duration": 1440,
      "percent": 8,
      "watchSeconds": 60,
      "lastPlayTime": "2026-06-05T12:00:00+08:00"
    }
  }
}
```

## 9. 收藏/取消收藏

### 收藏

`POST /api/movies/:id/favorite`

### 取消收藏

`DELETE /api/movies/:id/favorite`

### Response

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

## 10. 更新自定义资料

### Request

`POST /api/movies/:id/metadata/custom`

### Body

```json
{
  "data": {
    "title": "自定义标题",
    "description": "自定义简介",
    "coverUrl": "https://example.com/custom-cover.jpg",
    "backdropUrl": "https://example.com/custom-backdrop.jpg",
    "score": 9.0
  },
  "applyMode": "all",
  "metadataLocked": true
}
```

### Response

返回更新后的影片详情。

## 11. 锁定/解锁资料

### Request

`POST /api/movies/:id/metadata/lock`

### Body

```json
{
  "locked": true
}
```

### Response

返回更新后的影片详情。

## 12. 观影统计

### Request

`GET /api/movies/stats`

### Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
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
    "watchedCategoryDistribution": [],
    "sourceDistribution": [],
    "tagDistribution": [],
    "timeDistribution": [],
    "weekdayDistribution": [],
    "completionStats": [],
    "recentHistory": [],
    "personality": {
      "code": "ENTJ",
      "title": "片单指挥官",
      "algorithmVersion": "moviepop-local-v1",
      "dimensions": []
    }
  }
}
```
