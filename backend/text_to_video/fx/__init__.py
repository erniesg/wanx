from moviepy.editor import VideoFileClip, CompositeVideoClip
import subprocess
import tempfile
import time
import os

from . import segment_parser
from . import transcriber
from .text_drawer import (
    get_text_size_ex,
    create_text_ex,
    blur_text_clip,
    Word,
)

# Make add_captions directly importable
__all__ = ["add_captions"]

shadow_cache = {}
lines_cache = {}

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

    # Adjust path to be relative to the project structure for assets
    # Assumes assets/fonts is at backend/assets/fonts
    # __file__ is backend/text_to_video/fx/__init__.py
    # We need to go up three levels to the workspace root, then to backend/assets/fonts
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    font_path_try = os.path.join(base_path, "backend", "assets", "fonts", os.path.basename(font))

    if not os.path.exists(font_path_try):
        # Fallback to original logic if not found in the new location, just in case.
        dirname = os.path.dirname(__file__)
        font_path_try = os.path.join(dirname, "assets", "fonts", os.path.basename(font))
        if not os.path.exists(font_path_try):
            raise FileNotFoundError(f"Font '{os.path.basename(font)}' not found at expected project path or local fx/assets/fonts")

    return font_path_try

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

    # Synchronize audio duration with video duration if audio exists
    if video.audio is not None:
        video.audio = video.audio.set_duration(video.duration)

    text_bbox_width = video.w-padding*2
    clips = [video]

    if print_info:
        print(f"Input video to add_captions: duration={video.duration}s, fps={video.fps}, size=({video.w}x{video.h})")
        print(f"  Total frames expected for input video: {int(video.duration * video.fps) if video.duration and video.fps else 'N/A'}")

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
            if position == "bottom-center":
                text_y_offset = video.h - line_data["height"] - padding

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

    # Ensure the composite video has the same duration as the input video
    video_with_text = CompositeVideoClip(clips, size=video.size).set_duration(video.duration)

    video_with_text.write_videofile(
        filename=output_file,
        codec="libx264",
        audio_codec="aac",
        fps=video.fps,
        logger="bar" if print_info else None,
    )

    end_time = time.time()
    total_time = end_time - _start_time
    render_time = total_time - generation_time

    if print_info:
        # Reload the output video to check its actual duration and frames
        try:
            output_clip = VideoFileClip(output_file)
            print(f"Output video ({output_file}): duration={output_clip.duration}s, fps={output_clip.fps}, size=({output_clip.w}x{output_clip.h})")
            print(f"  Total frames in output video: {int(output_clip.duration * output_clip.fps) if output_clip.duration and output_clip.fps else 'N/A'}")
            output_clip.close()
        except Exception as e:
            print(f"Could not read output video details: {e}")

        print(f"Generated in {generation_time//60:02.0f}:{generation_time%60:02.0f}")
        print(f"Rendered in {render_time//60:02.0f}:{render_time%60:02.0f}")
        print(f"Done in {total_time//60:02.0f}:{total_time%60:02.0f}")
