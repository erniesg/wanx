from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from create_tiktok import create_tiktok

app = FastAPI(title="Simple API")

class VideoRequest(BaseModel):
    content: str

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
