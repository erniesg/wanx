from moviepy.editor import TextClip, ImageClip, VideoClip, CompositeVideoClip, ColorClip
from PIL import Image, ImageFilter, ImageFont, ImageDraw
import numpy
import tempfile
import logging
import os

logger = logging.getLogger(__name__)
text_cache = {} # For PIL-based text measurement if used

# Default font path (can be overridden)
DEFAULT_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "fonts")
DEFAULT_FONT_NAME = "Roboto-Bold.ttf" # Example, ensure this exists or provide a valid default

def get_default_font_path():
    path = os.path.join(DEFAULT_FONT_DIR, DEFAULT_FONT_NAME)
    if not os.path.exists(path):
        logger.warning(f"Default font {path} not found. MoviePy might use a system default.")
        return "Arial" # A common fallback
    return path

class Character:
    def __init__(self, text, color=None):
        self.text = text
        self.color = color

    def set_color(self, color):
        self.color = color

class Word:
    def __init__(self, word, color=None): # word is a string
        self.word = word
        self.color = color
        self.characters = []
        for char_text in self.word:
            self.characters.append(Character(char_text, color))

    def set_color(self, color):
        self.color = color
        for char in self.characters:
            char.set_color(color)

class TextClipEx(TextClip): # Not strictly used by create_text_ex but part of captacity's drawer
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.txt_color = kwargs.get('color', 'white')
        self.stroke_color = kwargs.get('stroke_color', None)
        self.stroke_width = kwargs.get('stroke_width', 0)

    def get_frame(self, t):
        # This might need to be reimplemented if TextClipEx is directly used
        # and complex frame manipulations are needed.
        # For now, rely on the base TextClip's get_frame.
        # If issues arise with TextClipEx, the captacity source has specific PIL drawing here.
        # However, our create_text already handles compositing.

        # Create PIL image
        pil_img = self.make_pil_image(t)

        # Convert to numpy array
        frame = numpy.array(pil_img)

        # Add alpha channel if missing
        if frame.shape[2] == 3:
            alpha = numpy.ones((frame.shape[0], frame.shape[1], 1), dtype=frame.dtype) * 255
            frame = numpy.concatenate((frame, alpha), axis=2)

        return frame

    def make_pil_image(self, t):
        txt = self.txt.decode('utf-8') if isinstance(self.txt, bytes) else self.txt

        # Use PIL to draw with stroke
        font_pil = ImageFont.truetype(self.font, self.fontsize)

        # Get text size using PIL
        bbox = font_pil.getbbox(txt)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Adjust canvas size for stroke
        canvas_w = text_w + 2 * self.stroke_width
        canvas_h = text_h + 2 * self.stroke_width

        img = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw stroke
        if self.stroke_color and self.stroke_width > 0:
            draw.text((self.stroke_width, self.stroke_width), txt, font=font_pil, fill=self.stroke_color, stroke_width=self.stroke_width, stroke_fill=self.stroke_color)

        # Draw text
        draw.text((self.stroke_width, self.stroke_width), txt, font=font_pil, fill=self.txt_color)

        return img


# Cache for PIL font loading
pil_font_cache = {}

def get_pil_font(font_path, font_size):
    cache_key = (font_path, font_size)
    if cache_key in pil_font_cache:
        return pil_font_cache[cache_key]
    try:
        font = ImageFont.truetype(font_path, font_size)
        pil_font_cache[cache_key] = font
        return font
    except Exception as e:
        logger.error(f"Failed to load font {font_path} with PIL: {e}. Trying Arial.")
        try:
            font = ImageFont.truetype("Arial.ttf", font_size) # Common system font
            pil_font_cache[("Arial.ttf", font_size)] = font # Cache Arial as well
            return font
        except Exception as e_arial:
            logger.error(f"Failed to load Arial with PIL: {e_arial}. Fallback to MoviePy default font behavior.")
            raise # Re-raise if Arial also fails, MoviePy will handle its own default

