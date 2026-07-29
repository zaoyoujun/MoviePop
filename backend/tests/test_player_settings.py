from __future__ import annotations

from backend.config import AppConfig


def test_player_settings_are_allowlisted_and_persisted(tmp_path, monkeypatch):
    previous_instance = AppConfig._instance
    monkeypatch.setenv("MOVIEPOP_BACKEND_BASE_DIR", str(tmp_path))
    try:
        AppConfig._instance = None
        config = AppConfig()
        config.update_player_settings(
            {
                "hwdec": "no",
                "enhancement_profile": "anime_strong",
                "frame_profile": "display",
                "subtitle_mode": "off",
                "show_playback_info": False,
                "always_on_top": True,
                "volume": 67,
            }
        )
        config.save_config()

        AppConfig._instance = None
        reloaded = AppConfig()
        reloaded.load_config()
        assert reloaded.get_player_settings() == {
            "hwdec": "no",
            "enhancement_profile": "anime_strong",
            "frame_profile": "display",
            "subtitle_mode": "off",
            "show_playback_info": False,
            "always_on_top": True,
            "volume": 67,
        }

        reloaded.update_player_settings(
            {
                "hwdec": "not-an-mpv-value",
                "enhancement_profile": "remote-filter-string",
                "frame_profile": "motion_gpu",
                "subtitle_mode": "always",
                "volume": 999,
            }
        )
        assert reloaded.get_player_settings() == {
            "hwdec": "no",
            "enhancement_profile": "anime_strong",
            "frame_profile": "display",
            "subtitle_mode": "off",
            "show_playback_info": False,
            "always_on_top": True,
            "volume": 100,
        }
    finally:
        AppConfig._instance = previous_instance
