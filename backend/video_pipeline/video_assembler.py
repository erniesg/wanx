import os
import json
import pathlib
import logging
import tempfile # Added for temporary audio/video files
from moviepy.editor import (
    concatenate_videoclips, AudioFileClip, VideoFileClip, VideoClip, CompositeVideoClip, ImageClip,
    concatenate_audioclips, CompositeAudioClip
)

# Project-level imports (ensure these paths are correct relative to where this script is run from)
# Assuming run from project root or PYTHONPATH is set up
from backend.video_pipeline.video_utils import (
    process_image_to_video_clip,
    process_video_clip,
    TIKTOK_DIMS,
    DEFAULT_FPS
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT_SUMMARY = PROJECT_ROOT / "test_outputs" / "orchestration_summary_updated_by_assembler_test.json"
# Fallback if the assembler test hasn't created the "updated" one
if not DEFAULT_INPUT_SUMMARY.exists():
    DEFAULT_INPUT_SUMMARY = PROJECT_ROOT / "test_outputs" / "orchestration_summary_output.json"

# Path to the transcription file - needed for precise end-of-speech timing
DEFAULT_TRANSCRIPTION_PATH = PROJECT_ROOT / "test_outputs" / "e2e_transcription_output.json"

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "test_outputs" / "final_video_assembly"
DEFAULT_OUTPUT_FILENAME = "assembled_video_step1.mp4"
TEMP_ASSEMBLY_DIR = PROJECT_ROOT / "test_outputs" / "temp_assembly_files" # For inspectable temp files
TEMP_ASSEMBLY_DIR.mkdir(parents=True, exist_ok=True) # Ensure it exists

TIKTOK_ASPECT_RATIO = TIKTOK_DIMS[0] / TIKTOK_DIMS[1]
DEFAULT_TARGET_FPS_ASSEMBLY = 24 # Consistent FPS for assembly output

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
        processed_clip = process_image_to_video_clip(asset_path_str, scene_duration, TIKTOK_DIMS, fps=DEFAULT_TARGET_FPS_ASSEMBLY)
    elif visual_type in ["STOCK_VIDEO", "AVATAR"]:
        asset_path_str = target_scene.get("video_asset_path") or target_scene.get("avatar_video_path")
        processed_clip = process_video_clip(asset_path_str, scene_duration, TIKTOK_DIMS, target_fps=DEFAULT_TARGET_FPS_ASSEMBLY)
    else:
        logger.error(f"Unknown visual type for scene {scene_id_to_debug}")
        return

    if processed_clip:
        debug_output_dir = PROJECT_ROOT / "test_outputs" / "debug_single_scene"
        debug_output_dir.mkdir(parents=True, exist_ok=True)
        debug_output_path = debug_output_dir / f"debugged_{scene_id_to_debug}_{pathlib.Path(asset_path_str).name}"
        logger.info(f"Writing debug clip for scene {scene_id_to_debug} to: {debug_output_path}")
        try:
            processed_clip.write_videofile(str(debug_output_path), codec="libx264", audio_codec="aac", fps=processed_clip.fps or DEFAULT_TARGET_FPS_ASSEMBLY, logger=None) # Changed logger
            logger.info(f"Debug clip saved: {debug_output_path}. Please check if it plays correctly.")
        except Exception as e:
            logger.error(f"Error writing debug clip for scene {scene_id_to_debug}: {e}")
        finally:
            if hasattr(processed_clip, 'close'): processed_clip.close()
    else:
        logger.error(f"Failed to process debug scene {scene_id_to_debug} from asset {asset_path_str}")

def assemble_video_step1(
    orchestration_summary_path: str = str(DEFAULT_INPUT_SUMMARY),
    output_dir: str = str(DEFAULT_OUTPUT_DIR),
    output_filename: str = DEFAULT_OUTPUT_FILENAME,
    transcription_path: str = str(DEFAULT_TRANSCRIPTION_PATH)
):
    """
    Assembles the main video track from scene assets and master voiceover.
    Three-step process:
    1A: Create final audio track (VO + BG music) and write to temp audio file.
    1B: Create final silent visual track (concatenated scenes) and write to temp video file.
    1C: Combine temp audio and video files into final output.
    """
    logger.info(f"Starting video assembly (3-step) using summary: {orchestration_summary_path}")
    output_dir_path = pathlib.Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    final_output_path = output_dir_path / output_filename

    if not pathlib.Path(orchestration_summary_path).exists():
        logger.error(f"Orchestration summary file not found: {orchestration_summary_path}")
        return
    if not pathlib.Path(transcription_path).exists():
        logger.error(f"Transcription file not found: {transcription_path}. Needed for precise speech end time.")
        return

    try:
        with open(orchestration_summary_path, 'r') as f:
            summary_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load or parse orchestration summary {orchestration_summary_path}: {e}")
        return

    try:
        with open(transcription_path, 'r') as f:
            transcription_data = json.load(f)
        if not transcription_data:
            logger.error("Transcription data is empty.")
            return
        max_transcription_time = transcription_data[-1]['end']
        logger.info(f"Determined max_transcription_time (end of last word): {max_transcription_time:.2f}s")
    except Exception as e:
        logger.error(f"Failed to load or parse transcription data from {transcription_path}: {e}")
        return

    scene_plans = []
    master_vo_path_str = None
    background_music_path_str = None

    if isinstance(summary_data, dict):
        scene_plans = summary_data.get("scene_plans", [])
        master_vo_path_str = summary_data.get("master_vo_path")
        background_music_path_str = summary_data.get("background_music_path")
    elif isinstance(summary_data, list):
        logger.warning("Orchestration summary is a list (older format). Master VO path might be missing.")
        scene_plans = summary_data
        potential_vo_path = PROJECT_ROOT / "test_outputs" / "How_Tencent_Bought_Its_Way_Into_AI_s_Top_8_master_vo.mp3"
        if potential_vo_path.exists():
            master_vo_path_str = str(potential_vo_path)
            logger.info(f"Using fallback master VO path: {master_vo_path_str}")
        else:
            logger.error("Master VO path could not be determined from list-formatted summary and fallback not found.")
            return
    else:
        logger.error(f"Unknown format for orchestration summary at {orchestration_summary_path}")
        return

    if not scene_plans:
        logger.error("No scene plans found in the summary. Cannot assemble video.")
        return
    if not master_vo_path_str or not pathlib.Path(master_vo_path_str).exists():
        logger.error(f"Master voiceover file not found at '{master_vo_path_str}'. Cannot assemble video.")
        return

    # --- Define temporary file paths using TEMP_ASSEMBLY_DIR ---
    temp_dir = TEMP_ASSEMBLY_DIR # Use the persistent temp directory
    # temp_dir path object already created and ensured to exist at the start of the script
    vo_filename_stem = pathlib.Path(master_vo_path_str).stem
    temp_final_audio_path = temp_dir / f"temp_final_audio_{vo_filename_stem}.mp3"
    temp_final_visual_path = temp_dir / f"temp_final_visual_{vo_filename_stem}.mp4"
    logger.info(f"Temporary audio will be stored as: {temp_final_audio_path}")
    logger.info(f"Temporary visuals will be stored as: {temp_final_visual_path}")

    if not background_music_path_str or not pathlib.Path(background_music_path_str).exists():
        fallback_bg_music_path = PROJECT_ROOT / "test_outputs" / "background_music.mp3"
        if fallback_bg_music_path.exists():
            logger.warning(f"Background music path not found or invalid in summary. Using fallback: {fallback_bg_music_path}")
            background_music_path_str = str(fallback_bg_music_path)
        elif background_music_path_str:
             logger.warning(f"Background music path '{background_music_path_str}' from summary is invalid and fallback {fallback_bg_music_path} also not found.")
        else:
             logger.info(f"No background music path in summary and fallback {fallback_bg_music_path} not found. Proceeding without background music.")

    source_clips_for_visual_track = []
    last_scene_planned_end_time = 0.0

    for i, scene in enumerate(scene_plans):
        logger.info(f"Processing scene {scene.get('scene_id', i+1)}: Type {scene.get('visual_type')}")
        planned_scene_start_time = scene.get("start_time")
        planned_scene_end_time = scene.get("end_time")

        if planned_scene_start_time is None or planned_scene_end_time is None:
            logger.warning(f"Scene {scene.get('scene_id', i+1)} is missing start_time or end_time. Skipping.")
            continue

        current_scene_original_planned_duration = planned_scene_end_time - planned_scene_start_time
        last_scene_planned_end_time = planned_scene_end_time

        if current_scene_original_planned_duration <= 0:
            logger.warning(f"Scene {scene.get('scene_id', i+1)} has non-positive original planned duration ({current_scene_original_planned_duration:.2f}s). Skipping.")
            continue

        duration_for_this_clip_processing = current_scene_original_planned_duration

        if i < len(scene_plans) - 1:
            next_scene = scene_plans[i+1]
            next_scene_planned_start_time = next_scene.get("start_time")
            if next_scene_planned_start_time is not None:
                gap_after_current_to_next_start = next_scene_planned_start_time - planned_scene_end_time
                if gap_after_current_to_next_start > 0.01:
                    logger.info(f"  Gap of {gap_after_current_to_next_start:.2f}s detected. Extending current scene {scene.get('scene_id', i+1)}'s visual.")
                    duration_for_this_clip_processing += gap_after_current_to_next_start

        asset_path_str = None
        visual_type = scene.get("visual_type")

        if visual_type == "AVATAR": asset_path_str = scene.get("avatar_video_path")
        elif visual_type == "STOCK_VIDEO": asset_path_str = scene.get("video_asset_path")
        elif visual_type == "STOCK_IMAGE": asset_path_str = scene.get("image_asset_path")
        else:
            logger.warning(f"Unknown visual_type '{visual_type}' for scene {scene.get('scene_id', i+1)}. Skipping.")
            continue

        if not asset_path_str or not pathlib.Path(asset_path_str).exists():
            logger.error(f"Asset path for scene {scene.get('scene_id', i+1)} not found or invalid: '{asset_path_str}'. Skipping scene.")
            continue

        processed_clip = None
        if visual_type == "STOCK_IMAGE":
            processed_clip = process_image_to_video_clip(asset_path_str, duration_for_this_clip_processing, TIKTOK_DIMS, fps=DEFAULT_TARGET_FPS_ASSEMBLY)
        else: # AVATAR or STOCK_VIDEO
            processed_clip = process_video_clip(asset_path_str, duration_for_this_clip_processing, TIKTOK_DIMS, target_fps=DEFAULT_TARGET_FPS_ASSEMBLY)

        if processed_clip:
            if processed_clip.duration is None or processed_clip.duration < 0.01:
                logger.warning(f"  Scene {scene.get('scene_id', i+1)} processed into a clip with near-zero or None duration ({processed_clip.duration}). Skipping append.")
                if hasattr(processed_clip, 'close'): processed_clip.close()
                continue

            processed_clip = processed_clip.set_audio(None) # Ensure all visual segments are silent before concat
            source_clips_for_visual_track.append(processed_clip)
            clip_fps = processed_clip.fps if hasattr(processed_clip, 'fps') and processed_clip.fps else DEFAULT_TARGET_FPS_ASSEMBLY
            num_frames = int(processed_clip.duration * clip_fps) if processed_clip.duration else 0
            logger.info(f"  Successfully processed scene {scene.get('scene_id', i+1)}. Effective duration: {duration_for_this_clip_processing:.2f}s. Actual clip duration: {processed_clip.duration:.2f}s, FPS: {clip_fps}, Frames: {num_frames}")
        else:
            logger.error(f"Failed to process asset for scene {scene.get('scene_id', i+1)} from path {asset_path_str}. Skipping scene.")

    if not source_clips_for_visual_track:
        logger.error("No scenes were successfully processed. Cannot create video.")
        return

    total_calculated_duration_pre_trailing_fill = sum(clip.duration for clip in source_clips_for_visual_track if clip and clip.duration is not None)
    logger.info(f"Total duration of visuals after inter-scene gap filling (before trailing speech fill): {total_calculated_duration_pre_trailing_fill:.2f}s")

    current_visual_timeline_end = total_calculated_duration_pre_trailing_fill

    if current_visual_timeline_end < max_transcription_time:
        trailing_speech_to_cover = max_transcription_time - current_visual_timeline_end
        if trailing_speech_to_cover > 0.01 and source_clips_for_visual_track:
            logger.info(f"  Visuals end at {current_visual_timeline_end:.2f}s, but transcription continues until {max_transcription_time:.2f}s. Extending last clip by {trailing_speech_to_cover:.2f}s.")
            last_visual_clip = source_clips_for_visual_track[-1]
            new_duration_for_last_clip = (last_visual_clip.duration or 0) + trailing_speech_to_cover
            try:
                extended_last_clip = last_visual_clip.set_duration(new_duration_for_last_clip)
                if extended_last_clip.duration is None or extended_last_clip.duration < 0.01:
                     logger.warning(f"Extending last clip resulted in zero or None duration.")
                else:
                    source_clips_for_visual_track[-1] = extended_last_clip
                    logger.info(f"  Last clip extended. New total visual duration: {sum(c.duration for c in source_clips_for_visual_track if c and c.duration is not None):.2f}s")
            except Exception as e:
                logger.error(f"  Error extending last visual clip: {e}. Proceeding with unextended clip.")

    final_visual_track = None
    try:
        logger.info(f"Concatenating {len(source_clips_for_visual_track)} processed scene clips.")
        final_visual_track = concatenate_videoclips(source_clips_for_visual_track, method="compose")
        if not final_visual_track:
            logger.error("concatenate_videoclips returned None. Cleaning up source clips and exiting.")
            for clip in source_clips_for_visual_track:
                if hasattr(clip, 'close'): clip.close()
            return
        if final_visual_track.fps is None:
            final_visual_track = final_visual_track.set_fps(DEFAULT_TARGET_FPS_ASSEMBLY)
        elif final_visual_track.fps != DEFAULT_TARGET_FPS_ASSEMBLY:
            final_visual_track = final_visual_track.set_fps(DEFAULT_TARGET_FPS_ASSEMBLY)
        logger.info(f"Visual track concatenated. Duration: {final_visual_track.duration:.2f}s, FPS: {final_visual_track.fps}, Total Frames: {int(final_visual_track.duration * final_visual_track.fps)}")
    except Exception as e:
        logger.error(f"Error during concatenation of video clips: {e}")
        for clip in source_clips_for_visual_track:
            if hasattr(clip, 'close'): clip.close()
        return

    master_audio_clip = None
    bg_music_clip_original = None
    final_audio_for_file_write = None
    actual_final_audio_duration = 0
    bg_music_final_processed_clip = None # To help with closing

    try:
        logger.info(f"--- STEP 1A: Preparing Final Audio Track ---")
        logger.info(f"Loading master voiceover from: {master_vo_path_str}")
        master_audio_clip = AudioFileClip(master_vo_path_str)
        final_audio_for_file_write = master_audio_clip

        if background_music_path_str and pathlib.Path(background_music_path_str).exists():
            logger.info(f"Processing background music from: {background_music_path_str}")
            bg_music_clip_original = AudioFileClip(background_music_path_str)
            bg_music_volume = 0.08
            bg_fade_duration = 1.5
            target_audio_duration = master_audio_clip.duration

            bg_music_adjusted_duration_clip = None
            if bg_music_clip_original.duration < target_audio_duration:
                num_loops = int(target_audio_duration / bg_music_clip_original.duration) + 1
                # Need to handle the intermediate concatenate_audioclips for closing
                temp_looped_bg_list = [bg_music_clip_original] * num_loops
                bg_music_looped_intermediate = concatenate_audioclips(temp_looped_bg_list)
                bg_music_adjusted_duration_clip = bg_music_looped_intermediate.set_duration(target_audio_duration)
                # bg_music_looped_intermediate should be closed if concatenate_audioclips creates a new resource not managed by bg_music_adjusted_duration_clip
                # However, MoviePy often reuses or manages internally. For safety, we can try closing.
            else:
                bg_music_adjusted_duration_clip = bg_music_clip_original.set_duration(target_audio_duration)

            if bg_music_adjusted_duration_clip:
                bg_music_final_processed_clip = (
                    bg_music_adjusted_duration_clip
                    .volumex(bg_music_volume)
                    .audio_fadein(bg_fade_duration)
                    .audio_fadeout(bg_fade_duration)
                )
                final_audio_for_file_write = CompositeAudioClip([master_audio_clip, bg_music_final_processed_clip])
                logger.info(f"Master VO composited with BG music. Resulting audio duration: {final_audio_for_file_write.duration:.2f}s")
            else: # Should not happen if bg_music_clip_original was valid
                logger.error("Background music clip (bg_music_adjusted_duration_clip) is None. Using master VO only.")

        if final_audio_for_file_write:
            actual_final_audio_duration = final_audio_for_file_write.duration
            audio_fps = 44100 # Common audio sampling rate
            total_audio_samples = int(actual_final_audio_duration * audio_fps)
            logger.info(f"Writing final audio track to temporary file: {temp_final_audio_path} (Duration: {actual_final_audio_duration:.2f}s, Sampling Rate: {audio_fps}Hz, Total Samples: {total_audio_samples})")
            final_audio_for_file_write.write_audiofile(str(temp_final_audio_path), fps=audio_fps, logger=None) # Changed logger
            logger.info(f"Final audio track successfully written to {temp_final_audio_path}")
        else:
            logger.error("Final audio track (final_audio_for_file_write) is None. Cannot proceed.")
            # Fall through to finally for cleanup
            return
    except Exception as e:
        logger.error(f"Error preparing or writing final audio track: {e}")
        return
    finally:
        logger.debug("Cleaning up audio clips used for temp audio file generation.")
        if master_audio_clip and hasattr(master_audio_clip, 'close'): master_audio_clip.close()
        if bg_music_clip_original and hasattr(bg_music_clip_original, 'close'): bg_music_clip_original.close()
        # Close intermediates created during BG music processing
        if 'bg_music_looped_intermediate' in locals() and hasattr(bg_music_looped_intermediate, 'close'):
             bg_music_looped_intermediate.close()
        if 'bg_music_adjusted_duration_clip' in locals() and hasattr(bg_music_adjusted_duration_clip, 'close') and bg_music_adjusted_duration_clip != bg_music_clip_original:
             bg_music_adjusted_duration_clip.close()
        if bg_music_final_processed_clip and hasattr(bg_music_final_processed_clip, 'close'):
             bg_music_final_processed_clip.close()
        # final_audio_for_file_write is a CompositeAudioClip, it doesn't have a .close itself usually,
        # its sources are what need closing.
        # if final_audio_for_file_write and hasattr(final_audio_for_file_write, 'close') and final_audio_for_file_write != master_audio_clip:
        #     final_audio_for_file_write.close()


    final_visual_track_silent = None # Define for finally block
    try:
        logger.info(f"--- STEP 1B: Preparing Final Silent Visual Track ---")
        if not final_visual_track:
            logger.error("Final visual track is None before silent visual track prep. This should not happen.")
            for clip in source_clips_for_visual_track: # Ensure these are closed if final_visual_track failed
                if hasattr(clip, 'close'): clip.close()
            return

        target_visual_duration = actual_final_audio_duration
        logger.info(f"Visual track current duration: {final_visual_track.duration:.2f}s. Target duration (from audio): {target_visual_duration:.2f}s")

        if abs(final_visual_track.duration - target_visual_duration) > 0.01:
            logger.info(f"Adjusting final visual track duration to match audio duration ({target_visual_duration:.2f}s)")
            final_visual_track = final_visual_track.set_duration(target_visual_duration)
            logger.info(f"Visual track after duration sync: {final_visual_track.duration:.2f}s")

        final_visual_track_silent = final_visual_track.without_audio()

        output_fps = final_visual_track_silent.fps or DEFAULT_TARGET_FPS_ASSEMBLY
        total_video_frames = int(final_visual_track_silent.duration * output_fps)

        logger.info(f"Writing final SILENT visual track to temporary file: {temp_final_visual_path} (Duration: {final_visual_track_silent.duration:.2f}s, FPS: {output_fps}, Total Frames: {total_video_frames})")
        final_visual_track_silent.write_videofile(
            str(temp_final_visual_path),
            codec="libx264",
            audio=False,
            fps=output_fps, # Use the possibly adjusted FPS
            logger=None # Changed logger
        )
        logger.info(f"Final SILENT visual track successfully written to {temp_final_visual_path}")
    except Exception as e:
        logger.error(f"Error writing final silent visual track: {e}")
        return
    finally:
        logger.debug("Cleaning up visual clips used for temp silent video file generation.")
        if final_visual_track and hasattr(final_visual_track, 'close'): final_visual_track.close()
        if final_visual_track_silent and hasattr(final_visual_track_silent, 'close') and final_visual_track_silent != final_visual_track:
            final_visual_track_silent.close()
        logger.info("Cleaning up individual source scene clips after temp visual track written.")
        for clip_idx, clip in enumerate(source_clips_for_visual_track):
            if hasattr(clip, 'close'):
                try:
                    clip.close()
                    logger.debug(f"Closed source scene clip {clip_idx}: {getattr(clip, 'filename', 'ImageClip/EffectClip')}")
                except Exception as e_close:
                    logger.warning(f"Error closing source scene clip {clip_idx}: {e_close}")
        source_clips_for_visual_track = []

    final_video_loaded = None
    final_audio_loaded = None
    video_with_combined_audio = None
    try:
        logger.info(f"--- STEP 1C: Combining Final Audio and Visual Tracks ---")
        if not pathlib.Path(temp_final_visual_path).exists():
            logger.error(f"Temporary visual file not found: {temp_final_visual_path}. Cannot combine.")
            return
        if not pathlib.Path(temp_final_audio_path).exists():
            logger.error(f"Temporary audio file not found: {temp_final_audio_path}. Cannot combine.")
            return

        logger.info(f"Loading temporary visual track from: {temp_final_visual_path}")
        final_video_loaded = VideoFileClip(str(temp_final_visual_path))
        logger.info(f"  Loaded temp visual: Duration {final_video_loaded.duration:.2f}s, FPS {final_video_loaded.fps}, Frames {int(final_video_loaded.duration * (final_video_loaded.fps or DEFAULT_TARGET_FPS_ASSEMBLY))}")

        logger.info(f"Loading temporary audio track from: {temp_final_audio_path}")
        final_audio_loaded = AudioFileClip(str(temp_final_audio_path))
        logger.info(f"  Loaded temp audio: Duration {final_audio_loaded.duration:.2f}s")

        if not final_video_loaded or not final_audio_loaded:
            logger.error("Failed to load temporary video or audio file. Cannot combine.")
            # Resources will be closed in finally block
            return

        logger.info(f"Combining audio and video. Initial video duration: {final_video_loaded.duration:.2f}s, Audio duration: {final_audio_loaded.duration:.2f}s")
        video_with_audio_intermediate = final_video_loaded.set_audio(final_audio_loaded)

        if not video_with_audio_intermediate:
            logger.error("Failed to set audio on video_loaded. Cannot proceed.")
            return # Resources will be closed in finally

        # Explicitly set the duration of the combined clip to the audio's duration.
        # This is the critical step to ensure audio is the source of truth for length.
        logger.info(f"Ensuring final clip duration matches audio duration ({final_audio_loaded.duration:.2f}s). Clip current duration: {video_with_audio_intermediate.duration:.2f}s")
        video_ready_for_render = video_with_audio_intermediate.set_duration(final_audio_loaded.duration)

        # Ensure FPS is set for the final render
        output_fps_final = video_ready_for_render.fps if hasattr(video_ready_for_render, 'fps') and video_ready_for_render.fps else DEFAULT_TARGET_FPS_ASSEMBLY
        if not hasattr(video_ready_for_render, 'fps') or video_ready_for_render.fps != output_fps_final:
            logger.info(f"Setting/standardizing FPS of final render clip to {output_fps_final}fps.")
            video_ready_for_render = video_ready_for_render.set_fps(output_fps_final)

        if not video_ready_for_render:
            logger.error("Failed to set duration or FPS on the combined video. Cannot write final output.")
            return # Resources will be closed in finally

        total_frames_final = int(video_ready_for_render.duration * output_fps_final)
        logger.info(f"Writing final combined video to: {final_output_path} (Final Duration: {video_ready_for_render.duration:.2f}s (set to audio's), FPS: {output_fps_final}, Total Frames: {total_frames_final})")

        video_ready_for_render.write_videofile(
            str(final_output_path),
            codec="libx264",
            audio_codec="aac",
            fps=output_fps_final,
            logger=None
        )
        logger.info(f"Successfully assembled video (Step 1 - Combined) saved to: {final_output_path}")

    except Exception as e:
        logger.error(f"Error combining final audio and video or writing final output: {e}", exc_info=True)
    finally:
        logger.debug("Cleaning up clips from final combination step.")
        if final_video_loaded and hasattr(final_video_loaded, 'close'): final_video_loaded.close()
        if final_audio_loaded and hasattr(final_audio_loaded, 'close'): final_audio_loaded.close()

        # Close intermediate composite clip if it exists and is different from final_video_loaded
        if 'video_with_audio_intermediate' in locals() and video_with_audio_intermediate and hasattr(video_with_audio_intermediate, 'close') and video_with_audio_intermediate != final_video_loaded:
            video_with_audio_intermediate.close()
            logger.debug("Closed video_with_audio_intermediate.")

        # Close the final clip that was rendered if it exists and is different from previously closed clips
        if 'video_ready_for_render' in locals() and video_ready_for_render and hasattr(video_ready_for_render, 'close') and \
           video_ready_for_render != final_video_loaded and \
           (not 'video_with_audio_intermediate' in locals() or video_ready_for_render != video_with_audio_intermediate):
            video_ready_for_render.close()
            logger.debug("Closed video_ready_for_render.")

        # DO NOT delete temp_final_audio_path and temp_final_visual_path for inspection
        logger.info(f"Temporary audio file kept for inspection: {temp_final_audio_path}")
        logger.info(f"Temporary visual file kept for inspection: {temp_final_visual_path}")

        # # Attempt to remove the temporary directory if it's empty (other than our specific files)
        # try:
        #     # Check if temp_dir only contains our two kept files or is empty
        #     items_in_temp_dir = list(temp_dir.iterdir())
        #     if len(items_in_temp_dir) <= 2: # Or just check if it's empty if we move them
        #          # For now, let's not remove the directory itself to avoid complexity if other temp files are there.
        #          # If we want to be stricter, we'd list contents and only remove if empty *after* moving our files, or if only our files exist.
        #          pass
        # except Exception as e_clean_dir:
        #     logger.warning(f"Error during final cleanup of temporary directory (or check): {e_clean_dir}")


if __name__ == '__main__':
    input_summary_for_run = DEFAULT_INPUT_SUMMARY
    transcription_file_for_run = DEFAULT_TRANSCRIPTION_PATH
    if not input_summary_for_run.exists():
        logger.warning(f"Input summary {input_summary_for_run} not found. Attempting fallback...")
        input_summary_for_run = PROJECT_ROOT / "test_outputs" / "orchestration_summary_output.json"
        if not input_summary_for_run.exists():
            logger.error(f"Fallback input summary {input_summary_for_run} also not found. Please generate it first.")
            exit(1)
        else:
            logger.info(f"Using fallback input summary: {input_summary_for_run}")
    else:
        logger.info(f"Using input summary: {input_summary_for_run}")

    if not transcription_file_for_run.exists():
        logger.error(f"Transcription file {transcription_file_for_run} not found. Cannot proceed with gap filling that relies on transcription end time.")
        exit(1)
    else:
        logger.info(f"Using transcription file: {transcription_file_for_run}")

    assemble_video_step1(
        orchestration_summary_path=str(input_summary_for_run),
        transcription_path=str(transcription_file_for_run)
    )
