import os
import pathlib
import shutil
import unittest
import json # Added for loading orchestration summary
from moviepy.editor import VideoClip # Used for type checking primarily

# Adjust import path to run from project root (e.g., using `python -m backend.tests.test_video_utils`)
from backend.video_pipeline.video_utils import (
    process_image_to_video_clip,
    process_video_clip,
    TIKTOK_DIMS,
    DEFAULT_FPS
)

class TestVideoUtilsWithRealAssets(unittest.TestCase):
    test_outputs_dir = pathlib.Path(__file__).parent / "test_outputs_video_utils"
    orchestration_summary_path = pathlib.Path(__file__).parent.parent.parent / "test_outputs" / "orchestration_summary_updated_by_assembler_test.json"
    if not orchestration_summary_path.exists():
        orchestration_summary_path = pathlib.Path(__file__).parent.parent.parent / "test_outputs" / "orchestration_summary_output.json"

    image_scene_data = None
    video_scene_data = None
    project_id_for_test = "unknown_project"

    @classmethod
    def setUpClass(cls):
        cls.test_outputs_dir.mkdir(parents=True, exist_ok=True)
        print(f"Attempting to load orchestration summary from: {cls.orchestration_summary_path}")
        if not cls.orchestration_summary_path.exists():
            print(f"Orchestration summary not found at {cls.orchestration_summary_path}. Tests requiring it will be skipped.")
            return

        try:
            with open(cls.orchestration_summary_path, 'r') as f:
                raw_data = json.load(f)

            scene_plans = []
            if isinstance(raw_data, dict):
                print(f"Loaded orchestration summary as a dictionary.")
                scene_plans = raw_data.get("scene_plans", [])
                cls.project_id_for_test = raw_data.get("video_project_id", cls.project_id_for_test)
            elif isinstance(raw_data, list):
                print(f"Loaded orchestration summary as a list. This might be an older format.")
                scene_plans = raw_data
                for scene in scene_plans:
                    if scene.get("visual_type") == "AVATAR" and scene.get("avatar_video_path"):
                        try:
                            filename = pathlib.Path(scene["avatar_video_path"]).name
                            # e.g. video_project_64462b04_001_avatar_ondemand.mp4
                            # We want "video_project_64462b04"
                            if filename.startswith("video_project_"):
                                parts = filename.split('_')
                                if len(parts) >= 3:
                                     cls.project_id_for_test = "_".join(parts[0:3]) # video_project_xxxx
                                     print(f"Inferred project_id: {cls.project_id_for_test} from avatar path.")
                                     break
                        except Exception:
                            pass
            else:
                print(f"Unknown format for orchestration summary. Expected dict or list.")
                return

            if not scene_plans:
                print("No scene plans found in the orchestration summary.")
                return

            for scene in scene_plans:
                if cls.image_scene_data is None and scene.get("visual_type") == "STOCK_IMAGE" and scene.get("image_asset_path") and pathlib.Path(scene["image_asset_path"]).exists():
                    cls.image_scene_data = scene
                    print(f"Found valid image scene for testing: {scene.get('scene_id')} - {scene.get('image_asset_path')}")

                path_key = None
                if scene.get("visual_type") == "STOCK_VIDEO": path_key = "video_asset_path"
                elif scene.get("visual_type") == "AVATAR": path_key = "avatar_video_path"

                if cls.video_scene_data is None and path_key and scene.get(path_key) and pathlib.Path(scene[path_key]).exists():
                    cls.video_scene_data = scene
                    print(f"Found valid video scene for testing: {scene.get('scene_id')} - {scene.get(path_key)}")

                if cls.image_scene_data and cls.video_scene_data:
                    break # Found both, no need to iterate further

            if not cls.image_scene_data:
                print("No suitable STOCK_IMAGE scene with a valid asset path found in orchestration summary for testing.")
            if not cls.video_scene_data:
                print("No suitable STOCK_VIDEO or AVATAR scene with a valid asset path found in orchestration summary for testing.")

        except json.JSONDecodeError as e:
            print(f"JSONDecodeError loading orchestration summary {cls.orchestration_summary_path}: {e}")
        except Exception as e:
            print(f"Error loading or processing orchestration summary {cls.orchestration_summary_path}: {e}")

    @classmethod
    def tearDownClass(cls):
        if cls.test_outputs_dir.exists():
            # shutil.rmtree(cls.test_outputs_dir) # Comment out to inspect outputs
            print(f"Test outputs saved in {cls.test_outputs_dir}. Manually clean if needed.")
            pass

    def test_process_real_image_to_video_clip(self):
        if not self.image_scene_data:
            self.skipTest("Skipping image processing test: no valid image scene data was loaded in setUpClass.")

        image_path = self.image_scene_data["image_asset_path"]
        duration = self.image_scene_data["end_time"] - self.image_scene_data["start_time"]
        self.assertTrue(duration > 0, "Image scene duration must be positive")

        print(f"\nTesting image to video clip with real asset: {image_path} for duration {duration:.2f}s")

        clip = process_image_to_video_clip(image_path, duration)
        self.assertIsNotNone(clip, "process_image_to_video_clip should return a clip for real image")
        if clip:
            self.assertIsInstance(clip, VideoClip, "Returned object should be a MoviePy VideoClip")
            self.assertAlmostEqual(clip.duration, duration, delta=0.01, msg="Clip duration should match scene duration")
            self.assertEqual(clip.size, TIKTOK_DIMS, "Clip dimensions should match target dimensions")
            self.assertEqual(clip.fps, DEFAULT_FPS, "Clip FPS should match default FPS")
            output_path = self.test_outputs_dir / f"processed_real_image_{self.image_scene_data['scene_id']}.mp4"
            clip.write_videofile(str(output_path), fps=DEFAULT_FPS, logger=None)
            self.assertTrue(output_path.exists(), f"Output file {output_path} was not created.")
            print(f"Saved processed real image to: {output_path}")
            clip.close()

    def test_process_real_video_clip(self):
        if not self.video_scene_data:
            self.skipTest("Skipping video processing test: no valid video scene data was loaded in setUpClass.")

        video_path = self.video_scene_data.get("video_asset_path") or self.video_scene_data.get("avatar_video_path")
        scene_duration = self.video_scene_data["end_time"] - self.video_scene_data["start_time"]
        self.assertTrue(scene_duration > 0, "Video scene duration must be positive")

        print(f"\nTesting video clip processing with real asset: {video_path} for target duration {scene_duration:.2f}s")

        clip = process_video_clip(video_path, scene_duration)
        self.assertIsNotNone(clip, "process_video_clip should return a clip for real video")
        if clip:
            self.assertIsInstance(clip, VideoClip, "Returned object should be a MoviePy VideoClip")
            from moviepy.editor import VideoFileClip as VFC
            original_clip_for_duration_check = VFC(video_path)
            expected_duration = min(scene_duration, original_clip_for_duration_check.duration)
            original_clip_for_duration_check.close()

            self.assertAlmostEqual(clip.duration, expected_duration, delta=0.1, msg=f"Clip duration ({clip.duration:.2f}s) should match expected ({expected_duration:.2f}s) for scene {self.video_scene_data['scene_id']}")
            self.assertEqual(clip.size, TIKTOK_DIMS, "Clip dimensions should match target dimensions")
            output_path = self.test_outputs_dir / f"processed_real_video_{self.video_scene_data['scene_id']}.mp4"
            clip.write_videofile(str(output_path), logger=None)
            self.assertTrue(output_path.exists(), f"Output file {output_path} was not created.")
            print(f"Saved processed real video to: {output_path}")
            clip.close()

    def test_process_image_file_not_found(self):
        clip = process_image_to_video_clip("non_existent_image.png", 2.0)
        self.assertIsNone(clip, "Should return None if image file not found")

    def test_process_video_file_not_found(self):
        clip = process_video_clip("non_existent_video.mp4", 2.0)
        self.assertIsNone(clip, "Should return None if video file not found")

if __name__ == '__main__':
    unittest.main()
