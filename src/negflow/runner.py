"""Task setup and validation for the NegFlow CLI."""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .fff_backend import (
    FffBackendUnavailable,
    FffConversionRequest,
    SUPPORTED_FFF_EXTENSIONS,
    convert_fff_to_tiff,
)
from .metadata import inspect_tiff_metadata
from .pipeline.crop import (
    detect_frame_boundaries,
    export_full_resolution_draft_frames,
    refine_frame_boundaries_from_source,
    write_crop_refinement_review,
    write_frame_crop_previews,
)
from .pipeline.final_export import export_final_pngs
from .pipeline.grade_basic import grade_draft_frames
from .pipeline.invert import create_inverted_previews

SUPPORTED_TIFF_EXTENSIONS = {".tif", ".tiff"}
STAGE_DIRECTORIES = (
    "01_raw_meta",
    "02_work_tiff",
    "03_inverted",
    "04_base_grade",
    "05_crop",
    "06_cleanup",
    "07_final",
)


@dataclass(frozen=True)
class ProcessResult:
    task_id: str
    task_dir: Path
    sidecar_path: Path
    log_path: Path


def process_fff(input_path: Path, output_root: Path, config_path: Path, preset: str) -> ProcessResult:
    input_path = input_path.resolve()
    output_root = output_root.resolve()

    _validate_fff_input(input_path)

    timestamp = _task_timestamp()
    task_id = f"{input_path.stem}_{timestamp}"
    task_dir, stage_dirs = _create_task_dirs(output_root, task_id)

    log_path = stage_dirs["07_final"] / f"{input_path.stem}_log.txt"
    logger = _build_logger(log_path)
    logger.info("Starting FFF conversion task")
    logger.info("Input: %s", input_path)

    config_snapshot = stage_dirs["01_raw_meta"] / "config_snapshot.yaml"
    _snapshot_config(config_path, config_snapshot, logger)

    sidecar_path = stage_dirs["07_final"] / f"{input_path.stem}_sidecar.json"
    output_tiff_path = stage_dirs["02_work_tiff"] / f"{input_path.stem}_work.tiff"

    try:
        convert_fff_to_tiff(
            FffConversionRequest(
                input_path=input_path,
                output_tiff_path=output_tiff_path,
                backend_mode="external_converter",
            )
        )
    except FffBackendUnavailable as exc:
        sidecar = {
            "task_id": task_id,
            "input_file": str(input_path),
            "input_size_bytes": input_path.stat().st_size,
            "created_at_utc": timestamp,
            "preset": preset,
            "status": "blocked",
            "implemented_stages": ["input_validation", "task_directory", "fff_backend_boundary", "logging", "sidecar"],
            "pending_stages": ["fff_conversion", "tiff_metadata", "invert", "film_base", "base_grade", "crop", "png_export"],
            "outputs": {
                "task_dir": str(task_dir),
                "intended_work_tiff": str(output_tiff_path),
                "log": str(log_path),
                "sidecar": str(sidecar_path),
            },
            "errors": [str(exc)],
            "warnings": ["No .fff converter backend is configured yet."],
        }
        sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.error("%s", exc)
        logger.info("Blocked sidecar written: %s", sidecar_path)
        _close_logger(logger)
        raise FffBackendUnavailable(str(exc), task_dir=task_dir, sidecar_path=sidecar_path, log_path=log_path) from exc

    _close_logger(logger)
    return ProcessResult(task_id=task_id, task_dir=task_dir, sidecar_path=sidecar_path, log_path=log_path)


