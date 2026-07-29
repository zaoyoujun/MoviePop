# Player enhancement shaders

These are vendored, version-pinned GLSL CNN shaders loaded directly by the
mpv/libmpv OpenGL renderer. They do not start a second video process or perform
offline transcoding.

| Player preset | Runtime shader | Best fit |
| --- | --- | --- |
| 动漫 AI 超分 · 性能 | Anime4K CNN S | 动漫，较低 GPU 开销 |
| 动漫 AI 超分 · 质量 | Anime4K CNN M | 动漫，较高细节与 GPU 开销 |
| 通用 AI 超分 · 性能 | FSRCNNX x2 8 | 影片，较低 GPU 开销 |
| 通用 AI 超分 · 质量 | FSRCNNX x2 16 | 影片，较高细节与 GPU 开销 |

- `anime4k/`: selected shaders from [bloc97/Anime4K](https://github.com/bloc97/Anime4K).
  The retained shader headers identify the bundled CNN implementation as v3.2;
  Anime4K is MIT licensed.
- `fsrcnnx/`: selected shaders from
  [igv/FSRCNN-TensorFlow](https://github.com/igv/FSRCNN-TensorFlow). The bundled
  shader headers are LGPL-3.0-or-later and must remain intact.

Both shader families run only when mpv is actually upscaling the source. A 4K
source on a 4K (or smaller) display may correctly leave the AI shader on standby.
See `THIRD_PARTY_NOTICES.md` for attribution and integrity hashes.
