# Development Status

## Project Summary
- Current focus: Keep the direct TIFF-compatible `.fff` path stable while evaluating an OpenCV-guided strip/frame crop path for real normal and partial roll scans.
- Current overall status: TIFF intake, direct TIFF-compatible `.fff` passthrough, external `.fff` converter handoff, project hygiene, inversion previews, guarded frame boxes, OpenCV crop and strip-frame probe artifacts, source-resolution separator crop refinement, crop-refinement review overlays, padded previews, full-resolution draft PNGs, roll-level film-base-normalized grade, final PNG export, and output-retention cleanup are implemented.
- Main goal: Create a repeatable Hasselblad X5 negative scan pipeline from TIFF / future `.fff` input to traceable PNG output.

## Current Methods Snapshot
- Intake / work TIFF:
  `tifffile` metadata inspection, hard-link-or-reference work-TIFF handling for TIFF input, and configurable external converter command handoff for `.fff`.
- Preview image processing:
  memory-conscious `tifffile.memmap` downsampling, direct negative inversion preview, and frame-region gray-world corrected preview.
- Frame splitting and crop review:
  preview-space frame detection with near-black rejection, wide-strip over-split protection, low-detail blank-tail trimming, an OpenCV threshold / morphology / connected-component probe, an OpenCV per-strip row-valley frame probe, source-resolution separator refinement, and coarse-vs-refined crop review overlay output.
- Per-frame export and grading:
  padded full-resolution draft PNG export, roll-level film-base-normalized inversion, per-frame tone mapping, and mild warm-neutral bias.
- Traceability:
  per-stage JSON metadata, contact sheets, logs, sidecars, and final PNG manifests.

## Current Completed Functionality
- `process-tiff` end-to-end run from TIFF input to final PNG folder
- direct TIFF-compatible `.fff` passthrough and `.fff` external converter handoff into the TIFF pipeline
- inversion preview artifacts
- crop rejection / refinement artifacts and review outputs
- OpenCV crop-probe and strip-frame-probe masks, overlays, and candidate metrics
- full-resolution draft frame export
- automatic roll-level base grade
- final PNG export
- output-retention cleanup for large intermediate frame PNG directories
- smoke tests for TIFF and mock `.fff` processing

## Current Remaining Plan
- choose and test a real Hasselblad / FlexColor `.fff` converter command only for `.fff` variants that are not directly TIFF-compatible
- validate the OpenCV strip-frame probe on more real `.fff` rolls, then decide whether it should replace the projection detector
- continue improving color accuracy while leaving crop/export behavior stable
- add batch processing after single-file `.fff` flow is validated

---

## Step 1 - Minimal TIFF CLI scaffold
Time: 2026-04-22 15:58 Asia/Shanghai
Status: completed

### Goal
- Create the smallest runnable project skeleton that accepts an existing TIFF scan, validates it, creates the expected task directory layout, writes a log, and writes a sidecar JSON.

### Completed
- Added a Python package under `src/negflow`.
- Added `python -m negflow process-tiff` CLI.
- Added TIFF input validation for `.tif` and `.tiff` files.
- Added output task directory creation with the planned pipeline stage folders.
- Added config snapshot support, task log output, and sidecar JSON output.
- Added a smoke test for task directory and sidecar creation.
- Fixed logger handler cleanup after the smoke test exposed a Windows file-lock issue.
- Added default configuration and README.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `configs/default.yaml`
- `src/negflow/__init__.py`
- `src/negflow/__main__.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 002_20260422T075821Z/07_final/图像 002_log.txt`
- `output/图像 002_20260422T075821Z/07_final/图像 002_sidecar.json`
- `output/图像 002_20260422T075821Z/01_raw_meta/config_snapshot.yaml`

### Problems Found
- The provided sample TIFF is about 1.29 GB, so the current step intentionally does not load or transform pixel data yet.
- The first real smoke test exposed that the file logger needed explicit handler cleanup on Windows; this was fixed before marking the step complete.
- `.fff` conversion is not implemented yet.

### Suspected Causes
- Large Hasselblad scans require memory-conscious image loading in the next image-processing step.
- Windows keeps open log files locked until the logging handler is closed.
- `.fff` support needs an external or replaceable backend rather than direct private-format parsing in the first implementation.

### Temporary Decisions / Workarounds
- Use direct TIFF input as the development path for now.
- Record later stages as pending in the sidecar JSON.
- Keep tests under project output paths because this environment restricts writes to system temp locations.

### README Check
- updated

### Remaining Work
- Add image metadata inspection for TIFF dimensions / bit depth without full pixel processing.
- Add the replaceable `.fff` backend interface.
- Add negative inversion and film base estimation in a later step.

### Recommended Next Step
- Implement lightweight TIFF metadata inspection and copy/link the input into `02_work_tiff` as the first real work-TIFF artifact.

---

## Step 2 - TIFF metadata and work artifact
Time: 2026-04-22 16:04 Asia/Shanghai
Status: completed

### Goal
- Read TIFF dimensions / dtype without loading full pixel data, and create a work-TIFF artifact in `02_work_tiff`.

### Completed
- Added lightweight TIFF metadata inspection using `tifffile.TiffFile`.
- Added metadata JSON output under `01_raw_meta`.
- Added work-TIFF artifact creation under `02_work_tiff`.
- The artifact now tries a hard link first, then records a source reference instead of copying huge scans if linking fails.
- Added sidecar fields for TIFF metadata and work-TIFF artifact details.
- Updated the smoke test to write a real small uint16 TIFF and verify metadata / artifact output.
- Updated README for the current user-facing behavior.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/metadata.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 002_20260422T080414Z/01_raw_meta/图像 002_tiff_metadata.json`
- `output/图像 002_20260422T080414Z/02_work_tiff/图像 002_work.tiff.reference.json`
- `output/图像 002_20260422T080414Z/07_final/图像 002_sidecar.json`
- `output/图像 002_20260422T080414Z/07_final/图像 002_log.txt`

### Problems Found
- Hard-link creation failed for the real sample in this Windows environment with `PermissionError`.
- A previous version briefly fell back to copying the 1.29 GB scan, which caused a timeout and unnecessary large output.

### Suspected Causes
- The current runtime permissions do not allow creating a hard link from `data\图像 002.tiff` into `output`.
- Large TIFF copying is too expensive to be a safe default.

### Temporary Decisions / Workarounds
- If hard-link creation fails, write a `.reference.json` file that points back to the source TIFF.
- Do not automatically copy large TIFF files in the default path.

### README Check
- updated

### Remaining Work
- Add a `.fff` adapter interface.
- Add negative inversion and film base estimation.
- Decide later whether to expose an explicit `--work-tiff-mode copy` option for users who want a physical copy.

### Recommended Next Step
- Add the replaceable `.fff` backend interface with a clear “not implemented / external converter required” error path, while keeping direct TIFF input working.

---

## Step 3 - FFF backend boundary
Time: 2026-04-22 16:09 Asia/Shanghai
Status: completed

### Goal
- Add the `.fff` entry point as a replaceable backend boundary, with a clear blocked/error path when no converter is configured.

### Completed
- Added `src/negflow/fff_backend.py` with a conversion request model and backend-unavailable exception.
- Added `python -m negflow process <file.fff>` CLI command.
- Added `process_fff` in the runner.
- `.fff` tasks now create the standard task directory layout, snapshot config, write a log, and write a blocked sidecar when conversion is unavailable.
- Kept the direct TIFF development path working.
- Added a smoke test for the blocked `.fff` backend path.
- Updated README with the new `process` command and current `.fff` limitation.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/__main__.py`
- `src/negflow/fff_backend.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process "output\_manual_fff\sample.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/sample_20260422T080938Z/07_final/sample_sidecar.json`
- `output/sample_20260422T080938Z/07_final/sample_log.txt`
- `output/图像 002_20260422T080837Z/07_final/图像 002_sidecar.json`

### Problems Found
- There is still no real `.fff` converter configured or executed.
- The manual `.fff` CLI validation intentionally exits with code 1, because the backend is unavailable.

### Suspected Causes
- Hasselblad `.fff` conversion needs an external converter or known export workflow before real implementation can proceed.

### Temporary Decisions / Workarounds
- Record blocked `.fff` tasks with sidecar/log instead of failing silently.
- Continue using `process-tiff` as the image-processing development path.

### README Check
- updated

### Remaining Work
- Choose or configure a real `.fff` to TIFF converter backend.
- Start TIFF image-processing work from the already validated `process-tiff` path.

### Recommended Next Step
- Implement the first TIFF image-processing stage: a conservative negative inversion prototype that writes an intermediate preview/artifact, using a memory-conscious strategy for the large sample.

---

## Step 4 - Project hygiene before image processing
Time: 2026-04-22 16:19 Asia/Shanghai
Status: completed

### Goal
- Tighten the project setup before starting pixel-processing work.

### Completed
- Added `.gitignore` for Python caches, generated output, and local scan samples.
- Added `requirements.txt` with currently used runtime dependencies.
- Added `pyproject.toml` with package metadata, editable install support, and a `negflow` console script entry point.
- Updated README setup instructions for editable installs and requirements-based installs.
- Cleaned up test imports.
- Updated tests so `_test_tmp` is removed after test runs.
- Removed prior temporary validation folders `_test_tmp` and `_manual_fff`.

