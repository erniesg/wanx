from pydub import AudioSegment
import logging
import os

logger = logging.getLogger(__name__)

def slice_audio(input_path: str, output_path: str, start_seconds: float, end_seconds: float) -> bool:
    """
    Slices a segment from an audio file and saves it.

    Args:
        input_path (str): Path to the input audio file.
        output_path (str): Path to save the sliced audio segment.
        start_seconds (float): Start time of the slice in seconds.
        end_seconds (float): End time of the slice in seconds.

    Returns:
        bool: True if slicing was successful, False otherwise.
    """
    try:
        if not os.path.exists(input_path):
            logger.error(f"Input audio file not found: {input_path}")
            return False

        # Convert seconds to milliseconds for pydub
        start_ms = int(start_seconds * 1000)
        end_ms = int(end_seconds * 1000)

        if start_ms < 0:
            logger.warning(f"Start time {start_seconds}s is negative, clamping to 0.")
            start_ms = 0

        if start_ms >= end_ms:
            logger.error(f"Start time {start_seconds}s is after or equal to end time {end_seconds}s. Cannot slice.")
            return False

        logger.info(f"Slicing audio from {input_path} (start: {start_seconds}s, end: {end_seconds}s) to {output_path}")

        # Load the audio file
        # pydub will attempt to determine the format from the extension,
        # or you can specify it with format="mp3" etc.
        audio = AudioSegment.from_file(input_path)

        if start_ms >= len(audio):
            logger.error(f"Start time {start_seconds}s is beyond the audio duration of {len(audio)/1000.0:.2f}s.")
            return False

        # Ensure end_ms does not exceed audio length
        if end_ms > len(audio):
            logger.warning(f"End time {end_seconds}s is beyond audio duration. Slicing till end of audio: {len(audio)/1000.0:.2f}s.")
            end_ms = len(audio)

        # Slice the audio
        sliced_audio = audio[start_ms:end_ms]

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Export the sliced audio
        # Default is mp3, pydub needs ffmpeg for this
        sliced_audio.export(output_path, format="mp3")

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Successfully sliced audio saved to {output_path}")
            return True
        else:
            logger.error(f"Failed to save sliced audio or file is empty at {output_path}")
            return False

    except Exception as e:
        logger.error(f"Error during audio slicing: {e}")
        # Log ffmpeg/ffprobe related errors if they commonly occur
        if "ffmpeg" in str(e).lower() or "ffprobe" in str(e).lower():
            logger.error("This error might be related to ffmpeg/ffprobe not being installed or not found in PATH.")
        return False

if __name__ == '__main__':
    # Basic test for slice_audio
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Testing audio_utils.py - slice_audio")

    # Create a dummy MP3 file for testing if you don't have one
    # This requires ffmpeg to be installed to create even a dummy mp3 with pydub
    dummy_input_dir = "../../test_outputs/temp_audio_slicing_test"
    dummy_input_filename = "dummy_test_input.mp3"
    dummy_input_path = os.path.join(dummy_input_dir, dummy_input_filename)

    dummy_output_dir = "../../test_outputs/temp_audio_slicing_test/output_slices"
    dummy_output_filename = "dummy_test_slice_0_5.mp3"
    dummy_output_path = os.path.join(dummy_output_dir, dummy_output_filename)

    os.makedirs(dummy_input_dir, exist_ok=True)
    os.makedirs(dummy_output_dir, exist_ok=True)

    try:
        # Create a 10-second silent mp3 for testing
        silence = AudioSegment.silent(duration=10000) # 10 seconds
        # Add a simple tone to make it audible if needed
        # from pydub.generators import Sine
        # tone = Sine(440).to_audio_segment(duration=10000).apply_gain(-20) # A4 tone for 10s
        # combined = silence.overlay(tone)
        # combined.export(dummy_input_path, format="mp3")
        silence.export(dummy_input_path, format="mp3")
        logger.info(f"Created dummy input MP3: {dummy_input_path}")

        if os.path.exists(dummy_input_path):
            # Test 1: Slice from 0 to 5 seconds
            success = slice_audio(dummy_input_path, dummy_output_path, 0.0, 5.0)
            if success:
                logger.info(f"Test 1 SUCCEEDED: Slice created at {dummy_output_path}")
                # Verify duration (approximate)
                try:
                    segment = AudioSegment.from_file(dummy_output_path)
                    logger.info(f"Sliced audio duration: {len(segment) / 1000.0}s (expected approx 5.0s)")
                    assert 4900 < len(segment) < 5100, "Slice duration incorrect"
                except Exception as e:
                    logger.error(f"Could not verify slice duration: {e}")
            else:
                logger.error("Test 1 FAILED to create slice.")

            # Test 2: Slice from 7 to 12 seconds (should clamp at 10s)
            dummy_output_path_2 = os.path.join(dummy_output_dir, "dummy_test_slice_7_end.mp3")
            success_2 = slice_audio(dummy_input_path, dummy_output_path_2, 7.0, 12.0)
            if success_2:
                logger.info(f"Test 2 SUCCEEDED: Slice created at {dummy_output_path_2}")
                try:
                    segment = AudioSegment.from_file(dummy_output_path_2)
                    logger.info(f"Sliced audio duration: {len(segment) / 1000.0}s (expected approx 3.0s)")
                    assert 2900 < len(segment) < 3100, "Slice duration incorrect for clamped end"
                except Exception as e:
                    logger.error(f"Could not verify slice duration for Test 2: {e}")
            else:
                logger.error("Test 2 FAILED to create slice.")

            # Test 3: Invalid slice (start after end)
            dummy_output_path_3 = os.path.join(dummy_output_dir, "dummy_test_slice_invalid.mp3")
            success_3 = slice_audio(dummy_input_path, dummy_output_path_3, 5.0, 2.0)
            if not success_3:
                logger.info(f"Test 3 SUCCEEDED (expected failure): Invalid slice was not created.")
            else:
                logger.error("Test 3 FAILED: Invalid slice was somehow created.")

        else:
            logger.error(f"Dummy input file {dummy_input_path} was not created. Cannot run tests.")
            logger.error("This might be due to ffmpeg not being installed or accessible in your PATH.")

    except Exception as e:
        logger.error(f"Error during __main__ test setup or execution: {e}")
        logger.error("Ensure ffmpeg is installed and in your PATH for pydub to work correctly, especially for MP3 export.")
