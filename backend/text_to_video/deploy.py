# deploy.py
import modal
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("modal-deploy")

# Create a Modal app
app = modal.App("wanx-backend")

# Get the current directory and parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))  # text_to_video directory
project_root = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels to reach project root

# Load secrets from .env file in project root
env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
    logger.info(f"Loading secrets from {env_path}")
    secrets = modal.Secret.from_dotenv(env_path)
else:
    logger.warning(f"Warning: .env file not found at {env_path}")
    secrets = modal.Secret.from_dict({})

# Define the image using debian_slim base
image = (
    modal.Image.debian_slim(python_version="3.10")
    # Install system dependencies including ImageMagick
    .apt_install([
        "ffmpeg",
        "imagemagick",
        "libmagick++-dev",
        "ghostscript"  # Required for some ImageMagick operations
    ])
    # Configure ImageMagick policy to allow text operations
    .run_commands([
        'bash -c \'echo "<policymap><policy domain=\\"path\\" rights=\\"read | write\\" pattern=\\"@*\\"/><policy domain=\\"path\\" rights=\\"read | write\\" pattern=\\"/tmp/*\\"/><policy domain=\\"coder\\" rights=\\"read | write\\" pattern=\\"PNG\\"/><policy domain=\\"coder\\" rights=\\"read | write\\" pattern=\\"LABEL\\"/><policy domain=\\"coder\\" rights=\\"read | write\\" pattern=\\"TEXT\\"/></policymap>" > /etc/ImageMagick-6/policy.xml\'',
        'chmod 1777 /tmp'
    ])
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
    secrets=[secrets]
)
@modal.asgi_app()
def app_function():
    import sys
    import logging

    # Configure logging for the FastAPI application
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )
    logger = logging.getLogger("modal-app")
    logger.info("Starting FastAPI application in Modal")

    # Test ImageMagick configuration
    try:
        import subprocess
        print("\n--- Testing ImageMagick Configuration ---")

        # Test 1: Check ImageMagick version
        version_cmd = subprocess.run(['convert', '-version'], capture_output=True, text=True)
        print("ImageMagick version:", version_cmd.stdout.split('\n')[0])

        # Test 2: Check policy file
        with open('/etc/ImageMagick-6/policy.xml', 'r') as f:
            print("\nImageMagick policy file contents:")
            print(f.read())

        # Test 3: Test text-to-image conversion
        test_cmd = subprocess.run(
            ['convert', 'label:test', '/tmp/test.png'],
            capture_output=True,
            text=True
        )
        if test_cmd.returncode == 0:
            print("\nText-to-image conversion test: SUCCESS")
        else:
            print("\nText-to-image conversion test: FAILED")
            print("Error:", test_cmd.stderr)

        # Test 4: Check /tmp permissions
        tmp_perms = subprocess.run(['ls', '-ld', '/tmp'], capture_output=True, text=True)
        print("\n/tmp directory permissions:", tmp_perms.stdout)

    except Exception as e:
        print("Error during ImageMagick tests:", str(e))

    print("\n--- End ImageMagick Tests ---\n")

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
        from text_to_video.main import app as fastapi_app
        logger.info("Successfully imported FastAPI app")
        return fastapi_app
    except ImportError as e:
        logger.error(f"Failed to import from text_to_video.main: {e}")
        raise

# Run the app
if __name__ == "__main__":
    logger.info("Deploying application to Modal")
    app.run()
