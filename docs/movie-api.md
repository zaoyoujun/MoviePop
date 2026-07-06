# 影视 API 文档

本文档先定义首页、分类列表、详情页需要的影视接口。前端会按这些字段消费数据，mock 时字段名尽量保持一致。

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

## 通用数据结构

### MovieItem

```json
{
  "id": "farewell-lily",
  "title": "葬送的芙莉莲",
  "alias": ["Frieren"],
  "category": "anime",
  "year": 2023,
  "sourceType": "webdav",
  "sourceName": "WebDAV",
  "durationText": "10 集",
  "coverUrl": "https://example.com/cover.jpg",
  "backdropUrl": "https://example.com/backdrop.jpg",
  "tags": ["动画", "奇幻", "冒险"],
  "score": 8.9,
  "isFavorite": false,
  "progress": {
    "currentEpisode": 1,
    "totalEpisodes": 10,
    "percent": 12
  },
  "updatedAt": "2026-06-05T12:00:00+08:00"
}
```

### LibraryStats

```json
{
  "total": 7,
  "remote": 7,
  "local": 0,
  "favorite": 0
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
        "alias": ["Frieren"],
        "category": "anime",
        "year": 2023,
        "sourceType": "webdav",
        "sourceName": "WebDAV",
        "durationText": "10 集",
        "coverUrl": "https://example.com/frieren-cover.jpg",
        "backdropUrl": "https://example.com/frieren-backdrop.jpg",
        "tags": ["动画", "奇幻", "冒险"],
        "score": 8.9,
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
| category | string | 否 | 分类 |
| keyword | string | 否 | 按标题、别名、简介搜索 |
| sourceType | string | 否 | `webdav` / `openlist` / `local` |
| favorite | boolean | 否 | 是否只看收藏 |
| page | number | 否 | 页码，默认 `1` |
| pageSize | number | 否 | 每页数量，默认 `24` |

### Response

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [],
    "pagination": {
      "page": 1,
      "pageSize": 24,
      "total": 100
    }
  }
}
```

`list` 中每一项使用 `MovieItem` 结构。

## 3. 获取影视详情

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
    "alias": ["Frieren"],
    "category": "anime",
    "year": 2023,
    "sourceType": "webdav",
    "sourceName": "WebDAV",
    "durationText": "10 集",
    "coverUrl": "https://example.com/frieren-cover.jpg",
    "backdropUrl": "https://example.com/frieren-backdrop.jpg",
    "tags": ["动画", "奇幻", "冒险"],
    "score": 8.9,
    "description": "勇者一行击败魔王后的漫长旅途故事。",
    "isFavorite": false,
    "episodes": [
      {
        "id": "ep-1",
        "title": "第 1 集",
        "episodeNumber": 1,
        "durationText": "24 分钟",
        "playUrl": "/api/movies/farewell-lily/play/ep-1",
        "sourceType": "webdav"
      }
    ],
    "progress": {
      "currentEpisode": 1,
      "totalEpisodes": 10,
      "percent": 12
    },
    "updatedAt": "2026-06-05T12:00:00+08:00"
  }
}
```

## 4. 获取播放地址

用于点击“立即播放”。

### Request

`GET /api/movies/:id/play`

### Query

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| episodeId | string | 否 | 剧集/动漫可传；电影可不传 |

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
      "Authorization": "Bearer mock-token"
    },
    "sourceType": "webdav"
  }
}
```

如果播放地址不需要额外请求，也可以直接在详情页 `episodes[].playUrl` 返回最终播放地址。

## 错误响应

```json
{
  "code": 404,
  "message": "movie not found",
  "data": null
}
```

常用错误码：

| code | 说明 |
| --- | --- |
| 0 | 成功 |
| 400 | 参数错误 |
| 404 | 资源不存在 |
| 500 | 服务端错误 |

## 前端首批需要 mock 的最低字段

如果你想先快速 mock 首页，只需要实现：

`GET /api/movies/home`

最低字段：

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
        "backdropUrl": "https://example.com/backdrop.jpg",
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
        "coverUrl": "https://example.com/cover.jpg"
      }
    ]
  }
}
```
