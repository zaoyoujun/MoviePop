"""SQLite 数据库服务"""
import sqlite3
import json
import os
from typing import Any
from datetime import datetime

try:
    from backend.config import AppConfig
except ImportError:
    from config import AppConfig

DB_PATH = str(AppConfig().DATA_DIR / 'library.db')

def init_db():
    """初始化数据库"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 启用 WAL 日志模式：后台任务（元数据拉取 / 热度采集）密集写入时，
    # 前台读请求不会被写锁阻塞，避免首次下载或补全期间页面/接口卡死。
    # journal_mode 是数据库级持久设置，设置一次后对所有连接生效。
    cursor.execute("PRAGMA journal_mode=WAL")
    # 写-写冲突时等待最多 8 秒再报 locked，而非立即抛错
    cursor.execute("PRAGMA busy_timeout=8000")
    conn.commit()

    # 创建电影表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id TEXT PRIMARY KEY,
            name TEXT,
            title TEXT,
            season INTEGER DEFAULT 1,
            season_title TEXT,
            episode_count INTEGER DEFAULT 0,
            episodes TEXT,
            is_series INTEGER DEFAULT 0,
            special_type TEXT,
            category TEXT,
            year_hint TEXT,
            source_label TEXT,
            file_path TEXT,
            files TEXT,
            cover_url TEXT,
            intro TEXT,
            rating REAL DEFAULT 0,
            tags TEXT,
            source_id TEXT,
            source_name TEXT,
            source_type TEXT,
            updated_at TEXT,
            year INTEGER,
            file_size TEXT,
            quality TEXT,
            subtitle_info TEXT,
            playback TEXT,
            backdrop_url TEXT,
            duration TEXT,
            genres TEXT,
            countries TEXT,
            languages TEXT,
            metadata_source TEXT,
            original_title TEXT,
            tmdb_id TEXT,
            tmdb_media_type TEXT,
            douban_url TEXT,
            vote_count INTEGER DEFAULT 0,
            release_group TEXT,
            video_codec TEXT,
            audio_info TEXT,
            franchise TEXT,
            search_title TEXT,
            series_title TEXT,
            part INTEGER DEFAULT 0,
            metadata_title TEXT,
            version_title TEXT,
            display_title TEXT,
            is_favorite INTEGER DEFAULT 0,
            metadata_locked INTEGER DEFAULT 0,
            added_at TEXT,
            chapter_name TEXT,
            home_display INTEGER DEFAULT 0,
            release_date TEXT,
            release_date_checked INTEGER DEFAULT 0,
            rating_checked INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('PRAGMA table_info(movies)')
    existing_movie_columns = {row[1] for row in cursor.fetchall()}
    for column_name, column_type in {
        'backdrop_url': 'TEXT',
        'duration': 'TEXT',
        'genres': 'TEXT',
        'countries': 'TEXT',
        'languages': 'TEXT',
        'metadata_source': 'TEXT',
        'original_title': 'TEXT',
        'tmdb_id': 'TEXT',
        'tmdb_media_type': 'TEXT',
        'douban_url': 'TEXT',
        'vote_count': 'INTEGER DEFAULT 0',
        'release_group': 'TEXT',
        'video_codec': 'TEXT',
        'audio_info': 'TEXT',
        'franchise': 'TEXT',
        'search_title': 'TEXT',
        'series_title': 'TEXT',
        'part': 'INTEGER DEFAULT 0',
        'metadata_title': 'TEXT',
        'version_title': 'TEXT',
        'display_title': 'TEXT',
        'is_favorite': 'INTEGER DEFAULT 0',
        'metadata_locked': 'INTEGER DEFAULT 0',
        'added_at': 'TEXT',
        'chapter_name': 'TEXT',
        'home_display': 'INTEGER DEFAULT 0',
        'release_date': 'TEXT',
        'release_date_checked': 'INTEGER DEFAULT 0',
        'rating_checked': 'INTEGER DEFAULT 0',
    }.items():
        if column_name not in existing_movie_columns:
            cursor.execute(f'ALTER TABLE movies ADD COLUMN {column_name} {column_type}')
    
    # 创建数据源表（存储敏感配置）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            path TEXT,
            username TEXT,
            password TEXT,
            driver TEXT,
            cookie TEXT,
            mount_path TEXT,
            host TEXT,
            port TEXT,
            protocol TEXT,
            selected_paths TEXT,
            active INTEGER DEFAULT 1,
            tint TEXT,
            stats TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    cursor.execute('PRAGMA table_info(sources)')
    existing_columns = {row[1] for row in cursor.fetchall()}
    for column_name, column_type in {
        'addition': 'TEXT',
        'storage_id': 'TEXT',
        'scan_error': 'TEXT',
    }.items():
        if column_name not in existing_columns:
            cursor.execute(f'ALTER TABLE sources ADD COLUMN {column_name} {column_type}')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS behavior_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            movie_id TEXT,
            episode_id TEXT,
            source_page TEXT,
            position REAL DEFAULT 0,
            duration REAL DEFAULT 0,
            playback_rate REAL DEFAULT 1,
            delta_seconds REAL DEFAULT 0,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_behavior_events_created_at ON behavior_events(created_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_behavior_events_movie_id ON behavior_events(movie_id)')

    # 精选虚拟片库（TMDB/Bangumi 精选拉取，约 1 万级）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata_pool (
            id TEXT PRIMARY KEY,
            source TEXT,
            external_id TEXT,
            media_type TEXT,
            title TEXT,
            original_title TEXT,
            release_date TEXT,
            year INTEGER,
            overview TEXT,
            genres TEXT,
            poster_path TEXT,
            backdrop_path TEXT,
            vote_average REAL,
            vote_count INTEGER,
            popularity REAL,
            origin_country TEXT,
            runtime INTEGER,
            status TEXT,
            detail_fetched INTEGER DEFAULT 0,
            fetched_at TEXT,
            updated_at TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_pool_title ON metadata_pool(title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_pool_year ON metadata_pool(year)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_pool_popularity ON metadata_pool(popularity DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_pool_vote_count ON metadata_pool(vote_count DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_pool_source_external ON metadata_pool(source, external_id)')

    # FTS5 全文索引（title/original_title/overview/genres）
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS metadata_pool_fts USING fts5(
            title, original_title, overview, genres,
            content='metadata_pool', content_rowid='rowid'
        )
    ''')
    # FTS5 外部内容表必须用触发器显式同步（'delete' 命令带旧值）。
    # 注意：不能直接 DELETE FROM metadata_pool_fts WHERE rowid=?——
    # external content 表删除时要读 content 表当前文本去匹配索引 term，
    # 首次插入 / 内容已更新时 index 与 content 不一致，FTS5 会报
    # "database disk image is malformed"（假损坏）。
    # genres 在主表存 JSON 数组字符串，这里展开成空格分隔便于分词。
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS trg_pool_fts_ai AFTER INSERT ON metadata_pool BEGIN
            INSERT INTO metadata_pool_fts(rowid, title, original_title, overview, genres)
            VALUES (new.rowid, new.title, new.original_title, new.overview,
                    replace(replace(replace(replace(new.genres, '["', ''), '"]', ''), '","', ' '), '"', ''));
        END
    ''')
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS trg_pool_fts_ad AFTER DELETE ON metadata_pool BEGIN
            INSERT INTO metadata_pool_fts(metadata_pool_fts, rowid, title, original_title, overview, genres)
            VALUES ('delete', old.rowid, old.title, old.original_title, old.overview,
                    replace(replace(replace(replace(old.genres, '["', ''), '"]', ''), '","', ' '), '"', ''));
        END
    ''')
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS trg_pool_fts_au AFTER UPDATE ON metadata_pool BEGIN
            INSERT INTO metadata_pool_fts(metadata_pool_fts, rowid, title, original_title, overview, genres)
            VALUES ('delete', old.rowid, old.title, old.original_title, old.overview,
                    replace(replace(replace(replace(old.genres, '["', ''), '"]', ''), '","', ' '), '"', ''));
            INSERT INTO metadata_pool_fts(rowid, title, original_title, overview, genres)
            VALUES (new.rowid, new.title, new.original_title, new.overview,
                    replace(replace(replace(replace(new.genres, '["', ''), '"]', ''), '","', ' '), '"', ''));
        END
    ''')

    # 热度信号时间序列（每次拉取存一行，支撑趋势走势图）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hotness_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pool_id TEXT,
            source TEXT,
            external_id TEXT,
            vote_average REAL,
            vote_count INTEGER,
            popularity REAL,
            collection_count INTEGER,
            fetched_at TEXT NOT NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hotness_pool ON hotness_series(pool_id, fetched_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hotness_fetched ON hotness_series(fetched_at)')

    # 愿望单/想看清单：收藏 metadata_pool 条目，与本地片库解耦
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wishlist (
            pool_id TEXT PRIMARY KEY,
            note TEXT DEFAULT '',
            added_at TEXT NOT NULL
        )
    ''')

    # 大模型响应缓存（方向 G：刮削识别 / 观影报告 / 推荐精排）
    # scope + request_hash 唯一，命中缓存不发起 HTTP 请求，控制费用。
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            request_meta TEXT,
            response_text TEXT NOT NULL,
            model TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(scope, request_hash)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_llm_cache_scope ON llm_cache(scope, created_at)')

    # TMDB 题材映射表（movie/tv 各一套 id→name，列表接口只有 genre_ids，靠它本地补全名称）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tmdb_genre_map (
            media_type TEXT NOT NULL,
            genre_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_en TEXT DEFAULT '',
            updated_at TEXT DEFAULT '',
            PRIMARY KEY (media_type, genre_id)
        )
    ''')

    # 通用应用状态键值表（调度器上次成功执行日期等，重启后用于错过补跑判断）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT ''
        )
    ''')

    # 旧库迁移：metadata_pool 增加 genre_ids 列（列表接口自带，纯本地即可回填题材名）
    pool_cols = [r[1] for r in cursor.execute("PRAGMA table_info(metadata_pool)").fetchall()]
    if 'genre_ids' not in pool_cols:
        cursor.execute("ALTER TABLE metadata_pool ADD COLUMN genre_ids TEXT DEFAULT '[]'")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_pool_genre_ids ON metadata_pool(genre_ids)")

    conn.commit()
    conn.close()

def save_library(movies, replace=True):
    """保存电影库到数据库"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()

    if replace:
        cursor.execute('DELETE FROM movies')
    
    for movie in movies:
        # 转换复杂字段为 JSON
        episodes_json = json.dumps(movie.get('episodes', []))
        files_json = json.dumps(movie.get('files', []))
        tags_json = json.dumps(movie.get('tags', []))
        playback_json = json.dumps(movie.get('playback', {}))
        genres_json = json.dumps(movie.get('genres', []))
        countries_json = json.dumps(movie.get('countries', []))
        languages_json = json.dumps(movie.get('languages', []))
        
        cursor.execute('''
            INSERT OR REPLACE INTO movies (
                id, name, title, season, season_title, episode_count,
                episodes, is_series, special_type, category, year_hint,
                source_label, file_path, files, cover_url, intro, rating,
                tags, source_id, source_name, source_type, updated_at,
                year, file_size, quality, subtitle_info, playback, backdrop_url,
                duration, genres, countries, languages, metadata_source,
                original_title, tmdb_id, tmdb_media_type, douban_url, vote_count,
                release_group, video_codec, audio_info, franchise, search_title, series_title, part,
                metadata_title, version_title, display_title, is_favorite, metadata_locked, added_at, chapter_name, home_display,
                release_date, release_date_checked, rating_checked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            movie.get('id', ''),
            movie.get('name', ''),
            movie.get('title', ''),
            movie.get('season', 1),
            movie.get('season_title', ''),
            movie.get('episode_count', 0),
            episodes_json,
            1 if movie.get('is_series') else 0,
            movie.get('special_type', ''),
            movie.get('category', ''),
            movie.get('year_hint', ''),
            movie.get('source_label', ''),
            movie.get('file_path', ''),
            files_json,
            movie.get('cover_url', ''),
            movie.get('intro', ''),
            movie.get('rating', 0),
            tags_json,
            movie.get('source_id', ''),
            movie.get('source_name', ''),
            movie.get('source_type', ''),
            movie.get('updated_at', datetime.now().isoformat()),
            movie.get('year'),
            movie.get('file_size', ''),
            movie.get('quality', ''),
            movie.get('subtitle_info', ''),
            playback_json,
            movie.get('backdrop_url', ''),
            movie.get('duration', ''),
            genres_json,
            countries_json,
            languages_json,
            movie.get('metadata_source', ''),
            movie.get('original_title', ''),
            str(movie.get('tmdb_id', '') or ''),
            movie.get('tmdb_media_type', ''),
            movie.get('douban_url', ''),
            int(movie.get('vote_count') or 0),
            movie.get('release_group', ''),
            movie.get('video_codec', ''),
            movie.get('audio_info', ''),
            movie.get('franchise', ''),
            movie.get('search_title', ''),
            movie.get('series_title', ''),
            int(movie.get('part') or 0),
            movie.get('metadata_title', ''),
            movie.get('version_title', ''),
            movie.get('display_title', ''),
            1 if movie.get('is_favorite') or movie.get('isFavorite') else 0,
            1 if movie.get('metadata_locked') or movie.get('metadataLocked') else 0,
            movie.get('added_at') or movie.get('updated_at') or datetime.now().isoformat(),
            movie.get('chapter_name', ''),
            1 if movie.get('home_display') or movie.get('homeDisplay') else 0,
            movie.get('release_date', ''),
            1 if movie.get('release_date_checked') or movie.get('releaseDateChecked') else 0,
            1 if movie.get('rating_checked') or movie.get('ratingChecked') else 0,
        ))
    
    conn.commit()
    conn.close()

def upsert_movie(movie):
    """Persist one scanned item without replacing the rest of the library."""
    if not isinstance(movie, dict) or not str(movie.get('id') or '').strip():
        raise ValueError('Movie id is required')
    save_library([movie], replace=False)


def remove_source_movies_not_in(source_id, movie_ids):
    """Remove stale entries for one source after a complete scan."""
    source_id = str(source_id or '').strip()
    if not source_id:
        return

    ids = [str(movie_id).strip() for movie_id in movie_ids if str(movie_id).strip()]
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    if ids:
        placeholders = ', '.join('?' for _ in ids)
        cursor.execute(
            f'DELETE FROM movies WHERE source_id = ? AND id NOT IN ({placeholders})',
            [source_id, *ids],
        )
    else:
        cursor.execute('DELETE FROM movies WHERE source_id = ?', (source_id,))
    conn.commit()
    conn.close()


def remove_source_movies_outside_paths(source_id, selected_paths):
    """Remove records from one source that fall outside its saved scan roots."""
    source_id = str(source_id or '').strip()
    roots = _normalized_scan_roots(selected_paths)
    if not source_id or not roots:
        return 0

    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    rows = cursor.execute(
        'SELECT id, file_path, files FROM movies WHERE source_id = ?',
        (source_id,),
    ).fetchall()
    stale_ids = []
    for movie_id, file_path, files_json in rows:
        paths = [file_path]
        try:
            files = json.loads(files_json) if files_json else []
        except (TypeError, json.JSONDecodeError):
            files = []
        if isinstance(files, list):
            paths.extend(files)
        usable_paths = [str(path or '').strip() for path in paths if str(path or '').strip()]
        if usable_paths and not any(_is_path_within_root(path, root) for path in usable_paths for root in roots):
            stale_ids.append(str(movie_id))

    if stale_ids:
        placeholders = ', '.join('?' for _ in stale_ids)
        cursor.execute(f'DELETE FROM movies WHERE id IN ({placeholders})', stale_ids)
        conn.commit()
    conn.close()
    return len(stale_ids)


def _normalized_scan_roots(values):
    if isinstance(values, str):
        values = [part.strip() for part in values.split(',') if part.strip()]
    if not isinstance(values, (list, tuple, set)):
        return []

    roots = []
    for value in values:
        root = str(value or '').strip().replace('\\', '/').rstrip('/')
        if not root:
            continue
        roots.append(root.casefold())
    return list(dict.fromkeys(roots))


def _is_path_within_root(path, root):
    candidate = str(path or '').strip().replace('\\', '/').rstrip('/').casefold()
    if not candidate:
        return False
    if root == '/':
        return candidate.startswith('/')
    return candidate == root or candidate.startswith(root + '/')


def load_library():
    """从数据库加载电影库"""
    if not os.path.exists(DB_PATH):
        init_db()
        return []
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM movies')
    rows = cursor.fetchall()
    
    movies = []
    for row in rows:
        movie = {
            'id': row[0],
            'name': row[1],
            'title': row[2],
            'season': row[3],
            'season_title': row[4],
            'episode_count': row[5],
            'episodes': json.loads(row[6]) if row[6] else [],
            'is_series': bool(row[7]),
            'special_type': row[8],
            'category': row[9],
            'year_hint': row[10],
            'source_label': row[11],
            'file_path': row[12],
            'files': json.loads(row[13]) if row[13] else [],
            'cover_url': row[14],
            'intro': row[15],
            'rating': row[16],
            'tags': json.loads(row[17]) if row[17] else [],
            'source_id': row[18],
            'source_name': row[19],
            'source_type': row[20],
            'updated_at': row[21],
            'year': row[22],
            'file_size': row[23],
            'quality': row[24],
            'subtitle_info': row[25],
            'playback': json.loads(row[26]) if row[26] else {},
            'backdrop_url': row[27] if len(row) > 27 else '',
            'duration': row[28] if len(row) > 28 else '',
            'genres': json.loads(row[29]) if len(row) > 29 and row[29] else [],
            'countries': json.loads(row[30]) if len(row) > 30 and row[30] else [],
            'languages': json.loads(row[31]) if len(row) > 31 and row[31] else [],
            'metadata_source': row[32] if len(row) > 32 else '',
            'original_title': row[33] if len(row) > 33 else '',
            'tmdb_id': row[34] if len(row) > 34 else '',
            'tmdb_media_type': row[35] if len(row) > 35 else '',
            'douban_url': row[36] if len(row) > 36 else '',
            'vote_count': row[37] if len(row) > 37 else 0,
            'release_group': row[38] if len(row) > 38 else '',
            'video_codec': row[39] if len(row) > 39 else '',
            'audio_info': row[40] if len(row) > 40 else '',
            'franchise': row[41] if len(row) > 41 else '',
            'search_title': row[42] if len(row) > 42 else '',
            'series_title': row[43] if len(row) > 43 else '',
            'part': row[44] if len(row) > 44 else 0,
            'metadata_title': row[45] if len(row) > 45 else '',
            'version_title': row[46] if len(row) > 46 else '',
            'display_title': row[47] if len(row) > 47 else '',
            'is_favorite': bool(row[48]) if len(row) > 48 else False,
            'metadata_locked': bool(row[49]) if len(row) > 49 else False,
            'added_at': row[50] if len(row) > 50 else '',
            'chapter_name': row[51] if len(row) > 51 else '',
            'home_display': bool(row[52]) if len(row) > 52 else False,
            'release_date': row[53] if len(row) > 53 else '',
            'release_date_checked': bool(row[54]) if len(row) > 54 else False,
            'rating_checked': bool(row[55]) if len(row) > 55 else False,
        }
        movies.append(movie)
    
    conn.close()
    return movies

def get_movie_by_id(movie_id):
    """根据 ID 获取电影"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM movies WHERE id = ?', (movie_id,))
    row = cursor.fetchone()
    
    if row:
        movie = {
            'id': row[0],
            'name': row[1],
            'title': row[2],
            'season': row[3],
            'season_title': row[4],
            'episode_count': row[5],
            'episodes': json.loads(row[6]) if row[6] else [],
            'is_series': bool(row[7]),
            'special_type': row[8],
            'category': row[9],
            'year_hint': row[10],
            'source_label': row[11],
            'file_path': row[12],
            'files': json.loads(row[13]) if row[13] else [],
            'cover_url': row[14],
            'intro': row[15],
            'rating': row[16],
            'tags': json.loads(row[17]) if row[17] else [],
            'source_id': row[18],
            'source_name': row[19],
            'source_type': row[20],
            'updated_at': row[21],
            'year': row[22],
            'file_size': row[23],
            'quality': row[24],
            'subtitle_info': row[25],
            'playback': json.loads(row[26]) if row[26] else {},
            'backdrop_url': row[27] if len(row) > 27 else '',
            'duration': row[28] if len(row) > 28 else '',
            'genres': json.loads(row[29]) if len(row) > 29 and row[29] else [],
            'countries': json.loads(row[30]) if len(row) > 30 and row[30] else [],
            'languages': json.loads(row[31]) if len(row) > 31 and row[31] else [],
            'metadata_source': row[32] if len(row) > 32 else '',
            'original_title': row[33] if len(row) > 33 else '',
            'tmdb_id': row[34] if len(row) > 34 else '',
            'tmdb_media_type': row[35] if len(row) > 35 else '',
            'douban_url': row[36] if len(row) > 36 else '',
            'vote_count': row[37] if len(row) > 37 else 0,
            'release_group': row[38] if len(row) > 38 else '',
            'video_codec': row[39] if len(row) > 39 else '',
            'audio_info': row[40] if len(row) > 40 else '',
            'franchise': row[41] if len(row) > 41 else '',
            'search_title': row[42] if len(row) > 42 else '',
            'series_title': row[43] if len(row) > 43 else '',
            'part': row[44] if len(row) > 44 else 0,
            'metadata_title': row[45] if len(row) > 45 else '',
            'version_title': row[46] if len(row) > 46 else '',
            'display_title': row[47] if len(row) > 47 else '',
            'is_favorite': bool(row[48]) if len(row) > 48 else False,
            'metadata_locked': bool(row[49]) if len(row) > 49 else False,
            'added_at': row[50] if len(row) > 50 else '',
            'chapter_name': row[51] if len(row) > 51 else '',
            'home_display': bool(row[52]) if len(row) > 52 else False,
            'release_date': row[53] if len(row) > 53 else '',
            'release_date_checked': bool(row[54]) if len(row) > 54 else False,
            'rating_checked': bool(row[55]) if len(row) > 55 else False,
        }
    else:
        movie = None
    
    conn.close()
    return movie

def update_playback(movie_id, episode_number, current_time, duration, watch_seconds_delta=0, episode_id=None):
    """更新播放进度"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    percent = 0
    try:
        duration_value = float(duration or 0)
        current_value = float(current_time or 0)
        if duration_value > 0:
            percent = round(max(0, min(100, current_value / duration_value * 100)), 2)
    except (TypeError, ValueError):
        percent = 0
    
    cursor.execute('SELECT playback FROM movies WHERE id = ?', (movie_id,))
    row = cursor.fetchone()
    previous = {}
    if row and row[0]:
        try:
            previous = json.loads(row[0])
            if not isinstance(previous, dict):
                previous = {}
        except Exception:
            previous = {}

    try:
        normalized_episode_number = int(episode_number or 0)
    except (TypeError, ValueError):
        normalized_episode_number = 0
    episode_key = str(episode_id or '').strip()
    if not episode_key and normalized_episode_number > 0:
        episode_key = f'ep{normalized_episode_number}'
    if not episode_key:
        episode_key = 'default'

    episode_map = previous.get('episodes') if isinstance(previous.get('episodes'), dict) else {}
    previous_episode = episode_map.get(episode_key) if isinstance(episode_map.get(episode_key), dict) else {}

    try:
        delta = int(float(watch_seconds_delta or 0))
    except (TypeError, ValueError):
        delta = 0
    if delta <= 0:
        try:
            last_position = int(float(previous_episode.get('current_time') or 0))
            position_delta = int(float(current_time or 0)) - last_position
            if 0 < position_delta <= 30:
                delta = position_delta
        except (TypeError, ValueError):
            delta = 0
    delta = max(0, min(delta, 120))
    total_watch_seconds = max(0, int(float(previous.get('watch_seconds') or 0))) + delta
    episode_watch_seconds = max(0, int(float(previous_episode.get('watch_seconds') or 0))) + delta
    now = datetime.now().isoformat()

    episode_playback = {
        'episode_id': episode_key,
        'episode_number': normalized_episode_number,
        'current_time': current_time,
        'duration': duration,
        'percent': percent,
        'last_play_time': now,
        'watch_seconds': episode_watch_seconds,
        'last_watch_delta': delta
    }
    episode_map[episode_key] = episode_playback

    playback = {
        'current_episode': normalized_episode_number,
        'current_episode_id': episode_key,
        'current_time': current_time,
        'duration': duration,
        'percent': percent,
        'last_play_time': now,
        'watch_seconds': total_watch_seconds,
        'last_watch_delta': delta,
        'episodes': episode_map
    }
    playback_json = json.dumps(playback)
    
    cursor.execute('UPDATE movies SET playback = ? WHERE id = ?', (playback_json, movie_id))
    conn.commit()
    conn.close()

def delete_movie(movie_id):
    """删除电影"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM movies WHERE id = ?', (movie_id,))
    conn.commit()
    conn.close()

def clear_library():
    """清空电影库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM movies')
    conn.commit()
    conn.close()

def save_behavior_event(event):
    """Save a lightweight viewing behavior event."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    metadata = event.get('metadata', {})
    if not isinstance(metadata, dict):
        metadata = {}
    created_at = event.get('created_at') or datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO behavior_events (
            event_type, movie_id, episode_id, source_page, position,
            duration, playback_rate, delta_seconds, metadata, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(event.get('event_type') or ''),
        str(event.get('movie_id') or ''),
        str(event.get('episode_id') or ''),
        str(event.get('source_page') or ''),
        float(event.get('position') or 0),
        float(event.get('duration') or 0),
        float(event.get('playback_rate') or 1),
        float(event.get('delta_seconds') or 0),
        json.dumps(metadata, ensure_ascii=False),
        created_at,
    ))
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return event_id


def load_behavior_events(since=None):
    """Load behavior events, optionally from an ISO datetime lower bound."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = '''
        SELECT id, event_type, movie_id, episode_id, source_page, position,
               duration, playback_rate, delta_seconds, metadata, created_at
        FROM behavior_events
    '''
    if since:
        cursor.execute(query + ' WHERE created_at >= ? ORDER BY created_at ASC', (since,))
    else:
        cursor.execute(query + ' ORDER BY created_at ASC')
    rows = cursor.fetchall()
    conn.close()

    events = []
    for row in rows:
        try:
            metadata = json.loads(row[9]) if row[9] else {}
        except Exception:
            metadata = {}
        events.append({
            'id': row[0],
            'event_type': row[1],
            'movie_id': row[2],
            'episode_id': row[3],
            'source_page': row[4],
            'position': row[5] or 0,
            'duration': row[6] or 0,
            'playback_rate': row[7] or 1,
            'delta_seconds': row[8] or 0,
            'metadata': metadata if isinstance(metadata, dict) else {},
            'created_at': row[10],
        })
    return events


def clear_behavior_events():
    """Clear viewing behavior event history."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM behavior_events')
    conn.commit()
    conn.close()


def get_library_stats():
    """获取库统计信息"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM movies')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM movies WHERE is_series = 1')
    series_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM movies WHERE category = "电影"')
    movie_count = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total': total,
        'series': series_count,
        'movies': movie_count
    }

# ==================== 数据源操作 ====================

def save_sources(sources):
    """保存数据源到数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM sources')
    
    for source in sources:
        selected_paths_json = json.dumps(source.get('selected_paths', []))
        stats_json = json.dumps(source.get('stats', {}))
        
        cursor.execute('''
            INSERT OR REPLACE INTO sources (
                id, name, type, path, username, password, driver, cookie,
                mount_path, host, port, protocol, selected_paths, active,
                tint, stats, created_at, updated_at, addition, storage_id,
                scan_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            source.get('id', ''),
            source.get('name', ''),
            source.get('type', ''),
            source.get('path', ''),
            source.get('username', ''),
            source.get('password', ''),
            source.get('driver', ''),
            source.get('cookie', ''),
            source.get('mount_path', ''),
            source.get('host', ''),
            source.get('port', ''),
            source.get('protocol', ''),
            selected_paths_json,
            1 if source.get('active') else 0,
            source.get('tint', ''),
            stats_json,
            source.get('created_at', datetime.now().isoformat()),
            source.get('updated_at', datetime.now().isoformat()),
            json.dumps(source.get('addition', {}), ensure_ascii=False),
            str(source.get('storage_id', '')),
            source.get('scan_error', '')
        ))
    
    conn.commit()
    conn.close()

