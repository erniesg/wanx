# backend/text_to_video/run_manual_assembly_test.py
import asyncio
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Add current dir to path to find modules
sys.path.append(os.path.dirname(__file__))

# Load env vars (might be needed by imported modules indirectly)
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)
print(f"Loaded .env from: {dotenv_path}")

# Import necessary parts
try:
    # Import only the function needed for assembly
    from heygen_workflow import run_assembly_and_captioning, check_job_completion # Keep check_job_completion for test
    # REMOVE import of global job_data from main
    # from main import job_data
    print("Successfully imported run_assembly_and_captioning and check_job_completion.")
except ImportError as e:
    print(f"ImportError: {e}. Ensure heygen_workflow.py is accessible.")
    exit(1)
except Exception as e:
     print(f"An unexpected error occurred during import: {e}")
     exit(1)

async def main():
    # Use the specific Job ID from the last successful asset generation run
    job_id_to_test = "heygen_job_3cc94445-2fde-4893-85d7-00c35200af50"
    print(f"Manually setting up and running assembly for job_id: {job_id_to_test}")

    # --- Manually Construct Job Data --- #
    # Replace placeholders if your paths differ slightly
    base_path = "/Users/erniesg/code/erniesg/wanx/backend"
    heygen_workflow_assets = os.path.join(base_path, "assets", "heygen_workflow")
    elevenlabs_audio_base = os.path.join(base_path, "assets", "audio", "speech")

    # --- !! IMPORTANT !! ---
    # Ensure the HeyGen videos below are downloaded manually from the logged URLs
    # and placed in the correct `heygen_downloads` subfolder.
    hook_heygen_local_path = os.path.join(heygen_workflow_assets, "heygen_downloads", job_id_to_test, "hook.mp4")
    conclusion_heygen_local_path = os.path.join(heygen_workflow_assets, "heygen_downloads", job_id_to_test, "conclusion.mp4")
    # --- !! IMPORTANT !! ---

    # Check if manually downloaded files exist (optional but helpful)
    if not os.path.exists(hook_heygen_local_path):
        print(f"WARNING: Expected HeyGen file not found at {hook_heygen_local_path}. Assembly might fail.")
    if not os.path.exists(conclusion_heygen_local_path):
        print(f"WARNING: Expected HeyGen file not found at {conclusion_heygen_local_path}. Assembly might fail.")

    # Construct the job_data structure for this specific job ID
    manual_job_entry = {
        "workflow_type": "heygen",
        "job_id": job_id_to_test,
        "status": "processing", # Will be updated by the function
        "error": None,
        "creation_time": datetime.now().isoformat(), # Or use time from logs
        "input_script_path": "/Users/erniesg/code/erniesg/wanx/public/script2.md",
        "parsed_script": { # Need a minimal script structure for segment order
            "script_segments": {
                "hook": {}, "conflict": {}, "body": {}, "conclusion": {}
            }
        },
        "assets": {
            "music_path": os.path.join(heygen_workflow_assets, "music", job_id_to_test, "background_music.mp3"),
            "music_status": "completed",
            "segments": {
                "hook": {
                    "type": "heygen",
                    "audio_path": os.path.join(elevenlabs_audio_base, "segment_hook.mp3"),
                    "audio_status": "completed",
                    "visual_status": "completed", # Simulate webhook success
                    "heygen_video_id": "08079f3dd8264cbd87ec34058f1ab400", # From logs
                    # URL that assembly will try to download from (or use local if exists)
                    "heygen_video_url": "https://files2.heygen.ai/aws_pacific/avatar_tmp/b592c13f5a974e938f0a04f833346c8e/08079f3dd8264cbd87ec34058f1ab400.mp4?Expires=1746787784&Signature=Zgc7YaM1BcixW~OhUbewzMoSpOkM3p~mQ~x1J7sOj7KnyafoogIwMGuVjzQ5DcHr2s9zCujdKxjymJJKSpsSQ0i-jdXVuOY8qSptFS6hv8ygirV5DvKgA6t6I9Qp3Ov3HxZUElNgZhz6zX9JSdJOJUamuqwaMAcAB7D5i8xH1qmKrixf8oWgSPP-dKgtWp7zyeflV0JWF2-nYdMbBr5Q7Lr7eaEMwN6VJH6-~SxSw6g8cUSgHJsLUzODYXNCqhHyj3c9ASSAiLT7FOmALITCBSKsqis5yVjHkPPYFDsr0TAIh4uBMOSQlhidxm4cxOu24Hco8LXJhtSyFo479mBkTg__&Key-Pair-Id=K38HBHX5LX3X2H",
                    "heygen_avatar_id": "Jin_Vest_Front_public",
                },
                "conflict": {
                    "type": "pexels",
                    "audio_path": os.path.join(elevenlabs_audio_base, "segment_conflict.mp3"),
                    "audio_status": "completed",
                    "visual_status": "completed", # Simulate pexels download success
                    "pexels_video_paths": [os.path.join(heygen_workflow_assets, "stock_video", job_id_to_test, "pexels_Xi_Jinping_Shanghai__16032122.mp4")],
                    "pexels_query": "Xi Jinping Shanghai visit ...",
                },
                "body": {
                    "type": "pexels",
                    "audio_path": os.path.join(elevenlabs_audio_base, "segment_body.mp3"),
                    "audio_status": "completed",
                    "visual_status": "completed", # Simulate pexels download success
                    "pexels_video_paths": [os.path.join(heygen_workflow_assets, "stock_video", job_id_to_test, "pexels_Chinese_AI_investmen_5841707.mp4")],
                    "pexels_query": "Chinese AI investment data ...",
                },
                "conclusion": {
                    "type": "heygen",
                    "audio_path": os.path.join(elevenlabs_audio_base, "segment_conclusion.mp3"),
                    "audio_status": "completed",
                    "visual_status": "completed", # Simulate webhook success
                    "heygen_video_id": "c1279a51d3ba4811a01643cef45b2120", # From logs
                    # URL that assembly will try to download from (or use local if exists)
                    "heygen_video_url": "https://files2.heygen.ai/aws_pacific/avatar_tmp/5073434a423746299e5e667b3f8e0149/c1279a51d3ba4811a01643cef45b2120.mp4?Expires=1746786932&Signature=XAJJ6U4RKcVz7KnJXuSMheT01xQb00AZZ41oYGO2B1QBNyi79HGeplecp52OWT1SQI4nfPHlvlPbKg53oAQyDvUE~iOh~F-RqESOO-kXoqolcYMXiOsCDXwClneDQHwTfdZg~yfMIi4XC9lFzGMuEqc8zNr12UWchEOIdMNrjBJ2FEW-D6oUZ6nNCXtWVzVACuadCksOdhaIIIGndA0YfU6TKY1vLZOwkBdPYTIMlruaa25tC1FgukG2mGkVKoIaC2DcsjaPhgG1MNVM2uYVzFQ1rPFGhBlEy13y8qOADbbWu~ygjHvT377XKYvkwK9CJ1OMihDWIZn5pqSNwI-GRw__&Key-Pair-Id=K38HBHX5LX3X2H",
                    "heygen_avatar_id": "Jin_Vest_Side_public",
                }
            }
        },
        "final_video_path_raw": None,
        "caption_file_path": None,
        "final_video_path_captioned": None
    }

    # Inject this manual state into the global dictionary
    # This simulates the state the main process *should* have had
    # job_data[job_id_to_test] = manual_job_entry # REMOVED - No longer injecting into global
    # print(f"Manually injected job data for {job_id_to_test} into the global job_data dictionary.")
    print(f"Constructed local job data for {job_id_to_test}.")

    # Verify completion check passes with manual data
    # Modify check function if needed, or just assume data is ready for test
    # For simplicity, we'll skip the check here and directly call assembly
    # if check_job_completion(manual_job_entry): # Need to adapt check_job_completion too
    print("Proceeding directly with assembly using constructed data...")
    # Call the modified function, passing the constructed data directly
    run_assembly_and_captioning(job_id_to_test, manual_job_entry)
    # else:
    #     print("Error: check_job_completion returned False even with manually constructed data. Check data structure.")
    #     # Print the constructed data for debugging


    print(f"Assembly process finished for job {job_id_to_test}. Check logs and output folder.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred running the async main function: {e}")
