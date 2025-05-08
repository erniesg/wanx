import asyncio
import os
import logging
import random
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any
import uuid

# Import necessary functions from other modules
from .script_parser import parse_script
from .tts import text_to_speech
from .pexels_client import find_and_download_videos
from .freesound_client import find_and_download_music
from .heygen_client import start_avatar_video_generation
# Import S3 client functions
from .s3_client import get_s3_client, ensure_s3_bucket, upload_to_s3

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Load environment variables
load_dotenv()
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
FREESOUND_API_KEY = os.getenv("FREESOUND_API_KEY")
# Assumes NGROK_PUBLIC_URL is set in .env or environment after starting ngrok
NGROK_PUBLIC_URL = os.getenv("NGROK_PUBLIC_URL")
ELEVENLABS_VOICE_ID = "oQZyHVc6FnIvc9bYS5yl" # Default voice from tts.py
HEYGEN_JIN_VOICE_ID = "f5d52985019847c5b0501a445c66dba8" # From user example
# S3 Configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")

# Define specific avatars for HeyGen segments (can be customized)
VEST_AVATARS = {
    "default": "Jin_Vest_Front_public", # Fallback avatar
    "hook": "Jin_Vest_Front_public",
    "conflict": "Jin_Vest_Side_public",
    "body": "Jin_Vest_Sitting_Front_public",
    "conclusion": "Jin_Vest_Side_public"
}

NUM_HEYGEN_SEGMENTS = 2 # How many segments to randomly choose for HeyGen

