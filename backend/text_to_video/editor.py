from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip
import os
import logging
import requests
import math
from moviepy.audio.fx.volumex import volumex
from moviepy.audio.AudioClip import CompositeAudioClip, concatenate_audioclips
from moviepy.video.fx.all import resize, crop

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

def combine_audio_video(audio_file, video_files, output_file="final_tiktok.mp4"):
    """
    Combine audio with multiple video clips to create a TikTok video.

    Args:
        audio_file (str): Path to the audio file
        video_files (list): List of paths to video files
        output_file (str): Path for the output video file

    Returns:
        str: Path to the final video file
    """
    try:
        # Load the audio file
        audio = AudioFileClip(audio_file)
        audio_duration = audio.duration

        # Load video clips
        video_clips = []
        for video_path in video_files:
            clip = VideoFileClip(video_path)
            video_clips.append(clip)

        # Concatenate video clips
        final_clip = concatenate_videoclips(video_clips)

        # If the combined video is shorter than the audio, loop the video
        if final_clip.duration < audio_duration:
            # Calculate how many times to loop
            loop_count = int(audio_duration / final_clip.duration) + 1
            looped_clips = []
            for _ in range(loop_count):
                looped_clips.extend(video_clips)

            final_clip = concatenate_videoclips(looped_clips)

        # Trim the video to match audio duration
        final_clip = final_clip.subclip(0, audio_duration)

        # Add the audio to the video
        final_clip = final_clip.set_audio(audio)

        # Write the result to a file
        final_clip.write_videofile(output_file, codec="libx264", audio_codec="aac")

        # Close the clips to free resources
        audio.close()
        final_clip.close()
        for clip in video_clips:
            clip.close()

        return output_file

    except Exception as e:
        print(f"Error combining audio and video: {e}")
        return None

def combine_project(project_name, audio_path=None):
    """
    Combine all assets for a project into a final video.

    Args:
        project_name (str): Name of the project
        audio_path (str, optional): Full path to the audio file

    Returns:
        str: Path to the final video
    """
    # Create necessary directories with consistent paths
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    assets_dir = os.path.join(backend_dir, "assets")
    audio_dir = os.path.join(assets_dir, "audio", "speech")
    videos_dir = os.path.join(assets_dir, "videos", project_name)
    output_dir = os.path.join(assets_dir, "output")

    os.makedirs(output_dir, exist_ok=True)

    # If audio_path is not provided, use the default location
    if not audio_path:
        audio_path = os.path.join(audio_dir, f"{project_name}.mp3")

    # Verify audio file exists
    if not os.path.exists(audio_path):
        logging.error(f"Audio file not found: {audio_path}")
        return None

    # Additional validation for audio file
    logging.info(f"Validating audio file: {audio_path}")
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(audio_path)
        logging.info(f"Audio file is valid, duration: {len(audio)/1000} seconds")
    except Exception as e:
        logging.error(f"Audio file validation failed: {str(e)}")
        # Try to create a silent audio file as fallback
        try:
            logging.info("Creating silent audio as fallback")
            from pydub import AudioSegment
            silent_audio = AudioSegment.silent(duration=30000)  # 30 seconds of silence
            silent_audio.export(audio_path, format="mp3")
            logging.info(f"Created silent audio file: {audio_path}")
        except Exception as e2:
            logging.error(f"Failed to create silent audio: {str(e2)}")
            return None

    # Get video files
    video_files = []
    for file in sorted(os.listdir(videos_dir)):
        if file.endswith(".mp4"):
            video_files.append(os.path.join(videos_dir, file))

    if not video_files:
        logging.error(f"No video files found in {videos_dir}")
        return None

    logging.info(f"Found {len(video_files)} video files to combine")
    for i, video in enumerate(video_files):
        logging.info(f"Video {i+1}: {os.path.basename(video)}")

    # Combine audio and videos
    output_file = os.path.join(output_dir, f"{project_name}_tiktok.mp4")
    return combine_audio_video(audio_path, video_files, output_file)