def get_text_size_pil(text: str, font: str, fontsize: int, stroke_width: int = 0) -> tuple[int, int]:
    """Measures text using PIL for potentially more accurate width, including stroke."""
    try:
        pil_font = get_pil_font(font, fontsize)

        # Pillow's getbbox provides (x1, y1, x2, y2) of the bounding box
        # For multiline text, this becomes more complex. Assuming single line for basic measurement.
        # If text is multiline, getsize_multiline or iterating lines might be needed.
        lines = text.split('\n')
        max_width = 0
        total_height = 0

        for i, line in enumerate(lines):
            if not line.strip(): # Handle empty lines if they contribute to height
                # A common way is to use the height of a space or a capital letter
                bbox_space = pil_font.getbbox(" ")
                line_height_pil = bbox_space[3] - bbox_space[1]
            else:
                bbox = pil_font.getbbox(line)
                line_width_pil = bbox[2] - bbox[0]
                line_height_pil = bbox[3] - bbox[1] # Height of the text itself

            # Add stroke to width for more accurate fitting.
            # This is a simplified addition; true bounding box of stroked text can be complex.
            actual_line_width = line_width_pil + (stroke_width * 2) if stroke_width > 0 else line_width_pil

            if actual_line_width > max_width:
                max_width = actual_line_width

            # Estimate interline spacing based on font size (can be improved)
            # For single line text, this doesn't matter as much.
            # For multi-line, this would be font_metrics.getsize(line)[1] or similar from fonttools if available
            # A simple heuristic:
            spacing_factor = 0.2
            total_height += line_height_pil
            if i < len(lines) -1 : # Add spacing if not the last line
                 total_height += int(line_height_pil * spacing_factor)


        return int(max_width), int(total_height)

    except Exception as e:
        logger.warning(f"PIL text measurement failed for '{text}' with font '{font}': {e}. Falling back to MoviePy's TextClip.size.")
        # Fallback: Use MoviePy's own text size calculation (less accurate for width with stroke)
        try:
            clip = TextClip(text, font=font, fontsize=fontsize, stroke_width=stroke_width, stroke_color="black", color="white")
            size = clip.size
            clip.close()
            return size[0], size[1]
        except Exception as e_mp:
            logger.error(f"MoviePy TextClip size fallback also failed: {e_mp}")
            return 10, 10 # Absolute fallback

def get_text_size_ex(text: str, font: str, fontsize: int, stroke_width: int = 0) -> tuple[int, int]:
    """Wrapper for text size measurement, currently using PIL-based method."""
    # Using font path directly; MoviePy handles font name resolution if not a path.
    # Ensure font is a valid path or a name MoviePy/PIL can find.
    font_to_use = font
    if not os.path.exists(font) and not font.lower().endswith(('.ttf', '.otf')) :
        # If it's not a path and not obviously a font file, try to make it a path.
        # This logic might need to be more robust, or rely on get_default_font_path more.
        # For now, assume 'font' is either a resolvable name or a direct path.
        pass
    elif not os.path.exists(font) and font.lower().endswith(('.ttf', '.otf')):
        # It looks like a font file but doesn't exist at this path, try default dir
        potential_path = os.path.join(DEFAULT_FONT_DIR, os.path.basename(font))
        if os.path.exists(potential_path):
            font_to_use = potential_path
        else: # Fallback if not in default dir either
            font_to_use = get_default_font_path() if font.lower() == DEFAULT_FONT_NAME.lower() else "Arial"


    return get_text_size_pil(text, font=font_to_use, fontsize=fontsize, stroke_width=stroke_width)


def create_text(txt: str, fontsize: int, color: str, font: str, bg_color='transparent',
                  stroke_color=None, stroke_width=1, kerning=0) -> CompositeVideoClip:
    """
    Creates a single TextClip, potentially wrapped for stroke/padding.
    Uses MoviePy's TextClip directly.
    """
    # Ensure font is valid for MoviePy
    font_to_use = font
    if not os.path.exists(font) and not font.lower().endswith(('.ttf', '.otf')) :
        pass # Assume it's a system font name like "Arial"
    elif not os.path.exists(font) and font.lower().endswith(('.ttf', '.otf')):
        potential_path = os.path.join(DEFAULT_FONT_DIR, os.path.basename(font))
        if os.path.exists(potential_path): font_to_use = potential_path
        else: font_to_use = get_default_font_path() if font.lower() == DEFAULT_FONT_NAME.lower() else "Arial"

    base_clip_args = {
        "txt": txt,
        "font": font_to_use,
        "fontsize": fontsize,
        "color": color,
        "bg_color": bg_color, # Usually transparent
        "kerning": kerning,
        # MoviePy TextClip handles method='label' or 'caption' for basic rendering
    }

    if stroke_color and stroke_width > 0:
        base_clip_args["stroke_color"] = stroke_color
        base_clip_args["stroke_width"] = stroke_width
        # For MoviePy's built-in stroke, 'label' method is often better.
        # If using PIL TextClipEx, that would handle its own stroking.
        base_clip_args["method"] = 'label' # or 'caption', 'label' usually better with stroke

    try:
        text_clip = TextClip(**base_clip_args)
    except Exception as e:
        logger.error(f"Failed to create TextClip for '{txt}' with font '{font_to_use}': {e}. Trying Arial.")
        base_clip_args["font"] = "Arial" # Fallback font
        text_clip = TextClip(**base_clip_args)

    padding = stroke_width * 2 if stroke_color and stroke_width > 0 else 2
    final_w = text_clip.w + padding
    final_h = text_clip.h + padding

    # Use RGBA for transparency: (R,G,B,Alpha)
    # Alpha=0 means fully transparent. No need for ismask=True or set_opacity(0) here.
    wrapper_clip = ColorClip(size=(final_w, final_h), color=(0,0,0,0), duration=1.0)

    positioned_text_clip = text_clip.set_position(('center', 'center'))
    final_clip = CompositeVideoClip([wrapper_clip, positioned_text_clip], size=(final_w, final_h))
    return final_clip


