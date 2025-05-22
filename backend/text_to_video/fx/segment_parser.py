from moviepy.editor import VideoFileClip, CompositeVideoClip
import subprocess
import tempfile
import time
import os
from typing import Callable, List, Dict, Any
import logging

from . import segment_parser
from . import transcriber
from .text_drawer import (
    get_text_size_ex,
    create_text_ex,
    blur_text_clip,
    Word,
)

shadow_cache = {}
lines_cache = {}

logger = logging.getLogger(__name__)

def fits_frame(line_count, font, font_size, stroke_width, frame_width):
    def fit_function(text):
        lines = calculate_lines(
            text,
            font,
            font_size,
            stroke_width,
            frame_width
        )
        return len(lines["lines"]) <= line_count
    return fit_function

def calculate_lines(text, font, font_size, stroke_width, frame_width):
    global lines_cache

    arg_hash = hash((text, font, font_size, stroke_width, frame_width))

    if arg_hash in lines_cache:
        return lines_cache[arg_hash]

    lines = []

    line_to_draw = None
    line = ""
    words = text.split()
    word_index = 0
    total_height = 0
    while word_index < len(words):
        word = words[word_index]
        line += word + " "
        text_size = get_text_size_ex(line.strip(), font, font_size, stroke_width)
        text_width = text_size[0]
        line_height = text_size[1]

        if text_width < frame_width:
            line_to_draw = {
                "text": line.strip(),
                "height": line_height,
            }
            word_index += 1
        else:
            if not line_to_draw:
                print(f"NOTICE: Word '{line.strip()}' is too long for the frame!")
                line_to_draw = {
                    "text": line.strip(),
                    "height": line_height,
                }
                word_index += 1

            lines.append(line_to_draw)
            total_height += line_height
            line_to_draw = None
            line = ""

    if line_to_draw:
        lines.append(line_to_draw)
        total_height += line_height

    data = {
        "lines": lines,
        "height": total_height,
    }

    lines_cache[arg_hash] = data

    return data

def ffmpeg(command):
    return subprocess.run(command, capture_output=True)

def create_shadow(text: str, font_size: int, font: str, blur_radius: float, opacity: float=1.0):
    global shadow_cache

    arg_hash = hash((text, font_size, font, blur_radius, opacity))

    if arg_hash in shadow_cache:
        return shadow_cache[arg_hash].copy()

    shadow = create_text_ex(text, font_size, "black", font, opacity=opacity)
    shadow = blur_text_clip(shadow, int(font_size*blur_radius))

    shadow_cache[arg_hash] = shadow.copy()

    return shadow

def get_font_path(font):
    if os.path.exists(font):
        return font

    dirname = os.path.dirname(__file__)
    font = os.path.join(dirname, "assets", "fonts", font)

    if not os.path.exists(font):
        raise FileNotFoundError(f"Font '{font}' not found")

    return font

def detect_local_whisper(print_info):
    try:
        import whisper
        use_local_whisper = True
        if print_info:
            print("Using local whisper model...")
    except ImportError:
        use_local_whisper = False
        if print_info:
            print("Using OpenAI Whisper API...")

    return use_local_whisper

