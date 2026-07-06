# 服务器 API 文档

本文档描述前端服务器页当前需要对接的真实接口。接口统一使用 JSON，请求基础路径为 `/api`，Vite 开发环境会将 `/api` 代理到后端服务。

## 通用响应

所有接口建议返回统一结构：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

- `code`: `0` 表示成功，非 `0` 表示失败。
- `message`: 失败原因或成功提示。
- `data`: 业务数据。

前端会在 `code !== 0` 时把 `message` 显示为错误提示。

## 数据源类型

添加数据源时，页面只展示两个大类：

| 大类 | 可选类型 | type |
| --- | --- | --- |
| 服务器 | WebDAV | `webdav` |
| 服务器 | OpenList | `openlist` |
| 本地存储 | 本地目录 | `local` |

## Source 对象

```json
{
  "id": "src-webdav-1",
  "name": "夸克",
  "type": "webdav",
  "typeLabel": "WebDAV",
  "path": "https://dav.example.com/media",
  "username": "demo",
  "active": false,
  "tint": "rgba(98, 96, 126, 0.76)",
  "stats": {
    "files": 1497,
    "movies": 0,
    "series": 0,
    "anime": 0,
    "music": 0,
    "unmatched": 0
  },
  "createdAt": "2026-06-06T10:00:00+08:00",
  "updatedAt": "2026-06-06T10:00:00+08:00"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 数据源唯一 ID。 |
| `name` | string | 是 | 数据源名称。 |
| `type` | string | 是 | `webdav`、`openlist` 或 `local`。 |
| `typeLabel` | string | 否 | 显示名称，不传时前端按 `type` 兜底显示。 |
| `path` | string | 是 | WebDAV / OpenList 地址或本地路径。 |
| `username` | string | 否 | 用户名。密码不要在列表接口中返回。 |
| `active` | boolean | 否 | 是否为当前选中的资源库。 |
| `tint` | string | 否 | 卡片主题色；不传时前端随机生成。 |
| `stats` | object | 是 | 资源统计。 |

## 获取数据源列表

```http
GET /api/sources
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "id": "src-webdav-1",
        "name": "夸克",
        "type": "webdav",
        "typeLabel": "WebDAV",
        "path": "https://dav.example.com/media",
        "active": false,
        "stats": {
          "files": 1497,
          "movies": 0,
          "series": 0,
          "anime": 0,
          "music": 0,
          "unmatched": 0
        }
      }
    ]
  }
}
```

## 验证连接

用于添加或修改数据源时测试连接。

```http
POST /api/sources/verify
Content-Type: application/json
```

请求：

```json
{
  "name": "WebDAV",
  "type": "webdav",
  "path": "https://dav.example.com/media",
  "username": "demo",
  "password": "secret"
}
```

响应：

```json
{
  "code": 0,
  "message": "连接成功",
  "data": {
    "ok": true
  }
}
```

失败时：

```json
{
  "code": 40001,
  "message": "连接失败，请检查地址或账号密码",
  "data": {
    "ok": false
  }
}
```

## 浏览媒体路径

点击添加后，前端会进入媒体路径选择页。后端需要根据当前路径返回目录和文件，文件夹与文件都通过复选框选择。

```http
POST /api/sources/browse
Content-Type: application/json
```

请求：

```json
{
  "type": "webdav",
  "path": "https://dav.example.com/media",
  "username": "demo",
  "password": "secret",
  "currentPath": "/"
}
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "path": "/",
    "entries": [
      {
        "name": "电影",
        "type": "folder",
        "path": "/电影"
      },
      {
        "name": "夜航信号.mp4",
        "type": "file",
        "path": "/夜航信号.mp4",
        "size": 1843200000,
        "modifiedAt": "2026-06-06T10:00:00+08:00"
      }
    ]
  }
}
```

规则：

- `entries[].type` 只能是 `folder` 或 `file`。
- 用户选择文件夹时，后端添加数据源后应扫描该文件夹下内容。
- 用户选择文件时，后端只添加对应文件。
- 前端会用 `entries[].path` 作为后续进入目录和确认添加的路径。

## 添加数据源

确认选择媒体路径后调用。前端支持一次选择多个文件夹或文件。

```http
POST /api/sources
Content-Type: application/json
```

请求：

```json
{
  "name": "WebDAV",
  "type": "webdav",
  "path": "https://dav.example.com/media",
  "username": "demo",
  "password": "secret",
  "selectedPaths": [
    {
      "name": "电影",
      "type": "folder",
      "path": "/电影"
    },
    {
      "name": "夜航信号.mp4",
      "type": "file",
      "path": "/夜航信号.mp4"
    }
  ]
}
```

响应推荐直接返回最新列表：

```json
{
  "code": 0,
  "message": "添加成功",
  "data": {
    "list": []
  }
}
```

也可以只返回新增对象：

```json
{
  "code": 0,
  "message": "添加成功",
  "data": {
    "source": {}
  }
}
```

## 修改数据源

卡片菜单点击“修改”后，前端会回显已有数据并提交更新。

```http
PUT /api/sources/{id}
Content-Type: application/json
```

请求：

```json
{
  "name": "夸克",
  "type": "webdav",
  "path": "https://dav.example.com/media",
  "username": "demo",
  "password": "new-secret"
}
```

响应：

```json
{
  "code": 0,
  "message": "修改成功",
  "data": {
    "source": {}
  }
}
```

## 重扫数据源

卡片菜单点击“重扫”后调用。后端根据数据源保存的路径重新扫描并返回最新统计。

```http
POST /api/sources/{id}/rescan
```

响应：

```json
{
  "code": 0,
  "message": "重扫完成",
  "data": {
    "source": {}
  }
}
```

## 删除数据源

卡片菜单点击“删除”后，前端会先弹出确认框，再调用删除接口。

```http
DELETE /api/sources/{id}
```

响应：

```json
{
  "code": 0,
  "message": "删除成功",
  "data": {
    "deleted": true
  }
}
```

## 前端当前对接点

- 列表页初次进入调用 `GET /api/sources`。
- 添加/修改弹窗中的“验证连接”调用 `POST /api/sources/verify`。
- 添加弹窗点击“添加”后调用 `POST /api/sources/browse` 打开路径选择。
- 路径选择页确认后调用 `POST /api/sources`。
- 修改调用 `PUT /api/sources/{id}`。
- 重扫调用 `POST /api/sources/{id}/rescan`。
- 删除调用 `DELETE /api/sources/{id}`。
