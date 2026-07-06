# JMH-MoviePop

一个小型桌面播放器项目，使用 Vue 前端、Python 后端，并通过 Electron 打包为桌面软件。

## 功能特点

- **媒体库管理** - 支持 WebDAV、OpenList、本地存储多种数据源
- **媒体分类浏览** - 电影、剧集、动漫、综艺、音乐等分类
- **收藏与历史** - 收藏喜欢的媒体，查看观影历史
- **观影统计** - 统计观影时长、分类分布等数据
- **详情预览** - 展示媒体详细信息、相关推荐

## 技术栈

- **前端**: Vue 3 + Composition API + Vite
- **后端**: Python + FastAPI
- **桌面**: Electron
- **UI 组件**: Naive UI + Ionicons

## 目录规划

```
JMH-MoviePop/
├── backend/                 # Python 后端
│   ├── app/
│   │   ├── api/             # HTTP/WebSocket 接口
│   │   ├── core/            # 配置、启动、公共基础能力
│   │   ├── models/          # 数据模型
│   │   └── services/        # 播放、扫描、文件、字幕等业务逻辑
│   └── tests/                # 后端测试
│
├── frontend/                # Vue 前端
│   ├── public/               # 静态公共资源
│   └── src/
│       ├── api/              # API 接口封装（含模拟数据）
│       ├── assets/            # 图片、样式、字体等资源
│       ├── components/        # 通用组件（按功能模块划分）
│       │   ├── detail/       # 详情页组件（Hero、Info、Recommend）
│       │   ├── home/         # 首页组件（Hero、Stats、MediaList）
│       │   └── server/       # 服务器管理组件（Header、Card、Grid、Modal）
│       ├── router/            # 路由配置
│       ├── stores/            # 状态管理
│       └── views/             # 页面级视图
│           ├── Home.vue       # 首页
│           ├── Favorites.vue  # 收藏页
│           ├── History.vue    # 历史记录
│           ├── MovieDetail.vue # 影片详情页
│           ├── Server.vue     # 服务器管理页
│           ├── Stats.vue      # 观影统计页
│           ├── Settings.vue   # 设置页
│           └── Layout.vue     # 应用布局
│
├── electron/                 # Electron 桌面端
│   ├── main/                 # 主进程
│   ├── preload/              # 预加载脚本
│   └── resources/
│       └── icons/            # 应用图标
│
├── shared/                   # 前后端共享约定
│   ├── contracts/            # API 契约、接口说明
│   └── types/                # 共享类型定义
│
├── docs/                      # 项目文档
├── scripts/                   # 开发、构建、打包脚本
└── build/                     # 打包输出目录
```

## 前端组件结构

```
components/
├── detail/                   # 影片详情页组件
│   ├── DetailHero.vue        # 详情页头部（海报、标题、评分）
│   ├── DetailInfo.vue         # 详情页信息（文件信息、简介）
│   └── DetailRecommend.vue     # 相关推荐列表
│
├── home/                     # 首页组件
│   ├── HomeHero.vue          # 首页轮播区
│   ├── HomeStats.vue          # 首页统计卡片
│   └── HomeMediaList.vue      # 首页媒体列表
│
└── server/                   # 服务器管理组件
    ├── ServerHeader.vue       # 页面头部
    ├── SourceCard.vue         # 数据源卡片
    ├── SourceGrid.vue         # 数据源网格
    ├── AddSourceModal.vue      # 添加数据源弹窗
    └── BrowseModal.vue        # 目录浏览弹窗
```

## 开发模式

前端支持**演示模式**，可在无后端情况下运行：
- 使用模拟数据展示功能
- 媒体卡片支持点击跳转详情页
- 添加/编辑/删除数据源功能演示

## 快速开始

```bash
# 安装依赖
cd frontend
npm install

# 启动开发服务器
npm run dev
```

## 接口约定

详见 `shared/contracts/` 目录下的 API 契约文档。
