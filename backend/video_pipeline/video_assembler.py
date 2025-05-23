import warnings

# Suppress specific UserWarning from ffmpeg_reader concerning frame reading issues
warnings.filterwarnings('ignore', message=".*bytes wanted but 0 bytes read.*", category=UserWarning)

import os
import json
import pathlib
import logging
import tempfile # Added for temporary audio/video files
import yaml # Added for loading config
import shutil # Added for cleaning up temp step files
from moviepy.editor import (
    concatenate_videoclips, AudioFileClip, VideoFileClip, VideoClip, CompositeVideoClip, ImageClip,
    concatenate_audioclips, CompositeAudioClip, TextClip # Added TextClip for potential future use
)

# Project-level imports (ensure these paths are correct relative to where this script is run from)
# Assuming run from project root or PYTHONPATH is set up
from backend.video_pipeline.video_utils import (
    process_image_to_video_clip,
    process_video_clip,
    # TIKTOK_DIMS, # Removed, will load from config
    # DEFAULT_FPS # Removed, will load from config
)
from backend.text_to_video.fx.text_animations import animate_text_fade, animate_text_scale # Added animate_text_scale
from backend.text_to_video.fx import add_captions as add_captions_fx # For captions step

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CONFIG_FILE_PATH = PROJECT_ROOT / "backend" / "tests" / "test_config.yaml" # Path to the config

# Load config for FPS and Dimensions
def load_assembly_config():
    if not CONFIG_FILE_PATH.exists():
        # Fallback for critical parameters if config is missing, though this should not happen in a normal run
        logger.error(f"Config file not found at {CONFIG_FILE_PATH}. Using emergency fallbacks for FPS/Dimensions.")
        return {"video_general": {"TARGET_FPS": 30, "TARGET_DIMENSIONS": [1080, 1920]}}
    with open(CONFIG_FILE_PATH, 'r') as f:
        return yaml.safe_load(f)

assembly_config_data = load_assembly_config()
VIDEO_CONFIG = assembly_config_data.get("video_general", {})
TARGET_FPS = VIDEO_CONFIG.get("TARGET_FPS", 30) # Default to 30 if not in config
TARGET_DIMENSIONS = tuple(VIDEO_CONFIG.get("TARGET_DIMENSIONS", [1080, 1920])) # Default if not in config
if len(TARGET_DIMENSIONS) != 2:
    logger.warning(f"TARGET_DIMENSIONS from config is not a pair: {TARGET_DIMENSIONS}. Using default [1080, 1920].")
    TARGET_DIMENSIONS = (1080, 1920)

DEFAULT_INPUT_SUMMARY = PROJECT_ROOT / "test_outputs" / "orchestration_summary_updated_by_assembler_test.json"
# Fallback if the assembler test hasn't created the "updated" one
if not DEFAULT_INPUT_SUMMARY.exists():
    DEFAULT_INPUT_SUMMARY = PROJECT_ROOT / "test_outputs" / "orchestration_summary_output.json"

# Path to the transcription file - needed for precise end-of-speech timing
DEFAULT_TRANSCRIPTION_PATH = PROJECT_ROOT / "test_outputs" / "e2e_transcription_output.json"

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "test_outputs" / "final_video_assembly"
TEMP_ASSEMBLY_DIR = PROJECT_ROOT / "test_outputs" / "temp_assembly_files" # For inspectable temp files
TEMP_ASSEMBLY_DIR.mkdir(parents=True, exist_ok=True) # Ensure it exists

# Output filenames for each step
OUTPUT_FILENAME_STEP1_BASE = "assembled_video_step1_base.mp4"
OUTPUT_FILENAME_STEP2_FX = "assembled_video_step2_fx.mp4"
OUTPUT_FILENAME_STEP3_FINAL = "assembled_video_step3_final.mp4"

# TIKTOK_ASPECT_RATIO = TIKTOK_DIMS[0] / TIKTOK_DIMS[1] # Will use TARGET_DIMENSIONS
# DEFAULT_TARGET_FPS_ASSEMBLY = 24 # Consistent FPS for assembly output - Will use TARGET_FPS

# FX Configuration
FX_TEXT_SIZE_MAPPING = {
    "small": 60,
    "medium": 80,
    "large": 100,
    "extralarge": 130,
    "default": 80
}
FX_DEFAULT_FADE_DURATION = 0.5 # seconds for fadein/fadeout

# Caption Configuration (can be expanded or moved to a config file)
CAPTION_FONT = "Bangers-Regular.ttf" # Ensure this font is in backend/assets/fonts/
CAPTION_FONT_SIZE = 70
CAPTION_FONT_COLOR = "yellow"
CAPTION_STROKE_WIDTH = 2
CAPTION_STROKE_COLOR = "black"
CAPTION_HIGHLIGHT_WORD = True
CAPTION_WORD_HIGHLIGHT_COLOR = "red"
CAPTION_LINE_COUNT = 2 # Max lines per caption block
CAPTION_PADDING = 50 # Padding from edge for caption bounding box
CAPTION_POSITION = "bottom-center" # As understood by add_captions_fx
CAPTION_SHADOW_STRENGTH = 0.5
CAPTION_SHADOW_BLUR = 0.05

