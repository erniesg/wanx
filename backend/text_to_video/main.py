from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header, Depends
from fastapi.responses import FileResponse, StreamingResponse
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

import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from create_tiktok import create_tiktok
# Import individual components for stepwise processing
from generate_script import generate_script
from tts import text_to_speech
from create_captions import create_captions
from ttv import generate_video
from editor import combine_audio_video_captions

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

app = FastAPI(
    title="Video Generation API",
    description="API for generating videos from text content with authentication required",
    version="1.0.0",
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

# Add this at the beginning of the file, after imports
# Ensure all necessary directories exist
def ensure_directories():
    """Create all necessary directories for the application"""
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    assets_dir = os.path.join(backend_dir, "assets")

    # Create directory structure
    directories = [
        os.path.join(assets_dir, "audio", "speech"),
        os.path.join(assets_dir, "videos"),
        os.path.join(backend_dir, "logs")
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    return backend_dir, assets_dir

# Call this function to ensure directories exist
backend_dir, assets_dir = ensure_directories()

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
        script = generate_script(content)

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
        captions_path = create_captions(audio_path, script, job_id)

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
        video_path = generate_video(script, job_id)

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
        final_video_path = combine_audio_video_captions(base_video_path, audio_path, captions_path, job_id)

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
    """
    if job_id not in job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    if step:
        # Return status for specific step
        if step not in job_data[job_id].get("steps", {}):
            raise HTTPException(status_code=404, detail=f"Step {step} not found")

        status = job_data[job_id]["steps"][step]
        details = job_data[job_id].get(f"{step}_details", {})

        return StepStatusResponse(
            status=status,
            details=details
        )
    else:
        # Return overall status
        overall_status = calculate_overall_status(job_data[job_id])
        progress = calculate_progress(job_data[job_id])

        return WorkflowStatusResponse(
            job_id=job_id,
            status=overall_status,
            steps=StepStatus(**job_data[job_id]["steps"]),
            progress=progress,
            error=job_data[job_id].get("error")
        )

# Add this to the startup event
@app.on_event("startup")
async def startup_event():
    """Run when the application starts"""
    ensure_directories()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
