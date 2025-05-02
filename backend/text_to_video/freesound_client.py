import os
import requests
import logging
from dotenv import load_dotenv
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define usable licenses
USABLE_LICENSES = ["Creative Commons 0", "Attribution"]

def find_and_download_music(api_key: str, query: str, output_path: str, min_duration: float = 60, max_duration: float = 180) -> str | None:
    """
    Search Freesound for music and download the HQ MP3 preview of the first suitable result.

    Args:
        api_key (str): Your Freesound API key.
        query (str): The search query (e.g., "ambient electronic background").
        output_path (str): Full path including filename to save the downloaded music.
        min_duration (float): Minimum duration in seconds. Default: 60.
        max_duration (float): Maximum duration in seconds. Default: 180.

    Returns:
        str | None: The path to the downloaded file if successful, otherwise None.
    """
    if not api_key:
        logger.error("Freesound API key is missing.")
        return None

    search_url = "https://freesound.org/apiv2/search/text/"
    # Freesound uses Token authentication for basic API key access
    headers = {"Authorization": f"Token {api_key}"}

    # Construct the filter string
    license_filter_parts = [f'license:"{name}"' for name in USABLE_LICENSES]
    license_filter = " OR ".join(license_filter_parts)
    duration_filter = f"duration:[{min_duration} TO {max_duration}]"
    combined_filter = f"({license_filter}) AND {duration_filter}"

    params = {
        "query": query,
        "filter": combined_filter,
        "fields": "id,name,license,previews,duration", # Request needed fields
        "sort": "rating_desc", # Sort by rating
        "page_size": 10 # Get a few results to check
    }

    try:
        logger.info(f"Searching Freesound for '{query}' with filters: {combined_filter}")
        response = requests.get(search_url, headers=headers, params=params, timeout=15)
        response.raise_for_status() # Raise an exception for bad status codes

        data = response.json()
        results = data.get("results", [])

        if not results:
            logger.warning(f"No suitable music found for query: '{query}' matching criteria.")
            return None

        logger.info(f"Found {len(results)} potential sounds for '{query}'. Trying the first one.")

        # Try the first result
        sound_info = results[0]
        sound_id = sound_info.get("id")
        previews = sound_info.get("previews")

        if not previews or "preview-hq-mp3" not in previews:
            logger.warning(f"Sound ID {sound_id} does not have an HQ MP3 preview available. Trying next if available...")
            # In a real scenario, you might loop through more results here
            return None

        download_url = previews["preview-hq-mp3"]

        # Ensure the output directory exists
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        # Download the preview file
        logger.info(f"Downloading HQ MP3 preview for sound ID {sound_id} ({sound_info.get('name')}) from {download_url}")
        try:
            music_response = requests.get(download_url, stream=True, timeout=60)
            music_response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in music_response.iter_content(chunk_size=8192):
                    f.write(chunk)

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Successfully downloaded music to {output_path}")
                return output_path
            else:
                logger.error(f"Failed to download music for sound ID {sound_id} correctly (file empty or not created).")
                return None

        except requests.exceptions.RequestException as download_err:
            logger.error(f"Error downloading music preview for sound ID {sound_id}: {download_err}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during music download for sound ID {sound_id}: {e}")
            return None

    except requests.exceptions.Timeout:
        logger.error(f"Freesound API request timed out for query: '{query}'.")
        return None
    except requests.exceptions.RequestException as req_err:
        # Log API error details if possible
        error_detail = ""
        try:
            error_detail = req_err.response.json()
        except Exception:
            pass # Ignore if response is not JSON
        logger.error(f"Freesound API request failed: {req_err} - {error_detail}")
        return None
    except Exception as e:
         logger.error(f"An unexpected error occurred during Freesound search: {e}")
         return None

# Example Usage (Item 11 - Test FreeSound Client)
if __name__ == "__main__":
    load_dotenv()
    freesound_api_key = os.getenv("FREESOUND_API_KEY")

    if not freesound_api_key:
        print("Error: FREESOUND_API_KEY not found in environment variables. Please set it in your .env file.")
    else:
        print("Testing Freesound Client...")

        # Define where to save test music
        current_dir = os.path.dirname(__file__)
        test_output_dir = os.path.join(current_dir, "..", "assets", "heygen_workflow", "music", "test_downloads")
        test_output_file = os.path.join(test_output_dir, "test_background_music.mp3")

        print(f"Test music will be saved to: {test_output_file}")

        # Example query based on script production notes
        test_query = "dramatic electronic tension" # From script2.md notes
        print(f"\nSearching for music with query: '{test_query}'")

        downloaded_path = find_and_download_music(freesound_api_key, test_query, test_output_file)

        if downloaded_path:
            print(f"\nSuccessfully downloaded test music to: {downloaded_path}")
        else:
            print(f"\nFailed to download music for query '{test_query}'. Check logs and API key.")

        # Example query 2
        test_query_2 = "ambient electronic contemplative discovery" # Inspired by script4.md notes
        test_output_file_2 = os.path.join(test_output_dir, "test_background_music_2.mp3")
        print(f"\nSearching for music with query: '{test_query_2}'")

        downloaded_path_2 = find_and_download_music(freesound_api_key, test_query_2, test_output_file_2)

        if downloaded_path_2:
            print(f"\nSuccessfully downloaded test music to: {downloaded_path_2}")
        else:
            print(f"\nFailed to download music for query '{test_query_2}'. Check logs and API key.")


        print("\nFreesound client test finished.")