def debug_single_scene(scene_id_to_debug: str, orchestration_summary_path: str):
    logger.info(f"--- DEBUGGING SINGLE SCENE: {scene_id_to_debug} ---")
    if not pathlib.Path(orchestration_summary_path).exists():
        logger.error(f"Orchestration summary file not found: {orchestration_summary_path}")
        return

    try:
        with open(orchestration_summary_path, 'r') as f:
            summary_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load or parse orchestration summary {orchestration_summary_path}: {e}")
        return

    scene_plans = []
    if isinstance(summary_data, dict):
        scene_plans = summary_data.get("scene_plans", [])
    elif isinstance(summary_data, list):
        scene_plans = summary_data
    else:
        logger.error("Unknown summary format.")
        return

    target_scene = next((s for s in scene_plans if s.get("scene_id") == scene_id_to_debug), None)

    if not target_scene:
        logger.error(f"Scene {scene_id_to_debug} not found in orchestration summary.")
        return

    asset_path_str = None
    visual_type = target_scene.get("visual_type")
    scene_duration = target_scene.get("end_time", 0) - target_scene.get("start_time", 0)

    if visual_type == "STOCK_IMAGE":
        asset_path_str = target_scene.get("image_asset_path")
        processed_clip = process_image_to_video_clip(asset_path_str, scene_duration, TARGET_DIMENSIONS, fps=TARGET_FPS)
    elif visual_type in ["STOCK_VIDEO", "AVATAR"]:
        asset_path_str = target_scene.get("video_asset_path") or target_scene.get("avatar_video_path")
        processed_clip = process_video_clip(asset_path_str, scene_duration, TARGET_DIMENSIONS, target_fps=TARGET_FPS)
    else:
        logger.error(f"Unknown visual type for scene {scene_id_to_debug}")
        return

    if processed_clip:
        debug_output_dir = PROJECT_ROOT / "test_outputs" / "debug_single_scene"
        debug_output_dir.mkdir(parents=True, exist_ok=True)
        debug_output_path = debug_output_dir / f"debugged_{scene_id_to_debug}_{pathlib.Path(asset_path_str).name}"
        logger.info(f"Writing debug clip for scene {scene_id_to_debug} to: {debug_output_path}")
        try:
            processed_clip.write_videofile(str(debug_output_path), codec="libx264", audio_codec="aac", fps=processed_clip.fps or TARGET_FPS, logger=None) # Changed logger
            logger.info(f"Debug clip saved: {debug_output_path}. Please check if it plays correctly.")
        except Exception as e:
            logger.error(f"Error writing debug clip for scene {scene_id_to_debug}: {e}")
        finally:
            if hasattr(processed_clip, 'close'): processed_clip.close()
    else:
        logger.error(f"Failed to process debug scene {scene_id_to_debug} from asset {asset_path_str}")

