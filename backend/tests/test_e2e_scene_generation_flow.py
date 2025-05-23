import unittest
import os
import json
import yaml
import logging
import pathlib
import shutil # Added for moving files
import subprocess # Added for ffprobe
from dotenv import load_dotenv

# Ensure paths are relative to the project root for consistency
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

# Add project root to sys.path to allow imports from backend module
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from backend.text_to_video.tts import text_to_speech, sanitize_filename
from backend.text_to_video.fx.transcriber import transcribe_locally
from backend.text_to_video.llm_clients.claude_client import ClaudeClient

# Configure basic logging for the test
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables (especially for API keys)
load_dotenv(PROJECT_ROOT / ".env")

CONFIG_FILE_PATH = PROJECT_ROOT / "backend" / "tests" / "test_config.yaml"
PROMPT_TEMPLATE_PATH = PROJECT_ROOT / "backend" / "prompts" / "visual_scene_planner_prompt_template.md"
TECH_IN_ASIA_SCRIPT_PROMPT_PATH = PROJECT_ROOT / "config" / "tech_in_asia_script_prompt.md"

# TEST_OUTPUT_BASE_DIR = PROJECT_ROOT / "test_outputs" # Will be loaded from config

# Specific sub-directory for this test run's artifacts will be derived from config/story name

def load_test_config():
    if not CONFIG_FILE_PATH.exists():
        raise FileNotFoundError(f"Test config file not found at {CONFIG_FILE_PATH}")
    with open(CONFIG_FILE_PATH, 'r') as f:
        return yaml.safe_load(f)

def get_prompt_template(template_path: pathlib.Path) -> str:
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template file not found at {template_path}")
    with open(template_path, 'r') as f:
        return f.read()

