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

    # Word highlighting
    highlight_color: str = "red"
    highlight_current_word: bool = False

DEFAULT_STYLE_CONFIG = CaptionStyleConfig()

def generate_moviepy_caption_clips(
    segments_data: List[Dict[str, Any]],
    video_dimensions: Tuple[int, int],
    style_config: CaptionStyleConfig = DEFAULT_STYLE_CONFIG,
) -> List[CompositeVideoClip]:
    video_w, video_h = video_dimensions
    all_caption_clips: List[CompositeVideoClip] = []

    if not segments_data or not any(s.get("words") for s in segments_data):
        logger.info("No segments or words provided to generate_moviepy_caption_clips.")
        return all_caption_clips

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
        segments=segments_data,
        fit_function=fit_function,
        allow_partial_sentences=style_config.allow_partial_sentences
    )

    total_word_count = sum(len(s.get("words", [])) for s in segments_data)
    logger.info(f"Parsed {total_word_count} words from {len(segments_data)} segment(s) into {len(parsed_caption_lines)} caption lines.")

    for i, line_data in enumerate(parsed_caption_lines):
        text_content_for_line = line_data.get("text")
        line_start_time = line_data.get("start")
        line_end_time = line_data.get("end")
        words_in_line = line_data.get("words", [])

        if not text_content_for_line or line_start_time is None or line_end_time is None or not words_in_line:
            logger.warning(f"Skipping line {i+1} due to incomplete data: {line_data}")
            continue

        line_duration = float(line_end_time) - float(line_start_time)
        if line_duration <= 0:
            logger.warning(f'Caption line {i+1} ("{text_content_for_line}") has non-positive duration ({line_duration}s). Skipping.')
            continue

        if style_config.highlight_current_word:
            for word_idx, active_word_info in enumerate(words_in_line):
                active_word_text = active_word_info["word"]
                active_word_start_time = float(active_word_info["start"])

                highlight_end_time = float(line_end_time)
                if word_idx + 1 < len(words_in_line):
                    next_word_start_time = float(words_in_line[word_idx+1]["start"])
                    highlight_end_time = min(next_word_start_time, float(line_end_time))

                highlight_duration = highlight_end_time - active_word_start_time
                if highlight_duration <= 0:
                    continue

                drawer_words_for_highlight: List[DrawerWord] = []
                current_offset_in_line = 0

                temp_line_text_iter = text_content_for_line.lstrip()
                original_words_in_line_for_drawing = []
                for w_obj_idx, w_obj_info in enumerate(words_in_line):
                    original_words_in_line_for_drawing.append(DrawerWord(w_obj_info['word'].lstrip() if w_obj_idx == 0 else w_obj_info['word']))

                for w_obj_idx, w_obj in enumerate(original_words_in_line_for_drawing):
                    if w_obj_idx == word_idx:
                        w_obj.set_color(style_config.highlight_color)
                    else:
                        w_obj.set_color(style_config.font_color)
                    drawer_words_for_highlight.append(w_obj)

                try:
                    caption_clip_highlight: CompositeVideoClip = create_text_ex(
                        text=drawer_words_for_highlight,
                        fontsize=style_config.font_size,
                        color=style_config.font_color,
                        font=style_config.font_path,
                        stroke_color=style_config.stroke_color,
                        stroke_width=style_config.stroke_width,
                        kerning=style_config.kerning,
                        opacity=style_config.opacity,
                        blur_radius=style_config.blur_radius,
                        bg_color=style_config.bg_color
                    )
                    if not caption_clip_highlight or not caption_clip_highlight.clips:
                        logger.warning(f"create_text_ex returned empty for highlight state: '{text_content_for_line}'")
                        continue

                    caption_clip_highlight = caption_clip_highlight.set_start(active_word_start_time).set_duration(highlight_duration)
                    pos_x_hl: Any = 'center'
                    pos_y_hl: Any
                    clip_w_hl, clip_h_hl = caption_clip_highlight.size
                    if clip_h_hl == 0: continue

                    if style_config.position_preset == "bottom_center": pos_y_hl = video_h - clip_h_hl - style_config.padding_from_edge
                    elif style_config.position_preset == "top_center": pos_y_hl = style_config.padding_from_edge
                    elif style_config.position_preset == "center_center": pos_y_hl = (video_h - clip_h_hl) / 2
                    else: pos_y_hl = video_h - clip_h_hl - style_config.padding_from_edge

                    all_caption_clips.append(caption_clip_highlight.set_position((pos_x_hl, pos_y_hl)))

                except Exception as e_hl:
                    logger.error(f'Failed to create/position highlight clip for "{active_word_text}" in "{text_content_for_line}": {e_hl}', exc_info=True)

        else:
            try:
                caption_clip_no_highlight: CompositeVideoClip = create_text_ex(
                    text=text_content_for_line,
                    fontsize=style_config.font_size,
                    color=style_config.font_color,
                    font=style_config.font_path,
                    stroke_color=style_config.stroke_color,
                    stroke_width=style_config.stroke_width,
                    kerning=style_config.kerning,
                    opacity=style_config.opacity,
                    blur_radius=style_config.blur_radius,
                    bg_color=style_config.bg_color
                )
                if not caption_clip_no_highlight or not caption_clip_no_highlight.clips:
                    logger.warning(f"create_text_ex returned empty for non-highlighted line: '{text_content_for_line}'")
                    continue

                caption_clip_no_highlight = caption_clip_no_highlight.set_start(line_start_time).set_duration(line_duration)

                pos_x: Any = 'center'
                pos_y: Any
                clip_w, clip_h = caption_clip_no_highlight.size
                if clip_h == 0: continue

                if style_config.position_preset == "bottom_center": pos_y = video_h - clip_h - style_config.padding_from_edge
                elif style_config.position_preset == "top_center": pos_y = style_config.padding_from_edge
                elif style_config.position_preset == "center_center": pos_y = (video_h - clip_h) / 2
                else: pos_y = video_h - clip_h - style_config.padding_from_edge

                all_caption_clips.append(caption_clip_no_highlight.set_position((pos_x, pos_y)))

            except Exception as e_nohl:
                logger.error(f'Failed to create/position non-highlight clip for "{text_content_for_line}": {e_nohl}', exc_info=True)

    logger.info(f"Generated {len(all_caption_clips)} total MoviePy clips for captions.")
    return all_caption_clips


