"""SQLite 数据库服务"""
import sqlite3
import json
import os
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
            metadata_locked INTEGER DEFAULT 0
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

    conn.commit()
    conn.close()

def save_library(movies):
    """保存电影库到数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

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
                metadata_title, version_title, display_title, is_favorite, metadata_locked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            1 if movie.get('metadata_locked') or movie.get('metadataLocked') else 0
        ))
    
    conn.commit()
    conn.close()

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
            'metadata_locked': bool(row[49]) if len(row) > 49 else False
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
            'metadata_locked': bool(row[49]) if len(row) > 49 else False
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

# 初始化数据库
init_db()
