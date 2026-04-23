"""Conservative negative inversion preview stage."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image


def create_inverted_previews(
    input_path: Path,
    direct_preview_path: Path,
    corrected_preview_path: Path,
    metadata_path: Path,
    max_dimension: int = 1600,
) -> dict[str, Any]:
    """Create downsampled direct and film-base-corrected inversion previews."""
    image = tifffile.memmap(input_path)
    if image.ndim not in {2, 3}:
        raise ValueError(f"Unsupported TIFF array dimensions for preview inversion: {image.shape}")

    height = int(image.shape[0])
    width = int(image.shape[1])
    stride = max(1, math.ceil(max(height, width) / max_dimension))

    sample = np.asarray(image[::stride, ::stride])
    inverted = _invert_by_dtype(sample)
    direct_preview = _to_uint8_preview(inverted)
    correction = _estimate_preview_channel_correction(direct_preview)
    corrected_preview = _apply_preview_channel_correction(direct_preview, correction["channel_multipliers"])

    _save_preview_png(direct_preview, direct_preview_path)
    _save_preview_png(corrected_preview, corrected_preview_path)

    metadata = {
        "stage": "inverted_previews",
        "method": "direct_dtype_inversion_downsampled_with_preview_channel_correction",
        "source": str(input_path),
        "direct_preview": str(direct_preview_path),
        "corrected_preview": str(corrected_preview_path),
        "source_shape": [int(value) for value in image.shape],
        "source_dtype": str(image.dtype),
        "stride": stride,
        "preview_shape": [int(value) for value in direct_preview.shape],
        "max_dimension": max_dimension,
        "correction": correction,
        "notes": [
            "These are diagnostic previews only.",
            "The corrected preview uses downsampled frame-region gray-world channel scaling, not final color grading.",
            "No exposure correction, crop, cleanup, or full-resolution output has been applied.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


def create_inverted_preview(input_path: Path, preview_path: Path, metadata_path: Path, max_dimension: int = 1600) -> dict[str, Any]:
    """Create a downsampled direct-inversion preview without grading or crop."""
    corrected_preview_path = preview_path.with_name(f"{preview_path.stem}_corrected{preview_path.suffix}")
    return create_inverted_previews(input_path, preview_path, corrected_preview_path, metadata_path, max_dimension)


def _invert_by_dtype(image: np.ndarray) -> np.ndarray:
    if np.issubdtype(image.dtype, np.integer):
        max_value = np.iinfo(image.dtype).max
        return max_value - image
    if np.issubdtype(image.dtype, np.floating):
        return 1.0 - np.clip(image, 0.0, 1.0)
    raise ValueError(f"Unsupported TIFF dtype for preview inversion: {image.dtype}")


def _to_uint8_preview(image: np.ndarray) -> np.ndarray:
    if np.issubdtype(image.dtype, np.integer):
        info = np.iinfo(image.dtype)
        scaled = image.astype(np.float32) / float(info.max)
    else:
        scaled = np.clip(image.astype(np.float32), 0.0, 1.0)
    return np.clip(np.rint(scaled * 255.0), 0, 255).astype(np.uint8)


def _estimate_preview_channel_correction(preview: np.ndarray) -> dict[str, Any]:
    if preview.ndim != 3 or preview.shape[2] < 3:
        return {
            "method": "skipped_grayscale",
            "channel_percentiles": [],
            "target_percentile": None,
            "channel_multipliers": [],
        }

    rgb = preview[:, :, :3].astype(np.float32)
    luminance = rgb.mean(axis=2)
    low_threshold = float(np.percentile(luminance, 5.0))
    high_threshold = float(np.percentile(luminance, 82.0))
    mask = (luminance >= low_threshold) & (luminance <= high_threshold) & (rgb.max(axis=2) < 245.0)
    if int(mask.sum()) < 32:
        mask = luminance < 245.0
    if int(mask.sum()) < 32:
        mask = np.ones(luminance.shape, dtype=bool)

    channel_means = np.maximum(np.mean(rgb[mask], axis=0), 1.0)
    target = float(np.mean(channel_means))
    multipliers = np.clip(target / channel_means, 0.5, 2.0)

    return {
        "method": "downsampled_frame_region_gray_world_balance",
        "luminance_low_percentile": 5.0,
        "luminance_high_percentile": 82.0,
        "luminance_low_threshold": low_threshold,
        "luminance_high_threshold": high_threshold,
        "sample_count": int(mask.sum()),
        "channel_means": [float(value) for value in channel_means],
        "target_mean": target,
        "channel_multipliers": [float(value) for value in multipliers],
    }


def _apply_preview_channel_correction(preview: np.ndarray, multipliers: list[float]) -> np.ndarray:
    if preview.ndim != 3 or preview.shape[2] < 3 or not multipliers:
        return preview.copy()
    corrected = preview.astype(np.float32).copy()
    corrected[:, :, :3] *= np.asarray(multipliers, dtype=np.float32)
    return np.clip(np.rint(corrected), 0, 255).astype(np.uint8)


def _save_preview_png(preview: np.ndarray, preview_path: Path) -> None:
    if preview.ndim == 2:
        pil_image = Image.fromarray(preview, mode="L")
    else:
        pil_image = Image.fromarray(preview[:, :, :3], mode="RGB")
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    pil_image.save(preview_path)
