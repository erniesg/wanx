import whisper
import logging
import os
from typing import List, Dict, Any
import difflib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the root directory for storing Whisper models within the project
# Project root is assumed to be three levels up from this script's directory
# (effects_engine -> text_to_video -> backend -> project_root)
# Adjust if your structure is different or manage path more robustly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Path from backend/text_to_video/fx/ to backend/assets/models/whisper_models/
DEFAULT_MODEL_DOWNLOAD_ROOT = os.path.join(CURRENT_DIR, "..", "..", "assets", "models", "whisper_models")
os.makedirs(DEFAULT_MODEL_DOWNLOAD_ROOT, exist_ok=True)

# Consider making the model name configurable if needed later
DEFAULT_WHISPER_MODEL = "base" # "tiny", "base", "small", "medium", "large"

def transcribe_locally(
    audio_file_path: str,
    whisper_model_name: str = DEFAULT_WHISPER_MODEL,
    model_download_root: str = DEFAULT_MODEL_DOWNLOAD_ROOT,
    language: str = None,
    initial_prompt: str = None
) -> List[Dict[str, Any]]: # Returns list of segments
    """
    Transcribes an audio file using the local Whisper package and returns
    word-level timestamps, structured as segments similar to captacity.

    Returns:
        List[Dict[str, Any]]: A list containing a single segment dictionary:
                               [{
                                 'words': List[WordDict],
                                 'start': float,
                                 'end': float
                               }]
                               Returns an empty list if transcription fails.
    """
    if not os.path.exists(audio_file_path):
        logger.error(f"Audio file not found at: {audio_file_path}")
        return []

    logger.info(f"Loading Whisper model: {whisper_model_name} (Download root: {model_download_root})")
    try:
        model = whisper.load_model(whisper_model_name, download_root=model_download_root)
    except Exception as e:
        logger.error(f"Failed to load Whisper model '{whisper_model_name}': {e}")
        return []

    logger.info(f"Starting local transcription for: {audio_file_path}")
    all_words_from_asr: List[Dict[str, Any]] = []
    try:
        transcription_result = model.transcribe(
            audio=audio_file_path,
            word_timestamps=True,
            language=language,
            initial_prompt=initial_prompt,
            fp16=False
        )

        if transcription_result and "segments" in transcription_result:
            for segment_asr in transcription_result["segments"]:
                if "words" in segment_asr and isinstance(segment_asr["words"], list):
                    all_words_from_asr.extend(segment_asr["words"])
            logger.info(f"Local transcription successful. Raw words found: {len(all_words_from_asr)}.")
        else:
            logger.warning("Local transcription did not return segments or was empty.")
            return []

    except Exception as e:
        logger.error(f"Error during local Whisper transcription: {e}", exc_info=True)
        return []

    if not all_words_from_asr:
        logger.warning("No words found by local transcription.")
        return []

    first_word_start = all_words_from_asr[0].get("start", 0.0)
    last_word_end = all_words_from_asr[-1].get("end", 0.0)
    if isinstance(first_word_start, str) : first_word_start = float(first_word_start)
    if isinstance(last_word_end, str) : last_word_end = float(last_word_end)

    processed_words = []
    for i, word_data in enumerate(all_words_from_asr):
        new_word_data = dict(word_data)
        if isinstance(new_word_data['word'], str) and not new_word_data['word'].startswith(' ') and i > 0:
            new_word_data['word'] = ' ' + new_word_data['word']
        processed_words.append(new_word_data)

    single_segment = {
        "words": processed_words,
        "start": float(first_word_start),
        "end": float(last_word_end)
    }
    return [single_segment]


# align_words_to_script now needs to handle the List[SegmentType] input if script alignment is still desired
# or be adapted. For now, generate_video.py calls this with a flat list of words.
# If transcribe_locally returns List[Segment], then generate_video.py must extract words first
# before calling align_words_to_script OR align_words_to_script is updated.

