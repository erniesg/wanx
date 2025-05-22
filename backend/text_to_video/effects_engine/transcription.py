import whisper
import logging
import os
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the root directory for storing Whisper models within the project
# Project root is assumed to be three levels up from this script's directory
# (effects_engine -> text_to_video -> backend -> project_root)
# Adjust if your structure is different or manage path more robustly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL_DOWNLOAD_ROOT = os.path.join(CURRENT_DIR, "models", "whisper_models")
os.makedirs(DEFAULT_MODEL_DOWNLOAD_ROOT, exist_ok=True)

# Consider making the model name configurable if needed later
DEFAULT_WHISPER_MODEL = "base" # "tiny", "base", "small", "medium", "large"

def get_word_level_timestamps(
    audio_file_path: str,
    whisper_model_name: str = DEFAULT_WHISPER_MODEL,
    model_download_root: str = DEFAULT_MODEL_DOWNLOAD_ROOT,
    language: str = None, # e.g., "en", None for auto-detect
    initial_prompt: str = None
) -> List[Dict[str, Any]]:
    """
    Transcribes an audio file using the local Whisper package and returns
    word-level timestamps.

    Args:
        audio_file_path (str): Path to the audio file.
        whisper_model_name (str): Name of the Whisper model to use.
        model_download_root (str): Directory to download/cache Whisper models.
        language (str, optional): Language code (e.g., 'en'). Defaults to None (auto-detect).
        initial_prompt (str, optional): Initial prompt for the transcription model.

    Returns:
        List[Dict[str, Any]]: A list of word objects, where each object is a
                               dictionary like:
                               {'word': ' Hello', 'start': 0.52, 'end': 0.73, 'probability': 0.95}
                               (Exact keys might vary slightly based on whisper version/settings,
                                but 'word', 'start', 'end' are standard for word_timestamps=True)
                               Returns an empty list if transcription fails or no words are found.
    """
    if not os.path.exists(audio_file_path):
        logger.error(f"Audio file not found at: {audio_file_path}")
        return []

    logger.info(f"Loading Whisper model: {whisper_model_name} (Target download root: {model_download_root})")
    try:
        model = whisper.load_model(whisper_model_name, download_root=model_download_root)
    except Exception as e:
        logger.error(f"Failed to load Whisper model '{whisper_model_name}': {e}")
        logger.error("Ensure the model name is correct and you have enough resources.")
        logger.error("Available models typically include: tiny, base, small, medium, large.")
        return []

    logger.info(f"Starting transcription for: {audio_file_path}")
    all_words = []
    try:
        # The fp16=False option might be needed on CPUs or non-NVIDIA GPUs.
        # For NVIDIA GPUs, fp16=True (default if not specified) is faster.
        # Adjust as per your hardware setup.
        transcription_result = model.transcribe(
            audio=audio_file_path,
            word_timestamps=True,
            language=language,
            initial_prompt=initial_prompt,
            fp16=False # Set to False for broader compatibility, can be True for NVIDIA GPUs
        )

        if transcription_result and "segments" in transcription_result:
            for segment in transcription_result["segments"]:
                if "words" in segment:
                    all_words.extend(segment["words"])
            logger.info(f"Transcription successful. Found {len(all_words)} words.")
        else:
            logger.warning("Transcription did not return segments or was empty.")

    except Exception as e:
        logger.error(f"Error during Whisper transcription: {e}")
        return []

    return all_words

if __name__ == '__main__':
    # --- This is a basic test block ---
    # To run this test:
    # 1. Make sure you have a test audio file (e.g., 'test_audio.mp3') in the same directory or provide a full path.
    #    You can generate a short one using an online TTS or by recording yourself.
    # 2. Ensure 'openai-whisper' is installed: pip install openai-whisper
    # 3. Run this script directly: python backend/text_to_video/effects_engine/transcription.py

    logger.info("Running basic test for get_word_level_timestamps...")

    # Create a dummy audio file for testing if one doesn't exist
    # For a real test, use an actual audio file with discernible speech.
    # This dummy file won't produce meaningful transcription but tests the flow.
    test_audio_file = "test.mp3"
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    test_audio_path = os.path.join(current_script_dir, test_audio_file)

    # Check if a real audio file is provided via an environment variable for better testing
    manual_test_audio_path = os.getenv("TEST_AUDIO_FILE_PATH")
    if manual_test_audio_path and os.path.exists(manual_test_audio_path):
        logger.info(f"Using provided test audio file: {manual_test_audio_path}")
        test_audio_path_to_use = manual_test_audio_path
    elif os.path.exists(test_audio_path): # Fallback to local dummy if exists
         logger.info(f"Using local dummy audio file: {test_audio_path} (may not produce good results).")
         test_audio_path_to_use = test_audio_path
    else:
        try:
            # Attempt to create a very simple, short silent WAV file as a placeholder if no audio is found
            # This is just to allow the script to run without an immediate file not found error.
            # Real speech audio is needed for a proper test.
            import wave
            with wave.open(test_audio_path, 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b'\\x00\\x00' * 44100) # 1 second of silence
            logger.info(f"Created dummy silent audio file for testing: {test_audio_path}")
            test_audio_path_to_use = test_audio_path
        except Exception as e_wave:
            logger.error(f"Could not create dummy audio file: {e_wave}. Please provide a test audio file.")
            test_audio_path_to_use = None

    if test_audio_path_to_use:
        # Using the 'tiny' model for a quicker test.
        # For better accuracy with real audio, 'base' or 'small' are good starting points.
        words = get_word_level_timestamps(
            test_audio_path_to_use,
            whisper_model_name="tiny",
            model_download_root=DEFAULT_MODEL_DOWNLOAD_ROOT
        )

        if words:
            logger.info(f"Successfully transcribed and got {len(words)} words.")
            logger.info("First 5 words (or fewer):")
            for i, word_data in enumerate(words[:5]):
                logger.info(f"  Word {i+1}: Text='{word_data.get('word')}', Start={word_data.get('start'):.2f}s, End={word_data.get('end'):.2f}s, Prob={word_data.get('probability', 'N/A'):.2f}")

            # Example of checking structure of the first word
            if words:
                first_word = words[0]
                expected_keys = ["word", "start", "end"]
                has_expected_keys = all(key in first_word for key in expected_keys)
                logger.info(f"First word has expected keys ('word', 'start', 'end'): {has_expected_keys}")
                if not has_expected_keys:
                    logger.warning(f"First word data: {first_word}")

        else:
            logger.warning("Transcription returned no words. This might be normal for a silent/dummy audio file.")
            logger.warning("For a real test, use an audio file with clear speech.")
    else:
        logger.error("No audio file available to test transcription.")

    logger.info("Basic test finished.")
