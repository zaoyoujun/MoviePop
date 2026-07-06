"""
后端启动入口
使用 uvicorn 启动 FastAPI 应用
"""
import uvicorn
import sys
try:
    from backend.app import app
    from backend.config import AppConfig
except ImportError:
    from app import app
    from config import AppConfig


def main():
    """启动 API 服务器"""
    config = AppConfig()
    config.load_config()
    port = config.SERVER_PORT

    print(f"==============================================")
    print(f"  JMH-MoviePop API Server")
    print(f"  地址: http://127.0.0.1:{port}")
    print(f"  文档: http://127.0.0.1:{port}/docs")
    print(f"==============================================")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--player":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        try:
            from backend.player.modern_player import main as player_main
        except ImportError:
            from player.modern_player import main as player_main
        raise SystemExit(player_main())
    main()