def assemble_video_step1_base_visuals_and_audio(
    orchestration_summary_path: str,
    output_dir_path: pathlib.Path, # Changed to pathlib.Path
    output_filename: str,
    transcription_path: str,
    target_fps: int, # Added
    target_dims: tuple[int, int] # Added
) -> str | None: # Returns path to the generated video or None on failure
    """
    Step 1: Assembles base video with concatenated visuals and final audio (VO + BG music).
    NO FX are applied in this step.
    """
    logger.info(f"--- STEP 1: Assembling Base Visuals and Audio --- ")
    logger.info(f"Using summary: {orchestration_summary_path}")
    final_output_path = output_dir_path / output_filename

    # Load orchestration summary
    if not pathlib.Path(orchestration_summary_path).exists():
        logger.error(f"Orchestration summary file not found: {orchestration_summary_path}")
        return None
    try:
        with open(orchestration_summary_path, 'r') as f: summary_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load or parse orchestration summary {orchestration_summary_path}: {e}"); return None

    # Load transcription data for timing
    if not pathlib.Path(transcription_path).exists():
        logger.error(f"Transcription file not found: {transcription_path}"); return None
    try:
        with open(transcription_path, 'r') as f: transcription_data = json.load(f)
        if not transcription_data: logger.error("Transcription data is empty."); return None
        max_transcription_time = transcription_data[-1]['end']
        logger.info(f"Determined max_transcription_time (end of last word): {max_transcription_time:.2f}s")
    except Exception as e:
        logger.error(f"Failed to load or parse transcription data from {transcription_path}: {e}"); return None

    # Extract scene_plans, master_vo_path, background_music_path
    scene_plans = summary_data.get("scene_plans", []) if isinstance(summary_data, dict) else summary_data
    if not isinstance(scene_plans, list): # Handle case where summary_data was dict but no scene_plans key
        logger.error("Scene plans are not in a list format or not found."); return None

    master_vo_path_str = summary_data.get("master_vo_path") if isinstance(summary_data, dict) else None
    background_music_path_str = summary_data.get("background_music_path") if isinstance(summary_data, dict) else None

    if isinstance(summary_data, list): # Fallback for older list-based summary for master_vo_path
        logger.warning("Orchestration summary is a list (older format). Attempting to find fallback Master VO.")
        potential_vo_path = PROJECT_ROOT / "test_outputs" / "How_Tencent_Bought_Its_Way_Into_AI_s_Top_8_master_vo.mp3"
        if potential_vo_path.exists(): master_vo_path_str = str(potential_vo_path)
        else: logger.error("Master VO path could not be determined from list-formatted summary and fallback not found."); return None

    if not scene_plans: logger.error("No scene plans found."); return None
    if not master_vo_path_str or not pathlib.Path(master_vo_path_str).exists():
        logger.error(f"Master voiceover file not found at '{master_vo_path_str}'."); return None

    # Temporary file paths for this step
    vo_filename_stem = pathlib.Path(master_vo_path_str).stem
    temp_final_audio_path = TEMP_ASSEMBLY_DIR / f"step1_temp_audio_{vo_filename_stem}.mp3"
    temp_final_visual_path = TEMP_ASSEMBLY_DIR / f"step1_temp_visual_{vo_filename_stem}.mp4"
    logger.info(f"Step 1 Temp audio: {temp_final_audio_path}")
    logger.info(f"Step 1 Temp visuals: {temp_final_visual_path}")

    # Fallback for background music
    if not background_music_path_str or not pathlib.Path(background_music_path_str).exists():
        fallback_bg_music_path = PROJECT_ROOT / "test_outputs" / "background_music.mp3"
        if fallback_bg_music_path.exists():
            logger.warning(f"BG music not in summary or invalid. Using fallback: {fallback_bg_music_path}")
            background_music_path_str = str(fallback_bg_music_path)
        # else: logger info/warning about no BG music will be handled in audio prep section

    # --- Process scene assets into MoviePy clips (NO FX HERE) ---
    source_clips_for_visual_track = []
    last_scene_planned_end_time = 0.0

    for i, scene in enumerate(scene_plans):
        logger.info(f"Processing scene {scene.get('scene_id', i+1)}: Type {scene.get('visual_type')}")
        planned_scene_start_time = scene.get("start_time")
        planned_scene_end_time = scene.get("end_time")

        if planned_scene_start_time is None or planned_scene_end_time is None:
            logger.warning(f"Scene {scene.get('scene_id', i+1)} is missing start_time or end_time. Skipping."); continue
        current_scene_original_planned_duration = planned_scene_end_time - planned_scene_start_time
        last_scene_planned_end_time = planned_scene_end_time
        if current_scene_original_planned_duration <= 0:
            logger.warning(f"Scene {scene.get('scene_id', i+1)} non-positive duration. Skipping."); continue

        duration_for_this_clip_processing = current_scene_original_planned_duration
        if i < len(scene_plans) - 1:
            next_scene = scene_plans[i+1]
            next_scene_planned_start_time = next_scene.get("start_time")
            if next_scene_planned_start_time is not None:
                gap_after_current_to_next_start = next_scene_planned_start_time - planned_scene_end_time
                if gap_after_current_to_next_start > 0.01:
                    duration_for_this_clip_processing += gap_after_current_to_next_start

        asset_path_str = None; visual_type = scene.get("visual_type")
        if visual_type == "AVATAR": asset_path_str = scene.get("avatar_video_path")
        elif visual_type == "STOCK_VIDEO": asset_path_str = scene.get("video_asset_path")
        elif visual_type == "STOCK_IMAGE": asset_path_str = scene.get("image_asset_path")
        else: logger.warning(f"Unknown visual_type '{visual_type}'. Skipping."); continue

        if not asset_path_str or not pathlib.Path(asset_path_str).exists():
            logger.error(f"Asset path for '{asset_path_str}' not found. Skipping."); continue

        processed_clip = None
        if visual_type == "STOCK_IMAGE":
            processed_clip = process_image_to_video_clip(asset_path_str, duration_for_this_clip_processing, target_dims, fps=target_fps)
        else:
            processed_clip = process_video_clip(asset_path_str, duration_for_this_clip_processing, target_dims, target_fps=target_fps)

        if processed_clip:
            if processed_clip.duration is None or processed_clip.duration < 0.01: # Check duration
                logger.warning(f"Scene {scene.get('scene_id', i+1)} processed clip has zero/None duration. Skipping.")
                if hasattr(processed_clip, 'close'): processed_clip.close(); continue

            processed_clip = processed_clip.set_audio(None) # Ensure silent
            source_clips_for_visual_track.append(processed_clip)
            clip_fps = processed_clip.fps if hasattr(processed_clip, 'fps') and processed_clip.fps else target_fps
            num_frames = int(processed_clip.duration * clip_fps) if processed_clip.duration else 0
            logger.info(f"  Successfully processed scene {scene.get('scene_id', i+1)}. Actual clip duration: {processed_clip.duration:.2f}s, FPS: {clip_fps}, Frames: {num_frames}")
        else:
            logger.error(f"Failed to process asset for scene {scene.get('scene_id', i+1)}. Skipping.")

    if not source_clips_for_visual_track: logger.error("No scenes processed for visual track."); return None

    # --- Trailing transcription gap filling (remains the same) ---
    total_calculated_duration_pre_trailing_fill = sum(c.duration for c in source_clips_for_visual_track if c and c.duration is not None)
    current_visual_timeline_end = total_calculated_duration_pre_trailing_fill
    if current_visual_timeline_end < max_transcription_time:
        trailing_speech_to_cover = max_transcription_time - current_visual_timeline_end
        if trailing_speech_to_cover > 0.01 and source_clips_for_visual_track:
            last_visual_clip = source_clips_for_visual_track[-1]
            new_duration_for_last_clip = (last_visual_clip.duration or 0) + trailing_speech_to_cover
            try:
                extended_last_clip = last_visual_clip.set_duration(new_duration_for_last_clip)
                if extended_last_clip.duration and extended_last_clip.duration >= 0.01:
                    source_clips_for_visual_track[-1] = extended_last_clip
            except Exception as e: logger.error(f"Error extending last visual clip: {e}")

    # --- Concatenate visual clips (remains the same) ---
    final_visual_track = None
    try:
        final_visual_track = concatenate_videoclips(source_clips_for_visual_track, method="compose")
        if not final_visual_track: logger.error("concatenate_videoclips returned None."); return None # Clean up handled by finally
        if final_visual_track.fps is None or final_visual_track.fps != target_fps:
            final_visual_track = final_visual_track.set_fps(target_fps)
        logger.info(f"Base visual track concatenated. Duration: {final_visual_track.duration:.2f}s, FPS: {final_visual_track.fps}")
    except Exception as e: logger.error(f"Error concatenating video clips: {e}"); return None # Clean up handled by finally

    # --- STEP 1A (for this function): Prepare and Write Final Audio Track ---
    master_audio_clip = None; bg_music_clip_original = None; final_audio_for_file_write = None
    actual_final_audio_duration = 0
    bg_music_final_processed_clip = None
    try:
        master_audio_clip = AudioFileClip(master_vo_path_str)
        final_audio_for_file_write = master_audio_clip
        if background_music_path_str and pathlib.Path(background_music_path_str).exists():
            bg_music_clip_original = AudioFileClip(background_music_path_str)
            target_audio_duration = master_audio_clip.duration
            bg_music_adjusted_duration_clip = None
            if bg_music_clip_original.duration < target_audio_duration:
                temp_looped_bg_list = [bg_music_clip_original] * (int(target_audio_duration / bg_music_clip_original.duration) + 1)
                bg_music_looped_intermediate = concatenate_audioclips(temp_looped_bg_list)
                bg_music_adjusted_duration_clip = bg_music_looped_intermediate.set_duration(target_audio_duration)
            else: bg_music_adjusted_duration_clip = bg_music_clip_original.set_duration(target_audio_duration)

            if bg_music_adjusted_duration_clip:
                bg_music_final_processed_clip = (bg_music_adjusted_duration_clip.volumex(0.08).audio_fadein(1.5).audio_fadeout(1.5))
                final_audio_for_file_write = CompositeAudioClip([master_audio_clip, bg_music_final_processed_clip])

        if not final_audio_for_file_write: logger.error("Final audio track is None before write."); return None
        actual_final_audio_duration = final_audio_for_file_write.duration
        audio_fps = 44100
        logger.info(f"Writing base audio to {temp_final_audio_path} (Dur: {actual_final_audio_duration:.2f}s)")
        final_audio_for_file_write.write_audiofile(str(temp_final_audio_path), fps=audio_fps, logger=None)
    except Exception as e: logger.error(f"Error preparing base audio: {e}"); return None
    finally:
        # Simplified audio cleanup for this step
        for clip_obj in [master_audio_clip, bg_music_clip_original, final_audio_for_file_write, bg_music_final_processed_clip, locals().get('bg_music_looped_intermediate'), locals().get('bg_music_adjusted_duration_clip')]:
            if clip_obj and hasattr(clip_obj, 'close'):
                # Avoid double closing if objects are the same (e.g. final_audio_for_file_write might be master_audio_clip)
                # This check isn't perfect for all aliasing but helps for direct assignment.
                is_primary_source = (clip_obj == master_audio_clip or clip_obj == bg_music_clip_original)
                is_final_composite = (clip_obj == final_audio_for_file_write)
                if not (is_final_composite and clip_obj == master_audio_clip): # Avoid double-closing master if it was the final write object
                    try: clip_obj.close()
                    except Exception as e_close_audio: logger.warning(f"Minor error closing audio clip: {e_close_audio}")

    # --- STEP 1B (for this function): Prepare and Write Final SILENT Visual Track ---
    final_visual_track_silent = None
    try:
        if not final_visual_track: logger.error("Base visual track is None before silent write."); return None
        target_visual_duration = actual_final_audio_duration
        if abs(final_visual_track.duration - target_visual_duration) > 0.01:
            final_visual_track = final_visual_track.set_duration(target_visual_duration)
        final_visual_track_silent = final_visual_track.without_audio()
        output_fps = final_visual_track_silent.fps or target_fps
        logger.info(f"Writing base silent visual to {temp_final_visual_path} (Dur: {final_visual_track_silent.duration:.2f}s, FPS: {output_fps})")
        final_visual_track_silent.write_videofile(str(temp_final_visual_path), codec="libx264", audio=False, fps=output_fps, logger=None)
    except Exception as e: logger.error(f"Error writing base silent visual: {e}"); return None
    finally:
        if final_visual_track and hasattr(final_visual_track, 'close'): final_visual_track.close()
        if final_visual_track_silent and hasattr(final_visual_track_silent, 'close') and final_visual_track_silent != final_visual_track: final_visual_track_silent.close()
        for clip in source_clips_for_visual_track:
            if hasattr(clip, 'close'):
                try: clip.close()
                except Exception as e_close_src: logger.warning(f"Minor error closing source visual clip: {e_close_src}")
        source_clips_for_visual_track = []

    # --- STEP 1C (for this function): Combine Temporary Audio and Video ---
    final_video_loaded = None; final_audio_loaded = None; video_with_combined_audio = None; video_ready_for_render = None
    try:
        if not temp_final_visual_path.exists() or not temp_final_audio_path.exists():
            logger.error("Temp visual or audio for base video not found."); return None
        final_video_loaded = VideoFileClip(str(temp_final_visual_path))
        final_audio_loaded = AudioFileClip(str(temp_final_audio_path))
        video_with_audio_intermediate = final_video_loaded.set_audio(final_audio_loaded)
        video_ready_for_render = video_with_audio_intermediate.set_duration(actual_final_audio_duration) # Use pre-calc audio duration

        output_fps_final = video_ready_for_render.fps if hasattr(video_ready_for_render, 'fps') and video_ready_for_render.fps else target_fps
        if not hasattr(video_ready_for_render, 'fps') or video_ready_for_render.fps != output_fps_final:
            video_ready_for_render = video_ready_for_render.set_fps(output_fps_final)

        if not video_ready_for_render: logger.error("Failed to prep base video for render."); return None
        logger.info(f"Writing Step 1 (Base) video to: {final_output_path} (Dur: {video_ready_for_render.duration:.2f}s)")
        video_ready_for_render.write_videofile(str(final_output_path), codec="libx264", audio_codec="aac", fps=output_fps_final, logger=None)
        logger.info(f"Successfully assembled Step 1 (Base) video: {final_output_path}")
        return str(final_output_path)
    except Exception as e:
        logger.error(f"Error combining base audio/video: {e}", exc_info=True); return None
    finally:
        for clip_obj in [final_video_loaded, final_audio_loaded, video_with_audio_intermediate, video_ready_for_render]:
            if clip_obj and hasattr(clip_obj, 'close'):
                try: clip_obj.close()
                except Exception as e_close_final: logger.warning(f"Minor error closing final combination clip: {e_close_final}")
        # Keep temp files for inspection for now, as per previous settings
        # if temp_final_audio_path.exists(): temp_final_audio_path.unlink()
        # if temp_final_visual_path.exists(): temp_final_visual_path.unlink()

