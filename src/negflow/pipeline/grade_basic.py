"""Basic per-frame grading for draft outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image, ImageDraw


def grade_draft_frames(
    draft_frames_metadata: dict[str, Any],
    output_dir: Path,
    metadata_path: Path,
    contact_sheet_path: Path,
) -> dict[str, Any]:
    """Apply conservative per-frame exposure/contrast normalization."""
    output_dir.mkdir(parents=True, exist_ok=True)
    graded_frames = []
    contact_images = []
    source_image, roll_color_model = _open_source_for_grading(draft_frames_metadata)

    for frame in draft_frames_metadata["frames"]:
        if source_image is not None and roll_color_model is not None and "padded_source_box" in frame:
            graded, params = _grade_source_negative_frame(source_image, frame, roll_color_model)
        else:
            image = Image.open(frame["draft_png"]).convert("RGB")
            graded, params = _grade_image(np.asarray(image))
        output_path = output_dir / f"{frame['id']}_graded.png"
        Image.fromarray(graded, mode="RGB").save(output_path)
        contact_images.append((frame["id"], Image.fromarray(graded, mode="RGB")))
        graded_frames.append(
            {
                "id": frame["id"],
                "source_draft_png": frame["draft_png"],
                "graded_png": str(output_path),
                "grade": params,
            }
        )

    _write_contact_sheet(contact_images, contact_sheet_path)
    result = {
        "stage": "basic_per_frame_grade",
        "source_stage": draft_frames_metadata.get("stage"),
        "output_dir": str(output_dir),
        "contact_sheet": str(contact_sheet_path),
        "frame_count": len(graded_frames),
        "roll_color_model": roll_color_model,
        "frames": graded_frames,
        "notes": [
            "Conservative per-frame base grade.",
            "When source TIFF coordinates are available, grading uses roll-level film base normalization before per-frame tone mapping.",
            "This is not a final film look or color-managed export.",
        ],
    }
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def _grade_image(image: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    rgb = image.astype(np.float32)
    low = np.percentile(rgb, 1.0, axis=(0, 1))
    high = np.percentile(rgb, 99.0, axis=(0, 1))
    span = np.maximum(high - low, 1.0)
    normalized = np.clip((rgb - low) / span, 0.0, 1.0)

    means = np.maximum(normalized.mean(axis=(0, 1)), 0.01)
    target = float(np.mean(means))
    multipliers = np.clip(target / means, 0.75, 1.35)
    balanced = np.clip(normalized * multipliers, 0.0, 1.0)

    gamma = 0.95
    graded = np.power(balanced, gamma)
    output = np.clip(np.rint(graded * 255.0), 0, 255).astype(np.uint8)
    return output, {
        "method": "per_channel_percentile_stretch_gray_balance_gamma",
        "low_percentile": 1.0,
        "high_percentile": 99.0,
        "low": [float(value) for value in low],
        "high": [float(value) for value in high],
        "mean_after_stretch": [float(value) for value in means],
        "gray_balance_multipliers": [float(value) for value in multipliers],
        "gamma": gamma,
    }


def _open_source_for_grading(draft_frames_metadata: dict[str, Any]) -> tuple[np.ndarray | None, dict[str, Any] | None]:
    source_tiff = draft_frames_metadata.get("source_tiff")
    frames = draft_frames_metadata.get("frames", [])
    if not source_tiff or not frames:
        return None, None
    try:
        image = tifffile.memmap(source_tiff)
    except (OSError, ValueError):
        return None, None
    if image.ndim != 3 or image.shape[2] < 3 or not np.issubdtype(image.dtype, np.integer):
        return None, None
    return image, _estimate_roll_color_model(image, frames)


def _estimate_roll_color_model(image: np.ndarray, frames: list[dict[str, Any]]) -> dict[str, Any]:
    margin_chunks = []
    frame_chunks = []
    max_value = float(np.iinfo(image.dtype).max)
    for frame in frames:
        source_box = frame.get("source_box")
        padded_box = frame.get("padded_source_box")
        if not source_box or not padded_box:
            continue
        frame_sample = _sample_source_box(image, source_box, max_step=48)
        if frame_sample.size:
            frame_chunks.append(frame_sample)
        for region in _frame_margin_regions(source_box, padded_box, image.shape[1], image.shape[0]):
            x0, y0, x1, y1 = region
            if x1 <= x0 or y1 <= y0:
                continue
            sample = _sample_source_region(image, x0, y0, x1, y1, max_step=32)
            if sample.size:
                margin_chunks.append(sample)

    if margin_chunks:
        margin_samples = np.concatenate(margin_chunks).astype(np.float32)
        reference_sample_source = "frame_margin_regions"
    else:
        stride = max(1, int(round(max(image.shape[0], image.shape[1]) / 1600)))
        margin_samples = np.asarray(image[::stride, ::stride, :3]).reshape(-1, 3).astype(np.float32)
        reference_sample_source = "whole_image_fallback"

    reference_classification = _classify_margin_references(margin_samples, max_value)
    film_base = np.asarray(reference_classification["clear_film_base_rgb"], dtype=np.float32)
    dark_margin_reference = np.asarray(reference_classification["dark_margin_reference_rgb"], dtype=np.float32)

    if frame_chunks:
        frame_samples = np.concatenate(frame_chunks).astype(np.float32)
    else:
        frame_samples = margin_samples
    density_reference, density_reference_detail = _estimate_density_reference(
        frame_samples,
        max_value=max_value,
        film_base=film_base,
        fallback_reference=dark_margin_reference,
    )
    return {
        "method": "classified_film_edge_reference_inversion",
        "source_dtype": str(image.dtype),
        "reference_sample_source": reference_sample_source,
        "sample_count": int(margin_samples.shape[0]),
        "frame_sample_count": int(frame_samples.shape[0]),
        "reference_classification": reference_classification,
        "density_reference": density_reference_detail,
        "film_base_rgb": [float(value) for value in film_base],
        "black_reference_rgb": [float(value) for value in density_reference],
        "density_reference_rgb": [float(value) for value in density_reference],
        "dark_margin_reference_rgb": [float(value) for value in dark_margin_reference],
    }


def _sample_source_box(image: np.ndarray, source_box: list[int], max_step: int) -> np.ndarray:
    x0, y0, x1, y1 = source_box
    return _sample_source_region(image, x0, y0, x1, y1, max_step=max_step)


def _sample_source_region(
    image: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    max_step: int,
) -> np.ndarray:
    if x1 <= x0 or y1 <= y0:
        return np.empty((0, 3), dtype=np.float32)
    step = max(8, min(max_step, int(round(max(x1 - x0, y1 - y0) / 180))))
    return np.asarray(image[y0:y1:step, x0:x1:step, :3]).reshape(-1, 3)


def _classify_margin_references(
    samples: np.ndarray,
    max_value: float,
    *,
    min_reference_samples: int = 256,
) -> dict[str, Any]:
    normalized = np.asarray(samples, dtype=np.float32).reshape(-1, 3) / max_value
    fallback_film_base = np.maximum(np.percentile(normalized, 94.0, axis=0), 0.02)
    fallback_dark = np.percentile(normalized, 2.0, axis=0)

    luminance = normalized.mean(axis=1)
    chroma = normalized.max(axis=1) - normalized.min(axis=1)

    high_luminance = normalized[luminance >= np.percentile(luminance, 90.0)]
    orange_base_mask = (
        (high_luminance[:, 0] > high_luminance[:, 1])
        & (high_luminance[:, 1] > high_luminance[:, 2])
        & ((high_luminance[:, 0] - high_luminance[:, 2]) >= 0.08)
    )
    orange_base = high_luminance[orange_base_mask]
    if orange_base.shape[0] >= min_reference_samples:
        clear_base_samples = orange_base
        clear_base_source = "high_luminance_orange_margin_pixels"
    elif high_luminance.shape[0] >= min_reference_samples:
        clear_base_samples = high_luminance
        clear_base_source = "high_luminance_margin_pixels"
    else:
        clear_base_samples = normalized
        clear_base_source = "fallback_all_margin_pixels"

    low_luminance = normalized[luminance <= np.percentile(luminance, 10.0)]
    low_luminance_chroma = low_luminance.max(axis=1) - low_luminance.min(axis=1)
    low_chroma_dark = low_luminance[low_luminance_chroma <= np.percentile(low_luminance_chroma, 80.0)]
    if low_chroma_dark.shape[0] >= min_reference_samples:
        dark_samples = low_chroma_dark
        dark_source = "low_luminance_low_chroma_margin_pixels"
    elif low_luminance.shape[0] >= min_reference_samples:
        dark_samples = low_luminance
        dark_source = "low_luminance_margin_pixels"
    else:
        dark_samples = normalized
        dark_source = "fallback_all_margin_pixels"

    clear_base = np.maximum(np.percentile(clear_base_samples, 50.0, axis=0), 0.02)
    dark_reference = np.minimum(np.percentile(dark_samples, 50.0, axis=0), clear_base - 0.005)
    return {
        "method": "margin_reference_classification",
        "fallback_film_base_percentile": 94.0,
        "fallback_dark_percentile": 2.0,
        "fallback_film_base_rgb": [float(value) for value in fallback_film_base],
        "fallback_dark_reference_rgb": [float(value) for value in fallback_dark],
        "clear_film_base_source": clear_base_source,
        "dark_margin_source": dark_source,
        "clear_film_base_sample_count": int(clear_base_samples.shape[0]),
        "dark_margin_sample_count": int(dark_samples.shape[0]),
        "clear_film_base_rgb": [float(value) for value in clear_base],
        "dark_margin_reference_rgb": [float(value) for value in dark_reference],
        "luminance_p90": float(np.percentile(luminance, 90.0)),
        "luminance_p10": float(np.percentile(luminance, 10.0)),
        "mean_margin_chroma": float(chroma.mean()),
    }


def _estimate_density_reference(
    samples: np.ndarray,
    *,
    max_value: float,
    film_base: np.ndarray,
    fallback_reference: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    normalized = np.asarray(samples, dtype=np.float32).reshape(-1, 3) / max_value
    raw_reference = np.percentile(normalized, 5.0, axis=0)
    density_reference = np.maximum(raw_reference, fallback_reference)
    density_reference = np.minimum(density_reference, film_base - 0.005)
    return density_reference, {
        "method": "in_frame_low_percentile_density_reference",
        "percentile": 5.0,
        "raw_density_reference_rgb": [float(value) for value in raw_reference],
        "fallback_floor_rgb": [float(value) for value in fallback_reference],
        "density_reference_rgb": [float(value) for value in density_reference],
        "sample_count": int(normalized.shape[0]),
    }


def _frame_margin_regions(
    source_box: list[int],
    padded_box: list[int],
    source_width: int,
    source_height: int,
) -> list[tuple[int, int, int, int]]:
    sx0, sy0, sx1, sy1 = source_box
    px0, py0, px1, py1 = padded_box
    px0, py0 = max(0, px0), max(0, py0)
    px1, py1 = min(source_width, px1), min(source_height, py1)
    return [
        (px0, py0, px1, max(py0, sy0)),
        (px0, min(py1, sy1), px1, py1),
        (px0, py0, max(px0, sx0), py1),
        (min(px1, sx1), py0, px1, py1),
    ]


def _grade_source_negative_frame(
    source_image: np.ndarray,
    frame: dict[str, Any],
    roll_color_model: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    x0, y0, x1, y1 = frame["padded_source_box"]
    crop = np.asarray(source_image[y0:y1, x0:x1, :3]).astype(np.float32)
    max_value = float(np.iinfo(source_image.dtype).max)
    negative = np.clip(crop / max_value, 0.0, 1.0)

    film_base = np.asarray(roll_color_model["film_base_rgb"], dtype=np.float32)
    density_reference = np.asarray(
        roll_color_model.get("density_reference_rgb", roll_color_model["black_reference_rgb"]),
        dtype=np.float32,
    )
    span = np.maximum(film_base - density_reference, 0.005)
    positive = np.clip((film_base - negative) / span, 0.0, 1.0)

    luminance = positive.mean(axis=2)
    low = float(np.percentile(luminance, 1.0))
    high = float(np.percentile(luminance, 99.0))
    normalized = np.clip((positive - low) / max(high - low, 0.01), 0.0, 1.0)

    neutral_mask = _neutral_candidate_mask(normalized)
    neutral_sample = normalized[neutral_mask] if int(neutral_mask.sum()) >= 256 else normalized.reshape(-1, 3)
    means = np.maximum(neutral_sample.mean(axis=0), 0.01)
    target = float(np.mean(means))
    neutral_multipliers = np.clip(target / means, 0.86, 1.24)
    warmth_bias = np.asarray([1.035, 1.0, 0.965], dtype=np.float32)
    neutral_multipliers = np.clip(neutral_multipliers * warmth_bias, 0.84, 1.28)
    balanced = np.clip(normalized * neutral_multipliers, 0.0, 1.0)

    gamma = 0.72
    graded = np.power(balanced, gamma)
    output = np.clip(np.rint(graded * 255.0), 0, 255).astype(np.uint8)
    return output, {
        "method": "source_tiff_roll_film_base_normalized_grade",
        "film_base_rgb": roll_color_model["film_base_rgb"],
        "black_reference_rgb": roll_color_model["black_reference_rgb"],
        "density_reference_rgb": [float(value) for value in density_reference],
        "dark_margin_reference_rgb": roll_color_model.get("dark_margin_reference_rgb"),
        "luminance_low_percentile": 1.0,
        "luminance_high_percentile": 99.0,
        "luminance_low": low,
        "luminance_high": high,
        "mean_after_tone_map": [float(value) for value in means],
        "neutral_sample_count": int(neutral_sample.shape[0]),
        "warmth_bias": [float(value) for value in warmth_bias],
        "neutral_multipliers": [float(value) for value in neutral_multipliers],
        "gamma": gamma,
    }


def _neutral_candidate_mask(image: np.ndarray) -> np.ndarray:
    luminance = image.mean(axis=2)
    chroma = image.max(axis=2) - image.min(axis=2)
    low = float(np.percentile(luminance, 8.0))
    high = float(np.percentile(luminance, 92.0))
    return (luminance >= low) & (luminance <= high) & (chroma <= 0.16)


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
