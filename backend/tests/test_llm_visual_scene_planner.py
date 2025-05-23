import unittest
import json
import os # Added for path joining

class TestLLMVisualScenePlanner(unittest.TestCase):

    def get_mock_word_transcript(self):
        """Provides a mock word-level transcript."""
        return [
            {"word": "Tencent", "start": 0.5, "end": 0.9, "speaker": "SPEAKER_00"},
            {"word": "just", "start": 0.9, "end": 1.1, "speaker": "SPEAKER_00"},
            {"word": "spent", "start": 1.1, "end": 1.5, "speaker": "SPEAKER_00"},
            {"word": "4", "start": 1.55, "end": 1.8, "speaker": "SPEAKER_00"},
            {"word": "billion", "start": 1.8, "end": 2.2, "speaker": "SPEAKER_00"},
            {"word": "dollars", "start": 2.2, "end": 2.6, "speaker": "SPEAKER_00"},
            {"word": "on", "start": 2.65, "end": 2.8, "speaker": "SPEAKER_00"},
            {"word": "AI", "start": 2.8, "end": 3.1, "speaker": "SPEAKER_00"},
            {"word": "in", "start": 3.15, "end": 3.3, "speaker": "SPEAKER_00"},
            {"word": "three", "start": 3.3, "end": 3.6, "speaker": "SPEAKER_00"},
            {"word": "months.", "start": 3.6, "end": 4.0, "speaker": "SPEAKER_00"}, # Scene 1 end (3.5s)
            {"word": "This", "start": 4.5, "end": 4.8, "speaker": "SPEAKER_00"},
            {"word": "is", "start": 4.8, "end": 5.0, "speaker": "SPEAKER_00"},
            {"word": "a", "start": 5.0, "end": 5.1, "speaker": "SPEAKER_00"},
            {"word": "major", "start": 5.1, "end": 5.5, "speaker": "SPEAKER_00"},
            {"word": "leap.", "start": 5.5, "end": 5.9, "speaker": "SPEAKER_00"}, # Scene 2 end (1.4s) - candidate for photo
            {"word": "They", "start": 6.8, "end": 7.0, "speaker": "SPEAKER_00"},
            {"word": "are", "start": 7.0, "end": 7.2, "speaker": "SPEAKER_00"},
            {"word": "showing", "start": 7.2, "end": 7.6, "speaker": "SPEAKER_00"},
            {"word": "real", "start": 7.6, "end": 7.9, "speaker": "SPEAKER_00"},
            {"word": "commitment", "start": 7.9, "end": 8.5, "speaker": "SPEAKER_00"},
            {"word": "now.", "start": 8.5, "end": 8.8, "speaker": "SPEAKER_00"}, # Scene 3 end (2.0s)
        ]

    def get_mock_script_json(self):
        """Provides a mock script JSON (like public/script.md)."""
        return {
            "video_structure": {
                "throughline": "Tencent's massive AI investment yields rapid advancement.",
                "title": "Tencent's AI Surge",
                "duration": "75 seconds",
                "target_audience": "Tech enthusiasts"
            },
            "script_segments": {
                "hook": {
                    "order_id": 1,
                    "voiceover": "Tencent just spent 4 billion dollars on AI in three months. This is a major leap. They are showing real commitment now.",
                    "visual_direction": "Financial charts, ranking charts",
                    "b_roll_keywords": ["AI investment", "financial growth", "global ranking"]
                },
                "conflict": { # ... other segments
                    "order_id": 2, "voiceover": "...", "b_roll_keywords": []
                },
                "body": { # ... other segments
                    "order_id": 3, "voiceover": "...", "b_roll_keywords": []
                },
                "conclusion": { # ... other segments
                    "order_id": 4, "voiceover": "...", "b_roll_keywords": []
                }
            },
            "production_notes": {
                "music_vibe": "upbeat electronic, tech-forward",
                "overall_tone": "Analytical and provocative"
            }
        }

    def get_mock_config(self):
        """Provides mock configuration relevant to scene planning."""
        return {
            "video_general": {
                "TARGET_FPS": 30,
                "TARGET_DIMENSIONS": [1080, 1920] # width, height for TikTok
            },
            "llm_scene_planner": {
                "MAX_SEGMENT_DURATION": 5.0, # seconds, desired max for LLM scenes
                "MIN_SEGMENT_DURATION": 1.0, # seconds, desired min for LLM scenes
                "PHOTO_SEGMENT_THRESHOLD": 1.5, # seconds, below or equal to this, prefer photo
                "MAX_KEYWORDS_PER_SCENE": 5,
                "AVATAR_SCENE_PREFERENCE": "first_scene_of_hook", # "first_scene_overall", "first_scene_of_each_part"
                "STOCK_SOURCES": ["pexels", "pixabay"], # For later use if LLM needs to know
                "STOCK_SELECTION_STRATEGY": "random_source_first_match" # For later use
            }
        }

    def get_conceptual_llm_prompt_structure(self):
        """
        Reads the conceptual LLM prompt template from an external file.
        This test now primarily verifies that the placeholders in the template file are as expected.
        The actual filling of these placeholders will be done by the LLM client/E2E test.
        """
        # Construct the path to the prompt template file
        # Assuming this test file is in backend/tests/
        # and the prompt is in backend/prompts/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_template_path = os.path.join(
            current_dir,
            "..", # up to backend/
            "prompts",
            "visual_scene_planner_prompt_template.md"
        )

        try:
            with open(prompt_template_path, 'r') as f:
                prompt_template_content = f.read()
        except FileNotFoundError:
            self.fail(f"Prompt template file not found at {prompt_template_path}")

        return prompt_template_content

    def get_expected_llm_output_structure(self):
        """
        This is an example of the kind of structured output the LLM should produce.
        The actual content will depend on the LLM's processing of the inputs and config.
        """
        mock_config = self.get_mock_config() # To access PHOTO_SEGMENT_THRESHOLD for example
        photo_threshold = mock_config['llm_scene_planner']['PHOTO_SEGMENT_THRESHOLD']

        scene1_duration = 4.0 - 0.5 # 3.5s
        scene2_duration = 5.9 - 4.5 # 1.4s
        scene3_duration = 8.8 - 6.8 # 2.0s

        scene2_visual_type = "STOCK_IMAGE" if scene2_duration <= photo_threshold else "STOCK_VIDEO"

        return [
            {
                "scene_id": "001",
                "start_time": 0.5,
                "end_time": 4.0,
                "text_for_scene": "Tencent just spent 4 billion dollars on AI in three months.", # Concatenated from mock_word_transcript
                "original_script_part_ref": "hook",
                "visual_type": "AVATAR", # Based on mock_config preference "first_scene_of_hook"
                "visual_keywords": ["Tencent", "AI investment", "4 billion dollars", "tech spending"],
                "fx_suggestion": {
                    "type": "TEXT_OVERLAY_FADE",
                    "text_content": "$4 Billion",
                    "params": {
                        "font_props": {"font": "Impact", "fontsize": 90, "color": "yellow"},
                        "is_transparent": True,
                        "position": ("center", "center")
                    }
                }
            },
            {
                "scene_id": "002",
                "start_time": 4.5,
                "end_time": 5.9, # Duration 1.4s
                "text_for_scene": "This is a major leap.", # Concatenated
                "original_script_part_ref": "hook",
                "visual_type": scene2_visual_type, # Should be STOCK_IMAGE if PHOTO_SEGMENT_THRESHOLD >= 1.4
                "visual_keywords": ["major leap", "progress", "advancement", "tech jump"],
                "fx_suggestion": None # Or null
            },
            {
                "scene_id": "003",
                "start_time": 6.8,
                "end_time": 8.8, # Duration 2.0s
                "text_for_scene": "They are showing real commitment now.", # Concatenated
                "original_script_part_ref": "hook",
                "visual_type": "STOCK_VIDEO", # Duration > PHOTO_SEGMENT_THRESHOLD (assuming 1.5s threshold)
                "visual_keywords": ["commitment", "business strategy", "corporate dedication", "tech focus"],
                "fx_suggestion": None # Or null
            }
            # ... more scenes would follow for the rest of the transcript
        ]

    def test_llm_scene_planner_contract(self):
        """
        This test doesn't call an LLM. It verifies our understanding of:
        1. The inputs the LLM will need.
        2. The conceptual structure of the prompt.
        3. The expected JSON output format from the LLM.
        """
        mock_transcript = self.get_mock_word_transcript()
        mock_script = self.get_mock_script_json()
        mock_config = self.get_mock_config()

        # The conceptual prompt structure is now the raw template content
        prompt_template_content = self.get_conceptual_llm_prompt_structure()
        expected_output_example = self.get_expected_llm_output_structure()

        # 1. Verify inputs are what we expect to provide
        self.assertIsInstance(mock_transcript, list)
        self.assertIsInstance(mock_script, dict)
        self.assertIsInstance(mock_config, dict)
        self.assertTrue(all("word" in item and "start" in item and "end" in item for item in mock_transcript))
        self.assertIn("video_structure", mock_script)
        self.assertIn("script_segments", mock_script)
        self.assertIn("llm_scene_planner", mock_config)
        self.assertIn("video_general", mock_config)

        # Check specific config keys used in prompt/logic
        self.assertIn("MAX_SEGMENT_DURATION", mock_config["llm_scene_planner"])
        self.assertIn("MIN_SEGMENT_DURATION", mock_config["llm_scene_planner"])
        self.assertIn("PHOTO_SEGMENT_THRESHOLD", mock_config["llm_scene_planner"])


        # 2. Verify prompt structure (conceptual)
        self.assertIn("Objective:", prompt_template_content)
        self.assertIn("Word-Level Transcript:", prompt_template_content)
        self.assertIn("Original Script Context:", prompt_template_content)
        self.assertIn("Configuration Guidance:", prompt_template_content)
        # Ensure these assertions look for the literal placeholders in the template file
        self.assertIn("Desired scene duration: {{min_segment_duration}} to {{max_segment_duration}} seconds.", prompt_template_content)
        self.assertIn("Threshold for using an image: If scene duration is <= {{photo_segment_threshold}} seconds, prefer 'STOCK_IMAGE'.", prompt_template_content)
        self.assertIn("Task:", prompt_template_content)
        self.assertIn("Output Format:", prompt_template_content)
        # Check for placeholders (conceptual check) - these should match the .md file
        self.assertIn("{{word_transcript_json_string}}", prompt_template_content)
        self.assertIn("{{script_json_string}}", prompt_template_content)
        self.assertIn("{{config_json_string}}", prompt_template_content)
        self.assertIn("{{min_segment_duration}}", prompt_template_content)
        self.assertIn("{{max_segment_duration}}", prompt_template_content)
        self.assertIn("{{photo_segment_threshold}}", prompt_template_content)
        self.assertIn("{{max_keywords_per_scene}}", prompt_template_content)
        self.assertIn("{{avatar_scene_preference}}", prompt_template_content)


        # 3. Verify expected output structure
        self.assertIsInstance(expected_output_example, list)
        for scene_plan in expected_output_example:
            self.assertIsInstance(scene_plan, dict)
            self.assertIn("scene_id", scene_plan)
            self.assertIsInstance(scene_plan["scene_id"], str)
            self.assertIn("start_time", scene_plan)
            self.assertIsInstance(scene_plan["start_time"], float)
            self.assertIn("end_time", scene_plan)
            self.assertIsInstance(scene_plan["end_time"], float)
            # Verify scene duration constraint (conceptual for expected output)
            duration = scene_plan["end_time"] - scene_plan["start_time"]
            self.assertGreaterEqual(duration, mock_config['llm_scene_planner']['MIN_SEGMENT_DURATION'] - 0.01) # allow for float precision
            self.assertLessEqual(duration, mock_config['llm_scene_planner']['MAX_SEGMENT_DURATION'] + 0.01)


            self.assertIn("text_for_scene", scene_plan)
            self.assertIsInstance(scene_plan["text_for_scene"], str)
            self.assertIn("original_script_part_ref", scene_plan)
            self.assertIsInstance(scene_plan["original_script_part_ref"], str)

            self.assertIn("visual_type", scene_plan)
            self.assertIn(scene_plan["visual_type"], ["AVATAR", "STOCK_VIDEO", "STOCK_IMAGE"]) # Updated enum

            # Verify PHOTO_SEGMENT_THRESHOLD logic in expected output
            if scene_plan["visual_type"] != "AVATAR":
                if duration <= mock_config['llm_scene_planner']['PHOTO_SEGMENT_THRESHOLD']:
                    self.assertEqual(scene_plan["visual_type"], "STOCK_IMAGE", f"Scene {scene_plan['scene_id']} duration {duration}s should be STOCK_IMAGE")
                else:
                    self.assertEqual(scene_plan["visual_type"], "STOCK_VIDEO", f"Scene {scene_plan['scene_id']} duration {duration}s should be STOCK_VIDEO")


            self.assertIn("visual_keywords", scene_plan)
            self.assertIsInstance(scene_plan["visual_keywords"], list)
            self.assertTrue(all(isinstance(kw, str) for kw in scene_plan["visual_keywords"]))

            self.assertIn("fx_suggestion", scene_plan)
            if scene_plan["fx_suggestion"] is not None: # fx_suggestion can be null
                self.assertIsInstance(scene_plan["fx_suggestion"], dict)
                self.assertIn("type", scene_plan["fx_suggestion"])
                self.assertIsInstance(scene_plan["fx_suggestion"]["type"], str)
                self.assertIn("text_content", scene_plan["fx_suggestion"])
                self.assertIsInstance(scene_plan["fx_suggestion"]["text_content"], str)
                self.assertIn("params", scene_plan["fx_suggestion"])
                self.assertIsInstance(scene_plan["fx_suggestion"]["params"], dict)

        print("\nTestLLMVisualScenePlanner: Contract definition test passed (with updated constraints).")
        # print(f"  Conceptual Prompt Structure:\n{'-'*20}\n{prompt_template_content}\n{'-'*20}")
        # print(f"  Example Expected Output (format validated):\n{'-'*20}\n{json.dumps(expected_output_example, indent=2)}\n{'-'*20}")

if __name__ == '__main__':
    unittest.main()