# Placeholder for Step 2
def apply_fx_to_video(input_video_path: str, output_dir_path: pathlib.Path, output_filename: str, scene_plans: list, target_fps: int, target_dims: tuple[int, int]) -> str | None: # Added target_fps and target_dims
    logger.info(f"--- STEP 2: Applying FX --- ")
    logger.info(f"Input video for FX: {input_video_path}")
    final_output_path = output_dir_path / output_filename

    if not pathlib.Path(input_video_path).exists():
        logger.error(f"Input video for FX not found: {input_video_path}")
        return None

    base_video_clip = None
    processed_fx_clips = [] # To hold the generated FX TextClips
    clips_to_composite = []

    try:
        base_video_clip = VideoFileClip(input_video_path)
        clips_to_composite.append(base_video_clip) # Start with the base video

        for scene_idx, scene in enumerate(scene_plans):
            fx_suggestion = scene.get("fx_suggestion")
            scene_id = scene.get("scene_id", f"scene_{scene_idx + 1}")

            if fx_suggestion and isinstance(fx_suggestion, dict):
                fx_type = fx_suggestion.get("type")
                if fx_type == "TEXT_OVERLAY_FADE":
                    logger.info(f"  Preparing FX: {fx_type} for scene {scene_id}")
                    try:
                        text_content = fx_suggestion.get("text_content", "Text FX")
                        params = fx_suggestion.get("params", {})
                        font_props_from_json = params.get("font_props", {})
                        size_keyword = font_props_from_json.get("size", "default").lower()
                        fontsize = FX_TEXT_SIZE_MAPPING.get(size_keyword, FX_TEXT_SIZE_MAPPING["default"])
                        font_name = font_props_from_json.get("font", "Arial-Bold")
                        pos_keyword = params.get("position", "center").lower()

                        position_map = {
                            "center": ("center", "center"), "top": ("center", "top"), "bottom": ("center", "bottom"),
                            "top-left": ("left", "top"), "top-right": ("right", "top"),
                            "bottom-left": ("left", "bottom"), "bottom-right": ("right", "bottom"),
                        }
                        text_position = position_map.get(pos_keyword, ("center", "center"))
                        if isinstance(params.get("position"), tuple) and len(params.get("position")) == 2:
                             text_position = params.get("position") # Allow direct tuple pass-through

                        fx_font_props = {
                            'font': font_name, 'fontsize': fontsize,
                            'color': font_props_from_json.get("color", "white"),
                        }

                        scene_start_time = scene.get("start_time")
                        scene_end_time = scene.get("end_time")

                        if scene_start_time is None or scene_end_time is None:
                            logger.warning(f"    Scene {scene_id} missing start/end times for FX. Skipping FX.")
                            continue

                        fx_clip_actual_duration = scene_end_time - scene_start_time
                        if fx_clip_actual_duration <= 0:
                            logger.warning(f"    Scene {scene_id} has zero or negative duration for FX ({fx_clip_actual_duration:.2f}s). Skipping FX.")
                            continue

                        # Ensure fade durations are reasonable for the FX clip's own duration
                        fade_in = min(FX_DEFAULT_FADE_DURATION, fx_clip_actual_duration / 3)
                        fade_out = min(FX_DEFAULT_FADE_DURATION, fx_clip_actual_duration / 3)

                        fx_animation_clip = animate_text_fade(
                            text_content=text_content,
                            total_duration=fx_clip_actual_duration, # Duration of the FX itself
                            screen_size=target_dims, # Use target_dims
                            font_props=fx_font_props,
                            position=text_position,
                            fadein_duration=fade_in,
                            fadeout_duration=fade_out,
                            is_transparent=True
                        )

                        if fx_animation_clip:
                            # Set the start time of this FX clip relative to the main video timeline
                            fx_animation_clip = fx_animation_clip.set_start(scene_start_time)
                            processed_fx_clips.append(fx_animation_clip)
                            logger.info(f"    Successfully prepared FX for scene {scene_id} with text: '{text_content}', Start: {scene_start_time:.2f}s, Dur: {fx_clip_actual_duration:.2f}s")
                        else:
                            logger.warning(f"    Failed to generate {fx_type} for scene {scene_id}")
                    except Exception as e_fx:
                        logger.error(f"    Error applying FX {fx_type} for scene {scene_id}: {e_fx}", exc_info=True)
                elif fx_type == "TEXT_OVERLAY_SCALE":
                    logger.info(f"  Preparing FX: {fx_type} for scene {scene_id}")
                    try:
                        text_content = fx_suggestion.get("text_content", "Scale FX")
                        params = fx_suggestion.get("params", {})
                        font_props_from_json = params.get("font_props", {})
                        size_keyword = font_props_from_json.get("size", "default").lower()
                        fontsize = FX_TEXT_SIZE_MAPPING.get(size_keyword, FX_TEXT_SIZE_MAPPING["default"])
                        font_name = font_props_from_json.get("font", "Arial-Bold")
                        pos_keyword = params.get("position", "center").lower()

                        position_map = {
                            "center": ("center", "center"), "top": ("center", "top"), "bottom": ("center", "bottom"),
                            "top-left": ("left", "top"), "top-right": ("right", "top"),
                            "bottom-left": ("left", "bottom"), "bottom-right": ("right", "bottom"),
                        }
                        text_position = position_map.get(pos_keyword, ("center", "center"))
                        if isinstance(params.get("position"), tuple) and len(params.get("position")) == 2:
                            text_position = params.get("position")

                        # Specific params for scale, with defaults if not in JSON
                        start_scale = float(params.get("start_scale", 1.0))
                        end_scale = float(params.get("end_scale", 2.0))
                        apply_fade_for_scale = bool(params.get("apply_fade", True))
                        fade_proportion_for_scale = float(params.get("fade_proportion", 0.2))

                        # assemble_final_video passes target_dims, which text_animations.py expects as screen_size
                        # animate_text_scale will use its own default font_props unless overridden
                        # We can pass a minimal font_props here if we only want to influence a part of it, or rely on its defaults.
                        # For now, let text_animations.py handle its defaults for font, size, color, stroke.
                        # If specific overrides are needed from params, they can be added to fx_font_props.
                        fx_font_props = {}
                        if "color" in font_props_from_json: fx_font_props['color'] = font_props_from_json["color"]
                        # if "fontsize" in font_props_from_json: fx_font_props['fontsize'] = font_props_from_json["fontsize"] # etc.

                        scene_start_time = scene.get("start_time")
                        scene_end_time = scene.get("end_time")

                        if scene_start_time is None or scene_end_time is None:
                            logger.warning(f"    Scene {scene_id} missing start/end times for FX. Skipping FX.")
                            continue
                        fx_clip_actual_duration = scene_end_time - scene_start_time
                        if fx_clip_actual_duration <= 0:
                            logger.warning(f"    Scene {scene_id} has zero or negative duration for FX ({fx_clip_actual_duration:.2f}s). Skipping FX.")
                            continue

                        fx_animation_clip = animate_text_scale(
                            text_content=text_content,
                            total_duration=fx_clip_actual_duration,
                            screen_size=target_dims,
                            font_props=fx_font_props if fx_font_props else None, # Pass None to use full defaults in animate_text_scale
                            position=text_position,
                            start_scale=start_scale,
                            end_scale=end_scale,
                            is_transparent=True, # Ensure transparent background
                            apply_fade=apply_fade_for_scale,
                            fade_proportion=fade_proportion_for_scale
                        )

                        if fx_animation_clip:
                            fx_animation_clip = fx_animation_clip.set_start(scene_start_time)
                            processed_fx_clips.append(fx_animation_clip)
                            logger.info(f"    Successfully prepared FX for scene {scene_id} with text: '{text_content}', Start: {scene_start_time:.2f}s, Dur: {fx_clip_actual_duration:.2f}s")
                        else:
                            logger.warning(f"    Failed to generate {fx_type} for scene {scene_id}")
                    except Exception as e_fx_scale:
                        logger.error(f"    Error applying FX {fx_type} for scene {scene_id}: {e_fx_scale}", exc_info=True)
                else:
                    logger.info(f"  Skipping unknown FX type: {fx_type} for scene {scene_id}")

        if not processed_fx_clips:
            logger.info("No FX were prepared or applied. Copying input video to output for Step 2.")
            if base_video_clip and hasattr(base_video_clip, 'close'): base_video_clip.close()
            import shutil
            shutil.copy(input_video_path, str(final_output_path))
            return str(final_output_path)

        # Add all prepared FX clips to the list for compositing
        clips_to_composite.extend(processed_fx_clips)

        # Create the final composite video with base video and all timed FX overlays
        logger.info(f"Compositing base video with {len(processed_fx_clips)} FX clips.")
        video_with_fx = CompositeVideoClip(clips_to_composite, size=target_dims) # Use target_dims
        # Ensure the final duration is that of the base video, as FX are overlays
        video_with_fx = video_with_fx.set_duration(base_video_clip.duration)
        if base_video_clip.audio: # Preserve audio from base video
            video_with_fx = video_with_fx.set_audio(base_video_clip.audio)

        output_fps = video_with_fx.fps if hasattr(video_with_fx, 'fps') and video_with_fx.fps else target_fps
        if not hasattr(video_with_fx, 'fps') or video_with_fx.fps != output_fps:
            video_with_fx = video_with_fx.set_fps(output_fps)

        logger.info(f"Writing Step 2 (FX) video to: {final_output_path} (Dur: {video_with_fx.duration:.2f}s, FPS: {output_fps})")
        video_with_fx.write_videofile(str(final_output_path), codec="libx264", audio_codec="aac", fps=output_fps, logger=None)
        logger.info(f"Successfully assembled Step 2 (FX) video: {final_output_path}")
        return str(final_output_path)

    except Exception as e:
        logger.error(f"Error during FX application (Step 2): {e}", exc_info=True)
        return None
    finally:
        if base_video_clip and hasattr(base_video_clip, 'close'):
            base_video_clip.close()
        for fx_clip in processed_fx_clips: # These are the full animation clips
            if hasattr(fx_clip, 'close'):
                try: fx_clip.close()
                except Exception as e_fx_close: logger.warning(f"Minor error closing FX animation clip: {e_fx_close}")
        # If video_with_fx was created, it should also be closed.
        # However, write_videofile usually closes the clip it writes. Let's be safe.
        if 'video_with_fx' in locals() and locals()['video_with_fx'] and hasattr(locals()['video_with_fx'], 'close'):
            try: locals()['video_with_fx'].close()
            except Exception as e_final_fx_close: logger.warning(f"Minor error closing final video_with_fx: {e_final_fx_close}")

