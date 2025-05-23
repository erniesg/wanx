import os
import json
import logging
import pathlib
import uuid # For generating a project_id if needed
from dotenv import load_dotenv

# Configure basic logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Project-level imports (adjust paths as necessary if this file moves)
try:
    from backend.text_to_video.argil_client import get_and_download_argil_video_if_ready
    from backend.video_pipeline.asset_orchestrator import RENDERED_AVATARS_DIR as DEFAULT_RENDERED_AVATARS_DIR
except ImportError:
    logger.error("Failed to import necessary modules. Ensure PYTHONPATH is set correctly or run from project root.")
    # Provide dummy functions or raise error if critical
    def get_and_download_argil_video_if_ready(*args, **kwargs):
        logger.error("Dummy get_and_download_argil_video_if_ready called due to import error.")
        return None
    DEFAULT_RENDERED_AVATARS_DIR = pathlib.Path("test_outputs/rendered_avatars") # Fallback

# --- Configuration ---
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TEST_OUTPUT_DIR = PROJECT_ROOT / "test_outputs"
ORCHESTRATION_SUMMARY_FILE = TEST_OUTPUT_DIR / "orchestration_summary_output.json"
# Use the RENDERED_AVATARS_DIR from asset_orchestrator or a local default
DOWNLOADED_AVATARS_OUTPUT_DIR = DEFAULT_RENDERED_AVATARS_DIR

ARGIL_API_KEY = os.getenv("ARGIL_API_KEY")

