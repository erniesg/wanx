import os
import requests
import logging
from dotenv import load_dotenv
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_and_download_videos(api_key: str, query: str, count: int, output_dir: str, orientation: str = "portrait", size: str = "medium") -> list[str]:
    """
    Search Pexels for videos matching the query and download a specified number.

    Args:
        api_key (str): Your Pexels API key.
        query (str): The search query (e.g., "nature", "city skyline").
        count (int): The number of videos to download.
        output_dir (str): Directory to save the downloaded videos.
        orientation (str): Desired video orientation ('landscape', 'portrait', 'square'). Default: 'portrait'.
        size (str): Minimum video size ('large', 'medium', 'small'). Default: 'medium'.

    Returns:
        list[str]: A list of file paths for the downloaded videos. Returns empty list on failure.
    """
    if not api_key:
        logger.error("Pexels API key is missing.")
        return []

    search_url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "per_page": min(count * 2, 80), # Fetch a bit more to allow for filtering/randomness
        "orientation": orientation,
        "size": size
    }

    downloaded_files = []
    try:
        logger.info(f"Searching Pexels for '{query}' (orientation: {orientation}, size: {size})")
        response = requests.get(search_url, headers=headers, params=params, timeout=15)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        data = response.json()
        videos = data.get("videos", [])

        if not videos:
            logger.warning(f"No videos found for query: '{query}' with specified criteria.")
            return []

        logger.info(f"Found {len(videos)} potential videos for '{query}'. Attempting to download {count}.")

        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Select random videos from the results if more were found than needed
        selected_videos = random.sample(videos, min(count, len(videos)))

        for video_info in selected_videos:
            video_id = video_info.get("id")
            video_files = video_info.get("video_files", [])

            # Try to find a suitable video quality link (prefer HD or Full HD)
            download_link = None
            preferred_qualities = ["hd", "sd"] # Pexels API uses 'hd', 'sd', etc. not 'medium'/'small' directly in files

            for quality in preferred_qualities:
                for vf in video_files:
                    if vf.get("quality") == quality and vf.get("file_type") == "video/mp4":
                        download_link = vf.get("link")
                        logger.info(f"Selected quality '{quality}' for video ID {video_id}")
                        break
                if download_link:
                    break

            if not download_link:
                logger.warning(f"Could not find a suitable MP4 download link (quality hd/sd) for video ID {video_id}. Skipping.")
                continue

            # Construct a safe filename
            safe_query = "".join(c if c.isalnum() else "_" for c in query[:20])
            output_filename = f"pexels_{safe_query}_{video_id}.mp4"
            output_path = os.path.join(output_dir, output_filename)

            # Download the video
            logger.info(f"Downloading video ID {video_id} to {output_path}")
            try:
                video_response = requests.get(download_link, stream=True, timeout=60) # Increased timeout for download
                video_response.raise_for_status()

                with open(output_path, 'wb') as f:
                    for chunk in video_response.iter_content(chunk_size=8192):
                        f.write(chunk)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Successfully downloaded {output_path}")
                    downloaded_files.append(output_path)
                else:
                     logger.error(f"Failed to download video ID {video_id} correctly (file empty or not created).")

            except requests.exceptions.RequestException as download_err:
                logger.error(f"Error downloading video ID {video_id} from {download_link}: {download_err}")
            except Exception as e:
                 logger.error(f"An unexpected error occurred during download for video ID {video_id}: {e}")

            # Stop if we have enough videos
            if len(downloaded_files) >= count:
                break

    except requests.exceptions.Timeout:
        logger.error(f"Pexels API request timed out for query: '{query}'.")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Pexels API request failed: {req_err}")
    except Exception as e:
         logger.error(f"An unexpected error occurred during Pexels search: {e}")

    if len(downloaded_files) < count:
         logger.warning(f"Could only download {len(downloaded_files)} out of {count} requested videos for query '{query}'.")

    return downloaded_files

