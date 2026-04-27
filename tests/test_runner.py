from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import tifffile

from negflow.fff_backend import FffBackendUnavailable, load_backend_config
from negflow.pipeline.crop import _trim_low_detail_vertical_tail, detect_frame_boundaries
from negflow.pipeline.grade_basic import _classify_margin_references
from negflow.pipeline.opencv_probe import write_opencv_crop_probe, write_opencv_strip_frame_probe
from negflow.runner import _select_active_frame_boundaries, load_output_retention_config, process_fff, process_tiff


class ProcessTiffSmokeTest(unittest.TestCase):
    def test_process_tiff_creates_task_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
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
            opencv_probe = sidecar["outputs"]["opencv_crop_probe"]
            self.assertTrue(Path(opencv_probe["metadata"]).exists())
            self.assertTrue(Path(opencv_probe["mask"]).exists())
            self.assertTrue(Path(opencv_probe["cleaned_mask"]).exists())
            self.assertTrue(Path(opencv_probe["overlay"]).exists())
            self.assertGreaterEqual(opencv_probe["candidate_count"], 1)
            opencv_strip_frame_probe = sidecar["outputs"]["opencv_strip_frame_probe"]
            self.assertTrue(Path(opencv_strip_frame_probe["metadata"]).exists())
            self.assertTrue(Path(opencv_strip_frame_probe["overlay"]).exists())
            self.assertGreaterEqual(opencv_strip_frame_probe["accepted_frame_count"], 1)
            self.assertGreaterEqual(opencv_strip_frame_probe["rejected_component_count"], 0)
            active_frame_boundary = sidecar["outputs"]["active_frame_boundary"]
            self.assertTrue(Path(active_frame_boundary["metadata"]).exists())
            self.assertTrue(Path(active_frame_boundary["overlay"]).exists())
            self.assertGreaterEqual(active_frame_boundary["box_count"], 1)
            self.assertIn(active_frame_boundary["active_detector"], {"opencv_strip_frame_probe", "frame_boundary_preview"})
            crop_refinement = sidecar["outputs"]["source_separator_crop_refinement"]
            self.assertTrue(Path(crop_refinement["metadata"]).exists())
            self.assertTrue(Path(crop_refinement["overlay"]).exists())
            self.assertEqual(crop_refinement["box_count"], active_frame_boundary["box_count"])
            self.assertGreaterEqual(crop_refinement["accepted_adjustment_count"], 0)
            crop_review = sidecar["outputs"]["crop_refinement_review"]
            self.assertTrue(Path(crop_review["metadata"]).exists())
            self.assertTrue(Path(crop_review["overlay"]).exists())
            self.assertEqual(crop_review["frame_count"], active_frame_boundary["box_count"])
            self.assertGreaterEqual(crop_review["accepted_adjustment_count"], 0)
            self.assertGreaterEqual(crop_review["rejected_adjustment_count"], 0)
            frame_previews = sidecar["outputs"]["frame_crop_previews"]
            self.assertTrue(Path(frame_previews["metadata"]).exists())
            self.assertTrue(Path(frame_previews["contact_sheet"]).exists())
            self.assertTrue(Path(frame_previews["output_dir"]).is_dir())
            self.assertEqual(frame_previews["frame_count"], active_frame_boundary["box_count"])
            draft_frames = sidecar["outputs"]["full_resolution_draft_frames"]
            self.assertTrue(Path(draft_frames["metadata"]).exists())
            self.assertTrue(Path(draft_frames["output_dir"]).is_dir())
            self.assertTrue(draft_frames["retained"])
            self.assertTrue(Path(draft_frames["contact_sheet"]).exists())
            self.assertEqual(draft_frames["frame_count"], active_frame_boundary["box_count"])
            graded_frames = sidecar["outputs"]["basic_per_frame_grade"]
            self.assertTrue(Path(graded_frames["metadata"]).exists())
            self.assertTrue(Path(graded_frames["output_dir"]).is_dir())
            self.assertTrue(graded_frames["retained"])
            self.assertTrue(Path(graded_frames["contact_sheet"]).exists())
            self.assertEqual(graded_frames["frame_count"], active_frame_boundary["box_count"])
            graded_metadata = json.loads(Path(graded_frames["metadata"]).read_text(encoding="utf-8"))
            self.assertEqual(graded_metadata["roll_color_model"]["method"], "classified_film_edge_reference_inversion")
            self.assertIn("reference_classification", graded_metadata["roll_color_model"])
            self.assertIn("density_reference_rgb", graded_metadata["roll_color_model"])
            self.assertIn("warmth_bias", graded_metadata["frames"][0]["grade"])
            final_png_export = sidecar["outputs"]["final_png_export"]
            self.assertTrue(Path(final_png_export["metadata"]).exists())
            self.assertTrue(Path(final_png_export["output_dir"]).is_dir())
            self.assertEqual(final_png_export["frame_count"], active_frame_boundary["box_count"])
            self.assertIn("final_png_export", sidecar["implemented_stages"])
            self.assertNotIn("final_png_export", sidecar["pending_stages"])
            self.assertIn("final_crop_refinement", sidecar["pending_stages"])
            retention = sidecar["outputs"]["output_retention"]
            self.assertTrue(Path(retention["metadata"]).exists())
            self.assertTrue(retention["keep_draft_frames"])
            self.assertTrue(retention["keep_graded_frames"])
            self.assertTrue(result.log_path.exists())

    def test_frame_detection_rejects_near_black_candidate_boxes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            preview_path = temp_path / "preview.png"
            metadata_path = temp_path / "boxes.json"
            overlay_path = temp_path / "overlay.png"
            preview = np.full((240, 240, 3), 245, dtype=np.uint8)
            preview[20:220, 20:90, :] = 130
            preview[20:220, 150:220, :] = 0
            from PIL import Image

            Image.fromarray(preview, mode="RGB").save(preview_path)

            result = detect_frame_boundaries(
                preview_path,
                metadata_path,
                overlay_path,
                stride=1,
                min_strip_width=20,
                min_frame_height=40,
            )

            self.assertTrue(result["boxes"])
            self.assertTrue(result["rejected_boxes"])
            self.assertTrue(all(box["mean_luminance"] > 8.0 for box in result["boxes"]))
            self.assertTrue(all(box["mean_luminance"] <= 8.0 for box in result["rejected_boxes"]))
            self.assertTrue(metadata_path.exists())
            self.assertTrue(overlay_path.exists())

    def test_frame_detection_caps_wide_strip_over_splitting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            preview_path = temp_path / "preview.png"
            metadata_path = temp_path / "boxes.json"
            overlay_path = temp_path / "overlay.png"
            preview = np.full((720, 420, 3), 245, dtype=np.uint8)
            for x in range(40, 340):
                preview[20:460, x, :] = 120 + ((x - 40) % 55)
            preview[460:700, 40:340, :] = 110
            for y in range(80, 440, 45):
                preview[y : y + 4, 40:340, :] = 55
            from PIL import Image

            Image.fromarray(preview, mode="RGB").save(preview_path)

            result = detect_frame_boundaries(
                preview_path,
                metadata_path,
                overlay_path,
                stride=1,
                min_strip_width=20,
                min_frame_height=40,
            )

            self.assertGreaterEqual(len(result["boxes"]), 1)
            self.assertEqual(len(result["boxes"]), 1)
            self.assertTrue(all("luminance_std" in box for box in result["boxes"]))
            self.assertTrue(metadata_path.exists())
            self.assertTrue(overlay_path.exists())

    def test_frame_detection_trims_low_detail_vertical_tail(self) -> None:
        textured_content = np.tile((np.arange(300) % 55) + 95, (460, 1)).astype(np.float32)
        blank_tail = np.full((240, 300), 110, dtype=np.float32)
        strip_luminance = np.vstack([textured_content, blank_tail])

        trimmed_end, detail = _trim_low_detail_vertical_tail(
            strip_luminance,
            content_start=0,
            content_end=700,
            strip_width=300,
            min_frame_height=40,
        )

        self.assertEqual(trimmed_end, 460)
        self.assertTrue(detail["applied"])
        self.assertEqual(detail["tail_height"], 240)

    def test_opencv_crop_probe_writes_diagnostic_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            preview_path = temp_path / "preview.png"
            metadata_path = temp_path / "probe.json"
            mask_path = temp_path / "mask.png"
            cleaned_mask_path = temp_path / "cleaned_mask.png"
            overlay_path = temp_path / "overlay.png"
            preview = np.full((240, 320, 3), 235, dtype=np.uint8)
            preview[30:210, 30:120, :] = 120
            preview[30:210, 190:290, :] = 0
            from PIL import Image

            Image.fromarray(preview, mode="RGB").save(preview_path)

            result = write_opencv_crop_probe(
                preview_path,
                metadata_path,
                mask_path,
                cleaned_mask_path,
                overlay_path,
                stride=2,
            )

            self.assertGreaterEqual(result["candidate_count"], 1)
            self.assertTrue(metadata_path.exists())
            self.assertTrue(mask_path.exists())
            self.assertTrue(cleaned_mask_path.exists())
            self.assertTrue(overlay_path.exists())
            self.assertTrue(any("near_black_candidate" in candidate["flags"] for candidate in result["candidates"]))

    def test_color_model_classifies_clear_base_and_dark_margin_references(self) -> None:
        max_value = 65535.0
        clear_base = np.tile(np.asarray([[52000, 36500, 28500]], dtype=np.float32), (700, 1))
        dark_margin = np.tile(np.asarray([[3100, 3000, 3000]], dtype=np.float32), (700, 1))
        scene_leak = np.tile(np.asarray([[26000, 24500, 23000]], dtype=np.float32), (700, 1))
        samples = np.vstack([clear_base, dark_margin, scene_leak])

        result = _classify_margin_references(samples, max_value)

        self.assertEqual(result["clear_film_base_source"], "high_luminance_orange_margin_pixels")
        self.assertEqual(result["dark_margin_source"], "low_luminance_low_chroma_margin_pixels")
        self.assertGreaterEqual(result["clear_film_base_sample_count"], 256)
        self.assertGreaterEqual(result["dark_margin_sample_count"], 256)
        self.assertAlmostEqual(result["clear_film_base_rgb"][0], 52000 / max_value, places=3)
        self.assertAlmostEqual(result["clear_film_base_rgb"][1], 36500 / max_value, places=3)
        self.assertAlmostEqual(result["clear_film_base_rgb"][2], 28500 / max_value, places=3)
        self.assertAlmostEqual(result["dark_margin_reference_rgb"][0], 3100 / max_value, places=3)

    def test_opencv_strip_frame_probe_splits_roi_frames_and_rejects_black_strip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            preview_path = temp_path / "preview.png"
            metadata_path = temp_path / "strip_probe.json"
            overlay_path = temp_path / "strip_overlay.png"
            preview = np.full((360, 280, 3), 235, dtype=np.uint8)
            preview[20:110, 30:100, :] = 145
            preview[120:210, 30:100, :] = 155
            preview[220:320, 30:100, :] = 150
            preview[110:120, 30:100, :] = 35
            preview[210:220, 30:100, :] = 35
            preview[20:320, 180:250, :] = 0
            from PIL import Image

            Image.fromarray(preview, mode="RGB").save(preview_path)
            crop_probe = {
                "stage": "opencv_crop_probe",
                "candidates": [
                    {"id": "opencv_component_1", "preview_box": [30, 20, 100, 320]},
                    {"id": "opencv_component_2", "preview_box": [180, 20, 250, 320]},
                ],
            }

            result = write_opencv_strip_frame_probe(
                preview_path,
                crop_probe,
                metadata_path,
                overlay_path,
                stride=2,
                min_frame_height=60,
            )

            self.assertEqual(result["accepted_frame_count"], 3)
            self.assertEqual(result["rejected_component_count"], 1)
            self.assertEqual([frame["source_box_estimate"][0] for frame in result["frames"]], [60, 60, 60])
            self.assertTrue(metadata_path.exists())
            self.assertTrue(overlay_path.exists())

    def test_opencv_strip_frame_probe_prefers_regular_separator_spacing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            preview_path = temp_path / "preview.png"
            metadata_path = temp_path / "strip_probe.json"
            overlay_path = temp_path / "strip_overlay.png"
            preview = np.full((360, 160, 3), 235, dtype=np.uint8)
            preview[20:320, 30:100, :] = 150
            for y in (120, 220):
                preview[y : y + 8, 30:100, :] = 35
            preview[70:76, 30:100, :] = 45
            preview[170:176, 30:100, :] = 45
            preview[270:276, 30:100, :] = 45
            from PIL import Image

            Image.fromarray(preview, mode="RGB").save(preview_path)
            crop_probe = {
                "stage": "opencv_crop_probe",
                "candidates": [
                    {"id": "opencv_component_1", "preview_box": [30, 20, 100, 320]},
                ],
            }

            result = write_opencv_strip_frame_probe(
                preview_path,
                crop_probe,
                metadata_path,
                overlay_path,
                stride=2,
                min_frame_height=60,
            )

            self.assertEqual(result["accepted_frame_count"], 3)
            self.assertEqual(
                [frame["preview_box"][1:4:2] for frame in result["frames"]],
                [[20, 124], [124, 224], [224, 320]],
            )
            self.assertTrue(metadata_path.exists())
            self.assertTrue(overlay_path.exists())

    def test_active_frame_boundaries_prefers_plausible_opencv_probe(self) -> None:
        projection = {
            "stage": "frame_boundary_preview",
            "method": "preview_strip_separator_projection",
            "source_preview": "preview.png",
            "stride": 2,
            "preview_size": [100, 200],
            "boxes": [
                {
                    "id": "strip1_frame1",
                    "strip_index": 1,
                    "frame_index": 1,
                    "preview_box": [10, 10, 40, 190],
                    "source_box_estimate": [20, 20, 80, 380],
                    "flags": ["tall_or_merged_frame"],
                }
            ],
        }
        opencv_probe = {
            "stage": "opencv_strip_frame_probe",
            "source_preview": "preview.png",
            "stride": 2,
            "preview_size": [100, 200],
            "min_frame_height": 40,
            "rejected_component_count": 0,
            "strip_details": [
                {
                    "status": "accepted",
                    "frame_count": 2,
                    "estimated_frame_count": 2,
                }
            ],
            "frames": [
                {
                    "id": "opencv_strip1_frame1",
                    "strip_index": 1,
                    "frame_index": 1,
                    "preview_box": [10, 10, 40, 100],
                    "source_box_estimate": [20, 20, 80, 200],
                    "flags": [],
                },
                {
                    "id": "opencv_strip1_frame2",
                    "strip_index": 1,
                    "frame_index": 2,
                    "preview_box": [10, 100, 40, 190],
                    "source_box_estimate": [20, 200, 80, 380],
                    "flags": [],
                },
            ],
        }

        result = _select_active_frame_boundaries(
            projection_boundaries=projection,
            opencv_strip_frame_probe=opencv_probe,
            metadata_path=Path("active.json"),
            overlay_path=Path("active.png"),
        )

        self.assertEqual(result["selection"]["active_detector"], "opencv_strip_frame_probe")
        self.assertFalse(result["selection"]["fallback_used"])
        self.assertEqual(len(result["boxes"]), 2)

    def test_active_frame_boundaries_falls_back_on_implausible_opencv_probe(self) -> None:
        projection = {
            "stage": "frame_boundary_preview",
            "method": "preview_strip_separator_projection",
            "source_preview": "preview.png",
            "stride": 2,
            "preview_size": [100, 200],
            "boxes": [
                {
                    "id": "strip1_frame1",
                    "strip_index": 1,
                    "frame_index": 1,
                    "preview_box": [10, 10, 40, 190],
                    "source_box_estimate": [20, 20, 80, 380],
                    "flags": [],
                }
            ],
        }
        opencv_probe = {
            "stage": "opencv_strip_frame_probe",
            "source_preview": "preview.png",
            "stride": 2,
            "preview_size": [100, 200],
            "strip_details": [
                {
                    "status": "accepted",
                    "frame_count": 2,
                    "estimated_frame_count": 2,
                }
            ],
            "frames": [
                {
                    "id": "opencv_strip1_frame1",
                    "strip_index": 1,
                    "frame_index": 1,
                    "preview_box": [10, 10, 40, 30],
                    "source_box_estimate": [20, 20, 80, 60],
                    "flags": ["short_frame"],
                }
            ],
        }

        result = _select_active_frame_boundaries(
            projection_boundaries=projection,
            opencv_strip_frame_probe=opencv_probe,
            metadata_path=Path("active.json"),
            overlay_path=Path("active.png"),
        )

        self.assertEqual(result["selection"]["active_detector"], "frame_boundary_preview")
        self.assertTrue(result["selection"]["fallback_used"])
        self.assertEqual(len(result["boxes"]), 1)

    def test_process_tiff_can_clean_intermediate_frame_png_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "sample.tiff"
            sample = np.full((80, 80, 3), 5000, dtype=np.uint16)
            sample[8:72, 10:35, :] = 42000
            sample[8:72, 45:70, :] = 42000
            tifffile.imwrite(input_file, sample)
            config_file = temp_path / "config.yaml"
            config_file.write_text(
                "\n".join(
                    [
                        "output:",
                        "  keep_draft_frames: false",
                        "  keep_graded_frames: false",
                        "preset:",
                        "  name: neutral_archive",
                    ]
                ),
                encoding="utf-8",
            )

            result = process_tiff(
                input_path=input_file,
                output_root=temp_path / "output",
                config_path=config_file,
                preset="neutral_archive",
            )

            sidecar = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
            draft_frames = sidecar["outputs"]["full_resolution_draft_frames"]
            graded_frames = sidecar["outputs"]["basic_per_frame_grade"]
            self.assertFalse(draft_frames["retained"])
            self.assertFalse(graded_frames["retained"])
            self.assertFalse(Path(draft_frames["output_dir"]).exists())
            self.assertFalse(Path(graded_frames["output_dir"]).exists())
            self.assertTrue(Path(draft_frames["metadata"]).exists())
            self.assertTrue(Path(draft_frames["contact_sheet"]).exists())
            self.assertTrue(Path(graded_frames["metadata"]).exists())
            self.assertTrue(Path(graded_frames["contact_sheet"]).exists())
            final_png_export = sidecar["outputs"]["final_png_export"]
            self.assertTrue(Path(final_png_export["output_dir"]).is_dir())
            retention = sidecar["outputs"]["output_retention"]
            self.assertTrue(Path(retention["metadata"]).exists())
            self.assertFalse(retention["keep_draft_frames"])
            self.assertFalse(retention["keep_graded_frames"])
            self.assertEqual(len(retention["cleanup_items"]), 2)