def add_captions_to_video(input_video_path: str, output_dir_path: pathlib.Path, output_filename: str, transcription_data: list) -> str | None:
    logger.info(f"--- STEP 3: Adding Captions --- ")
    logger.info(f"Input video for Captions: {input_video_path}")
    final_output_path = output_dir_path / output_filename

    if not pathlib.Path(input_video_path).exists():
        logger.error(f"Input video for captions not found: {input_video_path}")
        return None

    if not transcription_data:
        logger.error("Transcription data is empty. Cannot add captions.")
        return None

    try:
        logger.info(f"Calling add_captions_fx for {input_video_path}")
        logger.info(f"Outputting captions to: {final_output_path}")

        # Transform transcription_data into the structure expected by segment_parser
        # segment_parser.parse expects a list of segments, where each segment has a "words" key.
        # The e2e_transcription_output.json is a flat list of word objects.
        # We'll treat the entire transcription as a single segment for captioning purposes here.
        segments_for_parser = None
        if transcription_data and isinstance(transcription_data, list) and \
           all(isinstance(item, dict) and "word" in item for item in transcription_data):
            segments_for_parser = [{"words": transcription_data}]
            logger.info("Wrapped flat transcription data into a single segment for caption parser.")
        else:
            # If transcription_data is already in the correct segmented format or is problematic,
            # pass it as is, or handle error.
            logger.warning("Transcription data is not a flat list-of-words or is empty/None. Passing as is to add_captions_fx. This might be intended if data is pre-segmented.")
            segments_for_parser = transcription_data

        add_captions_fx(\
            video_file=input_video_path,\
            output_file=str(final_output_path), \
            font=CAPTION_FONT, \
            font_size=CAPTION_FONT_SIZE,\
            font_color=CAPTION_FONT_COLOR,\
            stroke_width=CAPTION_STROKE_WIDTH,\
            stroke_color=CAPTION_STROKE_COLOR,\
            highlight_current_word=CAPTION_HIGHLIGHT_WORD,\
            word_highlight_color=CAPTION_WORD_HIGHLIGHT_COLOR,\
            line_count=CAPTION_LINE_COUNT,\
            padding=CAPTION_PADDING,\
            position=CAPTION_POSITION, \
            shadow_strength=CAPTION_SHADOW_STRENGTH,\
            shadow_blur=CAPTION_SHADOW_BLUR,\
            print_info=True, \
            segments=segments_for_parser, \
            use_local_whisper="false" \
        )

        logger.info(f"Successfully added captions. Output: {final_output_path}")
        return str(final_output_path)

    except FileNotFoundError as fnf_error: # Catch if font file is not found by add_captions_fx
        logger.error(f"Error adding captions (font possibly not found by add_captions_fx): {fnf_error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error during caption addition (Step 3): {e}", exc_info=True)
        return None