def load_sources():
    """从数据库加载数据源"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM sources')
    rows = cursor.fetchall()
    
    sources = []
    for row in rows:
        source = {
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'path': row[3],
            'username': row[4],
            'password': row[5],
            'driver': row[6],
            'cookie': row[7],
            'mount_path': row[8],
            'host': row[9],
            'port': row[10],
            'protocol': row[11],
            'selected_paths': json.loads(row[12]) if row[12] else [],
            'active': bool(row[13]),
            'tint': row[14],
            'stats': json.loads(row[15]) if row[15] else {},
            'created_at': row[16],
            'updated_at': row[17],
            'addition': json.loads(row[18]) if len(row) > 18 and row[18] else {},
            'storage_id': row[19] if len(row) > 19 else '',
            'scan_error': row[20] if len(row) > 20 else ''
        }
        sources.append(source)
    
    conn.close()
    return sources

def get_source_by_id(source_id):
    """根据 ID 获取数据源"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM sources WHERE id = ?', (source_id,))
    row = cursor.fetchone()
    
    if row:
        source = {
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'path': row[3],
            'username': row[4],
            'password': row[5],
            'driver': row[6],
            'cookie': row[7],
            'mount_path': row[8],
            'host': row[9],
            'port': row[10],
            'protocol': row[11],
            'selected_paths': json.loads(row[12]) if row[12] else [],
            'active': bool(row[13]),
            'tint': row[14],
            'stats': json.loads(row[15]) if row[15] else {},
            'created_at': row[16],
            'updated_at': row[17],
            'addition': json.loads(row[18]) if len(row) > 18 and row[18] else {},
            'storage_id': row[19] if len(row) > 19 else '',
            'scan_error': row[20] if len(row) > 20 else ''
        }
    else:
        source = None
    
    conn.close()
    return source

