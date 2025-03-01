import captacity
import os
import logging
from moviepy.editor import VideoFileClip, AudioFileClip

logger = logging.getLogger("TikTokCreator")

def add_bottom_captions(video_file, output_file=None):
    """
    Add captions at the bottom of a video file.

    Args:
        video_file (str): Path to the input video
        output_file (str, optional): Path for the output video. If None, appends "_captioned" to input filename.

    Returns:
        str: Path to the captioned video or None if failed
    """
    if not os.path.exists(video_file):
        logger.error(f"Input video file does not exist: {video_file}")
        return None

    if output_file is None:
        # Create a default output filename if none provided
        name_parts = video_file.rsplit('.', 1)
        output_file = f"{name_parts[0]}_captioned.{name_parts[1]}" if len(name_parts) > 1 else f"{video_file}_captioned"

    try:
        # Extract audio from original video before adding captions
        logger.info(f"Extracting audio from original video: {video_file}")
        original_video = VideoFileClip(video_file)
        original_audio = original_video.audio

        # If the original video has no audio, log a warning
        if original_audio is None:
            logger.warning(f"Original video has no audio track: {video_file}")
            original_video.close()
            return None

        # Create a temporary audio file
        temp_audio_file = f"{name_parts[0]}_temp_audio.mp3"
        original_audio.write_audiofile(temp_audio_file)
        original_video.close()

        # Add captions to the video
        captacity.add_captions(
            video_file=video_file,
            output_file=output_file,
            font_size=80,
            font_color="yellow",
            stroke_width=3,
            stroke_color="black",
            shadow_strength=1.0,
            shadow_blur=0.1,
            highlight_current_word=True,
            word_highlight_color="red",
            line_count=1,
            position="bottom",
            padding=70,
            use_local_whisper=True
        )

        if os.path.exists(output_file):
            logger.info(f"Successfully added captions to video: {output_file}")

            # Now add the original audio back to the captioned video
            logger.info(f"Adding original audio back to captioned video")
            captioned_video = VideoFileClip(output_file)
            audio_clip = AudioFileClip(temp_audio_file)

            # Set the audio to the captioned video
            final_video = captioned_video.set_audio(audio_clip)

            # Save the final video with audio
            temp_output = f"{name_parts[0]}_with_audio.{name_parts[1]}"
            final_video.write_videofile(temp_output, codec="libx264", audio_codec="aac")

            # Close clips to free resources
            captioned_video.close()
            audio_clip.close()
            final_video.close()

            # Replace the captioned file with the one that has audio
            os.replace(temp_output, output_file)

            # Clean up temporary audio file
            if os.path.exists(temp_audio_file):
                os.remove(temp_audio_file)

            return output_file
        else:
            logger.error(f"Caption generation completed but output file not found: {output_file}")
            return None

    except Exception as e:
        logger.error(f"Error adding captions: {str(e)}")
        # Clean up any temporary files if they exist
        temp_audio_file = f"{name_parts[0]}_temp_audio.mp3"
        if os.path.exists(temp_audio_file):
            os.remove(temp_audio_file)
        return None
