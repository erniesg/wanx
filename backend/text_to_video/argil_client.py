import os
import requests
import logging
import time
import re
import uuid
import random
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://api.argil.ai/v1"
TRANSCRIPT_CHAR_LIMIT = 250  # Based on user's observation from Argil API

# --- Default Configuration (from user examples) ---
DEFAULT_AVATAR_ID = "6c354b49-6536-4d29-8aaa-a0c8ea2dd406"  # Emma Veranda
DEFAULT_VOICE_ID = "82c8d578-4952-4f16-bcd2-d6ddb7fd1bae"    # Yara
DEFAULT_GESTURE_SLUGS = [f"gesture-{i}" for i in range(1, 9)] # gesture-1 to gesture-8

def _get_headers(api_key: str) -> dict:
    """Helper to generate standard API headers."""
    if not api_key:
        raise ValueError("ARGIL_API_KEY is not set.")
    return {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

def split_transcript_text(transcript: str, limit: int = TRANSCRIPT_CHAR_LIMIT) -> list[str]:
    """
    Splits a long transcript into chunks under the character limit.
    Adapted from user-provided script.
    """
    if not transcript: # Handle empty transcript early
        return []
    if len(transcript) <= limit:
        return [transcript]

    chunks = []
    current_chunk = ""
    # Use a regex that splits after a sentence-ending punctuation mark followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', transcript)

    for sentence_idx, sentence_text in enumerate(sentences):
        sentence = sentence_text.strip()
        if not sentence:
            continue

        if len(current_chunk) + len(sentence) + 1 <= limit:  # +1 for potential space
            current_chunk += (" " + sentence if current_chunk else sentence)
        else:
            # If adding the sentence exceeds limit, finalize the current chunk
            if current_chunk:
                chunks.append(current_chunk)

            # If the sentence itself is too long, split it hard
            if len(sentence) > limit:
                logger.warning(f"Sentence part (original sentence index {sentence_idx}) is longer than limit ({limit}), hard splitting: '{sentence[:50]}...'")
                for i in range(0, len(sentence), limit):
                    chunks.append(sentence[i:i + limit])
                current_chunk = ""  # Reset current chunk
            else:
                current_chunk = sentence  # Start new chunk with the current sentence

    if current_chunk:  # Add the last chunk
        chunks.append(current_chunk)

    # Final check if any chunk somehow still exceeds limit
    final_chunks = []
    for chunk_idx, chunk_text in enumerate(chunks):
        if len(chunk_text) > limit:
            logger.warning(f"Chunk {chunk_idx} (from sentence processing) still exceeds limit ({len(chunk_text)} > {limit}). Hard splitting: '{chunk_text[:50]}...'")
            for i in range(0, len(chunk_text), limit):
                final_chunks.append(chunk_text[i:i + limit])
        elif chunk_text: # Ensure no empty strings are added
            final_chunks.append(chunk_text)

    if not final_chunks and transcript: # If all splitting failed but there was transcript
        logger.warning(f"Transcript splitting resulted in no chunks, but original transcript was not empty. Hard splitting original. Length: {len(transcript)}")
        for i in range(0, len(transcript), limit):
            final_chunks.append(transcript[i:i+limit])

    return final_chunks


def create_argil_video_job(
    api_key: str,
    video_title: str,
    full_transcript: str,
    avatar_id: str = DEFAULT_AVATAR_ID,
    voice_id: str = DEFAULT_VOICE_ID,
    gesture_slugs: list[str] = None,
    aspect_ratio: str = "9:16",
    callback_id: str = None # For potential future use or logging
) -> dict | None:
    """
    Creates a video generation job with Argil.
    Splits transcript into moments and assigns gestures.
    """
    logger.info(f"Attempting to create Argil video job. Title: {video_title}, Callback ID: {callback_id}")
    if not api_key:
        logger.error("API key is missing for Argil.")
        return None

    if gesture_slugs is None:
        gesture_slugs = DEFAULT_GESTURE_SLUGS
    if not gesture_slugs: # Ensure there's at least one gesture to avoid errors
        logger.warning("No gesture slugs provided, using a default 'gesture-1'")
        gesture_slugs = ["gesture-1"]

    transcript_chunks = split_transcript_text(full_transcript, TRANSCRIPT_CHAR_LIMIT)
    if not transcript_chunks:
        logger.error(f"Transcript splitting resulted in no chunks for title: {video_title}. Original transcript: '{full_transcript[:100]}...'")
        return {"success": False, "error": "Transcript splitting failed", "details": "No chunks generated"}


    moments_payload = []
    for i, chunk in enumerate(transcript_chunks):
        gesture_slug = gesture_slugs[i % len(gesture_slugs)] # Cycle through gestures
        moments_payload.append({
            "transcript": chunk,
            "avatarId": avatar_id,
            "voiceId": voice_id,
            "gestureSlug": gesture_slug,
            # "zoom": {"level": 1} # Optional: add if needed
        })

    payload = {
        "name": video_title,
        "moments": moments_payload,
        "subtitles": {"enable": False},  # Captions handled separately
        "aspectRatio": aspect_ratio,
        # "autoBrolls": {"enable": False, "source": "AVATAR_ACTION"}, # Removed as we want B-rolls disabled
        # "backgroundMusic": {} # Music handled separately
        "extras": {}
    }
    if callback_id:
        payload["extras"]["callback_id"] = callback_id


    url = f"{BASE_URL}/videos"
    logger.debug(f"Argil create_video_job payload: {payload}")
    try:
        response = requests.post(url, headers=_get_headers(api_key), json=payload, timeout=30)
        response.raise_for_status()
        response_data = response.json()
        video_id = response_data.get("id")
        if video_id:
            logger.info(f"Argil video creation initiated. Video ID: {video_id}, Title: {video_title}")
            return {"success": True, "video_id": video_id, "data": response_data}
        else:
            logger.error(f"Argil video creation succeeded but no video ID returned. Response: {response_data}")
            return {"success": False, "error": "No video_id in response", "data": response_data}
    except requests.exceptions.Timeout:
        logger.error("Argil API request timed out during video creation.")
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Argil API request failed during video creation: {e}")
        error_details = "No response details"
        status_code = None
        if e.response is not None:
            status_code = e.response.status_code
            try:
                error_details = e.response.json() # Try to parse JSON error
            except ValueError:
                error_details = e.response.text # Fallback to text
            logger.error(f"Response status: {status_code}, content: {error_details}")
        return {"success": False, "error": str(e), "status_code": status_code, "details": error_details}
    except Exception as e:
        logger.error(f"An unexpected error occurred during Argil video creation: {e}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


def render_argil_video(api_key: str, video_id: str) -> dict | None:
    """Sends a request to render a previously created Argil video."""
    logger.info(f"Attempting to render Argil video. Video ID: {video_id}")
    if not api_key or not video_id:
        logger.error("API key or Video ID is missing for rendering.")
        return None

    url = f"{BASE_URL}/videos/{video_id}/render"
    try:
        response = requests.post(url, headers=_get_headers(api_key), timeout=30)
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"Argil video render request successful for Video ID: {video_id}. Initial status: {response_data.get('status')}")
        return {"success": True, "data": response_data}
    except requests.exceptions.Timeout:
        logger.error(f"Argil API request timed out during video render for ID: {video_id}.")
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Argil API request failed during video render for ID: {video_id}: {e}")
        error_details = "No response details"
        status_code = None
        if e.response is not None:
            status_code = e.response.status_code
            try:
                error_details = e.response.json()
            except ValueError:
                error_details = e.response.text
            logger.error(f"Response status: {status_code}, content: {error_details}")
        return {"success": False, "error": str(e), "status_code": status_code, "details": error_details}
    except Exception as e:
        logger.error(f"An unexpected error occurred during Argil video render for ID: {video_id}: {e}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


def get_argil_video_details(api_key: str, video_id: str) -> dict | None:
    """Fetches the status and details of an Argil video."""
    logger.debug(f"Fetching details for Argil video ID: {video_id}")
    if not api_key or not video_id:
        logger.error("API key or Video ID is missing for fetching details.")
        return None

    url = f"{BASE_URL}/videos/{video_id}"
    try:
        response = requests.get(url, headers=_get_headers(api_key), timeout=30)
        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Argil video details fetched for Video ID: {video_id}. Status: {response_data.get('status')}")
        return {"success": True, "data": response_data}
    except requests.exceptions.Timeout:
        logger.error(f"Argil API request timed out while fetching details for video ID: {video_id}.")
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Argil API request failed while fetching details for video ID: {video_id}: {e}")
        error_details = "No response details"
        status_code = None
        if e.response is not None:
            status_code = e.response.status_code
            try:
                error_details = e.response.json()
            except ValueError:
                error_details = e.response.text
            logger.error(f"Response status: {status_code}, content: {error_details}")
        return {"success": False, "error": str(e), "status_code": status_code, "details": error_details}
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching Argil video details for ID: {video_id}: {e}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


def list_argil_webhooks(api_key: str) -> dict | None:
    """Lists all registered webhooks for the Argil account."""
    logger.info("Listing Argil webhooks.")
    if not api_key:
        logger.error("API key is missing for listing Argil webhooks.")
        return None

    url = f"{BASE_URL}/webhooks"
    try:
        response = requests.get(url, headers=_get_headers(api_key), timeout=30)
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"Successfully listed {len(response_data)} Argil webhooks.")
        return {"success": True, "data": response_data}
    except requests.exceptions.Timeout:
        logger.error("Argil API request timed out while listing webhooks.")
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Argil API request failed while listing webhooks: {e}")
        error_details = "No response details"
        status_code = None
        if e.response is not None:
            status_code = e.response.status_code
            try:
                error_details = e.response.json()
            except ValueError:
                error_details = e.response.text
            logger.error(f"Response status: {status_code}, content: {error_details}")
        return {"success": False, "error": str(e), "status_code": status_code, "details": error_details}
    except Exception as e:
        logger.error(f"An unexpected error occurred while listing Argil webhooks: {e}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


def create_argil_webhook(api_key: str, callback_url: str, events: list[str]) -> dict | None:
    """Creates a new webhook registration with Argil."""
    logger.info(f"Attempting to create Argil webhook. Callback URL: {callback_url}, Events: {events}")
    if not api_key or not callback_url or not events:
        logger.error("API key, callback URL, or events list is missing for creating Argil webhook.")
        return None

    payload = {
        "callbackUrl": callback_url,
        "events": events
    }
    url = f"{BASE_URL}/webhooks"
    logger.debug(f"Argil create_webhook payload: {payload}")
    try:
        response = requests.post(url, headers=_get_headers(api_key), json=payload, timeout=30)
        response.raise_for_status()
        response_data = response.json()
        webhook_id = response_data.get("id")
        if webhook_id:
            logger.info(f"Argil webhook creation successful. Webhook ID: {webhook_id}, URL: {callback_url}")
            return {"success": True, "webhook_id": webhook_id, "data": response_data}
        else:
            logger.error(f"Argil webhook creation succeeded but no webhook ID returned. Response: {response_data}")
            return {"success": False, "error": "No webhook_id in response", "data": response_data}
    except requests.exceptions.Timeout:
        logger.error(f"Argil API request timed out during webhook creation for URL: {callback_url}.")
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Argil API request failed during webhook creation for URL: {callback_url}: {e}")
        error_details = "No response details"
        status_code = None
        if e.response is not None:
            status_code = e.response.status_code
            try:
                error_details = e.response.json()
            except ValueError:
                error_details = e.response.text
            logger.error(f"Response status: {status_code}, content: {error_details}")
        return {"success": False, "error": str(e), "status_code": status_code, "details": error_details}
    except Exception as e:
        logger.error(f"An unexpected error occurred during Argil webhook creation: {e}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


if __name__ == "__main__":
    load_dotenv()
    argil_api_key = os.getenv("ARGIL_API_KEY")
    ngrok_public_url = os.getenv("NGROK_PUBLIC_URL")

    if not argil_api_key:
        print("Error: ARGIL_API_KEY not found in environment variables. Please set it in your .env file.")
    else:
        print("Testing Argil Client...")

        # --- Test Webhook Management ---
        print("\n--- Test Webhook Management ---")
        if not ngrok_public_url:
            print("NGROK_PUBLIC_URL not set in .env, skipping webhook creation test.")
        else:
            test_webhook_callback_url = f"{ngrok_public_url.rstrip('/')}/webhooks/argil_test_endpoint"
            test_webhook_events = ["VIDEO_GENERATION_SUCCESS", "VIDEO_GENERATION_FAILED"]
            print(f"Target test webhook URL: {test_webhook_callback_url}")

            list_resp = list_argil_webhooks(argil_api_key)
            webhook_exists = False
            if list_resp and list_resp.get("success"):
                for wh in list_resp["data"]:
                    if wh.get("callbackUrl") == test_webhook_callback_url and sorted(wh.get("events", [])) == sorted(test_webhook_events):
                        print(f"Test webhook already exists with ID: {wh.get('id')}")
                        webhook_exists = True
                        break

            if not webhook_exists:
                print("Attempting to create a test webhook...")
                create_wh_resp = create_argil_webhook(argil_api_key, test_webhook_callback_url, test_webhook_events)
                if create_wh_resp and create_wh_resp.get("success"):
                    print(f"Test webhook created successfully: {create_wh_resp.get('webhook_id')}")
                else:
                    err_msg = create_wh_resp.get('error') if create_wh_resp else 'No response'
                    details_msg = create_wh_resp.get('details') if create_wh_resp else ''
                    print(f"Failed to create test webhook. Error: {err_msg}. Details: {details_msg}")
            else:
                print("Skipping creation as a suitable test webhook already exists.")

        # --- Original Video Generation Test ---
        test_video_title = f"Argil Client Test {uuid.uuid4()}"

        # Test script that is intentionally long and has multiple sentences.
        test_script = (
            "This is the first sentence of our test script. It's designed to be significantly longer than 250 characters to properly "
            "evaluate if the transcript splitting mechanism works as intended when faced with lengthy input. Let's add some more verbose "
            "text here to make absolutely sure we cross that critical threshold by a good margin. Argil's API has specific character limits "
            "per moment, so ensuring this functionality is robust is absolutely crucial for reliable video generation. This is the second major part "
            "of the script, which will also be split. We are currently testing the client library specifically developed for interacting with "
            "the Argil platform, which is intended to handle various aspects of the video creation process including, but not limited to, "
            "initial job submission, the rendering phase, and periodic status polling to check for completion or failure. Each distinct segment "
            "of the overall script will eventually become an individual 'moment' within the Argil payload structure. We have the capability "
            "to assign different or specific gestures to each of these moments, or alternatively, we can cycle through a predefined list of "
            "available gestures for variety. The ultimate goal is to achieve seamless and effective integration with the existing video workflow. "
            "This is a final concluding sentence for this comprehensive test, ensuring that all edge cases and splitting scenarios are "
            "thoroughly covered before deployment."
        )
        short_test_script = "This is a short script. It should not be split." # Example of a short script

        test_callback_id = f"argil_job_test_{uuid.uuid4()}" # Unique ID for job tracking via extras

        print(f"\n--- Test 1: Create Argil Video Job ---")
        print(f"Video Title: {test_video_title}")
        print(f"Avatar ID: {DEFAULT_AVATAR_ID}")
        print(f"Voice ID: {DEFAULT_VOICE_ID}")
        print(f"Callback ID (Extras): {test_callback_id}")

        # Using the long script for testing splitting
        creation_response = create_argil_video_job(
            api_key=argil_api_key,
            video_title=test_video_title,
            full_transcript=test_script,
            avatar_id=DEFAULT_AVATAR_ID,
            voice_id=DEFAULT_VOICE_ID,
            aspect_ratio="9:16", # or "16:9"
            callback_id=test_callback_id # This will be placed in payload.extras.callback_id
        )

        if creation_response and creation_response.get("success"):
            test_video_id = creation_response.get("video_id")
            print(f"Successfully initiated video creation. Video ID: {test_video_id}")
            # print(f"Full creation response data: {creation_response.get('data')}") # Can be verbose

            print(f"\n--- Test 2: Render Argil Video ---")
            render_response = render_argil_video(argil_api_key, test_video_id)

            if render_response and render_response.get("success"):
                print(f"Successfully requested video rendering for ID: {test_video_id}")
                # print(f"Initial render status data: {render_response.get('data')}")

                print(f"\n--- Test 3: Poll for Video Status (if webhook not used/for immediate feedback) ---")
                print("(Note: In a real scenario, we'd primarily rely on webhooks for completion notification)")
                max_checks = 10  # Check every 30s for 5 mins
                check_interval = 30  # seconds
                video_done_or_failed = False

                for i in range(max_checks):
                    print(f"Polling attempt {i+1}/{max_checks}...")
                    status_details_response = get_argil_video_details(argil_api_key, test_video_id)

                    if status_details_response and status_details_response.get("success"):
                        video_data = status_details_response.get("data", {})
                        current_status = video_data.get("status")
                        print(f"Current video status: {current_status}")

                        if current_status == "DONE":
                            print("Video generation complete!")
                            print(f"Video URL: {video_data.get('videoUrl')}")
                            # print(f"Subtitled URL: {video_data.get('videoUrlSubtitled')}") # Argil provides this
                            # print(f"Full video data: {video_data}")
                            video_done_or_failed = True
                            break
                        elif current_status == "FAILED":
                            print("Video generation failed.")
                            print(f"Failure reason: {video_data.get('failureReason') or video_data}")
                            video_done_or_failed = True
                            break
                        elif current_status in ["PENDING", "PROCESSING", "RENDERING", "UPLOADING_ASSETS", "GENERATING_VIDEO", "GENERATING_AUDIO"]:
                            print(f"Video is still processing ({current_status}). Waiting {check_interval}s...")
                            time.sleep(check_interval)
                        else: # Unknown status
                            logger.warning(f"Unknown video status encountered: {current_status}. Waiting {check_interval}s...")
                            time.sleep(check_interval)
                    else:
                        err_msg = status_details_response.get('error') if status_details_response else 'No response'
                        details_msg = status_details_response.get('details') if status_details_response else ''
                        print(f"Failed to get video status: {err_msg}. Details: {details_msg}")
                        time.sleep(check_interval)

                if not video_done_or_failed:
                    print("Video did not complete or fail within the polling time. Please check Argil dashboard or logs for Video ID:", test_video_id)
            else:
                err_msg = render_response.get('error') if render_response else 'No response'
                details_msg = render_response.get('details') if render_response else ''
                print(f"Failed to render video. Error: {err_msg}. Details: {details_msg}")
        else:
            err_msg = creation_response.get('error') if creation_response else 'No response'
            details_msg = creation_response.get('details') if creation_response else ''
            print(f"Failed to create video. Error: {err_msg}. Details: {details_msg}")

        print("\nArgil client test finished.")