async def run_heygen_workflow(job_id: str, script_path: str, job_data_ref: Dict, active_jobs_ref: Dict):
    """
    Orchestrates the HeyGen video generation workflow.
    Handles parsing, asset generation initiation (audio, visuals, music).
    Relies on webhooks for HeyGen video completion.
    """
    logger.info(f"[{job_id}] Starting HeyGen workflow for script: {script_path}")

    # --- Get S3 Client and Ensure Bucket --- # Added Step
    s3_client = get_s3_client()
    if not s3_client or not S3_BUCKET_NAME:
        error_msg = "S3 client could not be initialized or S3_BUCKET_NAME is not set."
        logger.error(f"[{job_id}] {error_msg} Cannot proceed with HeyGen segments requiring audio upload.")
        # We might still be able to proceed if only Pexels segments were chosen?
        # For now, let's fail early if S3 isn't configured but needed later.
        # Consider adding logic here to check if heygen_target_segments is empty.
        # If S3 is strictly required for HeyGen audio uploads, we should probably fail here.
    else:
        bucket_ok = ensure_s3_bucket(s3_client, S3_BUCKET_NAME, region=AWS_DEFAULT_REGION)
        if not bucket_ok:
            error_msg = f"Failed to ensure S3 bucket '{S3_BUCKET_NAME}' exists or is accessible."
            logger.error(f"[{job_id}] {error_msg} Cannot proceed with HeyGen segments requiring audio upload.")
            # Fail early if bucket is needed and not ready
            # job_data_ref[job_id]["status"] = "failed"
            # job_data_ref[job_id]["error"] = error_msg
            # return
            # For now, log error and proceed, upload will fail later

    # --- 1. Initialization ---
    if not NGROK_PUBLIC_URL:
        logger.error(f"[{job_id}] NGROK_PUBLIC_URL environment variable not set. Webhook will fail.")
        # Decide if we should fail the job here or proceed without webhook
        # For now, we proceed but log error
        webhook_url = "http://localhost/invalid-webhook-url" # Placeholder
    else:
        webhook_url = f"{NGROK_PUBLIC_URL.rstrip('/')}/webhooks/heygen"

    # Create initial job state entry using the passed reference
    job_data_ref[job_id] = {
        "workflow_type": "heygen",
        "job_id": job_id,
        "status": "processing",
        "error": None,
        "creation_time": datetime.now().isoformat(),
        "input_script_path": script_path,
        "parsed_script": None,
        "assets": {
            "music_path": None,
            "music_status": "pending",
            "segments": {}
        },
        "final_video_path_raw": None,
        "caption_file_path": None,
        "final_video_path_captioned": None
    }
    # Use the passed active_jobs reference
    if job_id not in active_jobs_ref: active_jobs_ref[job_id] = []
    active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Workflow initialized.")

    # --- 2. Parse Script ---
    logger.info(f"[{job_id}] Parsing script...")
    active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Parsing script...")
    parsed_script = parse_script(script_path)
    if not parsed_script:
        error_msg = "Failed to parse script."
        logger.error(f"[{job_id}] {error_msg}")
        job_data_ref[job_id]["status"] = "failed"
        job_data_ref[job_id]["error"] = error_msg
        active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Error: {error_msg}")
        return # Stop processing
    job_data_ref[job_id]["parsed_script"] = parsed_script
    active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Script parsed successfully.")

    # --- 3. Prepare Segments & Initiate Asset Generation ---
    script_segments = parsed_script.get("script_segments", {})
    segment_names = [name for name in script_segments.keys() if name != "production_notes"]

    if not segment_names:
        error_msg = "No script segments found in parsed script (excluding production_notes)."
        logger.error(f"[{job_id}] {error_msg}")
        job_data_ref[job_id]["status"] = "failed"
        job_data_ref[job_id]["error"] = error_msg
        active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Error: {error_msg}")
        return

    # Randomly choose segments for HeyGen
    # heygen_target_segments = random.sample(segment_names, min(NUM_HEYGEN_SEGMENTS, len(segment_names)))
    # Use specific segments: hook and conclusion
    heygen_target_segments = [name for name in segment_names if name in ["hook", "conclusion"]]
    # Ensure they actually exist in the script to avoid errors
    heygen_target_segments = [name for name in heygen_target_segments if name in script_segments]

    logger.info(f"[{job_id}] Segments chosen for HeyGen: {heygen_target_segments}")

    # Define base paths for assets
    current_dir = os.path.dirname(__file__)
    assets_base = os.path.join(current_dir, "..", "assets", "heygen_workflow")
    audio_output_dir = os.path.join(assets_base, "temp_audio", job_id)
    pexels_output_dir = os.path.join(assets_base, "stock_video", job_id)
    music_output_dir = os.path.join(assets_base, "music", job_id)

    # Ensure directories exist
    os.makedirs(audio_output_dir, exist_ok=True)
    os.makedirs(pexels_output_dir, exist_ok=True)
    os.makedirs(music_output_dir, exist_ok=True)

    tasks_to_await = []

    # Initiate generation for each segment
    for segment_name in segment_names:
        segment_data = script_segments[segment_name]
        voiceover_text = segment_data.get("voiceover")
        b_roll_keywords = segment_data.get("b_roll_keywords", [])

        # Initialize segment state in the passed job_data_ref
        segment_type = "heygen" if segment_name in heygen_target_segments else "pexels"
        job_data_ref[job_id]["assets"]["segments"][segment_name] = {
            "type": segment_type,
            "audio_path": None,
            "audio_status": "pending",
            "visual_status": "pending",
        }
        segment_state = job_data_ref[job_id]["assets"]["segments"][segment_name]

        if not voiceover_text:
            logger.warning(f"[{job_id}] Segment '{segment_name}' has no voiceover text. Skipping audio.")
            segment_state["audio_status"] = "skipped"
            continue # Should we handle segments without voiceover differently?

        # --- 3a. Generate Audio (ElevenLabs) ---
        logger.info(f"[{job_id}] Initiating audio generation for segment: {segment_name}")
        active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Generating audio for {segment_name}...")
        audio_filename = f"segment_{segment_name}.mp3"
        audio_full_path = os.path.join(audio_output_dir, audio_filename)
        # Note: text_to_speech is synchronous. We could run it in an executor for parallelization.
        try:
            generated_audio_path = text_to_speech(voiceover_text, audio_filename) # Uses default voice
            if generated_audio_path and os.path.exists(generated_audio_path):
                # Ensure path is absolute or relative to project root if needed
                segment_state["audio_path"] = generated_audio_path # Store the returned path
                segment_state["audio_status"] = "completed"
                logger.info(f"[{job_id}] Audio completed for {segment_name}: {generated_audio_path}")
                active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Audio completed for {segment_name}.")
            else:
                raise ValueError("text_to_speech failed or returned invalid path")
        except Exception as e:
            error_msg = f"Audio generation failed for {segment_name}: {e}"
            logger.error(f"[{job_id}] {error_msg}")
            segment_state["audio_status"] = "failed"
            segment_state["error"] = error_msg
            active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Error: {error_msg}")
            # Optionally: Mark overall job as failed or try to continue without this segment's audio?

        # --- 3b. Initiate Visuals (HeyGen or Pexels) ---
        audio_public_url = None # Initialize for HeyGen
        if segment_name in heygen_target_segments:
            # --- HeyGen ---
            segment_state["type"] = "heygen"
            segment_state["visual_status"] = "processing" # Heygen is async
            avatar_id = VEST_AVATARS.get(segment_name, VEST_AVATARS["default"])
            segment_state["heygen_avatar_id"] = avatar_id

            # Upload audio to S3 if available
            if segment_state["audio_status"] == "completed" and s3_client and S3_BUCKET_NAME:
                local_audio = segment_state["audio_path"]
                s3_key = f"{job_id}/{segment_name}/audio.mp3" # Define S3 key structure
                audio_public_url = upload_to_s3(s3_client, local_audio, S3_BUCKET_NAME, s3_key)
                if not audio_public_url:
                    logger.error(f"[{job_id}] Failed to upload audio {local_audio} to S3 for segment {segment_name}. Proceeding without custom audio.")
                    # Reset audio status or mark error? Keep HeyGen going with its TTS for now.
                else:
                    logger.info(f"[{job_id}] Audio for {segment_name} uploaded to S3: {audio_public_url}")
            elif segment_state["audio_status"] != "completed":
                logger.warning(f"[{job_id}] Audio not completed for HeyGen segment {segment_name}. HeyGen will use its own TTS or fail if audio_url was intended.")
            else: # S3 client or bucket name missing
                logger.warning(f"[{job_id}] S3 not configured. HeyGen will use its own TTS for segment {segment_name}.")

            logger.info(f"[{job_id}] Initiating HeyGen video for segment: {segment_name} (Avatar: {avatar_id})")
            active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Starting HeyGen video for {segment_name}...")
            # Note: We need audio_url for HeyGen. For now, using text input.
            # To use ElevenLabs audio: upload generated_audio_path to a public URL (e.g., S3)
            # and pass that URL as voice_audio_url instead of voice_text.
            # TODO: Implement audio upload and use voice_audio_url
            # Example (pseudo-code):
            # if segment_state["audio_status"] == "completed":
            #    audio_public_url = upload_to_s3(segment_state["audio_path"])
            # else:
            #    audio_public_url = None # Or handle error
            heygen_response = start_avatar_video_generation(
                api_key=HEYGEN_API_KEY,
                avatar_id=avatar_id,
                # Use a default background for now, could be dynamic later
                background_url="https://images.pexels.com/photos/265125/pexels-photo-265125.jpeg",
                webhook_url=webhook_url,
                callback_id=f"{job_id}__{segment_name}", # Include segment name in callback
                voice_text=voiceover_text, # Using HeyGen TTS for now
                voice_id=HEYGEN_JIN_VOICE_ID, # Specific HeyGen voice
                voice_audio_url=audio_public_url, # Pass S3 URL if available, otherwise None
                title=f"{job_id} - {segment_name}"
            )
            if heygen_response and heygen_response.get("data", {}).get("video_id"):
                segment_state["heygen_video_id"] = heygen_response["data"]["video_id"]
                logger.info(f"[{job_id}] HeyGen video started for {segment_name}. Video ID: {segment_state['heygen_video_id']}")
            else:
                error_msg = f"Failed to start HeyGen video for {segment_name}. Response: {heygen_response}"
                logger.error(f"[{job_id}] {error_msg}")
                segment_state["visual_status"] = "failed"
                segment_state["error"] = error_msg
                active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Error: {error_msg}")
        else:
            # --- Pexels ---
            segment_state["type"] = "pexels"
            if not b_roll_keywords:
                logger.warning(f"[{job_id}] Segment '{segment_name}' is Pexels type but has no keywords. Skipping visuals.")
                segment_state["visual_status"] = "skipped"
                continue

            query = " ".join(b_roll_keywords)
            segment_state["pexels_query"] = query
            logger.info(f"[{job_id}] Initiating Pexels search for segment: {segment_name} (Query: {query})")
            active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Finding Pexels video for {segment_name}...")
            # Note: find_and_download_videos is synchronous.
            try:
                # Determine how many clips are needed based on audio duration (approx 5s/clip?)
                # Requires audio to be generated first - potential dependency issue if async
                # For now, just download 1 clip.
                num_clips = 1 # TODO: Calculate based on segment_data['timing'] or audio duration
                downloaded_paths = find_and_download_videos(
                    api_key=PEXELS_API_KEY,
                    query=query,
                    count=num_clips,
                    output_dir=pexels_output_dir,
                    orientation="portrait" # Assuming vertical format
                )
                if downloaded_paths:
                    segment_state["pexels_video_paths"] = downloaded_paths
                    segment_state["visual_status"] = "completed"
                    logger.info(f"[{job_id}] Pexels videos downloaded for {segment_name}: {downloaded_paths}")
                    active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Pexels video downloaded for {segment_name}.")
                else:
                     raise ValueError("find_and_download_videos returned no paths.")
            except Exception as e:
                error_msg = f"Pexels video download failed for {segment_name}: {e}"
                logger.error(f"[{job_id}] {error_msg}")
                segment_state["visual_status"] = "failed"
                segment_state["error"] = error_msg
                active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Error: {error_msg}")

    # --- 4. Initiate Music Download ---
    music_query = parsed_script.get("production_notes", {}).get("music_vibe")
    if music_query:
        logger.info(f"[{job_id}] Initiating music search (Query: {music_query})")
        active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Searching for background music...")
        music_filename = "background_music.mp3"
        # Construct the full output path before calling
        music_full_path = os.path.join(music_output_dir, music_filename)
        job_data_ref[job_id]["assets"]["music_status"] = "processing"
        # Note: find_and_download_music is synchronous
        try:
            # Call with the full output_path
            downloaded_music_path = find_and_download_music(FREESOUND_API_KEY, music_query, music_full_path)
            if downloaded_music_path:
                job_data_ref[job_id]["assets"]["music_path"] = downloaded_music_path
                job_data_ref[job_id]["assets"]["music_status"] = "completed"
                logger.info(f"[{job_id}] Background music downloaded: {downloaded_music_path}")
                active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Background music downloaded.")
            else:
                 raise ValueError("find_and_download_music returned no path.")
        except Exception as e:
            error_msg = f"Background music download failed: {e}"
            logger.error(f"[{job_id}] {error_msg}")
            job_data_ref[job_id]["assets"]["music_status"] = "failed"
            # Fix TypeError: handle None case for error string concatenation
            current_error = job_data_ref[job_id].get("error")
            new_error_part = "Music Download Failed"
            job_data_ref[job_id]["error"] = f"{current_error} | {new_error_part}" if current_error else new_error_part
            active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Error: {error_msg}")
    else:
        logger.warning(f"[{job_id}] No music_vibe found in production_notes. Skipping background music.")
        job_data_ref[job_id]["assets"]["music_status"] = "skipped"
        active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Skipped background music (no query).")

    # --- 5. Waiting Phase ---
    # The actual waiting for HeyGen webhooks and assembly will happen
    # either here (if run_heygen_workflow becomes long-running)
    # or triggered separately based on webhook updates.
    # For now, this function initiates everything and exits.
    logger.info(f"[{job_id}] Asset generation initiated. Waiting for HeyGen webhooks (if any) and manual trigger for assembly.")
    active_jobs_ref[job_id].append(f"[{datetime.now().isoformat()}] Asset generation initiated. Waiting for completion...")
    # TODO: Implement waiting logic or separate assembly step

