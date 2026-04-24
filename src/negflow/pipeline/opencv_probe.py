"""OpenCV-based crop candidate probe artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw


def write_opencv_crop_probe(
    preview_path: Path,
    metadata_path: Path,
    mask_path: Path,
    cleaned_mask_path: Path,
    overlay_path: Path,
    stride: int,
    min_area_ratio: float = 0.004,
) -> dict[str, Any]:
    """Write OpenCV contour/connected-component diagnostics from a corrected preview."""
    image = Image.open(preview_path).convert("RGB")
    rgb = np.asarray(image)
    luminance = rgb.mean(axis=2).astype(np.float32)
    mask, parameters = _build_content_mask(luminance)
    cleaned_mask = _clean_mask(mask)
    candidates = _component_candidates(cleaned_mask, luminance, stride, min_area_ratio)

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask).save(mask_path)
    Image.fromarray(cleaned_mask).save(cleaned_mask_path)
    _write_probe_overlay(image, candidates, overlay_path)

    result = {
        "stage": "opencv_crop_probe",
        "method": "opencv_threshold_morphology_connected_components",
        "source_preview": str(preview_path),
        "mask": str(mask_path),
        "cleaned_mask": str(cleaned_mask_path),
        "overlay": str(overlay_path),
        "stride": int(stride),
        "preview_size": [int(image.width), int(image.height)],
        "min_area_ratio": float(min_area_ratio),
        "parameters": parameters,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "notes": [
            "Diagnostic probe only; these candidates do not drive final crop export yet.",
            "The probe uses OpenCV thresholding, morphology, and connected components to expose candidate content regions.",
            "Use the candidate metrics and overlay to decide whether OpenCV should replace or guide the projection detector.",
        ],
    }
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def write_opencv_strip_frame_probe(
    preview_path: Path,
    crop_probe: dict[str, Any],
    metadata_path: Path,
    overlay_path: Path,
    stride: int,
    min_frame_height: int = 120,
) -> dict[str, Any]:
    """Split OpenCV component strips into frame candidates for comparison."""
    image = Image.open(preview_path).convert("RGB")
    rgb = np.asarray(image)
    luminance = rgb.mean(axis=2).astype(np.float32)
    effective_min_frame_height = min(min_frame_height, max(8, image.height // 10))

    frames = []
    strip_details = []
    rejected_components = []
    for strip_index, component in enumerate(crop_probe.get("candidates", []), start=1):
        x0, y0, x1, y1 = [int(value) for value in component["preview_box"]]
        strip_luminance = luminance[y0:y1, x0:x1]
        inset_metrics = _inset_luminance_metrics(strip_luminance)
        detail = {
            "strip_index": strip_index,
            "component_id": component["id"],
            "component_preview_box": [x0, y0, x1, y1],
            "inset_metrics": inset_metrics,
            "status": "accepted",
        }
        if inset_metrics["median_luminance"] <= 12.0 and inset_metrics["p90_luminance"] <= 18.0:
            detail["status"] = "rejected"
            detail["rejection_reason"] = "near_black_inset"
            rejected_components.append(detail)
            strip_details.append(detail)
            continue

        content_start = 0
        content_end = strip_luminance.shape[0]
        content_end, tail_trim = _trim_low_detail_tail(
            strip_luminance,
            content_start,
            content_end,
            strip_width=strip_luminance.shape[1],
            min_frame_height=effective_min_frame_height,
        )
        separator_segments = _separator_segments_from_strip_luminance(strip_luminance[content_start:content_end])
        frame_segments = _frame_segments_from_separator_segments(
            content_start,
            content_end,
            separator_segments,
            min_frame_height=effective_min_frame_height,
        )
        detail.update(
            {
                "content_y": [int(y0 + content_start), int(y0 + content_end)],
                "tail_trim": tail_trim,
                "separator_segments": [[int(y0 + start), int(y0 + end)] for start, end in separator_segments],
                "frame_count": len(frame_segments),
            }
        )
        strip_details.append(detail)

        for frame_index, (frame_y0, frame_y1) in enumerate(frame_segments, start=1):
            patch = strip_luminance[frame_y0:frame_y1]
            frame = {
                "id": f"opencv_strip{strip_index}_frame{frame_index}",
                "strip_index": strip_index,
                "component_id": component["id"],
                "frame_index": frame_index,
                "preview_box": [int(x0), int(y0 + frame_y0), int(x1), int(y0 + frame_y1)],
                "source_box_estimate": [
                    int(x0 * stride),
                    int((y0 + frame_y0) * stride),
                    int(x1 * stride),
                    int((y0 + frame_y1) * stride),
                ],
                "mean_luminance": float(patch.mean()) if patch.size else 0.0,
                "luminance_std": float(patch.std()) if patch.size else 0.0,
                "height": int(frame_y1 - frame_y0),
                "flags": _frame_flags(frame_y0, frame_y1, effective_min_frame_height),
            }
            frames.append(frame)

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    _write_strip_frame_overlay(image, frames, rejected_components, overlay_path)

    result = {
        "stage": "opencv_strip_frame_probe",
        "method": "opencv_component_roi_row_valley_split",
        "source_preview": str(preview_path),
        "source_crop_probe": crop_probe.get("metadata", crop_probe.get("stage")),
        "overlay": str(overlay_path),
        "stride": int(stride),
        "preview_size": [int(image.width), int(image.height)],
        "min_frame_height": int(effective_min_frame_height),
        "accepted_frame_count": len(frames),
        "rejected_component_count": len(rejected_components),
        "strip_details": strip_details,
        "frames": frames,
        "notes": [
            "Diagnostic probe only; these frame candidates do not drive final crop export yet.",
            "OpenCV connected components are treated as strip ROIs, then row-luminance valleys split frames inside each accepted strip.",
            "Near-black component interiors are rejected before frame splitting.",
        ],
    }
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def _build_content_mask(luminance: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    threshold = float(np.percentile(luminance, 84.0))
    mask = (luminance < threshold).astype(np.uint8) * 255
    return mask, {
        "threshold_method": "luminance_percentile",
        "foreground_below_percentile": 84.0,
        "threshold_value": threshold,
    }


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    open_size = max(3, int(round(min(height, width) * 0.003)))
    close_width = max(9, int(round(width * 0.018)))
    close_height = max(9, int(round(height * 0.018)))
    open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (open_size, open_size))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (close_width, close_height))
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
    return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, close_kernel)


def _component_candidates(
    mask: np.ndarray,
    luminance: np.ndarray,
    stride: int,
    min_area_ratio: float,
) -> list[dict[str, Any]]:
    height, width = mask.shape
    min_area = int(round(height * width * min_area_ratio))
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    candidates = []
    for label in range(1, component_count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        w = int(stats[label, cv2.CC_STAT_WIDTH])
        h = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < min_area:
            continue

        patch = luminance[y : y + h, x : x + w]
        component_mask = labels[y : y + h, x : x + w] == label
        values = patch[component_mask]
        aspect_ratio = float(w / max(1, h))
        fill_ratio = float(area / max(1, w * h))
        candidates.append(
            {
                "id": f"opencv_component_{len(candidates) + 1}",
                "preview_box": [x, y, x + w, y + h],
                "source_box_estimate": [int(x * stride), int(y * stride), int((x + w) * stride), int((y + h) * stride)],
                "area_pixels": area,
                "area_ratio": float(area / max(1, height * width)),
                "fill_ratio": fill_ratio,
                "aspect_ratio_width_over_height": aspect_ratio,
                "mean_luminance": float(values.mean()) if values.size else 0.0,
                "luminance_std": float(values.std()) if values.size else 0.0,
                "flags": _candidate_flags(values, aspect_ratio, fill_ratio),
            }
        )

    return sorted(candidates, key=lambda item: (item["preview_box"][1], item["preview_box"][0]))


def _inset_luminance_metrics(strip_luminance: np.ndarray) -> dict[str, float]:
    height, width = strip_luminance.shape
    x0 = min(width - 1, max(0, int(round(width * 0.08))))
    x1 = max(x0 + 1, min(width, int(round(width * 0.92))))
    y0 = min(height - 1, max(0, int(round(height * 0.04))))
    y1 = max(y0 + 1, min(height, int(round(height * 0.96))))
    inset = strip_luminance[y0:y1, x0:x1]
    return {
        "mean_luminance": float(inset.mean()) if inset.size else 0.0,
        "median_luminance": float(np.median(inset)) if inset.size else 0.0,
        "p90_luminance": float(np.percentile(inset, 90.0)) if inset.size else 0.0,
        "luminance_std": float(inset.std()) if inset.size else 0.0,
    }


def _trim_low_detail_tail(
    strip_luminance: np.ndarray,
    content_start: int,
    content_end: int,
    *,
    strip_width: int,
    min_frame_height: int,
    max_row_std: float = 8.0,
) -> tuple[int, dict[str, Any]]:
    detail = {
        "applied": False,
        "max_row_std": float(max_row_std),
        "min_tail_height": 0,
        "original_content_end": int(content_end),
        "trimmed_content_end": int(content_end),
        "tail_height": 0,
    }
    if content_end <= content_start:
        return content_end, detail

    inner = _horizontal_inset(strip_luminance[content_start:content_end])
    if inner.size == 0:
        return content_end, detail

    row_std = inner.std(axis=1)
    low_detail_rows = row_std < max_row_std
    tail_height = 0
    for value in low_detail_rows[::-1]:
        if not value:
            break
        tail_height += 1

    min_tail_height = max(int(round(min_frame_height * 1.5)), int(round(strip_width * 0.45)))
    detail["min_tail_height"] = int(min_tail_height)
    detail["tail_height"] = int(tail_height)
    if tail_height < min_tail_height:
        return content_end, detail

    trimmed_content_end = content_end - tail_height
    if trimmed_content_end - content_start < min_frame_height:
        return content_end, detail

    detail["applied"] = True
    detail["trimmed_content_end"] = int(trimmed_content_end)
    return trimmed_content_end, detail


def _separator_segments_from_strip_luminance(strip_luminance: np.ndarray) -> list[tuple[int, int]]:
    inner = _horizontal_inset(strip_luminance)
    if inner.shape[0] < 3:
        return []
    row_mean = inner.mean(axis=1)
    threshold = float(np.percentile(row_mean, 5.0))
    separator_mask = row_mean <= threshold
    raw_segments = _segments_from_mask(separator_mask, min_length=3)
    return _merge_close_segments(raw_segments, max_gap=max(8, strip_luminance.shape[0] // 60))


def _frame_segments_from_separator_segments(
    content_start: int,
    content_end: int,
    separator_segments: list[tuple[int, int]],
    *,
    min_frame_height: int,
) -> list[tuple[int, int]]:
    boundaries = [content_start]
    edge_margin = int(round(min_frame_height * 0.45))
    for y0, y1 in separator_segments:
        midpoint = (y0 + y1) // 2 + content_start
        if midpoint - content_start < edge_margin or content_end - midpoint < edge_margin:
            continue
        if midpoint - boundaries[-1] < int(round(min_frame_height * 0.75)):
            continue
        boundaries.append(midpoint)
    if content_end - boundaries[-1] >= int(round(min_frame_height * 0.75)):
        boundaries.append(content_end)
    else:
        boundaries[-1] = content_end

    frames = []
    for y0, y1 in zip(boundaries, boundaries[1:]):
        if y1 - y0 >= min_frame_height:
            frames.append((y0, y1))
    if not frames and content_end - content_start >= min_frame_height:
        return [(content_start, content_end)]
    return frames


def _horizontal_inset(strip_luminance: np.ndarray) -> np.ndarray:
    if strip_luminance.ndim != 2 or strip_luminance.shape[1] == 0:
        return strip_luminance
    width = strip_luminance.shape[1]
    x0 = min(width - 1, max(0, int(round(width * 0.08))))
    x1 = max(x0 + 1, min(width, int(round(width * 0.92))))
    return strip_luminance[:, x0:x1]


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


def _frame_flags(y0: int, y1: int, min_frame_height: int) -> list[str]:
    height = y1 - y0
    flags = []
    if height < int(round(min_frame_height * 1.2)):
        flags.append("short_frame")
    if height > int(round(min_frame_height * 2.8)):
        flags.append("tall_or_merged_frame")
    return flags


def _candidate_flags(values: np.ndarray, aspect_ratio: float, fill_ratio: float) -> list[str]:
    flags = []
    mean_luminance = float(values.mean()) if values.size else 0.0
    luminance_std = float(values.std()) if values.size else 0.0
    if mean_luminance <= 8.0:
        flags.append("near_black_candidate")
    if luminance_std < 8.0:
        flags.append("low_detail_candidate")
    if aspect_ratio > 2.5:
        flags.append("very_wide_candidate")
    if aspect_ratio < 0.18:
        flags.append("very_tall_candidate")
    if fill_ratio < 0.35:
        flags.append("sparse_component")
    return flags


def _write_probe_overlay(image: Image.Image, candidates: list[dict[str, Any]], overlay_path: Path) -> None:
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for candidate in candidates:
        x0, y0, x1, y1 = candidate["preview_box"]
        flags = candidate["flags"]
        color = (64, 224, 255) if "near_black_candidate" not in flags else (255, 176, 64)
        draw.rectangle((x0, y0, x1, y1), outline=color, width=3)
        draw.text((x0 + 4, y0 + 4), candidate["id"], fill=color)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(overlay_path)


def _write_strip_frame_overlay(
    image: Image.Image,
    frames: list[dict[str, Any]],
    rejected_components: list[dict[str, Any]],
    overlay_path: Path,
) -> None:
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for component in rejected_components:
        x0, y0, x1, y1 = component["component_preview_box"]
        draw.rectangle((x0, y0, x1, y1), outline=(255, 176, 64), width=3)
        draw.text((x0 + 4, y0 + 4), f"{component['component_id']} rejected", fill=(255, 176, 64))
    for frame in frames:
        x0, y0, x1, y1 = frame["preview_box"]
        draw.rectangle((x0, y0, x1, y1), outline=(64, 255, 160), width=3)
        draw.text((x0 + 4, y0 + 4), frame["id"], fill=(64, 255, 160))
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(overlay_path)
