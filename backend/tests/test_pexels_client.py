import unittest
import os
import shutil
import logging
import sys
from dotenv import load_dotenv
from unittest.mock import patch, MagicMock

# Adjust sys.path to allow importing from the backend directory
# This assumes the test script is in backend/tests and wanx is the project root.
# So, ../.. should point to the 'wanx' directory.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.text_to_video.pexels_client import find_and_download_videos, find_and_download_photos

# Suppress all logging output during tests, re-enable Critical for Pexels client errors if needed
# logging.disable(logging.INFO) # Or logging.CRITICAL to see only critical errors from pexels_client

class TestPexelsClient(unittest.TestCase):
    PEXELS_API_KEY = None
    # Place test downloads in a directory relative to this test file, inside backend/tests/
    TEST_OUTPUT_DIR_NAME = "test_pexels_client_downloads"
    TEST_OUTPUT_DIR = "" # Will be set in setUpClass

    @classmethod
    def setUpClass(cls):
        load_dotenv()
        cls.PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

        # Create test output directory within backend/tests/
        cls.TEST_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), cls.TEST_OUTPUT_DIR_NAME)

        if os.path.exists(cls.TEST_OUTPUT_DIR):
            shutil.rmtree(cls.TEST_OUTPUT_DIR)
        os.makedirs(cls.TEST_OUTPUT_DIR, exist_ok=True)

        # Suppress logging from the pexels_client and other modules for cleaner test output
        # You might want to set this to logging.DEBUG if you are debugging the tests themselves.
        logging.basicConfig(level=logging.CRITICAL) # Show only CRITICAL logs from any logger
        cls.pexels_client_logger = logging.getLogger('backend.text_to_video.pexels_client')
        cls.original_pexels_logger_level = cls.pexels_client_logger.getEffectiveLevel()
        cls.pexels_client_logger.setLevel(logging.CRITICAL)


    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.TEST_OUTPUT_DIR):
            shutil.rmtree(cls.TEST_OUTPUT_DIR)
        # Restore logger level
        cls.pexels_client_logger.setLevel(cls.original_pexels_logger_level)


    # --- Video Tests ---
    @unittest.skipIf(not os.getenv("PEXELS_API_KEY"), "PEXELS_API_KEY not found. Skipping live API video test.")
    def test_01_download_videos_success_live(self):
        query = "office work"
        count = 1
        downloaded_files = find_and_download_videos(self.PEXELS_API_KEY, query, count, self.TEST_OUTPUT_DIR)
        self.assertEqual(len(downloaded_files), count, f"Expected {count} video, got {len(downloaded_files)}")
        for f_path in downloaded_files:
            self.assertTrue(os.path.exists(f_path), f"File {f_path} should exist.")
            self.assertTrue(os.path.getsize(f_path) > 0, f"File {f_path} should not be empty.")
            self.assertTrue(os.path.dirname(f_path) == self.TEST_OUTPUT_DIR, f"File {f_path} should be in {self.TEST_OUTPUT_DIR}")
            self.assertTrue(os.path.basename(f_path).startswith("pexels_"), f"Filename {os.path.basename(f_path)} incorrect.")
            self.assertTrue(os.path.basename(f_path).endswith(".mp4"))

    def test_02_download_videos_no_api_key(self):
        downloaded_files = find_and_download_videos("", "test", 1, self.TEST_OUTPUT_DIR)
        self.assertEqual(len(downloaded_files), 0, "Expected 0 files with no API key for videos.")

    @unittest.skipIf(not os.getenv("PEXELS_API_KEY"), "PEXELS_API_KEY not found. Skipping live API video test for no results.")
    def test_03_download_videos_no_results_live(self):
        query = "zzxxccvvbbnnmmaassddffgg" # Highly unlikely query
        downloaded_files = find_and_download_videos(self.PEXELS_API_KEY, query, 1, self.TEST_OUTPUT_DIR)
        self.assertEqual(len(downloaded_files), 0, f"Expected 0 videos for unlikely query '{query}'.")

    # --- Photo Tests ---
    @unittest.skipIf(not os.getenv("PEXELS_API_KEY"), "PEXELS_API_KEY not found. Skipping live API photo test.")
    def test_04_download_photos_success_live(self):
        query = "modern city"
        count = 1
        downloaded_files = find_and_download_photos(self.PEXELS_API_KEY, query, count, self.TEST_OUTPUT_DIR, orientation="landscape")
        self.assertEqual(len(downloaded_files), count, f"Expected {count} photo, got {len(downloaded_files)}")
        for f_path in downloaded_files:
            self.assertTrue(os.path.exists(f_path), f"File {f_path} should exist.")
            self.assertTrue(os.path.getsize(f_path) > 0, f"File {f_path} should not be empty.")
            self.assertTrue(os.path.dirname(f_path) == self.TEST_OUTPUT_DIR, f"File {f_path} should be in {self.TEST_OUTPUT_DIR}")
            self.assertTrue(os.path.basename(f_path).startswith("pexels_photo_"), f"Filename {os.path.basename(f_path)} incorrect.")
            self.assertTrue(os.path.basename(f_path).lower().endswith((".jpg", ".jpeg", ".png")))


    def test_05_download_photos_no_api_key(self):
        downloaded_files = find_and_download_photos("", "test", 1, self.TEST_OUTPUT_DIR)
        self.assertEqual(len(downloaded_files), 0, "Expected 0 files with no API key for photos.")

    @unittest.skipIf(not os.getenv("PEXELS_API_KEY"), "PEXELS_API_KEY not found. Skipping live API photo test for no results.")
    def test_06_download_photos_no_results_live(self):
        query = "qqwweerrttyyuuiiooppåååå" # Highly unlikely query
        downloaded_files = find_and_download_photos(self.PEXELS_API_KEY, query, 1, self.TEST_OUTPUT_DIR)
        self.assertEqual(len(downloaded_files), 0, f"Expected 0 photos for unlikely query '{query}'.")

    # --- Mocked Tests ---
    @patch('backend.text_to_video.pexels_client.requests.get')
    def test_07_download_videos_mocked(self, mock_get):
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "videos": [{
                "id": 12345,
                "video_files": [{"quality": "hd", "file_type": "video/mp4", "link": "http://fakeurl.com/fakevideo.mp4"}]
            }], "total_results": 1, "page": 1, "per_page": 1
        }

        mock_download_response = MagicMock()
        mock_download_response.status_code = 200
        mock_download_response.iter_content.return_value = [b"fake video data chunk 1", b"fake video data chunk 2"]

        mock_get.side_effect = [mock_api_response, mock_download_response]

        downloaded_files = find_and_download_videos("FAKE_KEY", "mocked video", 1, self.TEST_OUTPUT_DIR)
        self.assertEqual(len(downloaded_files), 1)
        self.assertTrue(os.path.exists(downloaded_files[0]))
        with open(downloaded_files[0], 'rb') as f:
            content = f.read()
            self.assertEqual(content, b"fake video data chunk 1fake video data chunk 2")

        expected_video_search_params = {'query': 'mocked video', 'per_page': 2, 'orientation': 'portrait', 'size': 'medium'}
        mock_get.assert_any_call("https://api.pexels.com/videos/search", headers={"Authorization": "FAKE_KEY"}, params=expected_video_search_params, timeout=15)
        mock_get.assert_any_call("http://fakeurl.com/fakevideo.mp4", stream=True, timeout=60)


    @patch('backend.text_to_video.pexels_client.requests.get')
    def test_08_download_photos_mocked(self, mock_get):
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "photos": [{
                "id": 54321, "src": {"large": "http://fakeurl.com/fakephoto.jpeg"} # ensure .jpeg for filename test
            }], "total_results": 1, "page": 1, "per_page": 1
        }

        mock_download_response = MagicMock()
        mock_download_response.status_code = 200
        mock_download_response.iter_content.return_value = [b"fake photo data"]

        mock_get.side_effect = [mock_api_response, mock_download_response]

        downloaded_files = find_and_download_photos("FAKE_KEY", "mocked photo", 1, self.TEST_OUTPUT_DIR, orientation="square", size="small")
        self.assertEqual(len(downloaded_files), 1)
        self.assertTrue(os.path.exists(downloaded_files[0]))
        self.assertTrue(downloaded_files[0].endswith(".jpeg"))
        with open(downloaded_files[0], 'rb') as f:
            self.assertEqual(f.read(), b"fake photo data")

        expected_photo_search_params = {'query': 'mocked photo', 'per_page': 2, 'orientation': 'square', 'size': 'small'}
        mock_get.assert_any_call("https://api.pexels.com/v1/search", headers={"Authorization": "FAKE_KEY"}, params=expected_photo_search_params, timeout=15)
        mock_get.assert_any_call("http://fakeurl.com/fakephoto.jpeg", stream=True, timeout=60)

if __name__ == '__main__':
    # Need to import sys for this part if not already imported at the top
    # import sys
    # The sys.path manipulation should ideally be at the very top of the script
    # or handled by the test runner environment.
    unittest.main()
