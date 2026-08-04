"""
测试文件名解析器优化方案
覆盖核心设计原则中的各种场景
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.filename_parser import parse_video_filename, merge_series_videos
from services import db_service, library_service


def test_technical_version_directory_keeps_title_and_variant_label():
    parsed = parse_video_filename("/movies/电视剧/Example Show/Season 01/4K HDR/Example.Show.S01E01.mkv")

    assert parsed["title"] == "Example Show"
    assert parsed["version_title"] == "4K HDR"


def test_merge_separates_same_season_versions():
    entries = merge_series_videos([
        "/movies/电视剧/Example Show/Season 01/1080p WEB-DL/Example.Show.S01E01.mkv",
        "/movies/电视剧/Example Show/Season 01/4K HDR/Example.Show.S01E01.mkv",
    ])

    assert {(entry["title"], entry["version_title"]) for entry in entries} == {
        ("Example Show", "1080p WEB DL"),
        ("Example Show", "4K HDR"),
    }


def test_detail_exposes_structured_variants_seasons_and_chapters(monkeypatch):
    library = [
        {"id": "show-s1-hd", "title": "Example Show", "series_title": "Example Show", "category": "电视剧", "season": 1, "version_title": "1080p WEB DL", "episodes": [1, 2], "files": ["s1e1", "s1e2"]},
        {"id": "show-s1-4k", "title": "Example Show", "series_title": "Example Show", "category": "电视剧", "season": 1, "version_title": "4K HDR", "episodes": [1, 2], "files": ["s1-4k-e1", "s1-4k-e2"]},
        {"id": "show-s2-part1", "title": "Example Show", "series_title": "Example Show", "category": "电视剧", "season": 2, "chapter_name": "Final Chapter", "part": 1, "episodes": [1], "files": ["s2e1"]},
    ]
    monkeypatch.setattr(library_service, "load_library", lambda: library)

    detail = library_service.movie_to_detail(library[0])
    structure = detail["mediaStructure"]

    assert {variant["versionTitle"] for variant in structure["variants"]} == {"1080p WEB DL", "4K HDR", ""}
    assert [season["seasonNumber"] for season in structure["seasons"]] == [1, 2]
    assert structure["seasons"][1]["chapters"][0]["chapterName"] == "Final Chapter"
    assert detail["hasVersions"] is True


def test_fallback_parses_mixed_title_season_folder_and_numeric_episode():
    parsed = parse_video_filename("/downloads/Example.Show.S02.Complete/03.mkv")

    assert parsed["title"] == "Example Show"
    assert parsed["season"] == 2
    assert parsed["episode"] == 3
    assert parsed["type"] == "series"


def test_fallback_parses_ep_prefix_without_confusing_movie_numbers():
    series = parse_video_filename("/archive/Example Show Season 03/EP007.mkv")
    movie = parse_video_filename("/archive/Blade Runner 2049/Blade Runner 2049.mkv")

    assert (series["title"], series["season"], series["episode"], series["type"]) == ("Example Show", 3, 7, "series")
    assert movie["title"] == "Blade Runner 2049"
    assert movie["episode"] is None
    assert movie["type"] == "movie"


def test_scraped_animation_movie_keeps_directory_category_and_gets_anime_category():
    movie = library_service.movie_to_api_format({
        "id": "toy-story",
        "title": "Toy Story",
        "category": "电影",
        "media_type": "电影",
        "tmdb_media_type": "movie",
        "tags": ["Animation", "Family"],
    })

    assert movie["category"] == "movie"
    assert movie["categories"] == ["anime", "movie"]
    assert movie["type"] == "movie"


def test_dr_stone_directory_layout_keeps_series_seasons_parts_versions_and_specials():
    root = "/media/\u52a8\u6f2b/\u77f3\u7eaa\u5143"
    paths = [
        f"{root}/S01/1080P WEB\u7248/\u77f3\u7eaa\u5143 S01E01 [VCB-Studio][1080P][x265][AAC].mkv",
        f"{root}/S01/4K DV\u7248/\u77f3\u7eaa\u5143 S01E01 [2160P DV][HDR][x265].mkv",
        f"{root}/S01/\u56fd\u914d\u53cc\u8bed\u7248/\u77f3\u7eaa\u5143 S01E01 [\u56fd\u8bed+\u65e5\u8bed][\u4e2d\u5b57][1080P].mkv",
        f"{root}/Season 02 Stone Wars/BD\u539f\u76d8REMUX\u7248/Dr.Stone.S02E01.1080p.BluRay.REMUX.AVC.DTS-HD.MA.mkv",
        f"{root}/Season 02 Stone Wars/\u7b80\u4e2d\u5185\u5d4c\u7248/\u77f3\u7eaa\u5143 \u7b2c\u4e8c\u5b63 E01 [\u7b80\u4f53\u5185\u5d4c][1080P].mp4",
        f"{root}/\u7b2c\u4e09\u5b63 NEW WORLD/NEW WORLD #1/1080P\u6807\u51c6\u7248/\u77f3\u7eaa\u5143 S03E01 [1080P][x264].mkv",
        f"{root}/\u7b2c\u4e09\u5b63 NEW WORLD/NEW WORLD #1/\u9ed1\u767d\u539f\u8272\u7248/\u77f3\u7eaa\u5143 S03E01 [\u9ed1\u767d\u7248][1080P].mkv",
        f"{root}/\u7b2c\u4e09\u5b63 NEW WORLD/NEW WORLD #2/1080P WEB\u7248/\u77f3\u7eaa\u5143 S03E12 [1080P][WEB-DL].mkv",
        f"{root}/Season 04 \u79d1\u5b66\u4e0e\u672a\u6765/\u79d1\u5b66\u4e0e\u672a\u6765 #1/1080P\u7248/\u77f3\u7eaa\u5143 S04E01 [1080P].mkv",
        f"{root}/Season 04 \u79d1\u5b66\u4e0e\u672a\u6765/\u79d1\u5b66\u4e0e\u672a\u6765 #2/1080P\u7248/\u77f3\u7eaa\u5143 S04E09 [1080P].mkv",
        f"{root}/Season 04 \u79d1\u5b66\u4e0e\u672a\u6765/\u79d1\u5b66\u4e0e\u672a\u6765 #3/4K\u7248/\u77f3\u7eaa\u5143 S04E17 [2160P].mkv",
        f"{root}/\u7279\u522b\u6536\u5f55/OAD/\u77f3\u7eaa\u5143 OAD 01 [1080P].mkv",
        f"{root}/\u7279\u522b\u6536\u5f55/\u7279\u522b\u7bc7 \u9f99\u6c34\u7bc7/\u77f3\u7eaa\u5143 \u9f99\u6c34\u7bc7 \u7279\u522b\u7bc7 [1080P].mkv",
        f"{root}/\u7279\u522b\u6536\u5f55/\u5267\u573a\u7248 \u79d1\u5b66\u7684\u4e16\u754c/\u77f3\u7eaa\u5143 \u5267\u573a\u7248 \u79d1\u5b66\u7684\u4e16\u754c [1080P].mkv",
    ]

    parsed = [parse_video_filename(path) for path in paths]

    assert {item["title"] for item in parsed} == {"\u77f3\u7eaa\u5143"}
    assert [(item["season"], item["season_title"]) for item in parsed[3:5]] == [(2, "Stone Wars"), (2, "Stone Wars")]
    assert [(item["season"], item["season_title"], item["part"]) for item in parsed[8:11]] == [
        (4, "\u79d1\u5b66\u4e0e\u672a\u6765", 1), (4, "\u79d1\u5b66\u4e0e\u672a\u6765", 2), (4, "\u79d1\u5b66\u4e0e\u672a\u6765", 3),
    ]
    assert [item["special_type"] for item in parsed[-3:]] == ["OVA", "\u7279\u522b\u7bc7", "\u5267\u573a\u7248"]
    assert len(merge_series_videos(paths)) == 14


def test_chapter_directories_do_not_become_season_titles():
    root = "/media/\u52a8\u6f2b/Re \u4ece\u96f6\u5f00\u59cb\u7684\u5f02\u4e16\u754c\u751f\u6d3b"
    paths = [
        f"{root}/Season 03/\u88ad\u51fb\u7bc7 #1/Re\uff1a\u4ece\u96f6\u5f00\u59cb\u7684\u5f02\u4e16\u754c\u751f\u6d3b.S03E01.mkv",
        f"{root}/Season 03/\u88ad\u51fb\u7bc7 #2/Re\uff1a\u4ece\u96f6\u5f00\u59cb\u7684\u5f02\u4e16\u754c\u751f\u6d3b.S03E09.mkv",
        f"{root}/Season 04/\u4e27\u5931\u7bc7 #1/ReZero 4th Season [01].mkv",
    ]

    parsed = [parse_video_filename(path) for path in paths]

    assert [(item["season"], item["season_title"], item["chapter_name"], item["part"]) for item in parsed] == [
        (3, "", "\u88ad\u51fb\u7bc7", 1),
        (3, "", "\u88ad\u51fb\u7bc7", 2),
        (4, "", "\u4e27\u5931\u7bc7", 1),
    ]
    entries = merge_series_videos(paths)
    assert [(item["season"], item["season_title"], item["chapter_name"], item["part"]) for item in entries] == [
        (3, "", "\u88ad\u51fb\u7bc7", 1),
        (3, "", "\u88ad\u51fb\u7bc7", 2),
        (4, "", "\u4e27\u5931\u7bc7", 1),
    ]


def test_detail_uses_persisted_chapter_name_and_migrates_legacy_chapter_labels(monkeypatch):
    library = [
        {"id": "show-s3-part-1", "title": "Example Show", "series_title": "Example Show", "category": "\u7535\u89c6\u5267", "season": 3, "chapter_name": "\u88ad\u51fb\u7bc7", "part": 1, "episodes": [1], "files": ["s3e1"]},
        {"id": "show-s3-part-2", "title": "Example Show", "series_title": "Example Show", "category": "\u7535\u89c6\u5267", "season": 3, "season_title": "\u88ad\u51fb\u7bc7 #2", "part": 2, "episodes": [2], "files": ["s3e2"]},
    ]
    monkeypatch.setattr(library_service, "load_library", lambda: library)

    detail = library_service.movie_to_detail(library[0])

    assert detail["seasons"][0]["seasonTitle"] == ""
    assert [entry["chapterName"] for entry in detail["versions"][0]["seasons"]] == ["\u88ad\u51fb\u7bc7", "\u88ad\u51fb\u7bc7"]


def test_chapter_name_round_trips_through_library_database(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setattr(db_service, "DB_PATH", str(db_path))
    db_service.init_db()
    db_service.save_library([{"id": "chapter-test", "title": "Example", "chapter_name": "\u88ad\u51fb\u7bc7"}])

    assert db_service.load_library()[0]["chapter_name"] == "\u88ad\u51fb\u7bc7"
    assert db_service.get_movie_by_id("chapter-test")["chapter_name"] == "\u88ad\u51fb\u7bc7"


def run_case(name, file_path, expected):
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"路径: {file_path}")
    result = parse_video_filename(file_path)
    print(f"结果: {result}")
    
    passed = True
    for key, value in expected.items():
        actual = result.get(key)
        if actual != value:
            print(f"  FAIL {key}: 期望 {value}, 实际 {actual}")
            passed = False
        else:
            print(f"  PASS {key}: {value}")
    
    return passed


def run_tests():
    tests = [
        ("剧集-英文完整型-Season 01",
         "/movies/动漫/石纪元/Season 01/S01E01.mkv",
         {"title": "石纪元", "season": 1, "category": "动漫", "type": "series"}),
        
        ("剧集-中文标准型-第2季",
         "/movies/动漫/石纪元/第2季 Stone Wars/S02E01.mkv",
         {"title": "石纪元", "season": 2, "season_title": "Stone Wars", "category": "动漫", "type": "series"}),
        
        ("剧集-中文标准型-第一季",
         "/movies/电视剧/权力的游戏/第一季/第一集.mkv",
         {"title": "权力的游戏", "season": 1, "category": "电视剧", "type": "series"}),
        
        ("剧集-中文标准型-第壹季",
         "/movies/动漫/进击的巨人/第壹季/EP01.mkv",
         {"title": "进击的巨人", "season": 1, "category": "动漫", "type": "series"}),
        
        ("剧集-极简型-S03(目录)",
         "/movies/动漫/石纪元/S03/NEW WORLD #1/S03E01.mkv",
         {"title": "石纪元", "season": 3, "season_title": "NEW WORLD", "part": 1, "category": "动漫", "type": "series"}),
        
        ("剧集-极简型-S1(目录)",
         "/movies/动漫/海贼王/S1/EP01.mkv",
         {"title": "海贼王", "season": 1, "category": "动漫", "type": "series"}),
        
        ("剧集-S01E01格式-文件名",
         "/movies/动漫/石纪元/Season 01/[VCB-Studio] Dr. Stone S01E01.mkv",
         {"title": "石纪元", "season": 1, "episode": 1, "category": "动漫", "type": "series"}),
        
        ("剧集-无分类目录-向上回溯",
         "/quark/石纪元/Season 01/S01E01.mkv",
         {"title": "石纪元", "season": 1, "category": "动漫", "type": "series"}),
        
        ("剧集-季内分篇章-Part",
         "/movies/动漫/石纪元/Season 03/NEW WORLD #2/S03E01.mkv",
         {"title": "石纪元", "season": 3, "season_title": "NEW WORLD", "part": 2, "category": "动漫", "type": "series"}),
        
        ("剧集-版本目录-彩色版",
         "/movies/动漫/暗影蜘蛛侠/Season 01/彩色版/S01E01.mkv",
         {"title": "暗影蜘蛛侠", "season": 1, "version_title": "彩色版", "category": "动漫", "type": "series"}),
        
        ("电影-版本目录-导演剪辑版",
         "/movies/电影/蝙蝠侠/侠影之谜/导演剪辑版/蝙蝠侠.mkv",
         {"title": "侠影之谜", "version_title": "导演剪辑版", "category": "电影", "type": "movie", "franchise": "蝙蝠侠"}),
        
        ("电影-系列电影",
         "/movies/电影/玩具总动员/玩具总动员1/玩具总动员1.mkv",
         {"title": "玩具总动员1", "category": "电影", "type": "movie", "franchise": "玩具总动员"}),
        
        ("电影-系列电影-无分类目录",
         "/quark/玩具总动员/玩具总动员2/玩具总动员2.mkv",
         {"title": "玩具总动员2", "category": "电影", "type": "movie", "franchise": "玩具总动员"}),
        
        ("特殊内容-OVA",
         "/movies/动漫/石纪元/特别收录/OAD/OVA.mkv",
         {"title": "石纪元", "special_type": "OVA", "category": "动漫", "type": "series"}),
        
        ("特殊内容-特别篇",
         "/movies/动漫/石纪元/特别收录/特别篇 龙水篇/特别篇.mkv",
         {"title": "石纪元", "special_type": "特别篇", "category": "动漫", "type": "series"}),
        
        ("特殊内容-剧场版",
         "/movies/动漫/进击的巨人/剧场版/进击的巨人剧场版.mkv",
         {"title": "进击的巨人", "special_type": "剧场版", "category": "动漫", "type": "series"}),
        
        ("电影-单文件无特征",
         "/quark/盗梦空间/盗梦空间.mkv",
         {"title": "盗梦空间", "category": "电影", "type": "movie"}),
        
        ("电影-三级目录无季标识",
         "/quark/蝙蝠侠/黑暗骑士/黑暗骑士.mkv",
         {"title": "黑暗骑士", "category": "电影", "type": "movie", "franchise": "蝙蝠侠"}),
        
        ("剧集-罗马数字季-目录",
         "/movies/动漫/圣斗士星矢/Ⅱ/EP01.mkv",
         {"title": "圣斗士星矢", "season": 2, "category": "动漫", "type": "series"}),
        
        ("电影-文件名含S数字不误判",
         "/quark/S1复仇者联盟/复仇者联盟.mkv",
         {"title": "S1复仇者联盟", "category": "电影", "type": "movie"}),
    ]
    
    passed = 0
    failed = 0
    for name, path, expected in tests:
        if run_case(name, path, expected):
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"结果: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