class TestE2ESceneGenerationFlow(unittest.TestCase):

    # Class-level variables to store results between test steps
    config = None
    elevenlabs_api_key = None
    anthropic_api_key = None
    story_content = None
    script_data = None
    full_voiceover_text = None
    master_audio_path_str = None # This will now point to the path in TEST_OUTPUT_DIR
    word_level_transcript = None
    scene_plans_raw = None

    # Variables for FPS and Dimensions from config
    target_fps = None
    target_dimensions = None

    # Output directory for this specific test run
    current_test_output_dir = None

    @classmethod
    def setUpClass(cls):
        logger.info("Setting up E2E test class...")
        cls.config = load_test_config()
        cls.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        cls.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        # Load video general config
        video_general_config = cls.config.get("video_general", {})
        cls.target_fps = video_general_config.get("TARGET_FPS", 30)
        cls.target_dimensions = tuple(video_general_config.get("TARGET_DIMENSIONS", [1080, 1920]))
        if len(cls.target_dimensions) != 2:
            logger.warning(f"TARGET_DIMENSIONS from config is not a pair: {cls.target_dimensions}. Using default (1080, 1920).")
            cls.target_dimensions = (1080, 1920)

        # Determine output directory based on story path and base output dir in config
        paths_config = cls.config.get("paths", {})
        story_md_path_str = paths_config.get("test_story_md", "public/default_story.md")
        output_base_dir_str = paths_config.get("test_output_base_dir", "test_outputs") # Get base from config

        test_output_base_dir_path = PROJECT_ROOT / output_base_dir_str # Construct full path for base

        story_filename_stem = pathlib.Path(story_md_path_str).stem
        cls.current_test_output_dir = test_output_base_dir_path / story_filename_stem # Use resolved base path
        cls.current_test_output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"E2E test output directory for this run: {cls.current_test_output_dir}")

    def _load_story_content(self, story_path_str: str) -> str:
        story_path = PROJECT_ROOT / story_path_str
        if not story_path.exists():
            self.fail(f"Story file not found at {story_path}")
        with open(story_path, 'r') as f:
            return f.read()

    def test_00_generate_script_from_story(self):
        logger.info("Starting test_00_generate_script_from_story...")
        self.assertIsNotNone(TestE2ESceneGenerationFlow.config, "Config should be loaded.")
        if not TestE2ESceneGenerationFlow.anthropic_api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Skipping script generation from story.")

        story_md_path_str = TestE2ESceneGenerationFlow.config["paths"]["test_story_md"]
        TestE2ESceneGenerationFlow.story_content = self._load_story_content(story_md_path_str)
        self.assertTrue(len(TestE2ESceneGenerationFlow.story_content) > 0, "Story content is empty.")
        logger.info(f"Loaded story: {story_md_path_str}")

        script_prompt_template = get_prompt_template(TECH_IN_ASIA_SCRIPT_PROMPT_PATH)

        # For Claude, the system prompt is often separate. The template content can be the user prompt.
        # The tech_in_asia_script_prompt.md seems to be a full prompt including instructions.
        # We might need to delineate system vs user part if Claude API requires it explicitly.
        # For now, assuming the whole content of tech_in_asia_script_prompt.md is the user prompt,
        # and we add the story content at the end or as per template design.

        # The prompt expects the article/content to be transformed.
        # Let's assume the template itself is the main instruction set, and we append the story.
        # However, a more robust way would be if the prompt template had a placeholder like {{article_content}}.
        # Since it doesn't, we'll append the story content to the main prompt text.

        # Simulating a system prompt (often generic for such tasks if not explicit in template)
        system_prompt_for_script_gen = "You are an expert video script writer for Tech in Asia. Follow the user's instructions precisely."
        user_prompt_for_script_gen = script_prompt_template + "\\n\\n<article_content>\\n" + TestE2ESceneGenerationFlow.story_content + "\\n</article_content>"

        llm_config = TestE2ESceneGenerationFlow.config.get('llm_script_writer', TestE2ESceneGenerationFlow.config.get('llm_scene_planner', {})) # Fallback to scene_planner config for model name etc.

        claude_ai = ClaudeClient(model=llm_config.get("MODEL_NAME", "claude-3-5-sonnet-20240620"))
        call_params = {}
        if llm_config.get("MAX_TOKENS"): call_params['max_tokens'] = llm_config.get("MAX_TOKENS")
        if llm_config.get("TEMPERATURE"): call_params['temperature'] = float(llm_config.get("TEMPERATURE"))

        logger.info("Sending request to Claude for script generation...")
        raw_script_response = claude_ai.generate_text(
            system_prompt=system_prompt_for_script_gen,
            prompt=user_prompt_for_script_gen,
            **call_params
        )
        self.assertIsNotNone(raw_script_response, "LLM response for script generation was None.")

        # The prompt asks for a JSON object.
        try:
            # Attempt to find JSON block if the LLM wraps it in text
            json_match = re.search(r'```json\n(\{.*?\})\n```', raw_script_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else: # Assume the response is directly the JSON string
                json_str = raw_script_response

            TestE2ESceneGenerationFlow.script_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM script response: {e}")
            logger.error(f"Raw response was: \\n{raw_script_response}")
            self.fail("LLM script response was not valid JSON.")

        self.assertIsNotNone(TestE2ESceneGenerationFlow.script_data, "Generated script data is None after parsing.")
        self.assertIsInstance(TestE2ESceneGenerationFlow.script_data, dict, "Generated script data is not a dict.")

        # Save the generated script
        generated_script_output_path = TestE2ESceneGenerationFlow.current_test_output_dir / "generated_script_from_story.json"
        try:
            with open(generated_script_output_path, 'w') as f:
                json.dump(TestE2ESceneGenerationFlow.script_data, f, indent=2)
            logger.info(f"Generated script saved to: {generated_script_output_path}")
        except Exception as e:
            logger.error(f"Failed to save generated script: {e}")

        logger.info("test_00_generate_script_from_story PASSED")

    def test_01_load_script_and_config(self):
        logger.info("Starting test_01_load_script_and_config...")
        self.assertIsNotNone(TestE2ESceneGenerationFlow.config, "Config should be loaded in setUpClass")
        # Script data is now expected to be populated by test_00
        self.assertIsNotNone(TestE2ESceneGenerationFlow.script_data, "Script data was not generated from the previous step.")

        logger.info(f"Using generated script data. Title: {TestE2ESceneGenerationFlow.script_data.get('video_structure',{}).get('title','N/A')}")

        TestE2ESceneGenerationFlow.full_voiceover_text = " ".join(
            segment["voiceover"]
            for segment_key in ["hook", "conflict", "body", "conclusion"]
            if (segment := TestE2ESceneGenerationFlow.script_data.get("script_segments", {}).get(segment_key)) and "voiceover" in segment
        ).strip()
        self.assertTrue(len(TestE2ESceneGenerationFlow.full_voiceover_text) > 0, "Concatenated voiceover text is empty.")
        logger.info(f"Concatenated voiceover (first 100 chars): {TestE2ESceneGenerationFlow.full_voiceover_text[:100]}...")
        logger.info("test_01_load_script_and_config PASSED")

    def _get_audio_duration(self, file_path: str) -> float | None:
        """Gets audio duration using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except FileNotFoundError:
            logger.error("ffprobe command not found. Make sure FFmpeg is installed and in PATH.")
            self.skipTest("ffprobe not found, cannot get audio duration.")
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed for {file_path}: {e.stderr}")
            return None
        except ValueError as e:
            logger.error(f"Could not parse ffprobe duration output for {file_path}: {e}")
            return None

    def test_02_generate_tts(self):
        logger.info("Starting test_02_generate_tts...")
        if not TestE2ESceneGenerationFlow.elevenlabs_api_key:
            self.skipTest("ELEVENLABS_API_KEY not set. Skipping TTS generation.")
        self.assertIsNotNone(TestE2ESceneGenerationFlow.script_data, "Script data not available from previous step.")
        self.assertIsNotNone(TestE2ESceneGenerationFlow.full_voiceover_text, "Full voiceover text not prepared.")

        tts_config = TestE2ESceneGenerationFlow.config.get("tts_settings", {})
        # Sanitize title from generated script for filename
        script_title = TestE2ESceneGenerationFlow.script_data.get("video_structure", {}).get("title", "e2e_video")
        tts_output_filename = sanitize_filename(f"{script_title}_master_vo.mp3")

        default_tts_save_dir = PROJECT_ROOT / "backend" / "assets" / "audio" / "speech"
        temp_audio_path = default_tts_save_dir / tts_output_filename
        temp_audio_path.parent.mkdir(parents=True, exist_ok=True) # Ensure dir exists

        logger.info(f"Attempting to generate TTS audio. Intermediate default path: {temp_audio_path}")
        generated_audio_path_str = text_to_speech(
            text=TestE2ESceneGenerationFlow.full_voiceover_text,
            output_filename=tts_output_filename, # Will save to default_tts_save_dir / tts_output_filename
            voice_id=tts_config.get("VOICE_ID"),
            model_id=tts_config.get("MODEL_ID"),
            speed=float(tts_config.get("SPEED", 1.0)),
            stability=float(tts_config.get("STABILITY", 0.5)),
            similarity_boost=float(tts_config.get("SIMILARITY_BOOST", 0.75)),
            style=float(tts_config.get("STYLE", 0.0)),
            use_speaker_boost=tts_config.get("USE_SPEAKER_BOOST", True)
        )
        self.assertTrue(generated_audio_path_str, "TTS generation failed to return a path.")
        self.assertEqual(generated_audio_path_str, str(temp_audio_path), "TTS file not saved to expected default intermediate location.")
        self.assertTrue(os.path.exists(generated_audio_path_str), f"TTS audio file not found at intermediate path {generated_audio_path_str}")
        logger.info(f"TTS audio generated successfully at intermediate path: {generated_audio_path_str}")

        final_audio_path = TestE2ESceneGenerationFlow.current_test_output_dir / tts_output_filename # Use current_test_output_dir
        try:
            shutil.move(generated_audio_path_str, final_audio_path)
            logger.info(f"Moved TTS audio to final test output location: {final_audio_path}")
            TestE2ESceneGenerationFlow.master_audio_path_str = str(final_audio_path)
            self.assertTrue(os.path.exists(final_audio_path), f"Moved TTS audio file not found at {final_audio_path}")
        except Exception as e:
            self.fail(f"Failed to move TTS audio from {generated_audio_path_str} to {final_audio_path}: {e}")

        if TestE2ESceneGenerationFlow.master_audio_path_str:
            duration = self._get_audio_duration(TestE2ESceneGenerationFlow.master_audio_path_str)
            if duration is not None:
                logger.info(f"Duration of generated TTS audio ({TestE2ESceneGenerationFlow.master_audio_path_str}): {duration:.2f} seconds.")
            else:
                logger.warning(f"Could not determine duration for {TestE2ESceneGenerationFlow.master_audio_path_str}.")
        logger.info("test_02_generate_tts PASSED")

    def test_03_transcribe_audio(self):
        logger.info("Starting test_03_transcribe_audio...")
        if not TestE2ESceneGenerationFlow.master_audio_path_str:
            self.skipTest("Master audio path not available (TTS step likely skipped or failed). Skipping transcription.")

        logger.info(f"Transcribing audio file: {TestE2ESceneGenerationFlow.master_audio_path_str}")
        try:
            transcription_segments = transcribe_locally(TestE2ESceneGenerationFlow.master_audio_path_str)
        except Exception as e:
            if "ffmpeg" in str(e).lower() or "whisper" in str(e).lower():
                logger.warning(f"Local transcription failed (likely due to ffmpeg/whisper setup): {e}. Skipping subsequent tests.")
                TestE2ESceneGenerationFlow.word_level_transcript = None
                self.skipTest(f"Local transcription failed: {e}")
            raise

        self.assertIsNotNone(transcription_segments, "Transcription returned None.")
        self.assertTrue(len(transcription_segments) > 0, "Transcription did not yield any segments.")

        processed_word_level_transcript = []
        if transcription_segments and isinstance(transcription_segments, list) and len(transcription_segments) > 0 and 'words' in transcription_segments[0]:
            for segment in transcription_segments:
                 processed_word_level_transcript.extend(segment['words'])
        else:
            logger.warning("Transcription segments do not contain direct 'words' list or format is unexpected. Trying fallback.")
            for seg_idx, segment in enumerate(transcription_segments if isinstance(transcription_segments, list) else []):
                if not isinstance(segment, dict): continue
                text = segment.get('text', '').strip()
                start = segment.get('start', seg_idx * 2.0)
                end = segment.get('end', start + len(text.split()) * 0.5)
                words_in_segment = text.split()
                num_words = len(words_in_segment)
                approx_duration_per_word = (end - start) / num_words if num_words > 0 else 0
                current_time = start
                for word_text in words_in_segment:
                    processed_word_level_transcript.append({
                        "word": word_text,
                        "start": round(current_time, 3),
                        "end": round(current_time + approx_duration_per_word, 3),
                        "speaker": segment.get("speaker", "SPEAKER_00")
                    })
                    current_time += approx_duration_per_word

        self.assertTrue(len(processed_word_level_transcript) > 0, "Transcription did not yield word-level data, even after fallback.")
        TestE2ESceneGenerationFlow.word_level_transcript = processed_word_level_transcript
        logger.info(f"Transcription successful. First few words: {json.dumps(TestE2ESceneGenerationFlow.word_level_transcript[:3], indent=2)}")

        if TestE2ESceneGenerationFlow.word_level_transcript:
            try:
                valid_end_times = [item['end'] for item in TestE2ESceneGenerationFlow.word_level_transcript if isinstance(item.get('end'), (int, float))]
                if valid_end_times:
                    transcription_duration = max(valid_end_times)
                    logger.info(f"Total duration of transcription: {transcription_duration:.2f} seconds.")
                else:
                    logger.warning("No valid 'end' times found in transcription to calculate duration.")
            except (TypeError, KeyError) as e:
                logger.warning(f"Could not calculate total transcription duration due to missing or invalid 'end' times: {e}")

        transcription_output_path = TestE2ESceneGenerationFlow.current_test_output_dir / "e2e_transcription_output.json"
        try:
            with open(transcription_output_path, 'w') as f:
                json.dump(TestE2ESceneGenerationFlow.word_level_transcript, f, indent=2)
            logger.info(f"Transcription output saved to: {transcription_output_path}")
        except Exception as e:
            logger.error(f"Failed to save transcription output: {e}")

        logger.info("test_03_transcribe_audio PASSED")

    def test_04_prepare_and_invoke_llm(self):
        logger.info("Starting test_04_prepare_and_invoke_llm...")
        if not TestE2ESceneGenerationFlow.anthropic_api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Skipping LLM call.")
        if TestE2ESceneGenerationFlow.word_level_transcript is None or not TestE2ESceneGenerationFlow.word_level_transcript:
            self.skipTest("Word-level transcript not available. Skipping LLM call.")
        self.assertIsNotNone(TestE2ESceneGenerationFlow.script_data, "Script data not loaded.")

        llm_config = TestE2ESceneGenerationFlow.config['llm_scene_planner']
        visual_planner_prompt_path = PROJECT_ROOT / "backend" / "prompts" / "visual_scene_planner_prompt_template.md"
        prompt_template = get_prompt_template(visual_planner_prompt_path)
        system_prompt_for_claude = "You are an expert video production planner..."

        replacements = {
            "{{word_transcript_json_string}}": json.dumps(TestE2ESceneGenerationFlow.word_level_transcript),
            "{{script_json_string}}": json.dumps(TestE2ESceneGenerationFlow.script_data),
            "{{min_segment_duration}}": str(llm_config["MIN_SEGMENT_DURATION"]),
            "{{max_segment_duration}}": str(llm_config["MAX_SEGMENT_DURATION"]),
            "{{photo_segment_threshold}}": str(llm_config["PHOTO_SEGMENT_THRESHOLD"]),
            "{{max_keywords_per_scene}}": str(llm_config["MAX_KEYWORDS_PER_SCENE"]),
            "{{avatar_scene_preference}}": llm_config["AVATAR_SCENE_PREFERENCE"],
            "{{config_json_string}}": json.dumps(llm_config)
        }
        user_prompt_filled = prompt_template
        for placeholder, value in replacements.items():
            user_prompt_filled = user_prompt_filled.replace(placeholder, value)

        logger.info("Sending request to Claude for scene planning...")
        client_max_tokens = llm_config.get("MAX_TOKENS")
        client_temperature = llm_config.get("TEMPERATURE")
        claude_ai = ClaudeClient(model=llm_config.get("MODEL_NAME", "claude-3-5-sonnet-20240620"))
        call_params = {}
        if client_max_tokens is not None: call_params['max_tokens'] = client_max_tokens
        if client_temperature is not None: call_params['temperature'] = float(client_temperature)

        TestE2ESceneGenerationFlow.scene_plans_raw = claude_ai.generate_structured_output(
            system_prompt=system_prompt_for_claude,
            user_prompt=user_prompt_filled,
            **call_params
        )
        self.assertIsNotNone(TestE2ESceneGenerationFlow.scene_plans_raw, "LLM response was None.")
        logger.info(f"Received response from LLM. Type: {type(TestE2ESceneGenerationFlow.scene_plans_raw)}")
        logger.info("test_04_prepare_and_invoke_llm PASSED")

    def test_05_log_and_validate_llm_output(self):
        logger.info("Starting test_05_log_and_validate_llm_output...")
        if TestE2ESceneGenerationFlow.scene_plans_raw is None:
            self.skipTest("LLM scene plans not available. Skipping validation.")

        llm_output_path = TestE2ESceneGenerationFlow.current_test_output_dir / "e2e_llm_scene_plan_output.json"
        try:
            with open(llm_output_path, 'w') as f:
                json.dump(TestE2ESceneGenerationFlow.scene_plans_raw, f, indent=2)
            logger.info(f"LLM scene plans saved to: {llm_output_path}")
        except Exception as e:
            logger.error(f"Failed to save LLM output: {e}")

        self.assertIsInstance(TestE2ESceneGenerationFlow.scene_plans_raw, list, f"LLM response is not a list, got {type(TestE2ESceneGenerationFlow.scene_plans_raw)}.")
        self.assertTrue(len(TestE2ESceneGenerationFlow.scene_plans_raw) > 0, "LLM returned an empty list.")

        llm_config = TestE2ESceneGenerationFlow.config['llm_scene_planner']
        min_dur, max_dur = llm_config["MIN_SEGMENT_DURATION"], llm_config["MAX_SEGMENT_DURATION"]
        photo_thresh = llm_config.get("PHOTO_SEGMENT_THRESHOLD", 1.5) # Use .get for safety

        for i, scene_plan in enumerate(TestE2ESceneGenerationFlow.scene_plans_raw):
            with self.subTest(scene_index=i, scene_id=scene_plan.get("scene_id", "N/A")):
                self.assertIsInstance(scene_plan, dict, f"Scene {i} not a dict.")
                for key in ["scene_id", "start_time", "end_time", "text_for_scene", "original_script_part_ref", "visual_type", "visual_keywords", "fx_suggestion"]:
                    self.assertIn(key, scene_plan, f"Key '{key}' missing in scene {i}.")

                self.assertIsInstance(scene_plan["scene_id"], str)
                self.assertIsInstance(scene_plan["start_time"], (float, int))
                self.assertIsInstance(scene_plan["end_time"], (float, int))
                duration = scene_plan["end_time"] - scene_plan["start_time"]
                self.assertTrue(duration >= min_dur - 0.01 and duration <= max_dur + 0.01,
                                f"Scene duration {duration:.2f}s out of range [{min_dur:.2f}, {max_dur:.2f}]s.")
                self.assertIsInstance(scene_plan["text_for_scene"], str)
                self.assertIsInstance(scene_plan["original_script_part_ref"], str)
                self.assertIn(scene_plan["visual_type"], ["AVATAR", "STOCK_VIDEO", "STOCK_IMAGE"])
                if scene_plan["visual_type"] != "AVATAR":
                    if duration <= photo_thresh + 0.01: # Add tolerance for threshold comparison
                        self.assertEqual(scene_plan["visual_type"], "STOCK_IMAGE", f"Scene duration {duration:.2f}s <= threshold {photo_thresh:.2f}s, but type is not STOCK_IMAGE.")
                    else:
                        self.assertEqual(scene_plan["visual_type"], "STOCK_VIDEO", f"Scene duration {duration:.2f}s > threshold {photo_thresh:.2f}s, but type is not STOCK_VIDEO.")
                self.assertIsInstance(scene_plan["visual_keywords"], list)
                self.assertGreaterEqual(len(scene_plan["visual_keywords"]), 1) # Should have at least one keyword
                self.assertTrue(all(isinstance(kw, str) for kw in scene_plan["visual_keywords"]))
                if scene_plan["fx_suggestion"] is not None:
                    self.assertIsInstance(scene_plan["fx_suggestion"], dict)
                    self.assertIn("type", scene_plan["fx_suggestion"])
                    self.assertIn("text_content", scene_plan["fx_suggestion"])
        logger.info("test_05_log_and_validate_llm_output PASSED")

    def test_06_validate_durations(self):
        logger.info("Starting test_06_validate_durations...")
        if TestE2ESceneGenerationFlow.word_level_transcript is None:
            self.skipTest("Word-level transcript not available. Skipping duration validation.")
        if TestE2ESceneGenerationFlow.scene_plans_raw is None:
            self.skipTest("LLM scene plans not available. Skipping duration validation.")
        if TestE2ESceneGenerationFlow.master_audio_path_str is None:
            self.skipTest("Master audio path not available. Skipping duration validation.")

        # 1. Get Master Audio Duration
        audio_duration = self._get_audio_duration(TestE2ESceneGenerationFlow.master_audio_path_str)
        self.assertIsNotNone(audio_duration, "Could not determine master audio duration.")
        logger.info(f"Duration Check - Master Audio: {audio_duration:.3f}s")

        # 2. Get Total Transcription Duration
        transcription_duration = 0.0
        if TestE2ESceneGenerationFlow.word_level_transcript:
            valid_end_times = [item['end'] for item in TestE2ESceneGenerationFlow.word_level_transcript if isinstance(item.get('end'), (int, float))]
            if valid_end_times:
                transcription_duration = max(valid_end_times)
                # Assuming transcription starts near 0
            else:
                self.fail("No valid 'end' times found in transcription to calculate total duration.")
        logger.info(f"Duration Check - Transcription (max end time): {transcription_duration:.3f}s")

        # 3. Get Total Visual Scenes Duration from LLM plan
        # This should be from the start_time of the first scene to the end_time of the last scene.
        # Assumes scenes are ordered.
        scene_plan_total_duration = 0.0
        if TestE2ESceneGenerationFlow.scene_plans_raw:
            first_scene_start_time = TestE2ESceneGenerationFlow.scene_plans_raw[0].get('start_time')
            last_scene_end_time = TestE2ESceneGenerationFlow.scene_plans_raw[-1].get('end_time')
            if isinstance(first_scene_start_time, (int, float)) and isinstance(last_scene_end_time, (int, float)):
                scene_plan_total_duration = last_scene_end_time - first_scene_start_time
                # More accurately, the duration is simply the end time of the last word in the last scene,
                # assuming the LLM covers the whole transcript.
                # The prompt asks LLM to ensure "end_time of the last scene should closely match the end_time of the last word in the transcript"
                scene_plan_max_end_time = last_scene_end_time
                logger.info(f"Duration Check - LLM Scene Plan (max end time): {scene_plan_max_end_time:.3f}s")

                # Validate that the scene plan's max end time aligns with transcription duration
                # This is a more direct check of the LLM's adherence to covering the transcript
                self.assertAlmostEqual(scene_plan_max_end_time, transcription_duration, delta=0.5, # Allow 0.5s leeway
                                   msg=f"LLM Scene Plan max end time ({scene_plan_max_end_time:.3f}s) "
                                       f"does not closely match transcription duration ({transcription_duration:.3f}s).")
            else:
                self.fail("Could not determine scene plan total duration due to missing/invalid start/end times.")

        # Validate all three are close. Audio is usually the ground truth.
        # Transcription end time should be very close to audio duration.
        self.assertAlmostEqual(transcription_duration, audio_duration, delta=0.75, # Transcription can sometimes be slightly off from pure audio
                               msg=f"Transcription duration ({transcription_duration:.3f}s) "
                                   f"differs significantly from audio duration ({audio_duration:.3f}s).")

        # Scene plan's overall duration (represented by last scene's end time) should align with transcription.
        # (Already checked above more directly)

        logger.info("test_06_validate_durations PASSED")

if __name__ == '__main__':
    unittest.main()

# Need to import re for the script generation part
import re