def download_video(url: str, output_path: str) -> bool:
    """Downloads a video from a URL to a local path."""
    try:
        logger.info(f"Downloading video from {url} to {output_path}")
        response = requests.get(url, stream=True, timeout=120) # Long timeout for video download
        response.raise_for_status()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Successfully downloaded {output_path}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download video from {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during video download: {e}")
        return False

def assemble_heygen_video(job_id: str, job_data: dict, final_output_dir: str, bg_music_volume: float = 0.15) -> str | None:
    """
    Assembles the final video for the HeyGen workflow from generated assets.
    Manually concatenates audio tracks and standardizes visual dimensions.

    Args:
        job_id (str): The ID of the job.
        job_data (dict): The job's state data containing asset paths and statuses.
        final_output_dir (str): Directory to save the final raw video.
        bg_music_volume (float): Volume factor for background music (0.0 to 1.0). Defaults to 0.15.

    Returns:
        str | None: Path to the assembled (raw, pre-caption) video, or None on failure.
    """
    logger.info(f"[{job_id}] Starting assembly for HeyGen workflow (Manual Audio Concat).")
    processed_visual_clips = [] # List for visual-only clips
    processed_audio_clips = []  # List for separate audio tracks
    output_path = None
    all_clips_to_close = [] # Keep track of clips to close

    # --- Target Dimensions --- #
    target_width = 720
    target_height = 1280
    target_size = (target_width, target_height)
    # ----------------------- #

    # --- Create temp dir for intermediate clips --- #
    temp_dir = os.path.join(final_output_dir, f"temp_segments_{job_id}")
    os.makedirs(temp_dir, exist_ok=True)
    logger.info(f"[{job_id}] Saving intermediate processed segments to: {temp_dir}")
    # -------------------------------------------- #

    try:
        parsed_script = job_data.get("parsed_script")
        assets = job_data.get("assets", {})
        segments_data = assets.get("segments", {})

        if not parsed_script or not segments_data:
            logger.error(f"[{job_id}] Missing parsed_script or segments data for assembly.")
            return None

        heygen_download_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "heygen_workflow", "heygen_downloads", job_id)
        os.makedirs(heygen_download_dir, exist_ok=True)

        ordered_segment_names = [name for name in parsed_script.get("script_segments", {}).keys() if name != "production_notes"]

        for segment_name in ordered_segment_names:
            logger.info(f"[{job_id}] Processing segment: {segment_name}")
            segment_info = segments_data.get(segment_name)
            if not segment_info:
                logger.warning(f"[{job_id}] Missing segment info for '{segment_name}'. Skipping.")
                continue

            segment_type = segment_info.get("type")
            visual_status = segment_info.get("visual_status")
            audio_path = segment_info.get("audio_path") # Get audio path for Pexels

            segment_visual_raw_clip = None # Clip holding original visuals
            segment_audio_only_clip = None # Clip holding audio for this segment

            if visual_status != "completed":
                logger.warning(f"[{job_id}] Visuals not completed for segment '{segment_name}' (status: {visual_status}). Skipping segment visual.")
                continue

            # --- Load Visuals and Prepare Audio based on Type ---
            if segment_type == "heygen":
                # Load HeyGen Video
                heygen_url = segment_info.get("heygen_video_url")
                local_heygen_path = os.path.join(heygen_download_dir, f"{segment_name}.mp4")
                # (Download logic as before)
                if os.path.exists(local_heygen_path) and os.path.getsize(local_heygen_path) > 0:
                    logger.info(f"[{job_id}] Using existing local HeyGen video: {local_heygen_path}")
                elif heygen_url:
                    logger.info(f"[{job_id}] Local HeyGen video not found for '{segment_name}'. Attempting download from URL.")
                    if not download_video(heygen_url, local_heygen_path):
                        logger.error(f"[{job_id}] Failed to download HeyGen video for '{segment_name}'. Skipping.")
                        continue
                else:
                    logger.error(f"[{job_id}] Local HeyGen video for '{segment_name}' not found and no download URL available. Skipping.")
                    continue

                try:
                    full_heygen_clip = VideoFileClip(local_heygen_path)
                    all_clips_to_close.append(full_heygen_clip)
                    segment_visual_raw_clip = full_heygen_clip # Keep original visual
                    segment_audio_only_clip = full_heygen_clip.audio # Get embedded audio
                    if segment_audio_only_clip:
                         all_clips_to_close.append(segment_audio_only_clip)
                    else:
                         logger.warning(f"[{job_id}] HeyGen clip {local_heygen_path} loaded but had no audio track.")
                    logger.info(f"[{job_id}] Loaded HeyGen clip for {segment_name} (Duration: {full_heygen_clip.duration:.2f}s)")
                except Exception as e:
                    logger.error(f"[{job_id}] Failed to load local HeyGen video {local_heygen_path}: {e}. Skipping.")
                    continue

            elif segment_type == "pexels":
                # Load Separate Audio for Pexels
                if not audio_path or not os.path.exists(audio_path):
                    logger.warning(f"[{job_id}] Audio not found or path invalid for Pexels segment '{segment_name}'. Skipping segment.")
                    continue
                try:
                    segment_audio_only_clip = AudioFileClip(audio_path)
                    all_clips_to_close.append(segment_audio_only_clip)
                    segment_duration = segment_audio_only_clip.duration
                    logger.info(f"[{job_id}] Loaded audio for Pexels segment {segment_name}, duration: {segment_duration:.2f}s")
                except Exception as e:
                    logger.error(f"[{job_id}] Failed to load audio {audio_path} for Pexels segment '{segment_name}': {e}. Skipping segment.")
                    continue

                # Load and Process Pexels Visuals
                pexels_paths = segment_info.get("pexels_video_paths")
                if not pexels_paths:
                    logger.warning(f"[{job_id}] Pexels segment '{segment_name}' completed but paths missing. Skipping.")
                    continue
                # (Loading/Looping/Trimming logic for Pexels visuals as before)
                segment_pexels_clips = []
                total_pexels_duration = 0
                for pexels_path in pexels_paths:
                    if os.path.exists(pexels_path):
                        try:
                            clip = VideoFileClip(pexels_path)
                            segment_pexels_clips.append(clip)
                            all_clips_to_close.append(clip)
                            total_pexels_duration += clip.duration
                        except Exception as e:
                            logger.warning(f"[{job_id}] Failed to load Pexels video {pexels_path}: {e}. Skipping clip.")
                    else:
                        logger.warning(f"[{job_id}] Pexels video path not found: {pexels_path}. Skipping clip.")

                if not segment_pexels_clips:
                    logger.error(f"[{job_id}] No valid Pexels clips loaded for segment '{segment_name}'. Skipping segment.")
                    continue

                temp_concat_clip = concatenate_videoclips(segment_pexels_clips)
                all_clips_to_close.append(temp_concat_clip)

                # Trim/Loop VISUALS to match AUDIO duration
                if temp_concat_clip.duration < segment_duration:
                    num_loops = math.ceil(segment_duration / temp_concat_clip.duration)
                    looped_pexel_clips = [temp_concat_clip] * num_loops
                    final_pexels_concat = concatenate_videoclips(looped_pexel_clips)
                    all_clips_to_close.append(final_pexels_concat)
                    segment_visual_raw_clip = final_pexels_concat.subclip(0, segment_duration)
                else:
                    segment_visual_raw_clip = temp_concat_clip.subclip(0, segment_duration)
                # Pexels clips often have their own audio, remove it
                segment_visual_raw_clip = segment_visual_raw_clip.without_audio()
                all_clips_to_close.append(segment_visual_raw_clip)

            else:
                logger.warning(f"[{job_id}] Unknown segment type '{segment_type}' for '{segment_name}'. Skipping.")
                continue

            # --- Standardize Visual Dimensions --- #
            segment_visual_standardized_clip = None
            if segment_visual_raw_clip:
                if segment_visual_raw_clip.size == list(target_size):
                    logger.info(f"[{job_id}] Visuals for {segment_name} already match target size {target_size}.")
                    segment_visual_standardized_clip = segment_visual_raw_clip.without_audio()
                else:
                    logger.info(f"[{job_id}] Resizing/cropping visuals for {segment_name} from {segment_visual_raw_clip.size} to {target_size}.")
                    try:
                        # Resize to target width, maintaining aspect ratio
                        resized_clip = segment_visual_raw_clip.fx(resize, width=target_width)
                        all_clips_to_close.append(resized_clip)
                        # Crop centrally to target dimensions
                        cropped_clip = resized_clip.fx(crop,
                                                       width=target_width,
                                                       height=target_height,
                                                       x_center=resized_clip.w/2,
                                                       y_center=resized_clip.h/2)
                        all_clips_to_close.append(cropped_clip)
                        segment_visual_standardized_clip = cropped_clip.without_audio()
                    except Exception as e:
                        logger.error(f"[{job_id}] Failed to resize/crop visuals for {segment_name}: {e}. Skipping segment.")
                        # Ensure we don't proceed with potentially corrupted raw clip
                        segment_visual_standardized_clip = None
                        segment_audio_only_clip = None # Also discard audio if visual fails

            # --- Save intermediate standardized visual clip --- #
            if segment_visual_standardized_clip:
                temp_clip_filename = f"temp_segment_{len(processed_visual_clips)}_visual_{segment_name}.mp4"
                temp_clip_path = os.path.join(temp_dir, temp_clip_filename)
                try:
                    logger.info(f"[{job_id}] Saving intermediate standardized visual clip to: {temp_clip_path}")
                    segment_visual_standardized_clip.write_videofile(temp_clip_path, codec="libx264", audio=False)
                    logger.info(f"[{job_id}] Successfully saved intermediate standardized visual clip: {temp_clip_path}")
                except Exception as write_err:
                    logger.error(f"[{job_id}] Failed to write intermediate standardized visual clip {temp_clip_path}: {write_err}")

                processed_visual_clips.append(segment_visual_standardized_clip) # Add standardized clip
            else:
                 logger.error(f"[{job_id}] No standardized visual clip generated for segment '{segment_name}'.")

            # --- Add audio track to list --- #
            if segment_audio_only_clip:
                # Make sure audio duration matches the final VISUAL duration for this segment
                # This is crucial if HeyGen duration slightly differs or Pexels was trimmed
                visual_duration = segment_visual_standardized_clip.duration if segment_visual_standardized_clip else 0
                if visual_duration > 0 and abs(segment_audio_only_clip.duration - visual_duration) > 0.1:
                    logger.warning(f"[{job_id}] Audio duration ({segment_audio_only_clip.duration:.2f}s) differs from standardized visual duration ({visual_duration:.2f}s) for {segment_name}. Trimming audio.")
                    segment_audio_only_clip = segment_audio_only_clip.subclip(0, visual_duration)
                    all_clips_to_close.append(segment_audio_only_clip)

                processed_audio_clips.append(segment_audio_only_clip)
                logger.info(f"[{job_id}] Added audio for segment {segment_name} to list (Duration: {segment_audio_only_clip.duration:.2f}s).")
            else:
                 logger.warning(f"[{job_id}] No audio clip available for segment {segment_name} to add to manual concat list.")

            logger.info(f"[{job_id}] Finished processing segment: {segment_name}")

        # --- MANUAL AUDIO CONCATENATION --- #
        if not processed_audio_clips:
             logger.error(f"[{job_id}] No audio clips were successfully processed for manual concatenation.")
             return None

        logger.info(f"[{job_id}] Manually concatenating {len(processed_audio_clips)} audio clips...")
        try:
            final_voice_track = concatenate_audioclips(processed_audio_clips)
            all_clips_to_close.append(final_voice_track)
            voice_duration = final_voice_track.duration
            logger.info(f"[{job_id}] Final voice track duration: {voice_duration:.2f}s")
        except Exception as e:
            logger.error(f"[{job_id}] Failed to concatenate audio clips: {e}", exc_info=True)
            return None

        # --- Add Background Music to Manual Audio Track --- #
        music_path = assets.get("music_path")
        combined_final_audio = final_voice_track # Start with voice track

        if music_path and os.path.exists(music_path):
            logger.info(f"[{job_id}] Adding background music: {music_path}")
            try:
                bg_audio_clip = AudioFileClip(music_path)
                all_clips_to_close.append(bg_audio_clip)

                # Loop or trim music to match VOICE track duration
                if bg_audio_clip.duration < voice_duration:
                    bg_audio_clip = bg_audio_clip.loop(duration=voice_duration)
                elif bg_audio_clip.duration > voice_duration:
                    bg_audio_clip = bg_audio_clip.subclip(0, voice_duration)

                logger.info(f"[{job_id}] Setting background music volume to {bg_music_volume}")
                bg_audio_clip = bg_audio_clip.fx(volumex, bg_music_volume)

                combined_final_audio = CompositeAudioClip([final_voice_track, bg_audio_clip])
                all_clips_to_close.append(combined_final_audio)
                logger.info(f"[{job_id}] Background music mixed successfully.")

            except Exception as e:
                logger.error(f"[{job_id}] Failed to load or process background music {music_path}: {e}. Using voice track only.")
                combined_final_audio = final_voice_track # Fallback to voice only
        else:
            logger.warning(f"[{job_id}] Background music path not found or not provided. Using voice track only.")


        # --- VISUAL CONCATENATION --- #
        if not processed_visual_clips:
            logger.error(f"[{job_id}] No visual clips were successfully processed for assembly.")
            return None

        logger.info(f"[{job_id}] Concatenating {len(processed_visual_clips)} visual-only clips...")
        try:
            # Concatenate the visual clips (ensure they have no audio track)
            final_visuals_only = concatenate_videoclips(processed_visual_clips, method="compose") # Try compose method
            all_clips_to_close.append(final_visuals_only)
            logger.info(f"[{job_id}] Visuals concatenated. Duration: {final_visuals_only.duration:.2f}s")
        except Exception as e:
             logger.error(f"[{job_id}] Failed to concatenate visual clips: {e}", exc_info=True)
             return None

        # --- Final Combination --- #
        logger.info(f"[{job_id}] Combining final visuals (Duration: {final_visuals_only.duration:.2f}s) and final audio (Duration: {combined_final_audio.duration:.2f}s)")
        # Set the manually created audio onto the concatenated visuals
        final_video_with_audio = final_visuals_only.set_audio(combined_final_audio)
        # Trim final video just in case durations differ slightly due to precision? Or trust audio duration?
        # Let's trust the audio duration as the master length now.
        final_video_with_audio = final_video_with_audio.set_duration(combined_final_audio.duration)
        all_clips_to_close.append(final_video_with_audio)


        # --- Write Final Raw Video --- #
        os.makedirs(final_output_dir, exist_ok=True)
        output_filename = f"{job_id}_raw.mp4"
        output_path = os.path.join(final_output_dir, output_filename)

        logger.info(f"[{job_id}] Writing final raw video to: {output_path}")
        final_video_with_audio.write_videofile(output_path, codec="libx264", audio_codec="aac")
        logger.info(f"[{job_id}] Final raw video saved successfully.")
        return output_path

    except Exception as e:
        logger.error(f"[{job_id}] Unexpected error during video assembly: {e}", exc_info=True)
        return None
    finally:
        # --- Cleanup: Close all opened clips --- #
        logger.info(f"[{job_id}] Closing {len(all_clips_to_close)} MoviePy clips.")
        for clip in all_clips_to_close:
            try:
                clip.close()
            except Exception:
                pass
        if 'final_video_with_audio' in locals() and final_video_with_audio:
             try:
                 final_video_with_audio.close()
             except Exception: pass
        logger.info(f"[{job_id}] Assembly process finished.")

# Test function (requires assets to be pre-generated by heygen_workflow)
# if __name__ == "__main__":
#     # Assuming a job 'test_job_123' has run and generated assets
#     test_job_id = "heygen_job_from_previous_run"
#     # Manually construct or load job_data for testing
#     # example_job_data = load_job_data_from_file(test_job_id) # Needs implementation
#     example_job_data = { ... } # Populate with actual paths/status
#     final_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "heygen_workflow", "output")
#     raw_video = assemble_heygen_video(test_job_id, example_job_data, final_dir)
#     if raw_video:
#         print(f"Assembly test successful: {raw_video}")
#     else:
#         print("Assembly test failed.")