# Example of how to run (will be triggered by FastAPI endpoint later)
# async def main_test():
#     test_job_id = "heygen_test_123"
#     test_script = "../../public/script2.md" # Relative path adjust as needed
#     await run_heygen_workflow(test_job_id, test_script)
#     print("Workflow function finished initiation.")
#     print("Job Data:", job_data.get(test_job_id))

# if __name__ == "__main__":
#     asyncio.run(main_test())

# --- Assembly and Captioning Step --- #

# Import necessary functions from other modules for assembly
# These imports are only needed if check_job_completion and run_assembly_and_captioning are defined *here*.
# Since run_assembly_and_captioning was moved to main.py, these specific lines might not be needed here anymore.
# from .editor import assemble_heygen_video
# from .create_captions import add_bottom_captions

def check_job_completion(job_id: str, job_data_global: Dict[str, Any]) -> bool:
    """Checks if all assets for a given job ID are ready."""
    job_info = job_data_global.get(job_id)
    if not job_info or 'assets' not in job_info:
        return False

    assets = job_info.get("assets", {})
    segments = assets.get("segments", {})

    # Check music status (must be completed or skipped)
    music_status = assets.get("music_status")
    if music_status not in ["completed", "skipped", "failed"]:
        logger.debug(f"[{job_id}] Waiting for music: Status is {music_status}")
        return False # Music still pending/processing

    # Check status for all segments
    if not segments: return False # No segments defined

    for segment_name, segment_info in segments.items():
        audio_status = segment_info.get("audio_status")
        visual_status = segment_info.get("visual_status")

        # Audio must be completed or skipped (or failed if we allow partial assembly)
        if audio_status not in ["completed", "skipped", "failed"]:
            logger.debug(f"[{job_id}] Waiting for segment '{segment_name}' audio: Status is {audio_status}")
            return False

        # Visual must be completed or skipped (or failed if we allow partial assembly)
        if visual_status not in ["completed", "skipped", "failed"]:
            logger.debug(f"[{job_id}] Waiting for segment '{segment_name}' visuals: Status is {visual_status}")
            return False

    logger.info(f"[{job_id}] All assets appear to be ready for assembly.")
    return True # All segments and music are in a final state