def align_words_to_script(transcribed_segments: List[Dict[str, Any]], target_script: str) -> List[Dict[str, Any]]:
    """
    Aligns words within transcribed segments to a target script, transferring timings.
    Currently assumes a single segment in transcribed_segments for simplicity, matching
    the current output of transcribe_locally.

    Args:
        transcribed_segments: List of segment dictionaries from Whisper/transcribe_locally.
                              Expected structure: [{'words': List[WordDict], 'start': float, 'end': float}]
        target_script: The ground truth script as a single string.

    Returns:
        A new list of segment dictionaries, with words from the target_script and adjusted timings.
        The segment start/end times will also be updated based on the aligned words.
    """
    if not target_script.strip():
        logger.warning("Target script is empty. Returning original transcribed segments.")
        return transcribed_segments

    if not transcribed_segments or not transcribed_segments[0].get("words"):
        logger.warning("Transcribed segments are empty or contain no words. Cannot align.")
        # Return an empty segment structure if input was bad
        return []

    # For now, assuming all words are in the first segment as per transcribe_locally's current output
    # If multiple segments were genuinely returned by ASR and need alignment, this logic would need a loop.
    whisper_words_flat_list = transcribed_segments[0].get("words", [])
    original_segment_start = float(transcribed_segments[0].get("start", 0.0))
    original_segment_end = float(transcribed_segments[0].get("end", 0.0))

    if not whisper_words_flat_list:
        logger.warning("No words in the first segment to align. Returning original (possibly empty) segments.")
        return transcribed_segments

    # --- Core alignment logic (similar to previous flat list version) ---
    processed_whisper_words = []
    for w in whisper_words_flat_list:
        if not all(k in w for k in ['word', 'start', 'end']):
            logger.warning(f"Skipping word in alignment due to missing keys: {w}")
            continue
        try:
            word_copy = dict(w)
            word_copy['start'] = float(word_copy['start'])
            word_copy['end'] = float(word_copy['end'])
            processed_whisper_words.append(word_copy)
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping word in alignment due to invalid start/end time: {w} ({e})")
            continue

    if not processed_whisper_words: # if all words failed processing
        logger.warning("All words failed pre-processing for alignment. Cannot align.")
        return transcribed_segments # return original as fallback
    whisper_words_flat_list = processed_whisper_words

    script_words_list = target_script.strip().split()
    asr_words_for_diff = [w['word'].strip().lower().rstrip(',.!?') for w in whisper_words_flat_list]
    script_words_for_diff = [s_word.lower().rstrip(',.!?') for s_word in script_words_list]

    matcher = difflib.SequenceMatcher(None, asr_words_for_diff, script_words_for_diff, autojunk=False)
    aligned_words_output: List[Dict[str, Any]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                original_script_word_text = script_words_list[j1 + k]
                word_to_add = original_script_word_text
                # Revised spacing logic for 'equal'
                is_first_aligned_output = not aligned_words_output
                is_first_word_in_block = k == 0
                asr_word_had_leading_space = whisper_words_flat_list[i1+k]['word'].startswith(' ')

                if not word_to_add.startswith(' '):
                    if not is_first_aligned_output: # If not the very first word we are adding to output
                        word_to_add = ' ' + word_to_add
                    elif is_first_aligned_output and is_first_word_in_block and asr_word_had_leading_space:
                        # First word of all, but ASR had a space (e.g. transcription started mid-sentence)
                        word_to_add = ' ' + word_to_add
                    # Else (first word overall, ASR didn't have space or script word already has one), no leading space added here.

                aligned_words_output.append({
                    'word': word_to_add,
                    'start': float(whisper_words_flat_list[i1 + k]['start']),
                    'end': float(whisper_words_flat_list[i1 + k]['end']),
                    'probability': whisper_words_flat_list[i1 + k].get('probability', 1.0)
                })
        elif tag == 'replace':
            total_asr_duration = sum(float(whisper_words_flat_list[i]['end']) - float(whisper_words_flat_list[i]['start']) for i in range(i1, i2))
            num_script_words_in_block = j2 - j1
            avg_duration_per_script_word = total_asr_duration / num_script_words_in_block if num_script_words_in_block > 0 else 0.2
            current_time = float(whisper_words_flat_list[i1]['start']) if i1 < i2 else (float(aligned_words_output[-1]['end']) if aligned_words_output else 0.0)

            for k_idx_in_block, script_offset in enumerate(range(j2 - j1)):
                original_script_word_text = script_words_list[j1 + script_offset]
                word_to_add = original_script_word_text
                # Add leading space if not the first word being added overall, or if it's not the first in this replace block
                if not word_to_add.startswith(' '):
                    if not aligned_words_output and k_idx_in_block == 0: # First word of all output and first in block
                        pass # No leading space for the very first word
                    else: # Otherwise, add space
                        word_to_add = ' ' + word_to_add

                start_t = current_time
                end_t = current_time + avg_duration_per_script_word
                aligned_words_output.append({
                    'word': word_to_add,
                    'start': start_t,
                    'end': end_t,
                    'probability': 0.6
                })
                current_time = end_t

        elif tag == 'delete':
            pass

        elif tag == 'insert':
            num_inserted_script_words = j2 - j1
            avg_duration = 0.3
            start_time_insert = 0.0
            if aligned_words_output:
                start_time_insert = float(aligned_words_output[-1]['end']) + 0.01
            elif i1 < len(whisper_words_flat_list):
                start_time_insert = float(whisper_words_flat_list[i1]['start']) - (avg_duration * num_inserted_script_words) - 0.01
                if start_time_insert < 0: start_time_insert = 0.01

            current_time_insert = start_time_insert
            for k_idx_in_block, script_offset in enumerate(range(j2 - j1)):
                original_script_word_text = script_words_list[j1 + script_offset]
                word_to_add = original_script_word_text

                if not word_to_add.startswith(' '):
                    if not aligned_words_output and k_idx_in_block == 0: # First word of all output and first in block
                        pass # No leading space if it's absolutely the first word
                    else:
                        word_to_add = ' ' + word_to_add

                start_t = current_time_insert
                end_t = current_time_insert + avg_duration
                aligned_words_output.append({
                    'word': word_to_add,
                    'start': start_t,
                    'end': end_t,
                    'probability': 0.4
                })
                current_time_insert = end_t
    # --- End of core alignment logic ---

    if not aligned_words_output:
        logger.warning("Alignment produced no words. Returning original segments.")
        return transcribed_segments # Fallback to original if alignment fails to produce output

    # Update segment start/end times based on the new aligned words
    new_segment_start = aligned_words_output[0].get("start", original_segment_start)
    new_segment_end = aligned_words_output[-1].get("end", original_segment_end)

    logger.info(f"Alignment: ASR words {len(whisper_words_flat_list)}, Script words {len(script_words_list)}, Final aligned words {len(aligned_words_output)}")

    return [{
        "words": aligned_words_output,
        "start": float(new_segment_start),
        "end": float(new_segment_end)
    }]

if __name__ == '__main__':
    # --- This is a basic test block ---
    # To run this test:
    # 1. Make sure you have a test audio file (e.g., 'test_audio.mp3') in the same directory or provide a full path.
    #    You can generate a short one using an online TTS or by recording yourself.
    # 2. Ensure 'openai-whisper' is installed: pip install openai-whisper
    # 3. Run this script directly: python backend/text_to_video/effects_engine/transcription.py

    logger.info("Running basic test for transcribe_locally...")

    # Create a dummy audio file for testing if one doesn't exist
    # For a real test, use an actual audio file with discernible speech.
    # This dummy file won't produce meaningful transcription but tests the flow.
    test_audio_file = "test.mp3"
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    test_audio_path = os.path.join(current_script_dir, "..", "..", "assets", "test", test_audio_file) # Assuming test.mp3 is in assets/test

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
        segments_result = transcribe_locally(
            test_audio_path_to_use,
            whisper_model_name="tiny",
        )

        if segments_result:
            logger.info(f"Successfully transcribed. Got {len(segments_result)} segment(s).")
            for i_seg, seg_data in enumerate(segments_result):
                logger.info(f"  Segment {i_seg+1}: Start={seg_data.get('start'):.2f}s, End={seg_data.get('end'):.2f}s, Words={len(seg_data.get('words',[]))}")
                if seg_data.get('words'):
                    logger.info("    First 5 words of segment (or fewer):")
                    for i_word, word_data_item in enumerate(seg_data['words'][:5]):
                        logger.info(f"      Word {i_word+1}: '{word_data_item.get('word')}' ({word_data_item.get('start'):.2f}-{word_data_item.get('end'):.2f})")

            # Test alignment
            sample_script = "This is a sample script to test the alignment function with our tiny model output."
            logger.info(f"\nTesting alignment with script: '{sample_script}'")
            if segments_result and segments_result[0].get('words'):
                flat_words_for_alignment = segments_result[0]['words']
                aligned_script_words = align_words_to_script(flat_words_for_alignment, sample_script)
                logger.info(f"Alignment produced {len(aligned_script_words)} words.")
                logger.info("First 5 aligned words:")
                for i, aword in enumerate(aligned_script_words[:5]):
                    logger.info(f"  Word {i+1}: '{aword.get('word')}' ({aword.get('start'):.2f}-{aword.get('end'):.2f})")
            else:
                logger.warning("No words from transcription to test alignment.")
        else:
            logger.warning("Transcription returned no segments.")
    else:
        logger.error("No audio file available to test transcription.")

    logger.info("Basic transcription test finished.")
