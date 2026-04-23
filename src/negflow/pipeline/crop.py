"""Preview-space frame boundary detection."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image, ImageDraw


def detect_frame_boundaries(
    preview_path: Path,
    metadata_path: Path,
    overlay_path: Path,
    stride: int,
    min_strip_width: int = 80,
    min_frame_height: int = 120,
) -> dict[str, Any]:
    """Detect coarse frame boxes from a corrected downsampled preview."""
    image = Image.open(preview_path).convert("RGB")
    rgb = np.asarray(image)
    source_luminance = rgb.mean(axis=2)
    luminance, detection_preprocess = _enhance_detection_luminance(source_luminance)
    effective_min_strip_width = min(min_strip_width, max(4, image.width // 10))
    effective_min_frame_height = min(min_frame_height, max(8, image.height // 10))

    strip_mask = luminance.mean(axis=0) < float(np.percentile(luminance, 72.0))
    strip_segments = _segments_from_mask(strip_mask, min_length=effective_min_strip_width)

    boxes = []
    strip_details = []
    for strip_index, (x0, x1) in enumerate(strip_segments, start=1):
        strip_luminance = luminance[:, x0:x1]
        source_strip_luminance = source_luminance[:, x0:x1]
        row_profile = strip_luminance.mean(axis=1)
        content_start, content_end = _content_bounds_from_row_profile(row_profile)
        separator_segments = _separator_segments_from_strip(strip_luminance)
        frame_count = _estimate_frame_count(content_start, content_end, separator_segments, effective_min_frame_height)
        frame_segments = _frames_from_separators(
            content_start,
            content_end,
            separator_segments,
            frame_count=frame_count,
            min_frame_height=effective_min_frame_height,
        )
        strip_details.append(
            {
                "strip_index": strip_index,
                "preview_x": [int(x0), int(x1)],
                "content_y": [int(content_start), int(content_end)],
                "estimated_frame_count": int(frame_count),
                "separator_segments": [[int(y0), int(y1)] for y0, y1 in separator_segments],
            }
        )

        for frame_index, (y0, y1) in enumerate(frame_segments, start=1):
            flags = _box_quality_flags(y0, y1, effective_min_frame_height)
            boxes.append(
                {
                    "id": f"strip{strip_index}_frame{frame_index}",
                    "strip_index": strip_index,
                    "frame_index": frame_index,
                    "preview_box": [int(x0), int(y0), int(x1), int(y1)],
                    "source_box_estimate": [
                        int(x0 * stride),
                        int(y0 * stride),
                        int(x1 * stride),
                        int(y1 * stride),
                    ],
                    "mean_luminance": float(source_strip_luminance[y0:y1].mean()),
                    "detection_mean_luminance": float(strip_luminance[y0:y1].mean()),
                    "height": int(y1 - y0),
                    "confidence": "low" if flags else "medium",
                    "flags": flags,
                }
            )

    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    _write_overlay(image, boxes, overlay_path)

    result = {
        "stage": "frame_boundary_preview",
        "method": "preview_strip_separator_projection",
        "source_preview": str(preview_path),
        "overlay": str(overlay_path),
        "stride": int(stride),
        "preview_size": [int(image.width), int(image.height)],
        "min_strip_width": int(effective_min_strip_width),
        "min_frame_height": int(effective_min_frame_height),
        "detection_preprocess": detection_preprocess,
        "strip_segments": [[int(x0), int(x1)] for x0, x1 in strip_segments],
        "strip_details": strip_details,
        "boxes": boxes,
        "notes": [
            "Coarse preview-space detection only.",
            "Boxes are not final crops and have not been validated against full-resolution pixels.",
        ],
    }
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def write_frame_crop_previews(
    preview_path: Path,
    boxes: list[dict[str, Any]],
    output_dir: Path,
    contact_sheet_path: Path,
    metadata_path: Path,
    padding_ratio: float = 0.08,
) -> dict[str, Any]:
    """Write padded preview-space crops for visual review."""
    image = Image.open(preview_path).convert("RGB")
    output_dir.mkdir(parents=True, exist_ok=True)

    frame_outputs = []
    crop_images = []
    for box in boxes:
        x0, y0, x1, y1 = box["preview_box"]
        width = x1 - x0
        height = y1 - y0
        pad_x = max(2, int(round(width * padding_ratio)))
        pad_y = max(2, int(round(height * padding_ratio)))
        padded = [
            max(0, x0 - pad_x),
            max(0, y0 - pad_y),
            min(image.width, x1 + pad_x),
            min(image.height, y1 + pad_y),
        ]
        crop = image.crop(tuple(padded))
        draw = ImageDraw.Draw(crop)
        inner = (x0 - padded[0], y0 - padded[1], x1 - padded[0], y1 - padded[1])
        draw.rectangle(inner, outline=(255, 64, 64), width=3)
        draw.text((6, 6), box["id"], fill=(255, 64, 64))

        crop_path = output_dir / f"{box['id']}_preview.png"
        crop.save(crop_path)
        crop_images.append((box["id"], crop.copy()))
        frame_outputs.append(
            {
                "id": box["id"],
                "preview": str(crop_path),
                "preview_box": box["preview_box"],
                "padded_preview_box": [int(value) for value in padded],
                "padding_ratio": padding_ratio,
            }
        )

    _write_contact_sheet(crop_images, contact_sheet_path)

    result = {
        "stage": "frame_crop_previews",
        "source_preview": str(preview_path),
        "output_dir": str(output_dir),
        "contact_sheet": str(contact_sheet_path),
        "padding_ratio": padding_ratio,
        "frame_count": len(frame_outputs),
        "frames": frame_outputs,
        "notes": [
            "These are padded low-resolution review crops from the corrected preview.",
            "The red inner rectangle shows the detected frame box; surrounding pixels are intentional padding for review.",
        ],
    }
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def refine_frame_boundaries_from_source(
    input_path: Path,
    frame_boundaries: dict[str, Any],
    metadata_path: Path,
    overlay_path: Path,
    channel_multipliers: list[float],
    search_radius_source: int = 540,
    sample_step: int = 12,
    min_separator_contrast: float = 8.0,
) -> dict[str, Any]:
    """Refine frame-to-frame boundaries by sampling source-resolution separator bands."""
    refined = copy.deepcopy(frame_boundaries)
    stride = int(refined["stride"])
    image = tifffile.memmap(input_path)
    source_height = int(image.shape[0])
    source_width = int(image.shape[1])

    boxes = refined["boxes"]
    adjustments = []
    for strip_index in sorted({box["strip_index"] for box in boxes}):
        strip_boxes = sorted(
            (box for box in boxes if box["strip_index"] == strip_index),
            key=lambda box: box["frame_index"],
        )
        for previous, current in zip(strip_boxes, strip_boxes[1:]):
            candidate = _find_source_separator_boundary(
                image=image,
                previous_box=previous,
                current_box=current,
                source_width=source_width,
                source_height=source_height,
                channel_multipliers=channel_multipliers,
                search_radius_source=search_radius_source,
                sample_step=sample_step,
                min_separator_contrast=min_separator_contrast,
            )
            if candidate["accepted"]:
                boundary_y = int(candidate["candidate_y"])
                previous["source_box_estimate"][3] = boundary_y
                current["source_box_estimate"][1] = boundary_y
                previous["preview_box"][3] = int(round(boundary_y / stride))
                current["preview_box"][1] = int(round(boundary_y / stride))
            adjustments.append(candidate)

    for box in boxes:
        source_x0, source_y0, source_x1, source_y1 = box["source_box_estimate"]
        box["height"] = int(box["preview_box"][3] - box["preview_box"][1])
        box["source_height"] = int(source_y1 - source_y0)
        box["source_width"] = int(source_x1 - source_x0)
        box.setdefault("flags", [])
        if box["source_height"] <= 0 or box["source_width"] <= 0:
            box["flags"].append("invalid_refined_source_box")

    preview_image = Image.open(refined["source_preview"]).convert("RGB")
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    _write_overlay(preview_image, boxes, overlay_path)

    refined["stage"] = "frame_boundary_source_refinement"
    refined["method"] = "preview_strip_separator_projection_with_source_separator_refinement"
    refined["overlay"] = str(overlay_path)
    refined["source_refinement"] = {
        "source_tiff": str(input_path),
        "search_radius_source": int(search_radius_source),
        "sample_step": int(sample_step),
        "min_separator_contrast": float(min_separator_contrast),
        "adjustments": adjustments,
        "accepted_adjustment_count": sum(1 for item in adjustments if item["accepted"]),
    }
    refined["notes"] = [
        "Preview-space boxes refined with source-resolution separator sampling.",
        "Frame count and strip order are constrained from the preview detector.",
        "This remains automatic crop refinement and should still be visually reviewed.",
    ]
    metadata_path.write_text(json.dumps(refined, indent=2, ensure_ascii=False), encoding="utf-8")
    return refined


def write_crop_refinement_review(
    preview_path: Path,
    coarse_boundaries: dict[str, Any],
    refined_boundaries: dict[str, Any],
    metadata_path: Path,
    overlay_path: Path,
) -> dict[str, Any]:
    """Write a visual and JSON audit comparing coarse and refined crop boxes."""
    image = Image.open(preview_path).convert("RGB")
    coarse_boxes = {box["id"]: box for box in coarse_boundaries["boxes"]}
    refined_boxes = {box["id"]: box for box in refined_boundaries["boxes"]}
    box_deltas = []

    for frame_id in sorted(refined_boxes):
        coarse = coarse_boxes.get(frame_id)
        refined = refined_boxes[frame_id]
        if not coarse:
            continue
        coarse_source = coarse["source_box_estimate"]
        refined_source = refined["source_box_estimate"]
        coarse_preview = coarse["preview_box"]
        refined_preview = refined["preview_box"]
        box_deltas.append(
            {
                "id": frame_id,
                "preview_delta": [int(refined_preview[index] - coarse_preview[index]) for index in range(4)],
                "source_delta": [int(refined_source[index] - coarse_source[index]) for index in range(4)],
                "coarse_source_box": [int(value) for value in coarse_source],
                "refined_source_box": [int(value) for value in refined_source],
                "coarse_preview_box": [int(value) for value in coarse_preview],
                "refined_preview_box": [int(value) for value in refined_preview],
            }
        )

    adjustments = refined_boundaries.get("source_refinement", {}).get("adjustments", [])
    accepted_adjustments = [item for item in adjustments if item["accepted"]]
    rejected_adjustments = [item for item in adjustments if not item["accepted"]]
    source_deltas = [abs(int(value)) for item in box_deltas for value in item["source_delta"]]

    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    _write_refinement_comparison_overlay(image, coarse_boundaries["boxes"], refined_boundaries["boxes"], adjustments, overlay_path)

    result = {
        "stage": "crop_refinement_review",
        "source_preview": str(preview_path),
        "overlay": str(overlay_path),
        "coarse_stage": coarse_boundaries.get("stage"),
        "refined_stage": refined_boundaries.get("stage"),
        "frame_count": len(box_deltas),
        "accepted_adjustment_count": len(accepted_adjustments),
        "rejected_adjustment_count": len(rejected_adjustments),
        "max_abs_source_delta": int(max(source_deltas)) if source_deltas else 0,
        "box_deltas": box_deltas,
        "adjustments": adjustments,
        "legend": {
            "red": "coarse preview detector box",
            "green": "source-refined box",
            "orange_line": "rejected separator adjustment kept at original boundary",
        },
        "notes": [
            "Review artifact only; it does not change crop boxes.",
            "Use this before deciding whether skew-aware crop cleanup is necessary.",
        ],
    }
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def export_full_resolution_draft_frames(
    input_path: Path,
    boxes: list[dict[str, Any]],
    output_dir: Path,
    metadata_path: Path,
    contact_sheet_path: Path,
    channel_multipliers: list[float],
    padding_ratio: float = 0.03,
) -> dict[str, Any]:
    """Export full-resolution draft PNG crops from detected preview boxes."""
    image = tifffile.memmap(input_path)
    if image.ndim not in {2, 3}:
        raise ValueError(f"Unsupported TIFF array dimensions for crop export: {image.shape}")

    output_dir.mkdir(parents=True, exist_ok=True)
    source_height = int(image.shape[0])
    source_width = int(image.shape[1])
    frame_outputs = []
    contact_images = []

    for box in boxes:
        x0, y0, x1, y1 = box["source_box_estimate"]
        width = x1 - x0
        height = y1 - y0
        pad_x = max(0, int(round(width * padding_ratio)))
        pad_y = max(0, int(round(height * padding_ratio)))
        padded = [
            max(0, x0 - pad_x),
            max(0, y0 - pad_y),
            min(source_width, x1 + pad_x),
            min(source_height, y1 + pad_y),
        ]

        crop = np.asarray(image[padded[1] : padded[3], padded[0] : padded[2]])
        preview = _correct_inverted_crop_to_uint8(crop, channel_multipliers)
        crop_path = output_dir / f"{box['id']}_draft.png"
        _save_array_as_png(preview, crop_path)
        contact_images.append((box["id"], Image.fromarray(preview[:, :, :3], mode="RGB")))
        frame_outputs.append(
            {
                "id": box["id"],
                "draft_png": str(crop_path),
                "source_box": box["source_box_estimate"],
                "padded_source_box": [int(value) for value in padded],
                "padding_ratio": padding_ratio,
                "shape": [int(value) for value in crop.shape],
            }
        )

    _write_contact_sheet(contact_images, contact_sheet_path)

    result = {
        "stage": "full_resolution_draft_frames",
        "source_tiff": str(input_path),
        "output_dir": str(output_dir),
        "contact_sheet": str(contact_sheet_path),
        "padding_ratio": padding_ratio,
        "frame_count": len(frame_outputs),
        "channel_multipliers": [float(value) for value in channel_multipliers],
        "frames": frame_outputs,
        "notes": [
            "Draft full-resolution crops for inspection.",
            "Crop boxes are accepted preview estimates and may be refined near project finish.",
            "Color is simple direct inversion plus preview-derived channel multipliers, not final grading.",
        ],
    }
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def _find_source_separator_boundary(
    image: np.ndarray,
    previous_box: dict[str, Any],
    current_box: dict[str, Any],
    source_width: int,
    source_height: int,
    channel_multipliers: list[float],
    search_radius_source: int,
    sample_step: int,
    min_separator_contrast: float,
) -> dict[str, Any]:
    previous_source = previous_box["source_box_estimate"]
    current_source = current_box["source_box_estimate"]
    current_boundary = int(round((previous_source[3] + current_source[1]) / 2))
    previous_height = max(1, previous_source[3] - previous_source[1])
    current_height = max(1, current_source[3] - current_source[1])
    radius = min(search_radius_source, int(round(min(previous_height, current_height) * 0.18)))

    y0 = max(0, current_boundary - radius)
    y1 = min(source_height, current_boundary + radius)
    x0 = max(previous_source[0], current_source[0])
    x1 = min(previous_source[2], current_source[2], source_width)
    width = x1 - x0
    inset = min(max(8, width // 12), max(8, width // 4))
    x0 = min(x1 - 1, x0 + inset)
    x1 = max(x0 + 1, x1 - inset)

    if y1 - y0 < sample_step * 3 or x1 - x0 < sample_step * 3:
        return _separator_adjustment_result(previous_box, current_box, current_boundary, current_boundary, 0.0, False, "search_window_too_small")

    patch = np.asarray(image[y0:y1:sample_step, x0:x1:sample_step])
    luminance = _correct_inverted_luminance_profile(patch, channel_multipliers)
    if luminance.size < 3:
        return _separator_adjustment_result(previous_box, current_box, current_boundary, current_boundary, 0.0, False, "profile_too_short")

    smoothed = _smooth_profile(luminance, radius=2)
    candidate_index = int(np.argmin(smoothed))
    candidate_y = int(y0 + candidate_index * sample_step)
    contrast = float(np.median(smoothed) - smoothed[candidate_index])
    edge_margin = max(2, int(round(len(smoothed) * 0.08)))
    near_search_edge = candidate_index < edge_margin or candidate_index >= len(smoothed) - edge_margin
    max_delta = int(round(min(previous_height, current_height) * 0.16))
    delta = candidate_y - current_boundary
    accepted = contrast >= min_separator_contrast and abs(delta) <= max_delta and not near_search_edge
    reason = "accepted" if accepted else "low_contrast_or_unstable_candidate"
    return _separator_adjustment_result(previous_box, current_box, current_boundary, candidate_y, contrast, accepted, reason)


def _separator_adjustment_result(
    previous_box: dict[str, Any],
    current_box: dict[str, Any],
    current_boundary: int,
    candidate_y: int,
    contrast: float,
    accepted: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "between": [previous_box["id"], current_box["id"]],
        "current_boundary_y": int(current_boundary),
        "candidate_y": int(candidate_y),
        "delta_source_y": int(candidate_y - current_boundary),
        "separator_contrast": float(contrast),
        "accepted": bool(accepted),
        "reason": reason,
    }


def _correct_inverted_luminance_profile(patch: np.ndarray, channel_multipliers: list[float]) -> np.ndarray:
    inverted = _invert_by_dtype(patch)
    preview = _to_uint8_preview(inverted)
    if preview.ndim == 3 and preview.shape[2] >= 3 and channel_multipliers:
        corrected = preview.astype(np.float32)
        corrected[:, :, :3] *= np.asarray(channel_multipliers, dtype=np.float32)
        preview = np.clip(corrected, 0, 255).astype(np.float32)
        luminance = preview[:, :, :3].mean(axis=2)
    elif preview.ndim == 3:
        luminance = preview[:, :, :3].astype(np.float32).mean(axis=2)
    else:
        luminance = preview.astype(np.float32)
    return luminance.mean(axis=1)


def _smooth_profile(profile: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0 or profile.size < radius * 2 + 1:
        return profile.astype(np.float32)
    kernel = np.ones(radius * 2 + 1, dtype=np.float32)
    kernel /= kernel.sum()
    padded = np.pad(profile.astype(np.float32), radius, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def _segments_from_mask(mask: np.ndarray, min_length: int) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    start = None
    for index, value in enumerate(mask):
        if value and start is None:
            start = index
        elif not value and start is not None:
            if index - start >= min_length:
                segments.append((start, index))
            start = None
    if start is not None and len(mask) - start >= min_length:
        segments.append((start, len(mask)))
    return segments


def _enhance_detection_luminance(luminance: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    low = float(np.percentile(luminance, 2.0))
    high = float(np.percentile(luminance, 98.0))
    if high <= low:
        enhanced = luminance.astype(np.float32)
    else:
        normalized = np.clip((luminance.astype(np.float32) - low) / (high - low), 0.0, 1.0)
        enhanced = np.power(normalized, 1.25) * 255.0
    return enhanced, {
        "method": "percentile_contrast_stretch_gamma_darken",
        "low_percentile": 2.0,
        "high_percentile": 98.0,
        "low_value": low,
        "high_value": high,
        "gamma": 1.25,
    }


def _content_bounds_from_row_profile(row_profile: np.ndarray) -> tuple[int, int]:
    content_threshold = float(np.percentile(row_profile, 92.0))
    content_segments = _segments_from_mask(row_profile < content_threshold, min_length=max(8, len(row_profile) // 40))
    if not content_segments:
        return 0, len(row_profile)
    return content_segments[0][0], content_segments[-1][1]


def _separator_segments_from_strip(strip_luminance: np.ndarray) -> list[tuple[int, int]]:
    row_mean = strip_luminance.mean(axis=1)
    row_p10 = np.percentile(strip_luminance, 10.0, axis=1)
    mean_threshold = float(np.percentile(row_mean, 9.0))
    p10_threshold = float(np.percentile(row_p10, 10.0))
    separator_mask = (row_mean < mean_threshold) | (row_p10 < p10_threshold)
    raw_segments = _segments_from_mask(separator_mask, min_length=3)
    return _merge_close_segments(raw_segments, max_gap=8)


def _estimate_frame_count(
    content_start: int,
    content_end: int,
    separator_segments: list[tuple[int, int]],
    min_frame_height: int,
) -> int:
    content_height = max(1, content_end - content_start)
    candidates = []
    for y0, y1 in separator_segments:
        midpoint = (max(y0, content_start) + min(y1, content_end)) // 2
        if content_start < midpoint < content_end:
            candidates.append(midpoint)

    strong_boundaries = [content_start]
    last = content_start
    for midpoint in sorted(candidates):
        if midpoint - last >= int(min_frame_height * 0.75):
            strong_boundaries.append(midpoint)
            last = midpoint
    if content_end - last >= int(min_frame_height * 0.75):
        strong_boundaries.append(content_end)
    elif strong_boundaries[-1] != content_end:
        strong_boundaries[-1] = content_end

    if len(strong_boundaries) >= 3:
        intervals = np.diff(np.asarray(strong_boundaries))
        typical_height = float(np.median(intervals))
    else:
        typical_height = float(min_frame_height * 2)

    estimated = int(round(content_height / max(float(min_frame_height), typical_height)))
    return max(1, estimated)


def _frames_from_separators(
    content_start: int,
    content_end: int,
    separator_segments: list[tuple[int, int]],
    frame_count: int,
    min_frame_height: int,
) -> list[tuple[int, int]]:
    if frame_count > 1:
        return _equalized_frames(content_start, content_end, frame_count)

    boundaries = [content_start]
    for y0, y1 in separator_segments:
        if y1 <= content_start or y0 >= content_end:
            continue
        midpoint = (max(y0, content_start) + min(y1, content_end)) // 2
        if content_start < midpoint < content_end:
            boundaries.append(midpoint)
    boundaries.append(content_end)
    boundaries = sorted(set(boundaries))

    frames = []
    for y0, y1 in zip(boundaries, boundaries[1:]):
        if y1 - y0 >= min_frame_height:
            frames.append((y0, y1))
    return frames


def _equalized_frames(content_start: int, content_end: int, frame_count: int) -> list[tuple[int, int]]:
    edges = np.linspace(content_start, content_end, frame_count + 1)
    frames = []
    for index in range(frame_count):
        y0 = int(round(float(edges[index])))
        y1 = int(round(float(edges[index + 1])))
        if y1 > y0:
            frames.append((y0, y1))
    return frames


def _merge_close_segments(segments: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    if not segments:
        return []
    merged = [segments[0]]
    for start, end in segments[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= max_gap:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def _box_quality_flags(y0: int, y1: int, min_frame_height: int) -> list[str]:
    height = y1 - y0
    flags = []
    if height < int(min_frame_height * 1.2):
        flags.append("short_frame")
    if height > int(min_frame_height * 2.4):
        flags.append("tall_or_merged_frame")
    return flags


def _write_overlay(image: Image.Image, boxes: list[dict[str, Any]], overlay_path: Path) -> None:
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for box in boxes:
        x0, y0, x1, y1 = box["preview_box"]
        draw.rectangle((x0, y0, x1, y1), outline=(255, 64, 64), width=3)
        draw.text((x0 + 4, y0 + 4), box["id"], fill=(255, 64, 64))
    overlay.save(overlay_path)


def _write_refinement_comparison_overlay(
    image: Image.Image,
    coarse_boxes: list[dict[str, Any]],
    refined_boxes: list[dict[str, Any]],
    adjustments: list[dict[str, Any]],
    overlay_path: Path,
) -> None:
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for box in coarse_boxes:
        x0, y0, x1, y1 = box["preview_box"]
        draw.rectangle((x0, y0, x1, y1), outline=(255, 64, 64), width=2)
    for box in refined_boxes:
        x0, y0, x1, y1 = box["preview_box"]
        draw.rectangle((x0, y0, x1, y1), outline=(64, 255, 96), width=2)
        draw.text((x0 + 4, y0 + 4), box["id"], fill=(64, 255, 96))

    stride = 1
    if refined_boxes:
        source_height = max(max(box["source_box_estimate"][3], 1) for box in refined_boxes)
        preview_height = max(max(box["preview_box"][3], 1) for box in refined_boxes)
        stride = max(1, int(round(source_height / preview_height)))

    refined_lookup = {box["id"]: box for box in refined_boxes}
    for adjustment in adjustments:
        if adjustment["accepted"]:
            continue
        first_id, second_id = adjustment["between"]
        first = refined_lookup.get(first_id)
        second = refined_lookup.get(second_id)
        if not first or not second:
            continue
        x0 = min(first["preview_box"][0], second["preview_box"][0])
        x1 = max(first["preview_box"][2], second["preview_box"][2])
        y = int(round(adjustment["current_boundary_y"] / stride))
        draw.line((x0, y, x1, y), fill=(255, 176, 64), width=3)

    draw.rectangle((6, 6, 180, 50), fill=(255, 255, 255))
    draw.text((12, 10), "red: coarse", fill=(255, 64, 64))
    draw.text((12, 28), "green: refined", fill=(0, 128, 48))
    overlay.save(overlay_path)


def _write_contact_sheet(crop_images: list[tuple[str, Image.Image]], contact_sheet_path: Path) -> None:
    if not crop_images:
        Image.new("RGB", (320, 240), "white").save(contact_sheet_path)
        return

    thumb_width = 220
    label_height = 20
    gap = 12
    columns = 4
    thumbs = []
    for label, image in crop_images:
        thumb = image.copy()
        thumb.thumbnail((thumb_width, 260), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (thumb_width, thumb.height + label_height), "white")
        tile.paste(thumb, ((thumb_width - thumb.width) // 2, label_height))
        draw = ImageDraw.Draw(tile)
        draw.text((4, 2), label, fill=(0, 0, 0))
        thumbs.append(tile)

    rows = int(np.ceil(len(thumbs) / columns))
    row_heights = []
    for row_index in range(rows):
        row_tiles = thumbs[row_index * columns : (row_index + 1) * columns]
        row_heights.append(max(tile.height for tile in row_tiles))

    sheet_width = columns * thumb_width + (columns + 1) * gap
    sheet_height = sum(row_heights) + (rows + 1) * gap
    sheet = Image.new("RGB", (sheet_width, sheet_height), "white")

    y = gap
    for row_index in range(rows):
        x = gap
        row_tiles = thumbs[row_index * columns : (row_index + 1) * columns]
        for tile in row_tiles:
            sheet.paste(tile, (x, y))
            x += thumb_width + gap
        y += row_heights[row_index] + gap

    contact_sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(contact_sheet_path)


def _correct_inverted_crop_to_uint8(crop: np.ndarray, channel_multipliers: list[float]) -> np.ndarray:
    inverted = _invert_by_dtype(crop)
    preview = _to_uint8_preview(inverted)
    if preview.ndim == 3 and preview.shape[2] >= 3 and channel_multipliers:
        corrected = preview.astype(np.float32)
        corrected[:, :, :3] *= np.asarray(channel_multipliers, dtype=np.float32)
        preview = np.clip(np.rint(corrected), 0, 255).astype(np.uint8)
    return preview


def _invert_by_dtype(image: np.ndarray) -> np.ndarray:
    if np.issubdtype(image.dtype, np.integer):
        return np.iinfo(image.dtype).max - image
    if np.issubdtype(image.dtype, np.floating):
        return 1.0 - np.clip(image, 0.0, 1.0)
    raise ValueError(f"Unsupported TIFF dtype for crop export: {image.dtype}")


def _to_uint8_preview(image: np.ndarray) -> np.ndarray:
    if np.issubdtype(image.dtype, np.integer):
        scaled = image.astype(np.float32) / float(np.iinfo(image.dtype).max)
    else:
        scaled = np.clip(image.astype(np.float32), 0.0, 1.0)
    return np.clip(np.rint(scaled * 255.0), 0, 255).astype(np.uint8)


def _save_array_as_png(image: np.ndarray, path: Path) -> None:
    if image.ndim == 2:
        pil_image = Image.fromarray(image, mode="L")
    else:
        pil_image = Image.fromarray(image[:, :, :3], mode="RGB")
    pil_image.save(path)
