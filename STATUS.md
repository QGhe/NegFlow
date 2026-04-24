# Development Status

## Project Summary
- Current focus: Wire the `.fff` entry path into the existing TIFF pipeline through a configurable external converter, while keeping the current crop and color behavior stable.
- Current overall status: TIFF intake, external `.fff` converter handoff, project hygiene, inversion previews, constrained frame boxes, source-resolution separator crop refinement, crop-refinement review overlays, padded previews, full-resolution draft PNGs, roll-level film-base-normalized grade, and final PNG export are implemented.
- Main goal: Create a repeatable Hasselblad X5 negative scan pipeline from TIFF / future `.fff` input to traceable PNG output.

## Current Methods Snapshot
- Intake / work TIFF:
  `tifffile` metadata inspection, hard-link-or-reference work-TIFF handling for TIFF input, and configurable external converter command handoff for `.fff`.
- Preview image processing:
  memory-conscious `tifffile.memmap` downsampling, direct negative inversion preview, and frame-region gray-world corrected preview.
- Frame splitting and crop review:
  preview-space frame detection, source-resolution separator refinement, and coarse-vs-refined crop review overlay output.
- Per-frame export and grading:
  padded full-resolution draft PNG export, roll-level film-base-normalized inversion, per-frame tone mapping, and mild warm-neutral bias.
- Traceability:
  per-stage JSON metadata, contact sheets, logs, sidecars, and final PNG manifests.

## Current Completed Functionality
- `process-tiff` end-to-end run from TIFF input to final PNG folder
- `.fff` external converter handoff into the TIFF pipeline
- inversion preview artifacts
- crop refinement artifacts and review outputs
- full-resolution draft frame export
- automatic roll-level base grade
- final PNG export
- smoke tests for TIFF and mock `.fff` processing

## Current Remaining Plan
- choose and test a real Hasselblad / FlexColor `.fff` converter command on this machine
- continue improving color accuracy while leaving crop/export behavior stable
- revisit final crop accuracy near project wrap-up
- consider configurable retention for draft / graded / final image sets
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
