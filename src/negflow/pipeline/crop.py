"""Preview-space frame boundary detection."""

from __future__ import annotations

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
