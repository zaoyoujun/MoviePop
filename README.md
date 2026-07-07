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

## 目录结构

```
JMH-MoviePop/
├── package.json              # 项目配置（Node.js + Electron）
├── vite.config.js           # Vite 构建配置
├── index.html               # 前端入口 HTML
├── jsconfig.json            # JS 路径别名配置
├── start-frontend.bat       # Windows 一键启动脚本
│
├── src/                     # Vue 前端源码
│   ├── api/                 # API 接口封装（含模拟数据）
│   ├── assets/              # 图片、样式、字体等资源
│   ├── components/          # 通用组件（按功能模块划分）
│   │   ├── common/          # 通用组件（播放器、弹窗等）
│   │   ├── detail/          # 详情页组件（Hero、Info、Recommend）
│   │   ├── home/            # 首页组件（Hero、Stats、MediaList）
│   │   └── server/          # 服务器管理组件（Header、Card、Grid、Modal）
│   ├── composables/         # 组合式函数（数据获取、状态管理）
│   ├── constants/           # 常量定义（分类、数据源类型）
│   ├── router/              # 路由配置
│   ├── utils/               # 工具函数
│   ├── views/               # 页面级视图
│   │   ├── Home.vue         # 首页
│   │   ├── Favorites.vue    # 收藏页
│   │   ├── Layout.vue       # 应用布局
│   │   ├── MovieDetail.vue  # 影片详情页
│   │   ├── Scrape.vue       # 手动刮削页
│   │   ├── Server.vue       # 服务器管理页
│   │   ├── Settings.vue     # 设置页
│   │   └── Stats.vue        # 观影统计页
│   ├── App.vue              # 根组件
│   ├── main.js              # 应用入口
│   └── style.css            # 全局样式
│
├── public/                  # 静态公共资源
│   ├── favicon.ico          # 网站图标
│   └── 图标.ico             # 应用图标
│
├── electron/                # Electron 桌面端
│   ├── main.js              # 主进程入口
│   ├── preload.cjs          # 预加载脚本（CJS 格式）
│   └── preload.js           # 预加载脚本（ESM 格式）
│
├── backend/                 # Python 后端
│   ├── api/                 # HTTP 接口路由
│   ├── core/                # 核心模块（扫描、刮削、文件解析）
│   ├── services/            # 业务逻辑服务
│   ├── player/              # 播放器相关
│   ├── openlist/            # OpenList 客户端
│   ├── app.py               # 应用入口
│   ├── config.py            # 配置管理
│   ├── run.py               # 启动脚本
│   └── requirements.txt     # Python 依赖
│
├── build/                   # 打包输出目录（electron-builder 产物）
├── docs/                    # 项目文档
└── scripts/                 # 辅助脚本
```

## 前端组件结构

```
components/
├── common/                  # 通用组件
│   ├── DetailTransition.vue # 详情页切换动画
│   ├── MediaCard.vue        # 媒体卡片
│   ├── PlayerBar.vue        # 播放控制栏
│   ├── ScanToast.vue        # 扫描状态提示
│   ├── StatCard.vue         # 统计卡片
│   └── WindowTitleBar.vue   # 自定义窗口标题栏
│
├── detail/                  # 影片详情页组件
│   ├── DetailEpisodes.vue   # 剧集列表
│   ├── DetailHero.vue       # 详情页头部（海报、标题、评分）
│   ├── DetailInfo.vue       # 详情页信息（文件信息、简介）
│   └── DetailRecommend.vue  # 相关推荐列表
│
├── home/                    # 首页组件
│   ├── HomeHero.vue         # 首页轮播区
│   ├── HomeStats.vue        # 首页统计卡片
│   └── HomeMediaList.vue    # 首页媒体列表
│
└── server/                  # 服务器管理组件
    ├── ServerHeader.vue     # 页面头部
    ├── SourceCard.vue       # 数据源卡片
    ├── SourceGrid.vue       # 数据源网格
    ├── AddSourceModal.vue   # 添加数据源弹窗
    └── BrowseModal.vue      # 目录浏览弹窗
```

## 开发模式

前端支持**演示模式**，可在无后端情况下运行：
- 使用模拟数据展示功能
- 媒体卡片支持点击跳转详情页
- 添加/编辑/删除数据源功能演示

## 快速开始

```bash
# 安装依赖（在项目根目录）
npm install

# 启动前端开发服务器
npm run dev

# 启动 Electron 开发模式（同时启动前端和 Electron）
npm run electron:dev
```

或者在 Windows 上双击 `start-frontend.bat` 一键启动。

## 构建命令

```bash
# 构建前端
npm run build

# 构建后端（Windows）
npm run backend:build

# 构建 Electron 应用
npm run electron:build

# 构建便携版（Windows）
npm run electron:portable
```

## API 文档

后端 API 接口文档详见 `docs/` 目录下的文档文件。