def add_captions(
    video_file,
    output_file = "with_transcript.mp4",

    font = "Bangers-Regular.ttf",
    font_size = 130,
    font_color = "yellow",

    stroke_width = 3,
    stroke_color = "black",

    highlight_current_word = True,
    word_highlight_color = "red",

    line_count = 2,
    fit_function = None,

    padding = 50,
    position = ("center", "center"), # TODO: Implement this

    shadow_strength = 1.0,
    shadow_blur = 0.1,

    print_info = False,

    initial_prompt = None,
    segments = None,

    use_local_whisper = "auto",
):
    _start_time = time.time()

    font = get_font_path(font)

    if print_info:
        print("Extracting audio...")

    temp_audio_file = tempfile.NamedTemporaryFile(suffix=".wav").name
    ffmpeg([
        'ffmpeg',
        '-y',
        '-i', video_file,
        temp_audio_file
    ])

    if segments is None:
        if print_info:
            print("Transcribing audio...")

        if use_local_whisper == "auto":
            use_local_whisper = detect_local_whisper(print_info)

        if use_local_whisper:
            segments = transcriber.transcribe_locally(temp_audio_file, initial_prompt)
        else:
            segments = transcriber.transcribe_with_api(temp_audio_file, initial_prompt)

    if print_info:
        print("Generating video elements...")

    # Open the video file
    video = VideoFileClip(video_file)
    text_bbox_width = video.w-padding*2
    clips = [video]

    captions = segment_parser.parse(
        segments=segments,
        fit_function=fit_function if fit_function else fits_frame(
            line_count,
            font,
            font_size,
            stroke_width,
            text_bbox_width,
        ),
    )

    for caption in captions:
        captions_to_draw = []
        if highlight_current_word:
            for i, word in enumerate(caption["words"]):
                if i+1 < len(caption["words"]):
                    end = caption["words"][i+1]["start"]
                else:
                    end = word["end"]

                captions_to_draw.append({
                    "text": caption["text"],
                    "start": word["start"],
                    "end": end,
                })
        else:
            captions_to_draw.append(caption)

        for current_index, caption in enumerate(captions_to_draw):
            line_data = calculate_lines(caption["text"], font, font_size, stroke_width, text_bbox_width)

            text_y_offset = video.h // 2 - line_data["height"] // 2
            index = 0
            for line in line_data["lines"]:
                pos = ("center", text_y_offset)

                words = line["text"].split()
                word_list = []
                for w in words:
                    word_obj = Word(w)
                    if highlight_current_word and index == current_index:
                        word_obj.set_color(word_highlight_color)
                    index += 1
                    word_list.append(word_obj)

                # Create shadow
                shadow_left = shadow_strength
                while shadow_left >= 1:
                    shadow_left -= 1
                    shadow = create_shadow(line["text"], font_size, font, shadow_blur, opacity=1)
                    shadow = shadow.set_start(caption["start"])
                    shadow = shadow.set_duration(caption["end"] - caption["start"])
                    shadow = shadow.set_position(pos)
                    clips.append(shadow)

                if shadow_left > 0:
                    shadow = create_shadow(line["text"], font_size, font, shadow_blur, opacity=shadow_left)
                    shadow = shadow.set_start(caption["start"])
                    shadow = shadow.set_duration(caption["end"] - caption["start"])
                    shadow = shadow.set_position(pos)
                    clips.append(shadow)

                # Create text
                text = create_text_ex(word_list, font_size, font_color, font, stroke_color=stroke_color, stroke_width=stroke_width)
                text = text.set_start(caption["start"])
                text = text.set_duration(caption["end"] - caption["start"])
                text = text.set_position(pos)
                clips.append(text)

                text_y_offset += line["height"]

    end_time = time.time()
    generation_time = end_time - _start_time

    if print_info:
        print(f"Generated in {generation_time//60:02.0f}:{generation_time%60:02.0f} ({len(clips)} clips)")

    if print_info:
        print("Rendering video...")

    video_with_text = CompositeVideoClip(clips)

    video_with_text.write_videofile(
        filename=output_file,
        codec="libx264",
        fps=video.fps,
        logger="bar" if print_info else None,
    )

    end_time = time.time()
    total_time = end_time - _start_time
    render_time = total_time - generation_time

    if print_info:
        print(f"Generated in {generation_time//60:02.0f}:{generation_time%60:02.0f}")
        print(f"Rendered in {render_time//60:02.0f}:{render_time%60:02.0f}")
        print(f"Done in {total_time//60:02.0f}:{total_time%60:02.0f}")

def has_partial_sentence(text: str) -> bool:
    words = text.split()
    if len(words) >= 2:
        prev_word = words[-2].strip()
        if prev_word.endswith("."):
            return True
    return False

