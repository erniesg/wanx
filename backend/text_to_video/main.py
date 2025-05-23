from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header, Depends, Response
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import os
import traceback
import asyncio
import json
import uuid
import logging
from datetime import datetime
from dotenv import load_dotenv
from contextlib import asynccontextmanager # Import asynccontextmanager

import sys
import os
# Corrected sys.path.append - this should ideally point to the parent of 'backend'
# so that 'from backend.text_to_video...' works if you ever run scripts from outside 'wanx'
# but doesn't hurt.
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from .create_tiktok import create_tiktok
# Import individual components for stepwise processing
from .generate_script import transform_to_script as generate_script_func
from .tts import text_to_speech
from .create_captions import add_bottom_captions as create_captions_func
from .ttv import text_to_video as generate_video_func
from .editor import combine_audio_video as combine_audio_video_captions_func

# Import the new workflow orchestrator
from .heygen_workflow import run_heygen_workflow, check_job_completion
from .argil_workflow import run_argil_workflow

# Import S3 client for direct use if any (though mostly within workflows now)
# from .s3_client import get_s3_client, ensure_s3_bucket, upload_to_s3

# Import editor functions for assembly
from .editor import assemble_heygen_video, assemble_argil_video

# Import Argil client for potential use (e.g., webhook verification, though not strictly needed for receiver)
from backend.text_to_video.argil_client import list_argil_webhooks, create_argil_webhook

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("api")

# Define security scheme for API key authentication
MODAL_KEY_HEADER = APIKeyHeader(name="Modal-Key", auto_error=False)
MODAL_SECRET_HEADER = APIKeyHeader(name="Modal-Secret", auto_error=False)
X_AUTH_SOURCE_HEADER = APIKeyHeader(name="X-Auth-Source", auto_error=False)
X_AUTH_MODE_HEADER = APIKeyHeader(name="X-Auth-Mode", auto_error=False)