def assemble_final_video(
    orchestration_summary_path_str: str,
    transcription_path_str: str,
    final_output_dir: pathlib.Path, # Main output directory for the run (e.g. video_outputs/byd/)
    final_video_filename: str,      # Just the filename (e.g. byd_final_video.mp4)
    target_fps: int,
    target_dims: tuple[int, int]
) -> str | None:
    logger.info(f"===== STARTING FINAL VIDEO ASSEMBLY PROCESS ====")
    final_output_dir.mkdir(parents=True, exist_ok=True)

    # Define filenames for intermediate step outputs within the final_output_dir
    step1_base_filename = "_temp_step1_base_video.mp4"
    step2_fx_filename = "_temp_step2_fx_video.mp4"

    # Load scene_plans from orchestration_summary for FX step
    scene_plans_for_fx = []
    try:
        with open(orchestration_summary_path_str, 'r') as f: summary_data_main = json.load(f)
        scene_plans_for_fx = summary_data_main.get("scene_plans", [])
    except Exception as e:
        logger.error(f"Failed to load scene_plans from {orchestration_summary_path_str} for FX step: {e}")
        return None # Cannot proceed without scene plans if FX are intended

    # Load transcription_data for caption step
    transcription_data_for_captions = []
    try:
        with open(transcription_path_str, 'r') as f: transcription_data_for_captions = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load transcription data from {transcription_path_str} for caption step: {e}")
        return None # Cannot proceed without transcription for captions

    # Step 1: Assemble Base Video
    step1_output_path = assemble_video_step1_base_visuals_and_audio(
        orchestration_summary_path=orchestration_summary_path_str,
        output_dir_path=final_output_dir, # Step 1 writes its output here
        output_filename=step1_base_filename,
        transcription_path=transcription_path_str,
        target_fps=target_fps,
        target_dims=target_dims
    )
    if not step1_output_path or not pathlib.Path(step1_output_path).exists():
        logger.error(f"Step 1 (Base Video Assembly) failed or output file not found. Exiting.")
        return None

    # Step 2: Apply FX
    step2_output_path = apply_fx_to_video(
        input_video_path=step1_output_path,
        output_dir_path=final_output_dir, # Step 2 writes its output here
        output_filename=step2_fx_filename,
        scene_plans=scene_plans_for_fx,
        target_fps=target_fps,
        target_dims=target_dims
    )
    if not step2_output_path or not pathlib.Path(step2_output_path).exists():
        logger.error(f"Step 2 (FX Application) failed or output file not found. Exiting.")
        return None

    # Step 3: Add Captions (Writes to the final video path)
    final_video_full_path = final_output_dir / final_video_filename
    step3_output_path = add_captions_to_video(
        input_video_path=step2_output_path,
        output_dir_path=final_output_dir, # Actually writes to final_output_dir / final_video_filename
        output_filename=final_video_filename,
        transcription_data=transcription_data_for_captions
    )

    if not step3_output_path or not pathlib.Path(step3_output_path).exists():
        logger.error(f"Step 3 (Caption Addition) failed or final video not found. Exiting.")
        return None

    # Clean up intermediate step files (_temp_step1_base_video.mp4, _temp_step2_fx_video.mp4)
    for temp_file_path_str in [step1_output_path, step2_output_path]:
        if temp_file_path_str:
            temp_file = pathlib.Path(temp_file_path_str)
            if temp_file.exists():
                try: temp_file.unlink(); logger.info(f"Cleaned up temporary assembly file: {temp_file}")
                except Exception as e_clean: logger.warning(f"Could not delete temp file {temp_file}: {e_clean}")

    logger.info(f"===== VIDEO ASSEMBLY PROCESS COMPLETED. Final output: {step3_output_path} ====")
    return str(step3_output_path)


