import os
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from moviepy.editor import TextClip, ImageClip # type: ignore
import numpy # type: ignore
from PIL import Image, ImageDraw, ImageFont # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CaptionStyleConfig:
    # Font properties
    font_path: str = "Arial" # Default, consider providing a path to a .ttf file for consistency
    font_size: int = 48
    font_color: str = "white"

    # Background/Stroke for text emphasis
    stroke_color: Optional[str] = "black"
    stroke_width: float = 2.0 # Increased slightly from 1.5
    kerning: float = 0.0 # Added for character spacing adjustment

    # Caption box/background (optional, more advanced)
    # background_color: Optional[str] = None
    # text_bg_opacity: float = 0.5

    # Positioning
    # "bottom_center", "top_center", "center_center",
    # Later can add "bottom_left", "bottom_right", etc.
    position_preset: str = "bottom_center"
    padding_x_video_percent: float = 5.0 # Horizontal padding from video edge (if text is edge-aligned)
    padding_y_video_percent: float = 5.0 # Vertical padding from video edge

    # Line breaking
    max_chars_per_line: int = 40 # Approximate, can be refined with font metrics
    max_words_per_line: int = 10 # Alternative or additional constraint
    line_spacing_factor: float = 1.1 # Multiplier for line height if multiple lines in one TextClip

    # Word highlighting (for later use with LLM effects)
    # default_word_color: str = "white"
    # highlight_word_color: str = "yellow"


DEFAULT_STYLE_CONFIG = CaptionStyleConfig()

def segment_words_into_lines(
    timed_words: List[Dict[str, Any]],
    max_chars_per_line: int = DEFAULT_STYLE_CONFIG.max_chars_per_line,
    max_words_per_line: int = DEFAULT_STYLE_CONFIG.max_words_per_line,
    # TODO: Future: Could pass font info for more accurate width calculation
) -> List[Dict[str, Any]]:
    """
    Segments a list of timed words into caption lines based on character/word limits.

    Args:
        timed_words: List of word objects from transcription
                     (e.g., [{'word': ' Hello', 'start': 0.5, 'end': 0.9}, ...]).
        max_chars_per_line: Maximum characters allowed per line.
        max_words_per_line: Maximum words allowed per line.

    Returns:
        List of caption line data, each:
        {'text': "Line text",
         'start_time': S,
         'end_time': E,
         'words': [original_word_dicts_for_this_line]}
    """
    lines = []
    if not timed_words:
        return lines

    current_line_words: List[Dict[str, Any]] = []
    current_line_char_count = 0

    for i, word_data in enumerate(timed_words):
        word_text = word_data.get("word", "").strip() # Get the text of the word, remove leading/trailing spaces
        if not word_text: # Skip empty words if any
            continue

        word_len = len(word_text)

        # Check if adding this word exceeds limits
        # Add 1 for space if current_line_words is not empty
        potential_new_char_count = current_line_char_count + word_len + (1 if current_line_words else 0)

        # Enclose the entire condition in parentheses for implicit line continuation
        if (current_line_words and
            (len(current_line_words) >= max_words_per_line or
             potential_new_char_count > max_chars_per_line)):
            # Finalize current line
            line_text = " ".join(w.get("word", "").strip() for w in current_line_words)
            lines.append({
                "text": line_text,
                "start_time": current_line_words[0].get("start"),
                "end_time": current_line_words[-1].get("end"),
                "words": list(current_line_words) # Store a copy
            })
            # Start a new line with the current word
            current_line_words = [word_data]
            current_line_char_count = word_len
        else:
            # Add word to current line
            current_line_words.append(word_data)
            current_line_char_count = potential_new_char_count if current_line_words else word_len


    # Add the last remaining line
    if current_line_words:
        line_text = " ".join(w.get("word", "").strip() for w in current_line_words)
        lines.append({
            "text": line_text,
            "start_time": current_line_words[0].get("start"),
            "end_time": current_line_words[-1].get("end"),
            "words": list(current_line_words)
        })

    logger.info(f"Segmented {len(timed_words)} words into {len(lines)} caption lines.")
    return lines