def process_tiff(input_path: Path, output_root: Path, config_path: Path, preset: str) -> ProcessResult:
    input_path = input_path.resolve()
    output_root = output_root.resolve()

    _validate_tiff_input(input_path)

    timestamp = _task_timestamp()
    task_id = f"{input_path.stem}_{timestamp}"
    task_dir, stage_dirs = _create_task_dirs(output_root, task_id)

    log_path = stage_dirs["07_final"] / f"{input_path.stem}_log.txt"
    logger = _build_logger(log_path)
    logger.info("Starting TIFF passthrough task")
    logger.info("Input: %s", input_path)

    tiff_metadata = inspect_tiff_metadata(input_path)
    metadata_path = stage_dirs["01_raw_meta"] / f"{input_path.stem}_tiff_metadata.json"
    metadata_path.write_text(json.dumps(tiff_metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("TIFF metadata written: %s", metadata_path)

    config_snapshot = stage_dirs["01_raw_meta"] / "config_snapshot.yaml"
    _snapshot_config(config_path, config_snapshot, logger)

    work_tiff_path = stage_dirs["02_work_tiff"] / f"{input_path.stem}_work{input_path.suffix.lower()}"
    work_tiff_artifact = _materialize_work_tiff(input_path, work_tiff_path)
    logger.info("Work TIFF artifact: %s", work_tiff_artifact)

    inverted_preview_path = stage_dirs["03_inverted"] / f"{input_path.stem}_inverted_preview.png"
    corrected_preview_path = stage_dirs["03_inverted"] / f"{input_path.stem}_corrected_preview.png"
    inverted_metadata_path = stage_dirs["03_inverted"] / f"{input_path.stem}_inverted_preview.json"
    inverted_preview = create_inverted_previews(
        input_path,
        inverted_preview_path,
        corrected_preview_path,
        inverted_metadata_path,
    )
    logger.info("Inverted preview written: %s", inverted_preview_path)
    logger.info("Corrected preview written: %s", corrected_preview_path)

    frame_boxes_path = stage_dirs["05_crop"] / f"{input_path.stem}_frame_boxes.json"
    frame_overlay_path = stage_dirs["05_crop"] / f"{input_path.stem}_frame_boxes_overlay.png"
    frame_boundaries = detect_frame_boundaries(
        corrected_preview_path,
        frame_boxes_path,
        frame_overlay_path,
        stride=int(inverted_preview["stride"]),
    )
    logger.info("Frame boundary preview written: %s", frame_overlay_path)

    refined_frame_boxes_path = stage_dirs["05_crop"] / f"{input_path.stem}_frame_boxes_refined.json"
    refined_frame_overlay_path = stage_dirs["05_crop"] / f"{input_path.stem}_frame_boxes_refined_overlay.png"
    refined_frame_boundaries = refine_frame_boundaries_from_source(
        input_path,
        frame_boundaries,
        refined_frame_boxes_path,
        refined_frame_overlay_path,
        channel_multipliers=inverted_preview["correction"]["channel_multipliers"],
    )
    logger.info("Refined frame boundary preview written: %s", refined_frame_overlay_path)

    crop_review_path = stage_dirs["05_crop"] / f"{input_path.stem}_crop_refinement_review.json"
    crop_review_overlay_path = stage_dirs["05_crop"] / f"{input_path.stem}_crop_refinement_review_overlay.png"
    crop_review = write_crop_refinement_review(
        corrected_preview_path,
        frame_boundaries,
        refined_frame_boundaries,
        crop_review_path,
        crop_review_overlay_path,
    )
    logger.info("Crop refinement review written: %s", crop_review_overlay_path)

    frame_previews_dir = stage_dirs["05_crop"] / "frames_preview"
    frame_contact_sheet_path = stage_dirs["05_crop"] / f"{input_path.stem}_frame_contact_sheet.png"
    frame_previews_path = stage_dirs["05_crop"] / f"{input_path.stem}_frame_previews.json"
    frame_previews = write_frame_crop_previews(
        corrected_preview_path,
        refined_frame_boundaries["boxes"],
        frame_previews_dir,
        frame_contact_sheet_path,
        frame_previews_path,
    )
    logger.info("Frame crop contact sheet written: %s", frame_contact_sheet_path)

    draft_frames_dir = stage_dirs["07_final"] / "draft_frames"
    draft_frames_path = stage_dirs["07_final"] / f"{input_path.stem}_draft_frames.json"
    draft_contact_sheet_path = stage_dirs["07_final"] / f"{input_path.stem}_draft_contact_sheet.png"
    draft_frames = export_full_resolution_draft_frames(
        input_path,
        refined_frame_boundaries["boxes"],
        draft_frames_dir,
        draft_frames_path,
        draft_contact_sheet_path,
        channel_multipliers=inverted_preview["correction"]["channel_multipliers"],
    )
    logger.info("Draft full-resolution frames written: %s", draft_frames_dir)

    graded_frames_dir = stage_dirs["04_base_grade"] / "graded_frames"
    graded_frames_path = stage_dirs["04_base_grade"] / f"{input_path.stem}_graded_frames.json"
    graded_contact_sheet_path = stage_dirs["04_base_grade"] / f"{input_path.stem}_graded_contact_sheet.png"
    graded_frames = grade_draft_frames(
        draft_frames,
        graded_frames_dir,
        graded_frames_path,
        graded_contact_sheet_path,
    )
    logger.info("Graded draft frames written: %s", graded_frames_dir)

    final_png_dir = stage_dirs["07_final"] / "final_png"
    final_png_manifest_path = stage_dirs["07_final"] / f"{input_path.stem}_final_png_manifest.json"
    final_png_export = export_final_pngs(
        graded_frames,
        final_png_dir,
        final_png_manifest_path,
        input_path.stem,
    )
    logger.info("Final PNG export written: %s", final_png_dir)

    warnings = []
    if work_tiff_artifact["link_error"]:
        warnings.append("Work TIFF hard link failed; source reference was recorded instead.")
    warnings.append("Frame crop boxes are acceptable preview estimates but not fully final; revisit crop optimization near project finish.")
    warnings.append("Final PNGs are promoted from the basic per-frame grade; final crop refinement remains pending.")

    sidecar_path = stage_dirs["07_final"] / f"{input_path.stem}_sidecar.json"
    sidecar = {
        "task_id": task_id,
        "input_file": str(input_path),
        "input_size_bytes": input_path.stat().st_size,
        "tiff_metadata": tiff_metadata,
        "created_at_utc": timestamp,
        "preset": preset,
        "status": "completed",
        "implemented_stages": [
            "input_validation",
            "task_directory",
            "tiff_metadata",
            "work_tiff",
            "inverted_preview",
            "corrected_preview",
            "frame_boundary_preview",
            "source_separator_crop_refinement",
            "crop_refinement_review",
            "frame_crop_previews",
            "full_resolution_draft_frames",
            "basic_per_frame_grade",
            "final_png_export",
            "logging",
            "sidecar",
        ],
        "pending_stages": ["fff_backend", "final_crop_refinement"],
        "outputs": {
            "task_dir": str(task_dir),
            "tiff_metadata": str(metadata_path),
            "work_tiff": work_tiff_artifact,
            "inverted_preview": {
                "preview": str(inverted_preview_path),
                "metadata": str(inverted_metadata_path),
                "stride": inverted_preview["stride"],
                "preview_shape": inverted_preview["preview_shape"],
            },
            "corrected_preview": {
                "preview": str(corrected_preview_path),
                "metadata": str(inverted_metadata_path),
                "correction": inverted_preview["correction"],
            },
            "frame_boundary_preview": {
                "metadata": str(frame_boxes_path),
                "overlay": str(frame_overlay_path),
                "box_count": len(frame_boundaries["boxes"]),
            },
            "source_separator_crop_refinement": {
                "metadata": str(refined_frame_boxes_path),
                "overlay": str(refined_frame_overlay_path),
                "box_count": len(refined_frame_boundaries["boxes"]),
                "accepted_adjustment_count": refined_frame_boundaries["source_refinement"]["accepted_adjustment_count"],
            },
            "crop_refinement_review": {
                "metadata": str(crop_review_path),
                "overlay": str(crop_review_overlay_path),
                "frame_count": crop_review["frame_count"],
                "accepted_adjustment_count": crop_review["accepted_adjustment_count"],
                "rejected_adjustment_count": crop_review["rejected_adjustment_count"],
                "max_abs_source_delta": crop_review["max_abs_source_delta"],
            },
            "frame_crop_previews": {
                "metadata": str(frame_previews_path),
                "contact_sheet": str(frame_contact_sheet_path),
                "output_dir": str(frame_previews_dir),
                "frame_count": frame_previews["frame_count"],
                "padding_ratio": frame_previews["padding_ratio"],
            },
            "full_resolution_draft_frames": {
                "metadata": str(draft_frames_path),
                "output_dir": str(draft_frames_dir),
                "contact_sheet": str(draft_contact_sheet_path),
                "frame_count": draft_frames["frame_count"],
                "padding_ratio": draft_frames["padding_ratio"],
            },
            "basic_per_frame_grade": {
                "metadata": str(graded_frames_path),
                "output_dir": str(graded_frames_dir),
                "contact_sheet": str(graded_contact_sheet_path),
                "frame_count": graded_frames["frame_count"],
            },
            "final_png_export": {
                "metadata": str(final_png_manifest_path),
                "output_dir": str(final_png_dir),
                "frame_count": final_png_export["frame_count"],
            },
            "log": str(log_path),
            "sidecar": str(sidecar_path),
        },
        "warnings": warnings,
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Sidecar written: %s", sidecar_path)
    logger.info("Task complete")
    _close_logger(logger)

    return ProcessResult(task_id=task_id, task_dir=task_dir, sidecar_path=sidecar_path, log_path=log_path)


def _validate_tiff_input(input_path: Path) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")
    if input_path.suffix.lower() not in SUPPORTED_TIFF_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_TIFF_EXTENSIONS))
        raise ValueError(f"Unsupported input extension {input_path.suffix!r}; expected one of: {allowed}")


def _validate_fff_input(input_path: Path) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")
    if input_path.suffix.lower() not in SUPPORTED_FFF_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_FFF_EXTENSIONS))
        raise ValueError(f"Unsupported input extension {input_path.suffix!r}; expected one of: {allowed}")