# Ensure all necessary directories exist (function definition moved slightly earlier)
def ensure_directories():
    """Create all necessary directories for the application"""
    backend_dir = os.path.dirname(__file__) # Corrected: backend_dir is the current file's dir
    assets_dir = os.path.join(backend_dir, "..", "assets") # Go up one level to reach assets relative to backend_dir

    # Create directory structure for original workflow and HeyGen workflow
    directories = [
        os.path.join(assets_dir, "audio", "speech"),
        os.path.join(assets_dir, "videos"),
        os.path.join(backend_dir, "..", "logs"), # Logs relative to project root might be better
        # HeyGen workflow dirs
        os.path.join(assets_dir, "heygen_workflow", "temp_audio"),
        os.path.join(assets_dir, "heygen_workflow", "stock_video"),
        os.path.join(assets_dir, "heygen_workflow", "heygen_downloads"),
        os.path.join(assets_dir, "heygen_workflow", "music"),
        os.path.join(assets_dir, "heygen_workflow", "output"),
        os.path.join(assets_dir, "heygen_workflow", "captions"),
        # Argil workflow dirs
        os.path.join(assets_dir, "argil_workflow", "temp_audio"),
        os.path.join(assets_dir, "argil_workflow", "stock_video"),
        os.path.join(assets_dir, "argil_workflow", "argil_downloads"), # For downloaded Argil clips
        os.path.join(assets_dir, "argil_workflow", "music"),
        os.path.join(assets_dir, "argil_workflow", "output"),
        os.path.join(assets_dir, "argil_workflow", "captions"),
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    # Return paths relative to the backend/text_to_video dir might not be needed globally
    # return backend_dir, assets_dir

# Define the lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    logger.info("Application startup: Ensuring directories exist...")
    ensure_directories()
    load_dotenv()  # Load environment variables on startup
    logger.info("Loaded environment variables.")

    # --- Add Argil Webhook Check/Registration --- #
    argil_api_key = os.getenv("ARGIL_API_KEY")
    ngrok_url = os.getenv("NGROK_PUBLIC_URL")
    target_webhook_events = sorted(["VIDEO_GENERATION_SUCCESS", "VIDEO_GENERATION_FAILED"])

    if not argil_api_key:
        logger.warning("ARGIL_API_KEY not set. Skipping Argil webhook registration.")
    elif not ngrok_url:
        logger.warning("NGROK_PUBLIC_URL not set. Skipping Argil webhook registration.")
    else:
        webhook_callback_url = f"{ngrok_url.rstrip('/')}/webhooks/argil"
        logger.info(f"Checking for existing Argil webhook for URL: {webhook_callback_url}")

        webhook_found = False
        try:
            list_resp = list_argil_webhooks(argil_api_key)
            if list_resp and list_resp.get("success"):
                for wh in list_resp.get("data", []):
                    # Check URL and ensure the required events are present (order might differ)
                    if wh.get("callbackUrl") == webhook_callback_url and \
                       sorted(wh.get("events", [])) == target_webhook_events:
                        logger.info(f"Found existing Argil webhook: ID {wh.get('id')}")
                        webhook_found = True
                        break
            else:
                 logger.error(f"Failed to list Argil webhooks: {list_resp.get('error', 'Unknown error')}")

            if not webhook_found:
                logger.info(f"No suitable Argil webhook found. Attempting to create one...")
                create_resp = create_argil_webhook(
                    api_key=argil_api_key,
                    callback_url=webhook_callback_url,
                    events=target_webhook_events # Pass the sorted list
                )
                if create_resp and create_resp.get("success"):
                    logger.info(f"Successfully created Argil webhook: ID {create_resp.get('webhook_id')}")
                else:
                    logger.error(f"Failed to create Argil webhook: {create_resp.get('error', 'Unknown error')}. Details: {create_resp.get('details', '')}")

        except Exception as e:
            logger.error(f"An error occurred during Argil webhook check/registration: {e}", exc_info=True)
    # --- End Argil Webhook Check/Registration --- #

    logger.info("Application startup complete.")
    yield
    # Code to run on shutdown (if any)
    logger.info("Application shutdown.")

# Create FastAPI app instance using the lifespan manager
app = FastAPI(
    title="Video Generation API",
    description="API for generating videos from text content with authentication required",
    version="1.0.0",
    lifespan=lifespan # Use the new lifespan manager
)

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to log request headers
@app.middleware("http")
async def log_request_headers(request: Request, call_next):
    """Middleware to log all request headers"""
    # Log the request method and URL
    logger.info(f"Request: {request.method} {request.url}")

    # Log all headers
    headers = dict(request.headers)
    # Redact sensitive information if needed
    if "authorization" in headers:
        headers["authorization"] = "REDACTED"
    if "Modal-Secret" in headers:
        headers["Modal-Secret"] = "REDACTED"

    logger.info(f"Headers: {json.dumps(headers, indent=2)}")

    # Process the request and get the response
    response = await call_next(request)

    # Log the response status code
    logger.info(f"Response status: {response.status_code}")

    return response

# Store for active jobs and their status messages
active_jobs: Dict[str, List[str]] = {}
job_results: Dict[str, str] = {}
# Store for intermediate results in the workflow
job_data: Dict[str, Dict] = {}
# Example structure for job_data['some_job_id'] in the HeyGen workflow:
# {
#     "workflow_type": "heygen",
#     "job_id": "some_job_id",
#     "status": "pending" | "processing" | "assembling" | "captioning" | "completed" | "failed",
#     "error": str | None,
#     "creation_time": str (ISO format),
#     "input_script_path": str,
#     "parsed_script": dict | None,
#     "assets": {
#         "music_path": str | None,
#         "music_status": "pending" | "completed" | "failed",
#         "segments": {
#             "segment_name_1": {
#                 "type": "heygen" | "pexels",
#                 "audio_path": str | None,
#                 "audio_status": "pending" | "completed" | "failed",
#                 "visual_status": "pending" | "processing" | "completed" | "failed",
#                 # If type == "heygen":
#                 "heygen_video_id": str | None,
#                 "heygen_video_url": str | None,
#                 "heygen_avatar_id": str,
#                 # If type == "pexels":
#                 "pexels_video_paths": list[str] | None,
#                 "pexels_query": str,
#             },
#             "segment_name_2": { ... }
#         }
#     },
#     "final_video_path_raw": str | None, # Before captions
#     "caption_file_path": str | None,
#     "final_video_path_captioned": str | None # Final result
# }

# Authentication dependency
async def verify_authentication(
    auth_source: Optional[str] = Depends(X_AUTH_SOURCE_HEADER),
    auth_mode: Optional[str] = Depends(X_AUTH_MODE_HEADER)
):
    """
    Verify authentication headers.

    Requires:
    - X-Auth-Source must be "gimme-ai-gateway"
    - X-Auth-Mode must be either "admin" or "free"
    """

    # Check for required auth source
    if not auth_source or auth_source not in ["gimme-ai", "gimme-ai-gateway"]:
        logger.warning(f"Invalid auth source: {auth_source}")
        raise HTTPException(
            status_code=403,
            detail="Access denied. Invalid authentication source."
        )

    # Check for valid auth mode
    if not auth_mode or auth_mode not in ["admin", "free"]:
        logger.warning(f"Invalid auth mode: {auth_mode}")
        raise HTTPException(
            status_code=403,
            detail="Access denied. Invalid authentication mode."
        )

    logger.info(f"Authentication successful: source={auth_source}, mode={auth_mode}")
    return True

# Load environment variables from .env file
load_dotenv()  # Call load_dotenv early

# Define Pydantic models for request/response validation
class Options(BaseModel):
    style: Optional[str] = None
    duration: Optional[str] = None
    resolution: Optional[str] = None
    voice: Optional[str] = None

class Metadata(BaseModel):
    source: Optional[str] = None
    timestamp: Optional[str] = None

class VideoRequest(BaseModel):
    content: str
    options: Optional[Options] = None
    metadata: Optional[Metadata] = None

class WorkflowResponse(BaseModel):
    status: str = "started"

class WorkflowInitResponse(BaseModel):
    job_id: str
    status: str = "initialized"

class StepStatus(BaseModel):
    script: str = "pending"
    audio: str = "pending"
    captions: str = "pending"
    base_video: str = "pending"
    final_video: str = "pending"

class WorkflowStatusResponse(BaseModel):
    job_id: str
    status: str
    steps: StepStatus
    progress: int = 0
    error: Optional[str] = None

class StepStatusResponse(BaseModel):
    status: str
    details: Dict[str, Any] = {}

@app.get("/", dependencies=[Depends(verify_authentication)])
def read_root():
    return {"message": "Welcome to the Video Generation API"}

@app.post("/generate_video", dependencies=[Depends(verify_authentication)])
async def generate_video(request: VideoRequest):
    """
    Generate a video synchronously (blocks until complete)

    Requires authentication with Modal-Key and Modal-Secret headers.
    """
    try:
        # Generate the video using your create_tiktok function
        video_path = create_tiktok(request.content)

        # Check if video was created successfully
        if not video_path or not os.path.exists(video_path):
            raise HTTPException(status_code=500, detail="Failed to generate video")

        # Return the video file
        return FileResponse(
            path=video_path,
            media_type="video/mp4",
            filename=os.path.basename(video_path)
        )

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Detailed error: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error generating video: {str(e)}")

@app.post("/generate_video_stream", dependencies=[Depends(verify_authentication)])
async def generate_video_stream(request: VideoRequest, background_tasks: BackgroundTasks):
    """
    Start a video generation job and return a job ID for status tracking

    Requires authentication with Modal-Key and Modal-Secret headers.
    """
    job_id = str(uuid.uuid4())
    active_jobs[job_id] = []

    # Define callback function to collect status updates
    def log_callback(message):
        active_jobs[job_id].append(message)

    # Run video generation in a background task
    background_tasks.add_task(run_video_generation, job_id, request.content, log_callback)

    return {"job_id": job_id, "status": "started"}

async def run_video_generation(job_id, content, log_callback):
    """Run the video generation process in the background"""
    try:
        # Pass the job_id to create_tiktok to use as a consistent identifier
        video_path = create_tiktok(content, log_callback, job_id)

        # Store the result
        if video_path and os.path.exists(video_path):
            job_results[job_id] = video_path
            active_jobs[job_id].append(f"Video generation complete: {os.path.basename(video_path)}")
        else:
            active_jobs[job_id].append("Failed to generate video")
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error in background task: {error_details}")
        active_jobs[job_id].append(f"Error: {str(e)}")

@app.get("/stream_logs/{job_id}", dependencies=[Depends(verify_authentication)])
async def stream_logs(job_id: str):
    """
    Stream log messages for a specific job

    Requires authentication with Modal-Key and Modal-Secret headers.
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        # Send any existing messages
        current_index = 0

        while True:
            # Check if there are new messages
            if current_index < len(active_jobs[job_id]):
                # Send all new messages
                while current_index < len(active_jobs[job_id]):
                    message = active_jobs[job_id][current_index]
                    yield f"data: {json.dumps({'message': message})}\n\n"
                    current_index += 1

            # Check if job is complete
            if job_id in job_results:
                yield f"data: {json.dumps({'status': 'complete', 'video_path': job_results[job_id]})}\n\n"
                return

            # Wait before checking for new messages
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/get_video/{job_id}", dependencies=[Depends(verify_authentication)])
async def get_video(job_id: str):
    """
    Get the completed video for a job

    Requires authentication with Modal-Key and Modal-Secret headers.
    """
    if job_id not in job_results:
        raise HTTPException(status_code=404, detail="Video not found or generation not complete")

    video_path = job_results[job_id]

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=os.path.basename(video_path)
    )

@app.get("/job_status/{job_id}", dependencies=[Depends(verify_authentication)])
async def job_status(job_id: str):
    """
    Get the current status of a job

    Requires authentication with Modal-Key and Modal-Secret headers.
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    is_complete = job_id in job_results

    return {
        "job_id": job_id,
        "status": "complete" if is_complete else "processing",
        "logs": active_jobs[job_id],
        "video_path": job_results.get(job_id) if is_complete else None
    }

@app.get("/videos/{filename}", dependencies=[Depends(verify_authentication)])
@app.head("/videos/{filename}", dependencies=[Depends(verify_authentication)])  # Also allow HEAD requests
async def get_video_by_filename(filename: str):
    """
    Serve a video file directly by filename

    Requires authentication with Modal-Key and Modal-Secret headers.
    """
    # Construct the path to the video file
    video_path = os.path.join(assets_dir, "videos", filename)

    # Check if the file exists
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    # Return the video file
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=filename
    )

