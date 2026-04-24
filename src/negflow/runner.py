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
    FffConversionError,
    FffBackendUnavailable,
    FffConversionRequest,
    SUPPORTED_FFF_EXTENSIONS,
    convert_fff_to_tiff,
    load_backend_config,
    load_simple_yaml_mapping,
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
from .pipeline.opencv_probe import write_opencv_crop_probe, write_opencv_strip_frame_probe

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


@dataclass(frozen=True)
class OutputRetentionConfig:
    keep_draft_frames: bool = True
    keep_graded_frames: bool = True


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
    backend_config = load_backend_config(config_path)
    output_retention = load_output_retention_config(config_path)

    try:
        conversion_result = convert_fff_to_tiff(
            FffConversionRequest(
                input_path=input_path,
                output_tiff_path=output_tiff_path,
                backend_mode=backend_config.mode,
                converter_command=backend_config.external_converter_command,
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
            "warnings": [f"No usable .fff converter backend is configured yet (mode={backend_config.mode!r})."],
        }
        sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.error("%s", exc)
        logger.info("Blocked sidecar written: %s", sidecar_path)
        _close_logger(logger)
        raise FffBackendUnavailable(str(exc), task_dir=task_dir, sidecar_path=sidecar_path, log_path=log_path) from exc
    except FffConversionError as exc:
        sidecar = {
            "task_id": task_id,
            "input_file": str(input_path),
            "input_size_bytes": input_path.stat().st_size,
            "created_at_utc": timestamp,
            "preset": preset,
            "status": "failed",
            "implemented_stages": ["input_validation", "task_directory", "fff_backend_boundary", "logging", "sidecar"],
            "pending_stages": ["tiff_metadata", "invert", "film_base", "base_grade", "crop", "png_export"],
            "outputs": {
                "task_dir": str(task_dir),
                "intended_work_tiff": str(output_tiff_path),
                "log": str(log_path),
                "sidecar": str(sidecar_path),
            },
            "errors": [
                {
                    "message": str(exc),
                    "command": exc.command,
                    "returncode": exc.returncode,
                    "stdout": exc.stdout,
                    "stderr": exc.stderr,
                }
            ],
            "warnings": ["The configured external converter ran but did not complete a usable TIFF conversion."],
        }
        sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.error("%s", exc)
        if exc.command:
            logger.error("Converter command: %s", exc.command)
        if exc.stdout:
            logger.info("Converter stdout:\n%s", exc.stdout)
        if exc.stderr:
            logger.warning("Converter stderr:\n%s", exc.stderr)
        logger.info("Failed sidecar written: %s", sidecar_path)
        _close_logger(logger)
        raise FffBackendUnavailable(str(exc), task_dir=task_dir, sidecar_path=sidecar_path, log_path=log_path) from exc

    conversion_metadata_path = stage_dirs["02_work_tiff"] / f"{input_path.stem}_fff_conversion.json"
    conversion_metadata = {
        "backend_mode": conversion_result.backend_mode,
        "conversion_method": conversion_result.conversion_method,
        "command_template": conversion_result.command_template,
        "expanded_command": conversion_result.expanded_command,
        "output_tiff": str(conversion_result.output_tiff_path),
        "returncode": conversion_result.returncode,
        "stdout": conversion_result.stdout,
        "stderr": conversion_result.stderr,
    }
    conversion_metadata_path.write_text(json.dumps(conversion_metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("FFF conversion metadata written: %s", conversion_metadata_path)

    work_tiff_artifact = {
        "method": "converted" if conversion_result.conversion_method == "external_converter" else "tiff_compatible_reference",
        "path": str(conversion_result.output_tiff_path),
        "reference": None,
        "link_error": None,
    }
    return _run_tiff_pipeline_in_task(
        source_input_path=input_path,
        working_tiff_path=conversion_result.output_tiff_path,
        task_id=task_id,
        timestamp=timestamp,
        task_dir=task_dir,
        stage_dirs=stage_dirs,
        log_path=log_path,
        logger=logger,
        preset=preset,
        output_stem=input_path.stem,
        work_tiff_artifact=work_tiff_artifact,
        source_stage_name="fff_conversion",
        source_stage_output={
            "metadata": str(conversion_metadata_path),
            "backend_mode": conversion_result.backend_mode,
            "conversion_method": conversion_result.conversion_method,
            "output_tiff": str(conversion_result.output_tiff_path),
        },
        pending_stages=["final_crop_refinement"],
        warning_overrides=[
            "Frame crop boxes are acceptable preview estimates but not fully final; revisit crop optimization near project finish.",
            "Final PNGs are promoted from the basic per-frame grade; final crop refinement remains pending.",
        ],
        output_retention=output_retention,
    )


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

    config_snapshot = stage_dirs["01_raw_meta"] / "config_snapshot.yaml"
    _snapshot_config(config_path, config_snapshot, logger)
    output_retention = load_output_retention_config(config_path)

    work_tiff_path = stage_dirs["02_work_tiff"] / f"{input_path.stem}_work{input_path.suffix.lower()}"
    work_tiff_artifact = _materialize_work_tiff(input_path, work_tiff_path)
    logger.info("Work TIFF artifact: %s", work_tiff_artifact)
    return _run_tiff_pipeline_in_task(
        source_input_path=input_path,
        working_tiff_path=input_path,
        task_id=task_id,
        timestamp=timestamp,
        task_dir=task_dir,
        stage_dirs=stage_dirs,
        log_path=log_path,
        logger=logger,
        preset=preset,
        output_stem=input_path.stem,
        work_tiff_artifact=work_tiff_artifact,
        source_stage_name=None,
        source_stage_output=None,
        pending_stages=["fff_backend", "final_crop_refinement"],
        warning_overrides=None,
        output_retention=output_retention,
    )


def _run_tiff_pipeline_in_task(
    *,
    source_input_path: Path,
    working_tiff_path: Path,
    task_id: str,
    timestamp: str,
    task_dir: Path,
    stage_dirs: dict[str, Path],
    log_path: Path,
    logger: logging.Logger,
    preset: str,
    output_stem: str,
    work_tiff_artifact: dict[str, str | None],
    source_stage_name: str | None,
    source_stage_output: dict[str, object] | None,
    pending_stages: list[str],
    warning_overrides: list[str] | None,
    output_retention: OutputRetentionConfig,
) -> ProcessResult:
    tiff_metadata = inspect_tiff_metadata(working_tiff_path)
    metadata_path = stage_dirs["01_raw_meta"] / f"{output_stem}_tiff_metadata.json"
    metadata_path.write_text(json.dumps(tiff_metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("TIFF metadata written: %s", metadata_path)

    inverted_preview_path = stage_dirs["03_inverted"] / f"{output_stem}_inverted_preview.png"
    corrected_preview_path = stage_dirs["03_inverted"] / f"{output_stem}_corrected_preview.png"
    inverted_metadata_path = stage_dirs["03_inverted"] / f"{output_stem}_inverted_preview.json"
    inverted_preview = create_inverted_previews(
        working_tiff_path,
        inverted_preview_path,
        corrected_preview_path,
        inverted_metadata_path,
    )
    logger.info("Inverted preview written: %s", inverted_preview_path)
    logger.info("Corrected preview written: %s", corrected_preview_path)

    frame_boxes_path = stage_dirs["05_crop"] / f"{output_stem}_frame_boxes.json"
    frame_overlay_path = stage_dirs["05_crop"] / f"{output_stem}_frame_boxes_overlay.png"
    frame_boundaries = detect_frame_boundaries(
        corrected_preview_path,
        frame_boxes_path,
        frame_overlay_path,
        stride=int(inverted_preview["stride"]),
    )
    logger.info("Frame boundary preview written: %s", frame_overlay_path)

    opencv_probe_path = stage_dirs["05_crop"] / f"{output_stem}_opencv_crop_probe.json"
    opencv_probe_mask_path = stage_dirs["05_crop"] / f"{output_stem}_opencv_crop_probe_mask.png"
    opencv_probe_cleaned_mask_path = stage_dirs["05_crop"] / f"{output_stem}_opencv_crop_probe_cleaned_mask.png"
    opencv_probe_overlay_path = stage_dirs["05_crop"] / f"{output_stem}_opencv_crop_probe_overlay.png"
    opencv_crop_probe = write_opencv_crop_probe(
        corrected_preview_path,
        opencv_probe_path,
        opencv_probe_mask_path,
        opencv_probe_cleaned_mask_path,
        opencv_probe_overlay_path,
        stride=int(inverted_preview["stride"]),
    )
    logger.info("OpenCV crop probe written: %s", opencv_probe_overlay_path)

    opencv_strip_frame_probe_path = stage_dirs["05_crop"] / f"{output_stem}_opencv_strip_frame_probe.json"
    opencv_strip_frame_probe_overlay_path = stage_dirs["05_crop"] / f"{output_stem}_opencv_strip_frame_probe_overlay.png"
    opencv_strip_frame_probe = write_opencv_strip_frame_probe(
        corrected_preview_path,
        opencv_crop_probe,
        opencv_strip_frame_probe_path,
        opencv_strip_frame_probe_overlay_path,
        stride=int(inverted_preview["stride"]),
    )
    logger.info("OpenCV strip frame probe written: %s", opencv_strip_frame_probe_overlay_path)

    refined_frame_boxes_path = stage_dirs["05_crop"] / f"{output_stem}_frame_boxes_refined.json"
    refined_frame_overlay_path = stage_dirs["05_crop"] / f"{output_stem}_frame_boxes_refined_overlay.png"
    refined_frame_boundaries = refine_frame_boundaries_from_source(
        working_tiff_path,
        frame_boundaries,
        refined_frame_boxes_path,
        refined_frame_overlay_path,
        channel_multipliers=inverted_preview["correction"]["channel_multipliers"],
    )
    logger.info("Refined frame boundary preview written: %s", refined_frame_overlay_path)

    crop_review_path = stage_dirs["05_crop"] / f"{output_stem}_crop_refinement_review.json"
    crop_review_overlay_path = stage_dirs["05_crop"] / f"{output_stem}_crop_refinement_review_overlay.png"
    crop_review = write_crop_refinement_review(
        corrected_preview_path,
        frame_boundaries,
        refined_frame_boundaries,
        crop_review_path,
        crop_review_overlay_path,
    )
    logger.info("Crop refinement review written: %s", crop_review_overlay_path)

    frame_previews_dir = stage_dirs["05_crop"] / "frames_preview"
    frame_contact_sheet_path = stage_dirs["05_crop"] / f"{output_stem}_frame_contact_sheet.png"
    frame_previews_path = stage_dirs["05_crop"] / f"{output_stem}_frame_previews.json"
    frame_previews = write_frame_crop_previews(
        corrected_preview_path,
        refined_frame_boundaries["boxes"],
        frame_previews_dir,
        frame_contact_sheet_path,
        frame_previews_path,
    )
    logger.info("Frame crop contact sheet written: %s", frame_contact_sheet_path)

    draft_frames_dir = stage_dirs["07_final"] / "draft_frames"
    draft_frames_path = stage_dirs["07_final"] / f"{output_stem}_draft_frames.json"
    draft_contact_sheet_path = stage_dirs["07_final"] / f"{output_stem}_draft_contact_sheet.png"
    draft_frames = export_full_resolution_draft_frames(
        working_tiff_path,
        refined_frame_boundaries["boxes"],
        draft_frames_dir,
        draft_frames_path,
        draft_contact_sheet_path,
        channel_multipliers=inverted_preview["correction"]["channel_multipliers"],
    )
    logger.info("Draft full-resolution frames written: %s", draft_frames_dir)

    graded_frames_dir = stage_dirs["04_base_grade"] / "graded_frames"
    graded_frames_path = stage_dirs["04_base_grade"] / f"{output_stem}_graded_frames.json"
    graded_contact_sheet_path = stage_dirs["04_base_grade"] / f"{output_stem}_graded_contact_sheet.png"
    graded_frames = grade_draft_frames(
        draft_frames,
        graded_frames_dir,
        graded_frames_path,
        graded_contact_sheet_path,
    )
    logger.info("Graded draft frames written: %s", graded_frames_dir)

    final_png_dir = stage_dirs["07_final"] / "final_png"
    final_png_manifest_path = stage_dirs["07_final"] / f"{output_stem}_final_png_manifest.json"
    final_png_export = export_final_pngs(
        graded_frames,
        final_png_dir,
        final_png_manifest_path,
        output_stem,
    )
    logger.info("Final PNG export written: %s", final_png_dir)

    retention_cleanup = _apply_output_retention(
        task_dir=task_dir,
        stage_dir=stage_dirs["06_cleanup"],
        draft_frames_dir=draft_frames_dir,
        graded_frames_dir=graded_frames_dir,
        output_retention=output_retention,
        output_stem=output_stem,
        logger=logger,
    )

    warnings = list(warning_overrides or [])
    if not warnings:
        if work_tiff_artifact["link_error"]:
            warnings.append("Work TIFF hard link failed; source reference was recorded instead.")
        warnings.append("Frame crop boxes are acceptable preview estimates but not fully final; revisit crop optimization near project finish.")
        warnings.append("Final PNGs are promoted from the basic per-frame grade; final crop refinement remains pending.")

    sidecar_path = stage_dirs["07_final"] / f"{output_stem}_sidecar.json"
    implemented_stages = [
        "input_validation",
        "task_directory",
        "tiff_metadata",
        "work_tiff",
        "inverted_preview",
        "corrected_preview",
        "frame_boundary_preview",
        "opencv_crop_probe",
        "opencv_strip_frame_probe",
        "source_separator_crop_refinement",
        "crop_refinement_review",
        "frame_crop_previews",
        "full_resolution_draft_frames",
        "basic_per_frame_grade",
        "final_png_export",
        "logging",
        "sidecar",
    ]
    outputs = {
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
        "opencv_crop_probe": {
            "metadata": str(opencv_probe_path),
            "mask": str(opencv_probe_mask_path),
            "cleaned_mask": str(opencv_probe_cleaned_mask_path),
            "overlay": str(opencv_probe_overlay_path),
            "candidate_count": opencv_crop_probe["candidate_count"],
        },
        "opencv_strip_frame_probe": {
            "metadata": str(opencv_strip_frame_probe_path),
            "overlay": str(opencv_strip_frame_probe_overlay_path),
            "accepted_frame_count": opencv_strip_frame_probe["accepted_frame_count"],
            "rejected_component_count": opencv_strip_frame_probe["rejected_component_count"],
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
            "retained": output_retention.keep_draft_frames,
        },
        "basic_per_frame_grade": {
            "metadata": str(graded_frames_path),
            "output_dir": str(graded_frames_dir),
            "contact_sheet": str(graded_contact_sheet_path),
            "frame_count": graded_frames["frame_count"],
            "retained": output_retention.keep_graded_frames,
        },
        "final_png_export": {
            "metadata": str(final_png_manifest_path),
            "output_dir": str(final_png_dir),
            "frame_count": final_png_export["frame_count"],
        },
        "log": str(log_path),
        "sidecar": str(sidecar_path),
        "output_retention": retention_cleanup,
    }
    if source_stage_name and source_stage_output:
        implemented_stages.insert(2, source_stage_name)
        outputs[source_stage_name] = source_stage_output

    sidecar = {
        "task_id": task_id,
        "input_file": str(source_input_path),
        "input_size_bytes": source_input_path.stat().st_size,
        "tiff_metadata": tiff_metadata,
        "created_at_utc": timestamp,
        "preset": preset,
        "status": "completed",
        "implemented_stages": implemented_stages,
        "pending_stages": pending_stages,
        "outputs": outputs,
        "warnings": warnings,
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Sidecar written: %s", sidecar_path)
    logger.info("Task complete")
    _close_logger(logger)

    return ProcessResult(task_id=task_id, task_dir=task_dir, sidecar_path=sidecar_path, log_path=log_path)


def load_output_retention_config(config_path: Path) -> OutputRetentionConfig:
    if not config_path.exists():
        return OutputRetentionConfig()
    config_data = load_simple_yaml_mapping(config_path)
    output_data = config_data.get("output")
    if not isinstance(output_data, dict):
        return OutputRetentionConfig()
    return OutputRetentionConfig(
        keep_draft_frames=_parse_bool(output_data.get("keep_draft_frames"), default=True),
        keep_graded_frames=_parse_bool(output_data.get("keep_graded_frames"), default=True),
    )


def _parse_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
    return bool(value)


def _apply_output_retention(
    *,
    task_dir: Path,
    stage_dir: Path,
    draft_frames_dir: Path,
    graded_frames_dir: Path,
    output_retention: OutputRetentionConfig,
    output_stem: str,
    logger: logging.Logger,
) -> dict[str, object]:
    stage_dir.mkdir(parents=True, exist_ok=True)
    cleanup_items = []

    if not output_retention.keep_draft_frames:
        cleanup_items.append(_remove_output_dir(task_dir, draft_frames_dir, "full_resolution_draft_frame_pngs"))
    if not output_retention.keep_graded_frames:
        cleanup_items.append(_remove_output_dir(task_dir, graded_frames_dir, "graded_frame_pngs"))

    result = {
        "stage": "output_retention",
        "metadata": str(stage_dir / f"{output_stem}_output_retention.json"),
        "keep_draft_frames": output_retention.keep_draft_frames,
        "keep_graded_frames": output_retention.keep_graded_frames,
        "cleanup_items": cleanup_items,
        "notes": [
            "Only per-frame intermediate PNG directories are removed.",
            "JSON metadata, contact sheets, logs, sidecars, and final PNG exports are retained.",
        ],
    }
    Path(result["metadata"]).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Output retention metadata written: %s", result["metadata"])
    return result


def _remove_output_dir(task_dir: Path, directory: Path, label: str) -> dict[str, object]:
    task_root = task_dir.resolve()
    target = directory.resolve()
    if target != task_root and task_root not in target.parents:
        return {
            "label": label,
            "path": str(directory),
            "removed": False,
            "reason": "target_outside_task_dir",
        }
    if not target.exists():
        return {
            "label": label,
            "path": str(directory),
            "removed": False,
            "reason": "not_found",
        }
    file_count = sum(1 for item in target.rglob("*") if item.is_file())
    shutil.rmtree(target)
    return {
        "label": label,
        "path": str(directory),
        "removed": True,
        "file_count": file_count,
    }


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
