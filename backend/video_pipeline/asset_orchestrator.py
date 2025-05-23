import os
import json
import logging
import pathlib
import uuid
import random
import time # Added for polling
from dotenv import load_dotenv
import requests # Added for downloading rendered video

# Project-level imports
from backend.text_to_video.freesound_client import find_and_download_music
from backend.video_pipeline.audio_utils import slice_audio # Assuming this will be created
from backend.text_to_video.s3_client import get_s3_client, ensure_s3_bucket, upload_to_s3
from backend.text_to_video.argil_client import (
    create_argil_video_job,
    render_argil_video,
    get_argil_video_details, # Added for polling
    DEFAULT_AVATAR_ID as DEFAULT_ARGIL_AVATAR_ID,
    DEFAULT_VOICE_ID as DEFAULT_ARGIL_VOICE_ID,
    DEFAULT_GESTURE_SLUGS
)
from backend.text_to_video.pexels_client import find_and_download_videos as find_pexels_videos, find_and_download_photos as find_pexels_photos
# Import Pixabay client and its search parameter models
from backend.text_to_video.pixabay_client import (
    find_and_download_pixabay_videos,
    find_and_download_pixabay_images,
    # PixabayImageSearchParams, # Not strictly needed here if passing kwargs directly
    # PixabayVideoSearchParams  # Not strictly needed here if passing kwargs directly
)

# Configure basic logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Configuration ---
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TEST_OUTPUT_DIR = PROJECT_ROOT / "test_outputs"
SCENE_PLAN_FILE = TEST_OUTPUT_DIR / "e2e_llm_scene_plan_output.json"
MASTER_VOICEOVER_FILE = TEST_OUTPUT_DIR / "How_Tencent_Bought_Its_Way_Into_AI_s_Top_8_master_vo.mp3" # Example name
ORIGINAL_SCRIPT_FILE = PROJECT_ROOT / "public" / "script.md"
ORCHESTRATION_SUMMARY_FILE = TEST_OUTPUT_DIR / "orchestration_summary_output.json"
RENDERED_AVATARS_DIR = TEST_OUTPUT_DIR / "rendered_avatars" # Added for downloaded avatars

FREESOUND_API_KEY = os.getenv("FREESOUND_API_KEY")
ARGIL_API_KEY = os.getenv("ARGIL_API_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY") # Added Pixabay API Key

# Argil Polling Configuration
ARGIL_POLLING_INTERVAL_SECONDS = 30
ARGIL_MAX_POLLING_ATTEMPTS = 20 # Max attempts (e.g., 20 * 30s = 10 minutes)
ARGIL_SUCCESS_STATUS = "DONE" # Updated from "VIDEO_GENERATION_SUCCESS" to match observed Argil API status
ARGIL_FAILURE_STATUSES = ["VIDEO_GENERATION_FAILED", "ERROR", "FAILED"] # Common failure states