@app.delete("/cleanup/{job_id}", dependencies=[Depends(verify_authentication)])
async def cleanup_job(job_id: str):
    """
    Clean up resources for a completed job

    Requires authentication with Modal-Key and Modal-Secret headers.
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get the video path if it exists
    video_path = job_results.get(job_id)

    # Remove job data from memory
    active_jobs.pop(job_id, None)
    job_results.pop(job_id, None)
    job_data.pop(job_id, None)  # Clean up workflow data too

    # Optionally, delete the video file (uncomment if desired)
    # if video_path and os.path.exists(video_path):
    #     try:
    #         os.remove(video_path)
    #     except Exception as e:
    #         print(f"Error deleting file {video_path}: {e}")

    return {"status": "success", "message": f"Cleaned up resources for job {job_id}"}

# Helper functions for workflow status management
def calculate_overall_status(job_data):
    """Calculate the overall status based on step statuses"""
    steps = job_data.get("steps", {})

    # If any step failed, the overall status is failed
    if "failed" in steps.values():
        return "failed"

    # If all steps are completed, the overall status is completed
    if all(status == "completed" for status in steps.values()):
        return "completed"

    # If any step is processing, the overall status is processing
    if "processing" in steps.values():
        return "processing"

    # Otherwise, the status is pending
    return "pending"

def calculate_progress(job_data):
    """Calculate the overall progress percentage"""
    steps = job_data.get("steps", {})
    total_steps = len(steps)
    if total_steps == 0:
        return 0

    # Count completed steps
    completed_steps = sum(1 for status in steps.values() if status == "completed")

    # Count processing steps (count as half complete)
    processing_steps = sum(0.5 for status in steps.values() if status == "processing")

    # Calculate progress percentage
    progress = int((completed_steps + processing_steps) / total_steps * 100)
    return min(progress, 100)  # Ensure progress doesn't exceed 100%

# New stepwise workflow endpoints for Cloudflare integration

@app.post("/workflow/init", dependencies=[Depends(verify_authentication)], response_model=WorkflowInitResponse)
async def init_workflow(request: VideoRequest):
    """
    Initialize a video generation workflow and return a job ID.
    This is the first step in the workflow.
    """
    job_id = str(uuid.uuid4())
    active_jobs[job_id] = ["Workflow initialized"]

    # Initialize job data with content, options, and metadata
    job_data[job_id] = {
        "content": request.content,
        "options": request.options.dict() if request.options else {},
        "metadata": request.metadata.dict() if request.metadata else {},
        "created_at": datetime.now().isoformat(),
        "steps": {
            "script": "pending",
            "audio": "pending",
            "captions": "pending",
            "base_video": "pending",
            "final_video": "pending"
        }
    }

    logger.info(f"Initialized workflow with job_id: {job_id}")

    return {"job_id": job_id, "status": "initialized"}

@app.post("/workflow/generate_script/{job_id}", dependencies=[Depends(verify_authentication)], response_model=WorkflowResponse)
async def workflow_generate_script(job_id: str, background_tasks: BackgroundTasks):
    """
    Step 1: Generate a script from the content.
    """
    if job_id not in job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    # Update step status to processing
    job_data[job_id]["steps"]["script"] = "processing"
    active_jobs[job_id].append("Generating script...")

    # Start script generation in background
    background_tasks.add_task(generate_script_task, job_id)

    return {"status": "started"}

async def generate_script_task(job_id: str):
    """Background task to generate script"""
    try:
        content = job_data[job_id].get("content")
        if not content:
            raise ValueError("Content not found for this job")

        # Generate script
        script = generate_script_func(content)

        if not script:
            raise ValueError("Failed to generate script")

        # Store script in job data
        job_data[job_id]["script"] = script
        job_data[job_id]["steps"]["script"] = "completed"
        job_data[job_id]["script_details"] = {
            "length": len(script),
            "completed_at": datetime.now().isoformat()
        }
        active_jobs[job_id].append("Script generation complete")

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error generating script: {error_details}")
        job_data[job_id]["steps"]["script"] = "failed"
        job_data[job_id]["error"] = f"Script generation failed: {str(e)}"
        active_jobs[job_id].append(f"Error generating script: {str(e)}")

@app.post("/workflow/generate_audio/{job_id}", dependencies=[Depends(verify_authentication)], response_model=WorkflowResponse)
async def workflow_generate_audio(job_id: str, background_tasks: BackgroundTasks):
    """
    Step 2: Generate audio from the script.
    """
    if job_id not in job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if script generation is completed
    if job_data[job_id]["steps"]["script"] != "completed":
        raise HTTPException(status_code=400, detail="Script generation must complete before generating audio")

    # Update step status to processing
    job_data[job_id]["steps"]["audio"] = "processing"
    active_jobs[job_id].append("Generating audio...")

    # Start audio generation in background
    background_tasks.add_task(generate_audio_task, job_id)

    return {"status": "started"}

async def generate_audio_task(job_id: str):
    """Background task to generate audio"""
    try:
        script = job_data[job_id].get("script")
        if not script:
            raise ValueError("Script not found for this job")

        # Generate audio
        audio_path = text_to_speech(script, job_id)

        if not audio_path or not os.path.exists(audio_path):
            raise ValueError("Failed to generate audio")

        # Store audio path in job data
        job_data[job_id]["audio_path"] = audio_path
        job_data[job_id]["steps"]["audio"] = "completed"
        job_data[job_id]["audio_details"] = {
            "path": audio_path,
            "filename": os.path.basename(audio_path),
            "completed_at": datetime.now().isoformat()
        }
        active_jobs[job_id].append(f"Audio generation complete: {os.path.basename(audio_path)}")

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error generating audio: {error_details}")
        job_data[job_id]["steps"]["audio"] = "failed"
        job_data[job_id]["error"] = f"Audio generation failed: {str(e)}"
        active_jobs[job_id].append(f"Error generating audio: {str(e)}")

@app.post("/workflow/generate_captions/{job_id}", dependencies=[Depends(verify_authentication)], response_model=WorkflowResponse)
async def workflow_generate_captions(job_id: str, background_tasks: BackgroundTasks):
    """
    Step 3: Generate captions from the audio.
    """
    if job_id not in job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if audio generation is completed
    if job_data[job_id]["steps"]["audio"] != "completed":
        raise HTTPException(status_code=400, detail="Audio generation must complete before generating captions")

    # Update step status to processing
    job_data[job_id]["steps"]["captions"] = "processing"
    active_jobs[job_id].append("Generating captions...")

    # Start captions generation in background
    background_tasks.add_task(generate_captions_task, job_id)

    return {"status": "started"}

async def generate_captions_task(job_id: str):
    """Background task to generate captions"""
    try:
        audio_path = job_data[job_id].get("audio_path")
        script = job_data[job_id].get("script")

        if not audio_path or not script:
            raise ValueError("Audio path or script not found for this job")

        # Generate captions
        captions_path = create_captions_func(audio_path, script, job_id)

        if not captions_path:
            raise ValueError("Failed to generate captions")

        # Store captions path in job data
        job_data[job_id]["captions_path"] = captions_path
        job_data[job_id]["steps"]["captions"] = "completed"
        job_data[job_id]["captions_details"] = {
            "path": captions_path,
            "filename": os.path.basename(captions_path),
            "completed_at": datetime.now().isoformat()
        }
        active_jobs[job_id].append(f"Captions generation complete: {os.path.basename(captions_path)}")

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error generating captions: {error_details}")
        job_data[job_id]["steps"]["captions"] = "failed"
        job_data[job_id]["error"] = f"Captions generation failed: {str(e)}"
        active_jobs[job_id].append(f"Error generating captions: {str(e)}")

@app.post("/workflow/generate_base_video/{job_id}", dependencies=[Depends(verify_authentication)], response_model=WorkflowResponse)
async def workflow_generate_base_video(job_id: str, background_tasks: BackgroundTasks):
    """
    Step 4: Generate the base video.
    """
    if job_id not in job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if script generation is completed
    if job_data[job_id]["steps"]["script"] != "completed":
        raise HTTPException(status_code=400, detail="Script generation must complete before generating base video")

    # Update step status to processing
    job_data[job_id]["steps"]["base_video"] = "processing"
    active_jobs[job_id].append("Generating base video...")

    # Start base video generation in background
    background_tasks.add_task(generate_base_video_task, job_id)

    return {"status": "started"}

async def generate_base_video_task(job_id: str):
    """Background task to generate base video"""
    try:
        script = job_data[job_id].get("script")

        if not script:
            raise ValueError("Script not found for this job")

        # Generate base video
        video_path = generate_video_func(script, job_id)

        if not video_path or not os.path.exists(video_path):
            raise ValueError("Failed to generate base video")

        # Store base video path in job data
        job_data[job_id]["base_video_path"] = video_path
        job_data[job_id]["steps"]["base_video"] = "completed"
        job_data[job_id]["base_video_details"] = {
            "path": video_path,
            "filename": os.path.basename(video_path),
            "completed_at": datetime.now().isoformat()
        }
        active_jobs[job_id].append(f"Base video generation complete: {os.path.basename(video_path)}")

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error generating base video: {error_details}")
        job_data[job_id]["steps"]["base_video"] = "failed"
        job_data[job_id]["error"] = f"Base video generation failed: {str(e)}"
        active_jobs[job_id].append(f"Error generating base video: {str(e)}")

@app.post("/workflow/combine_final_video/{job_id}", dependencies=[Depends(verify_authentication)], response_model=WorkflowResponse)
async def workflow_combine_final_video(job_id: str, background_tasks: BackgroundTasks):
    """
    Step 5: Combine audio, video, and captions into the final video.
    """
    if job_id not in job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if required steps are completed
    if job_data[job_id]["steps"]["base_video"] != "completed":
        raise HTTPException(status_code=400, detail="Base video generation must complete before combining final video")

    if job_data[job_id]["steps"]["audio"] != "completed":
        raise HTTPException(status_code=400, detail="Audio generation must complete before combining final video")

    if job_data[job_id]["steps"]["captions"] != "completed":
        raise HTTPException(status_code=400, detail="Captions generation must complete before combining final video")

    # Update step status to processing
    job_data[job_id]["steps"]["final_video"] = "processing"
    active_jobs[job_id].append("Combining final video...")

    # Start final video combination in background
    background_tasks.add_task(combine_final_video_task, job_id)

    return {"status": "started"}

async def combine_final_video_task(job_id: str):
    """Background task to combine final video"""
    try:
        base_video_path = job_data[job_id].get("base_video_path")
        audio_path = job_data[job_id].get("audio_path")
        captions_path = job_data[job_id].get("captions_path")

        if not base_video_path or not audio_path or not captions_path:
            raise ValueError("Missing required files for final video combination")

        # Combine final video
        final_video_path = combine_audio_video_captions_func(base_video_path, audio_path, captions_path, job_id)

        if not final_video_path or not os.path.exists(final_video_path):
            raise ValueError("Failed to combine final video")

        # Store final video path in job data
        job_data[job_id]["final_video_path"] = final_video_path
        job_results[job_id] = final_video_path  # Store in job_results for compatibility with existing endpoints
        job_data[job_id]["steps"]["final_video"] = "completed"
        job_data[job_id]["final_video_details"] = {
            "path": final_video_path,
            "filename": os.path.basename(final_video_path),
            "completed_at": datetime.now().isoformat()
        }
        active_jobs[job_id].append(f"Final video generation complete: {os.path.basename(final_video_path)}")

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error combining final video: {error_details}")
        job_data[job_id]["steps"]["final_video"] = "failed"
        job_data[job_id]["error"] = f"Final video combination failed: {str(e)}"
        active_jobs[job_id].append(f"Error combining final video: {str(e)}")

@app.get("/workflow/status/{job_id}", dependencies=[Depends(verify_authentication)])
async def workflow_status(job_id: str, step: Optional[str] = None):
    """
    Get the current status of a workflow job.
    Optionally specify a step to get detailed status for that step.
    Handles both original step-by-step and new HeyGen workflow types.
    """
    if job_id not in job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    job_info = job_data[job_id]
    workflow_type = job_info.get("workflow_type", "original") # Default to original if type missing

    if workflow_type == "heygen":
        # Return tailored status for HeyGen workflow
        # Basic example: return the whole job_data entry
        # TODO: Could format this nicer later
        return job_info

    # --- Original Workflow Status Logic (keep as is) ---
    elif step:
        # Return status for specific step
        if step not in job_info.get("steps", {}):
            raise HTTPException(status_code=404, detail=f"Step {step} not found")

        status = job_info["steps"][step]
        details = job_info.get(f"{step}_details", {})

        return StepStatusResponse(
            status=status,
            details=details
        )
    else:
        # Return overall status
        overall_status = calculate_overall_status(job_info)
        progress = calculate_progress(job_info)

        return WorkflowStatusResponse(
            job_id=job_id,
            status=overall_status,
            steps=StepStatus(**job_info["steps"]),
            progress=progress,
            error=job_info.get("error")
        )

# --- HeyGen Webhook Receiver ---
@app.post("/webhooks/heygen")
async def handle_heygen_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle callbacks from HeyGen API v2"""
    try:
        payload = await request.json()
        logger.info(f"Received HeyGen webhook: {payload}")

        # Extract key information
        event_type = payload.get("event_type")
        event_data = payload.get("event_data", {})
        video_id = event_data.get("video_id")
        callback_id_str = event_data.get("callback_id") # Crucial for matching job

        # Ignore irrelevant event types early
        if event_type not in ["avatar_video.success", "avatar_video.fail"]:
            logger.warning(f"Received and ignoring HeyGen event type: {event_type} | Callback ID: {callback_id_str}")
            return JSONResponse(content={"status": "received"})

        if not callback_id_str:
            logger.error(f"Received HeyGen webhook event {event_type} without a callback_id. Cannot update job state.")
            return JSONResponse(content={"status": "received"})

        # --- Update Job State --- #
        try:
            # Split callback_id to get job_id and segment_name
            parts = callback_id_str.split("__", 1)
            if len(parts) != 2:
                logger.error(f"Could not parse job_id and segment_name from callback_id: {callback_id_str}")
                return JSONResponse(content={"status": "received"})
            job_id, segment_name = parts

            # Find the job and segment in our shared state
            if job_id in job_data and segment_name in job_data[job_id].get("assets", {}).get("segments", {}):
                segment_state = job_data[job_id]["assets"]["segments"][segment_name]

                # Update job status based on the event
                if event_type == "avatar_video.success":
                    status = "success"
                    video_url = event_data.get("url")
                    segment_state["visual_status"] = "completed"
                    segment_state["heygen_video_url"] = video_url
                    segment_state.pop("error", None) # Clear previous error if any
                    logger.info(f"HeyGen Success | Job: {job_id} | Segment: {segment_name} | Video ID: {video_id} | URL: {video_url}")
                    active_jobs[job_id].append(f"[{datetime.now().isoformat()}] HeyGen video completed for {segment_name}.")

                    # Check if all assets are now ready for this job
                    if check_job_completion(job_id, job_data): # Pass job_data to checker
                        logger.info(f"[{job_id}] All assets ready. Triggering assembly and captioning.")
                        # Trigger assembly in the background, passing the specific job's data
                        current_job_data_snapshot = job_data.get(job_id, {}).copy() # Get a copy of the data for the task
                        if current_job_data_snapshot:
                            background_tasks.add_task(run_assembly_and_captioning, job_id, current_job_data_snapshot)
                        else:
                            logger.error(f"[{job_id}] Could not retrieve job data snapshot for background task.")
                        # TODO: Remove this warning once background task confirmed working
                        # logger.warning(f"[{job_id}] Assembly triggering logic needs implementation (e.g., via BackgroundTasks).")

                elif event_type == "avatar_video.fail":
                    status = "failed"
                    # Try to get the specific message, fall back to default
                    error_message = event_data.get("msg", event_data.get("error", "Unknown failure reason"))
                    segment_state["visual_status"] = "failed"
                    segment_state["error"] = error_message
                    logger.error(f"HeyGen Failure | Job: {job_id} | Segment: {segment_name} | Video ID: {video_id} | Error: {error_message}")
                    active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Error: HeyGen video failed for {segment_name}: {error_message}")
                    # Optionally update overall job status here too
                    # job_data[job_id]["status"] = "failed"
                    # job_data[job_id]["error"] = f"HeyGen segment {segment_name} failed: {error_message}"

                # Check completion and potentially trigger next step
                if check_job_completion(job_id):
                    logger.info(f"[{job_id}] All assets ready. Triggering assembly and captioning.")
                    # Run assembly in background to avoid blocking webhook response
                    # Need BackgroundTasks dependency here
                    # Get BackgroundTasks instance - requires modification to endpoint signature
                    # For now, log that it SHOULD trigger. Actual triggering needs endpoint change.
                    logger.warning(f"[{job_id}] TODO: Need BackgroundTasks in webhook handler to trigger assembly.")
                    # Example (requires adding background_tasks: BackgroundTasks = Depends() to endpoint):
                    # background_tasks.add_task(run_assembly_and_captioning, job_id)
                else:
                    logger.info(f"[{job_id}] Job not yet ready for assembly after segment '{segment_name}' update.")

            else:
                logger.error(f"Webhook received for unknown job_id '{job_id}' or segment_name '{segment_name}'. Callback ID: {callback_id_str}")
                # Still return 200 to HeyGen, but log the error

        except Exception as e:
            logger.error(f"Error updating job state for callback_id {callback_id_str}: {e}", exc_info=True)
            # Don't return 500 to HeyGen if possible, just log our internal error

        # --- End Update Job State ---

        # Future step: Find the job in active_jobs/job_data using callback_id and update its status
    except json.JSONDecodeError:
        raw_body = await request.body()
        logger.error(f"Failed to decode HeyGen webhook JSON. Raw body: {raw_body.decode()}")
        return JSONResponse(content={"status": "received"})
    except Exception as e:
        logger.error(f"Error processing HeyGen webhook: {e}", exc_info=True)
        # Still return 200 to HeyGen to avoid retries if possible,
        # but log the internal error.
        return JSONResponse(content={"status": "received"})

    # Respond quickly to HeyGen
    return JSONResponse(content={"status": "received"})

