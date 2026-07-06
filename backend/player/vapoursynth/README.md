# VapourSynth AI frame interpolation

`rife_realtime.vpy` is loaded by mpv's `vapoursynth` video filter when the player selects `AI补帧`.

External runtime requirements:

- VapourSynth
- `plugins/librife_windows_x86-64.dll` from styler00dollar/VapourSynth-RIFE-ncnn-Vulkan is bundled here and loaded by the script.
- RIFE model folders under `plugins/models/`, especially `rife-v4_ensembleFalse_fastTrue` or `rife-v2.3`.
- A Vulkan-capable GPU

The built-in `关闭` / `自然` / `平滑` / `运动` frame interpolation modes do not need these dependencies.
