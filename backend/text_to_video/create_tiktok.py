import logging
from .editor import combine_audio_video, combine_project
from .utils import get_audio_length
from .video_guy import create_video_content, generate_videos
from .tts import text_to_speech, sanitize_filename
import os
import re
from .generate_script import transform_to_script
from .create_captions import add_bottom_captions

# Configure logging
# Create logs directory in backend
backend_dir = os.path.dirname(os.path.dirname(__file__))
log_dir = os.path.join(backend_dir, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "tiktok_creation.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TikTokCreator")

def sanitize_project_name(name):
    """
    Sanitize a project name by removing spaces and special characters.

    Args:
        name (str): The project name to sanitize

    Returns:
        str: Sanitized project name
    """
    # Replace spaces with underscores and remove special characters
    sanitized = re.sub(r'[^\w\-_.]', '_', name.replace(' ', '_'))
    return sanitized

def create_tiktok(content, log_callback=None, job_id=None):
    """
    Create a TikTok video from content with progress updates via callback.

    Args:
        content (str): The content to create a video from
        log_callback (callable, optional): Function to call with status updates
        job_id (str, optional): Unique identifier for this job

    Returns:
        str: Path to the final video
    """
    # Send initial status
    if log_callback:
        log_callback("Starting to process content...")

    logger.info("Starting TikTok creation process")

    # Use job_id as the project name if provided, otherwise sanitize content
    if job_id:
        project_name = job_id
        logger.info(f"Using job_id as project name: {project_name}")
    else:
        project_name = sanitize_project_name(content[:10])
        logger.info(f"Using sanitized content as project name: {project_name}")

    # Create necessary directories with consistent paths
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    assets_dir = os.path.join(backend_dir, "assets")
    audio_dir = os.path.join(assets_dir, "audio", "speech")
    videos_dir = os.path.join(assets_dir, "videos")

    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(videos_dir, exist_ok=True)

    if log_callback:
        log_callback("Transforming content to script...")

    script = transform_to_script(content)
    if not script:
        logger.error("Failed to transform content to script")
        if log_callback:
            log_callback("Error: Failed to transform content to script")
        return None

    audio_file = f"{project_name}.mp3"
    audio_path = os.path.join(audio_dir, audio_file)
    logger.info(f"Project name: {project_name}")
    logger.info(f"Audio will be saved to: {audio_path}")

    if log_callback:
        log_callback("Generating audio from script...")

    # Generate audio from text
    logger.info("Generating speech from text")
    audio_path = text_to_speech(script, audio_file)

    # Add additional validation for the audio file
    if not audio_path or not os.path.exists(audio_path):
        logger.error(f"Failed to create audio file: {audio_file}")
        if log_callback:
            log_callback("Error: Failed to create audio file")
        return None

    # Verify the audio file is valid
    logger.info(f"Verifying audio file integrity: {audio_path}")
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(audio_path)
        logger.info(f"Audio file verified: {audio_path}, duration: {len(audio)/1000} seconds")
        audio_length = len(audio)/1000  # Convert milliseconds to seconds
    except Exception as e:
        logger.error(f"Error verifying audio file: {str(e)}")
        if log_callback:
            log_callback(f"Error: Audio file verification failed: {str(e)}")
        # Try to get length using get_audio_length as fallback
        audio_length = get_audio_length(audio_path)
        if audio_length is None:
            logger.error("Failed to get audio length, using default length of 30 seconds")
            audio_length = 30  # Default to 30 seconds if we can't determine length
            if log_callback:
                log_callback("Warning: Using default audio length of 30 seconds")

    logger.info(f"Audio length: {audio_length} seconds")

    # Calculate number of videos needed
    num_videos = max(1, int(audio_length / 6))
    logger.info(f"Generating {num_videos} videos (6 seconds each)")

    if log_callback:
        log_callback(f"Creating {num_videos} video segments...")

    # Generate video prompts and create videos
    logger.info("Creating video content prompts")
    # Create videos directory for this project
    project_videos_dir = os.path.join(videos_dir, project_name)
    os.makedirs(project_videos_dir, exist_ok=True)

    # Pass the project_name to create_video_content
    video_project_name = create_video_content(content, num_videos=num_videos, project_name=project_name)

    # Check if project_name is None
    if video_project_name is None:
        logger.error("Failed to create video content")
        if log_callback:
            log_callback("Error: Failed to create video content")
        return None

    # Combine audio and videos
    if log_callback:
        log_callback("Combining audio and videos...")

    output_file = f"{project_name}_tiktok.mp4"
    logger.info(f"Combining audio and videos into {output_file}")

    # Pass the full audio_path to combine_project
    final_video = combine_project(project_name, audio_path=audio_path)

    if not final_video or not os.path.exists(final_video):
        logger.error("Failed to create TikTok video")
        if log_callback:
            log_callback("Error: Failed to create final video")
        return None

    try:
        # Add captions to the final video
        if log_callback:
            log_callback("Adding captions to video...")

        logger.info(f"Adding captions to the video")
        captioned_video = add_bottom_captions(final_video)

        if not captioned_video or not os.path.exists(captioned_video):
            logger.warning("Failed to add captions, returning uncaptioned video")
            if log_callback:
                log_callback("Warning: Failed to add captions, using uncaptioned video")
            return final_video

        logger.info(f"TikTok video with captions created: {captioned_video}")
        if log_callback:
            log_callback("Video creation complete!")
        return captioned_video
    except Exception as e:
        logger.error(f"Error adding captions: {str(e)}")
        logger.info("Returning video without captions")
        if log_callback:
            log_callback(f"Warning: Error adding captions: {str(e)}")
        return final_video


if __name__ == "__main__":
    logger.info("=== Starting new TikTok creation session ===")

    content = "Tesla shares rose by 14.8% on Wednesday as investors speculated about possible policy changes under a Trump presidency. The electric car maker, led by CEO Elon Musk, may benefit if subsidies for alternative energy decrease and tariffs on Chinese imports increase. Other electric vehicle makers saw their stocks decline. Shanghai-based Nio's shares fell by 5.3%, while Rivian and Lucid Group's shares dropped by 8.3% and 5.3%, respectively. Despite the surge, Tesla recently faced a downturn following an underwhelming robotaxi unveiling."

    try:
        final_video = create_tiktok(content)
        logger.info(f"Process completed. Final video: {final_video}")
    except Exception as e:
        logger.exception(f"Error in TikTok creation process: {e}")

    logger.info("=== TikTok creation session ended ===")