@app.options("/webhooks/heygen")
async def options_heygen_webhook():
    return JSONResponse(content={"status": "ok"}, headers={
        "Access-Control-Allow-Origin": "*", # Be more specific in production
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    })
# --- End HeyGen Webhook Receiver ---

# --- Argil Webhook Receiver ---
@app.post("/webhooks/argil")
async def handle_argil_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle callbacks from Argil API"""
    try:
        payload = await request.json()
        logger.info(f"Received Argil webhook: {json.dumps(payload, indent=2)}")

        event_type = payload.get("event")
        event_data = payload.get("data", {})
        video_id = event_data.get("videoId")
        # Assuming callback_id is passed in extras like: {"callback_id": "jobid__segmentname"}
        extras = event_data.get("extras", {})
        callback_id_str = extras.get("callback_id")

        if event_type not in ["VIDEO_GENERATION_SUCCESS", "VIDEO_GENERATION_FAILED"]:
            logger.warning(f"Received and ignoring Argil event type: {event_type} | Callback ID: {callback_id_str}")
            return JSONResponse(content={"status": "received", "message": "Event type ignored"})

        if not callback_id_str:
            logger.error(f"Received Argil webhook event {event_type} for video {video_id} without a callback_id in extras. Cannot update job state.")
            return JSONResponse(content={"status": "received", "message": "Missing callback_id in extras"})

        try:
            parts = callback_id_str.split("__", 1)
            if len(parts) != 2:
                logger.error(f"Could not parse job_id and segment_name from Argil callback_id: {callback_id_str}")
                return JSONResponse(content={"status": "received", "message": "Invalid callback_id format"})
            job_id, segment_name = parts

            # --- MODIFICATION START: Handle unknown job_id by creating a minimal entry ---
            if job_id not in job_data:
                logger.info(f"Argil webhook for new or externally managed job_id '{job_id}'. Creating minimal entry in job_data.")
                job_data[job_id] = {
                    "workflow_type": "argil_external", # Mark as externally triggered
                    "job_id": job_id,
                    "status": "processing_webhook", # Initial status upon first webhook
                    "creation_time": datetime.now().isoformat(),
                    "assets": {
                        "segments": {}
                    },
                    "logs": [f"[{datetime.now().isoformat()}] First webhook received for external job. Parsed segment: {segment_name}"]
                }
                if job_id not in active_jobs: active_jobs[job_id] = [] # Ensure log list for active_jobs too
                active_jobs[job_id].append(f"[{datetime.now().isoformat()}] First webhook for external job {job_id}, segment {segment_name}")

            # Ensure segment entry exists
            if "segments" not in job_data[job_id].get("assets", {}): # Should be created above if job_id was new
                 job_data[job_id]["assets"]["segments"] = {}

            if segment_name not in job_data[job_id]["assets"]["segments"]:
                logger.info(f"Argil webhook for new segment '{segment_name}' within job_id '{job_id}'. Creating minimal segment entry.")
                job_data[job_id]["assets"]["segments"][segment_name] = {
                    "type": "argil", # Assume type based on webhook source
                    "visual_status": "processing_webhook", # Initial status
                    "argil_video_id": video_id, # Store video_id from current webhook
                    "logs": [f"[{datetime.now().isoformat()}] First webhook received for this segment."]
                }
            # --- MODIFICATION END ---

            if job_id in job_data and job_data[job_id].get("assets", {}).get("segments", {}).get(segment_name):
                # Ensure the segment type is Argil, though callback_id uniqueness should handle this
                # if job_data[job_id]["assets"]["segments"][segment_name].get("type") != "argil":
                #     logger.warning(f"Argil webhook for non-Argil segment? Job: {job_id}, Segment: {segment_name}. Ignoring.")
                #     return JSONResponse(content={"status": "received", "message": "Segment type mismatch"})

                segment_state = job_data[job_id]["assets"]["segments"][segment_name]

                if event_type == "VIDEO_GENERATION_SUCCESS":
                    video_url = event_data.get("videoUrl") # Argil uses videoUrl
                    segment_state["visual_status"] = "completed"
                    segment_state["argil_video_url"] = video_url # Store the Argil video URL
                    segment_state.pop("error", None)
                    logger.info(f"Argil Success | Job: {job_id} | Segment: {segment_name} | Video ID: {video_id} | URL: {video_url}")
                    if job_id not in active_jobs: active_jobs[job_id] = [] # Ensure log list exists
                    active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Argil video completed for {segment_name}.")

                elif event_type == "VIDEO_GENERATION_FAILED":
                    # Argil payload for failure might not have a specific error message in event_data directly.
                    # The main video object (if fetched via GET /videos/{id}) might have failureReason.
                    # For now, we'll log a generic message and the video_id.
                    error_message = f"Argil video generation failed for videoId {video_id}. Event: {event_data.get('videoName', 'N/A')}"
                    segment_state["visual_status"] = "failed"
                    segment_state["error"] = error_message
                    # Update video_id if it wasn't set at creation (e.g. first webhook for segment)
                    segment_state["argil_video_id"] = video_id
                    logger.error(f"Argil Failure | Job: {job_id} | Segment: {segment_name} | Video ID: {video_id} | Message: {error_message}")
                    if job_id not in active_jobs: active_jobs[job_id] = []
                    active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Error: Argil video failed for {segment_name}: {error_message}")
                    # Optionally update overall job status
                    # job_data[job_id]["status"] = "failed"
                    # job_data[job_id]["error"] = f"Argil segment {segment_name} failed: {error_message}"

                # Check for overall job completion and trigger assembly if ready
                if check_job_completion(job_id, job_data): # Pass job_data
                    logger.info(f"[{job_id}] All assets ready after Argil segment update. Triggering assembly and captioning.")
                    current_job_data_snapshot = job_data.get(job_id, {}).copy()
                    if current_job_data_snapshot:
                        background_tasks.add_task(run_assembly_and_captioning, job_id, job_data[job_id])
                    else:
                        logger.error(f"[{job_id}] Webhook: Could not retrieve job data snapshot for background assembly task after Argil update for job {job_id}.")
                else:
                    logger.info(f"[{job_id}] Job not yet ready for assembly after Argil segment '{segment_name}' update.")

            else:
                logger.error(f"Argil webhook received for job_id '{job_id}' segment_name '{segment_name}', but could not find/initialize state in job_data. Callback ID: {callback_id_str}")

        except Exception as e:
            logger.error(f"Error processing Argil callback_id {callback_id_str} or updating job state: {e}", exc_info=True)

    except json.JSONDecodeError:
        raw_body = await request.body()
        logger.error(f"Failed to decode Argil webhook JSON. Raw body: {raw_body.decode()}")
        return JSONResponse(content={"status": "error", "message": "Invalid JSON"}, status_code=400)
    except Exception as e:
        logger.error(f"Error processing Argil webhook: {e}", exc_info=True)
        return JSONResponse(content={"status": "error", "message": "Internal server error"}, status_code=500)

    return JSONResponse(content={"status": "received"})

@app.options("/webhooks/argil")
async def options_argil_webhook():
    return JSONResponse(content={"status": "ok"}, headers={
        "Access-Control-Allow-Origin": "*", # Be more specific in production
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Api-Key", # Added X-Api-Key if Argil sends it
    })
# --- End Argil Webhook Receiver ---

# --- Workflow Test Endpoints ---
@app.post("/v2/workflow/heygen/start/{script_filename}", dependencies=[Depends(verify_authentication)])
async def start_heygen_workflow_v2(script_filename: str, background_tasks: BackgroundTasks):
    """
    Endpoint to trigger the HeyGen workflow.
    Uses a script filename (e.g., 'script2.md') from the 'public/' directory.
    Requires NGROK_PUBLIC_URL env var to be set for webhooks.
    """
    job_id = f"heygen_job_{uuid.uuid4()}"
    logger.info(f"Received request to start HeyGen workflow with job_id: {job_id} for script: {script_filename}")

    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    script_path = os.path.join(workspace_root, "public", script_filename)

    if not os.path.exists(script_path):
        logger.error(f"Script file not found at calculated path: {script_path}")
        raise HTTPException(status_code=404, detail=f"Script file '{script_filename}' not found in public directory.")

    # Pass the global job_data and active_jobs dictionaries to the background task
    background_tasks.add_task(run_heygen_workflow, job_id, script_path, job_data, active_jobs)
    logger.info(f"Added HeyGen workflow task to background for job_id: {job_id}")
    return {"job_id": job_id, "status": "initiated", "message": "HeyGen workflow started."}

@app.post("/v2/workflow/argil/start/{script_filename}", dependencies=[Depends(verify_authentication)])
async def start_argil_workflow_v2(script_filename: str, background_tasks: BackgroundTasks):
    """
    Endpoint to trigger the Argil workflow.
    Uses a script filename (e.g., 'script2.md') from the 'public/' directory.
    Requires NGROK_PUBLIC_URL and ARGIL_API_KEY env vars to be set.
    """
    job_id = f"argil_job_{uuid.uuid4()}"
    logger.info(f"Received request to start Argil workflow with job_id: {job_id} for script: {script_filename}")

    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    script_path = os.path.join(workspace_root, "public", script_filename)

    if not os.path.exists(script_path):
        logger.error(f"Script file not found at calculated path: {script_path}")
        raise HTTPException(status_code=404, detail=f"Script file '{script_filename}' not found in public directory.")

    # Pass the global job_data and active_jobs dictionaries to the background task
    background_tasks.add_task(run_argil_workflow, job_id, script_path, job_data, active_jobs)
    logger.info(f"Added Argil workflow task to background for job_id: {job_id}")
    return {"job_id": job_id, "status": "initiated", "message": "Argil workflow started."}

# --- Assembly and Captioning Runner (called by webhooks after check_job_completion) ---
# This function is defined in heygen_workflow.py but might be better placed in main.py
# or a shared utility module if it handles multiple workflow types.
# For now, let's assume it's available or we redefine/adapt it here.

def run_assembly_and_captioning(job_id: str, current_job_data_for_assembly: Dict[str, Any]):
    """
    Orchestrates the video assembly and captioning process for a completed job.
    Accepts the specific job_data dictionary for the job to perform assembly.
    This function MODIFIES current_job_data_for_assembly with results.
    """
    logger.info(f"[{job_id}] Initiating assembly and captioning. Workflow type: {current_job_data_for_assembly.get('workflow_type')}")
    active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Assembly and captioning process started.")
    current_job_data_for_assembly["status"] = "assembling"

    raw_video_path = None
    workflow_type = current_job_data_for_assembly.get("workflow_type")

    try:
        # Ensure necessary output directories exist based on workflow type
        # The assembly functions themselves might also create job-specific subdirs
        # but the base 'output' dir per workflow type should be ensured here or in ensure_directories.
        if workflow_type == "argil":
            output_dir = os.path.join(assets_dir, "argil_workflow", "output")
        elif workflow_type == "heygen":
            output_dir = os.path.join(assets_dir, "heygen_workflow", "output")
        else: # Default or original workflow
            output_dir = os.path.join(assets_dir, "output") # General output
        os.makedirs(output_dir, exist_ok=True)

        logger.info(f"[{job_id}] Running video assembly for {workflow_type} workflow.")

        if workflow_type == "argil":
            raw_video_path = assemble_argil_video(
                job_id=job_id,
                job_data=current_job_data_for_assembly,
                final_output_dir=output_dir
            )
        elif workflow_type == "heygen":
            raw_video_path = assemble_heygen_video(
                job_id=job_id,
                job_data=current_job_data_for_assembly,
                final_output_dir=output_dir
            )
        else:
            error_msg = f"Unknown workflow type '{workflow_type}' for job {job_id}. Cannot assemble."
            logger.error(f"[{job_id}] {error_msg}")
            current_job_data_for_assembly["status"] = "failed"
            current_job_data_for_assembly["error"] = error_msg
            active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Error: {error_msg}")
            return

        if not raw_video_path or not os.path.exists(raw_video_path):
            error_msg = f"Assembly failed or raw video not found for job {job_id} (workflow: {workflow_type})"
            logger.error(f"[{job_id}] {error_msg}")
            current_job_data_for_assembly["status"] = "assembly_failed"
            current_job_data_for_assembly["error"] = error_msg
            active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Error: {error_msg}")
            return

        current_job_data_for_assembly["final_video_path_raw"] = raw_video_path
        current_job_data_for_assembly["status"] = "assembly_complete"
        logger.info(f"[{job_id}] Raw video assembly successful: {raw_video_path}")
        active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Raw video assembly successful: {os.path.basename(raw_video_path)}.")

        # --- Captioning Step (common for all workflows if raw video is produced) ---
        logger.info(f"[{job_id}] Starting captioning process for {raw_video_path}")
        current_job_data_for_assembly["status"] = "captioning"
        active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Generating captions...")
        try:
            # Define where SRT files should be stored, possibly per workflow
            if workflow_type == "argil":
                captions_base_dir = os.path.join(assets_dir, "argil_workflow", "captions")
            elif workflow_type == "heygen":
                captions_base_dir = os.path.join(assets_dir, "heygen_workflow", "captions")
            else:
                captions_base_dir = os.path.join(assets_dir, "captions") # General captions
            os.makedirs(captions_base_dir, exist_ok=True)
            srt_file_path = os.path.join(captions_base_dir, f"{job_id}.srt")

            # The add_bottom_captions function needs to know where to save the SRT
            # and what the script content is. Script content should be in current_job_data_for_assembly["parsed_script"]
            # We might need a more generic caption generation function if create_captions is too specific.
            # For now, assuming add_bottom_captions is adaptable or we use a placeholder.

            # Placeholder for script text extraction for captions
            # This needs to be robust. The full script text might be assembled from segments.
            script_text_for_captions = "Caption script text not fully implemented here. Placeholder."
            parsed_script_data = current_job_data_for_assembly.get("parsed_script")
            if parsed_script_data and parsed_script_data.get("full_script_text"): # Assuming full_script_text is available
                script_text_for_captions = parsed_script_data["full_script_text"]
            elif parsed_script_data and parsed_script_data.get("script_segments"):
                # Concatenate voiceovers from segments if full_script_text isn't directly available
                texts = []
                ordered_segment_names_for_caption = list(parsed_script_data.get("script_segments", {}).keys())
                ordered_segment_names_for_caption = [name for name in ordered_segment_names_for_caption if name != "production_notes"]
                for seg_name in ordered_segment_names_for_caption:
                    segment = parsed_script_data["script_segments"].get(seg_name)
                    if segment and segment.get("voiceover"):
                        texts.append(segment["voiceover"])
                script_text_for_captions = " ".join(texts)

            # This part needs to be confirmed based on how create_captions function works.
            # It typically needs an audio file to transcribe, or pre-segmented text with timings.
            # For now, we use the existing add_bottom_captions which implies Whisper is run on the raw video.
            # If SRT is already generated from a previous step (e.g. by tts.py or generate_captions.py), use that.
            caption_file_path = current_job_data_for_assembly.get("caption_file_path") # Check if SRT was pre-generated

            if caption_file_path and os.path.exists(caption_file_path):
                 logger.info(f"[{job_id}] Using pre-existing SRT file for captions: {caption_file_path}")
                 captioned_video_path = create_captions_func(raw_video_path, srt_file_path=caption_file_path)
            elif current_job_data_for_assembly.get("final_video_path_raw") and script_text_for_captions: # Check if raw video audio can be used
                logger.info(f"[{job_id}] Generating captions by transcribing raw video and aligning with script text...")
                # This implies add_bottom_captions can take the raw video and script text
                # to generate and burn captions. This might need adjustment in add_bottom_captions itself.
                # For a robust solution, a dedicated SRT generation step is better if not using Whisper on final raw audio.

                # Let's assume add_bottom_captions can handle Whisper internally if no SRT is given
                # or we need a separate create_srt_from_audio function first.
                # The current create_captions.py takes audio and script, not video.
                # For simplicity, we'll assume add_bottom_captions can get audio from raw_video_path for Whisper.
                captioned_video_path = create_captions_func(raw_video_path) # This will run Whisper on the raw_video_path audio
                # The add_bottom_captions should also save the SRT it generates, and we should store its path.
                # Let's assume it returns the video path AND saves SRT like: video_path.replace('.mp4', '.srt')
                generated_srt_path = raw_video_path.replace(".mp4", ".srt")
                if os.path.exists(generated_srt_path):
                    current_job_data_for_assembly["caption_file_path"] = generated_srt_path
                else: # Fallback if SRT naming convention is different
                    current_job_data_for_assembly["caption_file_path"] = os.path.join(captions_base_dir, f"{job_id}_final.srt")

            else:
                logger.warning(f"[{job_id}] Cannot generate captions. No pre-existing SRT and not enough info for on-the-fly generation.")
                raise Exception("Caption generation prerequisites not met.")


            if captioned_video_path and os.path.exists(captioned_video_path):
                current_job_data_for_assembly["final_video_path_captioned"] = captioned_video_path
                current_job_data_for_assembly["status"] = "completed"
                logger.info(f"[{job_id}] Captioning successful: {captioned_video_path}")
                active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Video completed with captions: {os.path.basename(captioned_video_path)}.")
                job_results[job_id] = captioned_video_path # Store final result for /get_video endpoint
            else:
                raise Exception("Captioning function did not return a valid path or file not found.")
        except Exception as e:
            error_msg = f"Captioning failed for job {job_id}: {e}"
            logger.error(f"[{job_id}] {error_msg}", exc_info=True)
            current_job_data_for_assembly["status"] = "captioning_failed"
            current_job_data_for_assembly["error"] = error_msg
            active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Error: {error_msg}")
            # If captioning fails, we can still consider the raw video as a partial success
            if raw_video_path:
                job_results[job_id] = raw_video_path # Store raw video path
                current_job_data_for_assembly["status"] = "completed_no_captions"
                logger.warning(f"[{job_id}] Proceeding with uncaptioned video due to captioning failure.")
                active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Video completed without captions: {os.path.basename(raw_video_path)}.")

    except Exception as e:
        error_msg = f"Video assembly or captioning process failed for job {job_id}: {e}"
        logger.exception(f"[{job_id}] {error_msg}") # Use logger.exception to include traceback
        current_job_data_for_assembly["status"] = "failed"
        current_job_data_for_assembly["error"] = error_msg
        active_jobs[job_id].append(f"[{datetime.now().isoformat()}] Error: {error_msg}")

    logger.info(f"[{job_id}] Assembly and captioning run finished. Final job status: {current_job_data_for_assembly.get('status', 'unknown')}")
# --- End Assembly and Captioning Runner ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.text_to_video.main:app", host="0.0.0.0", port=8000, reload=True)
