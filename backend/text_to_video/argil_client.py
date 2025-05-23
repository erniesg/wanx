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
    callback_id: str = None,
    moments_payload: list[dict] = None
) -> dict | None:
    """
    Creates a video generation job with Argil.
    If moments_payload is provided, it's used directly.
    Otherwise, splits full_transcript into moments and assigns gestures.
    """
    logger.info(f"Attempting to create Argil video job. Title: {video_title}, Callback ID: {callback_id}")
    if not api_key:
        logger.error("API key is missing for Argil.")
        return None

    job_gesture_slugs = gesture_slugs if gesture_slugs is not None else DEFAULT_GESTURE_SLUGS
    if not job_gesture_slugs:
        logger.warning("No job-level gesture slugs provided or default, using a single 'gesture-1' for fallback if needed.")
        job_gesture_slugs = ["gesture-1"]

    default_single_gesture = job_gesture_slugs[1]

    final_moments_payload = []

    if moments_payload and len(moments_payload) > 0:
        logger.info(f"Using provided moments_payload with {len(moments_payload)} moment(s).")
        for idx, moment_data in enumerate(moments_payload):
            # Ensure essential fields are present, falling back to job defaults
            # Transcript is expected to be in moment_data if it's from orchestrator
            if "audioUrl" not in moment_data or not moment_data.get("audioUrl"):
                # Only add/ensure transcript if there's no audioUrl for this moment
                if "transcript" not in moment_data or not moment_data["transcript"]:
                    logger.warning(f"Moment {idx} in provided payload is missing 'transcript' AND 'audioUrl'. Setting transcript to a space.")
                    moment_data["transcript"] = " " # Default to space if both are missing to avoid Argil error for no content
                else:
                    logger.info(f"Moment {idx} includes transcript: '{moment_data['transcript'][:30]}...'")
            elif "transcript" in moment_data:
                # If audioUrl is present AND transcript is also somehow present, log it but Argil will likely error.
                # The orchestrator should prevent this, but this is a client-side check.
                logger.warning(f"Moment {idx} has BOTH audioUrl and transcript. Orchestrator should ensure only one. Transcript: '{moment_data['transcript'][:30]}...'")

            moment_data["avatarId"] = moment_data.get("avatarId", avatar_id) # Use moment's, else job's

            # Handle voiceId carefully: only add job-level voice_id if no audioUrl is present AND moment doesn't already have a voiceId.
            if "audioUrl" not in moment_data or not moment_data.get("audioUrl"):
                if "voiceId" not in moment_data or not moment_data.get("voiceId"):
                    moment_data["voiceId"] = voice_id # Assign job-level voice_id
                    logger.debug(f"Moment {idx} has no audioUrl and no specific voiceId, assigned job-level voiceId: {voice_id}")
            elif "voiceId" in moment_data:
                # If audioUrl is present AND voiceId is also in moment_data (e.g. from orchestrator), remove the voiceId.
                # The orchestrator should ideally not send it, but this is a safeguard.
                logger.warning(f"Moment {idx} has audioUrl AND voiceId. Removing voiceId '{moment_data['voiceId']}' as audioUrl is present.")
                del moment_data["voiceId"]

            # If gestureSlug is missing in the provided moment, use the first job-level default gesture
            if "gestureSlug" not in moment_data or not moment_data["gestureSlug"]:
                moment_data["gestureSlug"] = default_single_gesture
                logger.debug(f"Moment {idx} in payload missing gestureSlug, assigned default: {default_single_gesture}")

            # audioUrl if present in moment_data is used directly.
            if "audioUrl" in moment_data:
                logger.info(f"Moment {idx} includes audioUrl: {moment_data['audioUrl']}")

            final_moments_payload.append(moment_data)
    else:
        logger.info("No moments_payload provided, or it's empty. Splitting full_transcript.")
        if not full_transcript:
            logger.error(f"full_transcript is empty and no moments_payload provided for title: {video_title}.")
            return {"success": False, "error": "Transcript missing and no moments_payload", "details": "Cannot create job without content."}

        transcript_chunks = split_transcript_text(full_transcript, TRANSCRIPT_CHAR_LIMIT)
        if not transcript_chunks:
            logger.error(f"Transcript splitting resulted in no chunks for title: {video_title}. Original: '{full_transcript[:100]}...'")
            return {"success": False, "error": "Transcript splitting failed", "details": "No chunks generated"}

        for i, chunk in enumerate(transcript_chunks):
            assigned_gesture_slug = job_gesture_slugs[i % len(job_gesture_slugs)] # Cycle through job_gesture_slugs
            final_moments_payload.append({
                "transcript": chunk,
                "avatarId": avatar_id, # Job-level avatar
                "voiceId": voice_id,   # Job-level voice
                "gestureSlug": assigned_gesture_slug,
            })
        logger.info(f"Created {len(final_moments_payload)} moments from full_transcript.")

    if not final_moments_payload:
        logger.error(f"No moments could be prepared for Argil job: {video_title}")
        return {"success": False, "error": "No moments generated", "details": "Payload construction failed."}

    payload = {
        "name": video_title,
        "moments": final_moments_payload,
        "subtitles": {"enable": False},
        "aspectRatio": aspect_ratio,
        "autoBrolls": {"enable": False, "source": "GENERATION"},
        "extras": {}
    }
    if callback_id:
        payload["extras"]["callback_id"] = callback_id

    url = f"{BASE_URL}/videos"
    logger.debug(f"Argil create_video_job final payload: {payload}")
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
                error_details = e.response.json()
            except ValueError:
                error_details = e.response.text
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
    """Fetches details for a specific Argil video job."""
    logger.info(f"Fetching details for Argil Video ID: {video_id}")
    if not api_key or not video_id:
        logger.error("API key or Video ID is missing for fetching details.")
        return None

    url = f"{BASE_URL}/videos/{video_id}"
    try:
        response = requests.get(url, headers=_get_headers(api_key), timeout=30)
        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Successfully fetched details for Argil Video ID: {video_id}. Response: {response_data}")
        return {"success": True, "data": response_data}
    except requests.exceptions.Timeout:
        logger.error(f"Argil API request timed out while fetching details for ID: {video_id}.")
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Argil API request failed while fetching details for ID: {video_id}: {e}")
        error_details = "No response details"
        status_code = None
        if e.response is not None:
            status_code = e.response.status_code
            try:
                error_details = e.response.json()
            except ValueError: # Catch if response is not JSON
                error_details = e.response.text
            logger.error(f"Response status: {status_code}, content: {error_details}")
        return {"success": False, "error": str(e), "status_code": status_code, "details": error_details}
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"An unexpected error occurred while fetching Argil video details: {e}")
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