def delete_source(source_id):
    """删除数据源"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM sources WHERE id = ?', (source_id,))
    conn.commit()
    conn.close()

def clear_sources():
    """清空数据源"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM sources')
    conn.commit()
    conn.close()

# ==================== metadata_pool（精选虚拟片库）====================

def pool_count(media_type: str | None = None, q: str | None = None) -> int:
    """返回虚拟片库条目数；可按 media_type / 关键词（FTS5）过滤。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        if q:
            row = conn.execute(
                '''SELECT COUNT(*) FROM metadata_pool m
                   JOIN metadata_pool_fts f ON m.rowid = f.rowid
                   WHERE metadata_pool_fts MATCH ?''',
                (q,)
            ).fetchone()
        elif media_type:
            # 动漫 = Bangumi 源条目 ∪ TMDB 动画条目（genres 含「动画」）
            if media_type == 'anime':
                row = conn.execute(
                    "SELECT COUNT(*) FROM metadata_pool WHERE media_type = 'anime' OR genres LIKE '%\"动画\"%'"
                ).fetchone()
            else:
                row = conn.execute(
                    'SELECT COUNT(*) FROM metadata_pool WHERE media_type = ?',
                    (media_type,)
                ).fetchone()
        else:
            row = conn.execute('SELECT COUNT(*) FROM metadata_pool').fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()

def pool_is_empty() -> bool:
    return pool_count() == 0

def _serialize_pool_genres(item: dict, key: str) -> str:
    value = item.get(key)
    if isinstance(value, str):
        return value
    return json.dumps(value or [], ensure_ascii=False)


# 单条 UPSERT 的 SQL（genres 列冲突时保护详情懒加载结果）
_POOL_UPSERT_SQL = '''
    INSERT INTO metadata_pool
    (id, source, external_id, media_type, title, original_title,
     release_date, year, overview, genres, poster_path, backdrop_path,
     vote_average, vote_count, popularity, origin_country, runtime,
     status, detail_fetched, fetched_at, updated_at, genre_ids)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(id) DO UPDATE SET
      source=excluded.source, external_id=excluded.external_id,
      media_type=excluded.media_type, title=excluded.title,
      original_title=excluded.original_title, release_date=excluded.release_date,
      year=excluded.year, overview=excluded.overview,
      genres=CASE WHEN metadata_pool.detail_fetched = 1 AND excluded.genres = '[]'
                  THEN metadata_pool.genres ELSE excluded.genres END,
      poster_path=excluded.poster_path, backdrop_path=excluded.backdrop_path,
      vote_average=excluded.vote_average, vote_count=excluded.vote_count,
      popularity=excluded.popularity, origin_country=excluded.origin_country,
      runtime=excluded.runtime, status=excluded.status,
      detail_fetched=MAX(metadata_pool.detail_fetched, excluded.detail_fetched),
      updated_at=excluded.updated_at,
      genre_ids=excluded.genre_ids
'''


def _pool_item_params(item: dict) -> tuple:
    pool_id = item.get('id') or f"{item.get('source')}:{item.get('external_id')}"
    return (
        pool_id,
        item.get('source', ''),
        item.get('external_id', ''),
        item.get('media_type', ''),
        item.get('title', ''),
        item.get('original_title', ''),
        item.get('release_date', ''),
        item.get('year'),
        item.get('overview', ''),
        _serialize_pool_genres(item, 'genres'),
        item.get('poster_path', ''),
        item.get('backdrop_path', ''),
        item.get('vote_average'),
        item.get('vote_count'),
        item.get('popularity'),
        _serialize_pool_genres(item, 'origin_country'),
        item.get('runtime'),
        item.get('status', ''),
        int(bool(item.get('detail_fetched'))),
        item.get('fetched_at', ''),
        item.get('updated_at', ''),
        _serialize_pool_genres(item, 'genre_ids'),
    )


def upsert_pool_item(item: dict):
    """新增/更新一条虚拟片库条目。

    使用 UPSERT（ON CONFLICT）保留 rowid；
    FTS5 索引由 metadata_pool 上的触发器（trg_pool_fts_ai/ad/au）自动同步。
    冲突时不覆盖 detail_fetched，且已详情补全的 genres 不会被空列表冲掉。
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute(_POOL_UPSERT_SQL, _pool_item_params(item))
        conn.commit()
    finally:
        conn.close()


