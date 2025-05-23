import unittest
import os
import json
import yaml
import logging
import pathlib
import shutil # Added for moving files
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
TEST_OUTPUT_DIR = PROJECT_ROOT / "test_outputs"

def load_test_config():
    if not CONFIG_FILE_PATH.exists():
        raise FileNotFoundError(f"Test config file not found at {CONFIG_FILE_PATH}")
    with open(CONFIG_FILE_PATH, 'r') as f:
        return yaml.safe_load(f)

def get_llm_scene_planner_prompt_template() -> str:
    if not PROMPT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Prompt template file not found at {PROMPT_TEMPLATE_PATH}")
    with open(PROMPT_TEMPLATE_PATH, 'r') as f:
        return f.read()

class TestE2ESceneGenerationFlow(unittest.TestCase):

    # Class-level variables to store results between test steps
    config = None
    elevenlabs_api_key = None
    anthropic_api_key = None
    script_data = None
    full_voiceover_text = None
    master_audio_path_str = None # This will now point to the path in TEST_OUTPUT_DIR
    word_level_transcript = None
    scene_plans_raw = None

    @classmethod
    def setUpClass(cls):
        logger.info("Setting up E2E test class...")
        cls.config = load_test_config()
        cls.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        cls.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        # Ensure the main test output directory exists
        TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Main test output dir: {TEST_OUTPUT_DIR}")
        # The specific audio_output_dir from config is no longer the primary destination for E2E test artifacts

    def _load_script_md(self, script_path_str: str) -> dict:
        script_path = PROJECT_ROOT / script_path_str
        if not script_path.exists():
            self.fail(f"Script.md file not found at {script_path}")
        with open(script_path, 'r') as f:
            return json.load(f)

    def test_01_load_script_and_config(self):
        logger.info("Starting test_01_load_script_and_config...")
        self.assertIsNotNone(TestE2ESceneGenerationFlow.config, "Config should be loaded in setUpClass")
        script_md_path_str = TestE2ESceneGenerationFlow.config["paths"]["test_script_md"]
        TestE2ESceneGenerationFlow.script_data = self._load_script_md(script_md_path_str)
        self.assertIsNotNone(TestE2ESceneGenerationFlow.script_data, "Script data failed to load.")
        logger.info(f"Loaded script: {script_md_path_str}")
        TestE2ESceneGenerationFlow.full_voiceover_text = " ".join(
            segment["voiceover"]
            for segment_key in ["hook", "conflict", "body", "conclusion"]
            if (segment := TestE2ESceneGenerationFlow.script_data.get("script_segments", {}).get(segment_key))
        ).strip()
        self.assertTrue(len(TestE2ESceneGenerationFlow.full_voiceover_text) > 0, "Concatenated voiceover text is empty.")
        logger.info(f"Concatenated voiceover (first 100 chars): {TestE2ESceneGenerationFlow.full_voiceover_text[:100]}...")
        logger.info("test_01_load_script_and_config PASSED")

    def test_02_generate_tts(self):
        logger.info("Starting test_02_generate_tts...")
        if not TestE2ESceneGenerationFlow.elevenlabs_api_key:
            self.skipTest("ELEVENLABS_API_KEY not set. Skipping TTS generation.")
        self.assertIsNotNone(TestE2ESceneGenerationFlow.script_data, "Script data not loaded from previous step.")
        self.assertIsNotNone(TestE2ESceneGenerationFlow.full_voiceover_text, "Full voiceover text not prepared.")

        tts_config = TestE2ESceneGenerationFlow.config.get("tts_settings", {})
        tts_output_filename = sanitize_filename(f"{TestE2ESceneGenerationFlow.script_data['video_structure']['title']}_master_vo.mp3")

        # TTS module saves to its default assets path
        # backend/assets/audio/speech/
        default_tts_save_dir = PROJECT_ROOT / "backend" / "assets" / "audio" / "speech"
        temp_audio_path = default_tts_save_dir / tts_output_filename

        logger.info(f"Attempting to generate TTS audio. Intermediate default path: {temp_audio_path}")
        # text_to_speech returns the path where it saved the file (its default location)
        generated_audio_path_str = text_to_speech(
            text=TestE2ESceneGenerationFlow.full_voiceover_text,
            output_filename=tts_output_filename,
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

        # Move the generated audio file to the consolidated test_outputs directory
        final_audio_path = TEST_OUTPUT_DIR / tts_output_filename
        try:
            shutil.move(generated_audio_path_str, final_audio_path)
            logger.info(f"Moved TTS audio to final test output location: {final_audio_path}")
            TestE2ESceneGenerationFlow.master_audio_path_str = str(final_audio_path)
            self.assertTrue(os.path.exists(final_audio_path), f"Moved TTS audio file not found at {final_audio_path}")
        except Exception as e:
            self.fail(f"Failed to move TTS audio from {generated_audio_path_str} to {final_audio_path}: {e}")

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
                if not isinstance(segment, dict): continue # Skip if segment is not a dict
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

        # Save transcription output
        transcription_output_path = TEST_OUTPUT_DIR / "e2e_transcription_output.json"
        try:
            with open(transcription_output_path, 'w') as f:
                json.dump(TestE2ESceneGenerationFlow.word_level_transcript, f, indent=2)
            logger.info(f"Transcription output saved to: {transcription_output_path}")
        except Exception as e:
            logger.error(f"Failed to save transcription output: {e}") # Log error but don't fail test for this

        logger.info("test_03_transcribe_audio PASSED")

    def test_04_prepare_and_invoke_llm(self):
        logger.info("Starting test_04_prepare_and_invoke_llm...")
        if not TestE2ESceneGenerationFlow.anthropic_api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Skipping LLM call.")
        if TestE2ESceneGenerationFlow.word_level_transcript is None or not TestE2ESceneGenerationFlow.word_level_transcript:
            self.skipTest("Word-level transcript not available. Skipping LLM call.")
        self.assertIsNotNone(TestE2ESceneGenerationFlow.script_data, "Script data not loaded.")

        llm_config = TestE2ESceneGenerationFlow.config['llm_scene_planner']
        prompt_template = get_llm_scene_planner_prompt_template()
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

        llm_output_path = TEST_OUTPUT_DIR / "e2e_llm_scene_plan_output.json"
        try:
            with open(llm_output_path, 'w') as f:
                json.dump(TestE2ESceneGenerationFlow.scene_plans_raw, f, indent=2)
            logger.info(f"LLM scene plans saved to: {llm_output_path}")
        except Exception as e:
            logger.error(f"Failed to save LLM output: {e}")

        self.assertIsInstance(TestE2ESceneGenerationFlow.scene_plans_raw, list, f"LLM response is not a list, got {type(TestE2ESceneGenerationFlow.scene_plans_raw)}.")
        self.assertTrue(len(TestE2ESceneGenerationFlow.scene_plans_raw) > 0, "LLM returned an empty list.")

        llm_config = TestE2ESceneGenerationFlow.config['llm_scene_planner']
        min_dur, max_dur, photo_thresh = llm_config["MIN_SEGMENT_DURATION"], llm_config["MAX_SEGMENT_DURATION"], llm_config["PHOTO_SEGMENT_THRESHOLD"]

        for i, scene_plan in enumerate(TestE2ESceneGenerationFlow.scene_plans_raw):
            with self.subTest(scene_index=i, scene_id=scene_plan.get("scene_id", "N/A")):
                self.assertIsInstance(scene_plan, dict, f"Scene {i} not a dict.")
                for key in ["scene_id", "start_time", "end_time", "text_for_scene", "original_script_part_ref", "visual_type", "visual_keywords", "fx_suggestion"]:
                    self.assertIn(key, scene_plan, f"Key '{key}' missing in scene {i}.")

                self.assertIsInstance(scene_plan["scene_id"], str)
                self.assertIsInstance(scene_plan["start_time"], (float, int))
                self.assertIsInstance(scene_plan["end_time"], (float, int))
                duration = scene_plan["end_time"] - scene_plan["start_time"]
                self.assertGreaterEqual(duration, min_dur - 0.01, f"Duration {duration}s < min {min_dur}s.")
                self.assertLessEqual(duration, max_dur + 0.01, f"Duration {duration}s > max {max_dur}s.")
                self.assertIsInstance(scene_plan["text_for_scene"], str)
                self.assertTrue(len(scene_plan["text_for_scene"]) > 0)
                self.assertIsInstance(scene_plan["original_script_part_ref"], str)
                self.assertIn(scene_plan["visual_type"], ["AVATAR", "STOCK_VIDEO", "STOCK_IMAGE"])
                if scene_plan["visual_type"] != "AVATAR":
                    if duration <= photo_thresh: self.assertEqual(scene_plan["visual_type"], "STOCK_IMAGE")
                    else: self.assertEqual(scene_plan["visual_type"], "STOCK_VIDEO")
                self.assertIsInstance(scene_plan["visual_keywords"], list)
                self.assertGreaterEqual(len(scene_plan["visual_keywords"], 1))
                self.assertTrue(all(isinstance(kw, str) for kw in scene_plan["visual_keywords"]))
                if scene_plan["fx_suggestion"] is not None:
                    self.assertIsInstance(scene_plan["fx_suggestion"], dict)
                    self.assertIn("type", scene_plan["fx_suggestion"])
                    self.assertIn("text_content", scene_plan["fx_suggestion"])
        logger.info("test_05_log_and_validate_llm_output PASSED")

if __name__ == '__main__':
    unittest.main()
