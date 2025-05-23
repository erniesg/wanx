import unittest
from unittest.mock import patch, MagicMock, call
import os
import json
import logging
import pathlib
import shutil

# Ensure paths are relative to the project root for consistency
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

# Add project root to sys.path to allow imports from backend module
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from backend.video_pipeline.asset_orchestrator import orchestrate_video_assets
from backend.text_to_video.argil_client import DEFAULT_GESTURE_SLUGS # For verifying gesture

# Configure basic logging for the test
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Test Configuration ---
TEST_OUTPUT_DIR_BASE = PROJECT_ROOT / "test_outputs"
# Define specific subdirectories for this test to isolate its outputs
ORCHESTRATOR_TEST_OUTPUT_DIR = TEST_OUTPUT_DIR_BASE / "orchestrator_test_run"
TEMP_SCENE_AUDIO_DIR_EXPECTED = ORCHESTRATOR_TEST_OUTPUT_DIR / "temp_scene_audio"
STOCK_VIDEO_DIR_EXPECTED = ORCHESTRATOR_TEST_OUTPUT_DIR / "stock_media" / "videos"
STOCK_IMAGE_DIR_EXPECTED = ORCHESTRATOR_TEST_OUTPUT_DIR / "stock_media" / "images"

# Prerequisite files (expected to be in test_outputs/ from e2e run)
# We will copy them to a test-specific input location for isolation if needed,
# or orchestrator will be modified to accept paths.
# For now, assume orchestrator reads from fixed paths in TEST_OUTPUT_DIR_BASE.
SCENE_PLAN_FILE_SRC = TEST_OUTPUT_DIR_BASE / "e2e_llm_scene_plan_output.json"
MASTER_VOICEOVER_FILE_SRC = TEST_OUTPUT_DIR_BASE / "How_Tencent_Bought_Its_Way_Into_AI_s_Top_8_master_vo.mp3"
ORIGINAL_SCRIPT_FILE_SRC = PROJECT_ROOT / "public" / "script.md"

# Mock S3 bucket and region if S3 client is used
S3_BUCKET_NAME_MOCK = "mock-test-bucket"
AWS_REGION_MOCK = "us-east-1"


