# NegFlow

NegFlow is a command-line workflow for turning Hasselblad Flextight X5 negative scans into traceable PNG outputs.

Current scope: the project has a minimal Python CLI scaffold that validates TIFF input, reads lightweight TIFF metadata, creates a standardized task directory, records a work-TIFF artifact, writes diagnostic downsampled direct and corrected inversion previews, writes a coarse frame-boundary overlay, creates padded low-resolution per-frame crop previews, exports full-resolution draft frames, applies a basic per-frame grade, promotes those graded frames into a final PNG export folder, writes a log file, and records a sidecar JSON. It also has a `.fff` backend boundary that records a blocked task when no external converter is configured. Final crop refinement and actual `.fff` conversion are planned next steps.

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

## Input / output overview

- Input: a single `.tif` or `.tiff` file for the current development path, or a `.fff` file for backend-boundary validation.
- Output: a task folder under `output/` with raw metadata, a work-TIFF hard link or source reference, downsampled direct/corrected inversion previews, a coarse frame-boundary overlay, padded low-resolution frame previews, full-resolution draft frames, graded frames, `07_final/final_png/` exports, a final PNG manifest, a log, and a sidecar JSON.

## Repository structure

```text
src/negflow/      Python package and CLI entry point
tests/            smoke tests
configs/          default configuration
output/           generated local artifacts
data/             sample scans
```

## Notes and limitations

- `.fff` conversion is intentionally not implemented yet; the current `process` command records a blocked task with a sidecar and log.
- The current final PNGs are promoted from the basic per-frame grade. Crop boxes are acceptable draft estimates, but final crop refinement is still a known follow-up before considering the pipeline complete.