if __name__ == '__main__':
    # This block is for standalone testing of the assembler if needed.
    # It requires orchestration_summary_output.json and e2e_transcription_output.json
    # to exist in the `test_outputs` directory or as specified by DEFAULT_INPUT_SUMMARY/TRANSCRIPTION_PATH.

    logger.info("Running video_assembler.py directly for testing purposes.")

    # Load config to get FPS and Dims for standalone run
    cfg_main = load_assembly_config() # This is already defined at module level, but good to be explicit for __main__
    main_target_fps = cfg_main.get("video_general", {}).get("TARGET_FPS", 30)
    main_target_dims = tuple(cfg_main.get("video_general", {}).get("TARGET_DIMENSIONS", [1080, 1920]))
    if len(main_target_dims) != 2: main_target_dims = (1080, 1920)

    # Define input file paths for standalone test (these should exist)
    # Using the DEFAULT_ constants defined at the top of the file
    test_orchestration_summary = DEFAULT_INPUT_SUMMARY
    test_transcription_file = DEFAULT_TRANSCRIPTION_PATH

    # Define output for standalone test
    standalone_output_dir = PROJECT_ROOT / "video_outputs" / "assembler_standalone_test"
    standalone_output_dir.mkdir(parents=True, exist_ok=True)
    standalone_final_filename = "standalone_assembled_video.mp4"

    if not test_orchestration_summary.exists():
        logger.error(f"TESTING ABORTED: Orchestration summary not found at {test_orchestration_summary}")
        sys.exit(1)
    if not test_transcription_file.exists():
        logger.error(f"TESTING ABORTED: Transcription file not found at {test_transcription_file}")
        sys.exit(1)

    logger.info(f"Using Orchestration Summary: {test_orchestration_summary}")
    logger.info(f"Using Transcription File: {test_transcription_file}")
    logger.info(f"Outputting to: {standalone_output_dir / standalone_final_filename}")

    final_video = assemble_final_video(
        orchestration_summary_path_str=str(test_orchestration_summary),
        transcription_path_str=str(test_transcription_file),
        final_output_dir=standalone_output_dir,
        final_video_filename=standalone_final_filename,
        target_fps=main_target_fps,
        target_dims=main_target_dims
    )

    if final_video:
        logger.info(f"Standalone assembler test successful. Video at: {final_video}")
    else:
        logger.error("Standalone assembler test FAILED.")
