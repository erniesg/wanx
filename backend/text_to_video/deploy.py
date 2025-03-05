# deploy.py
import modal

# Create a Modal app
app = modal.App("wanx-backend")

# Define the Docker image using the Dockerfile
image = (
    modal.Image.from_dockerfile("Dockerfile")
    .add_local_dir(".", remote_path="/app/text_to_video")
)

# Define the ASGI app function
@app.function(image=image)
@modal.asgi_app()
def app_function():
    # Import your FastAPI app
    from text_to_video.main import app as fastapi_app
    return fastapi_app

# Run the app
if __name__ == "__main__":
    app.run()
