import os
import json
import logging
import pathlib
import uuid
import random
import time
from dotenv import load_dotenv
import requests

# Project-level imports
from backend.text_to_video.freesound_client import find_and_download_music
from backend.video_pipeline.audio_utils import slice_audio
from backend.text_to_video.s3_client import get_s3_client, ensure_s3_bucket, upload_to_s3
from backend.text_to_video.argil_client import (
    create_argil_video_job,
    render_argil_video,
    get_argil_video_details,
    DEFAULT_AVATAR_ID as DEFAULT_ARGIL_AVATAR_ID,
    DEFAULT_VOICE_ID as DEFAULT_ARGIL_VOICE_ID,
    DEFAULT_GESTURE_SLUGS
)
from backend.text_to_video.pexels_client import find_and_download_videos as find_pexels_videos, find_and_download_photos as find_pexels_photos
from backend.text_to_video.pixabay_client import (
    find_and_download_pixabay_videos,
    find_and_download_pixabay_images,
)

# Configure basic logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Argil Polling Configuration
ARGIL_POLLING_INTERVAL_SECONDS = 30
ARGIL_MAX_POLLING_ATTEMPTS = 20
ARGIL_SUCCESS_STATUS = "DONE"
ARGIL_FAILURE_STATUSES = ["VIDEO_GENERATION_FAILED", "ERROR", "FAILED"]

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

