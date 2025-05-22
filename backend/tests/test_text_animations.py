import unittest
import os
from moviepy.editor import VideoClip # For type hinting, actual clips are CompositeVideoClip

# Adjust path to import from the parent directory's fx module
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'text_to_video', 'fx'))

from text_animations import animate_text_fade, animate_text_scale

# Define a directory for test outputs within the tests directory
BASE_TEST_DIR = os.path.dirname(__file__) # Gets the directory of the current test file
TEST_OUTPUT_DIR = os.path.join(BASE_TEST_DIR, "output")
DEFAULT_FPS = 24

class TestTextAnimations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(TEST_OUTPUT_DIR):
            os.makedirs(TEST_OUTPUT_DIR)
            print(f"Created test output directory: {TEST_OUTPUT_DIR}")
        else:
            print(f"Test output directory already exists: {TEST_OUTPUT_DIR}")

    def test_animate_text_fade_basic(self):
        """Test basic functionality of animate_text_fade."""
        screen_size = (1280, 720)
        total_duration = 3.0
        text_content = "Test Fade"
        font_props = {'fontsize': 50, 'color': 'white'}
        output_filename = "test_fade_basic.mp4"

        clip = animate_text_fade(
            text_content=text_content,
            total_duration=total_duration,
            screen_size=screen_size,
            font_props=font_props,
            fadein_duration=0.5,
            fadeout_duration=0.5,
            is_transparent=True
        )

        self.assertIsNotNone(clip)
        self.assertIsInstance(clip, VideoClip)
        self.assertEqual(clip.duration, total_duration)
        self.assertEqual(clip.size, screen_size)

        # Save for manual inspection
        clip.write_videofile(os.path.join(TEST_OUTPUT_DIR, output_filename), fps=DEFAULT_FPS, logger=None)
        print(f"Saved test video: {os.path.join(TEST_OUTPUT_DIR, output_filename)}")

    def test_animate_text_fade_no_fade(self):
        """Test animate_text_fade with zero fade durations."""
        screen_size = (800, 600)
        total_duration = 2.0
        output_filename = "test_fade_no_fade.mp4"
        clip = animate_text_fade(
            text_content="No Fade Test",
            total_duration=total_duration,
            screen_size=screen_size,
            fadein_duration=0,
            fadeout_duration=0,
            is_transparent=False,
            bg_color=(10,20,30)
        )
        self.assertEqual(clip.duration, total_duration)
        self.assertEqual(clip.size, screen_size)
        clip.write_videofile(os.path.join(TEST_OUTPUT_DIR, output_filename), fps=DEFAULT_FPS, logger=None)
        print(f"Saved test video: {os.path.join(TEST_OUTPUT_DIR, output_filename)}")

    def test_animate_text_fade_long_fades_adjusted(self):
        """Test that fade durations are adjusted if they exceed total_duration."""
        screen_size = (1920, 1080)
        total_duration = 1.0 # Short duration
        output_filename = "test_fade_long_fades_adjusted.mp4"
        clip = animate_text_fade(
            text_content="Long Fades Adjusted",
            total_duration=total_duration,
            screen_size=screen_size,
            fadein_duration=1.0,
            fadeout_duration=1.0
        )
        self.assertEqual(clip.duration, total_duration)
        self.assertEqual(clip.size, screen_size)
        clip.write_videofile(os.path.join(TEST_OUTPUT_DIR, output_filename), fps=DEFAULT_FPS, logger=None)
        print(f"Saved test video: {os.path.join(TEST_OUTPUT_DIR, output_filename)}")

    # --- Tests for animate_text_scale ---

    def test_animate_text_scale_basic_zoom_in(self):
        """Test basic zoom-in functionality of animate_text_scale."""
        screen_size = (1280, 720)
        total_duration = 2.5
        text_content = "Test Scale Up"
        output_filename = "test_scale_up_basic.mp4"

        clip = animate_text_scale(
            text_content=text_content,
            total_duration=total_duration,
            screen_size=screen_size,
            start_scale=0.5,
            end_scale=1.5,
            is_transparent=True,
            apply_fade=True
        )
        self.assertIsNotNone(clip)
        self.assertIsInstance(clip, VideoClip)
        self.assertEqual(clip.duration, total_duration)
        self.assertEqual(clip.size, screen_size)
        clip.write_videofile(os.path.join(TEST_OUTPUT_DIR, output_filename), fps=DEFAULT_FPS, logger=None)
        print(f"Saved test video: {os.path.join(TEST_OUTPUT_DIR, output_filename)}")

    def test_animate_text_scale_zoom_out_no_fade(self):
        """Test zoom-out functionality without the fade."""
        screen_size = (1024, 768)
        total_duration = 3.0
        output_filename = "test_scale_zoom_out_no_fade.mp4"
        clip = animate_text_scale(
            text_content="Zoom Out No Fade",
            total_duration=total_duration,
            screen_size=screen_size,
            start_scale=2.0,
            end_scale=0.8,
            is_transparent=False,
            bg_color=(0,0,100),
            apply_fade=False
        )
        self.assertEqual(clip.duration, total_duration)
        self.assertEqual(clip.size, screen_size)
        clip.write_videofile(os.path.join(TEST_OUTPUT_DIR, output_filename), fps=DEFAULT_FPS, logger=None)
        print(f"Saved test video: {os.path.join(TEST_OUTPUT_DIR, output_filename)}")

    def test_animate_text_scale_no_scale_change(self):
        """Test animate_text_scale when start and end scales are the same."""
        screen_size = (1920, 1080)
        total_duration = 1.5
        output_filename = "test_scale_no_scale_change.mp4"
        clip = animate_text_scale(
            text_content="No Scale Change",
            total_duration=total_duration,
            screen_size=screen_size,
            start_scale=1.0,
            end_scale=1.0,
            apply_fade=True
        )
        self.assertEqual(clip.duration, total_duration)
        self.assertEqual(clip.size, screen_size)
        clip.write_videofile(os.path.join(TEST_OUTPUT_DIR, output_filename), fps=DEFAULT_FPS, logger=None)
        print(f"Saved test video: {os.path.join(TEST_OUTPUT_DIR, output_filename)}")

if __name__ == '__main__':
    unittest.main()
