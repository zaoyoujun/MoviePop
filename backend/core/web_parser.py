"""
通用网页视频解析器
用于解析yt-dlp不支持的视频聚合网站
支持解析网站层级结构（分类、视频列表、视频详情）
"""
import hashlib
import logging
import re
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class WebParser:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.host = urlparse(base_url).netloc

    def _fetch_page(self, url):
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except Exception as exc:
            logger.error(f"Failed to fetch page {url}: {exc}")
            return None

    def _parse_html(self, html):
        if not html:
            return None
        try:
            return BeautifulSoup(html, "html.parser")
        except Exception as exc:
            logger.error(f"Failed to parse HTML: {exc}")
            return None

    def browse(self, url):
        parsed = urlparse(url)
        path = parsed.path.lower()

        if path.startswith("/v/"):
            return self._parse_video_page(url)
        elif path.startswith("/p/"):
            return self._parse_play_page(url)
        elif path.startswith("/vod/"):
            return self._parse_category_page(url)
        elif path.startswith("/rank/"):
            return self._parse_rank_page(url)
        else:
            return self._parse_home_page(url)

    def _parse_home_page(self, url):
        html = self._fetch_page(url)
        soup = self._parse_html(html)
        if not soup:
            return {"error": "无法获取页面内容"}

        result = {
            "success": True,
            "originalUrl": url,
            "type": "channel",
            "title": self._extract_title(soup) or "网站首页",
            "playlists": [],
            "videos": [],
        }

        categories = self._extract_categories(soup, url)
        for cat in categories:
            result["playlists"].append({
                "id": hashlib.md5(cat["url"].encode()).hexdigest()[:12],
                "url": cat["url"],
                "title": cat["title"],
                "thumbnail": "",
                "videoCount": 0,
                "uploader": "",
                "type": "playlist",
            })

        videos = self._extract_videos(soup, url)
        result["videos"] = videos

        return result

    def _parse_category_page(self, url):
        html = self._fetch_page(url)
        soup = self._parse_html(html)
        if not soup:
            return {"error": "无法获取页面内容"}

        result = {
            "success": True,
            "originalUrl": url,
            "type": "playlist",
            "title": self._extract_title(soup) or "分类列表",
            "playlists": [],
            "videos": [],
        }

        videos = self._extract_videos(soup, url)
        result["videos"] = videos

        return result

    def _parse_rank_page(self, url):
        html = self._fetch_page(url)
        soup = self._parse_html(html)
        if not soup:
            return {"error": "无法获取页面内容"}

        result = {
            "success": True,
            "originalUrl": url,
            "type": "playlist",
            "title": "排行榜",
            "playlists": [],
            "videos": [],
        }

        videos = self._extract_videos(soup, url)
        result["videos"] = videos

        return result

    def _parse_video_page(self, url):
        html = self._fetch_page(url)
        soup = self._parse_html(html)
        if not soup:
            return {"error": "无法获取页面内容"}

        title = self._extract_title(soup)
        cover_url = self._extract_video_cover(soup, url)
        description = self._extract_description(soup)
        episodes = self._extract_episodes(soup, url)

        video_id = hashlib.md5(url.encode()).hexdigest()[:12]

        if episodes:
            return {
                "success": True,
                "originalUrl": url,
                "type": "playlist",
                "title": title or "未命名视频",
                "description": description,
                "playlists": [],
                "videos": episodes,
            }
        else:
            play_url = self._extract_play_url(html, url)
            return {
                "success": True,
                "originalUrl": url,
                "type": "single_video",
                "title": title or "未命名视频",
                "description": description,
                "videos": [{
                    "id": video_id,
                    "url": play_url or url,
                    "title": title or "未命名视频",
                    "description": description,
                    "coverUrl": cover_url,
                    "backdropUrl": cover_url,
                    "thumbnail": cover_url,
                    "duration": 0,
                    "durationText": "",
                    "year": None,
                    "uploader": "",
                    "viewCount": 0,
                    "likeCount": 0,
                    "type": "video",
                }],
            }

    def _parse_play_page(self, url):
        html = self._fetch_page(url)
        soup = self._parse_html(html)
        if not soup:
            return {"error": "无法获取页面内容"}

        title = self._extract_title(soup)
        cover_url = self._extract_video_cover(soup, url)
        play_url = self._extract_play_url(html, url)

        video_id = hashlib.md5(url.encode()).hexdigest()[:12]

        return {
            "success": True,
            "originalUrl": url,
            "type": "single_video",
            "title": title or "未命名视频",
            "description": "",
            "videos": [{
                "id": video_id,
                "url": play_url or url,
                "title": title or "未命名视频",
                "description": "",
                "coverUrl": cover_url,
                "backdropUrl": cover_url,
                "thumbnail": cover_url,
                "duration": 0,
                "durationText": "",
                "year": None,
                "uploader": "",
                "viewCount": 0,
                "likeCount": 0,
                "type": "video",
            }],
        }

    def _extract_episodes(self, soup, base_url):
        episodes = []
        
        all_links = soup.find_all("a", href=True)
        for link in all_links:
            href = link["href"]
            if href.startswith("/p/"):
                full_url = urljoin(base_url, href)
                episode_title = link.get_text().strip()
                if episode_title and len(episode_title) < 50:
                    episode_id = hashlib.md5(full_url.encode()).hexdigest()[:12]
                    episodes.append({
                        "id": episode_id,
                        "url": full_url,
                        "title": episode_title,
                        "description": "",
                        "coverUrl": "",
                        "backdropUrl": "",
                        "thumbnail": "",
                        "duration": 0,
                        "durationText": "",
                        "year": None,
                        "uploader": "",
                        "viewCount": 0,
                        "likeCount": 0,
                        "type": "video",
                    })

        seen_ids = set()
        unique_episodes = []
        for e in episodes:
            if e["id"] not in seen_ids:
                seen_ids.add(e["id"])
                unique_episodes.append(e)

        return unique_episodes

    def _extract_play_url(self, html, base_url):
        patterns = [
            r'"url"\s*:\s*["\']([^"\']+\.(mp4|m3u8|flv|ts|webm))["\']',
            r'"src"\s*:\s*["\']([^"\']+\.(mp4|m3u8|flv|ts|webm))["\']',
            r'"videoUrl"\s*:\s*["\']([^"\']+)["\']',
            r'"playUrl"\s*:\s*["\']([^"\']+)["\']',
            r'"m3u8"\s*:\s*["\']([^"\']+)["\']',
            r'"mp4"\s*:\s*["\']([^"\']+)["\']',
            r'sourceUrl\s*=\s*["\']([^"\']+)["\']',
            r'player\.config\s*=\s*({[^}]+})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                if isinstance(match, tuple):
                    url = match[0]
                else:
                    url = match
                
                if url and not url.startswith("http"):
                    url = urljoin(base_url, url)
                
                if url and (".mp4" in url or ".m3u8" in url or ".flv" in url):
                    return url

        player_config_match = re.search(r'player\.config\s*=\s*({.*?});', html, re.DOTALL)
        if player_config_match:
            try:
                import json
                config_str = player_config_match.group(1)
                config = json.loads(config_str)
                if isinstance(config, dict):
                    for key in ["url", "src", "videoUrl", "playUrl", "m3u8", "mp4"]:
                        if key in config and config[key]:
                            url = config[key]
                            if not url.startswith("http"):
                                url = urljoin(base_url, url)
                            return url
            except:
                pass

        return None

    def _extract_title(self, soup):
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text().strip().replace(" - ", "_").split("_")[0]
        return None

    def _extract_description(self, soup):
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            return meta.get("content", "")
        return ""

    def _extract_categories(self, soup, base_url):
        categories = []

        nav_elements = soup.find_all("nav")
        for nav in nav_elements:
            links = nav.find_all("a", href=True)
            for link in links:
                href = link["href"]
                if href.startswith("/vod/") or href.startswith("/"):
                    full_url = urljoin(base_url, href)
                    title = link.get_text().strip()
                    if title and len(title) < 20:
                        categories.append({"title": title, "url": full_url})

        if not categories:
            sidebar = soup.find("div", class_=re.compile("sidebar|menu|nav"))
            if sidebar:
                links = sidebar.find_all("a", href=True)
                for link in links:
                    href = link["href"]
                    if href.startswith("/vod/"):
                        full_url = urljoin(base_url, href)
                        title = link.get_text().strip()
                        if title:
                            categories.append({"title": title, "url": full_url})

        return categories

    def _extract_videos(self, soup, base_url):
        videos = []

        video_patterns = [
            {"tag": "div", "class": re.compile("video|item|list|thumb|cover")},
            {"tag": "li", "class": re.compile("video|item|list")},
            {"tag": "article", "class": re.compile("video|item")},
        ]

        for pattern in video_patterns:
            items = soup.find_all(pattern["tag"], class_=pattern["class"])
            for item in items:
                video = self._parse_video_item(item, base_url)
                if video:
                    videos.append(video)

        if not videos:
            all_links = soup.find_all("a", href=True)
            for link in all_links:
                href = link["href"]
                if href.startswith("/v/"):
                    video = self._parse_video_item_from_link(link, base_url)
                    if video:
                        videos.append(video)

        seen_ids = set()
        unique_videos = []
        for v in videos:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                unique_videos.append(v)

        return unique_videos

    def _parse_video_item(self, item, base_url):
        try:
            link = item.find("a", href=True)
            if not link:
                return None

            href = link["href"]
            if not href.startswith("/v/"):
                return None

            full_url = urljoin(base_url, href)
            video_id = hashlib.md5(full_url.encode()).hexdigest()[:12]

            img = item.find("img")
            cover_url = ""
            if img:
                cover_url = img.get("src") or img.get("data-src") or img.get("data-original")
                if cover_url:
                    if not cover_url.startswith("http"):
                        cover_url = urljoin(base_url, cover_url)

            title = ""
            title_elem = item.find("h3") or item.find("h4") or item.find("h5") or item.find("span")
            if title_elem:
                title = title_elem.get_text().strip()
            if not title and link.get_text():
                title = link.get_text().strip()

            duration = item.find("span", class_=re.compile("duration|time"))
            duration_text = ""
            if duration:
                duration_text = duration.get_text().strip()

            return {
                "id": video_id,
                "url": full_url,
                "title": title or "未命名视频",
                "description": "",
                "coverUrl": cover_url,
                "backdropUrl": cover_url,
                "thumbnail": cover_url,
                "duration": 0,
                "durationText": duration_text,
                "year": None,
                "uploader": "",
                "viewCount": 0,
                "likeCount": 0,
                "type": "video",
            }
        except Exception as exc:
            logger.debug(f"Failed to parse video item: {exc}")
            return None

    def _parse_video_item_from_link(self, link, base_url):
        try:
            href = link["href"]
            full_url = urljoin(base_url, href)
            video_id = hashlib.md5(full_url.encode()).hexdigest()[:12]

            title = link.get_text().strip()
            if not title or len(title) > 100:
                return None

            return {
                "id": video_id,
                "url": full_url,
                "title": title,
                "description": "",
                "coverUrl": "",
                "backdropUrl": "",
                "thumbnail": "",
                "duration": 0,
                "durationText": "",
                "year": None,
                "uploader": "",
                "viewCount": 0,
                "likeCount": 0,
                "type": "video",
            }
        except Exception as exc:
            logger.debug(f"Failed to parse video link: {exc}")
            return None

    def _extract_video_cover(self, soup, base_url):
        poster_meta = soup.find("meta", attrs={"property": "og:image"})
        if poster_meta:
            return poster_meta.get("content", "")

        video_tag = soup.find("video")
        if video_tag and video_tag.get("poster"):
            poster = video_tag["poster"]
            if not poster.startswith("http"):
                poster = urljoin(base_url, poster)
            return poster

        img_tags = soup.find_all("img")
        for img in img_tags:
            src = img.get("src") or img.get("data-src")
            if src and ("cover" in src.lower() or "poster" in src.lower()):
                if not src.startswith("http"):
                    src = urljoin(base_url, src)
                return src

        return ""


def browse_web_site(url: str) -> dict:
    """
    使用网页解析器浏览视频网站
    
    :param url: 视频网站URL
    :return: 包含层级信息的字典
    """
    try:
        parser = WebParser(url)
        return parser.browse(url)
    except Exception as exc:
        logger.error(f"Web parser error: {exc}", exc_info=True)
        return {"error": str(exc)}