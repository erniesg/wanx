import os
import requests
import logging
from dotenv import load_dotenv
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEYGEN_API_ENDPOINT = "https://api.heygen.com/v2/video/generate"

def start_avatar_video_generation(
    api_key: str,
    avatar_id: str,
    background_url: str,
    webhook_url: str,
    callback_id: str,
    voice_text: str = None,
    voice_audio_url: str = None,
    voice_id: str = None, # Optional: HeyGen voice ID if using voice_text
    title: str = "Generated Video",
    test: bool = False # Set to True for test mode (doesn't send request)
) -> dict | None:
    """
    Starts a video generation job using the HeyGen API (v2).

    Args:
        api_key (str): Your HeyGen API key.
        avatar_id (str): The ID of the HeyGen avatar to use.
        background_url (str): URL of the background image or video.
        webhook_url (str): The URL HeyGen will call upon completion/failure.
        callback_id (str): A unique identifier you provide, returned in the webhook.
        voice_text (str, optional): Text for the avatar to speak (uses HeyGen TTS).
        voice_audio_url (str, optional): URL of a pre-generated audio file for lip-sync.
        voice_id (str, optional): HeyGen's internal voice ID (needed only if using voice_text and not voice_audio_url).
        title (str): Title for the video project in HeyGen.
        test (bool): If True, simulates the request without actually calling the API.

    Returns:
        dict | None: The JSON response from HeyGen API if successful, otherwise None.
                     Returns a simulation dict if test=True.
    """
    if not api_key:
        logger.error("HeyGen API key is missing.")
        return None
    if not webhook_url:
        logger.error("Webhook URL is required for status updates.")
        return None
    if not voice_text and not voice_audio_url:
        logger.error("Either voice_text or voice_audio_url must be provided.")
        return None
    if voice_text and not voice_audio_url and not voice_id:
        logger.error("HeyGen voice_id is required when using voice_text without a voice_audio_url.")
        return None

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": api_key
    }

    # Construct the voice part of the payload
    if voice_audio_url:
        voice_payload = {
            "type": "audio",
            "audio_url": voice_audio_url
        }
        logger.info("Using voice_audio_url for HeyGen voice payload.")
    else: # voice_text must be present
        voice_payload = {
            "type": "text",
            "input_text": voice_text,
            "voice_id": voice_id,
            # Optional speed/pitch params could be added here
        }
        logger.info("Using voice_text for HeyGen voice payload.")

    # Construct the main payload
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal", # Or other styles if needed
                    "offset": {"x": 0.0, "y": 0.25} # Changed for bottom-center placement
                },
                "voice": voice_payload,
                "background": {
                    "type": "image", # Assuming image for now, could be video
                    "url": background_url,
                    "fit": "crop"
                }
            }
            # Note: This structure is for a single scene.
            # For multi-scene videos like in the user example,
            # multiple dicts would go into 'video_inputs'.
            # This initial client focuses on single segment calls.
        ],
        "dimension": {
            "width": 720, # Reduced from 1080 to 720
            "height": 1280 # Reduced from 1920 to 1280
        },
        "title": title,
        "caption": False, # Captions disabled for now, handle separately
        "test": test, # Use HeyGen's test mode if specified
        "callback_id": callback_id,
        # Add callback_url explicitly for V2 if provided
        "callback_url": webhook_url
         # Explicitly adding webhook_url here if needed by API v2
         # The docs are a bit unclear if it's top-level or just for v1 webhook registration
         # Check HeyGen V2 API reference if callbacks don't work.
    }


    logger.info(f"Sending request to HeyGen API. Test mode: {test}. Callback ID: {callback_id}")
    logger.debug(f"HeyGen Payload: {payload}")

    if test:
        logger.info("Simulating HeyGen API call.")
        return {
            "success": True,
            "message": "Test mode enabled, request not sent.",
            "data": {"video_id": f"test_{uuid.uuid4()}"} # Simulate a video ID
        }

    try:
        response = requests.post(HEYGEN_API_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"HeyGen API response received: {response_data}")

        # Check for success indication in the response (structure might vary)
        if response_data.get("success", True): # Assume success if key missing, check API docs
            video_id = response_data.get("data", {}).get("video_id")
            logger.info(f"HeyGen video generation started successfully. Video ID: {video_id}")
            return response_data
        else:
            error_message = response_data.get("error", {}).get("message", "Unknown error")
            logger.error(f"HeyGen API returned an error: {error_message}")
            return None

    except requests.exceptions.Timeout:
        logger.error("HeyGen API request timed out.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"HeyGen API request failed: {e}")
        # Log response content if available
        if e.response is not None:
             logger.error(f"Response status: {e.response.status_code}")
             try:
                 logger.error(f"Response content: {e.response.text}")
             except Exception:
                 pass # Ignore if response content isn't easily readable
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during HeyGen API call: {e}")
        return None

# 13. Test HeyGen Client (Start Job)
if __name__ == "__main__":
    load_dotenv()
    heygen_api_key = os.getenv("HEYGEN_API_KEY")

    if not heygen_api_key:
        print("Error: HEYGEN_API_KEY not found in environment variables.")
    else:
        print("Testing HeyGen Client (Start Job)...")

        # --- Test Parameters ---
        # Use a publicly available Jin Vest avatar ID from HeyGen docs/examples
        test_avatar_id = "Jin_Vest_Front_public"
        # A sample voice ID (replace if you have a specific one, ensure it matches voice_text lang)
        test_voice_id = "f5d52985019847c5b0501a445c66dba8" # Jin - Professional voice ID from user example
        test_voice_text = "Hello from the HeyGen API test client!"
        # A generic background image URL
        test_background_url = "https://images.pexels.com/photos/265125/pexels-photo-265125.jpeg"
        # !! IMPORTANT: Replace with your actual ngrok URL when testing webhook !!
        test_webhook_url = "https://8420-112-199-131-111.ngrok-free.app/webhooks/heygen" # Placeholder
        test_callback_id = f"test_job_{uuid.uuid4()}"
        # --- End Test Parameters ---

        print(f"Using Avatar ID: {test_avatar_id}")
        print(f"Using Voice ID: {test_voice_id}")
        print(f"Using Text: '{test_voice_text}'")
        print(f"Using Background: {test_background_url}")
        print(f"Using Webhook URL: {test_webhook_url} <-- MAKE SURE THIS IS YOUR NGROK URL LATER")
        print(f"Using Callback ID: {test_callback_id}")

        # Set test=True for initial run to check payload without sending
        # Set test=False to actually call the API
        response = start_avatar_video_generation(
            api_key=heygen_api_key,
            avatar_id=test_avatar_id,
            background_url=test_background_url,
            webhook_url=test_webhook_url, # Pass the test webhook URL here
            callback_id=test_callback_id,
            voice_text=test_voice_text,
            voice_id=test_voice_id,
            title="Client Test Video",
            test=False # <-- Set to True initially
        )

        print("\n--- HeyGen Client Test Response ---")
        if response:
            import json
            print(json.dumps(response, indent=2))
            if response.get("success", True) and not response.get("message","").startswith("Test mode"):
                 print("\nSuccessfully initiated HeyGen video generation.")
            elif response.get("message","").startswith("Test mode"):
                 print("\nTest mode succeeded. Payload structure seems okay. Set test=False to run for real.")
            else:
                 print("\nHeyGen API call failed or returned an error.")
        else:
            print("\nHeyGen API call failed. Check logs.")

        print("\nHeyGen client test finished.")