def upsert_pool_items_batch(items: list[dict]) -> int:
    """批量 UPSERT（单事务），供全量拉取/题材回填使用，1 万行秒级完成。"""
    if not items:
        return 0
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.executemany(_POOL_UPSERT_SQL, [_pool_item_params(it) for it in items])
        conn.commit()
        return len(items)
    finally:
        conn.close()


# ==================== tmdb_genre_map（题材 id→名称映射）====================

def replace_genre_map(media_type: str, genres: list[dict]) -> int:
    """整表替换某 media_type 的题材映射。genres: [{'id': int, 'name': str, 'name_en': str}]"""
    if not genres:
        return 0
    now = datetime.now().isoformat(timespec='seconds')
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute('DELETE FROM tmdb_genre_map WHERE media_type = ?', (media_type,))
        conn.executemany(
            '''INSERT INTO tmdb_genre_map (media_type, genre_id, name, name_en, updated_at)
               VALUES (?, ?, ?, ?, ?)''',
            [(media_type, int(g['id']), g.get('name', ''), g.get('name_en', ''), now) for g in genres],
        )
        conn.commit()
        return len(genres)
    finally:
        conn.close()


def get_genre_map(media_type: str) -> dict[int, str]:
    """返回 {genre_id: 中文名}；无数据返回空 dict（调用方据此决定是否联网拉取）。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            'SELECT genre_id, name FROM tmdb_genre_map WHERE media_type = ?',
            (media_type,),
        ).fetchall()
        return {int(r[0]): r[1] for r in rows}
    finally:
        conn.close()


def genre_map_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute('SELECT COUNT(*) FROM tmdb_genre_map').fetchone()[0]
    finally:
        conn.close()


def count_pool_missing_genres() -> int:
    """统计缺少题材的条目数（genres 与 genre_ids 都为空）。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(
            """SELECT COUNT(*) FROM metadata_pool
               WHERE (genres IS NULL OR genres = '' OR genres = '[]')
                 AND (genre_ids IS NULL OR genre_ids = '' OR genre_ids = '[]')"""
        ).fetchone()[0]
    finally:
        conn.close()