class TestAssetOrchestrator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        logger.info("Setting up TestAssetOrchestrator class...")
        # Ensure the main test output directory for this test run exists and is clean
        if ORCHESTRATOR_TEST_OUTPUT_DIR.exists():
            shutil.rmtree(ORCHESTRATOR_TEST_OUTPUT_DIR)
        ORCHESTRATOR_TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Orchestrator test output dir: {ORCHESTRATOR_TEST_OUTPUT_DIR}")

        # Check for prerequisite files - skip all tests if not found
        cls.skip_all_tests = False
        if not SCENE_PLAN_FILE_SRC.exists():
            logger.error(f"Prerequisite scene plan file not found: {SCENE_PLAN_FILE_SRC}. Skipping tests.")
            cls.skip_all_tests = True
        if not MASTER_VOICEOVER_FILE_SRC.exists():
            logger.error(f"Prerequisite master voiceover file not found: {MASTER_VOICEOVER_FILE_SRC}. Skipping tests.")
            cls.skip_all_tests = True
        if not ORIGINAL_SCRIPT_FILE_SRC.exists():
            logger.error(f"Prerequisite original script file not found: {ORIGINAL_SCRIPT_FILE_SRC}. Skipping tests.")
            cls.skip_all_tests = True

        # API keys check - skip if any are missing for services we intend to call (even if mocked)
        # This ensures the orchestrator itself can initialize without erroring on os.getenv
        cls.FREESOUND_API_KEY = os.getenv("FREESOUND_API_KEY")
        cls.ARGIL_API_KEY = os.getenv("ARGIL_API_KEY")
        cls.PEXELS_API_KEY_ENV = os.getenv("PEXELS_API_KEY") # Added for Pexels
        cls.S3_BUCKET_NAME_ENV = os.getenv("S3_BUCKET_NAME") # Actual S3 bucket from .env
        cls.AWS_DEFAULT_REGION_ENV = os.getenv("AWS_DEFAULT_REGION")

        if not all([cls.FREESOUND_API_KEY, cls.ARGIL_API_KEY, cls.PEXELS_API_KEY_ENV, cls.S3_BUCKET_NAME_ENV, cls.AWS_DEFAULT_REGION_ENV]):
            logger.warning("One or more API keys/S3/Pexels configs missing in .env. Orchestrator might skip some operations. Tests will still run with mocks.")
            # We don't make this a skip_all_tests = True because mocks handle functionality,
            # but the orchestrator might log warnings about missing keys.

    def setUp(self):
        if TestAssetOrchestrator.skip_all_tests:
            self.skipTest("Skipping test due to missing prerequisite files.")

        # Patch the constants in asset_orchestrator to use our test-specific output dir
        # and specific S3 config for predictability in tests.
        self.patch_test_output_dir = patch('backend.video_pipeline.asset_orchestrator.TEST_OUTPUT_DIR', ORCHESTRATOR_TEST_OUTPUT_DIR)
        self.patch_s3_bucket = patch('backend.video_pipeline.asset_orchestrator.S3_BUCKET_NAME', S3_BUCKET_NAME_MOCK)
        self.patch_aws_region = patch('backend.video_pipeline.asset_orchestrator.AWS_DEFAULT_REGION', AWS_REGION_MOCK)

        self.mock_test_output_dir = self.patch_test_output_dir.start()
        self.mock_s3_bucket = self.patch_s3_bucket.start()
        self.mock_aws_region = self.patch_aws_region.start()

    def tearDown(self):
        self.patch_test_output_dir.stop()
        self.patch_s3_bucket.stop()
        self.patch_aws_region.stop()

    @patch('backend.video_pipeline.asset_orchestrator.find_and_download_photos')
    @patch('backend.video_pipeline.asset_orchestrator.find_and_download_videos')
    @patch('backend.video_pipeline.asset_orchestrator.render_argil_video')
    @patch('backend.video_pipeline.asset_orchestrator.create_argil_video_job')
    @patch('backend.video_pipeline.asset_orchestrator.upload_to_s3')
    @patch('backend.video_pipeline.asset_orchestrator.slice_audio')
    @patch('backend.video_pipeline.asset_orchestrator.find_and_download_music')
    @patch('backend.video_pipeline.asset_orchestrator.ensure_s3_bucket')
    @patch('backend.video_pipeline.asset_orchestrator.get_s3_client')
    def test_orchestrate_video_assets_all_types(self,
                                              mock_get_s3_client,
                                              mock_ensure_s3_bucket,
                                              mock_find_music,
                                              mock_slice_audio,
                                              mock_upload_to_s3,
                                              mock_create_argil_job,
                                              mock_render_argil_video,
                                              mock_find_pexels_videos,
                                              mock_find_pexels_photos):
        logger.info("Running test_orchestrate_video_assets_all_types...")

        # --- Configure Mocks ---
        # S3 Client Mocks
        mock_s3_client_instance = MagicMock()
        mock_get_s3_client.return_value = mock_s3_client_instance
        mock_ensure_s3_bucket.return_value = True # Assume bucket is fine

        # Freesound Mock
        mock_music_filename = "mock_background_music.mp3"
        mock_find_music.return_value = str(ORCHESTRATOR_TEST_OUTPUT_DIR / mock_music_filename)

        # Audio Slicing Mock
        mock_slice_audio.return_value = True # Simulate successful slicing

        # S3 Upload Mock
        mock_upload_to_s3.return_value = f"https://{S3_BUCKET_NAME_MOCK}.s3.{AWS_REGION_MOCK}.amazonaws.com/mock_audio_slice.mp3"

        # Argil Mocks
        mock_create_argil_job.return_value = {"success": True, "video_id": "mock_argil_video_id_123"}
        mock_render_argil_video.return_value = {"success": True, "data": {"status": "RENDERING"}}

        # Pexels Mocks
        mock_video_filename = "mock_stock_video.mp4"
        mock_find_pexels_videos.return_value = [str(STOCK_VIDEO_DIR_EXPECTED / mock_video_filename)]
        mock_image_filename = "mock_stock_image.jpg"
        mock_find_pexels_photos.return_value = [str(STOCK_IMAGE_DIR_EXPECTED / mock_image_filename)]

        # --- Run Orchestrator ---
        orchestrate_video_assets() # This will now use ORCHESTRATOR_TEST_OUTPUT_DIR

        # --- Assertions ---
        # 1. Music Download
        expected_music_output_path = ORCHESTRATOR_TEST_OUTPUT_DIR / "background_music.mp3"
        mock_find_music.assert_called_once()
        args, _ = mock_find_music.call_args
        self.assertIsInstance(args[1], str) # Query
        self.assertEqual(args[2], str(expected_music_output_path)) # output_path
        logger.info(f"Verified music download called with output: {expected_music_output_path}")

        # 2. S3 Client Initialization (if keys were present)
        if self.S3_BUCKET_NAME_ENV and self.AWS_DEFAULT_REGION_ENV and self.ARGIL_API_KEY:
            mock_get_s3_client.assert_called_once()
            mock_ensure_s3_bucket.assert_called_once_with(mock_s3_client_instance, S3_BUCKET_NAME_MOCK, region=AWS_REGION_MOCK)
            logger.info("Verified S3 client and bucket checks.")
        else:
            mock_get_s3_client.assert_not_called()
            logger.info("S3 client not expected to be called due to missing env vars for it.")

        # 3. Scene Processing (Focus on AVATAR, STOCK_VIDEO, and STOCK_IMAGE scenes from e2e_llm_scene_plan_output.json)
        # Load the scene plan to know how many avatar, stock video, and stock image scenes to expect calls for.
        with open(SCENE_PLAN_FILE_SRC, 'r') as f:
            scene_plans_data = json.load(f)

        avatar_scenes = [s for s in scene_plans_data if s["visual_type"] == "AVATAR"]
        stock_video_scenes = [s for s in scene_plans_data if s["visual_type"] == "STOCK_VIDEO"]
        stock_image_scenes = [s for s in scene_plans_data if s["visual_type"] == "STOCK_IMAGE"]
        num_avatar_scenes = len(avatar_scenes)
        num_stock_video_scenes = len(stock_video_scenes)
        num_stock_image_scenes = len(stock_image_scenes)

        if num_avatar_scenes > 0 and mock_get_s3_client.called: # Only if S3 client was set up
            self.assertEqual(mock_slice_audio.call_count, num_avatar_scenes)
            self.assertEqual(mock_upload_to_s3.call_count, num_avatar_scenes)
            self.assertEqual(mock_create_argil_job.call_count, num_avatar_scenes)
            self.assertEqual(mock_render_argil_video.call_count, num_avatar_scenes)
            logger.info(f"Verified correct number of calls for {num_avatar_scenes} avatar scenes.")

            # Detailed check for the first avatar scene call (example)
            first_avatar_scene = avatar_scenes[0]
            expected_slice_output_local_path_pattern = TEMP_SCENE_AUDIO_DIR_EXPECTED / f"video_project_*{first_avatar_scene['scene_id']}_audio.mp3"

            # Check slice_audio call
            slice_args, _ = mock_slice_audio.call_args_list[0]
            self.assertEqual(slice_args[0], str(MASTER_VOICEOVER_FILE_SRC)) # input_path
            # self.assertTrue(pathlib.Path(slice_args[1]).match(str(expected_slice_output_local_path_pattern))) # output_path with uuid
            self.assertTrue(str(slice_args[1]).startswith(str(TEMP_SCENE_AUDIO_DIR_EXPECTED / "video_project_"))) # Check prefix
            self.assertEqual(slice_args[2], first_avatar_scene["start_time"]) # start_seconds
            self.assertEqual(slice_args[3], first_avatar_scene["end_time"])   # end_seconds
            logger.info("Verified first slice_audio call parameters.")

            # Check upload_to_s3 call
            upload_args, _ = mock_upload_to_s3.call_args_list[0]
            # self.assertTrue(pathlib.Path(upload_args[1]).match(str(expected_slice_output_local_path_pattern))) # local_file_path
            self.assertTrue(str(upload_args[1]).startswith(str(TEMP_SCENE_AUDIO_DIR_EXPECTED / "video_project_"))) # Check prefix
            self.assertEqual(upload_args[2], S3_BUCKET_NAME_MOCK) # bucket_name
            self.assertTrue(upload_args[3].endswith(f"{first_avatar_scene['scene_id']}_audio.mp3")) # s3_key
            logger.info("Verified first upload_to_s3 call parameters.")

            # Check create_argil_video_job call
            actual_call_kwargs = mock_create_argil_job.call_args_list[0].kwargs

            self.assertEqual(actual_call_kwargs['api_key'], self.ARGIL_API_KEY)
            self.assertTrue(actual_call_kwargs['video_title'].endswith(f"{first_avatar_scene['scene_id']}_Avatar"))
            self.assertEqual(actual_call_kwargs['full_transcript'], first_avatar_scene['text_for_scene'])
            moment_payload = actual_call_kwargs['moments_payload'][0]
            self.assertEqual(moment_payload['transcript'], first_avatar_scene['text_for_scene'])
            self.assertEqual(moment_payload['audioUrl'], mock_upload_to_s3.return_value)
            self.assertEqual(moment_payload['gestureSlug'], DEFAULT_GESTURE_SLUGS[0]) # Check the assigned gesture
            logger.info("Verified first create_argil_video_job call parameters and moment payload.")

            # Check render_argil_video call
            render_args_tuple, _ = mock_render_argil_video.call_args_list[0] # render_argil_video called with positional args
            self.assertEqual(render_args_tuple[0], self.ARGIL_API_KEY) # api_key
            self.assertEqual(render_args_tuple[1], "mock_argil_video_id_123") # video_id
            logger.info("Verified first render_argil_video call parameters.")

        elif num_avatar_scenes > 0 and not mock_get_s3_client.called:
             logger.warning("AVATAR scenes exist in plan, but S3 client mock was not called (likely due to missing S3 env vars). Argil calls skipped by orchestrator.")
             mock_slice_audio.assert_not_called()
             mock_upload_to_s3.assert_not_called()
             mock_create_argil_job.assert_not_called()
             mock_render_argil_video.assert_not_called()

        # Stock Video scenes assertions
        if num_stock_video_scenes > 0 and self.PEXELS_API_KEY_ENV:
            self.assertEqual(mock_find_pexels_videos.call_count, num_stock_video_scenes)
            first_stock_video_scene = stock_video_scenes[0]
            video_call_args = mock_find_pexels_videos.call_args_list[0].kwargs
            self.assertEqual(video_call_args['api_key'], self.PEXELS_API_KEY_ENV)
            self.assertEqual(video_call_args['query'], first_stock_video_scene['visual_keywords'][0])
            self.assertEqual(video_call_args['count'], 1)
            self.assertEqual(video_call_args['output_dir'], str(STOCK_VIDEO_DIR_EXPECTED))
            logger.info("Verified Pexels video download calls.")
        elif num_stock_video_scenes > 0 and not self.PEXELS_API_KEY_ENV:
            mock_find_pexels_videos.assert_not_called()
            logger.info("Pexels video client not expected to be called due to missing PEXELS_API_KEY.")

        # Stock Image scenes assertions
        if num_stock_image_scenes > 0 and self.PEXELS_API_KEY_ENV:
            self.assertEqual(mock_find_pexels_photos.call_count, num_stock_image_scenes)
            first_stock_image_scene = stock_image_scenes[0]
            image_call_args = mock_find_pexels_photos.call_args_list[0].kwargs
            self.assertEqual(image_call_args['api_key'], self.PEXELS_API_KEY_ENV)
            self.assertEqual(image_call_args['query'], first_stock_image_scene['visual_keywords'][0])
            self.assertEqual(image_call_args['count'], 1)
            self.assertEqual(image_call_args['output_dir'], str(STOCK_IMAGE_DIR_EXPECTED))
            logger.info("Verified Pexels image download calls.")
        elif num_stock_image_scenes > 0 and not self.PEXELS_API_KEY_ENV:
            mock_find_pexels_photos.assert_not_called()
            logger.info("Pexels image client not expected to be called due to missing PEXELS_API_KEY.")

        # Verify that the temp_scene_audio directory was created inside ORCHESTRATOR_TEST_OUTPUT_DIR
        self.assertTrue((ORCHESTRATOR_TEST_OUTPUT_DIR / "temp_scene_audio").exists())
        self.assertTrue((ORCHESTRATOR_TEST_OUTPUT_DIR / "temp_scene_audio").is_dir())
        logger.info("Verified creation of temp_scene_audio directory.")

        # Verify creation of output directories
        self.assertTrue(TEMP_SCENE_AUDIO_DIR_EXPECTED.exists() and TEMP_SCENE_AUDIO_DIR_EXPECTED.is_dir())
        self.assertTrue(STOCK_VIDEO_DIR_EXPECTED.exists() and STOCK_VIDEO_DIR_EXPECTED.is_dir())
        self.assertTrue(STOCK_IMAGE_DIR_EXPECTED.exists() and STOCK_IMAGE_DIR_EXPECTED.is_dir())
        logger.info("Verified creation of all expected output subdirectories.")

if __name__ == '__main__':
    unittest.main()
