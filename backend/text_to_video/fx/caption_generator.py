import os
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from moviepy.editor import VideoClip, CompositeVideoClip, ColorClip # type: ignore

# Import from the new local modules
from .text_drawer import create_text_ex, get_text_size_ex, Word as DrawerWord, Character as DrawerCharacter
from .segment_parser import parse as parse_segments

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CaptionStyleConfig:
    # Font properties
    font_path: str = "Arial"
    font_size: int = 72 # Adjusted default based on previous tests
    font_color: str = "white"

    # Background/Stroke for text emphasis
    stroke_color: Optional[str] = "black"
    stroke_width: int = 3 # Adjusted default
    kerning: float = 0.0 # Matches text_drawer.create_text_ex

    # Opacity and Blur (from text_drawer)
    opacity: float = 1.0
    blur_radius: int = 0
    bg_color: str = 'transparent' # For create_text_ex pass-through

    # Positioning - using a simple pixel padding from edge
    position_preset: str = "bottom_center" # e.g., "bottom_center", "top_center", "center_center"
    padding_from_edge: int = 50 # Pixel padding from the relevant video edge

    # Line breaking for segment_parser
    video_width_percent_for_text: float = 90.0 # Text should not exceed this % of video width
    allow_partial_sentences: bool = False

DEFAULT_STYLE_CONFIG = CaptionStyleConfig()

def generate_moviepy_caption_clips(
    timed_words: List[Dict[str, Any]],
    video_dimensions: Tuple[int, int],
    style_config: CaptionStyleConfig = DEFAULT_STYLE_CONFIG,
) -> List[CompositeVideoClip]:
    video_w, video_h = video_dimensions
    all_caption_clips: List[CompositeVideoClip] = []

    if not timed_words:
        logger.info("No timed words provided, returning empty list of clips.")
        return all_caption_clips

    segments_for_parser = [{"words": timed_words}]
    max_text_width_px = video_w * (style_config.video_width_percent_for_text / 100.0)

    def fit_function(text_line: str) -> bool:
        if not text_line.strip(): return True
        try:
            text_w, _ = get_text_size_ex(
                text=text_line,
                font=style_config.font_path,
                fontsize=style_config.font_size,
                stroke_width=style_config.stroke_width
            )
            return text_w <= max_text_width_px
        except Exception as e:
            logger.error(f"Error in fit_function for '{text_line}': {e}", exc_info=True)
            return False

    parsed_caption_lines: List[Dict[str, Any]] = parse_segments(
        segments=segments_for_parser,
        fit_function=fit_function,
        allow_partial_sentences=style_config.allow_partial_sentences
    )
    logger.info(f"Parsed {len(timed_words)} words into {len(parsed_caption_lines)} caption lines.")

    for i, line_data in enumerate(parsed_caption_lines):
        text_content = line_data.get("text")
        start_time_val = line_data.get("start") # segment_parser output uses "start" and "end"
        end_time_val = line_data.get("end")

        if text_content is None or start_time_val is None or end_time_val is None:
            logger.warning(f"Skipping line {i+1} due to missing data: {line_data}")
            continue

        duration = float(end_time_val) - float(start_time_val)
        if duration <= 0:
            logger.warning(f'Caption line {i+1} (\"{text_content}\") has non-positive duration ({duration}s). Skipping.')
            continue

        try:
            caption_clip: CompositeVideoClip = create_text_ex(
                text=text_content,
                fontsize=style_config.font_size,
                color=style_config.font_color,
                font=style_config.font_path,
                bg_color=style_config.bg_color, # Pass through
                stroke_color=style_config.stroke_color,
                stroke_width=style_config.stroke_width,
                kerning=style_config.kerning,
                opacity=style_config.opacity,
                blur_radius=style_config.blur_radius
                # video_height is NOT passed as per user's text_drawer.py for create_text_ex
            )

            if not caption_clip or caption_clip.size == (0,0) or not caption_clip.clips:
                logger.warning(f'create_text_ex returned an empty/invalid clip for text: "{text_content}". Skipping.')
                continue

            caption_clip = caption_clip.set_start(start_time_val).set_duration(duration)

            clip_w, clip_h = caption_clip.size
            if clip_w is None or clip_h is None or clip_h == 0: # Additional check for valid clip dimensions
                logger.warning(f'Caption clip for "{text_content}" has invalid dimensions ({clip_w}x{clip_h}). Skipping.')
                continue

            pos_x: Any = 'center'
            pos_y: Any

            if style_config.position_preset == "bottom_center":
                pos_y = video_h - clip_h - style_config.padding_from_edge
            elif style_config.position_preset == "top_center":
                pos_y = style_config.padding_from_edge
            elif style_config.position_preset == "center_center":
                pos_y = (video_h - clip_h) / 2
            else: # Default to bottom_center if preset is unknown
                logger.warning(f"Unknown position_preset: '{style_config.position_preset}'. Defaulting to bottom_center.")
                pos_y = video_h - clip_h - style_config.padding_from_edge

            # Ensure x is also calculated if not 'center' for some presets later
            if pos_x == 'center':
                pass # MoviePy handles 'center' for x
            # elif pos_x calculation needed for other presets...

            final_positioned_clip = caption_clip.set_position((pos_x, pos_y))
            all_caption_clips.append(final_positioned_clip)

        except Exception as e:
            logger.error(f'Failed to create/position caption clip for "{text_content}": {e}', exc_info=True)

    return all_caption_clips


