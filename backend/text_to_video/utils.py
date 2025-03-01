from pydub import AudioSegment
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_audio_length(audio_file_path):
    """
    Get the length of an audio file in seconds.
    
    Args:
        audio_file_path (str): Path to the audio file
        
    Returns:
        float: Length of the audio in seconds
    """
    try:
        logger.info(f"Getting audio length for: {audio_file_path}")
        audio = AudioSegment.from_file(audio_file_path)
        # Duration is in milliseconds, convert to seconds
        duration_seconds = len(audio) / 1000.0
        logger.info(f"Audio duration: {duration_seconds:.2f} seconds")
        return duration_seconds
    except Exception as e:
        logger.error(f"Error getting audio length: {e}")
        return None
    
if __name__ == "__main__":
    # Specify the audio file path directly
    audio_file = "/Users/techinasia/text-to-shorts/audio/speech/Tesla shar.mp3"  # Replace with your actual file path
    
    logger.info(f"Checking audio length for: {audio_file}")
    duration = get_audio_length(audio_file)
    
    if duration is not None:
        print(f"Audio duration: {duration:.2f} seconds")
    else:
        print("Failed to get audio duration.")