def _task_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _create_task_dirs(output_root: Path, task_id: str) -> tuple[Path, dict[str, Path]]:
    task_dir = output_root / task_id
    stage_dirs = {name: task_dir / name for name in STAGE_DIRECTORIES}
    for directory in stage_dirs.values():
        directory.mkdir(parents=True, exist_ok=False)
    return task_dir, stage_dirs


def _snapshot_config(config_path: Path, config_snapshot: Path, logger: logging.Logger) -> None:
    if config_path.exists():
        shutil.copy2(config_path, config_snapshot)
        logger.info("Config snapshot: %s", config_snapshot)
    else:
        logger.warning("Config file not found: %s", config_path)


def _build_logger(log_path: Path) -> logging.Logger:
    logger_name = f"negflow.{log_path.parent.parent.name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


def _materialize_work_tiff(input_path: Path, work_tiff_path: Path) -> dict[str, str | None]:
    try:
        os.link(input_path, work_tiff_path)
        return {
            "method": "hardlink",
            "path": str(work_tiff_path),
            "reference": None,
            "link_error": None,
        }
    except OSError as exc:
        reference_path = work_tiff_path.with_suffix(work_tiff_path.suffix + ".reference.json")
        reference = {
            "source_tiff": str(input_path),
            "intended_work_tiff": str(work_tiff_path),
            "reason": "Hard link creation failed; keeping a reference instead of copying a large scan.",
            "link_error": f"{type(exc).__name__}: {exc}",
        }
        reference_path.write_text(json.dumps(reference, indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "method": "reference",
            "path": None,
            "reference": str(reference_path),
            "link_error": reference["link_error"],
        }


def _close_logger(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