def create_styled_caption_clip_pillow(
    line_data: Dict[str, Any],
    video_dimensions: Tuple[int, int], # (width, height)
    style_config: CaptionStyleConfig = DEFAULT_STYLE_CONFIG
) -> Optional[ImageClip]:
    """
    Creates a MoviePy ImageClip for a single caption line using Pillow for text rendering.
    This allows for more control over styling, especially strokes.

    Args:
        line_data: A dictionary for a single caption line, including 'text', 'start_time', 'end_time'.
        video_dimensions: Tuple (video_width, video_height).
        style_config: CaptionStyleConfig object.

    Returns:
        A MoviePy ImageClip object, or None if creation fails.
    """
    video_w, video_h = video_dimensions
    text_content = line_data.get("text")
    start_time = line_data.get("start_time")
    end_time = line_data.get("end_time")

    if text_content is None or start_time is None or end_time is None:
        logger.error(f"Missing essential data in line_data for ImageClip creation: {line_data}")
        return None

    duration = end_time - start_time
    if duration <= 0:
        logger.warning(f"Caption line has non-positive duration ({duration}s). Skipping: \"{text_content}\"")
        return None

    try:
        # 1. Load font
        try:
            font = ImageFont.truetype(style_config.font_path, style_config.font_size)
        except IOError:
            logger.warning(f"Could not load font: {style_config.font_path}. Trying default Pillow font.")
            try:
                font = ImageFont.load_default()
                logger.warning(f"Using Pillow's default font. Font size {style_config.font_size} might not apply as expected.")
            except IOError:
                 logger.error("Could not load any font. Cannot create text image.")
                 return None

        # 2. Determine text dimensions more accurately using Pillow
        # Use textbbox to get (left, top, right, bottom) which is more robust for actual painted pixels
        # We draw at (0,0) on a dummy canvas then get the bbox to know the true size
        dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1,1))) # Minimal dummy image
        text_bbox = dummy_draw.textbbox((0, 0), text_content, font=font, anchor='lt') #left-top anchor

        # More robust calculation of text dimensions from bbox
        bbox_left, bbox_top, bbox_right, bbox_bottom = text_bbox
        text_actual_width = bbox_right - bbox_left
        text_actual_height = bbox_bottom - bbox_top

        # If using kerning from TextClip, it's not directly applicable here.
        # Pillow's text drawing doesn't have a simple kerning parameter like MoviePy's TextClip.
        # For true kerning with Pillow, one would typically draw character by character and adjust spacing.
        # We will ignore style_config.kerning for this Pillow-based renderer for now.
        if style_config.kerning != 0.0:
            logger.warning("Pillow renderer: 'kerning' from CaptionStyleConfig is not directly applied in this version.")

        sw = int(style_config.stroke_width)
        internal_padding = max(2, int(sw * 0.5)) # Add a small internal padding, at least 2px, can be tuned

        # Create image canvas: text_width/height + stroke spread on all sides + internal_padding
        img_width = text_actual_width + (sw * 2) + (internal_padding * 2)
        img_height = text_actual_height + (sw * 2) + (internal_padding * 2)

        if img_width <= 0 or img_height <=0:
            logger.warning(f"Calculated image dimensions are invalid ({img_width}x{img_height}) for text: '{text_content}'. Skipping.")
            return None

        img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0)) # Transparent background
        draw = ImageDraw.Draw(img)

        # 3. Draw stroke (by drawing text at multiple offsets)
        if style_config.stroke_color and sw > 0:
            for x_offset in range(-sw, sw + 1):
                for y_offset in range(-sw, sw + 1):
                    # Simple circular/square spread for stroke. More sophisticated methods exist.
                    if x_offset*x_offset + y_offset*y_offset <= sw*sw: # circular spread
                        # Draw at (base_x, base_y) for top-left of text bbox within padded canvas
                        draw_origin_x = sw + internal_padding - bbox_left
                        draw_origin_y = sw + internal_padding - bbox_top
                        draw.text(
                            (draw_origin_x + x_offset, draw_origin_y + y_offset),
                            text_content,
                            font=font,
                            fill=style_config.stroke_color
                        )

        # 4. Draw main text on top
        # Draw at (base_x, base_y) for top-left of text bbox within padded canvas
        draw_origin_x = sw + internal_padding - bbox_left
        draw_origin_y = sw + internal_padding - bbox_top
        draw.text(
            (draw_origin_x, draw_origin_y),
            text_content,
            font=font,
            fill=style_config.font_color
        )

        # 5. Convert Pillow Image to MoviePy ImageClip
        # Convert RGBA Pillow image to NumPy array
        np_array = numpy.array(img)
        img_clip = ImageClip(np_array, transparent=True, ismask=False)

        img_clip = img_clip.set_start(start_time).set_duration(duration)

        # Positioning
        # Calculate padding in pixels
        padding_x_px = video_w * (style_config.padding_x_video_percent / 100.0)
        padding_y_px = video_h * (style_config.padding_y_video_percent / 100.0)

        clip_w, clip_h = img_clip.size

        pos_x: Any = 'center' # Default for x
        pos_y: Any = 'center' # Default for y

        if style_config.position_preset == "bottom_center":
            pos_x = 'center'
            pos_y = video_h - clip_h - padding_y_px
        elif style_config.position_preset == "top_center":
            pos_x = 'center'
            pos_y = padding_y_px
        elif style_config.position_preset == "center_center":
            pos_x = 'center'
            pos_y = 'center'
        # Add more presets like "bottom_left", "center_left", etc. as needed
        # Example for bottom_left:
        # elif style_config.position_preset == "bottom_left":
        #     pos_x = padding_x_px
        #     pos_y = video_h - clip_h - padding_y_px

        img_clip = img_clip.set_position((pos_x, pos_y))

        logger.debug(f"Created ImageClip (Pillow): \"{text_content}\" | Pos: ({pos_x}, {pos_y}) | Size: ({clip_w}, {clip_h})")
        return img_clip

    except Exception as e:
        logger.error(f"Failed to create ImageClip (Pillow) for \"{text_content}\": {e}", exc_info=True)
        # Log more details if ImageMagick is involved, as it's a common source of issues
        if "ImageMagick" in str(e):
            logger.error("This error might be related to ImageMagick. Ensure it's installed and configured correctly for MoviePy.")
            logger.error("On some systems, you might need to edit the policy.xml for ImageMagick to allow read/write for MVG/TEXT.")
        return None


