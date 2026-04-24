# NegFlow

NegFlow is a command-line workflow for turning Hasselblad Flextight X5 negative scans into traceable PNG outputs.

Current scope: the project has a minimal Python CLI scaffold that validates TIFF input, reads lightweight TIFF metadata, creates a standardized task directory, records a work-TIFF artifact, writes diagnostic downsampled direct and corrected inversion previews, writes a coarse frame-boundary overlay, refines frame-to-frame crop boundaries with source-resolution separator sampling, writes a crop-refinement review overlay, creates padded low-resolution per-frame crop previews, exports full-resolution draft frames, applies roll-level film-base-normalized grading with a mild warm-neutral bias, promotes those graded frames into a final PNG export folder, writes a log file, and records a sidecar JSON. It now also supports a configurable external `.fff` converter command that writes a work TIFF and then continues through the existing TIFF pipeline. More color tuning and real converter integration are the next likely steps.

## Current methods

The current pipeline uses these main methods:

- Intake and work-TIFF setup:
  validate input type, inspect TIFF metadata with `tifffile`, and create either a hard-linked work TIFF, a source reference, or a converted TIFF from an external `.fff` converter command.
- Preview inversion and scanner-color correction:
  use `tifffile.memmap` plus strided downsampling to avoid loading the full scan, then build a direct inversion preview and a frame-region gray-world corrected preview.
- Frame detection and crop refinement:
  detect coarse frame boundaries in preview space, then refine inter-frame separators in source-resolution TIFF space and write a coarse-vs-refined review overlay.
- Full-resolution crop export:
  cut per-frame draft PNGs from the source TIFF with conservative padding so crop misses are easier to inspect.
- Automatic color conversion:
  estimate one roll-level film base from frame margins, apply film-base-normalized inversion, tone-map each frame, and add a mild warm-neutral bias.
- Traceability:
  write manifests, sidecars, logs, contact sheets, and per-stage JSON metadata so every run can be inspected later.

## Implemented features

These parts are working today:

- `python -m negflow process-tiff ...`
- `python -m negflow process ...` with a configurable external `.fff` converter command
- standardized task directory creation
- config snapshot and task logging
- TIFF metadata capture
- work-TIFF artifact tracking
- direct and corrected inversion previews
- coarse frame box detection
- source-resolution separator crop refinement
- crop refinement review overlay and JSON
- padded frame preview contact sheet
- full-resolution draft frame export
- roll-level automatic base grade
- final PNG export and manifest
- smoke tests for TIFF and mock `.fff -> TIFF -> full pipeline` handoff

## Remaining plan

The main remaining work is:

- choose and validate a real Hasselblad / FlexColor `.fff` converter command on this machine
- continue improving color logic without disturbing crop or export behavior
- revisit final crop accuracy near project wrap-up
- optionally reduce disk usage and runtime by making draft / graded / final image retention configurable
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

To enable `.fff` processing, configure an external converter command in `configs/default.yaml` or a task-specific config. The command is expanded with these placeholders:

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

- Input: a single `.tif` or `.tiff` file, or a `.fff` file when an external converter command is configured.
- Output: a task folder under `output/` with raw metadata, a converted or linked work-TIFF artifact, downsampled direct/corrected inversion previews, coarse and source-refined frame-boundary overlays, a crop-refinement review overlay and JSON, padded low-resolution frame previews, full-resolution draft frames, film-base-normalized graded frames, `07_final/final_png/` exports, a final PNG manifest, a log, and a sidecar JSON.

## Repository structure

```text
src/negflow/      Python package and CLI entry point
tests/            smoke tests
configs/          default configuration
output/           generated local artifacts
data/             sample scans
```

## Notes and limitations

- `.fff` conversion now depends on an external converter command supplied in config. Without that command, the current `process` path records a blocked task with a sidecar and log.
- The repository currently validates the `.fff -> TIFF -> full pipeline` handoff through a mock converter smoke test. A real Hasselblad X5/FlexColor converter command still needs to be chosen and tuned in your environment.
- The current final PNGs are promoted from a conservative roll-level film-base-normalized grade with a small warm-neutral bias. Crop boxes include source-resolution separator refinement plus a coarse-vs-refined review overlay. Color is improved but still not a final color-managed film profile.
