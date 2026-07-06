**Source Visual Truth**
- Path: `C:\Users\21124\AppData\Local\Temp\codex-clipboard-530ef73f-275d-4df1-b1d6-029cacea9e98.png`
- Target: episode selector as a horizontal still-image rail with left/right arrows, white episode labels, and a thin horizontal scrollbar. Per user confirmation, keep it inside the left detail column instead of spanning the full content grid.

**Implementation Evidence**
- Detail screenshot: `D:\R0\JMH-MoviePop\artifacts\qa\detail-episode-rail-left-column.png`
- Viewport: 1635 x 920
- State: detail page at `/movie/movie-3`, scrolled to the episode section.

**Full-View Comparison Evidence**
- Source and implementation were both opened before review.
- Implementation now uses a horizontal episode carousel inside the left content column, matching the user's requested restored placement while retaining the reference interaction model.

**Focused Region Comparison**
- Focused region: episode rail.
- The implementation screenshot clearly shows arrows, wide 16:9 thumbnails, centered white episode labels, and an overflow scrollbar.

**Findings**
- No actionable P0/P1/P2 findings remain.
- In local mock data, episode stills are not available, so cards fall back to the current landscape cover and repeat. The component now supports `thumbnailUrl`, `stillUrl`, `imageUrl`, `coverUrl`, and `backdropUrl` per episode, so real episode artwork will render when provided by the backend.

**Required Fidelity Surfaces**
- Fonts and typography: Passed. Episode labels are bold, white, centered, and compact like the reference.
- Spacing and layout rhythm: Passed. The rail spans the left content column and places controls outside the card run, matching the requested restored layout.
- Colors and visual tokens: Passed. Transparent controls and white labels sit over the dark themed detail page without introducing unrelated colors.
- Image quality and asset fidelity: Passed with data caveat. The component uses real episode still fields when available; fallback is only used for missing local mock stills.
- Copy and content: Passed. Episode numbering is preserved and displayed as `第N集 标题`.

**Patches Made Since Previous QA Pass**
- Rebuilt `DetailEpisodes.vue` as a horizontal still-image carousel.
- Added left/right scroll buttons and native horizontal scrollbar styling.
- Added episode thumbnail resolution with real still fields first, then version/hero fallback.
- Moved the episode component back into the left info column after user confirmation.
- Normalized fallback mock detail data so local series episodes render during testing.
- Fixed series detection to respect `type: 'series'` in addition to category labels.

**Implementation Checklist**
- `npm run build` passes.
- Episode rail screenshot captured at `D:\R0\JMH-MoviePop\artifacts\qa\detail-episode-rail-left-column.png`.
- DOM verification: 10 episode cards rendered for `/movie/movie-3`, rail is horizontally scrollable, and rail width matches the left content column.

**Follow-up Polish**
- Add backend episode still extraction or scraping if real sources do not currently provide per-episode thumbnails.

**final result: passed**
