"""
测试文件名解析器优化方案
覆盖核心设计原则中的各种场景
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.filename_parser import parse_video_filename, merge_series_videos


def test_case(name, file_path, expected):
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"路径: {file_path}")
    result = parse_video_filename(file_path)
    print(f"结果: {result}")
    
    passed = True
    for key, value in expected.items():
        actual = result.get(key)
        if actual != value:
            print(f"  ❌ {key}: 期望 {value}, 实际 {actual}")
            passed = False
        else:
            print(f"  ✅ {key}: {value}")
    
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
        if test_case(name, path, expected):
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"结果: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)