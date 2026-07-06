import os
os.environ["PATH"] = os.path.dirname(__file__) + os.pathsep + os.environ["PATH"]
import mpv

# 后台空渲染模式，不弹出播放窗口
player = mpv.MPV(vo='null')
print("libmpv 加载成功，版本：", player.mpv_version)
player.terminate()