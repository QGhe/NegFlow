"""Final PNG export helpers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def export_final_pngs(
    graded_frames_metadata: dict[str, Any],
    output_dir: Path,
    metadata_path: Path,
    output_name_prefix: str,
) -> dict[str, Any]:
    """Promote graded frame PNGs into the final export folder with a manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    final_frames = []

    for index, frame in enumerate(graded_frames_metadata["frames"], start=1):
        source_png = Path(frame["graded_png"])
        final_name = f"{output_name_prefix}_{index:02d}_{frame['id']}.png"
        final_path = output_dir / final_name
        shutil.copy2(source_png, final_path)
        final_frames.append(
            {
                "id": frame["id"],
                "sequence": index,
                "source_graded_png": str(source_png),
                "final_png": str(final_path),
                "source_draft_png": frame.get("source_draft_png"),
                "grade": frame.get("grade"),
            }
        )

    result = {
        "stage": "final_png_export",
        "source_stage": graded_frames_metadata.get("stage"),
        "output_dir": str(output_dir),
        "frame_count": len(final_frames),
        "frames": final_frames,
        "notes": [
            "Final PNGs are currently promoted from the basic per-frame grade.",
            "Crop boxes remain acceptable draft estimates and should be refined before calling the pipeline complete.",
        ],
    }
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