def create_text_chars(
    text: list[Word] | list[Character], # List of Word or Character objects
    fontsize: int,
    color: str, # Default color, can be overridden by Word/Character
    font: str,
    bg_color='transparent',
    blur_radius: int = 0, # Not directly used by create_text, but for API consistency
    opacity=1,           # Not directly used by create_text, but for API consistency
    stroke_color=None,
    stroke_width=1,
    add_space_between_words=True
) -> list[CompositeVideoClip]:

    char_clips = []
    is_first_char_overall = True

    for item_idx, item in enumerate(text): # Item can be Word or Character
        if isinstance(item, Word):
            word_obj = item
            if add_space_between_words and item_idx > 0 and not is_first_char_overall:
                # Add a space clip if it's not the first word
                space_char_clip = create_text(" ", fontsize, color, font, bg_color, stroke_color, stroke_width)
                char_clips.append(space_char_clip)

            for char_idx, char_obj in enumerate(word_obj.characters):
                char_text = char_obj.text
                char_color = char_obj.color if char_obj.color else color
                char_clip = create_text(char_text, fontsize, char_color, font, bg_color, stroke_color, stroke_width)
                char_clips.append(char_clip)
                is_first_char_overall = False

        elif isinstance(item, Character): # If input is already list of Characters
            char_obj = item
            char_text = char_obj.text
            char_color = char_obj.color if char_obj.color else color
            char_clip = create_text(char_text, fontsize, char_color, font, bg_color, stroke_color, stroke_width)
            char_clips.append(char_clip)
            is_first_char_overall = False
        else:
            logger.warning(f"Unsupported item type in create_text_chars: {type(item)}. Skipping.")

    return char_clips


def create_composite_text(
    char_clips: list[CompositeVideoClip],
    kerning: float = 0
) -> CompositeVideoClip:
    if not char_clips:
        return ColorClip(size=(1,1), color=(0,0,0,0), duration=0.001) # RGBA transparent

    total_width = 0
    max_height = 0
    for clip in char_clips:
        total_width += clip.w
        if kerning and total_width > clip.w:
            total_width += kerning
        if clip.h > max_height:
            max_height = clip.h

    if total_width <=0 : total_width = 1
    if max_height <=0 : max_height = 1

    # Use RGBA for transparency
    background = ColorClip(size=(int(total_width), int(max_height)), color=(0,0,0,0), duration=1)

    clips_to_composite = [background]
    current_x = 0
    for i, clip in enumerate(char_clips):
        y_pos = max_height - clip.h
        positioned_clip = clip.set_position((current_x, y_pos))
        clips_to_composite.append(positioned_clip)
        current_x += clip.w
        if i < len(char_clips) - 1:
            current_x += kerning

    return CompositeVideoClip(clips_to_composite, size=(int(total_width), int(max_height)))


def blur_text_clip(text_clip: VideoClip, blur_radius: int) -> VideoClip:
    if blur_radius <= 0:
        return text_clip
    def blur_effect(gf, t):
        frame = gf(t)
        pil_image = Image.fromarray(frame)
        blurred_image = pil_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        return numpy.array(blurred_image)
    return text_clip.fl(blur_effect)


def str_to_charlist(text: str) -> list[Character]:
    return [Character(char) for char in text]

