import argparse
import os
import logging
from moviepy.editor import CompositeVideoClip, ColorClip, AudioFileClip, VideoFileClip # type: ignore
from moviepy.video.fx.all import crop, resize # type: ignore

# Updated import for transcription module
from .fx.transcription import transcribe_locally, align_words_to_script, DEFAULT_WHISPER_MODEL, DEFAULT_MODEL_DOWNLOAD_ROOT
from .fx.caption_generator import generate_moviepy_caption_clips, CaptionStyleConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define default output directory within backend/assets/output/
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# generate_video.py is in backend/text_to_video/
# Target is backend/assets/output/
# So, from CURRENT_SCRIPT_DIR, we go up one level ("..") to backend/, then into assets/output/
DEFAULT_OUTPUT_DIR = os.path.join(CURRENT_SCRIPT_DIR, "..", "assets", "output")
os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

DEFAULT_VIDEO_DIMENSIONS = (1080, 1920) # Vertical TikTok style
DEFAULT_FPS = 24

TARGET_ASPECT_RATIO = 9.0 / 16.0
TARGET_DIMENSIONS = DEFAULT_VIDEO_DIMENSIONS

def main():
    parser = argparse.ArgumentParser(description="Generate a video with dynamic captions.")
    parser.add_argument("--audio_path", type=str, default=None, help="Path to an audio file for transcription and soundtrack.")
    parser.add_argument("--video_path", type=str, default=None, help="Path to a video file for visuals. If no --audio_path, its audio is used.")
    parser.add_argument("--output_filename", type=str, default=None, help="Optional: Filename for the output video.")
    parser.add_argument("--font_path", type=str, default="Arial", help="Path to the font file or font name for captions.")
    parser.add_argument("--font_size", type=int, default=72, help="Font size for captions.")
    parser.add_argument("--font_color", type=str, default="yellow", help="Font color for captions.")
    parser.add_argument("--stroke_width", type=int, default=3, help="Stroke width for captions.")
    parser.add_argument("--stroke_color", type=str, default="black", help="Stroke color for captions.")
    parser.add_argument("--padding_from_edge", type=int, default=60, help="Padding from video edge for captions (pixels).")
    parser.add_argument("--whisper_model", type=str, default=DEFAULT_WHISPER_MODEL, help=f"Whisper model to use (default: {DEFAULT_WHISPER_MODEL}).")
    parser.add_argument("--script_text", type=str, default=None, help="Optional: Target script text to align transcription against.")
    parser.add_argument("--script_file", type=str, default=None, help="Optional: Path to a .txt file containing the target script.")
    parser.add_argument("--highlight_current_word", action='store_true', help="Enable highlighting of the current word in captions.")
    parser.add_argument("--word_highlight_color", type=str, default="red", help="Color for highlighting the current word.")

    args = parser.parse_args()

    if not args.audio_path and not args.video_path:
        logger.error("You must provide either an --audio_path or a --video_path (or both).")
        return

    input_audio_for_transcription = None
    source_video_clip_for_visuals = None
    temp_audio_filename = None # For audio extracted from video if no separate audio_path
    initial_video_duration = 0.0 # Duration from source video if provided

    # Determine the audio source for transcription
    if args.audio_path:
        if not os.path.exists(args.audio_path):
            logger.error(f"Provided audio file not found: {args.audio_path}")
            return
        input_audio_for_transcription = args.audio_path
        logger.info(f"Using provided audio file for transcription and soundtrack: {args.audio_path}")
    elif args.video_path: # No separate audio, try to extract from video
        if not os.path.exists(args.video_path):
            logger.error(f"Video file for audio extraction not found: {args.video_path}")
            return
        try:
            logger.info(f"No separate audio path. Attempting to extract audio from video: {args.video_path}")
            video_for_audio_extraction = VideoFileClip(args.video_path)
            if video_for_audio_extraction.audio is None:
                logger.error(f"The video file {args.video_path} has no audio track.")
                return # Cannot proceed if this was the only audio source

            temp_audio_filename = os.path.join(DEFAULT_OUTPUT_DIR, f"temp_audio_from_video_{os.path.basename(args.video_path)}.mp3")
            video_for_audio_extraction.audio.write_audiofile(temp_audio_filename, logger=None)
            input_audio_for_transcription = temp_audio_filename
            logger.info(f"Extracted audio from video to {temp_audio_filename} for transcription.")
            # Keep video_for_audio_extraction open if it's also the visual source later
        except Exception as e:
            logger.error(f"Error extracting audio from video {args.video_path}: {e}")
            if temp_audio_filename and os.path.exists(temp_audio_filename):
                 os.remove(temp_audio_filename) # Clean up partial temp file
            return

    if not input_audio_for_transcription:
        logger.error("Critical: No audio could be sourced for transcription.")
        return

    # Process video for visuals if path is provided
    if args.video_path:
        if not os.path.exists(args.video_path):
            # This should have been caught if it was the audio source, but check again for clarity
            logger.error(f"Video file for visuals not found: {args.video_path}")
            if temp_audio_filename and os.path.exists(temp_audio_filename):
                 os.remove(temp_audio_filename) # Clean up if temp audio was made
            return
        try:
            logger.info(f"Loading video for visuals: {args.video_path}")
            source_video_clip_for_visuals = VideoFileClip(args.video_path)
            initial_video_duration = source_video_clip_for_visuals.duration
        except Exception as e:
            logger.error(f"Error loading video file {args.video_path} for visuals: {e}")
            if temp_audio_filename and os.path.exists(temp_audio_filename):
                os.remove(temp_audio_filename) # Clean up if temp audio was made
            return

    # --- 1. Transcription ---
    logger.info(f"Starting transcription for {input_audio_for_transcription} using model {args.whisper_model}...")
    # transcribe_locally returns List[SegmentDict]
    raw_segments = transcribe_locally(
        audio_file_path=input_audio_for_transcription,
        whisper_model_name=args.whisper_model,
        model_download_root=DEFAULT_MODEL_DOWNLOAD_ROOT
    )

    if not raw_segments or not raw_segments[0].get("words"):
        logger.error("Transcription failed or no words/segments were found.")
        if temp_audio_filename and os.path.exists(temp_audio_filename):
             os.remove(temp_audio_filename)
        return
    logger.info(f"Transcription successful, {len(raw_segments[0]['words'])} words found in {len(raw_segments)} segment(s).")

    # --- Script Alignment ---
    target_script_content = None
    if args.script_text:
        target_script_content = args.script_text
    elif args.script_file:
        if os.path.exists(args.script_file):
            try:
                with open(args.script_file, 'r', encoding='utf-8') as f_script:
                    target_script_content = f_script.read()
                logger.info(f"Loaded target script from: {args.script_file}")
            except Exception as e:
                logger.error(f"Error reading script file {args.script_file}: {e}")
        else:
            logger.warning(f"Script file {args.script_file} not found. No alignment.")

    processed_segments = raw_segments
    if target_script_content:
        logger.info("Aligning transcribed segments to the provided script...")
        # align_words_to_script now takes segments and returns segments
        processed_segments = align_words_to_script(raw_segments, target_script_content)
        if processed_segments and processed_segments[0].get("words"):
            logger.info(f"Alignment complete. Words after alignment: {len(processed_segments[0]['words'])} in {len(processed_segments)} segment(s).")
        else:
            logger.warning("Alignment resulted in no words/segments. Using raw transcription.")
            processed_segments = raw_segments # Fallback to raw if alignment fails badly

    # For generate_moviepy_caption_clips, we need a flat list of words.
    # Assuming single segment for now as per current transcribe_locally and align_words_to_script output.
    timed_words_for_captions = []
    if processed_segments and processed_segments[0].get("words"):
        timed_words_for_captions = processed_segments[0]["words"]
    else:
        logger.error("No timed words available after transcription/alignment to generate captions.")
        if temp_audio_filename and os.path.exists(temp_audio_filename):
            os.remove(temp_audio_filename)
        return

    # --- 2. Define Video Properties & Caption Styling ---
    final_video_dimensions = TARGET_DIMENSIONS
    caption_based_duration = 0.0
    if timed_words_for_captions:
        last_word_end = timed_words_for_captions[-1].get("end")
        if isinstance(last_word_end, (int, float)): caption_based_duration = float(last_word_end)
    if caption_based_duration <= 0: caption_based_duration = 5.0 # Fallback duration

    caption_style = CaptionStyleConfig(
        font_path=args.font_path,
        font_size=args.font_size,
        font_color=args.font_color,
        stroke_width=args.stroke_width,
        stroke_color=args.stroke_color,
        padding_from_edge=args.padding_from_edge,
        highlight_current_word=args.highlight_current_word,
        highlight_color=args.word_highlight_color
    )
    logger.info(f"Using caption style: {caption_style}")

    # --- 3. Generate Caption Clips ---
    logger.info("Generating caption clips...")
    # generate_moviepy_caption_clips now expects segments_data
    caption_clips = generate_moviepy_caption_clips(
        segments_data=processed_segments, # Pass the segments list directly
        video_dimensions=final_video_dimensions,
        style_config=caption_style
    )
    if not caption_clips:
        logger.warning("No caption clips were generated. Proceeding with a video without captions if possible.")

    # --- 4. Prepare Base Video Layer & Determine Final Duration ---
    base_video_layer = None
    actual_audio_duration_from_file = 0.0

    # Load the definitive audio file for the soundtrack to get its duration
    try:
        definitive_audio_clip = AudioFileClip(input_audio_for_transcription)
        actual_audio_duration_from_file = definitive_audio_clip.duration
        logger.info(f"Duration of audio source '{input_audio_for_transcription}': {actual_audio_duration_from_file:.2f}s")
    except Exception as e:
        logger.error(f"Could not load audio from {input_audio_for_transcription} to determine its duration: {e}.")
        # Fallback if audio duration can't be read, though transcription would likely have failed earlier.
        actual_audio_duration_from_file = initial_video_duration if source_video_clip_for_visuals else caption_based_duration
        if actual_audio_duration_from_file == 0 and caption_based_duration > 0 : actual_audio_duration_from_file = caption_based_duration
        elif actual_audio_duration_from_file == 0 : actual_audio_duration_from_file = 5.0 # Absolute fallback
        logger.warning(f"Using fallback for audio duration: {actual_audio_duration_from_file:.2f}s")

    # Determine final playback duration (total_duration)
    if args.audio_path:
        # If a specific audio file is given (--audio_path), its duration is the authoritative length.
        total_duration = actual_audio_duration_from_file
        logger.info(
            f"Authoritative duration set by --audio_path ({args.audio_path}): {total_duration:.2f}s. "
            f"Visuals and captions will be truncated if they exceed this."
        )
        if source_video_clip_for_visuals and initial_video_duration > total_duration:
            logger.info(f"Visual video (original duration {initial_video_duration:.2f}s) will be truncated to {total_duration:.2f}s.")
        if caption_based_duration > total_duration: # Note: captions are timed absolutely, truncation is implicit by video end
            logger.info(f"Caption content (ends at {caption_based_duration:.2f}s) may extend beyond video end ({total_duration:.2f}s). Truncation is implicit.")

    else:
        # No --audio_path. Audio was extracted from --video_path (if provided).
        # The video's own length (visual and audio) or caption length determines duration.
        # actual_audio_duration_from_file is the duration of audio extracted from the video.
        # initial_video_duration is the duration of the video visuals. These should be nearly identical.

        primary_media_duration = 0.0
        if source_video_clip_for_visuals: # implies audio came from this video.
            primary_media_duration = initial_video_duration # Duration of the video file itself
            # Sanity check if video's visual and audio track lengths differ wildly (can happen with bad files)
            if abs(initial_video_duration - actual_audio_duration_from_file) > 0.5: # More than 0.5s diff
                logger.warning(
                    f"Visual video duration ({initial_video_duration:.2f}s) and its extracted audio duration "
                    f"({actual_audio_duration_from_file:.2f}s) differ. Using visual duration as primary for this case."
                )
        elif input_audio_for_transcription : # Only audio was provided (e.g. --audio_path only, handled by the 'if args.audio_path:' block)
                                            # This 'else' branch implies --audio_path was NOT given.
                                            # So, if source_video_clip_for_visuals is None here, it means an error in logic or ColorClip.
                                            # For ColorClip with extracted audio (no video_path), audio duration is key.
                                            # This specific sub-case (no video_path, but also no args.audio_path) is an edge case
                                            # where input_audio_for_transcription would be a temp file from a video that was NOT args.video_path
                                            # which means it should have been caught by args.audio_path.
                                            # For safety, if we reach here without source_video_clip_for_visuals, audio is king.
            primary_media_duration = actual_audio_duration_from_file

        # Whichever is longer: the media's own playthrough time, or the time taken by captions.
        total_duration = max(caption_based_duration, primary_media_duration)
        if primary_media_duration == 0 and total_duration == 0: # Absolute fallback if everything is zero
            total_duration = 5.0
            logger.warning(f"All media and caption durations were zero. Defaulting to {total_duration:.2f}s.")

        logger.info(
            f"Duration based on provided media (video/audio length: {primary_media_duration:.2f}s) "
            f"and caption content (ends at {caption_based_duration:.2f}s). Calculated final video duration: {total_duration:.2f}s."
        )

    logger.info(f"Final video output duration will be set to: {total_duration:.2f}s")

    # Process the visual video layer (if one was provided)
    if source_video_clip_for_visuals:
        logger.info(f"Processing visual video (original size: {source_video_clip_for_visuals.size}, duration: {initial_video_duration:.2f}s)")
        current_w, current_h = source_video_clip_for_visuals.size
        target_w, target_h = TARGET_DIMENSIONS
        current_aspect = current_w / current_h
        processed_visual_clip = None

        if current_aspect > TARGET_ASPECT_RATIO: # Wider than target
            resized_intermediate = source_video_clip_for_visuals.resize(height=target_h)
            crop_amount = (resized_intermediate.w - target_w) / 2
            if crop_amount >= 0: processed_visual_clip = crop(resized_intermediate, x1=crop_amount, width=target_w)
            else: processed_visual_clip = resized_intermediate.resize((target_w, target_h)) # Fallback
        elif current_aspect < TARGET_ASPECT_RATIO: # Narrower than target
            resized_intermediate = source_video_clip_for_visuals.resize(width=target_w)
            crop_amount = (resized_intermediate.h - target_h) / 2
            if crop_amount >= 0: processed_visual_clip = crop(resized_intermediate, y1=crop_amount, height=target_h)
            else: processed_visual_clip = resized_intermediate.resize((target_w, target_h)) # Fallback
        else: # Aspect ratios match
            processed_visual_clip = source_video_clip_for_visuals.resize(TARGET_DIMENSIONS)

        base_video_layer = processed_visual_clip.set_duration(total_duration)
        # Remove audio from this visual clip if a separate audio_path was provided
        if args.audio_path and source_video_clip_for_visuals.audio is not None:
            base_video_layer = base_video_layer.without_audio()

    else: # No video file, use ColorClip
        base_video_layer = ColorClip(size=final_video_dimensions, color=(50, 50, 50), duration=total_duration)

    # --- 5. Prepare Final Audio ---
    final_audio_track = None
    try:
        # Load the audio clip that will be used for the final video.
        # Its duration will be its natural duration.
        # If the total_duration of the video is longer, there will be silence.
        # If the total_duration is shorter, the audio will be truncated by the final composite.
        final_audio_track = AudioFileClip(input_audio_for_transcription)
        logger.info(f"Loaded final audio track from {input_audio_for_transcription} with natural duration: {final_audio_track.duration:.2f}s")
    except Exception as e:
        logger.error(f"Failed to prepare final audio track from {input_audio_for_transcription}: {e}")

    # --- 6. Composite Video ---
    logger.info("Compositing final video...")
    video_elements = [base_video_layer] + caption_clips
    final_video = CompositeVideoClip(video_elements, size=final_video_dimensions)
    if final_audio_track:
        final_video = final_video.set_audio(final_audio_track)
    final_video = final_video.set_duration(total_duration)

    # --- 7. Render Output ---
    output_filename = args.output_filename
    if not output_filename:
        src_basename = "captioned_video"
        if args.video_path: src_basename = os.path.splitext(os.path.basename(args.video_path))[0]
        elif args.audio_path: src_basename = os.path.splitext(os.path.basename(args.audio_path))[0]
        output_filename = f"{src_basename}_captioned.mp4"
    output_path = os.path.join(DEFAULT_OUTPUT_DIR, output_filename)

    logger.info(f"Rendering final video to: {output_path}")
    try:
        final_video.write_videofile(
            output_path, fps=DEFAULT_FPS, codec="libx264", audio_codec="aac",
            threads=4, logger='bar'
        )
        logger.info(f"Video successfully generated: {output_path}")
    except Exception as e:
        logger.error(f"Failed to write video file: {e}", exc_info=True)

    # Clean up temporary extracted audio file
    if temp_audio_filename and os.path.exists(temp_audio_filename):
        try:
            os.remove(temp_audio_filename)
            logger.info(f"Cleaned up temporary audio file: {temp_audio_filename}")
        except Exception as e_del:
            logger.warning(f"Could not delete temp audio file {temp_audio_filename}: {e_del}")

if __name__ == "__main__":
    main()