if __name__ == '__main__':
    logger.info("Running basic tests for caption_generator.py (v4 - using presumed captacity modules)...")

    sample_timed_words_long = [
        {'word': ' Baidu', 'start': 0.0, 'end': 0.5}, {'word': ' Inc.', 'start': 0.5, 'end': 1.0},
        {'word': ' is', 'start': 1.0, 'end': 1.3}, {'word': ' set', 'start': 1.3, 'end': 1.5},
        {'word': ' to', 'start': 1.5, 'end': 1.6}, {'word': ' release', 'start': 1.6, 'end': 2.0},
        {'word': ' its', 'start': 2.0, 'end': 2.2}, {'word': ' Ernie', 'start': 2.2, 'end': 2.4},
        {'word': ' Bot', 'start': 2.4, 'end': 2.7}, {'word': ' in', 'start': 2.7, 'end': 3.2},
        {'word': ' March.', 'start': 3.2, 'end': 4.0},
        {'word': ' This', 'start': 4.1, 'end': 4.5}, {'word': ' is', 'start': 4.5, 'end': 4.7},
        {'word': ' a', 'start': 4.7, 'end': 4.8}, {'word': ' much', 'start': 4.8, 'end': 5.1},
        {'word': ' longer', 'start': 5.1, 'end': 5.5}, {'word': ' sentence', 'start': 5.5, 'end': 6.0},
        {'word': ' intended', 'start': 6.0, 'end': 6.4}, {'word': ' to', 'start': 6.4, 'end': 6.5},
        {'word': ' test', 'start': 6.5, 'end': 6.8}, {'word': ' the', 'start': 6.8, 'end': 7.0},
        {'word': ' line', 'start': 7.0, 'end': 7.3}, {'word': ' breaking', 'start': 7.3, 'end': 7.8},
        {'word': ' capabilities', 'start': 7.8, 'end': 8.5},{'word': ' extensively.', 'start': 8.5, 'end': 9.0},
    ]

    video_dimensions_test = (1080, 1920) # Vertical TikTok-style

    test_style = CaptionStyleConfig()
    test_style.font_size = 90 # Increased font size for testing visibility
    test_style.font_color = "yellow"
    test_style.stroke_color = "black"
    test_style.stroke_width = 4 # Increased stroke width
    test_style.padding_from_edge = 60 # Adjusted padding
    test_style.kerning = -2

    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    font_dir = os.path.join(current_script_dir, "..", "..", "assets", "fonts")
    assumed_font_filename = "Roboto-Bold.ttf"
    test_font_path = os.path.join(font_dir, assumed_font_filename)

    if os.path.exists(test_font_path):
        logger.info(f"Using font for test: {test_font_path}")
        test_style.font_path = test_font_path
    else:
        logger.warning(f"Test font file NOT FOUND: {test_font_path}. Using Arial.")
        test_style.font_path = "Arial"

    logger.info(f"--- Test: Generating caption clips with Style: {test_style} ---")
    generated_clips = generate_moviepy_caption_clips(
        timed_words=sample_timed_words_long,
        video_dimensions=video_dimensions_test,
        style_config=test_style
    )

    if generated_clips:
        logger.info(f"Successfully generated {len(generated_clips)} caption clips.")
        total_duration = 0.0
        if sample_timed_words_long:
            last_word_end_time = sample_timed_words_long[-1].get("end")
            total_duration = float(last_word_end_time) if isinstance(last_word_end_time, (int, float)) else 9.0
        if generated_clips and generated_clips[-1].end is not None and generated_clips[-1].end > total_duration:
            total_duration = generated_clips[-1].end
        if total_duration <=0 : total_duration = 9.0

        background_clip = ColorClip(size=video_dimensions_test, color=(50, 50, 50), duration=total_duration)
        final_composition = CompositeVideoClip([background_clip] + generated_clips, size=video_dimensions_test)
        output_filename_test = "output_captions_test_v4.mp4"
        output_path_test = os.path.join(current_script_dir, output_filename_test)

        logger.info(f"Attempting to render test video to: {output_path_test}")
        try:
            final_composition.write_videofile(
                output_path_test, fps=24, codec="libx264", audio_codec="aac", threads=4, logger='bar'
            )
            logger.info(f"Test video rendered: '{output_filename_test}'. Please inspect.")
        except Exception as render_e:
            logger.error(f"Failed to render test video: {render_e}", exc_info=True)
    else:
        logger.warning("No caption clips were generated.")
    logger.info("\nBasic tests for caption_generator.py (v4) finished.")

# To run this test directly (ensure effects_engine is in PYTHONPATH or run from project root):
# python -m effects_engine.caption_generator
# Or if in effects_engine directory:
# python caption_generator.py (might need `..` for imports if not a package)