def poll_and_download_argil_videos(scene_plans: list, api_key: str, project_id: str, rendered_avatars_dir: pathlib.Path) -> list:
    """
    Polls Argil for video job completion and downloads successful videos.
    Updates scene_plans in place with status and download paths.
    """
    if not api_key:
        logger.warning("ARGIL_API_KEY not provided. Skipping Argil polling and download.")
        return scene_plans

    os.makedirs(rendered_avatars_dir, exist_ok=True)
    logger.info(f"Starting Argil polling for {len(scene_plans)} scenes. Output dir: {rendered_avatars_dir}")

    all_jobs_finalized = True

    for scene_plan_item in scene_plans:
        if scene_plan_item.get("visual_type") == "AVATAR" and "argil_video_id" in scene_plan_item:
            video_id = scene_plan_item["argil_video_id"]
            scene_id = scene_plan_item.get("scene_id", "unknown_scene")
            current_status = scene_plan_item.get("argil_render_status", "UNKNOWN")

            if current_status == ARGIL_SUCCESS_STATUS and "avatar_video_path" in scene_plan_item:
                logger.info(f"Scene {scene_id} (Argil ID: {video_id}) already processed and downloaded. Skipping poll.")
                continue
            if current_status in ARGIL_FAILURE_STATUSES or current_status == "polling_timed_out":
                logger.info(f"Scene {scene_id} (Argil ID: {video_id}) already in a final failure state: {current_status}. Skipping poll.")
                all_jobs_finalized = all_jobs_finalized and True
                continue

            logger.info(f"Polling for AVATAR scene {scene_id}, Argil Video ID: {video_id}, Current Status: {current_status}")
            all_jobs_finalized = False

            for attempt in range(ARGIL_MAX_POLLING_ATTEMPTS):
                logger.debug(f"Polling attempt {attempt + 1}/{ARGIL_MAX_POLLING_ATTEMPTS} for Argil Video ID: {video_id}")
                details_response = get_argil_video_details(api_key, video_id)

                if details_response and details_response.get("success"):
                    job_data = details_response.get("data", {})
                    status = job_data.get("status")
                    scene_plan_item["argil_render_status"] = status
                    logger.info(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Status: {status}")

                    if status == ARGIL_SUCCESS_STATUS:
                        download_url = job_data.get("videoUrl")

                        if download_url:
                            logger.info(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Succeeded. Download URL: {download_url}")
                            avatar_filename = f"{project_id}_{scene_id}_avatar.mp4"
                            avatar_output_path = rendered_avatars_dir / avatar_filename
                            if _download_file_from_url(download_url, avatar_output_path):
                                scene_plan_item["avatar_video_path"] = str(avatar_output_path)
                                logger.info(f"Successfully downloaded rendered avatar for Scene {scene_id} to {avatar_output_path}")
                            else:
                                scene_plan_item["argil_render_status"] = "download_failed"
                                logger.error(f"Failed to download rendered avatar for Scene {scene_id} from {download_url}")
                        else:
                            scene_plan_item["argil_render_status"] = "success_no_url"
                            logger.error(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Succeeded but no download URL found in response: {job_data}")
                        all_jobs_finalized = True
                        break

                    elif status in ARGIL_FAILURE_STATUSES:
                        logger.error(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Failed with status: {status}. Details: {job_data.get('error')}")
                        all_jobs_finalized = True
                        break
                    else:
                        logger.info(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Status {status} is pending. Waiting {ARGIL_POLLING_INTERVAL_SECONDS}s...")
                        time.sleep(ARGIL_POLLING_INTERVAL_SECONDS)
                else:
                    logger.warning(f"Failed to get details for Argil Video ID: {video_id} (Scene: {scene_id}) on attempt {attempt + 1}. Response: {details_response}")
                    if attempt == ARGIL_MAX_POLLING_ATTEMPTS - 1:
                        scene_plan_item["argil_render_status"] = "polling_details_failed"
                        all_jobs_finalized = True
                    else:
                        time.sleep(ARGIL_POLLING_INTERVAL_SECONDS)

            else:
                if scene_plan_item["argil_render_status"] not in [ARGIL_SUCCESS_STATUS] + ARGIL_FAILURE_STATUSES and \
                   scene_plan_item["argil_render_status"] not in ["download_failed", "success_no_url", "polling_details_failed"]:
                    logger.warning(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Polling timed out after {ARGIL_MAX_POLLING_ATTEMPTS} attempts. Last status: {scene_plan_item.get('argil_render_status')}")
                    scene_plan_item["argil_render_status"] = "polling_timed_out"
                    all_jobs_finalized = True
        elif scene_plan_item.get("visual_type") == "AVATAR" and "argil_video_id" not in scene_plan_item:
            logger.warning(f"AVATAR Scene {scene_plan_item.get('scene_id', 'unknown_scene')} has no argil_video_id. Skipping polling.")

    if all_jobs_finalized:
        logger.info("Argil polling and download process complete. All pollable jobs have reached a final state or timed out.")
    else:
        logger.info("Argil polling and download process iteration complete. Some jobs may still be pending if max global timeout not reached (not implemented here).")

    return scene_plans

def run_asset_orchestration(
    scene_plan_path_str: str,
    master_vo_path_str: str,
    original_script_path_str: str,
    output_dir: pathlib.Path,
) -> pathlib.Path:
    logger.info("Starting video asset orchestration...")

    # Resolve input paths
    scene_plan_file = pathlib.Path(scene_plan_path_str)
    master_vo_file = pathlib.Path(master_vo_path_str)
    original_script_file = pathlib.Path(original_script_path_str)

    # Define output paths based on the provided output_dir
    orchestration_summary_file = output_dir / "05_orchestration_summary.json"
    rendered_avatars_dir = output_dir / "rendered_avatars"
    stock_media_base_dir = output_dir / "stock_media"
    stock_video_output_dir = stock_media_base_dir / "videos"
    stock_image_output_dir = stock_media_base_dir / "images"
    temp_sliced_audio_dir = output_dir / "temp_scene_audio"

    # Create necessary output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered_avatars_dir.mkdir(parents=True, exist_ok=True)
    stock_video_output_dir.mkdir(parents=True, exist_ok=True)
    stock_image_output_dir.mkdir(parents=True, exist_ok=True)
    temp_sliced_audio_dir.mkdir(parents=True, exist_ok=True)

    # --- Get API Keys from environment (as done previously) ---
    freesound_api_key = os.getenv("FREESOUND_API_KEY")
    argil_api_key = os.getenv("ARGIL_API_KEY")
    s3_bucket_name = os.getenv("S3_BUCKET_NAME")
    aws_default_region = os.getenv("AWS_DEFAULT_REGION")
    pexels_api_key = os.getenv("PEXELS_API_KEY")
    pixabay_api_key = os.getenv("PIXABAY_API_KEY")

    # --- 1. Load Inputs ---
    logger.info(f"Loading scene plan from: {scene_plan_file}")
    if not scene_plan_file.exists():
        logger.error(f"Scene plan file not found: {scene_plan_file}")
        raise FileNotFoundError(f"Scene plan file not found: {scene_plan_file}")
    with open(scene_plan_file, 'r') as f:
        scene_plans = json.load(f)

    logger.info(f"Loading original script (JSON output from script gen) from: {original_script_file}")
    if not original_script_file.exists():
        logger.error(f"Original script file (JSON) not found: {original_script_file}")
        raise FileNotFoundError(f"Original script file (JSON) not found: {original_script_file}")
    with open(original_script_file, 'r') as f:
        original_script_data = json.load(f) # This is the JSON script, not the .md story

    if not master_vo_file.exists():
        logger.error(f"Master voiceover file not found: {master_vo_file}")
        raise FileNotFoundError(f"Master voiceover file not found: {master_vo_file}")
    logger.info(f"Master voiceover file located: {master_vo_file}")

    # --- 2. Fetch Background Music ---
    music_vibe = original_script_data.get("production_notes", {}).get("music_vibe")
    downloaded_music_path = None
    if music_vibe and freesound_api_key:
        actual_music_query = music_vibe.split(',')[0].strip()
        logger.info(f"Attempting to download background music. Query: '{actual_music_query}'")
        music_output_filename = "background_music.mp3"
        # Save music directly into the main output_dir for this run
        music_output_path = output_dir / music_output_filename
        downloaded_music_path = find_and_download_music(freesound_api_key, actual_music_query, str(music_output_path))
        if downloaded_music_path:
            logger.info(f"Background music downloaded to: {downloaded_music_path}")
        else:
            logger.warning(f"Failed to download background music for query: {actual_music_query}")
    elif not music_vibe: logger.info("No music_vibe in script. Skipping background music.")
    elif not freesound_api_key: logger.warning("FREESOUND_API_KEY not set. Skipping background music.")

    # --- Initialize S3 Client (if needed for Argil) ---
    s3_client = None
    if s3_bucket_name and aws_default_region and argil_api_key:
        logger.info("Initializing S3 client...")
        s3_client = get_s3_client()
        if s3_client:
            if not ensure_s3_bucket(s3_client, s3_bucket_name, region=aws_default_region):
                logger.error(f"Failed to ensure S3 bucket '{s3_bucket_name}'. Argil audio uploads will fail.")
                s3_client = None
        else: logger.error("Failed to initialize S3 client.")
    elif not (s3_bucket_name and aws_default_region):
        logger.warning("S3 config missing. S3 uploads for Argil will be skipped.")

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
            if not argil_api_key: logger.warning(f"ARGIL_API_KEY not set. Skipping AVATAR scene {scene_id}."); continue
            if s3_client is None: logger.warning(f"S3 client N/A. Skipping AVATAR scene {scene_id}."); continue
            if text_for_scene is None or start_time is None or end_time is None: logger.warning(f"Missing data for AVATAR scene {scene_id}. Skipping."); continue

            sliced_audio_filename = f"{video_project_id}_{scene_id}_audio.mp3"
            sliced_audio_local_path = temp_sliced_audio_dir / sliced_audio_filename
            if not slice_audio(str(master_vo_file), str(sliced_audio_local_path), start_time, end_time):
                logger.error(f"Failed to slice audio for scene {scene_id}. Skipping Argil."); continue

            s3_audio_key = f"{video_project_id}/audio/{sliced_audio_filename}"
            audio_s3_url = upload_to_s3(s3_client, str(sliced_audio_local_path), s3_bucket_name, s3_audio_key)
            if not audio_s3_url: logger.error(f"Failed to upload S3 audio for {scene_id}. Skipping Argil."); continue
            scene_plan_item["audio_s3_url"] = audio_s3_url
            logger.info(f"Uploaded scene audio to S3: {audio_s3_url}")

            argil_job_title = f"{video_project_id}_{scene_id}_Avatar"
            argil_callback_id = f"{video_project_id}__{scene_id}"
            selected_gesture = DEFAULT_GESTURE_SLUGS[0] if DEFAULT_GESTURE_SLUGS else "gesture-1"
            moment_details = {"avatarId": DEFAULT_ARGIL_AVATAR_ID, "gestureSlug": selected_gesture, "audioUrl": audio_s3_url}

            creation_response = create_argil_video_job(
                api_key=argil_api_key, video_title=argil_job_title, full_transcript=text_for_scene,
                moments_payload=[moment_details], avatar_id=DEFAULT_ARGIL_AVATAR_ID,
                voice_id=DEFAULT_ARGIL_VOICE_ID, aspect_ratio="9:16", callback_id=argil_callback_id
            )
            if creation_response and creation_response.get("success"):
                argil_video_id = creation_response.get("video_id")
                scene_plan_item["argil_video_id"] = argil_video_id
                render_response = render_argil_video(argil_api_key, argil_video_id)
                if render_response and render_response.get("success"):
                    scene_plan_item["argil_render_status"] = render_response.get('data',{}).get('status')
                    logger.info(f"Argil video render requested for {scene_id}. Status: {scene_plan_item['argil_render_status']}")
                else: scene_plan_item["argil_render_status"] = "render_failed"; logger.error(f"Failed to render Argil video {scene_id}.")
            else: scene_plan_item["argil_creation_status"] = "creation_failed"; logger.error(f"Failed to create Argil job for {scene_id}.")

        elif visual_type == "STOCK_VIDEO":
            if not visual_keywords: logger.warning(f"No keywords for STOCK_VIDEO {scene_id}. Skipping."); continue
            query = visual_keywords[0]

            all_configured_providers = []
            if pexels_api_key: all_configured_providers.append("pexels")
            if pixabay_api_key: all_configured_providers.append("pixabay")

            if not all_configured_providers:
                logger.warning(f"No API keys for any stock video providers. Skipping STOCK_VIDEO for {scene_id}.")
                continue

            downloaded_paths = []
            primary_provider_choice = random.choice(all_configured_providers)
            providers_to_try = [primary_provider_choice]

            # If more than one provider is configured, add the others as fallbacks
            if len(all_configured_providers) > 1:
                fallback_providers = [p for p in all_configured_providers if p != primary_provider_choice]
                providers_to_try.extend(fallback_providers)

            for provider_index, current_provider in enumerate(providers_to_try):
                logger.info(f"Attempting STOCK_VIDEO for {scene_id} from provider: {current_provider} (Attempt {provider_index + 1}/{len(providers_to_try)}) with query: '{query}'")

                if current_provider == "pexels":
                    downloaded_paths = find_pexels_videos(pexels_api_key, query, 1, str(stock_video_output_dir), orientation="portrait")
                elif current_provider == "pixabay":
                    downloaded_paths = find_and_download_pixabay_videos(pixabay_api_key, query, 1, str(stock_video_output_dir), orientation="vertical")

                if downloaded_paths:
                    scene_plan_item["video_asset_path"] = str(pathlib.Path(downloaded_paths[0]))
                    scene_plan_item["stock_media_provider"] = current_provider
                    logger.info(f"Successfully downloaded STOCK_VIDEO for {scene_id} from {current_provider}: {downloaded_paths[0]}")
                    break # Success, no need to try other providers
                else:
                    logger.warning(f"Failed to download STOCK_VIDEO from {current_provider} for {scene_id} with query '{query}'.")

            if not downloaded_paths: # If still no paths after trying all configured providers
                 logger.error(f"Exhausted all providers but failed to download STOCK_VIDEO for {scene_id} with query '{query}'.")

        elif visual_type == "STOCK_IMAGE":
            if not visual_keywords: logger.warning(f"No keywords for STOCK_IMAGE {scene_id}. Skipping."); continue
            query = visual_keywords[0]

            all_configured_providers = []
            if pexels_api_key: all_configured_providers.append("pexels")
            if pixabay_api_key: all_configured_providers.append("pixabay")

            if not all_configured_providers:
                logger.warning(f"No API keys for any stock image providers. Skipping STOCK_IMAGE for {scene_id}.")
                continue

            downloaded_paths = []
            primary_provider_choice = random.choice(all_configured_providers)
            providers_to_try = [primary_provider_choice]

            if len(all_configured_providers) > 1:
                fallback_providers = [p for p in all_configured_providers if p != primary_provider_choice]
                providers_to_try.extend(fallback_providers)

            for provider_index, current_provider in enumerate(providers_to_try):
                logger.info(f"Attempting STOCK_IMAGE for {scene_id} from provider: {current_provider} (Attempt {provider_index + 1}/{len(providers_to_try)}) with query: '{query}'")

                if current_provider == "pexels":
                    downloaded_paths = find_pexels_photos(pexels_api_key, query, 1, str(stock_image_output_dir), orientation="portrait")
                elif current_provider == "pixabay":
                    downloaded_paths = find_and_download_pixabay_images(pixabay_api_key, query, 1, str(stock_image_output_dir), orientation="vertical")

                if downloaded_paths:
                    scene_plan_item["image_asset_path"] = str(pathlib.Path(downloaded_paths[0]))
                    scene_plan_item["stock_media_provider"] = current_provider
                    logger.info(f"Successfully downloaded STOCK_IMAGE for {scene_id} from {current_provider}: {downloaded_paths[0]}")
                    break # Success
                else:
                    logger.warning(f"Failed to download STOCK_IMAGE from {current_provider} for {scene_id} with query '{query}'.")

            if not downloaded_paths: # If still no paths after trying all
                logger.error(f"Exhausted all providers but failed to download STOCK_IMAGE for {scene_id} with query '{query}'.")
        else:
            logger.warning(f"Unknown visual_type '{visual_type}' for scene {scene_id}.")

    logger.info("Initial asset orchestration pass completed.")

    # --- 4. Poll for Argil Video Completion and Download ---
    if argil_api_key:
        scene_plans = poll_and_download_argil_videos(scene_plans, argil_api_key, video_project_id, rendered_avatars_dir)
    else:
        logger.warning("ARGIL_API_KEY not set. Skipping Argil polling.")
        for sp in scene_plans:
            if sp.get("visual_type") == "AVATAR": sp["argil_render_status"] = "skipped_no_api_key"

    # --- 5. Save Orchestration Summary ---
    orchestration_summary = {
        "video_project_id": video_project_id,
        "master_vo_path": str(master_vo_file),
        "background_music_path": str(downloaded_music_path) if downloaded_music_path else None,
        "scene_plans": scene_plans,
        "original_script_file_used": str(original_script_file),
        "scene_plan_file_used": str(scene_plan_file)
    }
    with open(orchestration_summary_file, 'w') as f:
        json.dump(orchestration_summary, f, indent=2)
    logger.info(f"Orchestration summary saved to: {orchestration_summary_file}")

    # Clean up temporary sliced audio directory
    if temp_sliced_audio_dir.exists():
        try:
            shutil.rmtree(temp_sliced_audio_dir)
            logger.info(f"Cleaned up temp sliced audio dir: {temp_sliced_audio_dir}")
        except Exception as e:
            logger.warning(f"Error cleaning up temp sliced audio dir {temp_sliced_audio_dir}: {e}")

    logger.info("Video asset orchestration finished.")
    return orchestration_summary_file