def parse(
    segments: List[Dict[str, Any]],
    fit_function: Callable[[str], bool],
    allow_partial_sentences: bool = False,
) -> List[Dict[str, Any]]:
    captions: List[Dict[str, Any]] = []
    current_caption: Dict[str, Any] = {
        "start": None,
        "end": 0.0,
        "words": [],
        "text": "",
    }

    # Optional: Logic to merge words not separated by spaces if needed (from captacity)
    # Depends on the exact output format of your transcription step.
    # Whisper output usually has leading spaces for subsequent words.
    # for s_idx, segment_data in enumerate(segments):
    #     words_in_segment = segment_data.get("words", [])
    #     merged_words = []
    #     w_idx = 0
    #     while w_idx < len(words_in_segment):
    #         current_word_obj = words_in_segment[w_idx]
    #         # If next word exists and starts without a space (and current isn't space)
    #         if (w_idx + 1 < len(words_in_segment) and
    #             not words_in_segment[w_idx+1]["word"].startswith(' ') and
    #             current_word_obj["word"].strip() != ""):
    #             current_word_obj["word"] += words_in_segment[w_idx+1]["word"]
    #             current_word_obj["end"] = words_in_segment[w_idx+1]["end"]
    #             w_idx += 1 # Skip next word as it has been merged
    #         merged_words.append(current_word_obj)
    #         w_idx += 1
    #     segments[s_idx]["words"] = merged_words

    if not segments or not (segments[0].get("words") if segments else False):
        logger.debug("Segment parser received empty segments or segments with no words.")
        # If current_caption has text (e.g. from a previous loop if structure changes), append it.
        if current_caption["text"].strip():
            captions.append(current_caption)
        # Return an empty list if no words, or list containing the (empty) current_caption if structure implies.
        # For safety, returning empty list is cleaner if no words were processed.
        return [] if not current_caption["text"].strip() else [current_caption]

    for segment in segments:
        words_in_segment = segment.get("words", [])
        if not words_in_segment:
            continue

        for word_data in words_in_segment:
            word_text = word_data.get("word", "")
            word_start = word_data.get("start")
            word_end = word_data.get("end")

            if word_start is None or word_end is None:
                logger.warning(f"Word data missing start/end time: {word_data}. Skipping.")
                continue

            word_start = float(word_start)
            word_end = float(word_end)

            if current_caption["start"] is None:
                current_caption["start"] = word_start

            # Add the current word to the line text.
            # If current_caption["text"] is empty and word_text starts with a space, strip it for the first word.
            # Otherwise, the leading space of subsequent words is desired.
            prospective_text = ""
            if not current_caption["text"]: # First word of this caption line
                prospective_text = current_caption["text"] + word_text.lstrip()
            else: # Subsequent words
                # Ensure word_text has a leading space if it's not already there and previous text isn't empty
                if not word_text.startswith(' ') and current_caption["text"]:
                    prospective_text = current_caption["text"] + " " + word_text
                else:
                    prospective_text = current_caption["text"] + word_text

            # Check if the new line fits
            line_is_too_long = False
            if prospective_text.strip(): # Only call fit_function if there's actual text
                if not fit_function(prospective_text.strip()): # fit_function expects stripped text
                    line_is_too_long = True

            caption_can_break_here = allow_partial_sentences or not has_partial_sentence(prospective_text)

            if not line_is_too_long and caption_can_break_here:
                current_caption["words"].append(word_data)
                current_caption["end"] = word_end
                current_caption["text"] = prospective_text
            else:
                # Word doesn't fit or shouldn't break here. Finalize previous caption.
                if current_caption["text"].strip():
                    captions.append(current_caption)

                # Start new caption with current word.
                # First word of a new line should not have a leading space if word_text had one.
                current_caption = {
                    "start": word_start,
                    "end": word_end,
                    "words": [word_data],
                    "text": word_text.lstrip()
                }

    # Append the last caption being built
    if current_caption["text"].strip():
        captions.append(current_caption)

    return [c for c in captions if c["text"].strip()] # Ensure no empty captions are returned
