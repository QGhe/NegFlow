from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import tifffile

from negflow.fff_backend import FffBackendUnavailable
from negflow.runner import process_fff, process_tiff


class ProcessTiffSmokeTest(unittest.TestCase):
    def test_process_tiff_creates_task_structure(self) -> None:
        temp_root = Path.cwd() / "output" / "_test_tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))

        with tempfile.TemporaryDirectory(dir=temp_root) as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "sample.tiff"
            sample = np.full((80, 80, 3), 5000, dtype=np.uint16)
            sample[8:72, 10:35, :] = 42000
            sample[8:72, 45:70, :] = 42000
            tifffile.imwrite(input_file, sample)
            config_file = temp_path / "config.yaml"
            config_file.write_text("preset:\n  name: neutral_archive\n", encoding="utf-8")

            result = process_tiff(
                input_path=input_file,
                output_root=temp_path / "output",
                config_path=config_file,
                preset="neutral_archive",
            )

            self.assertTrue(result.task_dir.exists())
            for stage in (
                "01_raw_meta",
                "02_work_tiff",
                "03_inverted",
                "04_base_grade",
                "05_crop",
                "06_cleanup",
                "07_final",
            ):
                self.assertTrue((result.task_dir / stage).is_dir())

            sidecar = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
            self.assertEqual(sidecar["status"], "completed")
            self.assertEqual(sidecar["preset"], "neutral_archive")
            self.assertEqual(sidecar["tiff_metadata"]["width"], 80)
            self.assertEqual(sidecar["tiff_metadata"]["height"], 80)
            self.assertEqual(sidecar["tiff_metadata"]["dtype"], "uint16")
            work_tiff = sidecar["outputs"]["work_tiff"]
            self.assertIn(work_tiff["method"], {"hardlink", "reference"})
            if work_tiff["path"]:
                self.assertTrue(Path(work_tiff["path"]).exists())
            if work_tiff["reference"]:
                self.assertTrue(Path(work_tiff["reference"]).exists())
            self.assertTrue(Path(sidecar["outputs"]["tiff_metadata"]).exists())
            inverted_preview = sidecar["outputs"]["inverted_preview"]
            self.assertTrue(Path(inverted_preview["preview"]).exists())
            self.assertTrue(Path(inverted_preview["metadata"]).exists())
            self.assertEqual(inverted_preview["preview_shape"], [80, 80, 3])
            corrected_preview = sidecar["outputs"]["corrected_preview"]
            self.assertTrue(Path(corrected_preview["preview"]).exists())
            self.assertEqual(corrected_preview["correction"]["method"], "downsampled_frame_region_gray_world_balance")
            frame_boundary = sidecar["outputs"]["frame_boundary_preview"]
            self.assertTrue(Path(frame_boundary["metadata"]).exists())
            self.assertTrue(Path(frame_boundary["overlay"]).exists())
            self.assertGreaterEqual(frame_boundary["box_count"], 1)
            frame_previews = sidecar["outputs"]["frame_crop_previews"]
            self.assertTrue(Path(frame_previews["metadata"]).exists())
            self.assertTrue(Path(frame_previews["contact_sheet"]).exists())
            self.assertTrue(Path(frame_previews["output_dir"]).is_dir())
            self.assertEqual(frame_previews["frame_count"], frame_boundary["box_count"])
            draft_frames = sidecar["outputs"]["full_resolution_draft_frames"]
            self.assertTrue(Path(draft_frames["metadata"]).exists())
            self.assertTrue(Path(draft_frames["output_dir"]).is_dir())
            self.assertTrue(Path(draft_frames["contact_sheet"]).exists())
            self.assertEqual(draft_frames["frame_count"], frame_boundary["box_count"])
            graded_frames = sidecar["outputs"]["basic_per_frame_grade"]
            self.assertTrue(Path(graded_frames["metadata"]).exists())
            self.assertTrue(Path(graded_frames["output_dir"]).is_dir())
            self.assertTrue(Path(graded_frames["contact_sheet"]).exists())
            self.assertEqual(graded_frames["frame_count"], frame_boundary["box_count"])
            final_png_export = sidecar["outputs"]["final_png_export"]
            self.assertTrue(Path(final_png_export["metadata"]).exists())
            self.assertTrue(Path(final_png_export["output_dir"]).is_dir())
            self.assertEqual(final_png_export["frame_count"], frame_boundary["box_count"])
            self.assertIn("final_png_export", sidecar["implemented_stages"])
            self.assertNotIn("final_png_export", sidecar["pending_stages"])
            self.assertIn("final_crop_refinement", sidecar["pending_stages"])
            self.assertTrue(result.log_path.exists())


class ProcessFffBackendTest(unittest.TestCase):
    def test_process_fff_records_blocked_sidecar_when_backend_is_missing(self) -> None:
        temp_root = Path.cwd() / "output" / "_test_tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))

        with tempfile.TemporaryDirectory(dir=temp_root) as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "sample.fff"
            input_file.write_bytes(b"fake-fff")
            config_file = temp_path / "config.yaml"
            config_file.write_text("backend:\n  mode: external_converter\n", encoding="utf-8")

            with self.assertRaises(FffBackendUnavailable) as context:
                process_fff(
                    input_path=input_file,
                    output_root=temp_path / "output",
                    config_path=config_file,
                    preset="neutral_archive",
                )

            sidecar_path = context.exception.sidecar_path
            self.assertIsNotNone(sidecar_path)
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            self.assertEqual(sidecar["status"], "blocked")
            self.assertIn("fff_backend_boundary", sidecar["implemented_stages"])
            self.assertIn("fff_conversion", sidecar["pending_stages"])
            self.assertTrue(sidecar["errors"])


if __name__ == "__main__":
    unittest.main()