class ProcessFffBackendTest(unittest.TestCase):
    def test_output_retention_config_reads_boolean_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.yaml"
            config_file.write_text(
                "\n".join(
                    [
                        "output:",
                        "  keep_draft_frames: false",
                        "  keep_graded_frames: true",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_output_retention_config(config_file)

            self.assertFalse(config.keep_draft_frames)
            self.assertTrue(config.keep_graded_frames)

    def test_backend_config_keeps_hash_inside_quoted_converter_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.yaml"
            config_file.write_text(
                "\n".join(
                    [
                        "backend:",
                        "  mode: external_converter",
                        "  external_converter_command: 'C:\\\\Tools #1\\\\fffconvert.exe' # real comment",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_backend_config(config_file)

            self.assertEqual(config.mode, "external_converter")
            self.assertEqual(config.external_converter_command, "C:\\\\Tools #1\\\\fffconvert.exe")

    def test_process_fff_records_blocked_sidecar_when_backend_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
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

    def test_process_fff_uses_tiff_compatible_passthrough_without_external_converter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "sample.fff"
            sample = np.full((80, 80, 3), 7000, dtype=np.uint16)
            sample[8:72, 10:35, :] = 44000
            sample[8:72, 45:70, :] = 44000
            tifffile.imwrite(input_file, sample)
            config_file = temp_path / "config.yaml"
            config_file.write_text(
                "\n".join(
                    [
                        "backend:",
                        "  mode: tiff_passthrough",
                        "preset:",
                        "  name: neutral_archive",
                    ]
                ),
                encoding="utf-8",
            )

            result = process_fff(
                input_path=input_file,
                output_root=temp_path / "output",
                config_path=config_file,
                preset="neutral_archive",
            )

            sidecar = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
            self.assertEqual(sidecar["status"], "completed")
            self.assertIn("fff_conversion", sidecar["implemented_stages"])
            self.assertNotIn("fff_backend", sidecar["pending_stages"])
            self.assertEqual(sidecar["outputs"]["work_tiff"]["method"], "tiff_compatible_reference")
            self.assertEqual(sidecar["outputs"]["work_tiff"]["path"], str(input_file.resolve()))
            fff_conversion = sidecar["outputs"]["fff_conversion"]
            self.assertEqual(fff_conversion["backend_mode"], "tiff_passthrough")
            self.assertEqual(fff_conversion["conversion_method"], "tiff_compatible_reference")
            self.assertTrue(Path(fff_conversion["metadata"]).exists())
            self.assertTrue(Path(sidecar["outputs"]["final_png_export"]["metadata"]).exists())

    def test_process_fff_runs_external_converter_and_completes_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "sample.fff"
            input_file.write_bytes(b"fake-fff")

            converter_script = temp_path / "mock_converter.py"
            converter_script.write_text(
                "\n".join(
                    [
                        "import sys",
                        "from pathlib import Path",
                        "import numpy as np",
                        "import tifffile",
                        "",
                        "output_path = Path(sys.argv[2])",
                        "output_path.parent.mkdir(parents=True, exist_ok=True)",
                        "sample = np.full((80, 80, 3), 6000, dtype=np.uint16)",
                        "sample[8:72, 10:35, :] = 45000",
                        "sample[8:72, 45:70, :] = 45000",
                        "tifffile.imwrite(output_path, sample)",
                    ]
                ),
                encoding="utf-8",
            )

            config_file = temp_path / "config.yaml"
            config_file.write_text(
                "\n".join(
                    [
                        "backend:",
                        "  mode: external_converter",
                        f"  external_converter_command: '\"{sys.executable}\" \"{converter_script}\" {{input_path_quoted}} {{output_tiff_path_quoted}}'",
                        "preset:",
                        "  name: neutral_archive",
                    ]
                ),
                encoding="utf-8",
            )

            result = process_fff(
                input_path=input_file,
                output_root=temp_path / "output",
                config_path=config_file,
                preset="neutral_archive",
            )

            sidecar = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
            self.assertEqual(sidecar["status"], "completed")
            self.assertEqual(sidecar["input_file"], str(input_file.resolve()))
            self.assertIn("fff_conversion", sidecar["implemented_stages"])
            self.assertNotIn("fff_backend", sidecar["pending_stages"])
            self.assertEqual(sidecar["pending_stages"], ["final_crop_refinement"])
            self.assertEqual(sidecar["outputs"]["work_tiff"]["method"], "converted")
            self.assertTrue(Path(sidecar["outputs"]["work_tiff"]["path"]).exists())
            fff_conversion = sidecar["outputs"]["fff_conversion"]
            self.assertTrue(Path(fff_conversion["metadata"]).exists())
            self.assertEqual(fff_conversion["backend_mode"], "external_converter")
            self.assertEqual(fff_conversion["conversion_method"], "external_converter")
            self.assertTrue(Path(fff_conversion["output_tiff"]).exists())
            self.assertTrue(Path(sidecar["outputs"]["tiff_metadata"]).exists())
            self.assertTrue(Path(sidecar["outputs"]["final_png_export"]["metadata"]).exists())
            self.assertTrue(Path(sidecar["outputs"]["final_png_export"]["output_dir"]).is_dir())


if __name__ == "__main__":
    unittest.main()
