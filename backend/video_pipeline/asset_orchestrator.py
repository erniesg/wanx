import os
import json
import logging
import pathlib
import uuid
from dotenv import load_dotenv

# Project-level imports
from backend.text_to_video.freesound_client import find_and_download_music
from backend.video_pipeline.audio_utils import slice_audio # Assuming this will be created
from backend.text_to_video.s3_client import get_s3_client, ensure_s3_bucket, upload_to_s3
from backend.text_to_video.argil_client import (
    create_argil_video_job,
    render_argil_video,
    DEFAULT_AVATAR_ID as DEFAULT_ARGIL_AVATAR_ID,
    DEFAULT_VOICE_ID as DEFAULT_ARGIL_VOICE_ID,
    DEFAULT_GESTURE_SLUGS
)
from backend.text_to_video.pexels_client import find_and_download_videos, find_and_download_photos

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

FREESOUND_API_KEY = os.getenv("FREESOUND_API_KEY")
ARGIL_API_KEY = os.getenv("ARGIL_API_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

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
        logger.info(f"Attempting to download background music with vibe: {music_vibe}")
        music_output_filename = "background_music.mp3"
        music_output_path = TEST_OUTPUT_DIR / music_output_filename
        downloaded_music_path = find_and_download_music(FREESOUND_API_KEY, music_vibe, str(music_output_path))
        if downloaded_music_path:
            logger.info(f"Background music downloaded to: {downloaded_music_path}")
        else:
            logger.warning(f"Failed to download background music for vibe: {music_vibe}")
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

            argil_moments = [
                {
                    "transcript": text_for_scene,
                    "avatarId": DEFAULT_ARGIL_AVATAR_ID, # Or make configurable per scene plan
                    "voiceId": DEFAULT_ARGIL_VOICE_ID,   # This voiceId is for Argil's TTS if audioUrl is NOT used or fails.
                                                        # Since we provide audioUrl, Argil's voiceId choice here is less critical.
                    "audioUrl": audio_s3_url,
                    "gestureSlug": selected_gesture
                }
            ]

            logger.info(f"Creating Argil video job for {scene_id} with title '{argil_job_title}' and audioUrl: {audio_s3_url}")
            creation_response = create_argil_video_job(
                api_key=ARGIL_API_KEY,
                video_title=argil_job_title,
                full_transcript=text_for_scene, # Main transcript for the job, moments override with audioUrl
                moments_payload=argil_moments, # Pass the constructed moments directly
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
            if not PEXELS_API_KEY:
                logger.warning(f"PEXELS_API_KEY not set. Skipping STOCK_VIDEO scene {scene_id}.")
                continue
            if not visual_keywords:
                logger.warning(f"No visual keywords for STOCK_VIDEO scene {scene_id}. Skipping Pexels search.")
                continue

            query = visual_keywords[0]
            logger.info(f"Searching Pexels for STOCK_VIDEO for scene {scene_id} with query: '{query}'")

            downloaded_video_paths = find_and_download_videos(
                api_key=PEXELS_API_KEY,
                query=query,
                count=1,
                output_dir=str(stock_video_output_dir),
                orientation="portrait"
            )
            if downloaded_video_paths and len(downloaded_video_paths) > 0:
                logger.info(f"STOCK_VIDEO for scene {scene_id} notionally 'downloaded' from Pexels: {downloaded_video_paths[0]}")
                scene_plan_item["video_asset_path"] = str(pathlib.Path(downloaded_video_paths[0]))
            else:
                logger.warning(f"Failed to download STOCK_VIDEO from Pexels for scene {scene_id} with query '{query}'.")

        elif visual_type == "STOCK_IMAGE":
            if not PEXELS_API_KEY:
                logger.warning(f"PEXELS_API_KEY not set. Skipping STOCK_IMAGE scene {scene_id}.")
                continue
            if not visual_keywords:
                logger.warning(f"No visual keywords for STOCK_IMAGE scene {scene_id}. Skipping Pexels search.")
                continue

            query = visual_keywords[0]
            logger.info(f"Searching Pexels for STOCK_IMAGE for scene {scene_id} with query: '{query}'")

            downloaded_image_paths = find_and_download_photos(
                api_key=PEXELS_API_KEY,
                query=query,
                count=1,
                output_dir=str(stock_image_output_dir),
                orientation="portrait"
            )
            if downloaded_image_paths and len(downloaded_image_paths) > 0:
                logger.info(f"STOCK_IMAGE for scene {scene_id} notionally 'downloaded' from Pexels: {downloaded_image_paths[0]}")
                scene_plan_item["image_asset_path"] = str(pathlib.Path(downloaded_image_paths[0]))
            else:
                logger.warning(f"Failed to download STOCK_IMAGE from Pexels for scene {scene_id} with query '{query}'.")

        else:
            logger.warning(f"Unknown visual_type '{visual_type}' for scene {scene_id}. Skipping.")

    logger.info("Initial asset orchestration pass completed. Further steps (polling, assembly) would follow.")

    # Save the updated scene_plans with new asset info
    try:
        with open(ORCHESTRATION_SUMMARY_FILE, 'w') as f:
            json.dump(scene_plans, f, indent=2)
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
