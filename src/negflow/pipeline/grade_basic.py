"""Basic per-frame grading for draft outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
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

    for frame in draft_frames_metadata["frames"]:
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
        "frames": graded_frames,
        "notes": [
            "Conservative per-frame draft grade only.",
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
