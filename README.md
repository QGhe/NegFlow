# NegFlow

NegFlow is a command-line workflow for turning Hasselblad Flextight X5 negative scans into traceable PNG outputs.

Current scope: the project has a minimal Python CLI scaffold that validates TIFF input, reads lightweight TIFF metadata, creates a standardized task directory, records a work-TIFF artifact, writes diagnostic downsampled direct and corrected inversion previews, writes a coarse frame-boundary overlay with near-black, wide-strip, and low-detail-tail crop guards, writes OpenCV crop probes with mask / connected-component / strip-frame overlay artifacts, refines frame-to-frame crop boundaries with source-resolution separator sampling, writes a crop-refinement review overlay, creates padded low-resolution per-frame crop previews, exports full-resolution draft frames, applies roll-level film-base-normalized grading with a mild warm-neutral bias, promotes those graded frames into a final PNG export folder, writes a log file, and records a sidecar JSON. It now also supports `.fff` files that are directly TIFF-compatible, plus a configurable external `.fff` converter command for files that require separate conversion. The default config removes large draft and graded per-frame intermediate PNG directories after final export while keeping metadata, contact sheets, and final PNGs. More color tuning and broader real-roll validation are the next likely steps.

## Current methods

The current pipeline uses these main methods:

- Intake and work-TIFF setup:
  validate input type, inspect TIFF metadata with `tifffile`, and create either a hard-linked work TIFF, a source reference, a direct TIFF-compatible `.fff` reference, or a converted TIFF from an external `.fff` converter command.
- Preview inversion and scanner-color correction:
  use `tifffile.memmap` plus strided downsampling to avoid loading the full scan, then build a direct inversion preview and a frame-region gray-world corrected preview.
- Frame detection and crop refinement:
  detect coarse frame boundaries in preview space, reject near-black candidate regions, cap unusually wide strip over-splitting, trim long low-detail blank tails, then refine inter-frame separators in source-resolution TIFF space and write a coarse-vs-refined review overlay.
- OpenCV crop probe:
  write threshold masks, cleaned masks, connected-component candidate boxes, metrics, and an overlay to evaluate a future OpenCV-guided detector without changing final crop export yet.
- OpenCV strip-frame probe:
  treat OpenCV connected components as strip ROIs, reject near-black component interiors, and split accepted strips into frame candidates with row-luminance valleys for compare-only review.
- Full-resolution crop export:
  cut per-frame draft PNGs from the source TIFF with conservative padding so crop misses are easier to inspect.
- Automatic color conversion:
  estimate one roll-level film base from frame margins, apply film-base-normalized inversion, tone-map each frame, and add a mild warm-neutral bias.
- Traceability:
  write manifests, sidecars, logs, contact sheets, and per-stage JSON metadata so every run can be inspected later.
- Output retention:
  keep final PNGs plus review metadata/contact sheets, and optionally remove large intermediate draft and graded per-frame PNG directories after export.

## Implemented features

These parts are working today:

- `python -m negflow process-tiff ...`
- `python -m negflow process ...` for directly TIFF-compatible `.fff` files
- `python -m negflow process ...` with a configurable external `.fff` converter command when direct reading is not possible
- standardized task directory creation
- config snapshot and task logging
- TIFF metadata capture
- work-TIFF artifact tracking
- direct and corrected inversion previews
- coarse frame box detection
- near-black / wide-strip / low-detail-tail crop guards
- OpenCV crop probe artifacts for mask and connected-component review
- OpenCV strip-frame probe artifacts for per-strip frame candidate review
- source-resolution separator crop refinement
- crop refinement review overlay and JSON
- padded frame preview contact sheet
- full-resolution draft frame export
- roll-level automatic base grade
- final PNG export and manifest
- configurable cleanup of draft / graded intermediate frame PNG directories
- smoke tests for TIFF and mock `.fff -> TIFF -> full pipeline` handoff

## Remaining plan

The main remaining work is:

- validate more real Hasselblad / FlexColor `.fff` rolls and choose an external converter command only for `.fff` variants that are not directly TIFF-compatible
- validate the OpenCV strip-frame probe on more real `.fff` rolls, then decide whether it should replace the projection detector
- continue improving color logic without disturbing crop or export behavior
- validate crop behavior on more normal and partial real rolls
- continue reducing disk usage and runtime after validating the new draft / graded intermediate cleanup on more rolls
- later add batch processing once the single-file `.fff` path is proven end to end

## How to run

Install runtime dependencies:

```bash
python -m pip install -e .
```

For environments where editable installs are not desired, install the runtime dependencies directly:

```bash
python -m pip install -r requirements.txt
```

```bash
python -m negflow process-tiff "data/图像 002.tiff" --output output --preset neutral_archive
```

```bash
python -m negflow process "input/example.fff" --output output --preset neutral_archive
```

The default `backend.mode: tiff_passthrough` can process `.fff` files that are directly readable as TIFF containers by `tifffile`.

For `.fff` files that are not directly TIFF-compatible, configure an external converter command in `configs/default.yaml` or a task-specific config. The command is expanded with these placeholders:

- `{input_path}` and `{output_tiff_path}` for raw paths.
- `{input_path_quoted}` and `{output_tiff_path_quoted}` for shell-quoted Windows-safe paths.
- `{input_stem}` and `{output_tiff_stem}` for filename stems.

Example:

```yaml
backend:
  mode: external_converter
  external_converter_command: '"C:\path\to\converter.exe" {input_path_quoted} {output_tiff_path_quoted}'
```

## Input / output overview

- Input: a single `.tif` or `.tiff` file, a directly TIFF-compatible `.fff` file, or a `.fff` file when an external converter command is configured.
- Output: a task folder under `output/` with raw metadata, a converted or linked work-TIFF artifact, downsampled direct/corrected inversion previews, coarse and source-refined frame-boundary overlays, OpenCV crop-probe mask / cleaned-mask / overlay artifacts, OpenCV strip-frame probe overlay / JSON artifacts, crop candidate rejection metadata, a crop-refinement review overlay and JSON, padded low-resolution frame previews, full-resolution draft frames, film-base-normalized graded frames, `07_final/final_png/` exports, a final PNG manifest, a log, and a sidecar JSON.
- By default, `configs/default.yaml` removes the large per-frame draft and graded PNG directories after final PNG export. The corresponding JSON metadata and contact sheets are retained. Set `output.keep_draft_frames: true` or `output.keep_graded_frames: true` to keep those intermediate frame PNGs.

## Repository structure

```text
src/negflow/      Python package and CLI entry point
tests/            smoke tests
configs/          default configuration
output/           generated local artifacts
data/             sample scans
```

## Notes and limitations

- `.fff` handling first tries the configured backend mode. The default `tiff_passthrough` mode supports `.fff` files that are directly TIFF-compatible; non-compatible `.fff` files still require an external converter command.
- The repository currently validates the `.fff -> TIFF -> full pipeline` handoff through a mock converter smoke test. A real Hasselblad X5/FlexColor converter command still needs to be chosen and tuned in your environment.
- The current final PNGs are promoted from a conservative roll-level film-base-normalized grade with a small warm-neutral bias. Crop boxes include near-black candidate rejection, wide-strip over-split protection, low-detail blank-tail trimming, source-resolution separator refinement, OpenCV diagnostic probes, and a coarse-vs-refined review overlay. The OpenCV probes do not drive final export yet. Color is improved but still not a final color-managed film profile.
- The default output-retention settings favor smaller task folders. Re-run with `output.keep_draft_frames: true` and `output.keep_graded_frames: true` when you need all intermediate per-frame PNG files for debugging.