def run_assembly_preparation_test():
    logger.info("Starting Video Assembly Preparation Test...")

    if not ORCHESTRATION_SUMMARY_FILE.exists():
        logger.error(f"Orchestration summary file not found: {ORCHESTRATION_SUMMARY_FILE}")
        logger.error("Please run the asset orchestrator first to generate this file.")
        return

    logger.info(f"Loading orchestration summary from: {ORCHESTRATION_SUMMARY_FILE}")
    with open(ORCHESTRATION_SUMMARY_FILE, 'r') as f:
        orchestration_data = json.load(f)

    scene_plans = orchestration_data.get("scene_plans", [])
    video_project_id = orchestration_data.get("video_project_id", f"asm_test_{uuid.uuid4().hex[:8]}")
    master_vo_path = orchestration_data.get("master_vo_path")
    background_music_path = orchestration_data.get("background_music_path")

    logger.info(f"Successfully loaded orchestration data. Project ID: {video_project_id}")
    if not scene_plans:
        logger.error("No scene plans found in the orchestration summary. Cannot proceed.")
        return
    if not master_vo_path:
        logger.warning("Master voiceover path not found in orchestration summary.")

    logger.info(f"Using Video Project ID for potential downloads: {video_project_id}")
    os.makedirs(DOWNLOADED_AVATARS_OUTPUT_DIR, exist_ok=True)

    ready_assets_for_assembly = []
    missing_assets = []

    for scene_index, scene_plan_item in enumerate(scene_plans):
        scene_id = scene_plan_item.get("scene_id", f"scene_{scene_index:03d}")
        visual_type = scene_plan_item.get("visual_type")
        asset_path = None
        asset_ready = False

        logger.info(f"Checking assets for Scene {scene_id} (Type: {visual_type})")

        if visual_type == "AVATAR":
            asset_path = scene_plan_item.get("avatar_video_path")
            argil_video_id = scene_plan_item.get("argil_video_id")
            current_status = scene_plan_item.get("argil_render_status")

            if asset_path and pathlib.Path(asset_path).is_file():
                logger.info(f"  AVATAR for scene {scene_id} found at: {asset_path}")
                asset_ready = True
            elif argil_video_id:
                logger.info(f"  AVATAR for scene {scene_id} not found locally or path invalid. Argil ID: {argil_video_id}, Status: {current_status}")
                if not ARGIL_API_KEY:
                    logger.warning(f"  ARGIL_API_KEY not set. Cannot attempt to download Argil video for {scene_id}.")
                elif current_status == "polling_timed_out" or current_status == "DONE" or not current_status : # Or if status suggests it might be ready
                    logger.info(f"  Attempting to check and download Argil video {argil_video_id} for scene {scene_id}...")
                    downloaded_path = get_and_download_argil_video_if_ready(
                        api_key=ARGIL_API_KEY,
                        video_id=argil_video_id,
                        output_dir=str(DOWNLOADED_AVATARS_OUTPUT_DIR),
                        project_id=video_project_id, # Pass the determined project_id
                        scene_id=scene_id
                    )
                    if downloaded_path:
                        logger.info(f"  Successfully downloaded AVATAR for scene {scene_id} to: {downloaded_path}")
                        scene_plan_item["avatar_video_path"] = downloaded_path # Update in memory
                        asset_path = downloaded_path
                        asset_ready = True
                        # Update render status to reflect it was successfully obtained now
                        scene_plan_item["argil_render_status"] = "DONE_AND_DOWNLOADED_BY_ASSEMBLER"
                    else:
                        logger.warning(f"  Failed to download AVATAR for scene {scene_id} (Argil ID: {argil_video_id}). It might not be ready or an error occurred.")
                else:
                    logger.info(f"  Argil video {argil_video_id} for scene {scene_id} status is '{current_status}'. Not attempting download.")
            else:
                logger.warning(f"  AVATAR scene {scene_id} has no 'avatar_video_path' and no 'argil_video_id'. Cannot acquire asset.")

        elif visual_type == "STOCK_VIDEO":
            asset_path = scene_plan_item.get("video_asset_path")
            if asset_path and pathlib.Path(asset_path).is_file():
                logger.info(f"  STOCK_VIDEO for scene {scene_id} found at: {asset_path}")
                asset_ready = True
            else:
                logger.warning(f"  STOCK_VIDEO for scene {scene_id} not found or path invalid: {asset_path}")

        elif visual_type == "STOCK_IMAGE":
            asset_path = scene_plan_item.get("image_asset_path")
            if asset_path and pathlib.Path(asset_path).is_file():
                logger.info(f"  STOCK_IMAGE for scene {scene_id} found at: {asset_path}")
                asset_ready = True
            else:
                logger.warning(f"  STOCK_IMAGE for scene {scene_id} not found or path invalid: {asset_path}")
        else:
            logger.warning(f"  Unknown visual_type '{visual_type}' for scene {scene_id}. Skipping asset check.")

        if asset_ready and asset_path:
            ready_assets_for_assembly.append({
                "scene_id": scene_id,
                "visual_type": visual_type,
                "asset_path": asset_path,
                "original_scene_info": scene_plan_item # Keep original info for assembler
            })
        else:
            missing_assets.append({
                "scene_id": scene_id,
                "visual_type": visual_type,
                "expected_path": asset_path, # This might be None if never set
                "details": f"Argil ID: {scene_plan_item.get('argil_video_id')}, Status: {scene_plan_item.get('argil_render_status')}" if visual_type == "AVATAR" else "Path not found or invalid."
            })

    logger.info("\n--- Video Assembly Preparation Summary ---")
    logger.info(f"Total scenes processed: {len(scene_plans)}")
    logger.info(f"Assets ready for assembly: {len(ready_assets_for_assembly)}")
    for asset_info in ready_assets_for_assembly:
        logger.info(f"  - Scene: {asset_info['scene_id']}, Type: {asset_info['visual_type']}, Path: {asset_info['asset_path']}")

    if missing_assets:
        logger.warning(f"Assets missing or not ready: {len(missing_assets)}")
        for missing_info in missing_assets:
            logger.warning(f"  - Scene: {missing_info['scene_id']}, Type: {missing_info['visual_type']}, Details: {missing_info['details']}")
    else:
        logger.info("All assets appear to be ready for assembly!")

    updated_summary_path = TEST_OUTPUT_DIR / "orchestration_summary_updated_by_assembler_test.json"
    # Save the entire orchestration_data dictionary, which now includes the potentially updated scene_plans
    orchestration_data["scene_plans"] = scene_plans # Ensure the main dict reflects changes to scene_plans
    try:
        with open(updated_summary_path, 'w') as f:
            json.dump(orchestration_data, f, indent=2)
        logger.info(f"Updated orchestration summary (in-memory changes) saved to: {updated_summary_path}")
    except Exception as e:
        logger.error(f"Failed to save updated orchestration summary: {e}")

    logger.info("Video Assembly Preparation Test finished.")

if __name__ == "__main__":
    # Ensure .env is populated with ARGIL_API_KEY
    # This test expects 'test_outputs/orchestration_summary_output.json' to exist.
    # Run asset_orchestrator.py if it does not.
    logger.info("Running test_video_assembler.py directly.")
    run_assembly_preparation_test()
