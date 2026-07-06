import vapoursynth as vs
from pathlib import Path

core = vs.core

if not hasattr(core, "rife"):
    plugin_path = Path(__file__).resolve().parent / "plugins" / "librife_windows_x86-64.dll"
    if plugin_path.exists():
        core.std.LoadPlugin(path=str(plugin_path))

if not hasattr(core, "rife"):
    raise RuntimeError(
        "VapourSynth-RIFE-ncnn-Vulkan is not installed. "
        "Install HomeOfVapourSynthEvolution/VapourSynth-RIFE-ncnn-Vulkan to use AI frame interpolation."
    )

src = video_in

matrix = "709"
if src.width <= 1024 and src.height <= 576:
    matrix = "470bg"

rgb = core.resize.Bicubic(src, format=vs.RGBS, matrix_in_s=matrix)

try:
    doubled = core.rife.RIFE(rgb, model=11, factor_num=2, factor_den=1, sc=True)
except Exception:
    doubled = core.rife.RIFE(rgb, model=5, factor_num=2, factor_den=1, sc=True)

video_out = core.resize.Bicubic(doubled, format=vs.YUV420P8, matrix_s=matrix)
