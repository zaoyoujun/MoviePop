# Player enhancement shaders

This directory contains runtime GLSL shaders loaded by the mpv/libmpv player.

- `anime4k/`: selected shaders from bloc97/Anime4K release `v4.0.1`.
- `fsrcnnx/`: selected shaders from igv/FSRCNN-TensorFlow release `1.1`.

The player falls back gracefully if a shader file is missing.
