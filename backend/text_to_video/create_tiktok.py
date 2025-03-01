import logging
from editor import combine_audio_video, combine_project
from utils import get_audio_length
from video_guy import create_video_content, generate_videos
from tts import text_to_speech
import os
from generate_script import transform_to_script
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tiktok_creation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TikTokCreator")

def create_tiktok(content: str):
    logger.info("Starting TikTok creation process")
    
    script = transform_to_script(content)
    
    # Generate video prompts
    project_name = content[:10]
    audio_file = f"{project_name}.mp3"
    logger.info(f"Project name: {project_name}")
    
    # Generate audio from text
    logger.info("Generating speech from text")
    text_to_speech(script, audio_file)
    logger.info(f"Audio saved to {audio_file}")
    
    # Get audio length
    audio_length = get_audio_length(f"audio/speech/{audio_file}")
    logger.info(f"Audio length: {audio_length} seconds")
    
    # Calculate number of videos needed
    num_videos = max(1, int(audio_length / 6))
    logger.info(f"Generating {num_videos} videos (6 seconds each)")
    
    # Generate video prompts and create videos
    logger.info("Creating video content prompts")
    os.makedirs(f"videos/{project_name}", exist_ok=True)
    project_name = create_video_content(content, num_videos=num_videos, project_name=project_name)
    
    # Check if project_name is None
    if project_name is None:
        logger.error("Failed to create video content")
        return None
    
    # Combine audio and videos
    output_file = f"{project_name}_tiktok.mp4"
    logger.info(f"Combining audio and videos into {output_file}")
    final_video = combine_project(project_name)
    
    if final_video:
        logger.info(f"TikTok video created successfully: {final_video}")
    else:
        logger.error("Failed to create TikTok video")
    
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

