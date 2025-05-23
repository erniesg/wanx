import os
import json
import pathlib
import logging
from moviepy.editor import (
    concatenate_videoclips, AudioFileClip, VideoClip, CompositeVideoClip, ImageClip
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
        processed_clip = process_video_clip(asset_path_str, scene_duration, TIKTOK_DIMS)
    else:
        logger.error(f"Unknown visual type for scene {scene_id_to_debug}")
        return

    if processed_clip:
        debug_output_dir = PROJECT_ROOT / "test_outputs" / "debug_single_scene"
        debug_output_dir.mkdir(parents=True, exist_ok=True)
        debug_output_path = debug_output_dir / f"debugged_{scene_id_to_debug}_{pathlib.Path(asset_path_str).name}"
        logger.info(f"Writing debug clip for scene {scene_id_to_debug} to: {debug_output_path}")
        try:
            # If it's a video, try to preserve its original audio for this debug step
            # The process_video_clip should have kept audio=True
            processed_clip.write_videofile(str(debug_output_path), codec="libx264", audio_codec="aac", fps=processed_clip.fps or DEFAULT_TARGET_FPS_ASSEMBLY, logger="bar")
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
    Step 1: Visuals + Master Voiceover.
    """
    logger.info(f"Starting video assembly (Step 1) using summary: {orchestration_summary_path}")
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

    # Extract scene_plans and master_vo_path
    scene_plans = []
    master_vo_path_str = None

    if isinstance(summary_data, dict):
        scene_plans = summary_data.get("scene_plans", [])
        master_vo_path_str = summary_data.get("master_vo_path")
        # video_project_id = summary_data.get("video_project_id", "unknown_project")
        # background_music_path_str = summary_data.get("background_music_path")
    elif isinstance(summary_data, list):
        logger.warning("Orchestration summary is a list (older format). Master VO path might be missing.")
        scene_plans = summary_data
        # Attempt to find a default master VO if not in an old list format summary
        # This is a fallback, ideally the summary contains this info.
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

    # --- 1. Process scene assets into MoviePy clips ---
    processed_scene_clips = []
    total_calculated_duration = 0.0 # This will sum the durations of processed clips

    last_scene_planned_end_time = 0.0 # To track the end of the LLM's planned content

    for i, scene in enumerate(scene_plans):
        logger.info(f"Processing scene {scene.get('scene_id', i+1)}: Type {scene.get('visual_type')}")

        planned_scene_start_time = scene.get("start_time")
        planned_scene_end_time = scene.get("end_time")

        if planned_scene_start_time is None or planned_scene_end_time is None:
            logger.warning(f"Scene {scene.get('scene_id', i+1)} is missing start_time or end_time. Skipping.")
            continue

        current_scene_original_planned_duration = planned_scene_end_time - planned_scene_start_time
        last_scene_planned_end_time = planned_scene_end_time # Keep track of the latest plan end time

        if current_scene_original_planned_duration <= 0:
            logger.warning(f"Scene {scene.get('scene_id', i+1)} has non-positive original planned duration ({current_scene_original_planned_duration:.2f}s). Skipping.")
            continue

        duration_for_this_clip_processing = current_scene_original_planned_duration

        # Inter-scene gap filling: Check for a gap *after* the current scene and *before* the next one
        if i < len(scene_plans) - 1: # If this is not the last scene
            next_scene = scene_plans[i+1]
            next_scene_planned_start_time = next_scene.get("start_time")

            if next_scene_planned_start_time is not None:
                gap_after_current_to_next_start = next_scene_planned_start_time - planned_scene_end_time
                if gap_after_current_to_next_start > 0.01: # Threshold for significant gap
                    logger.info(f"  Gap of {gap_after_current_to_next_start:.2f}s detected after scene {scene.get('scene_id', i+1)} (ends {planned_scene_end_time:.2f}s) and before next scene {next_scene.get('scene_id', i+2)} (starts {next_scene_planned_start_time:.2f}s).")
                    logger.info(f"  Extending current scene {scene.get('scene_id', i+1)}'s visual to cover this gap.")
                    duration_for_this_clip_processing += gap_after_current_to_next_start

        asset_path_str = None
        visual_type = scene.get("visual_type")
        scene_duration = duration_for_this_clip_processing

        if visual_type == "AVATAR":
            asset_path_str = scene.get("avatar_video_path")
        elif visual_type == "STOCK_VIDEO":
            asset_path_str = scene.get("video_asset_path")
        elif visual_type == "STOCK_IMAGE":
            asset_path_str = scene.get("image_asset_path")
        else:
            logger.warning(f"Unknown visual_type '{visual_type}' for scene {scene.get('scene_id', i+1)}. Skipping.")
            continue

        if not asset_path_str or not pathlib.Path(asset_path_str).exists():
            logger.error(f"Asset path for scene {scene.get('scene_id', i+1)} not found or invalid: '{asset_path_str}'. Skipping scene.")
            continue

        if visual_type == "STOCK_IMAGE":
            processed_clip = process_image_to_video_clip(asset_path_str, duration_for_this_clip_processing, TIKTOK_DIMS, fps=DEFAULT_TARGET_FPS_ASSEMBLY)
        else: # AVATAR or STOCK_VIDEO
            processed_clip = process_video_clip(asset_path_str, duration_for_this_clip_processing, TIKTOK_DIMS)

        if processed_clip:
            if processed_clip.duration is None or processed_clip.duration < 0.01:
                logger.warning(f"  Scene {scene.get('scene_id', i+1)} processed into a clip with near-zero or None duration ({processed_clip.duration}). Skipping append.")
                if hasattr(processed_clip, 'close'): processed_clip.close()
                continue

            if processed_clip.audio is None:
                 processed_clip = processed_clip.set_audio(None)

            processed_scene_clips.append(processed_clip)
            # total_calculated_duration will be summed up later from actual clip durations
            logger.info(f"  Successfully processed scene {scene.get('scene_id', i+1)}. Original planned duration: {current_scene_original_planned_duration:.2f}s. Effective duration for processing (with inter-scene gap fill): {duration_for_this_clip_processing:.2f}s. Actual clip duration: {processed_clip.duration:.2f}s")
        else:
            logger.error(f"Failed to process asset for scene {scene.get('scene_id', i+1)} from path {asset_path_str}. Skipping scene.")
            # Potentially stop assembly or try to fill with a placeholder?
            # For now, just skip.

    if not processed_scene_clips:
        logger.error("No scenes were successfully processed. Cannot create video.")
        return

    # Recalculate total_calculated_duration from the actual durations of processed clips
    total_calculated_duration = sum(clip.duration for clip in processed_scene_clips if clip and clip.duration is not None)
    logger.info(f"Total duration of visuals after inter-scene gap filling: {total_calculated_duration:.2f}s")

    # Trailing transcription gap filling:
    # Extend the last clip if the LLM plan + inter-scene gaps don't cover the full transcription.
    # last_scene_planned_end_time is the end_time of the last scene as per the LLM plan.
    # max_transcription_time is the end of the last word.
    if scene_plans: # Ensure scene_plans was not empty
        # Check if the content covered by LLM (last_scene_planned_end_time) or the sum of processed clips
        # (total_calculated_duration, which includes inter-scene gap fills)
        # is less than the actual end of speech.
        # We want visuals to at least cover up to max_transcription_time.

        current_visual_timeline_end = total_calculated_duration # This is the most reliable measure of our current visual length

        if current_visual_timeline_end < max_transcription_time:
            trailing_speech_to_cover = max_transcription_time - current_visual_timeline_end
            if trailing_speech_to_cover > 0.01 and processed_scene_clips:
                logger.info(f"  Visuals end at {current_visual_timeline_end:.2f}s, but transcription continues until {max_transcription_time:.2f}s.")
                logger.info(f"  Extending the last visual clip by {trailing_speech_to_cover:.2f}s to cover remaining transcribed speech.")

                last_visual_clip = processed_scene_clips[-1]
                new_duration_for_last_clip = (last_visual_clip.duration or 0) + trailing_speech_to_cover

                # Create a new clip with the extended duration
                # For MoviePy, set_duration usually returns a new clip or modifies self and returns self.
                # To be safe, assign the result.
                try:
                    extended_last_clip = last_visual_clip.set_duration(new_duration_for_last_clip)
                    if extended_last_clip.duration is None or extended_last_clip.duration < 0.01 :
                         logger.warning(f"Extending last clip resulted in zero or None duration. Original duration: {last_visual_clip.duration}, extension amount: {trailing_speech_to_cover}")
                    else:
                        processed_scene_clips[-1] = extended_last_clip
                        # Update total_calculated_duration
                        total_calculated_duration = sum(clip.duration for clip in processed_scene_clips if clip and clip.duration is not None)
                        logger.info(f"  Last clip extended. New total visual duration: {total_calculated_duration:.2f}s")

                except Exception as e:
                    logger.error(f"  Error extending last visual clip: {e}. Proceeding with unextended clip.")

    # --- 2. Concatenate visual clips ---
    logger.info(f"Concatenating {len(processed_scene_clips)} processed scene clips.")
    # Using method="compose" for clips that might have different FPS or require careful handling.
    # However, for simple sequential concatenation, default method (chain) is usually fine if clips are well-behaved.
    # Ensure all clips have consistent FPS or are resampled by MoviePy if needed during concat.
    # For now, assuming video_utils produces clips that can be concatenated.
    try:
        final_visual_track = concatenate_videoclips(processed_scene_clips, method="compose")
        logger.info(f"Visual track concatenated. Total duration from concatenation: {final_visual_track.duration:.2f}s. Expected based on sum of (potentially extended) clips: {total_calculated_duration:.2f}s")
        if abs(final_visual_track.duration - total_calculated_duration) > 0.1:
             logger.warning(f"  Discrepancy between concatenated track duration ({final_visual_track.duration:.2f}s) and sum of clip durations ({total_calculated_duration:.2f}s). Check for issues.")
             # Use the duration from concatenation as it's the most reliable for the final_visual_track object
             total_calculated_duration = final_visual_track.duration

    except Exception as e:
        logger.error(f"Error during concatenation of video clips: {e}")
        # Clean up clips if error occurs
        for clip in processed_scene_clips:
            if hasattr(clip, 'close'): clip.close()
        return

    # --- 3. Load master voiceover and set as audio ---
    logger.info(f"Loading master voiceover from: {master_vo_path_str}")
    master_audio_clip = AudioFileClip(master_vo_path_str)

    # Ensure audio and video durations match. The video track should be the master duration.
    # If audio is longer, it will be cut. If shorter, video will have silence at the end.
    # Ideally, total_calculated_duration from scene processing should closely match master_audio_clip.duration
    logger.info(f"Master audio duration: {master_audio_clip.duration:.2f}s. Visual track duration: {final_visual_track.duration:.2f}s")

    # Add more detailed logging about duration discrepancies
    audio_duration = master_audio_clip.duration
    visual_duration = total_calculated_duration # Use the sum of effective clip durations
    duration_discrepancy = audio_duration - visual_duration

    if duration_discrepancy > 0.01: # Using a small threshold for floating point comparisons
        logger.warning(f"VISUAL TRACK IS SHORTER than master audio by {duration_discrepancy:.2f}s.")
        logger.warning("  This will result in a black screen or frozen last frame for the remainder of the audio.")
        logger.warning("  This typically indicates that the LLM scene plan does not cover the entire duration of the transcribed speech, leaving gaps between scenes.")
        logger.warning(f"  Master Audio: {audio_duration:.2f}s | Transcription-based Visuals: {visual_duration:.2f}s (sum of scene durations from plan)")
    elif duration_discrepancy < -0.01:
        logger.warning(f"VISUAL TRACK IS LONGER than master audio by {-duration_discrepancy:.2f}s.")
        logger.warning("  The visual track will be truncated to match the master audio duration.")

    video_with_audio = final_visual_track.set_audio(master_audio_clip)
    # Crucially, set the duration of the final composite to be exactly that of the (potentially shorter) of the two.
    # Or, more robustly, the audio is master. So video is cut/extended to match audio.
    video_with_audio = video_with_audio.set_duration(master_audio_clip.duration)

    logger.info(f"Final clip duration after audio merge (set to master audio duration): {video_with_audio.duration:.2f}s")

    # --- 4. Write to output file ---
    logger.info(f"Writing assembled video (Step 1) to: {final_output_path}")
    try:
        video_with_audio.write_videofile(
            str(final_output_path),
            codec="libx264",
            audio_codec="aac",
            fps=DEFAULT_TARGET_FPS_ASSEMBLY, # Use consistent assembly FPS
            logger="bar"
        )
        logger.info(f"Successfully assembled video (Step 1) saved to: {final_output_path}")
    except Exception as e:
        logger.error(f"Error writing final video: {e}")
    finally:
        # Clean up: close all clips
        for clip in processed_scene_clips:
            if hasattr(clip, 'close'): clip.close()
        if hasattr(final_visual_track, 'close'): final_visual_track.close()
        if hasattr(master_audio_clip, 'close'): master_audio_clip.close()
        if hasattr(video_with_audio, 'close'): video_with_audio.close()

if __name__ == '__main__':
    # This allows running the assembler directly.
    # It will use the default orchestration summary file and output location.
    # Ensure that orchestrate_video_assets.py and then test_video_assembler.py (to update paths)
    # have been run to produce the necessary JSON input and assets.

    # Example to run from CLI:
    # python -m backend.video_pipeline.video_assembler

    # Check if the default input summary exists before running
    input_summary_for_run = DEFAULT_INPUT_SUMMARY
    transcription_file_for_run = DEFAULT_TRANSCRIPTION_PATH # Added this
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

    if not transcription_file_for_run.exists(): # Added this check
        logger.error(f"Transcription file {transcription_file_for_run} not found. Cannot proceed with gap filling that relies on transcription end time.")
        # Decide if to exit or run without this specific gap filling. For now, let's make it critical.
        exit(1)
    else:
        logger.info(f"Using transcription file: {transcription_file_for_run}")

    # --- To debug a single scene, uncomment the line below and comment out the main assembly call ---
    # debug_single_scene(scene_id_to_debug="002", orchestration_summary_path=str(input_summary_for_run))
    # debug_single_scene(scene_id_to_debug="003", orchestration_summary_path=str(input_summary_for_run))
    # debug_single_scene(scene_id_to_debug="010", orchestration_summary_path=str(input_summary_for_run))
    assemble_video_step1(
        orchestration_summary_path=str(input_summary_for_run),
        transcription_path=str(transcription_file_for_run) # Pass it here
    )