# --- Helper function to download a file from URL ---
def _download_file_from_url(url: str, output_path: pathlib.Path) -> bool:
    """Downloads a file from a URL to the given output_path."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(output_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        logger.info(f"Successfully downloaded file from {url} to {output_path}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading file from {url}: {e}")
    except IOError as e:
        logger.error(f"IOError saving file to {output_path}: {e}")
    return False

# --- Argil Polling and Downloading Function ---
def poll_and_download_argil_videos(scene_plans: list, api_key: str, project_id: str) -> list:
    """
    Polls Argil for video job completion and downloads successful videos.
    Updates scene_plans in place with status and download paths.
    """
    if not api_key:
        logger.warning("ARGIL_API_KEY not provided. Skipping Argil polling and download.")
        return scene_plans

    os.makedirs(RENDERED_AVATARS_DIR, exist_ok=True)
    logger.info(f"Starting Argil polling for {len(scene_plans)} scenes. Output dir: {RENDERED_AVATARS_DIR}")

    all_jobs_finalized = True # Track if all jobs reach a final state

    for scene_plan_item in scene_plans:
        if scene_plan_item.get("visual_type") == "AVATAR" and "argil_video_id" in scene_plan_item:
            video_id = scene_plan_item["argil_video_id"]
            scene_id = scene_plan_item.get("scene_id", "unknown_scene")
            current_status = scene_plan_item.get("argil_render_status", "UNKNOWN")

            # Skip if already in a final success (downloaded) or hard failure state
            if current_status == ARGIL_SUCCESS_STATUS and "avatar_video_path" in scene_plan_item:
                logger.info(f"Scene {scene_id} (Argil ID: {video_id}) already processed and downloaded. Skipping poll.")
                continue
            if current_status in ARGIL_FAILURE_STATUSES or current_status == "polling_timed_out":
                logger.info(f"Scene {scene_id} (Argil ID: {video_id}) already in a final failure state: {current_status}. Skipping poll.")
                all_jobs_finalized = all_jobs_finalized and True # Still considered final
                continue

            logger.info(f"Polling for AVATAR scene {scene_id}, Argil Video ID: {video_id}, Current Status: {current_status}")
            all_jobs_finalized = False # At least one job needs polling

            for attempt in range(ARGIL_MAX_POLLING_ATTEMPTS):
                logger.debug(f"Polling attempt {attempt + 1}/{ARGIL_MAX_POLLING_ATTEMPTS} for Argil Video ID: {video_id}")
                details_response = get_argil_video_details(api_key, video_id)

                if details_response and details_response.get("success"):
                    job_data = details_response.get("data", {})
                    status = job_data.get("status") # This is Argil's internal status string for the video job
                    scene_plan_item["argil_render_status"] = status # Update with the latest status
                    logger.info(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Status: {status}")

                    if status == ARGIL_SUCCESS_STATUS: # Argil internal success status might be "DONE" or similar
                        # We need to confirm the exact field for the download URL from Argil's get_video_details response
                        # The API doc for GET /videos/{id} specifies a 'videoUrl' field directly in the response data.
                        download_url = job_data.get("videoUrl")

                        if download_url:
                            logger.info(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Succeeded. Download URL: {download_url}")
                            avatar_filename = f"{project_id}_{scene_id}_avatar.mp4"
                            avatar_output_path = RENDERED_AVATARS_DIR / avatar_filename
                            if _download_file_from_url(download_url, avatar_output_path):
                                scene_plan_item["avatar_video_path"] = str(avatar_output_path)
                                logger.info(f"Successfully downloaded rendered avatar for Scene {scene_id} to {avatar_output_path}")
                            else:
                                scene_plan_item["argil_render_status"] = "download_failed"
                                logger.error(f"Failed to download rendered avatar for Scene {scene_id} from {download_url}")
                        else:
                            scene_plan_item["argil_render_status"] = "success_no_url"
                            logger.error(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Succeeded but no download URL found in response: {job_data}")
                        all_jobs_finalized = True # This job is now final
                        break  # Exit polling loop for this scene

                    elif status in ARGIL_FAILURE_STATUSES:
                        logger.error(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Failed with status: {status}. Details: {job_data.get('error')}")
                        all_jobs_finalized = True # This job is now final
                        break  # Exit polling loop for this scene
                    else: # Still pending
                        logger.info(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Status {status} is pending. Waiting {ARGIL_POLLING_INTERVAL_SECONDS}s...")
                        time.sleep(ARGIL_POLLING_INTERVAL_SECONDS)
                else:
                    logger.warning(f"Failed to get details for Argil Video ID: {video_id} (Scene: {scene_id}) on attempt {attempt + 1}. Response: {details_response}")
                    # Decide if we should retry or give up on API error for get_details
                    if attempt == ARGIL_MAX_POLLING_ATTEMPTS - 1: # If last attempt also failed to get details
                        scene_plan_item["argil_render_status"] = "polling_details_failed"
                        all_jobs_finalized = True # Give up on this job
                    else:
                         time.sleep(ARGIL_POLLING_INTERVAL_SECONDS) # Wait before retrying get_details

            else: # Loop finished without break (i.e., max attempts reached for a pending job)
                if scene_plan_item["argil_render_status"] not in [ARGIL_SUCCESS_STATUS] + ARGIL_FAILURE_STATUSES and \
                   scene_plan_item["argil_render_status"] not in ["download_failed", "success_no_url", "polling_details_failed"]:
                    logger.warning(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Polling timed out after {ARGIL_MAX_POLLING_ATTEMPTS} attempts. Last status: {scene_plan_item.get('argil_render_status')}")
                    scene_plan_item["argil_render_status"] = "polling_timed_out"
                    all_jobs_finalized = True # This job is now final (due to timeout)
        elif scene_plan_item.get("visual_type") == "AVATAR" and "argil_video_id" not in scene_plan_item:
            logger.warning(f"AVATAR Scene {scene_plan_item.get('scene_id', 'unknown_scene')} has no argil_video_id. Skipping polling.")
            # This scene is effectively final for polling purposes as it can't be polled.

    if all_jobs_finalized:
        logger.info("Argil polling and download process complete. All pollable jobs have reached a final state or timed out.")
    else:
        logger.info("Argil polling and download process iteration complete. Some jobs may still be pending if max global timeout not reached (not implemented here).")

    return scene_plans

# --- Main Orchestration Function ---
def orchestrate_video_assets():
    logger.info("Starting video asset orchestration...")

    # --- 1. Load Inputs ---
    logger.info(f"Loading scene plan from: {SCENE_PLAN_FILE}")
    if not SCENE_PLAN_FILE.exists():
        logger.error(f"Scene plan file not found: {SCENE_PLAN_FILE}")
        return
    with open(SCENE_PLAN_FILE, 'r') as f:
        scene_plans = json.load(f)

    logger.info(f"Loading original script from: {ORIGINAL_SCRIPT_FILE}")
    if not ORIGINAL_SCRIPT_FILE.exists():
        logger.error(f"Original script file not found: {ORIGINAL_SCRIPT_FILE}")
        return
    with open(ORIGINAL_SCRIPT_FILE, 'r') as f:
        original_script_data = json.load(f)

    if not MASTER_VOICEOVER_FILE.exists():
        logger.error(f"Master voiceover file not found: {MASTER_VOICEOVER_FILE}. Please ensure E2E test ran successfully.")
        return
    logger.info(f"Master voiceover file located: {MASTER_VOICEOVER_FILE}")

    # --- Create output subdirectories for stock media ---
    stock_video_output_dir = TEST_OUTPUT_DIR / "stock_media" / "videos"
    stock_image_output_dir = TEST_OUTPUT_DIR / "stock_media" / "images"
    os.makedirs(stock_video_output_dir, exist_ok=True)
    os.makedirs(stock_image_output_dir, exist_ok=True)

    # --- 2. Fetch Background Music (Step 0 from user query) ---
    music_vibe = original_script_data.get("production_notes", {}).get("music_vibe")
    downloaded_music_path = None
    if music_vibe and FREESOUND_API_KEY:
        # If music_vibe contains commas, use only the part before the first comma
        actual_music_query = music_vibe.split(',')[0].strip()
        logger.info(f"Attempting to download background music. Original vibe: '{music_vibe}', Using query: '{actual_music_query}'")
        music_output_filename = "background_music.mp3"
        music_output_path = TEST_OUTPUT_DIR / music_output_filename
        downloaded_music_path = find_and_download_music(FREESOUND_API_KEY, actual_music_query, str(music_output_path))
        if downloaded_music_path:
            logger.info(f"Background music downloaded to: {downloaded_music_path}")
        else:
            logger.warning(f"Failed to download background music for query: {actual_music_query}")
    elif not music_vibe:
        logger.info("No music_vibe specified in script. Skipping background music.")
    elif not FREESOUND_API_KEY:
        logger.warning("FREESOUND_API_KEY not set. Skipping background music.")

    # --- Initialize S3 Client (needed for Avatar scenes) ---
    s3_client = None
    if S3_BUCKET_NAME and AWS_DEFAULT_REGION and ARGIL_API_KEY: # ARGIL_API_KEY check implies we might do Argil stuff
        logger.info("Initializing S3 client for potential uploads...")
        s3_client = get_s3_client()
        if s3_client:
            bucket_ok = ensure_s3_bucket(s3_client, S3_BUCKET_NAME, region=AWS_DEFAULT_REGION)
            if not bucket_ok:
                logger.error(f"Failed to ensure S3 bucket '{S3_BUCKET_NAME}'. Argil audio uploads will fail.")
                s3_client = None # Prevent further S3 operations if bucket is not ready
        else:
            logger.error("Failed to initialize S3 client. Argil audio uploads will not be possible.")
    elif not (S3_BUCKET_NAME and AWS_DEFAULT_REGION):
        logger.warning("S3_BUCKET_NAME or AWS_DEFAULT_REGION not configured. S3 uploads for Argil audio will be skipped.")

    # Temporary directory for sliced audio files
    temp_sliced_audio_dir = TEST_OUTPUT_DIR / "temp_scene_audio"
    os.makedirs(temp_sliced_audio_dir, exist_ok=True)

    video_project_id = f"video_project_{uuid.uuid4().hex[:8]}"
    logger.info(f"Generated Video Project ID: {video_project_id}")

    # --- 3. Process Scenes (Avatar, Stock Video, Stock Image) ---
    for scene_index, scene_plan_item in enumerate(scene_plans):
        scene_id = scene_plan_item.get("scene_id", f"scene_{scene_index:03d}")
        visual_type = scene_plan_item.get("visual_type")
        text_for_scene = scene_plan_item.get("text_for_scene")
        start_time = scene_plan_item.get("start_time")
        end_time = scene_plan_item.get("end_time")
        visual_keywords = scene_plan_item.get("visual_keywords", [])

        logger.info(f"Processing {scene_id} ({visual_type}) - Text: '{text_for_scene[:50] if text_for_scene else 'N/A'}...'")

        if visual_type == "AVATAR":
            if not ARGIL_API_KEY:
                logger.warning(f"ARGIL_API_KEY not set. Skipping AVATAR scene {scene_id}.")
                continue
            if s3_client is None:
                logger.warning(f"S3 client not available. Skipping AVATAR scene {scene_id} requiring S3 upload for audio.")
                continue
            if text_for_scene is None or start_time is None or end_time is None:
                logger.warning(f"Missing text, start_time, or end_time for AVATAR scene {scene_id}. Skipping.")
                continue

            # 3.1. Slice audio for this scene
            sliced_audio_filename = f"{video_project_id}_{scene_id}_audio.mp3"
            sliced_audio_local_path = temp_sliced_audio_dir / sliced_audio_filename

            slice_success = slice_audio(
                str(MASTER_VOICEOVER_FILE),
                str(sliced_audio_local_path),
                start_time,
                end_time
            )
            if not slice_success:
                logger.error(f"Failed to slice audio for scene {scene_id}. Skipping Argil processing for this scene.")
                continue

            # 3.2. Upload sliced audio to S3
            s3_audio_key = f"{video_project_id}/audio/{sliced_audio_filename}"
            audio_s3_url = upload_to_s3(s3_client, str(sliced_audio_local_path), S3_BUCKET_NAME, s3_audio_key)
            if not audio_s3_url:
                logger.error(f"Failed to upload sliced audio to S3 for scene {scene_id}. Skipping Argil processing.")
                continue
            scene_plan_item["audio_s3_url"] = audio_s3_url
            logger.info(f"Uploaded scene audio to S3: {audio_s3_url}")

            # 3.3. Create Argil video job with audioUrl
            argil_job_title = f"{video_project_id}_{scene_id}_Avatar"
            # For webhook tracking, if we implement it later. For now, helps identify jobs.
            argil_callback_id = f"{video_project_id}__{scene_id}"

            # Argil moments: for pre-made audio, one moment is usually sufficient.
            # The transcript in the moment can be the scene text; Argil might use it if audioUrl fails.
            selected_gesture = DEFAULT_GESTURE_SLUGS[0] if DEFAULT_GESTURE_SLUGS else "gesture-1" # Fallback if list is empty
            logger.info(f"Assigning gesture '{selected_gesture}' to Argil moment for scene {scene_id}.")

            # Construct the moment. If audio_s3_url is present, Argil prefers that and transcript becomes optional or even problematic if present.
            # voiceId should also be omitted if audioUrl is used, to prevent permission issues with Argil voices.
            moment_details = {
                "avatarId": DEFAULT_ARGIL_AVATAR_ID, # Or make configurable per scene plan
                "gestureSlug": selected_gesture
            }
            if audio_s3_url:
                moment_details["audioUrl"] = audio_s3_url
                # Do NOT add transcript if audioUrl is provided, per Argil's requirement.
                # Do NOT add voiceId if audioUrl is provided.
                if "transcript" in scene_plan_item: # Remove if present, though ideally not added
                    del scene_plan_item["transcript"]
            else:
                # This case should ideally not happen if we always generate and upload audio for AVATAR scenes.
                # If it does, we fall back to using the text_for_scene for Argil's TTS.
                moment_details["transcript"] = text_for_scene if text_for_scene else " " # Default to space if no text
                moment_details["voiceId"] = DEFAULT_ARGIL_VOICE_ID # Only add voiceId if no audioUrl

            argil_moments_payload = [moment_details]

            logger.info(f"Creating Argil video job for {scene_id} with title '{argil_job_title}' and using {'audioUrl' if audio_s3_url else 'transcript with voiceId'}.")
            creation_response = create_argil_video_job(
                api_key=ARGIL_API_KEY,
                video_title=argil_job_title,
                full_transcript=text_for_scene, # Main transcript for the job, moments override with audioUrl
                moments_payload=argil_moments_payload, # Pass the constructed moments directly
                avatar_id=DEFAULT_ARGIL_AVATAR_ID, # Default avatar for overall job if moments don't specify
                voice_id=DEFAULT_ARGIL_VOICE_ID,   # Default voice for overall job if moments don't specify
                aspect_ratio="9:16",
                callback_id=argil_callback_id
            )

            if creation_response and creation_response.get("success"):
                argil_video_id = creation_response.get("video_id")
                logger.info(f"Argil video job created for {scene_id}. Video ID: {argil_video_id}. Attempting to render.")
                scene_plan_item["argil_video_id"] = argil_video_id

                render_response = render_argil_video(ARGIL_API_KEY, argil_video_id)
                if render_response and render_response.get("success"):
                    logger.info(f"Argil video render request successful for {scene_id} (Video ID: {argil_video_id}). Status: {render_response.get('data',{}).get('status')}")
                    scene_plan_item["argil_render_status"] = render_response.get('data',{}).get('status')
                else:
                    logger.error(f"Failed to render Argil video for {scene_id} (Video ID: {argil_video_id}). Response: {render_response}")
                    scene_plan_item["argil_render_status"] = "render_failed"
            else:
                logger.error(f"Failed to create Argil video job for {scene_id}. Response: {creation_response}")
                scene_plan_item["argil_creation_status"] = "creation_failed"

            # For now, we fire and forget. Actual waiting/webhook handling is complex and for a later stage.
            logger.info(f"AVATAR scene {scene_id} processing initiated with Argil.")

        elif visual_type == "STOCK_VIDEO":
            if not visual_keywords:
                logger.warning(f"No visual keywords for STOCK_VIDEO scene {scene_id}. Skipping stock media search.")
                continue

            query = visual_keywords[0]
            downloaded_video_paths = []
            provider_choice = "pexels" # Default

            # Randomly choose between Pexels and Pixabay if both keys are available
            available_providers = []
            if PEXELS_API_KEY: available_providers.append("pexels")
            if PIXABAY_API_KEY: available_providers.append("pixabay")

            if not available_providers:
                logger.warning(f"No API key found for Pexels or Pixabay. Skipping STOCK_VIDEO scene {scene_id}.")
                continue

            provider_choice = random.choice(available_providers)
            logger.info(f"Chosen provider for STOCK_VIDEO scene {scene_id}: {provider_choice}")

            if provider_choice == "pexels":
                logger.info(f"Searching Pexels for STOCK_VIDEO for scene {scene_id} with query: '{query}'")
                downloaded_video_paths = find_pexels_videos(
                    api_key=PEXELS_API_KEY,
                    query=query,
                    count=1,
                    output_dir=str(stock_video_output_dir),
                    orientation="portrait"
                )
            elif provider_choice == "pixabay":
                logger.info(f"Searching Pixabay for STOCK_VIDEO for scene {scene_id} with query: '{query}'")
                # Pixabay client uses kwargs for search params like orientation
                downloaded_video_paths = find_and_download_pixabay_videos(
                    api_key=PIXABAY_API_KEY,
                    query=query,
                    count=1,
                    output_dir=str(stock_video_output_dir),
                    orientation="vertical" # Pixabay uses 'vertical', 'horizontal', 'all' for orientation
                )

            if downloaded_video_paths and len(downloaded_video_paths) > 0:
                logger.info(f"STOCK_VIDEO for scene {scene_id} 'downloaded' from {provider_choice}: {downloaded_video_paths[0]}")
                scene_plan_item["video_asset_path"] = str(pathlib.Path(downloaded_video_paths[0]))
                scene_plan_item["stock_media_provider"] = provider_choice
            else:
                logger.warning(f"Failed to download STOCK_VIDEO from {provider_choice} for scene {scene_id} with query '{query}'.")

        elif visual_type == "STOCK_IMAGE":
            if not visual_keywords:
                logger.warning(f"No visual keywords for STOCK_IMAGE scene {scene_id}. Skipping stock media search.")
                continue

            query = visual_keywords[0]
            downloaded_image_paths = []
            provider_choice = "pexels" # Default

            available_providers = []
            if PEXELS_API_KEY: available_providers.append("pexels")
            if PIXABAY_API_KEY: available_providers.append("pixabay")

            if not available_providers:
                logger.warning(f"No API key found for Pexels or Pixabay. Skipping STOCK_IMAGE scene {scene_id}.")
                continue

            provider_choice = random.choice(available_providers)
            logger.info(f"Chosen provider for STOCK_IMAGE scene {scene_id}: {provider_choice}")

            if provider_choice == "pexels":
                logger.info(f"Searching Pexels for STOCK_IMAGE for scene {scene_id} with query: '{query}'")
                downloaded_image_paths = find_pexels_photos(
                    api_key=PEXELS_API_KEY,
                    query=query,
                    count=1,
                    output_dir=str(stock_image_output_dir),
                    orientation="portrait"
                )
            elif provider_choice == "pixabay":
                logger.info(f"Searching Pixabay for STOCK_IMAGE for scene {scene_id} with query: '{query}'")
                # Pixabay client uses kwargs for search params like orientation
                downloaded_image_paths = find_and_download_pixabay_images(
                    api_key=PIXABAY_API_KEY,
                    query=query,
                    count=1,
                    output_dir=str(stock_image_output_dir),
                    orientation="vertical" # Pixabay uses 'vertical', 'horizontal', 'all' for orientation
                )

            if downloaded_image_paths and len(downloaded_image_paths) > 0:
                logger.info(f"STOCK_IMAGE for scene {scene_id} 'downloaded' from {provider_choice}: {downloaded_image_paths[0]}")
                scene_plan_item["image_asset_path"] = str(pathlib.Path(downloaded_image_paths[0]))
                scene_plan_item["stock_media_provider"] = provider_choice
            else:
                logger.warning(f"Failed to download STOCK_IMAGE from {provider_choice} for scene {scene_id} with query '{query}'.")

        else:
            logger.warning(f"Unknown visual_type '{visual_type}' for scene {scene_id}. Skipping.")

    logger.info("Initial asset orchestration pass completed.")

    # --- 4. Poll for Argil Video Completion and Download ---
    if ARGIL_API_KEY: # Only poll if Argil key is available
        logger.info("Proceeding to poll Argil for video completions and download.")
        scene_plans = poll_and_download_argil_videos(scene_plans, ARGIL_API_KEY, video_project_id)
    else:
        logger.info("ARGIL_API_KEY not set. Skipping Argil video polling and download phase.")

    # Prepare the comprehensive summary data
    orchestration_summary_data = {
        "video_project_id": video_project_id,
        "master_vo_path": str(MASTER_VOICEOVER_FILE) if MASTER_VOICEOVER_FILE.exists() else None,
        "background_music_path": str(downloaded_music_path) if downloaded_music_path else None,
        "scene_plans": scene_plans
    }

    # Save the updated scene_plans with new asset info (including polled status and download paths)
    try:
        with open(ORCHESTRATION_SUMMARY_FILE, 'w') as f:
            json.dump(orchestration_summary_data, f, indent=2)
        logger.info(f"Orchestration summary saved to: {ORCHESTRATION_SUMMARY_FILE}")
    except Exception as e:
        logger.error(f"Failed to save orchestration summary: {e}")


if __name__ == "__main__":
    # This allows running the orchestrator directly if the prerequisite files exist in test_outputs/
    # Ensure .env is populated with ARGIL_API_KEY, S3_BUCKET_NAME, AWS_DEFAULT_REGION, FREESOUND_API_KEY
    # Also ensure ffmpeg is installed and in PATH for audio slicing.

    # Before running, make sure these files exist from a successful E2E test run:
    # - test_outputs/e2e_llm_scene_plan_output.json
    # - test_outputs/How_Tencent_Bought_Its_Way_Into_AI_s_Top_8_master_vo.mp3 (or your actual master vo filename)
    # - public/script.md

    logger.info("Running asset_orchestrator.py directly for testing.")
    orchestrate_video_assets()