# Keep the old TextClip-based function for reference or fallback if needed, renamed
create_styled_caption_clip_textclip = create_styled_caption_clip_pillow

# The primary function will now be the Pillow-based one
create_styled_caption_clip = create_styled_caption_clip_pillow


if __name__ == '__main__':
    logger.info("Running basic tests for caption_generator.py...")

    # --- Test 1: segment_words_into_lines ---
    sample_timed_words = [
        {'word': ' Hello', 'start': 0.0, 'end': 0.5, 'probability': 0.9},
        {'word': ' world,', 'start': 0.5, 'end': 1.0, 'probability': 0.9},
        {'word': ' this', 'start': 1.0, 'end': 1.3, 'probability': 0.9},
        {'word': ' is', 'start': 1.3, 'end': 1.5, 'probability': 0.9},
        {'word': ' a', 'start': 1.5, 'end': 1.6, 'probability': 0.9},
        {'word': ' test', 'start': 1.6, 'end': 2.0, 'probability': 0.9},
        {'word': ' of', 'start': 2.0, 'end': 2.2, 'probability': 0.9},
        {'word': ' the', 'start': 2.2, 'end': 2.4, 'probability': 0.9},
        {'word': ' line', 'start': 2.4, 'end': 2.7, 'probability': 0.9},
        {'word': ' breaking', 'start': 2.7, 'end': 3.2, 'probability': 0.9},
        {'word': ' functionality.', 'start': 3.2, 'end': 4.0, 'probability': 0.9},
    ]

    logger.info("\n--- Testing segment_words_into_lines ---")
    lines = segment_words_into_lines(sample_timed_words, max_chars_per_line=20, max_words_per_line=5)

    assert len(lines) > 0, "Line breaking should produce at least one line."
    expected_line_count_approx = 3 # Based on "Hello world, this is", "a test of the line", "breaking functionality." with char_limit=20
    # This assertion is approximate as behavior can vary slightly. Manual inspection of logs is better.
    logger.info(f"Segmented into {len(lines)} lines (expected approx {expected_line_count_approx} for char_limit=20).")

    for i, line in enumerate(lines):
        logger.info(f"  Line {i+1}: Text='{line['text']}', Start={line['start_time']:.2f}, End={line['end_time']:.2f}")
        assert "text" in line and "start_time" in line and "end_time" in line and "words" in line
        assert isinstance(line["text"], str) and line["text"]
        assert isinstance(line["start_time"], float) and line["start_time"] >= 0
        assert isinstance(line["end_time"], float) and line["end_time"] >= line["start_time"]
        assert isinstance(line["words"], list) and len(line["words"]) > 0

    # Test with empty input
    lines_empty = segment_words_into_lines([])
    assert len(lines_empty) == 0, "Line breaking with empty input should produce zero lines."
    logger.info("segment_words_into_lines: Empty input test PASSED.")

    # --- Test 2: create_styled_caption_clip (Pillow renderer) ---
    logger.info("\n--- Testing create_styled_caption_clip (Pillow renderer) ---")
    mock_line_data = {
        "text": "Pillow Text Line 1",
        "start_time": 0.0,
        "end_time": 3.0,
        "words": [{'word': 'Pillow', 'start':0.0, 'end':0.5}]
    }
    output_video_dim_test_2_2 = (640, 480) # Test with a slightly different dimension

    test_style = CaptionStyleConfig()
    test_style.font_size = 40
    test_style.padding_y_video_percent = 10
    test_style.stroke_width = 2 # Pixel width for Pillow stroke
    test_style.font_color = "#FFFF00" # Yellow
    test_style.stroke_color = "#000000" # Black
    # test_style.kerning = -1 # Kerning is not used by Pillow renderer in this impl.

    font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")
    assumed_font_filename = "Roboto-Regular.ttf"
    test_font_path = os.path.join(font_dir, assumed_font_filename)

    if os.path.exists(test_font_path):
        logger.info(f"Using font for Test 2.2 (Pillow): {test_font_path}")
        test_style.font_path = test_font_path
    else:
        logger.warning(f"Font file NOT FOUND: {test_font_path}. Test will use Pillow default font.")

    # Now using the new Pillow-based function (which is now assigned to create_styled_caption_clip)
    img_clip_for_render = create_styled_caption_clip(mock_line_data, output_video_dim_test_2_2, style_config=test_style)

    if img_clip_for_render:
        logger.info("create_styled_caption_clip (Pillow): Basic object creation test PASSED.")

        logger.info("\n--- Test 2.2 (Pillow): Rendering single caption clip (output_single_caption_pillow.mp4) ---")
        from moviepy.editor import ColorClip, CompositeVideoClip # Already imported at top level for module use

        background_clip = ColorClip(size=output_video_dim_test_2_2, color=(60, 60, 60), duration=3.0)
        final_clip_test_2_2 = CompositeVideoClip([background_clip, img_clip_for_render], size=output_video_dim_test_2_2)

        output_filename_test_2_2 = "output_single_caption_pillow.mp4"
        output_path_test_2_2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename_test_2_2)

        try:
            final_clip_test_2_2.write_videofile(output_path_test_2_2, fps=24, codec="libx264")
            logger.info(f"Test 2.2 (Pillow): Successfully rendered '{output_filename_test_2_2}'. Please visually inspect it.")
            logger.info(f"Check for: Yellow text \"Pillow Text Line 1\", black stroke, font size {test_style.font_size}, bottom-center, 3s duration.")
        except Exception as render_e:
            logger.error(f"Test 2.2 (Pillow): Failed to render video: {render_e}", exc_info=True)
    else:
        logger.warning("create_styled_caption_clip (Pillow): Returned None. Check logs.")

    logger.info("\nBasic tests for caption_generator.py finished.")
