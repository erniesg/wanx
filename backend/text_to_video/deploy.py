# deploy.py
import modal
import os

# Create a Modal app
app = modal.App("wanx-backend")

# Get the current directory and parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))  # text_to_video directory
project_root = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels to reach project root

# Load secrets from .env file in project root
env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
    print(f"Loading secrets from {env_path}")
    secrets = modal.Secret.from_dotenv(env_path)
else:
    print(f"Warning: .env file not found at {env_path}")
    secrets = modal.Secret.from_dict({})

# Define the image using debian_slim base
image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install(["ffmpeg"])
    # Install core dependencies first with exact versions
    .pip_install([
        "pydantic==2.10.6",
        "instructor==1.7.2",
        "fastapi==0.104.1",
        "typer==0.9.0",
        "rich==13.7.0",
        "aiohttp==3.9.1"
    ])
    # Install torch separately first
    .pip_install("torch==2.6.0")
    # Install whisper with its dependencies
    .pip_install([
        "numba==0.61.0",
        "openai-whisper==20240930"
    ])
    # Then install remaining requirements
    .pip_install_from_requirements("requirements.txt", force_build=True)
    .add_local_dir(".", remote_path="/app/text_to_video")
)

# Define the ASGI app function
@app.function(
    image=image,
    secrets=[secrets]  # Add secrets to the function
)
@modal.asgi_app()
def app_function():
    import sys

    # Debug prints
    print("Current working directory:", os.getcwd())
    print("Directory contents of /app:", os.listdir("/app"))
    print("Python path:", sys.path)

    # Verify environment variables are set
    required_env_vars = [
        "JIGSAW_API_KEY",
        "GROQ_API_KEY",
        "DASHSCOPE_API_KEY",
        "REPLICATE_API_TOKEN",
        "VITE_API_URL",
        "ELEVENLABS_API_KEY"
    ]

    for var in required_env_vars:
        if var not in os.environ:
            print(f"Warning: {var} is not set in environment")
        else:
            print(f"Found {var} in environment")

    # Try both paths
    sys.path.append("/app")
    sys.path.append(os.getcwd())

    try:
        from main import app as fastapi_app
        return fastapi_app
    except ImportError as e:
        print(f"Failed to import from main directly: {e}")
        try:
            from text_to_video.main import app as fastapi_app
            return fastapi_app
        except ImportError as e:
            print(f"Failed to import from text_to_video.main: {e}")
            raise

# Run the app
if __name__ == "__main__":
    app.run()
