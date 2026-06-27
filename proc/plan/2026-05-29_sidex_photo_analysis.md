# 2026-05-29 SIDEX Photo Analysis

## Scope
- Account/source: Google Photos, `bispro89@gmail.com`.
- Date/time window: photos taken on `2026-05-29` at or after `12:00:00` KST.
- Event context: SIDEX 2026 exhibition.
- Floor map: `/Users/gq/Downloads/SIDEX2026_v3.pdf`.
- Exhibitor search page: `https://www.sidex.or.kr/exhibition/partner_search.php` via Playwright.

## Current State
- Bulk/ZIP approach cancelled by user request.
- Active Google Photos download process stopped.
- `google-bispro` browser session restarted/closed to stop lingering download loops.
- Partial downloaded photos are in `output/google-photos/2026-05-29-bispro89/`.

## Output Contract
- For every downloaded/processed photo, produce a sidecar:
  - `{file_stem}_text.json`
  - Include OCR text, photo timestamp, orientation/rotation info, candidate vendor, booth/context evidence, products/claims, sector tags, and confidence.
- Produce one final Markdown report:
  - Group photos by exhibitor/vendor.
  - List all user photos under each vendor.
  - Summarize what was likely seen.
  - Summarize each vendor's product/claims/strengths.
  - Include sector classification such as scanner, milling, implant parts, software, idea product, CAD, etc. Multiple sectors allowed.
  - Include a `백인식 메모:` placeholder under each vendor.
  - Include event-level insights.

## Working Plan
- [x] Stop the in-flight download run.
- [x] Re-scan Google Photos for `2026-05-29 12:00+` items without triggering bulk ZIP.
- [x] Download photos one by one and preserve original timestamp filenames when available.
- [x] Normalize image orientation using EXIF transpose or equivalent.
- [x] OCR each normalized image and write `{file_stem}_text.json`.
- [x] Extract reference data from the SIDEX PDF and exhibitor search page.
- [x] Run VQA on low-confidence photos and save resized-image visual analysis under `output/sidex-2026/vqa/`.
- [x] Match each photo to likely exhibitor using OCR text, VQA text, timestamp sequence, booth/map proximity, and exhibitor data.
- [x] Write vendor-grouped Markdown report.
- [x] Verify counts: downloaded photos, text JSON files, VQA JSON files, grouped report references.

## Notes
- The site currently showed `152 selected` for the Today group after late backup completed.
- Re-scan result saved to `output/google-photos/2026-05-29-bispro89/noon-items.json`: 148 photos at/after noon (`12:32:06` through `14:55:02`).
- SIDEX partner search scraped via Playwright: `output/sidex-2026/reference/sidex_partners.json` contains 255 exhibitors.
- SIDEX floor-map text/image references saved under `output/sidex-2026/reference/`.
- Prior partial individual downloads are not final coverage; they are reusable inputs only if they fall within the noon window.
- Individual download/OCR coverage verified: 148 target items, 148 normalized photos, 148 `{file_stem}_text.json` sidecars.
- Low-confidence VQA target set: 139 photos. VQA uses resized JPEGs with max edge 1536px and writes `{file_stem}_vqa.json` per target.
- Final VQA coverage: 141 VQA JSON files; every current low-confidence or memo-needed photo has VQA.
- Final report after VQA/manual alias association: 148 photos, 62 vendor groups, 21 unknown vendor groups / 24 photos, 6 estimated vendor groups / 22 photos.

## 2026-05-29 Qwen Local VQA Rework
- User correction: previous OCR text is too inaccurate; treat OCR as unreliable.
- New source split:
  - `output/sidex-2026/originals/snaps`: 71 photos, time/path order, use as primary vendor route.
  - `output/sidex-2026/originals/handouts`: 77 photos, insert into snap-derived vendors; create separate vendor groups if absent.
- Local model: Ollama `qwen3.6:35b` (`vision` capability, Q4_K_M, already installed).
- Per-image output: `output/sidex-2026/qwen-vqa/{snaps,handouts}/{stem}_qwen_vqa.json`.
- Report output target: `output/sidex-2026/qwen-vqa/SIDEX_2026_qwen_vendor_report.md`.
- Markdown format: 업체명, embedded photos, 섹터, 이 회사가 주장하는 것, `백인식 메모:` blank.
- Unknown photos are grouped at the very end with `입력필요 백인식 메모:`.
- Final Qwen run coverage:
  - `snaps`: 71/71 JSON, errors 0.
  - `handouts`: 77/77 JSON, errors 0.
  - Report: 66 vendor groups, 0 unknown photos, 148 embedded thumbnails.
  - `qwen_visible_brand` groups are marked with `입력필요 백인식 메모:` because they are photo-visible brand groups rather than direct SIDEX reference matches.