def find_and_download_photos(api_key: str, query: str, count: int, output_dir: str, orientation: str = "landscape", size: str = "medium", color: str = None, locale: str = None) -> list[str]:
    """
    Search Pexels for photos matching the query and download a specified number.

    Args:
        api_key (str): Your Pexels API key.
        query (str): The search query (e.g., "nature", "city skyline").
        count (int): The number of photos to download.
        output_dir (str): Directory to save the downloaded photos.
        orientation (str): Desired photo orientation ('landscape', 'portrait', 'square'). Default: 'landscape'.
        size (str): Minimum photo size ('large', 'medium', 'small'). Default: 'medium'.
        color (str, optional): Desired photo color.
        locale (str, optional): The locale of the search.

    Returns:
        list[str]: A list of file paths for the downloaded photos. Returns empty list on failure.
    """
    if not api_key:
        logger.error("Pexels API key is missing.")
        return []

    search_url = "https://api.pexels.com/v1/search" # Photo search endpoint
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "per_page": min(count * 2, 80), # Fetch a bit more to allow for filtering/randomness
        "orientation": orientation,
        "size": size
    }
    if color:
        params["color"] = color
    if locale:
        params["locale"] = locale

    downloaded_files = []
    try:
        logger.info(f"Searching Pexels for photos: '{query}' (orientation: {orientation}, size: {size})")
        response = requests.get(search_url, headers=headers, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()
        photos = data.get("photos", [])

        if not photos:
            logger.warning(f"No photos found for query: '{query}' with specified criteria.")
            return []

        logger.info(f"Found {len(photos)} potential photos for '{query}'. Attempting to download {count}.")

        os.makedirs(output_dir, exist_ok=True)

        selected_photos = random.sample(photos, min(count, len(photos)))

        for photo_info in selected_photos:
            photo_id = photo_info.get("id")
            photo_src = photo_info.get("src", {})

            # Prefer 'large' or 'original' photo size. 'medium' is also an option.
            # The API returns 'original', 'large2x', 'large', 'medium', 'small', 'portrait', 'landscape', 'tiny'
            download_link = photo_src.get("large") or photo_src.get("original") or photo_src.get("medium")

            if not download_link:
                logger.warning(f"Could not find a suitable download link (large/original/medium) for photo ID {photo_id}. Skipping.")
                continue

            # Determine file extension from the download link or default to .jpg
            file_extension = ".jpg" # Default
            if '.' in download_link.split('/')[-1]:
                file_extension = "." + download_link.split('.')[-1].split('?')[0] # Get extension before query params
                if len(file_extension) > 5 : # Basic sanity check for extension length
                    file_extension = ".jpg"


            safe_query = "".join(c if c.isalnum() else "_" for c in query[:20])
            output_filename = f"pexels_photo_{safe_query}_{photo_id}{file_extension}"
            output_path = os.path.join(output_dir, output_filename)

            logger.info(f"Downloading photo ID {photo_id} to {output_path}")
            try:
                photo_response = requests.get(download_link, stream=True, timeout=60)
                photo_response.raise_for_status()

                with open(output_path, 'wb') as f:
                    for chunk in photo_response.iter_content(chunk_size=8192):
                        f.write(chunk)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Successfully downloaded {output_path}")
                    downloaded_files.append(output_path)
                else:
                    logger.error(f"Failed to download photo ID {photo_id} correctly (file empty or not created).")

            except requests.exceptions.RequestException as download_err:
                logger.error(f"Error downloading photo ID {photo_id} from {download_link}: {download_err}")
            except Exception as e:
                logger.error(f"An unexpected error occurred during photo download for ID {photo_id}: {e}")

            if len(downloaded_files) >= count:
                break

    except requests.exceptions.Timeout:
        logger.error(f"Pexels API photo search request timed out for query: '{query}'.")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Pexels API photo search request failed: {req_err}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during Pexels photo search: {e}")

    if len(downloaded_files) < count:
        logger.warning(f"Could only download {len(downloaded_files)} out of {count} requested photos for query '{query}'.")

    return downloaded_files

# Example Usage (Item 9 - Test Pexels Client)
if __name__ == "__main__":
    load_dotenv()
    pexels_api_key = os.getenv("PEXELS_API_KEY")

    if not pexels_api_key:
        print("Error: PEXELS_API_KEY not found in environment variables. Please set it in your .env file.")
    else:
        print("Testing Pexels Client...")

        # Import the script parser to get keywords
        try:
            from script_parser import parse_script
        except ImportError:
            print("Error: Could not import parse_script from script_parser.py. Make sure it's in the same directory or Python path.")
            exit()

        # Define where to save test videos
        current_dir = os.path.dirname(__file__)
        test_output_dir = os.path.join(current_dir, "..", "assets", "heygen_workflow", "stock_video", "test_downloads")
        print(f"Test videos will be saved to: {test_output_dir}")


        # --- Test with script2.md ---
        print("\n--- Testing with script2.md ---")
        script2_path = os.path.join(current_dir, "..", "..", "public", "script2.md")
        script2_data = parse_script(script2_path)

        if script2_data and "script_segments" in script2_data:
            # Get keywords from the 'hook' segment
            hook_keywords = script2_data["script_segments"].get("hook", {}).get("b_roll_keywords", [])
            if hook_keywords:
                # Join keywords into a single query string
                video_query_hook = " ".join(hook_keywords)
                print(f"Searching for 1 video with query: '{video_query_hook}'")
                downloaded_videos = find_and_download_videos(pexels_api_key, video_query_hook, 1, test_output_dir, orientation="portrait")
                if downloaded_videos:
                    print(f"Downloaded videos: {downloaded_videos}")
                else:
                    print("No videos downloaded for the hook query.")

                photo_query_hook = " ".join(hook_keywords) # Can use same keywords for photos
                print(f"Searching for 1 photo with query: '{photo_query_hook}'")
                downloaded_photos = find_and_download_photos(pexels_api_key, photo_query_hook, 1, test_output_dir, orientation="portrait")
                if downloaded_photos:
                    print(f"Downloaded photos: {downloaded_photos}")
                else:
                    print("No photos downloaded for the hook query.")
            else:
                 print("No b_roll_keywords found in the 'hook' segment of script2.md")

            # Get keywords from the 'body' segment
            body_keywords = script2_data["script_segments"].get("body", {}).get("b_roll_keywords", [])
            if body_keywords:
                 # Take the first few keywords
                 video_query_body = " ".join(body_keywords[:3]) # Use first 3 keywords
                 print(f"Searching for 1 video with query: '{video_query_body}'")
                 downloaded_videos = find_and_download_videos(pexels_api_key, video_query_body, 1, test_output_dir, orientation="portrait")
                 if downloaded_videos:
                     print(f"Downloaded videos: {downloaded_videos}")
                 else:
                     print("No videos downloaded for the body query.")

                 photo_query_body = " ".join(body_keywords[:2]) # Use first 2 keywords for photos
                 print(f"Searching for 1 photo with query: '{photo_query_body}' (landscape)")
                 downloaded_photos = find_and_download_photos(pexels_api_key, photo_query_body, 1, test_output_dir, orientation="landscape")
                 if downloaded_photos:
                     print(f"Downloaded photos: {downloaded_photos}")
                 else:
                     print("No photos downloaded for the body query.")
            else:
                 print("No b_roll_keywords found in the 'body' segment of script2.md")

        else:
            print(f"Could not parse script2.md or find 'script_segments'. Path checked: {script2_path}")


        # --- Test with script4.md ---
        print("\n--- Testing with script4.md ---")
        script4_path = os.path.join(current_dir, "..", "..", "public", "script4.md")
        script4_data = parse_script(script4_path)

        if script4_data and "script_segments" in script4_data:
            # Get keywords from the 'conflict' segment
            conflict_keywords = script4_data["script_segments"].get("conflict", {}).get("b_roll_keywords", [])
            if conflict_keywords:
                 query3 = " ".join(conflict_keywords)
                 print(f"Searching for 1 video with query: '{query3}'")
                 downloaded = find_and_download_videos(pexels_api_key, query3, 1, test_output_dir, orientation="portrait")
                 if downloaded:
                     print(f"Downloaded files: {downloaded}")
                 else:
                     print("No videos downloaded for the third query.")

                 # Also test photo download for conflict segment
                 photo_query_conflict = " ".join(conflict_keywords[:2]) # Use first 2 keywords for photo
                 print(f"Searching for 1 photo with query: '{photo_query_conflict}' (square)")
                 downloaded_photos = find_and_download_photos(pexels_api_key, photo_query_conflict, 1, test_output_dir, orientation="square")
                 if downloaded_photos:
                     print(f"Downloaded photos: {downloaded_photos}")
                 else:
                     print("No photos downloaded for the conflict query.")
            else:
                 print("No b_roll_keywords found in the 'conflict' segment of script4.md")
        else:
            print(f"Could not parse script4.md or find 'script_segments'. Path checked: {script4_path}")

        print("\nPexels client test finished.")