def query_pool(params: dict) -> list[dict]:
    """分页查询虚拟片库，支持简单过滤与排序。"""
    q = (params.get('q') or '').strip()
    sort = (params.get('sort') or 'popularity').strip().lower()
    media_type = (params.get('media_type') or '').strip().lower()
    page = max(1, int(params.get('page') or 1))
    per_page = max(1, min(100, int(params.get('per_page') or 20)))
    offset = (page - 1) * per_page

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = []
        if q:
            # FTS5 unicode61 分词器不切分 CJK 连续串：裸词「咒术」匹配不到
            # 「咒术回战」。给每个未带通配的词补前缀 *，中文部分词与英文
            # partial 搜索都能命中（已带 * 的词保持原样）。
            fts_q = ' '.join(
                t if t.endswith('*') else t + '*' for t in q.split() if t
            )
            sql = '''SELECT m.* FROM metadata_pool m
                     JOIN metadata_pool_fts f ON m.rowid = f.rowid
                     WHERE metadata_pool_fts MATCH ?
                     ORDER BY rank
                     LIMIT ? OFFSET ?'''
            rows = conn.execute(sql, (fts_q, per_page, offset)).fetchall()
        else:
            order = 'popularity DESC'
            if sort == 'vote_count':
                order = 'vote_count DESC'
            elif sort == 'vote_average':
                order = 'vote_average DESC'
            elif sort == 'year':
                order = 'year DESC'
            # 动漫 = Bangumi 源条目（media_type='anime'）∪ TMDB 动画条目
            # （zh-CN 题材归一后流派名固定为「动画」，存于 genres JSON 数组）
            if media_type == 'anime':
                where = "WHERE media_type = 'anime' OR genres LIKE '%\"动画\"%'"
                args = []
            elif media_type:
                where = 'WHERE media_type = ?'
                args = [media_type]
            else:
                where, args = '', []
            sql = f'SELECT * FROM metadata_pool {where} ORDER BY {order} LIMIT ? OFFSET ?'
            rows = conn.execute(sql, tuple(args + [per_page, offset])).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_pool_item(pool_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute('SELECT * FROM metadata_pool WHERE id = ?', (pool_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def find_similar_pool_items(pool_id: str, limit: int = 12) -> list[dict]:
    """根据同类型+同年代从 metadata_pool 找相似条目（用于详情页相似推荐）。

    匹配规则：genres 有交集 或 media_type+year 相近；排除自身，按 popularity 降序。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        target = conn.execute('SELECT * FROM metadata_pool WHERE id = ?', (pool_id,)).fetchone()
        if not target:
            return []
        media_type = target['media_type']
        year = target['year'] or 0
        genres = _parse_genres(target['genres'])
        year_lo = int(year) - 8 if year else 0
        year_hi = int(year) + 8 if year else 9999

        # 先按类型/年份粗筛
        rows = conn.execute(
            '''SELECT * FROM metadata_pool
               WHERE id != ? AND media_type = ? AND year BETWEEN ? AND ?
               ORDER BY popularity DESC, vote_average DESC
               LIMIT 200''',
            (pool_id, media_type, year_lo, year_hi)
        ).fetchall()

        # 若有 genres，优先挑类型交集的
        scored = []
        for row in rows:
            row_genres = set(_parse_genres(row['genres']))
            overlap = len(set(genres) & row_genres) if genres else 0
            scored.append((dict(row), overlap))
        scored.sort(key=lambda x: (x[1], x[0].get('popularity') or 0, x[0].get('vote_average') or 0), reverse=True)
        return [item for item, _ in scored[:limit]]
    finally:
        conn.close()


def _parse_genres(raw) -> list[str]:
    """解析 metadata_pool.genres（JSON 数组字符串）；兼容历史逗号分隔脏数据。"""
    if isinstance(raw, list):
        return [str(g).strip() for g in raw if str(g).strip()]
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        parsed = _safe_json(text)
        if isinstance(parsed, list):
            return [str(g).strip() for g in parsed if str(g).strip()]
    return [g.strip() for g in text.split(",") if g.strip()]


def get_top_pool_by_popularity(limit: int = 500) -> list[dict]:
    """直接从 metadata_pool 取 popularity Top（列表拉取时的存量热度）。

    与 get_top_hotness_by_popularity（快照表，仅覆盖约 1200 条）UNION 后
    才能覆盖全量 1 万候选池。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''SELECT id AS pool_id, source, external_id, title, original_title,
                      media_type, poster_path, backdrop_path, release_date, year,
                      vote_average, vote_count, popularity, genres, genre_ids,
                      overview, origin_country, runtime, updated_at, detail_fetched
               FROM metadata_pool
               ORDER BY CASE WHEN popularity IS NULL THEN 1 ELSE 0 END,
                        popularity DESC, vote_count DESC
               LIMIT ?''',
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_hotness_trends(pool_ids: list[str], days: int = 30) -> dict[str, dict]:
    """批量计算候选条目近 N 天热度趋势。

    取每个 pool_id 窗口内最早/最晚两个快照（必须跨不同自然日且间隔≥20 小时），
    以 vote_count 增长率为主、popularity 变化率为辅。
    返回 {pool_id: {"voteGrowth": float, "popChange": float, "available": bool, "snapshotDate": str}}
    """
    if not pool_ids:
        return {}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in pool_ids)
        rows = conn.execute(
            f'''SELECT h.pool_id, h.vote_count, h.vote_average, h.popularity, h.fetched_at
                FROM hotness_series h
                INNER JOIN (
                    SELECT pool_id, MIN(fetched_at) AS mn, MAX(fetched_at) AS mx
                    FROM hotness_series
                    WHERE fetched_at >= datetime('now', ?)
                    GROUP BY pool_id
                ) t ON h.pool_id = t.pool_id AND (h.fetched_at = t.mn OR h.fetched_at = t.mx)
                WHERE h.pool_id IN ({placeholders})
                ORDER BY h.pool_id, h.fetched_at''',
            [f'-{int(days)} days'] + list(pool_ids),
        ).fetchall()

        from datetime import datetime as _dt
        grouped: dict[str, list] = {}
        for r in rows:
            grouped.setdefault(r["pool_id"], []).append(r)

        result: dict[str, dict] = {}
        for pid, pair in grouped.items():
            latest_ts = str(pair[-1]["fetched_at"] or "")
            if len(pair) < 2:
                result[pid] = {"voteGrowth": 0.0, "popChange": 0.0,
                               "available": False, "snapshotDate": latest_ts[:10]}
                continue
            first, last = pair[0], pair[-1]
            try:
                t0 = _dt.fromisoformat(str(first["fetched_at"]))
                t1 = _dt.fromisoformat(str(last["fetched_at"]))
            except (TypeError, ValueError):
                result[pid] = {"voteGrowth": 0.0, "popChange": 0.0,
                               "available": False, "snapshotDate": latest_ts[:10]}
                continue
            gap_hours = (t1 - t0).total_seconds() / 3600
            # 必须跨自然日且间隔 ≥20 小时，否则只是首次拉取的连续快照，不是真实趋势
            if t0.date() == t1.date() or gap_hours < 20:
                result[pid] = {"voteGrowth": 0.0, "popChange": 0.0,
                               "available": False, "snapshotDate": latest_ts[:10]}
                continue

            v0 = float(first["vote_count"] or 0)
            v1 = float(last["vote_count"] or 0)
            vote_growth = (v1 - v0) / v0 if v0 > 0 else (1.0 if v1 > 0 else 0.0)
            p0 = float(first["popularity"] or 0)
            p1 = float(last["popularity"] or 0)
            pop_change = (p1 - p0) / p0 if p0 > 0 else 0.0
            # winsorize 截尾，防个别极端值主导
            vote_growth = max(-0.5, min(2.0, vote_growth))
            pop_change = max(-0.5, min(2.0, pop_change))
            result[pid] = {"voteGrowth": round(vote_growth, 4),
                           "popChange": round(pop_change, 4),
                           "available": True, "snapshotDate": latest_ts[:10]}
        return result
    finally:
        conn.close()


def get_latest_snapshot_date() -> str:
    """最近一次热度快照日期（前端数据新鲜度提示用）。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT MAX(fetched_at) FROM hotness_series").fetchone()
        return str(row[0] or "")[:10]
    finally:
        conn.close()

# ==================== hotness_series（热度时间序列）====================

def insert_hotness(record: dict):
    """插入一条热度快照。"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute(
            '''INSERT INTO hotness_series
               (pool_id, source, external_id, vote_average, vote_count,
                popularity, collection_count, fetched_at)
               VALUES (?,?,?,?,?,?,?,?)''',
            (
                record.get('pool_id', ''),
                record.get('source', ''),
                record.get('external_id', ''),
                record.get('vote_average'),
                record.get('vote_count'),
                record.get('popularity'),
                record.get('collection_count'),
                record.get('fetched_at', ''),
            ),
        )
        conn.commit()
    finally:
        conn.close()

def insert_hotness_batch(records: list[dict]):
    """批量插入热度快照（单连接 + 单事务），供热度刷新任务使用。"""
    if not records:
        return
    conn = sqlite3.connect(DB_PATH, timeout=15)
    try:
        conn.executemany(
            '''INSERT INTO hotness_series
               (pool_id, source, external_id, vote_average, vote_count,
                popularity, collection_count, fetched_at)
               VALUES (?,?,?,?,?,?,?,?)''',
            [
                (
                    r.get('pool_id', ''),
                    r.get('source', ''),
                    r.get('external_id', ''),
                    r.get('vote_average'),
                    r.get('vote_count'),
                    r.get('popularity'),
                    r.get('collection_count'),
                    r.get('fetched_at', ''),
                )
                for r in records
            ],
        )
        conn.commit()
    finally:
        conn.close()

def list_pool_ids() -> set[str]:
    """返回 metadata_pool 中全部条目 id（'tmdb:{external_id}'），供热度快照过滤。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        return {r[0] for r in conn.execute('SELECT id FROM metadata_pool')}
    finally:
        conn.close()


def list_pool_ids_by_source(source: str) -> list[dict]:
    """返回某来源（如 'bangumi'）的全部条目 id 与 external_id，供周同步刷新热度。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            'SELECT id, external_id FROM metadata_pool WHERE source = ?', (source,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_hotness_series(pool_id: str, days: int = 30) -> list[dict]:
    """返回某条目近 N 天的热度时间序列（按时间升序）。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''SELECT pool_id, source, external_id, vote_average, vote_count,
                      popularity, collection_count, fetched_at
               FROM hotness_series
               WHERE pool_id = ? AND fetched_at >= datetime('now', ?)
               ORDER BY fetched_at ASC''',
            (pool_id, f'-{int(days)} days'),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_hotness_latest(pool_id: str) -> dict | None:
    """返回某条目最近一条热度快照。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            '''SELECT * FROM hotness_series WHERE pool_id = ?
               ORDER BY fetched_at DESC LIMIT 1''',
            (pool_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_top_hotness_by_popularity(limit: int = 20) -> list[dict]:
    """返回热度最高的条目（基于最近一次快照 popularity），JOIN 池条目信息用于榜单展示。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # 取每条 pool_id 最新一条快照，按 popularity 降序（NULL 排末尾）
        rows = conn.execute(
            '''SELECT h.pool_id, h.source, h.external_id,
                      h.vote_average AS snap_vote_average,
                      h.vote_count AS snap_vote_count,
                      h.popularity AS snap_popularity,
                      h.fetched_at AS snap_fetched_at,
                      m.title, m.original_title, m.media_type, m.poster_path,
                      m.backdrop_path, m.release_date, m.year,
                      m.vote_average, m.vote_count, m.popularity,
                      m.genres, m.genre_ids, m.overview, m.origin_country, m.runtime
               FROM hotness_series h
               INNER JOIN (
                   SELECT pool_id, MAX(fetched_at) AS max_ts
                   FROM hotness_series GROUP BY pool_id
               ) latest ON h.pool_id = latest.pool_id AND h.fetched_at = latest.max_ts
               INNER JOIN metadata_pool m ON m.id = h.pool_id
               ORDER BY CASE WHEN h.popularity IS NULL THEN 1 ELSE 0 END,
                        h.popularity DESC
               LIMIT ?''',
            (limit,),
        ).fetchall()
        items = [dict(r) for r in rows]
        # 快照值优先（更新），池内值兜底，统一成推荐侧使用的字段名
        for it in items:
            it["vote_average"] = it.get("snap_vote_average") if it.get("snap_vote_average") is not None else it.get("vote_average")
            it["vote_count"] = it.get("snap_vote_count") if it.get("snap_vote_count") is not None else it.get("vote_count")
            it["popularity"] = it.get("snap_popularity") if it.get("snap_popularity") is not None else it.get("popularity")
            it["fetched_at"] = it.get("snap_fetched_at")
        return items
    finally:
        conn.close()


# ==================== wishlist（想看清单）====================

def add_wishlist(pool_id: str, note: str = "") -> bool:
    """加入想看清单，已存在则更新 note。"""
    from datetime import datetime as _dt
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute(
            '''INSERT INTO wishlist (pool_id, note, added_at) VALUES (?, ?, ?)
               ON CONFLICT(pool_id) DO UPDATE SET note=excluded.note''',
            (pool_id, note or "", _dt.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def remove_wishlist(pool_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        cur = conn.execute('DELETE FROM wishlist WHERE pool_id = ?', (pool_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def in_wishlist(pool_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute('SELECT 1 FROM wishlist WHERE pool_id = ?', (pool_id,)).fetchone()
        return row is not None
    finally:
        conn.close()


def list_wishlist() -> list[dict]:
    """返回想看清单（JOIN metadata_pool 取展示字段，按加入时间倒序）。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''SELECT w.pool_id, w.note, w.added_at,
                      m.title, m.original_title, m.media_type, m.year,
                      m.poster_path, m.backdrop_path, m.vote_average, m.vote_count,
                      m.genres, m.overview
               FROM wishlist w
               LEFT JOIN metadata_pool m ON m.id = w.pool_id
               ORDER BY w.added_at DESC'''
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ==================== 推荐：用户偏好画像 ====================

def get_user_preference_profile() -> dict:
    """基于本地片库的播放/收藏行为，汇总用户偏好，供发现推荐加权。

    返回:
      {
        "behavior_count": int,              # 有行为的影片数（冷启动判断，保留原语义）
        "owned_count": int,                 # 全片库入库数（含无行为）
        "media_type": {"movie": w, "tv": w},# 按行为强度加权的媒介偏好
        "genre_weights": {规范题材名: 权重},  # 行为强度加权 + 白名单归一
        "favorite_count": int,
        "owned_external_ids": set[str],     # 全部入库影片的 tmdb external_id（owned 标记/降权）
      }
    """
    try:
        from backend.core import genre_taxonomy
    except ImportError:
        from core import genre_taxonomy

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            '''SELECT tmdb_id, tmdb_media_type, genres, tags, category,
                      playback, is_favorite
               FROM movies'''
        ).fetchall()

        movie_map = get_genre_map("movie")
        tv_map = get_genre_map("tv")
        valid_names = genre_taxonomy.build_canonical_name_set(movie_map, tv_map)

        media_weight = {"movie": 0.0, "tv": 0.0}
        genre_weights: dict[str, float] = {}
        owned: set[str] = set()
        behavior_count = 0
        favorite_count = 0

        for r in rows:
            tid = str(r["tmdb_id"] or "").strip()
            if tid:
                owned.add(tid)

            is_fav = bool(r["is_favorite"])
            if is_fav:
                favorite_count += 1
            playback = _safe_json(r["playback"])
            has_play = isinstance(playback, dict) and bool(playback)
            if not (has_play or is_fav):
                continue
            behavior_count += 1

            # 行为强度：播放=1，完播(>=90%)再+2，收藏+3；仅收藏无播放=2
            weight = 0.0
            if has_play:
                weight += 1.0
                try:
                    percent = float(playback.get("percent") or 0)
                except (TypeError, ValueError):
                    percent = 0.0
                if percent >= 90:
                    weight += 2.0
            if is_fav:
                weight += 3.0
            if not has_play and is_fav:
                weight = 2.0

            mt = (r["tmdb_media_type"] or "").strip().lower()
            if mt in ("movie", "tv"):
                media_weight[mt] += weight

            # 题材：genres 优先，tags 补充；统一过白名单归一
            seen_in_movie: set[str] = set()
            for raw_list in (_safe_json(r["genres"]), _safe_json(r["tags"])):
                if not isinstance(raw_list, list):
                    continue
                for raw_tag in raw_list:
                    for canon in genre_taxonomy.canonicalize_tag(str(raw_tag), valid_names):
                        seen_in_movie.add(canon)
            for canon in seen_in_movie:
                genre_weights[canon] = genre_weights.get(canon, 0.0) + weight

        return {
            "behavior_count": behavior_count,
            "owned_count": len(owned),
            "media_type": media_weight,
            "genre_weights": genre_weights,
            "favorite_count": favorite_count,
            "owned_external_ids": owned,
        }
    finally:
        conn.close()


def _safe_json(value) -> Any:
    """安全解析 DB 中的 JSON 字符串；已是 list/dict 原样返回，失败返回 None。"""
    if isinstance(value, (list, dict)):
        return value
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None

# ==================== llm_cache（大模型响应缓存）====================

def get_app_state(key: str) -> str:
    """读取通用状态值；不存在返回空串。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute('SELECT value FROM app_state WHERE key = ?', (key,)).fetchone()
        return str(row[0]) if row and row[0] is not None else ""
    finally:
        conn.close()


def set_app_state(key: str, value: str) -> None:
    """写入通用状态键值（覆盖）。"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute(
            '''INSERT INTO app_state (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value, updated_at = excluded.updated_at''',
            (key, str(value), datetime.now().isoformat(timespec='seconds')),
        )
        conn.commit()
    finally:
        conn.close()


def get_llm_cache(scope: str, request_hash: str) -> dict | None:
    """读取一条 LLM 缓存；不存在返回 None。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            'SELECT response_text, model, created_at FROM llm_cache WHERE scope = ? AND request_hash = ?',
            (scope, request_hash),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_llm_cache(scope: str, request_hash: str, response_text: str,
                  model: str = '', request_meta: dict | None = None) -> None:
    """写入 LLM 缓存（同 scope+hash 覆盖）。只缓存成功响应，由调用方保证。"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute(
            '''INSERT INTO llm_cache (scope, request_hash, request_meta, response_text, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(scope, request_hash) DO UPDATE SET
                   request_meta = excluded.request_meta,
                   response_text = excluded.response_text,
                   model = excluded.model,
                   created_at = excluded.created_at''',
            (
                scope,
                request_hash,
                json.dumps(request_meta or {}, ensure_ascii=False),
                response_text,
                model or '',
                datetime.now().isoformat(timespec='seconds'),
            ),
        )
        conn.commit()
    finally:
        conn.close()


# 初始化数据库
init_db()