def _download_file_from_url_argil(url: str, output_path: str) -> bool:
    """
    Downloads a file from a URL to the given output_path.
    Specific to Argil client, consider moving to a shared utility if used elsewhere.
    Creates parent directories if they don't exist.
    """
    try:
        # Ensure output_path is a Path object for .parent and .mkdir
        import pathlib
        output_path_obj = pathlib.Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=60) as r: # Added timeout
            r.raise_for_status()
            with open(output_path_obj, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        logger.info(f"Successfully downloaded file from {url} to {output_path}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading file from {url}: {e}")
    except IOError as e: # More specific exception for file I/O
        logger.error(f"IOError saving file to {output_path}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during download from {url} to {output_path}: {e}")
    return False

def get_and_download_argil_video_if_ready(
    api_key: str,
    video_id: str,
    output_dir: str,
    project_id: str, # Used for filename uniqueness
    scene_id: str    # Used for filename uniqueness
) -> str | None:
    """
    Checks if an Argil video is ready (status 'DONE') and downloads it.
    Returns the path to the downloaded video if successful, otherwise None.
    """
    logger.info(f"Checking status and attempting download for Argil Video ID: {video_id} (Scene: {scene_id})")
    details_response = get_argil_video_details(api_key, video_id)

    if not details_response or not details_response.get("success"):
        logger.error(f"Failed to get details for Argil Video ID: {video_id}. Cannot proceed with download check.")
        return None

    job_data = details_response.get("data", {})
    status = job_data.get("status")
    video_url = job_data.get("videoUrl") # As per API doc for GET /videos/{id}

    logger.info(f"Argil Video ID: {video_id} (Scene: {scene_id}) - Current Status: {status}, Video URL: {video_url}")

    if status == "DONE": # Check against the "DONE" status
        if video_url:
            import pathlib # Ensure pathlib is available
            avatar_filename = f"{project_id}_{scene_id}_avatar_ondemand.mp4"
            output_path = pathlib.Path(output_dir) / avatar_filename
            # Create the directory if it doesn't exist, using the shared RENDERED_AVATARS_DIR might be better.
            # For now, using the passed output_dir.
            pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)

            logger.info(f"Video {video_id} is DONE. Attempting download from {video_url} to {output_path}")
            if _download_file_from_url_argil(video_url, str(output_path)):
                logger.info(f"Successfully downloaded Argil video {video_id} to {output_path}")
                return str(output_path)
            else:
                logger.error(f"Failed to download Argil video {video_id} from {video_url}")
                return None
        else:
            logger.error(f"Argil Video ID: {video_id} is DONE but no videoUrl found. Data: {job_data}")
            return None
    elif status in ["FAILED", "VIDEO_GENERATION_FAILED", "ERROR"]: # Explicitly check for failure states
        logger.error(f"Argil Video ID: {video_id} (Scene: {scene_id}) has failed with status: {status}. Cannot download.")
        return None
    else: # Any other status (GENERATING_VIDEO, etc.)
        logger.info(f"Argil Video ID: {video_id} (Scene: {scene_id}) is not yet DONE. Status: {status}. Download will not be attempted.")
        return None


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

        # --- Video Generation Test ---
        test_video_title_default_split = f"Argil Client Test Default Split {uuid.uuid4()}"
        test_script_long = (
            "This is the first sentence of our test script. It's designed to be significantly longer than 250 characters to properly "
            "evaluate if the transcript splitting mechanism works as intended when faced with lengthy input. This is sentence two. This is sentence three, let's make it a bit longer to test more splitting cases."
        )
        test_callback_id_1 = f"argil_job_test_split_{uuid.uuid4()}"

        print(f"\n--- Test 1: Create Argil Video Job (Default Transcript Splitting) ---")
        print(f"Video Title: {test_video_title_default_split}")
        creation_response_split = create_argil_video_job(
            api_key=argil_api_key,
            video_title=test_video_title_default_split,
            full_transcript=test_script_long, # This will be split
            # avatar_id, voice_id, gesture_slugs will use defaults
            callback_id=test_callback_id_1
        )

        if creation_response_split and creation_response_split.get("success"):
            test_video_id_split = creation_response_split.get("video_id")
            print(f"Successfully initiated video (split transcript). Video ID: {test_video_id_split}")
            # No rendering here to keep test faster and focused on creation logic
        else:
            err_msg = creation_response_split.get('error') if creation_response_split else 'No response'
            details_msg = creation_response_split.get('details') if creation_response_split else ''
            print(f"Failed to create video (split transcript). Error: {err_msg}. Details: {details_msg}")

        # --- Test 2: Create Argil Video Job (Using Predefined moments_payload) ---
        test_video_title_payload = f"Argil Client Test MomentsPayload {uuid.uuid4()}"
        test_callback_id_2 = f"argil_job_test_payload_{uuid.uuid4()}"

        # Example moments_payload (e.g., from asset_orchestrator.py)
        # For a real test with audioUrl, you'd need a live S3 URL with a short audio clip.
        # For this client unit test, we'll simulate the structure.
        example_audio_url = "https://example.com/fake_audio.mp3" # Placeholder

        predefined_moments = [
            {
                "transcript": "This is moment 1 from a predefined payload. It uses a specific audio.",
                # "avatarId": "some_specific_avatar_id", # Optional: override job-level avatar
                # "voiceId": "some_specific_voice_id",   # Optional: override job-level voice (for Argil TTS)
                "gestureSlug": "gesture-3", # Explicitly set gesture
                "audioUrl": example_audio_url
            },
            {
                "transcript": "This is moment 2. No audioUrl, so Argil would TTS this if it were the only moment type.",
                "avatarId": DEFAULT_AVATAR_ID, # Using default for variety
                "gestureSlug": "gesture-5"  # Different gesture
            },
            {
                # Moment missing some fields, to test defaults application
                "transcript": "Moment 3, minimal data. Will use job defaults for avatar/voice/gesture."
            }
        ]

        print(f"\n--- Test 2: Create Argil Video Job (Predefined moments_payload) ---")
        print(f"Video Title: {test_video_title_payload}")
        creation_response_payload = create_argil_video_job(
            api_key=argil_api_key,
            video_title=test_video_title_payload,
            full_transcript="This is a fallback transcript, should ideally not be used if moments_payload is valid.", # Fallback
            moments_payload=predefined_moments, # <<<< Passing predefined moments
            avatar_id="job_level_avatar_if_moment_lacks_it", # Job level default avatar
            voice_id="job_level_voice_if_moment_lacks_it",   # Job level default voice (for Argil TTS)
            # gesture_slugs (job-level) will provide default_single_gesture if a moment lacks gestureSlug
            callback_id=test_callback_id_2
        )

        if creation_response_payload and creation_response_payload.get("success"):
            test_video_id_payload = creation_response_payload.get("video_id")
            print(f"Successfully initiated video (moments_payload). Video ID: {test_video_id_payload}")
            # Further steps like rendering and polling could be tested here too,
            # but would make the test longer and require live audio URLs for full validation.
            # The focus here is on the job creation logic with moments_payload.
        else:
            err_msg = creation_response_payload.get('error') if creation_response_payload else 'No response'
            details_msg = creation_response_payload.get('details') if creation_response_payload else ''
            print(f"Failed to create video (moments_payload). Error: {err_msg}. Details: {details_msg}")
            if creation_response_payload:
                print(f"Full response details: {creation_response_payload.get('details')}")


        # The original polling test logic can be adapted if needed for one of these video IDs.
        # For brevity, focusing on the creation logic differences here.
        # ... (original polling test logic if you want to reinstate it for one of the IDs) ...

        print("\nArgil client test finished.")