### Files Changed
- `.gitignore`
- `README.md`
- `STATUS.md`
- `pyproject.toml`
- `requirements.txt`
- `status.json`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260422T081948Z/07_final/图像 002_sidecar.json`
- `pyproject.toml`
- `requirements.txt`

### Problems Found
- `python -m pip check` fails in the current global Anaconda environment because of unrelated pre-existing package conflicts.
- `tomllib` is not available in this Python 3.10 environment, so `pyproject.toml` was validated through pip metadata parsing instead.

### Suspected Causes
- The current environment has broad globally installed packages with version conflicts unrelated to NegFlow.
- `tomllib` is part of Python 3.11+, while this environment is Python 3.10.

### Temporary Decisions / Workarounds
- Treat `python -m pip install -e . --no-deps --dry-run` as the local packaging metadata validation for now.
- Keep using `PYTHONPATH=src` for direct development commands until the project is actually installed.

### README Check
- updated

### Remaining Work
- Add a dedicated virtual environment setup recommendation later if dependency isolation becomes important.
- Start pixel-processing work from the validated TIFF path.

### Recommended Next Step
- Implement a conservative negative inversion prototype that writes an intermediate artifact without trying to perfect color or crop yet.

---

## Step 5 - Downsampled inversion preview
Time: 2026-04-22 16:33 Asia/Shanghai
Status: completed

### Goal
- Add the first TIFF image-processing artifact: a conservative, downsampled direct negative inversion preview for inspection.

### Completed
- Added `src/negflow/pipeline/invert.py`.
- Added a `03_inverted/*_inverted_preview.png` diagnostic output.
- Added a `03_inverted/*_inverted_preview.json` metadata output.
- The preview stage uses `tifffile.memmap` and strided sampling so the 1.29 GB sample is not fully loaded into memory.
- Updated sidecar output to include the inverted preview path, metadata path, stride, and preview shape.
- Added Pillow as a runtime dependency for PNG preview writing.
- Updated tests to verify the inversion preview artifacts are created.
- Updated README to describe the current diagnostic inversion behavior.

### Files Changed
- `README.md`
- `STATUS.md`
- `pyproject.toml`
- `requirements.txt`
- `status.json`
- `src/negflow/pipeline/__init__.py`
- `src/negflow/pipeline/invert.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260422T083359Z/03_inverted/图像 002_inverted_preview.png`
- `output/图像 002_20260422T083359Z/03_inverted/图像 002_inverted_preview.json`
- `output/图像 002_20260422T083359Z/07_final/图像 002_sidecar.json`

### Problems Found
- The non-escalated sandbox cannot `memmap` the large sample TIFF and raises `PermissionError`; the same command succeeds with read/write permission in the project.
- The preview is visibly blue and uncorrected because it is only a direct inversion.
- The scan contains multiple frames in one tall strip, so later crop detection needs to split frames rather than crop one final image.

### Suspected Causes
- The sandbox permission model blocks NumPy memmap access to the large sample unless the command is approved.
- Color cast is expected because film-base correction and white balance are not implemented yet.

### Temporary Decisions / Workarounds
- Keep this as a diagnostic preview only.
- Do not attempt full-resolution inversion, film-base correction, grading, crop, or final PNG export in this step.

### README Check
- updated

### Remaining Work
- Implement film-base estimation and corrected inversion.
- Detect and split the multiple frames visible in the scan.
- Decide whether to add a graceful sidecar error path if memmap fails in non-sandboxed user environments.

### Recommended Next Step
- Add film-base sampling / estimation on the downsampled preview path, then use it to produce a less color-cast corrected inversion preview.

---

## Step 6 - Corrected inversion preview
Time: 2026-04-22 16:45 Asia/Shanghai
Status: completed

### Goal
- Add a less color-cast diagnostic inversion preview using downsampled frame-region channel balancing.

### Completed
- Refactored the inversion stage to produce both direct and corrected previews from one downsampled TIFF sample.
- Added `03_inverted/*_corrected_preview.png`.
- Added correction parameters to `03_inverted/*_inverted_preview.json` and the final sidecar.
- Implemented a frame-region gray-world channel balance that excludes much of the white inter-frame background.
- Verified on the Hasselblad sample that direct preview channel means around `[144, 182, 200]` become corrected means around `[173, 174, 170]`.
- Updated tests and README for the corrected preview behavior.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/invert.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260422T084532Z/03_inverted/图像 002_inverted_preview.png`
- `output/图像 002_20260422T084532Z/03_inverted/图像 002_corrected_preview.png`
- `output/图像 002_20260422T084532Z/03_inverted/图像 002_inverted_preview.json`
- `output/图像 002_20260422T084532Z/07_final/图像 002_sidecar.json`

### Problems Found
- The first highlight-based correction sampled the white inter-frame background and produced no useful correction; it was replaced in this step.
- The corrected preview is more neutral but still not final color, and the inter-frame background becomes warm.

### Suspected Causes
- The scan contains large white gaps between frames, so naive highlight sampling mostly measures scanner/background areas rather than frame content.
- Frame-aware crop/split detection is needed before more reliable per-frame color correction.

### Temporary Decisions / Workarounds
- Use downsampled frame-region gray-world balancing as a diagnostic preview correction.
- Keep corrected preview clearly marked as non-final and non-graded.

### README Check
- updated

### Remaining Work
- Detect frame boundaries so color correction can be estimated per frame rather than across the entire strip.
- Add crop/split metadata before attempting final per-frame PNG export.

### Recommended Next Step
- Implement a first frame-boundary detection preview from the corrected downsampled image, writing detected boxes to JSON and an overlay preview.

---

## Step 7 - Coarse frame-boundary overlay
Time: 2026-04-22 16:51 Asia/Shanghai
Status: completed

### Goal
- Add a first preview-space frame-boundary detector that writes coarse boxes to JSON and an overlay image.

### Completed
- Added `src/negflow/pipeline/crop.py`.
- Added `05_crop/*_frame_boxes.json`.
- Added `05_crop/*_frame_boxes_overlay.png`.
- Integrated frame-boundary metadata into the final sidecar.
- Added a synthetic TIFF test shape with two dark frame strips on a light background.
- Made detection minimum sizes adapt to preview dimensions so small test images and the real scan can both run.
- Updated README to mention the coarse frame-boundary overlay.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/crop.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260422T085103Z/05_crop/图像 002_frame_boxes.json`
- `output/图像 002_20260422T085103Z/05_crop/图像 002_frame_boxes_overlay.png`
- `output/图像 002_20260422T085103Z/07_final/图像 002_sidecar.json`

### Problems Found
- The detector finds 6 coarse boxes on the real sample, but some boxes are merged and not suitable for final crop/export.
- Right strip frame 1 is a large merged region; left strip frame 4 also covers multiple visual areas.
- Projection-only detection is too simple for this sample's varying frame brightness and gaps.

### Suspected Causes
- Some frame gaps are not bright enough after preview correction, so row projection merges neighboring frames.
- Different frames contain different sky/building brightness patterns, confusing a single strip-level threshold.

### Temporary Decisions / Workarounds
- Treat frame boxes as preview diagnostics only.
- Keep full-resolution crop/export pending until boundary detection is refined.

### README Check
- updated

### Remaining Work
- Refine frame splitting inside each strip, likely using local gap detection and expected frame size constraints.
- Add confidence/problem flags per detected box.
- Only after detection is reliable, map boxes back to full-resolution crops.

### Recommended Next Step
- Improve frame-boundary splitting with gap detection and confidence flags, then re-evaluate the overlay before any real crop export.

---

## Step 8 - Refine frame splitting logic
Time: 2026-04-22 17:17 Asia/Shanghai
Status: completed

### Goal
- Investigate and fix the inaccurate frame splitting from Step 7.

### Completed
- Confirmed the previous logic was flawed because it only used strip-level row brightness thresholds.
- Measured row projection profiles and found that real frame separators are often dark horizontal border lines, not bright gaps.
- Replaced simple row-threshold frame detection with strip detection plus horizontal separator detection.
- Added per-strip `separator_segments` and `content_y` diagnostics to frame box JSON.
- Added per-box `height`, `confidence`, and `flags` fields.
- Re-ran the real Hasselblad sample and improved detection from 6 coarse/merged boxes to 12 per-frame boxes.

### Files Changed
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/crop.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260422T091749Z/05_crop/图像 002_frame_boxes.json`
- `output/图像 002_20260422T091749Z/05_crop/图像 002_frame_boxes_overlay.png`
- `output/图像 002_20260422T091749Z/07_final/图像 002_sidecar.json`

### Problems Found
- The original Step 7 projection logic merged multiple frames because it assumed separators would appear as bright gaps.
- The real scan often separates frames with dark horizontal borders.

### Suspected Causes
- Frame content brightness varies strongly, so content rows and separator rows cannot be separated reliably with one global bright/dark threshold.
- The corrected preview is good enough for diagnostics but not yet geometrically normalized.

### Temporary Decisions / Workarounds
- Use horizontal dark separator detection inside each strip for preview-space frame splitting.
- Keep boxes marked as preview diagnostics until full-resolution validation is added.

### README Check
- no change needed

### Remaining Work
- Validate box coordinates against full-resolution crops.
- Add a review/contact-sheet output before final PNG export.
- Improve confidence scoring using expected aspect ratio and edge margins.

### Recommended Next Step
- Generate low-resolution per-frame crop previews from the detected boxes so each detected frame can be reviewed individually before full-resolution export.

---

## Step 9 - Constrained frame box alignment
Time: 2026-04-22 18:02 Asia/Shanghai
Status: completed

### Goal
- Improve frame box alignment using the user's suggested directions: contrast/darken detection preprocessing and equal-size non-overlap constraints.

### Completed
- Added detection-only luminance preprocessing: percentile contrast stretch plus gamma darkening.
- Kept the visible corrected preview unchanged; preprocessing is used only for segmentation decisions.
- Added preprocessing parameters to `frame_boxes.json`.
- Changed strip frame splitting to estimate frame count and then distribute non-overlapping equal-height boxes within each strip's content bounds.
- Preserved separator diagnostics for debugging.
- Re-ran the real Hasselblad sample and produced 12 aligned preview boxes, 6 per strip.

### Files Changed
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/crop.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260422T100230Z/05_crop/图像 002_frame_boxes.json`
- `output/图像 002_20260422T100230Z/05_crop/图像 002_frame_boxes_overlay.png`
- `output/图像 002_20260422T100230Z/07_final/图像 002_sidecar.json`

### Problems Found
- Pure separator-based splitting could still leave short dropped intervals between boxes.
- The frame boxes are now more regular, but they are still preview-space estimates and should be reviewed through per-frame previews before full-resolution crop export.

### Suspected Causes
- Some separator detections are internal image edges or frame borders rather than true frame gaps.
- Equal physical frame size is a stronger assumption for this sample than local threshold-only splitting.

### Temporary Decisions / Workarounds
- Use detected strip bounds and estimated frame count to build equal-height, non-overlapping preview boxes.
- Keep separator locations in JSON as diagnostics rather than using every separator as a hard crop boundary.

### README Check
- no change needed

### Remaining Work
- Generate low-resolution per-frame crop previews from these boxes.
- Validate whether box padding should be adjusted before full-resolution export.
- Add user override options for expected frames per strip if other rolls differ.

### Recommended Next Step
- Generate low-resolution per-frame crop previews from the detected boxes and a contact sheet for visual approval.

---

## Step 10 - Padded per-frame review previews
Time: 2026-04-22 18:15 Asia/Shanghai
Status: completed

### Goal
- Generate low-resolution per-frame crop previews with extra padding around each detected frame so the user can verify whether the frame box cuts into the image.

### Completed
- Added padded per-frame preview output under `05_crop/frames_preview/`.
- Added a red inner rectangle on each preview showing the detected frame box.
- Added 8% padding around each frame box where image boundaries allow it.
- Added `05_crop/*_frame_contact_sheet.png` for quick review.
- Added `05_crop/*_frame_previews.json` with padded and unpadded preview boxes.
- Integrated frame preview outputs into the final sidecar.
- Updated README to mention padded low-resolution frame previews.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/crop.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260422T101547Z/05_crop/图像 002_frame_contact_sheet.png`
- `output/图像 002_20260422T101547Z/05_crop/图像 002_frame_previews.json`
- `output/图像 002_20260422T101547Z/05_crop/frames_preview/`
- `output/图像 002_20260422T101547Z/07_final/图像 002_sidecar.json`

### Problems Found
- Some edge frames cannot receive full padding on the outer scan boundary because the preview image ends there.
- These are still preview-space crops, not full-resolution output.

### Suspected Causes
- The frame strips sit close to the scan's left/right boundaries in the preview.

### Temporary Decisions / Workarounds
- Keep padding clipped to preview bounds.
- Use the red inner rectangle to distinguish detected frame box from review padding.

### README Check
- updated

### Remaining Work
- Let the user review the contact sheet and individual frame previews.
- If boxes are accepted, map the padded or unpadded boxes to full-resolution coordinates.
- Add optional padding configuration before full-resolution export.

### Recommended Next Step
- Review the padded contact sheet; then implement full-resolution crop preview/export using the approved box strategy.

---

## Step 11 - Full-resolution draft frame PNGs
Time: 2026-04-22 18:25 Asia/Shanghai
Status: completed

### Goal
- Move forward with the accepted-but-imperfect crop boxes by exporting full-resolution draft frame PNGs for review.

### Completed
- Added full-resolution draft crop export from detected frame boxes.
- Used source TIFF memmap slicing so each frame is processed by region rather than loading the whole scan at once.
- Applied direct inversion plus the existing preview-derived channel multipliers.
- Added 3% padding to full-resolution draft crops.
- Added `07_final/draft_frames/` with 12 draft PNGs.
- Added `07_final/*_draft_frames.json` with source and padded source coordinates.
- Added `07_final/*_draft_contact_sheet.png` for quick review.
- Integrated draft outputs into the final sidecar.
- Recorded that crop accuracy is acceptable for now but not perfect, and should be revisited near project finish.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/crop.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260422T102549Z/07_final/draft_frames/`
- `output/图像 002_20260422T102549Z/07_final/图像 002_draft_frames.json`
- `output/图像 002_20260422T102549Z/07_final/图像 002_draft_contact_sheet.png`
- `output/图像 002_20260422T102549Z/07_final/图像 002_sidecar.json`

### Problems Found
- Full-resolution draft export takes about 95 seconds on the sample because it writes 12 large PNGs.
- Crop boxes are acceptable but not fully accurate; crop refinement should be revisited near project finish.
- Draft color is still simple inversion plus global channel correction, not final grading.

### Suspected Causes
- PNG compression and large frame dimensions dominate runtime.
- Preview-space crop detection cannot perfectly capture frame edges without later full-resolution refinement or manual overrides.

### Temporary Decisions / Workarounds
- Keep these outputs named `draft` rather than final.
- Preserve padding and coordinate metadata so crop rules can be changed later without losing traceability.

### README Check
- updated

### Remaining Work
- Add base grading / exposure normalization.
- Add final crop refinement pass near project finish.
- Add final PNG export naming once color and crop are accepted.

### Recommended Next Step
- Implement basic per-frame exposure normalization / base grade on draft frames while keeping the current crop issue recorded for later refinement.

---

## Step 12 - Basic per-frame grade
Time: 2026-04-22 18:34 Asia/Shanghai
Status: completed

### Goal
- Add conservative per-frame exposure / contrast normalization for full-resolution draft frames.

### Completed
- Added `src/negflow/pipeline/grade_basic.py`.
- Added per-frame percentile stretch, gray balance, and slight gamma adjustment.
- Added `04_base_grade/graded_frames/` with 12 graded PNGs.
- Added `04_base_grade/*_graded_frames.json` with per-frame grade parameters.
- Added `04_base_grade/*_graded_contact_sheet.png`.
- Integrated graded outputs into the final sidecar.
- Updated README for current scope.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/grade_basic.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260422T103434Z/04_base_grade/graded_frames/`
- `output/图像 002_20260422T103434Z/04_base_grade/图像 002_graded_frames.json`
- `output/图像 002_20260422T103434Z/04_base_grade/图像 002_graded_contact_sheet.png`
- `output/图像 002_20260422T103434Z/07_final/图像 002_sidecar.json`

### Problems Found
- Full sample processing now takes about 3 minutes because it writes both draft and graded full-resolution PNGs.
- The graded contact sheet is more readable but somewhat heavy-handed; this is still not final look or color.
- Crop accuracy remains acceptable but not perfect and is still recorded for later refinement.

### Suspected Causes
- Large PNG write time dominates runtime.
- Per-frame percentile stretch can increase contrast aggressively on low-contrast scans.

### Temporary Decisions / Workarounds
- Keep outputs marked as graded drafts rather than final.
- Use contact sheet review before deciding final grade/export defaults.

### README Check
- updated

### Remaining Work
- Add final export folder/naming once grade and crop are accepted.
- Revisit crop refinement near project finish.
- Add configurable grade strength / preset later.

### Recommended Next Step
- Add a final-export command/stage that copies or writes accepted graded frames into `07_final/final_png` with sidecar metadata, while still marking crop refinement as a known follow-up.

---

## Step 13 - Final PNG export
Time: 2026-04-22 18:48 Asia/Shanghai
Status: completed

### Goal
- Promote the current graded frame PNGs into a final export folder with traceable metadata.

### Completed
- Added `src/negflow/pipeline/final_export.py`.
- Added `07_final/final_png/` export creation.
- Added `07_final/*_final_png_manifest.json` with source graded PNG, source draft PNG, grade parameters, and final filename per frame.
- Integrated final PNG export into the TIFF processing sidecar.
- Kept `final_crop_refinement` in pending stages and added a warning that current final PNGs are promoted from the basic grade.
- Updated the smoke test to verify final PNG export metadata and pending-stage state.
- Updated README for the new final export folder and current limitations.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/final_export.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260422T104400Z/07_final/final_png/`
- `output/图像 002_20260422T104400Z/07_final/图像 002_final_png_manifest.json`
- `output/图像 002_20260422T104400Z/07_final/图像 002_sidecar.json`

### Problems Found
- The final PNG export duplicates the graded PNG files, so disk use increases by another full set of frame PNGs.
- The current exported final PNGs still inherit the known crop imperfection.
- Console display of Chinese paths can appear mojibake in PowerShell output, while filesystem listings still show the expected Chinese filenames.

### Suspected Causes
- `shutil.copy2` intentionally creates independent final files for an inspectable final folder.
- Crop refinement was deliberately deferred after the current detection became acceptable enough to continue.
- PowerShell code page / terminal encoding affects display of JSON text containing Chinese paths.

### Temporary Decisions / Workarounds
- Keep the duplicate final files for now because they make the final output folder simple to inspect and consume.
- Keep crop refinement explicitly pending in sidecar and status instead of hiding it.

### README Check
- updated

### Remaining Work
- Revisit final crop refinement near project finish.
- Add actual `.fff` conversion backend when a usable converter path or workflow is available.
- Tune grade strength / preset behavior if the current basic grade is too heavy-handed.

### Recommended Next Step
- Revisit the crop-refinement pass using the current final PNG manifest as the acceptance target, or connect a real `.fff` conversion backend if the converter path is available.

---

## Step 14 - Source separator crop refinement
Time: 2026-04-23 11:38 Asia/Shanghai
Status: completed

### Goal
- Improve crop boundary alignment without changing frame count or introducing overlapping crops.

### Completed
- Added source-resolution separator sampling in `src/negflow/pipeline/crop.py`.
- Kept preview detection as the frame-count and strip-order source of truth.
- Refined internal frame boundaries by sampling high-resolution TIFF windows around each current boundary.
- Accepted only separator candidates with enough luminance contrast and stable position.
- Added `05_crop/*_frame_boxes_refined.json`.
- Added `05_crop/*_frame_boxes_refined_overlay.png`.
- Routed frame previews, full-resolution draft frames, graded frames, and final PNG export through the refined boxes.
- Updated the sidecar with `source_separator_crop_refinement`.
- Updated tests to verify the refinement output exists and preserves frame count.
- Updated `.gitignore` to exclude generated `*.egg-info/`.
- Updated README for the refined crop output.

### Files Changed
- `.gitignore`
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/crop.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260423T033501Z/05_crop/图像 002_frame_boxes_refined.json`
- `output/图像 002_20260423T033501Z/05_crop/图像 002_frame_boxes_refined_overlay.png`
- `output/图像 002_20260423T033501Z/05_crop/图像 002_frame_contact_sheet.png`
- `output/图像 002_20260423T033501Z/07_final/final_png/`
- `output/图像 002_20260423T033501Z/07_final/图像 002_sidecar.json`

### Problems Found
- One candidate boundary on the sample had low separator contrast and was correctly rejected.
- The crop is improved but still axis-aligned; it does not yet correct slight strip/frame skew.
- Full sample processing remains around 3 minutes because it writes draft, graded, and final PNG sets.

### Suspected Causes
- Some adjacent frames have less obvious separator contrast in the positive preview.
- The current crop model is still rectangular and axis-aligned, while scanned film/frame edges can be slightly skewed.
- PNG writes dominate runtime.

### Temporary Decisions / Workarounds
- Keep rejected low-confidence boundary unchanged rather than risking a worse crop.
- Keep `final_crop_refinement` pending until visual review confirms whether skew-aware crop correction is needed.
- Continue preserving padded previews so crop errors remain easy to spot.

### README Check
- updated

### Remaining Work
- Visually review the refined outputs.
- Decide whether to add skew-aware strip/frame rectification.
- Connect actual `.fff` conversion backend later.

### Recommended Next Step
- Inspect the refined contact sheet and final PNGs; if crop alignment is acceptable, move next to either skew-aware crop cleanup or `.fff` backend integration.

---

## Step 15 - Crop refinement review overlay
Time: 2026-04-23 13:45 Asia/Shanghai
Status: completed

### Goal
- Add a clear review artifact for comparing coarse crop boxes against source-refined crop boxes.

### Completed
- Added `write_crop_refinement_review` in `src/negflow/pipeline/crop.py`.
- Added `05_crop/*_crop_refinement_review.json`.
- Added `05_crop/*_crop_refinement_review_overlay.png`.
- The review overlay draws coarse boxes in red and refined boxes in green.
- The review JSON records per-frame preview/source deltas, accepted adjustments, rejected adjustments, and max source-coordinate movement.
- Integrated `crop_refinement_review` into the TIFF sidecar.
- Updated smoke tests to verify the review JSON and overlay exist.
- Updated README for the new crop review output.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/crop.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260423T054202Z/05_crop/图像 002_crop_refinement_review.json`
- `output/图像 002_20260423T054202Z/05_crop/图像 002_crop_refinement_review_overlay.png`
- `output/图像 002_20260423T054202Z/05_crop/图像 002_frame_contact_sheet.png`
- `output/图像 002_20260423T054202Z/07_final/final_png/`
- `output/图像 002_20260423T054202Z/07_final/图像 002_sidecar.json`

### Problems Found
- The review overlay confirms crop changes are limited to frame-to-frame boundaries; it does not address frame/strip skew.
- The current red/green overlay is useful but still preview-resolution only.
- Full sample processing still takes about 3 minutes because the whole pipeline rewrites image outputs.

### Suspected Causes
- The current crop model is axis-aligned and intentionally avoids geometric warping.
- Preview overlays are fast and readable, but cannot show every full-resolution edge detail.
- PNG export remains the runtime bottleneck.

### Temporary Decisions / Workarounds
- Use the review overlay as the decision gate before implementing skew-aware crop cleanup.
- Keep `final_crop_refinement` pending until skew-aware cleanup is either implemented or explicitly deferred.

### README Check
- updated

### Remaining Work
- Decide whether skew-aware crop cleanup is worth implementing now.
- Push the post-Step-14/15 changes to GitHub when requested.
- Connect actual `.fff` conversion backend later.

### Recommended Next Step
- If the review overlay looks acceptable, either push the latest local changes to GitHub or start a small skew-aware crop investigation.

---

## Step 16 - Roll film-base color grade
Time: 2026-04-23 14:38 Asia/Shanghai
Status: completed

### Goal
- Improve color conversion only, without changing crop detection, crop coordinates, FFF handling, or final PNG naming.

### Completed
- Updated `src/negflow/pipeline/grade_basic.py`.
- Added source-TIFF-aware grading when draft frame metadata includes `source_tiff` and crop coordinates.
- Estimated one roll-level film base / color mask model from frame margin samples instead of estimating each frame independently.
- Replaced the main grade path with film-base-normalized inversion followed by per-frame tone mapping.
- Changed neutral balancing to use low-saturation midtone candidates instead of the entire image.
- Preserved the old draft-PNG grading path as a fallback.
- Added roll color model metadata to `04_base_grade/*_graded_frames.json`.
- Updated tests to assert the roll color model is recorded.
- Updated README for the new color grade behavior.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/grade_basic.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260423T063229Z/04_base_grade/图像 002_graded_contact_sheet.png`
- `output/图像 002_20260423T063229Z/04_base_grade/图像 002_graded_frames.json`
- `output/图像 002_20260423T063229Z/07_final/final_png/`
- `output/图像 002_20260423T063229Z/07_final/图像 002_sidecar.json`

### Problems Found
- The new output is more traceable and roll-consistent, but it may still look slightly cool on this overcast sample.
- The method is still a conservative automatic grade, not a calibrated film/scanner ICC workflow.
- The grade reads source TIFF crops again, so processing remains disk-heavy.

### Suspected Causes
- The sample appears to contain mostly overcast daylight and cool architectural scenes, making automatic neutrality ambiguous.
- True film/scanner profiling would need known targets or scanner/film profiles, which the current sample does not provide.
- The pipeline still writes draft, graded, and final PNGs separately.

### Temporary Decisions / Workarounds
- Prefer a shared roll-level film base estimate over per-frame color-mask guesses.
- Keep neutral correction clipped so a single frame cannot swing color too aggressively.
- Leave crop and export behavior unchanged for this color-only step.

### README Check
- updated

### Remaining Work
- Visually compare the new final PNGs against the previous output.
- Tune color warmth / neutral candidate rules if the result is still too cool.
- Push this color step to GitHub when accepted.

### Recommended Next Step
- Inspect the new graded contact sheet and final PNGs; if the direction is right, tune warmth/neutral behavior or push the color step to GitHub.

---

## Step 17 - Warm-neutral bias tune
Time: 2026-04-23 14:58 Asia/Shanghai
Status: completed

### Goal
- Slightly warm the roll-level automatic grade without changing crop/export behavior.

### Completed
- Updated `src/negflow/pipeline/grade_basic.py`.
- Added a small warm-neutral bias after neutral balance estimation.
- Recorded the bias in frame grade metadata as `warmth_bias`.
- Re-ran the real sample to `output/图像 002_20260423T064857Z/`.
- Updated tests to check that the new grade metadata records `warmth_bias`.
- Updated README for the new warm-neutral behavior.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/grade_basic.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260423T064857Z/04_base_grade/图像 002_graded_contact_sheet.png`
- `output/图像 002_20260423T064857Z/04_base_grade/图像 002_graded_frames.json`
- `output/图像 002_20260423T064857Z/07_final/final_png/`
- `output/图像 002_20260423T064857Z/07_final/图像 002_sidecar.json`

### Problems Found
- The warm bias is intentionally mild, so improvement is subtle rather than dramatic.
- The result is still automatic and scene-agnostic; some frames may still want manual taste adjustments.
- Processing cost is unchanged because the source-TIFF grade path is unchanged.

### Suspected Causes
- The sample is dominated by cool overcast daylight and gray architecture, so only a modest warm shift is appropriate.
- Stronger warming at this stage would likely push indoor highlights and neutral walls too yellow.

### Temporary Decisions / Workarounds
- Keep the warm shift explicit and recorded in metadata rather than hiding it inside film-base estimation.
- Keep the bias small so it can be tuned again without rethinking the whole grading model.

### README Check
- updated

### Remaining Work
- Decide whether this warmth level is acceptable.
- Push the updated color stage to GitHub.
- Continue color tuning only if you still want a different balance.

### Recommended Next Step
- If this warmth level looks acceptable, push the latest local changes to GitHub; otherwise continue with another small color-only adjustment.

---

## Step 18 - External FFF converter handoff
Time: 2026-04-23 16:28 Asia/Shanghai
Status: completed

### Goal
- Turn the `.fff` backend boundary into a real external-converter handoff that can produce a work TIFF and continue through the existing TIFF pipeline.

### Completed
- Expanded `src/negflow/fff_backend.py` with backend config loading, a minimal YAML reader, and external converter command execution.
- Added placeholder expansion for `{input_path}`, `{output_tiff_path}`, `{input_path_quoted}`, `{output_tiff_path_quoted}`, `{input_stem}`, and `{output_tiff_stem}`.
- Added explicit conversion failure handling with captured command, return code, stdout, and stderr.
- Refactored `src/negflow/runner.py` so `.fff` conversion can hand off directly into the same TIFF processing path used by `process-tiff`.
- Added `02_work_tiff/*_fff_conversion.json` metadata for configured `.fff` conversions.
- Added `backend.external_converter_command: null` to `configs/default.yaml`.
- Added a smoke test that uses a mock external converter to create a TIFF and verifies the `.fff -> TIFF -> full pipeline` path completes.
- Re-ran the real TIFF sample to confirm the shared pipeline refactor did not break the current working path.
- Updated README for external converter configuration and placeholder usage.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `configs/default.yaml`
- `src/negflow/fff_backend.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m pip install -e . --no-deps --dry-run
```

### Outputs To Inspect
- `output/图像 002_20260423T082452Z/04_base_grade/图像 002_graded_contact_sheet.png`
- `output/图像 002_20260423T082452Z/07_final/final_png/`
- `output/图像 002_20260423T082452Z/07_final/图像 002_sidecar.json`
- `configs/default.yaml`

### Problems Found
- A real Hasselblad X5 / FlexColor converter command is still not configured in this environment, so live `.fff` validation has not been run yet.
- The new YAML reader is intentionally narrow and only targets the current nested config structure used by this project.
- The shared TIFF pipeline still writes draft, graded, and final PNG sets, so runtime remains dominated by image export.

### Suspected Causes
- The project still needs an actual external `.fff` exporter or converter that is available on this machine.
- Adding a full YAML dependency just for backend settings was deliberately avoided in this small step.
- PNG encoding is still the slowest part of the end-to-end path.

### Temporary Decisions / Workarounds
- Validate the `.fff` converter handoff with a mock converter test until a real converter command is chosen.
- Keep the config reader small and local to backend settings for now.
- Reuse the existing TIFF pipeline exactly as-is after conversion instead of branching behavior for `.fff`.

### README Check
- updated

### Remaining Work
- Choose and test a real Hasselblad / FlexColor external converter command for `.fff` input.
- Decide later whether to replace the minimal YAML reader with a full parser.
- Continue color tuning or output-footprint optimization as separate steps.

### Recommended Next Step
- Configure a real `.fff` converter command and run the first live `.fff` end-to-end validation, or return to color tuning while keeping this converter wiring in place.

---

## Step 19 - Working-document refresh
Time: 2026-04-24 10:20 Asia/Shanghai
Status: completed

### Goal
- Refresh the project working documents so they clearly summarize current methods, finished functionality, and remaining plans without needing to read the whole step history.

### Completed
- Updated `README.md` with dedicated sections for current methods, implemented features, and remaining plan.
- Updated the top of `STATUS.md` with a concise snapshot of current methods, completed functionality, and remaining plan.
- Kept the detailed step-by-step development record intact below the new summary sections.
- Prepared the documentation state for GitHub sync.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`

### Run Command
```bash
No functional code changes in this step.
```

### Test Command
```bash
Not rerun in this step because the update is documentation-only.
```

### Outputs To Inspect
- `README.md`
- `STATUS.md`
- `status.json`

### Problems Found
- The project state was already implemented, but the highest-signal summary was spread across README text and many step entries.
- `status.json` previously contained mojibake in some Chinese paths due to terminal/display encoding.

### Suspected Causes
- The project grew quickly through incremental steps, so the documentation remained accurate but not compact.
- Some earlier file inspection happened through a terminal encoding path that did not preserve Chinese characters cleanly in copied output.

### Temporary Decisions / Workarounds
- Keep the detailed historical log in `STATUS.md`, but add a compact status snapshot at the top.
- Rewrite `status.json` cleanly with current UTF-8 content.

### README Check
- updated

### Remaining Work
- Push the refreshed documentation to GitHub.
- Continue with either live `.fff` converter validation or color tuning in the next implementation step.

### Recommended Next Step
- Push this documentation refresh to GitHub, then continue with the next functional step.

---

## Step 20 - Verification and FFF config parser hardening
Time: 2026-04-24 11:07 Asia/Shanghai
Status: completed

### Goal
- Verify the currently implemented TIFF and mock `.fff` functionality, identify whether the implemented scope is stable, and make only the smallest useful optimization found during review.

### Completed
- Read `AGENTS.md`, `README.md`, `STATUS.md`, `status.json`, the CLI, runner, backend, crop, inversion, grading, and final export modules.
- Ran the full existing smoke test suite; the first sandboxed run failed because Windows temp-directory writes were blocked, then the approved run passed.
- Ran the real TIFF sample through the current pipeline and confirmed it completed with 12 detected/exported frames.
- Inspected the generated sidecar, final PNG manifest, crop refinement review, graded frame metadata, graded contact sheet, and crop review overlay.
- Hardened the minimal backend YAML reader so `#` inside quoted converter commands is preserved while comments outside quotes are still stripped.
- Added a regression test for quoted external converter commands containing `#`.
- Re-ran the test suite after the change and re-ran the real TIFF main command after the change.

### Files Changed
- `src/negflow/fff_backend.py`
- `tests/test_runner.py`
- `STATUS.md`
- `status.json`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process-tiff "data\图像 002.tiff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 002_20260424T030437Z/04_base_grade/图像 002_graded_contact_sheet.png`
- `output/图像 002_20260424T030437Z/05_crop/图像 002_crop_refinement_review_overlay.png`
- `output/图像 002_20260424T030437Z/05_crop/图像 002_crop_refinement_review.json`
- `output/图像 002_20260424T030437Z/07_final/final_png/`
- `output/图像 002_20260424T030437Z/07_final/图像 002_sidecar.json`

### Problems Found
- The implemented TIFF path is stable on the sample, but final crop refinement is still explicitly pending.
- The real `.fff` path is still blocked on choosing and validating an actual Hasselblad/FlexColor converter command on this machine.
- The external converter config reader was brittle around `#` characters inside quoted commands; this step fixed that.
- `git -C D:\code\NegFlow status --short` reported that the folder is not currently recognized as a Git repository, even though a partial `.git` directory is present.

### Suspected Causes
- Crop precision is intentionally deferred until the project wraps up, because the current boxes are already acceptable for review output.
- `.fff` support needs a real external converter binary or command-line export path, which has not been selected yet.
- The minimal YAML reader previously stripped comments with a plain split on `#`.
- The local `.git` directory appears incomplete or locked, so Git metadata may need cleanup before the next push.

### Temporary Decisions / Workarounds
- Keep the YAML reader small and dependency-free, but make comment stripping quote-aware.
- Treat this as a backend-configuration hardening step rather than a broader parser rewrite.
- Do not update README because user-facing commands, outputs, and implemented scope did not change.

### README Check
- no change needed

### Remaining Work
- Configure and run a real `.fff` converter command.
- Decide whether the next functional step should be live `.fff` validation, final crop precision, color tuning, or output footprint reduction.
- Repair or reinitialize Git metadata before attempting another push from `D:\code\NegFlow`.

### Recommended Next Step
- Pick the next step together: live `.fff` converter validation is the highest-leverage next implementation step; if no converter is available yet, tune final color or add output-retention controls as the next small step.

---

## Step 21 - Live FFF converter availability check
Time: 2026-04-24 11:15 Asia/Shanghai
Status: blocked

### Goal
- Check whether the next planned step, live `.fff` converter validation, can be run on this machine with the current project inputs and installed software.

### Completed
- Checked `data/` and nearby project/workspace folders for real `.fff` sample inputs.
- Checked `configs/default.yaml`; `backend.external_converter_command` is still `null`.
- Searched `C:\Program Files` and `C:\Program Files (x86)` for FlexColor, Hasselblad, 3F, FFF, or Imacon executables.
- Found FlexColor installed at `C:\Program Files\Hasselblad\FlexColor v4.8.9.1\FlexColor.exe`.
- Confirmed the FlexColor install includes `Imacon 3f` Photoshop plugins and `Flextight X5 & 949.icc`.
- Read the local FlexColor readme and searched it for command-line, batch, export, TIFF, and 3F references.
- Did not configure `configs/default.yaml`, because no reliable unattended `.fff -> TIFF` command syntax was found.

### Files Changed
- `STATUS.md`
- `status.json`

### Run Command
```bash
Get-ChildItem -Recurse -File -Path 'D:\code','D:\hqg\文档\New project' -Include *.fff -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -File -Path 'C:\Program Files','C:\Program Files (x86)' -Include *Flex*.exe,*Hassel*.exe,*3F*.exe,*fff*.exe,*Imacon*.exe -ErrorAction SilentlyContinue
```

### Test Command
```bash
Select-String -Path 'C:\Program Files\Hasselblad\FlexColor v4.8.9.1\Misc\FlexColor read me.rtf' -Pattern 'command line|batch|export|TIFF|3f scan destination|Photoshop plugin' -CaseSensitive:$false
```

### Outputs To Inspect
- `C:\Program Files\Hasselblad\FlexColor v4.8.9.1\FlexColor.exe`
- `C:\Program Files\Hasselblad\FlexColor v4.8.9.1\Plugins\Imacon 3f.8bi`
- `C:\Program Files\Hasselblad\FlexColor v4.8.9.1\PluginsX64\Imacon 3fX64.8bi`
- `C:\Program Files\Hasselblad\FlexColor v4.8.9.1\Profiles\Flextight X5 & 949.icc`
- `C:\Program Files\Hasselblad\FlexColor v4.8.9.1\Misc\FlexColor read me.rtf`

### Problems Found
- No real `.fff` sample file was found under the project `data/` folder, `D:\code`, or the current workspace root.
- FlexColor is installed, but no local documentation was found for an unattended command-line `.fff -> TIFF` export.
- `configs/default.yaml` still has no real converter command configured.

### Suspected Causes
- The current repo was developed against a real TIFF sample and a mock `.fff` converter test, not against live `.fff` files.
- FlexColor appears to be primarily GUI/plugin oriented in this installation, at least from the visible local files.

### Temporary Decisions / Workarounds
- Do not guess a FlexColor command-line template.
- Do not launch the FlexColor GUI from the agent just to probe behavior, because no `.fff` sample is available to complete a real validation anyway.
- Keep the existing mock converter test as the automated safety net until a real sample and converter path are available.

### README Check
- no change needed

### Remaining Work
- Provide or place at least one real `.fff` sample under `data/` or another known path.
- Confirm whether FlexColor supports unattended command-line export, or choose another converter/export bridge.
- Once both are available, configure `backend.external_converter_command` and run `python -m negflow process "<sample.fff>" --output output --preset neutral_archive`.

### Recommended Next Step
- If a real `.fff` sample and export command can be supplied, repeat live `.fff` validation. Otherwise, move to the next non-blocked implementation step: output-retention controls to reduce disk usage and runtime footprint.

---

## Step 22 - TIFF-compatible FFF passthrough
Time: 2026-04-24 11:31 Asia/Shanghai
Status: completed

### Goal
- Use the newly supplied real `.fff` samples to validate whether the project can process Hasselblad/FlexColor 3F files without an external converter, and add the smallest useful support if possible.

### Completed
- Found four real `.fff` files under `data/fff/`.
- Verified that `图像 001.fff` and `图像 004.fff` start with a TIFF header and can be opened by `tifffile.TiffFile`.
- Confirmed `图像 001.fff` has a full-resolution main page with shape `28320 x 7592 x 3`, `uint16`, axes `YXS`.
- Confirmed `图像 004.fff` has a full-resolution main page with shape `7720 x 7593 x 3`, `uint16`, axes `YXS`.
- Added direct support for `backend.mode: tiff_passthrough` `.fff` files that are TIFF-compatible.
- The `.fff` path now records `conversion_method: tiff_compatible_reference` and uses the original `.fff` as the working TIFF source when no external converter is needed.
- Kept the external converter path unchanged for `.fff` variants that need a separate converter.
- Added a smoke test for TIFF-compatible `.fff` passthrough.
- Updated README to describe directly TIFF-compatible `.fff` support.
- Ran the test suite successfully.
- Ran `图像 004.fff` end to end; it completed, but its detected frames include black/non-image regions and should be treated as a crop robustness case.
- Ran `图像 001.fff` end to end; it completed with 12 final PNGs and a usable graded contact sheet.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/fff_backend.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 001.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 001_20260424T032801Z/04_base_grade/图像 001_graded_contact_sheet.png`
- `output/图像 001_20260424T032801Z/05_crop/图像 001_crop_refinement_review_overlay.png`
- `output/图像 001_20260424T032801Z/02_work_tiff/图像 001_fff_conversion.json`
- `output/图像 001_20260424T032801Z/07_final/final_png/`
- `output/图像 001_20260424T032801Z/07_final/图像 001_sidecar.json`
- `output/图像 004_20260424T032640Z/04_base_grade/图像 004_graded_contact_sheet.png`

### Problems Found
- `图像 001.fff` processes successfully and looks like a normal 12-frame roll.
- `图像 004.fff` processes successfully but currently produces 18 detected boxes, including black/non-image areas, so crop detection needs a later robustness pass for partial/short strips or nonstandard scans.
- Terminal display still shows mojibake for Chinese paths in command output, but file paths are written correctly in UTF-8 JSON/Markdown.

### Suspected Causes
- Hasselblad 3F files in this sample set are TIFF-container compatible, so `tifffile` can read the main image page directly.
- `图像 004.fff` is much smaller than the other `.fff` files and likely has a different layout or partial content that confuses the current strip detector.
- Console encoding is separate from the project file encoding.

### Temporary Decisions / Workarounds
- Prefer direct `tiff_passthrough` for TIFF-compatible `.fff` files before requiring an external converter.
- Keep external converter support for future `.fff` variants that are not directly readable.
- Do not try to fix the `图像 004.fff` crop behavior in this step; record it as a focused future crop robustness task.

### README Check
- updated

### Remaining Work
- Run the remaining large `.fff` samples (`图像 002.fff`, `图像 003.fff`) when broader roll validation is desired.
- Add crop robustness for partial/short/nonstandard `.fff` scans like `图像 004.fff`.
- Add output-retention controls to reduce disk use after full `.fff` support is proven.
- Repair or reinitialize Git metadata before pushing.

### Recommended Next Step
- Add output-retention controls as the next small implementation step, or first run `图像 002.fff` and `图像 003.fff` if you want broader validation before changing output behavior.

---

## Step 23 - Output retention cleanup
Time: 2026-04-24 11:41 Asia/Shanghai
Status: completed

### Goal
- Reduce task-folder disk usage by making large intermediate frame PNG retention configurable, while keeping final PNGs and review artifacts inspectable.

### Completed
- Added `OutputRetentionConfig` and `load_output_retention_config`.
- Added `output.keep_draft_frames` and `output.keep_graded_frames` settings.
- Updated `configs/default.yaml` so both large intermediate frame PNG directories are removed by default after final PNG export.
- Added `06_cleanup/*_output_retention.json` metadata for cleanup actions.
- Updated sidecar output records with `retained` flags for draft and graded frame PNG directories.
- Kept JSON metadata, contact sheets, logs, sidecars, crop review artifacts, and final PNG exports.
- Added tests for retention config parsing and intermediate PNG cleanup.
- Updated README to describe the new default retention behavior.
- Ran the test suite successfully.
- Ran real `图像 001.fff` with the new default config and confirmed final PNGs remain while `07_final/draft_frames` and `04_base_grade/graded_frames` are removed.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `configs/default.yaml`
- `src/negflow/fff_backend.py`
- `src/negflow/runner.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 001.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 001_20260424T033802Z/06_cleanup/图像 001_output_retention.json`
- `output/图像 001_20260424T033802Z/07_final/final_png/`
- `output/图像 001_20260424T033802Z/07_final/图像 001_sidecar.json`
- `output/图像 001_20260424T033802Z/04_base_grade/图像 001_graded_contact_sheet.png`
- `output/图像 001_20260424T033802Z/05_crop/图像 001_crop_refinement_review_overlay.png`

### Problems Found
- The old `图像 001.fff` output with retained intermediates was about 818 MB.
- The new `图像 001.fff` output with default cleanup is about 298 MB.
- This saved roughly 520 MB for one 12-frame roll output while preserving final PNGs and review artifacts.
- Final manifest entries still reference source graded PNG paths that may be removed when `keep_graded_frames: false`; this is acceptable as provenance but should be understood as a historical path unless intermediates are retained.

### Suspected Causes
- Full-resolution draft PNGs and graded PNGs duplicate much of the final export footprint.
- The final PNG export copies graded images before cleanup, so cleanup can safely remove the intermediate directories afterward.

### Temporary Decisions / Workarounds
- Default to smaller task folders in `configs/default.yaml`.
- Keep retention opt-in with `output.keep_draft_frames: true` and `output.keep_graded_frames: true` for debugging runs.
- Only remove directories inside the current task folder, with a guard against deleting outside paths.

### README Check
- updated

### Remaining Work
- Inspect and improve crop logic, especially partial/nonstandard scans like `图像 004.fff`.
- Consider adding a separate final manifest field that marks removed intermediate source paths as not retained.
- Repair or reinitialize Git metadata before pushing.

### Recommended Next Step
- Start a focused crop-review step: inspect current crop detection on `图像 001.fff` and `图像 004.fff`, identify whether the strip/frame logic is correct, then make the smallest safe crop improvement.

---

## Step 24 - Crop robustness for partial FFF scans
Time: 2026-04-24 12:02 Asia/Shanghai
Status: completed

### Goal
- Improve crop detection for the partial/nonstandard `图像 004.fff` scan without regressing the normal 12-frame `图像 001.fff` roll.

### Completed
- Inspected the previous `图像 004.fff` crop artifacts and confirmed the old detector produced 18 boxes, including six near-black boxes from the right-side black strip.
- Added a near-black candidate rejection pass that records rejected boxes in `05_crop/*_frame_boxes.json` instead of exporting them.
- Added luminance standard-deviation metadata to detected crop boxes for easier crop diagnostics.
- Added a wide-strip frame-count cap so internal image texture and horizontal lines do not split an unusually wide partial scan into many false frames.
- Fixed `_frames_from_separators` so an estimated frame count of 1 returns one content region instead of continuing to split on internal separators.
- Added low-detail vertical tail trimming for long blank tails, guarded so it only applies when enough nonblank content remains.
- Re-ran `图像 004.fff`; final crop output changed from 18 false/fragmented frames to 1 final PNG covering the visible image area.
- Re-ran `图像 001.fff`; it still produces 12 final PNGs with no rejected boxes and no tail trim applied.
- Added unit tests for near-black rejection, wide-strip over-split prevention, and low-detail tail trimming.
- Updated README for the new crop-guard behavior and crop metadata.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/crop.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 004.fff" --output output --preset neutral_archive
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 001.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 004_20260424T035643Z/05_crop/图像 004_frame_boxes_overlay.png`
- `output/图像 004_20260424T035643Z/05_crop/图像 004_frame_boxes.json`
- `output/图像 004_20260424T035643Z/04_base_grade/图像 004_graded_contact_sheet.png`
- `output/图像 004_20260424T035643Z/07_final/final_png/`
- `output/图像 004_20260424T035643Z/07_final/图像 004_sidecar.json`
- `output/图像 001_20260424T035759Z/04_base_grade/图像 001_graded_contact_sheet.png`
- `output/图像 001_20260424T035759Z/07_final/final_png/`
- `output/图像 001_20260424T035759Z/07_final/图像 001_sidecar.json`

### Problems Found
- `图像 004.fff` is a partial/nonstandard scan with one visible image area, a long blank tail, and a separate black strip.
- The previous projection detector treated internal subject texture and blank/black areas as frame separators or frames.
- The new crop guards improve this case, but they are still heuristic and need validation on `图像 002.fff` and `图像 003.fff`.

### Suspected Causes
- `图像 004.fff` is much shorter than the other roll scans and has a wide partial-strip layout rather than the normal two narrow six-frame strips.
- Projection-only separator detection is vulnerable to subject texture, black scanner regions, and blank film-base tails unless constrained by strip geometry and content detail.

### Temporary Decisions / Workarounds
- Reject near-black candidates only when at least one brighter candidate remains, so all-black diagnostic inputs do not disappear by accident.
- Apply wide-strip frame-count capping only when a strip is unusually wide relative to the minimum frame height.
- Trim low-detail vertical tails only when the tail is long enough and a valid content region remains.

### README Check
- updated

### Remaining Work
- Run `图像 002.fff` and `图像 003.fff` to validate the crop guards across more normal full rolls.
- Continue color tuning after the crop behavior is stable across the supplied `.fff` set.
- Consider adding a crop-review report that summarizes rejected boxes and applied trims in one compact artifact.

### Recommended Next Step
- Validate the updated crop logic on `图像 002.fff` and `图像 003.fff`, then decide whether crop is stable enough to return to color tuning.

---

## Step 25 - OpenCV crop probe
Time: 2026-04-24 14:35 Asia/Shanghai
Status: completed

### Goal
- Add an OpenCV-based crop diagnostic path that can be compared against the current projection detector without changing final crop/export behavior yet.

### Completed
- Added `src/negflow/pipeline/opencv_probe.py`.
- The probe reads the corrected preview, builds a luminance threshold mask, cleans it with OpenCV morphology, extracts connected components, and writes candidate boxes with area / fill / aspect / luminance metrics.
- The pipeline now writes `05_crop/*_opencv_crop_probe.json`, `*_opencv_crop_probe_mask.png`, `*_opencv_crop_probe_cleaned_mask.png`, and `*_opencv_crop_probe_overlay.png`.
- Added the OpenCV probe output to the final sidecar under `outputs.opencv_crop_probe`.
- Added `opencv-python>=4.8` to `requirements.txt` and `pyproject.toml`.
- Added unit / smoke coverage for the OpenCV probe artifacts.
- Ran the full unit test suite successfully.
- Ran real `图像 004.fff`; the OpenCV probe found two large connected components: the left visible content strip and the right black strip region.
- Ran real `图像 001.fff`; the OpenCV probe found the two normal film strips while final export still produced 12 PNGs.
- Updated README for the new OpenCV diagnostic artifacts.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `pyproject.toml`
- `requirements.txt`
- `src/negflow/runner.py`
- `src/negflow/pipeline/opencv_probe.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 004.fff" --output output --preset neutral_archive
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 001.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 004_20260424T063024Z/05_crop/图像 004_opencv_crop_probe_overlay.png`
- `output/图像 004_20260424T063024Z/05_crop/图像 004_opencv_crop_probe.json`
- `output/图像 004_20260424T063024Z/05_crop/图像 004_opencv_crop_probe_cleaned_mask.png`
- `output/图像 001_20260424T063053Z/05_crop/图像 001_opencv_crop_probe_overlay.png`
- `output/图像 001_20260424T063053Z/05_crop/图像 001_opencv_crop_probe.json`
- `output/图像 001_20260424T063053Z/07_final/图像 001_sidecar.json`

### Problems Found
- The OpenCV probe currently finds film-strip-level connected components, not individual final frames.
- On `图像 004.fff`, the right black strip is grouped with its border/film-base edge, so mean luminance alone is not enough to reject it reliably.
- On `图像 001.fff`, OpenCV cleanly identifies two normal strips, which is a better first segmentation layer than global projection.

### Suspected Causes
- Threshold + morphology is good at finding large content/strip regions, but frame boundaries inside a strip still need a second-stage detector.
- The right side of `图像 004.fff` contains black interior plus nonblack border pixels, which raises whole-component luminance metrics.

### Temporary Decisions / Workarounds
- Keep OpenCV output as a diagnostic probe only; do not use it to drive final PNG export in this step.
- Record candidate metrics and overlays so the next step can design a safer second-stage per-strip splitter.

### README Check
- updated

### Remaining Work
- Use OpenCV strip components as regions of interest, then perform per-strip internal frame detection.
- Add component interior metrics, such as inset luminance / texture stats, to better distinguish black strips from real image strips.
- Validate the probe on `图像 002.fff` and `图像 003.fff`.

### Recommended Next Step
- Build a second-stage crop prototype that uses OpenCV components as strip ROIs and runs frame splitting inside each strip, while still writing compare-only artifacts before replacing final crop.

---

## Step 26 - OpenCV strip-frame probe
Time: 2026-04-24 15:19 Asia/Shanghai
Status: completed

### Goal
- Add a compare-only second-stage crop prototype that uses OpenCV connected components as strip ROIs and splits frames inside each accepted strip.

### Completed
- Added `write_opencv_strip_frame_probe` to `src/negflow/pipeline/opencv_probe.py`.
- The strip-frame probe rejects near-black component interiors using inset luminance metrics before attempting frame splitting.
- Accepted strip ROIs are optionally tail-trimmed for long low-detail blank endings, then split by row-luminance valley separator bands.
- The pipeline now writes `05_crop/*_opencv_strip_frame_probe.json` and `*_opencv_strip_frame_probe_overlay.png`.
- Added strip-frame probe output to the final sidecar under `outputs.opencv_strip_frame_probe`.
- Added a synthetic test that verifies a 3-frame strip is split and a black strip is rejected.
- Ran the full unit test suite successfully.
- Ran real `图像 004.fff`; the probe produced 1 accepted frame and rejected the right-side black component.
- Ran real `图像 001.fff`; the probe produced 12 accepted frame candidates across two strips, matching the final PNG count.
- Updated README for the new OpenCV strip-frame diagnostic artifacts.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/runner.py`
- `src/negflow/pipeline/opencv_probe.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 004.fff" --output output --preset neutral_archive
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 001.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 004_20260424T071400Z/05_crop/图像 004_opencv_strip_frame_probe_overlay.png`
- `output/图像 004_20260424T071400Z/05_crop/图像 004_opencv_strip_frame_probe.json`
- `output/图像 001_20260424T071439Z/05_crop/图像 001_opencv_strip_frame_probe_overlay.png`
- `output/图像 001_20260424T071439Z/05_crop/图像 001_opencv_strip_frame_probe.json`
- `output/图像 001_20260424T071439Z/07_final/图像 001_sidecar.json`
- `output/图像 004_20260424T071400Z/07_final/图像 004_sidecar.json`

### Problems Found
- The OpenCV strip-frame probe matches expected counts on `图像 001.fff` and `图像 004.fff`, but it has not yet been validated on `图像 002.fff` or `图像 003.fff`.
- The probe currently writes comparison artifacts only; final export still uses the existing projection/refinement boxes.
- Some frame boxes are intentionally strip-width boxes and still need final border/padding policy before becoming production crop boxes.

### Suspected Causes
- OpenCV component detection provides a better first-level strip ROI than global projection.
- Row-luminance valley splitting works well inside normal strip ROIs because frame separators become local low-row bands.
- Partial scans like `图像 004.fff` still need near-black interior rejection and low-detail tail trimming.

### Temporary Decisions / Workarounds
- Keep the OpenCV strip-frame probe compare-only until it is validated on more real rolls.
- Do not replace final crop export in the same step, even though the probe results are promising on 001 and 004.

### README Check
- updated

### Remaining Work
- Run `图像 002.fff` and `图像 003.fff` through the updated probe and compare against current final crop output.
- Decide whether to promote OpenCV strip-frame boxes to the default crop detector.
- If promoted, add a fallback path to the existing projection detector for unusual scans.

### Recommended Next Step
- Validate the OpenCV strip-frame probe on `图像 002.fff` and `图像 003.fff`; if both match expected roll structure, replace the old projection detector with this OpenCV-guided detector behind a fallback.

---

## Step 27 - OpenCV probe validation on 002 and 003
Time: 2026-04-24 16:00 Asia/Shanghai
Status: completed

### Goal
- Validate the OpenCV strip-frame probe on the fuller `图像 002.fff` and `图像 003.fff` rolls, while treating `图像 004.fff` only as a boundary case.
- Check whether Git version management can be enabled safely.

### Completed
- Ran `图像 002.fff` end to end.
- Ran `图像 003.fff` end to end.
- Inspected both OpenCV strip-frame probe JSON files and overlays.
- Confirmed `图像 002.fff` is a strong pass: two OpenCV strip components, 12 strip-frame candidates, 0 rejected components, 12 projection boxes, and 12 final PNGs.
- Confirmed `图像 003.fff` exposes a remaining crop issue: OpenCV strip-frame probe reduces the old projection over-split from 17 boxes to 13 candidates, but still over-splits the second strip by one frame group.
- Confirmed `图像 003.fff` current final export still follows the old projection detector and therefore exports 17 PNGs.
- Ran the full unit test suite successfully after validation.
- Checked Git state. The project folder contains a broken `.git` directory, but Git does not recognize it as a repository.
- Investigated the broken `.git` directory. It is missing `HEAD`, `objects`, and `config`, and contains a stale `HEAD.lock`.
- Found a Windows explicit DENY ACL on `.git` that blocks normal cleanup / initialization.

### Files Changed
- `STATUS.md`
- `status.json`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 002.fff" --output output --preset neutral_archive
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 003.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 002_20260424T074430Z/05_crop/图像 002_opencv_strip_frame_probe_overlay.png`
- `output/图像 002_20260424T074430Z/05_crop/图像 002_opencv_strip_frame_probe.json`
- `output/图像 002_20260424T074430Z/07_final/final_png/`
- `output/图像 003_20260424T074846Z/05_crop/图像 003_opencv_strip_frame_probe_overlay.png`
- `output/图像 003_20260424T074846Z/05_crop/图像 003_opencv_strip_frame_probe.json`
- `output/图像 003_20260424T074846Z/07_final/final_png/`

### Problems Found
- `图像 002.fff` validates the OpenCV strip-frame approach well.
- `图像 003.fff` shows the OpenCV strip-frame probe is not yet ready to replace the default detector: the second strip is split into 7 candidates instead of the expected 6.
- The old projection detector is worse on `图像 003.fff`, producing 17 boxes / final PNGs.
- Git cannot be initialized normally because the existing `.git` directory has a stale `HEAD.lock` and an explicit DENY ACL.
- A temporary ACL export file under `output/git_acl.txt` could not be removed because the current Windows permissions also denied deletion there.

### Suspected Causes
- `图像 003.fff` has a frame in the second strip where strong local subject edges / dark bands look like separator valleys, so row-valley splitting mistakes internal image content for frame gaps.
- The existing `.git` directory appears to be a partial or crashed initialization from an earlier environment, with inherited or stale Windows ACLs.

### Temporary Decisions / Workarounds
- Do not promote the OpenCV strip-frame probe to default crop yet.
- Do not use `图像 004.fff` as a primary validation sample; keep it only as a partial-scan boundary case.
- Do not force-delete or reset `.git`; repair Git permissions in a dedicated step or have the user remove the broken `.git` directory manually outside the agent if desired.

### README Check
- no change needed

### Remaining Work
- Improve the OpenCV strip-frame splitter so `图像 003.fff` second strip stays at 6 frame candidates.
- Consider a separator acceptance rule that rejects valleys without enough cross-strip separator coverage or that create short/implausible neighboring frame intervals.
- Repair Git repository metadata / ACLs, then create an initial commit once the working tree is safely versionable.

### Recommended Next Step
- Add a conservative separator-validation rule to the OpenCV strip-frame probe, targeting the `图像 003.fff` over-split while preserving the clean 12-frame results for `图像 001.fff` and `图像 002.fff`.

---

## Step 28 - Regularized OpenCV separator selection
Time: 2026-04-24 16:34 Asia/Shanghai
Status: completed

### Goal
- Fix the `图像 003.fff` OpenCV strip-frame probe over-split where the second strip's `strip2_frame2` through `strip2_frame4` were incorrectly fragmented.

### Completed
- Reinitialized Git after the user removed the broken `.git` directory.
- Created the baseline Git commit `94c15fb Initial NegFlow pipeline`.
- Changed the OpenCV strip-frame probe so it estimates the expected frame count from strip geometry, then selects the most regularly spaced separator subset instead of greedily accepting every row-luminance valley.
- Added a regression test where regular true separator bands must be preferred over irregular internal dark bands.
- Ran the full unit test suite successfully.
- Re-ran `图像 003.fff`; the OpenCV strip-frame probe now reports 12 accepted candidates instead of 13.
- Confirmed `图像 003.fff` second strip now has 6 candidates: `[19-263]`, `[263-512]`, `[512-765]`, `[765-1018]`, `[1018-1273]`, `[1273-1519]` in preview space.
- Re-ran `图像 002.fff`; the OpenCV strip-frame probe remains at 12 accepted candidates.
- Confirmed the current final export still uses the old projection detector, so `图像 003.fff` final PNG count remains 17 until OpenCV-guided boxes are promoted in a later step.

### Files Changed
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/opencv_probe.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 003.fff" --output output --preset neutral_archive
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 002.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 003_20260424T082621Z/05_crop/图像 003_opencv_strip_frame_probe_overlay.png`
- `output/图像 003_20260424T082621Z/05_crop/图像 003_opencv_strip_frame_probe.json`
- `output/图像 002_20260424T083008Z/05_crop/图像 002_opencv_strip_frame_probe_overlay.png`
- `output/图像 002_20260424T083008Z/05_crop/图像 002_opencv_strip_frame_probe.json`

### Problems Found
- The OpenCV strip-frame probe now looks correct for `图像 002.fff` and `图像 003.fff`, but final export still follows the old projection detector.
- `图像 003.fff` final PNG output remains 17 until the OpenCV-guided detector is promoted.
- The temporary `output/git_acl.txt` file from the earlier Git-permission investigation could not be removed due to Windows permissions, but it is under ignored `output/`.

### Suspected Causes
- The previous greedy row-valley splitter accepted internal subject shadows before later, better-spaced separator bands.
- Selecting a regular separator subset better matches the physical spacing of frames in a strip.

### Temporary Decisions / Workarounds
- Keep the OpenCV strip-frame probe compare-only in this step.
- Use Git commits from this point onward to anchor changes.

### README Check
- no change needed

### Remaining Work
- Promote the OpenCV strip-frame detector into the actual crop/export path, with the old projection detector kept as fallback.
- Re-run `图像 001.fff`, `图像 002.fff`, and `图像 003.fff` after promotion to confirm final PNG counts and crop overlays.

### Recommended Next Step
- Replace the default preview detector boxes with OpenCV strip-frame boxes when the OpenCV probe returns plausible results; keep the current projection detector as fallback.

---

## Step 29 - Promote OpenCV crop selection
Time: 2026-04-24 17:13 Asia/Shanghai
Status: completed

### Goal
- Use the OpenCV strip-frame detector for actual crop/refine/export when its result is plausible, while keeping the older projection detector as fallback.

### Completed
- Added an `active_frame_boundary` selection artifact that records which detector drives downstream output.
- Wired source-resolution separator refinement, crop review, preview crops, draft frames, grading, and final PNG export to the selected active boxes.
- Kept the old projection detector output as a separate review/fallback artifact.
- Added plausibility checks for OpenCV boxes: non-empty frames, valid boxes, no short-frame flags, accepted strip details, and matching estimated/actual strip frame counts.
- Added tests for choosing plausible OpenCV boxes and falling back on implausible OpenCV boxes.
- Re-ran `图像 003.fff`; the old projection detector still reports 17 boxes, but active selection uses 12 OpenCV boxes and final PNG export now contains 12 files.
- Re-ran `图像 002.fff`; projection, OpenCV active selection, and final PNG export all remain at 12 files.
- Visually checked the active overlays and contact sheets for `图像 002.fff` and `图像 003.fff`; the previously bad `图像 003` second-strip frames now appear as continuous, regular frame crops.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/runner.py`
- `src/negflow/pipeline/crop.py`
- `src/negflow/pipeline/opencv_probe.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 003.fff" --output output --preset neutral_archive
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 002.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 003_20260424T090427Z/05_crop/图像 003_active_frame_boxes_overlay.png`
- `output/图像 003_20260424T090427Z/05_crop/图像 003_frame_contact_sheet.png`
- `output/图像 003_20260424T090427Z/07_final/final_png/`
- `output/图像 002_20260424T090816Z/05_crop/图像 002_active_frame_boxes_overlay.png`
- `output/图像 002_20260424T090816Z/05_crop/图像 002_frame_contact_sheet.png`
- `output/图像 002_20260424T090816Z/07_final/final_png/`

### Problems Found
- The earlier crop error was caused by image-internal dark bands / subject edges being interpreted as separator valleys, especially in `图像 003` strip 2.
- The new active selection greatly reduces that specific failure, but it cannot fully guarantee perfect crops for every unusual scan.
- The current fallback rule is conservative and should be validated on `图像 001.fff` and more real rolls.

### Suspected Causes
- A global or greedy row-projection splitter cannot always distinguish a real film-frame gap from high-contrast content such as trees, cars, building edges, or dark scan bands.
- OpenCV component ROIs plus regular separator spacing better match the physical roll layout, which is why `图像 003` now stays at 6 frames per strip.

### Temporary Decisions / Workarounds
- Prefer plausible OpenCV strip-frame boxes for downstream export.
- Keep projection boxes as visible fallback/review artifacts instead of deleting the old detector.
- Continue requiring visual overlay/contact-sheet review for real rolls.

### README Check
- updated

### Remaining Work
- Validate the active crop selector on `图像 001.fff` and additional complete rolls.
- Tune fallback rules for partial rolls and highly damaged / unusually spaced scans.
- Continue color tuning after crop behavior is stable.

### Recommended Next Step
- Run the active crop/export path on `图像 001.fff`, then decide whether to tune crop fallback rules further or move back to color improvement.

---

## Step 30 - Validate active crop on image 001
Time: 2026-04-24 18:14 Asia/Shanghai
Status: completed

### Goal
- Run the promoted OpenCV active crop/export path on `图像 001.fff` as a third complete-roll regression sample.

### Completed
- Re-ran `图像 001.fff` through the full `.fff -> active crop -> final PNG` pipeline.
- Confirmed active selection used `opencv_strip_frame_probe`.
- Confirmed the projection detector, OpenCV active selection, and final PNG export all report 12 frames.
- Visually reviewed the active frame overlay and crop contact sheet; no obvious internal-texture over-split like the earlier `图像 003` failure was visible.
- Re-ran the full unit test suite successfully.

### Files Changed
- `STATUS.md`
- `status.json`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 001.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

### Outputs To Inspect
- `output/图像 001_20260424T100940Z/05_crop/图像 001_active_frame_boxes_overlay.png`
- `output/图像 001_20260424T100940Z/05_crop/图像 001_frame_contact_sheet.png`
- `output/图像 001_20260424T100940Z/07_final/final_png/`
- `output/图像 001_20260424T100940Z/07_final/图像 001_sidecar.json`

### Problems Found
- No new crop-selection failure was found on `图像 001.fff`.
- Terminal display still shows mojibake for some Chinese paths in command output, but generated filesystem paths and artifacts are usable.

### Suspected Causes
- `图像 001.fff` has clear strip geometry and the OpenCV ROI plus regular separator selection matches the expected 6 frames per strip.

### Temporary Decisions / Workarounds
- Treat `图像 001.fff`, `图像 002.fff`, and `图像 003.fff` as passing the current active crop detector.
- Keep `图像 004.fff` out of the primary complete-roll validation set because it has only one frame.

### README Check
- no change needed

### Remaining Work
- Tune crop fallback only if a new real roll exposes a failure.
- Move back to color improvement now that the active crop path is stable on the three complete sample rolls.

### Recommended Next Step
- Start a small color-quality step: compare the latest final PNG contact sheets for `图像 001.fff`, `图像 002.fff`, and `图像 003.fff`, then tune only one color parameter or grading rule if a consistent cast/problem is visible.

---

## Step 31 - Color quality review
Time: 2026-04-27 10:56 Asia/Shanghai
Status: completed

### Goal
- Compare the latest final PNG outputs for `图像 001.fff`, `图像 002.fff`, and `图像 003.fff` before changing any color algorithm.

### Completed
- Reviewed the latest graded contact sheets for the three complete sample rolls.
- Confirmed each latest run still has 12 final PNG files.
- Wrote a color statistics review artifact using central final-PNG pixels while avoiding black borders where possible.
- Validated the generated color review JSON.
- Found that a single global warm-up is not the safest first color change: `图像 001` is visibly and statistically cool/cyan, `图像 002` is near neutral, and `图像 003` is slightly warm on average.
- Found the more consistent issue across the sample set is conservative color: low saturation / muted chroma and a slightly gray look, especially on `图像 002` and `图像 003`.

### Files Changed
- `STATUS.md`
- `status.json`

### Run Command
```bash
@'<inline color statistics script>'@ | python -
```

### Test Command
```bash
python -m json.tool output\color_review_20260427T000000Z\color_quality_review.json
```

### Outputs To Inspect
- `output/color_review_20260427T000000Z/color_quality_review.json`
- `output/图像 001_20260424T100940Z/04_base_grade/图像 001_graded_contact_sheet.png`
- `output/图像 002_20260424T090816Z/04_base_grade/图像 002_graded_contact_sheet.png`
- `output/图像 003_20260424T090427Z/04_base_grade/图像 003_graded_contact_sheet.png`

### Problems Found
- `图像 001` average neutral RGB is approximately `[125.24, 133.85, 137.08]`, with R-B around `-11.84`, matching the visible cool/cyan cast.
- `图像 002` average neutral RGB is approximately `[129.31, 129.21, 128.90]`, so it is not asking for a broad warm correction.
- `图像 003` average neutral RGB is approximately `[127.22, 125.94, 124.80]`, slightly warm rather than cool.
- Average chroma is low on `图像 002` and `图像 003`, and the contact sheets look muted / gray.

### Suspected Causes
- The current roll-level base normalization and per-frame neutral balance are doing useful cast control but are intentionally conservative.
- The current grade has no explicit saturation or local contrast shaping after neutral balance, so overcast winter scenes can look flatter than expected.

### Temporary Decisions / Workarounds
- Do not start Step 32 with a simple global warm bias increase.
- Prefer one small saturation/chroma or tone-contrast adjustment, then validate against all three complete rolls.

### README Check
- no change needed

### Remaining Work
- Implement one small color tweak and rerun the three complete rolls.
- Keep an eye on `图像 001`, because it may still need a separate cooler-roll correction after the more general muted-color issue is addressed.

### Recommended Next Step
- Add a conservative post-balance saturation/chroma boost in the source TIFF grading path, then rerun `图像 001.fff`, `图像 002.fff`, and `图像 003.fff` to compare contact sheets and stats.

---

## Step 32 - Color calibration logic review
Time: 2026-04-27 11:05 Asia/Shanghai
Status: completed

### Goal
- Evaluate whether film-edge black/white reference areas should drive color calibration, and define the next color-calibration logic before changing grading code.

### Completed
- Re-read the current grading implementation.
- Confirmed the current pipeline already uses crop padding / margin pixels, but only as mixed percentile samples: 94th percentile for film base and 2nd percentile for black reference.
- Generated a dedicated calibration diagnostic from `图像 001.fff`, `图像 002.fff`, and `图像 003.fff`.
- Sampled source-resolution pixels outside each active frame box but inside padded crop boxes.
- Compared the current roll model against classified edge candidates.
- Wrote a calibration review JSON artifact and a reference swatch image.
- Confirmed the user's film-edge calibration idea is directionally correct, but it needs explicit reference classification.

### Files Changed
- `STATUS.md`
- `status.json`

### Run Command
```bash
@'<inline color calibration reference diagnostic script>'@ | python -
```

### Test Command
```bash
python -m json.tool output\color_calibration_logic_review_20260427T000000Z\color_calibration_logic_review.json
```

### Outputs To Inspect
- `output/color_calibration_logic_review_20260427T000000Z/color_calibration_logic_review.json`
- `output/color_calibration_logic_review_20260427T000000Z/reference_swatches.png`

### Problems Found
- Current `film_base_rgb` is close to the classified clear-film-base candidate, so the margin-based film-base idea is valid.
- Current `black_reference_rgb` is effectively a very dark scanner / border value around `0.046` in all channels; it is stable, but it should not be treated as a complete white-point solution.
- Margin samples mix multiple physical things: clear orange film base, dense black edge / scanner darkness, possible scanner background, and occasional scene leakage from padded crop regions.
- The current model does not explicitly classify those reference types before calibration.

### Suspected Causes
- The existing percentile method was intentionally simple and robust enough for early output, but it collapses physically different references into two numbers.
- Clear color-negative film base should anchor the positive black point after inversion; it is not a positive white reference.
- Positive white / highlight density should be estimated from robust in-frame bright-content statistics, not from the clear film border alone.

### Temporary Decisions / Workarounds
- Adopt a two-stage color-calibration model for the next implementation step:
  1. Use active crop boxes to sample candidate film-edge references outside frames.
  2. Classify high-transmission orange clear-base pixels separately from dark edge / scanner pixels.
  3. Use classified clear film base as the per-roll inversion/base-removal anchor.
  4. Use robust in-frame high-density / highlight statistics for the positive white scale.
  5. Apply guarded per-frame neutral balance only after base inversion and tone mapping.
  6. Add conservative chroma shaping after neutral balance, not before.
- Do not use a simple global warm bias as the primary fix.

### README Check
- no change needed

### Remaining Work
- Implement the classified film-edge calibration model in `grade_basic.py`.
- Add unit coverage for reference classification and fallback behavior.
- Rerun `图像 001.fff`, `图像 002.fff`, and `图像 003.fff` and compare color stats/contact sheets.

### Recommended Next Step
- Replace the current mixed-margin percentile color model with explicit film-edge reference classification, keeping the old percentile behavior as fallback when classification is weak.

---

## Step 33 - Classified film-edge color model
Time: 2026-04-27 14:26 Asia/Shanghai
Status: completed

### Goal
- Replace the mixed-margin percentile color model with explicit film-edge reference classification while keeping conservative fallback behavior.

### Completed
- Updated `grade_basic.py` to classify margin samples into clear film-base and dark-margin references.
- Added roll metadata for `reference_classification`, `density_reference`, `density_reference_rgb`, and `dark_margin_reference_rgb`.
- Changed the source TIFF grading path to use the classified clear film base plus an in-frame low-percentile density reference.
- Kept the old percentile estimates in metadata as fallback/reference fields.
- Added unit coverage for clear film-base and dark-margin classification.
- Updated the smoke test expectation for the new roll color model method.
- Updated README color-method wording.
- Re-ran `图像 001.fff`, `图像 002.fff`, and `图像 003.fff`; all produced 12 final PNG files.
- Generated a before/after color model review JSON.
- Re-ran the full unit test suite successfully.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`
- `src/negflow/pipeline/grade_basic.py`
- `tests/test_runner.py`

### Run Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 001.fff" --output output --preset neutral_archive
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 002.fff" --output output --preset neutral_archive
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m negflow process "data\fff\图像 003.fff" --output output --preset neutral_archive
```

### Test Command
```bash
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m json.tool output\color_model_review_20260427T000000Z\classified_color_model_review.json
```

### Outputs To Inspect
- `output/图像 001_20260427T060516Z/04_base_grade/图像 001_graded_contact_sheet.png`
- `output/图像 002_20260427T061233Z/04_base_grade/图像 002_graded_contact_sheet.png`
- `output/图像 003_20260427T061702Z/04_base_grade/图像 003_graded_contact_sheet.png`
- `output/color_model_review_20260427T000000Z/classified_color_model_review.json`

### Problems Found
- The new model is deliberately conservative; visual change is small.
- `图像 001` still has a noticeable cool/cyan tendency after the structural calibration improvement.
- The classified model slightly raises median luminance across the three complete rolls, but it does not solve muted saturation by itself.

### Suspected Causes
- The previous edge percentile model already estimated film base reasonably well, so explicit classification mostly improves model correctness and traceability rather than making a dramatic visual shift.
- The remaining muted look likely needs a separate, guarded chroma/saturation step after neutral balance.

### Temporary Decisions / Workarounds
- Keep classified film-edge calibration as the base color logic.
- Do not add saturation/chroma shaping in this same step, so the impact of the calibration model stays isolated.

### README Check
- updated

### Remaining Work
- Add a conservative post-balance chroma boost and validate it separately.
- Investigate whether `图像 001` needs a roll-level cool/cyan correction guard after the general chroma step.

### Recommended Next Step
- Add one small post-balance chroma/saturation shaping step, then rerun the three complete rolls and compare against the Step 33 outputs.

---

## Step 34 - Documentation refresh before GitHub push
Time: 2026-04-27 14:46 Asia/Shanghai
Status: completed

### Goal
- Refresh project documentation before publishing the latest classified film-edge color model work to GitHub.

### Completed
- Updated README wording so the next color step is explicitly framed as controlled contrast / midtone separation.
- Kept the implementation unchanged in this step.
- Confirmed the working tree was clean before the documentation refresh.

### Files Changed
- `README.md`
- `STATUS.md`
- `status.json`

### Run Command
```bash
git status --short
```

### Test Command
```bash
python -m json.tool status.json
```

### Outputs To Inspect
- `README.md`
- `STATUS.md`
- `status.json`

### Problems Found
- No code problem was found in this documentation-only step.
- The latest local branch contains new commits beyond the previously pushed `origin/codex/active-crop-validation` branch.

### Suspected Causes
- Step 31 through Step 33 were committed locally after the previous GitHub push.

### Temporary Decisions / Workarounds
- Push the existing `main` HEAD to the safe GitHub branch `codex/active-crop-validation`, rather than pushing to remote `main`, because remote `main` has a separate history.

### README Check
- updated

### Remaining Work
- Push the branch to GitHub.
- Start a separate contrast-tuning step after the push.

### Recommended Next Step
- Use a guarded S-curve / midtone contrast adjustment with highlight and shadow protection, then rerun the three complete rolls and compare contact sheets.
