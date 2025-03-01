from fastapi import FastAPI, HTTPException, WebSocket, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import asyncio
import json
from typing import Dict, List, Optional
from create_tiktok import create_tiktok

app = FastAPI(title="Simple API")

class VideoRequest(BaseModel):
    content: str

# Store active generation jobs with their logs
active_jobs: Dict[str, List[str]] = {}

@app.get("/")
def read_root():
    return {"message": "Welcome to the Simple API"}

@app.post("/generate_video")
async def generate_video(request: VideoRequest):
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
        raise HTTPException(status_code=500, detail=f"Error generating video: {str(e)}")

# New endpoint to start a video generation job
@app.post("/live/start_generation")
async def start_generation(request: VideoRequest, background_tasks: BackgroundTasks):
    try:
        # Generate a unique job ID
        job_id = f"job_{len(active_jobs) + 1}_{os.urandom(4).hex()}"

        # Initialize empty log list for this job
        active_jobs[job_id] = []

        # Start the generation in the background
        background_tasks.add_task(
            run_generation_with_logs,
            job_id=job_id,
            content=request.content
        )

        return {"job_id": job_id, "status": "processing"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting generation: {str(e)}")

# Function to run generation and capture logs
async def run_generation_with_logs(job_id: str, content: str):
    try:
        # Add initial log
        active_jobs[job_id].append("Starting video generation...")

        # Run the generation (modify create_tiktok to accept a callback for logs)
        video_path = create_tiktok(
            content,
            log_callback=lambda msg: active_jobs[job_id].append(msg)
        )

        # Add final log with the result
        if video_path and os.path.exists(video_path):
            active_jobs[job_id].append(f"Video generated successfully: {video_path}")
            active_jobs[job_id].append("DONE:" + video_path)  # Special marker for completion
        else:
            active_jobs[job_id].append("Failed to generate video")
            active_jobs[job_id].append("ERROR:Generation failed")  # Special marker for error

    except Exception as e:
        active_jobs[job_id].append(f"Error: {str(e)}")
        active_jobs[job_id].append("ERROR:" + str(e))  # Special marker for error

# WebSocket endpoint for streaming logs
@app.websocket("/live/ws/logs/{job_id}")
async def websocket_logs(websocket: WebSocket, job_id: str):
    await websocket.accept()

    if job_id not in active_jobs:
        await websocket.send_json({"error": "Job not found"})
        await websocket.close()
        return

    # Send existing logs first
    for log in active_jobs[job_id]:
        await websocket.send_json({"log": log})

    # Track which logs we've sent
    last_sent_index = len(active_jobs[job_id])

    # Keep connection open to stream new logs
    try:
        while True:
            if job_id in active_jobs and len(active_jobs[job_id]) > last_sent_index:
                # Send new logs
                for log in active_jobs[job_id][last_sent_index:]:
                    await websocket.send_json({"log": log})

                    # Check if generation is complete or failed
                    if log.startswith("DONE:") or log.startswith("ERROR:"):
                        await websocket.close()
                        return

                last_sent_index = len(active_jobs[job_id])

            await asyncio.sleep(0.5)  # Check for new logs every 0.5 seconds
    except:
        # Handle disconnection
        pass

# Endpoint to check job status and get the video when complete
@app.get("/live/job_status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    logs = active_jobs[job_id]

    # Check if job is complete
    for log in logs:
        if log.startswith("DONE:"):
            video_path = log.replace("DONE:", "")
            return {"status": "complete", "video_path": video_path}
        elif log.startswith("ERROR:"):
            error_msg = log.replace("ERROR:", "")
            return {"status": "error", "error": error_msg}

    return {"status": "processing", "logs": logs}

# Endpoint to get the generated video
@app.get("/live/get_video/{job_id}")
async def get_video(job_id: str):
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    # Find the video path from logs
    video_path = None
    for log in active_jobs[job_id]:
        if log.startswith("DONE:"):
            video_path = log.replace("DONE:", "")
            break

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found or generation not complete")

    # Return the video file
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=os.path.basename(video_path)
    )

# Optional: Cleanup job after some time
@app.delete("/live/cleanup/{job_id}")
async def cleanup_job(job_id: str):
    if job_id in active_jobs:
        del active_jobs[job_id]
        return {"status": "cleaned up"}
    return {"status": "job not found"}

# Add this temporary debug endpoint
@app.get("/debug/job_logs/{job_id}")
async def debug_job_logs(job_id: str):
    if job_id not in active_jobs:
        return {"error": "Job not found"}
    return {"logs": active_jobs[job_id]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
