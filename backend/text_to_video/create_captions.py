import captacity
import os
import logging

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
            return output_file
        else:
            logger.error(f"Caption generation completed but output file not found: {output_file}")
            return None

    except Exception as e:
        logger.error(f"Error adding captions: {str(e)}")
        return None