def run_assembly_and_captioning(job_id: str, current_job_data: Dict[str, Any]):
    """
    Orchestrates the video assembly and captioning process for a completed job.
    Accepts the specific job_data dictionary to avoid global state issues.
    """
    logger.info(f"[{job_id}] Starting assembly and captioning process.")
    try:
        # Ensure necessary directories exist
        output_dir = os.path.join("backend", "assets", "heygen_workflow", "output")
        os.makedirs(output_dir, exist_ok=True)

        # --- Assembly ---
        logger.info(f"[{job_id}] Running video assembly.")
        # Call assemble_heygen_video without specifying bg_music_volume
        # so it uses the default defined in editor.py (which we will fix)
        raw_video_path = assemble_heygen_video(
            job_id=job_id,
            job_data=current_job_data, # Pass the specific job data
            final_output_dir=output_dir
            # No bg_music_volume specified here, rely on default
        )

        if not raw_video_path or not os.path.exists(raw_video_path):
            error_msg = f"Assembly failed or raw video not found for job {job_id}"
            logger.error(f"[{job_id}] {error_msg}")
            current_job_data["status"] = "assembly_failed"
            current_job_data["error"] = error_msg
            return # Stop processing if assembly failed

        current_job_data["final_video_path_raw"] = raw_video_path
        current_job_data["status"] = "assembly_complete"
        logger.info(f"[{job_id}] Raw video assembly successful: {raw_video_path}")

        # --- Captioning ---
        logger.info(f"[{job_id}] Starting captioning process for {raw_video_path}")
        try:
            captioned_video_path = add_bottom_captions(raw_video_path)
            if captioned_video_path and os.path.exists(captioned_video_path):
                current_job_data["final_video_path_captioned"] = captioned_video_path
                current_job_data["status"] = "completed"
                logger.info(f"[{job_id}] Captioning successful: {captioned_video_path}")
            else:
                raise Exception("Captioning function did not return a valid path or file not found.")
        except Exception as e:
            error_msg = f"Captioning failed for job {job_id}: {e}"
            logger.error(f"[{job_id}] {error_msg}", exc_info=True)
            current_job_data["status"] = "captioning_failed"
            current_job_data["error"] = error_msg
            # Optionally keep the raw path if captions fail?
            # If you want the workflow to still 'succeed' with the uncaptioned video:
            # current_job_data["status"] = "completed_no_captions"
            # logger.warning(f"[{job_id}] Proceeding with uncaptioned video due to captioning failure.")

    except Exception as e:
        error_msg = f"Video assembly or captioning process failed for job {job_id}: {e}"
        logger.exception(f"[{job_id}] {error_msg}") # Use logger.exception to include traceback
        current_job_data["status"] = "failed"
        current_job_data["error"] = error_msg

    logger.info(f"[{job_id}] Assembly and captioning finished. Final status: {current_job_data.get('status', 'unknown')}")

# Example of how to run (will be triggered by FastAPI endpoint later)