def create_text_ex(
    text: list[Word] | list[Character] | str,
    fontsize: int,
    color: str,
    font: str,
    bg_color='transparent', # Background for individual char clips from create_text
    blur_radius: int = 0,   # For final composite clip
    opacity = 1,            # For final composite clip
    stroke_color = None,
    stroke_width = 1,
    kerning = 0, # Visual spacing between character clips
) -> CompositeVideoClip:

    if isinstance(text, str):
        # If raw string, convert to list of Word objects for consistent processing
        # This assumes space-separated words. More complex tokenization might be needed for other cases.
        word_strings = text.split(' ')
        list_of_words = [Word(word_str.strip(), color=color) for word_str in word_strings if word_str.strip()]
        # Filter out empty words that might result from multiple spaces
        text = list_of_words

    # Create individual character clips.
    # text is now List[Word] or List[Character]
    char_clips_list = create_text_chars(
        text,
        fontsize,
        color, # Default color, words/chars can override
        font,
        bg_color,
        0, # blur_radius for create_text_chars not used
        1, # opacity for create_text_chars not used
        stroke_color,
        stroke_width,
        add_space_between_words=True # Important for when input is List[Word]
    )

    if not char_clips_list:
        # Handle empty input case: return a tiny, transparent, very short clip
        return ColorClip(size=(1,1), color=(0,0,0,0), ismask=True, duration=0.01).set_opacity(0)

    # Composite these character clips into a single line
    line_clip = create_composite_text(char_clips_list, kerning=kerning)

    # Apply overall opacity and blur if specified
    if opacity < 1:
        line_clip = line_clip.set_opacity(opacity)
    if blur_radius > 0:
        line_clip = blur_text_clip(line_clip, blur_radius)

    return line_clip

# Example usage or test block (optional, can be removed or kept for direct testing)
if __name__ == '__main__':
    from moviepy.editor import ColorClip, CompositeVideoClip, concatenate_videoclips

    logger.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG) # Ensure logs are visible

    font_path_test = get_default_font_path()
    logger.info(f"Using font for test: {font_path_test}")

    # Test 1: Simple string
    clip1 = create_text_ex(
        text="Hello",
        fontsize=70,
        color="yellow",
        font=font_path_test,
        stroke_color="black",
        stroke_width=3,
        kerning=2
    )
    logger.info(f"Clip 1 size: {clip1.size}")


    # Test 2: List of Word objects
    words_list = [Word("Hello", color="cyan"), Word("World", color="magenta")]
    clip2 = create_text_ex(
        text=words_list,
        fontsize=70,
        color="white", # Default, overridden by Word objects
        font=font_path_test,
        stroke_color="blue",
        stroke_width=2,
        kerning=-2
    )
    logger.info(f"Clip 2 size: {clip2.size}")

    # Test 3: Empty Text
    clip_empty = create_text_ex(
        text="",
        fontsize=70,
        color="white",
        font=font_path_test
    )
    logger.info(f"Clip Empty size: {clip_empty.size}")


    # Test 4: Text with blur and opacity
    clip_effects = create_text_ex(
        text="Effects!",
        fontsize=90,
        color="lightgreen",
        font=font_path_test,
        stroke_color="darkgreen",
        stroke_width=4,
        blur_radius=2,
        opacity=0.8
    )
    logger.info(f"Clip Effects size: {clip_effects.size}")

    # To actually see them, we need to set duration and composite onto a background
    bg_color_clip = ColorClip(size=(800, 600), color=(50,50,50), duration=5)

    if clip1 and clip1.size[0] > 1 and clip1.size[1] > 1 : clip1 = clip1.set_duration(2).set_start(0).set_position(("center", 50))
    if clip2 and clip2.size[0] > 1 and clip2.size[1] > 1 : clip2 = clip2.set_duration(2).set_start(0).set_position(("center", 150))
    if clip_empty and clip_empty.size[0] > 1 and clip_empty.size[1] > 1 : clip_empty = clip_empty.set_duration(1).set_start(0).set_position(("center", 250)) # Will be tiny
    if clip_effects and clip_effects.size[0] > 1 and clip_effects.size[1] > 1 : clip_effects = clip_effects.set_duration(2).set_start(2.5).set_position(("center", "center"))

    final_video_clips = [bg_color_clip]
    if clip1 and clip1.duration: final_video_clips.append(clip1)
    if clip2 and clip2.duration: final_video_clips.append(clip2)
    if clip_empty and clip_empty.duration : final_video_clips.append(clip_empty)
    if clip_effects and clip_effects.duration: final_video_clips.append(clip_effects)


    if len(final_video_clips) > 1:
        output_path_test = "text_drawer_test_output.mp4"
        final_comp = CompositeVideoClip(final_video_clips, size=(800,600))
        try:
            logger.info(f"Attempting to render test video to: {output_path_test}")
            final_comp.write_videofile(output_path_test, fps=24, codec="libx264")
            logger.info(f"Test video rendered: {output_path_test}")
        except Exception as e:
            logger.error(f"Could not render test video: {e}", exc_info=True)
    else:
        logger.info("No valid clips generated to render for test.")
    logger.info("text_drawer.py test finished.")
