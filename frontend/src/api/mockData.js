export const MOCK_DATA = {
  stats: {
    total: 128,
    remote: 86,
    local: 42,
    favorite: 18
  },

  hero: [
    {
      id: 'hero-1',
      title: '星际穿越',
      category: 'movie',
      year: 2014,
      rating: '9.2',
      description: '地球面临末日，人类踏上跨越星际的壮丽旅程，寻找新的家园与希望。',
      backdropUrl: 'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=1920&q=85',
      tags: ['科幻', '冒险', '4K REMUX'],
      sourceType: 'webdav',
      sourceName: '蓝光原盘'
    },
    {
      id: 'hero-2',
      title: '沙丘 2',
      category: 'movie',
      year: 2024,
      rating: '8.9',
      description: '沙漠、命运和权力交织成新的史诗，适合在大屏幕上继续放映。',
      backdropUrl: 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=1920&q=85',
      tags: ['科幻', '史诗', 'HDR'],
      sourceType: 'openlist',
      sourceName: 'OpenList 电影库'
    },
    {
      id: 'hero-3',
      title: '盗梦空间',
      category: 'movie',
      year: 2010,
      rating: '9.3',
      description: '层层梦境像精密机械一样展开，每一次回看都能发现新的线索。',
      backdropUrl: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=1920&q=85',
      tags: ['悬疑', '科幻', '重看推荐'],
      sourceType: 'local',
      sourceName: '本地硬盘'
    }
  ],

  items: [
    {
      id: 'movie-1',
      title: '沙丘 2',
      category: 'movie',
      year: 2024,
      rating: '8.9',
      progress: { percent: 68 },
      coverUrl: 'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=700&q=85',
      backdropUrl: 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=1600&q=85',
      sourceType: 'openlist',
      sourceName: 'OpenList'
    },
    {
      id: 'movie-2',
      title: '奥本海默',
      category: 'movie',
      year: 2023,
      rating: '9.1',
      progress: { percent: 42 },
      coverUrl: 'https://images.unsplash.com/photo-1505686994434-e3cc5abf1330?w=700&q=85',
      backdropUrl: 'https://images.unsplash.com/photo-1485846234645-a62644f84728?w=1600&q=85',
      sourceType: 'webdav',
      sourceName: '蓝光原盘'
    },
    {
      id: 'movie-3',
      title: '盗梦空间',
      category: 'movie',
      year: 2010,
      rating: '9.3',
      progress: { percent: 87 },
      coverUrl: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=700&q=85',
      sourceType: 'webdav',
      sourceName: 'NAS 片库'
    },
    {
      id: 'movie-4',
      title: '这个杀手不太冷',
      category: 'movie',
      year: 1994,
      rating: '9.4',
      progress: { percent: 100 },
      coverUrl: 'https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?w=700&q=85',
      sourceType: 'local',
      sourceName: '本地硬盘'
    },
    {
      id: 'movie-5',
      title: '泰坦尼克号',
      category: 'movie',
      year: 1997,
      rating: '9.5',
      progress: { percent: 58 },
      coverUrl: 'https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=700&q=85',
      sourceType: 'openlist',
      sourceName: '经典电影'
    },
    {
      id: 'movie-6',
      title: '阿甘正传',
      category: 'movie',
      year: 1994,
      rating: '9.5',
      progress: { percent: 100 },
      coverUrl: 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=700&q=85',
      sourceType: 'local',
      sourceName: '本地硬盘'
    },
    {
      id: 'movie-7',
      title: '千与千寻',
      category: 'anime',
      year: 2001,
      rating: '9.4',
      progress: { percent: 89 },
      coverUrl: 'https://images.unsplash.com/photo-1560169897-fc0cdbdfa4d5?w=700&q=85',
      sourceType: 'openlist',
      sourceName: '动漫合集'
    },
    {
      id: 'movie-8',
      title: '无间道',
      category: 'movie',
      year: 2002,
      rating: '9.1',
      progress: { percent: 91 },
      coverUrl: 'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=700&q=85',
      sourceType: 'webdav',
      sourceName: '华语电影'
    },
    {
      id: 'movie-9',
      title: '星际穿越',
      category: 'movie',
      year: 2014,
      rating: '9.2',
      progress: { percent: 76 },
      coverUrl: 'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=700&q=85',
      sourceType: 'webdav',
      sourceName: '蓝光原盘'
    },
    {
      id: 'movie-10',
      title: '指环王：王者无敌',
      category: 'movie',
      year: 2003,
      rating: '9.3',
      progress: { percent: 63 },
      coverUrl: 'https://images.unsplash.com/photo-1514539079130-25950c84af65?w=700&q=85',
      sourceType: 'openlist',
      sourceName: '史诗合集'
    },
    {
      id: 'movie-11',
      title: '黑客帝国',
      category: 'movie',
      year: 1999,
      rating: '9.1',
      progress: { percent: 45 },
      coverUrl: 'https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=700&q=85',
      sourceType: 'local',
      sourceName: '本地硬盘'
    },
    {
      id: 'movie-12',
      title: '布达佩斯大饭店',
      category: 'movie',
      year: 2014,
      rating: '8.9',
      progress: { percent: 33 },
      coverUrl: 'https://images.unsplash.com/photo-1524230572899-a752b3835840?w=700&q=85',
      sourceType: 'webdav',
      sourceName: '导演精选'
    }
  ],

  sources: [
    {
      id: 'source-1',
      name: 'NAS 电影库',
      type: 'WebDAV',
      active: true,
      tint: '#46d5c5',
      host: 'dav.example.com',
      port: '443',
      protocol: 'https',
      username: 'admin',
      password: 'password123',
      path: 'https://dav.example.com/movies',
      mountPath: 'movies',
      files: 1024,
      movies: 486,
      series: 128,
      anime: 256,
      music: 64,
      unmatched: 90
    },
    {
      id: 'source-2',
      name: '动漫合集',
      type: '内置 OpenList',
      active: true,
      tint: '#667eea',
      host: '',
      port: '',
      protocol: 'http',
      username: '',
      password: '',
      driver: 'quark',
      cookie: 'Cookie 示例',
      path: '/quark/anime',
      mountPath: '/quark/anime',
      files: 512,
      movies: 32,
      series: 64,
      anime: 380,
      music: 12,
      unmatched: 24
    },
    {
      id: 'source-3',
      name: '本地硬盘',
      type: '本地存储',
      active: false,
      tint: '#f06f5c',
      host: '',
      port: '',
      protocol: 'http',
      username: '',
      password: '',
      path: 'D:/Movies',
      mountPath: 'D:/Movies',
      files: 256,
      movies: 156,
      series: 48,
      anime: 32,
      music: 20,
      unmatched: 0
    }
  ],

  favorites: [
    {
      id: 'fav-1',
      title: '星际穿越',
      category: 'movie',
      year: 2014,
      sourceType: 'webdav',
      sourceName: '蓝光原盘',
      progress: { percent: 76 },
      coverUrl: 'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=700&q=85',
      backdropUrl: 'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=1600&q=85'
    },
    {
      id: 'fav-2',
      title: '盗梦空间',
      category: 'movie',
      year: 2010,
      sourceType: 'openlist',
      sourceName: 'OpenList',
      progress: { percent: 87 },
      coverUrl: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=700&q=85'
    },
    {
      id: 'fav-3',
      title: '千与千寻',
      category: 'anime',
      year: 2001,
      sourceType: 'local',
      sourceName: '本地硬盘',
      progress: { percent: 89 },
      coverUrl: 'https://images.unsplash.com/photo-1560169897-fc0cdbdfa4d5?w=700&q=85'
    }
  ],

  history: [
    {
      id: 'hist-1',
      title: '星际穿越',
      category: '电影',
      progress: 100,
      watchedAt: '06-12 21:30',
      coverUrl: 'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=700&q=85'
    },
    {
      id: 'hist-2',
      title: '沙丘 2',
      category: '电影',
      progress: 75,
      watchedAt: '06-11 22:15',
      coverUrl: 'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=700&q=85'
    },
    {
      id: 'hist-3',
      title: '盗梦空间',
      category: '电影',
      progress: 45,
      watchedAt: '06-10 20:00',
      coverUrl: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=700&q=85'
    }
  ]
}
