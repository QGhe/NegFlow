"""Lightweight TIFF metadata inspection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tifffile


def inspect_tiff_metadata(input_path: Path) -> dict[str, Any]:
    """Read TIFF page metadata without loading full pixel data."""
    with tifffile.TiffFile(input_path) as tif:
        if not tif.pages:
            raise ValueError(f"TIFF has no image pages: {input_path}")

        page = tif.pages[0]
        shape = tuple(int(value) for value in page.shape)
        dtype = str(page.dtype)
        axes = page.axes

    return {
        "shape": list(shape),
        "dtype": dtype,
        "axes": axes,
        "width": _axis_size(shape, axes, "X"),
        "height": _axis_size(shape, axes, "Y"),
        "samples_per_pixel": _axis_size(shape, axes, "S") or 1,
    }


def _axis_size(shape: tuple[int, ...], axes: str, axis: str) -> int | None:
    if axis not in axes:
        return None
    return shape[axes.index(axis)]