if __name__ == '__main__':
    logger.info("Running basic tests for caption_generator.py (captacity-aligned structure)...")

    sample_segments_test = [
        {
            "start": 0.0, "end": 9.0,
            "words": [
                {'word': ' Baidu', 'start': 0.0, 'end': 0.5, 'probability': 0.9},
                {'word': ' Inc.', 'start': 0.5, 'end': 1.0, 'probability': 0.9},
                {'word': ' is', 'start': 1.0, 'end': 1.3, 'probability': 0.9},
                {'word': ' set', 'start': 1.3, 'end': 1.5, 'probability': 0.9},
                {'word': ' to', 'start': 1.5, 'end': 1.6, 'probability': 0.9},
                {'word': ' release', 'start': 1.6, 'end': 2.0, 'probability': 0.9},
                {'word': ' its', 'start': 2.0, 'end': 2.2, 'probability': 0.9},
                {'word': ' Ernie', 'start': 2.2, 'end': 2.4, 'probability': 0.9},
                {'word': ' Bot', 'start': 2.4, 'end': 2.7, 'probability': 0.9},
                {'word': ' in', 'start': 2.7, 'end': 3.2, 'probability': 0.9},
                {'word': ' March.', 'start': 3.2, 'end': 4.0, 'probability': 0.9},
                {'word': ' This', 'start': 4.1, 'end': 4.5, 'probability': 0.9},
                {'word': ' is', 'start': 4.5, 'end': 4.7, 'probability': 0.9},
                {'word': ' a', 'start': 4.7, 'end': 4.8, 'probability': 0.9},
                {'word': ' much', 'start': 4.8, 'end': 5.1, 'probability': 0.9},
                {'word': ' longer', 'start': 5.1, 'end': 5.5, 'probability': 0.9},
                {'word': ' sentence', 'start': 5.5, 'end': 6.0, 'probability': 0.9},
                {'word': ' intended', 'start': 6.0, 'end': 6.4, 'probability': 0.9},
                {'word': ' to', 'start': 6.4, 'end': 6.5, 'probability': 0.9},
                {'word': ' test', 'start': 6.5, 'end': 6.8, 'probability': 0.9},
                {'word': ' the', 'start': 6.8, 'end': 7.0, 'probability': 0.9},
                {'word': ' line', 'start': 7.0, 'end': 7.3, 'probability': 0.9},
                {'word': ' breaking', 'start': 7.3, 'end': 7.8, 'probability': 0.9},
                {'word': ' capabilities', 'start': 7.8, 'end': 8.5, 'probability': 0.9},
                {'word': ' extensively.', 'start': 8.5, 'end': 9.0, 'probability': 0.9},
            ]
        }
    ]

    video_dimensions_test = (1080, 1920)
    test_style = CaptionStyleConfig(
        font_size=90,
        font_color="yellow",
        stroke_color="black",
        stroke_width=4,
        padding_from_edge=60,
        kerning=-2,
        highlight_current_word=True,
        highlight_color="red"
    )

    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    font_dir = os.path.join(current_script_dir, "..", "..", "assets", "fonts")
    assumed_font_filename = "Roboto-Bold.ttf"
    test_font_path = os.path.join(font_dir, assumed_font_filename)

    if os.path.exists(test_font_path):
        test_style.font_path = test_font_path
    else:
        logger.warning(f"Test font file NOT FOUND: {test_font_path}. Using Arial.")
        test_style.font_path = "Arial"

    logger.info(f"--- Test: Generating caption clips with Style: {test_style} ---")
    generated_clips = generate_moviepy_caption_clips(
        segments_data=sample_segments_test,
        video_dimensions=video_dimensions_test,
        style_config=test_style
    )

    if generated_clips:
        logger.info(f"Successfully generated {len(generated_clips)} caption clips for test.")
        total_duration_test = 0.0
        if sample_segments_test and sample_segments_test[0]["words"]:
             last_word_end_time = sample_segments_test[0]["words"][-1].get("end")
             total_duration_test = float(last_word_end_time) if isinstance(last_word_end_time, (int, float)) else 9.0
        if total_duration_test <=0 : total_duration_test = 9.0

        background_clip = ColorClip(size=video_dimensions_test, color=(50, 50, 50), duration=total_duration_test)
        final_composition = CompositeVideoClip([background_clip] + generated_clips, size=video_dimensions_test).set_duration(total_duration_test)

        output_filename_test = "output_captions_test_highlight.mp4"
        output_path_test = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename_test)

        logger.info(f"Attempting to render test video to: {output_path_test}")
        try:
            final_composition.write_videofile(
                output_path_test, fps=24, codec="libx264", audio_codec="aac", threads=4, logger='bar'
            )
            logger.info(f"Test video rendered: '{output_filename_test}'. Please inspect.")
        except Exception as render_e:
            logger.error(f"Failed to render test video: {render_e}", exc_info=True)
    else:
        logger.warning("No caption clips generated for test.")
    logger.info("Caption_generator.py tests finished.")

# To run this test directly (ensure effects_engine is in PYTHONPATH or run from project root):
# python -m effects_engine.caption_generator
# Or if in effects_engine directory:
# python caption_generator.py (might need `..` for imports if not a package)
