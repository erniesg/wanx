import os
import requests
import logging
from dotenv import load_dotenv
import random
import re
from typing import List, Optional, Dict, Any
from pathlib import Path

from backend.text_to_video.models.pixabay_models import (
    PixabayImageSearchParams, PixabayImageSearchResponse, PixabayImageHit,
    PixabayVideoSearchParams, PixabayVideoSearchResponse, PixabayVideoHit
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://pixabay.com/api/"
VIDEO_URL = "https://pixabay.com/api/videos/"

def _sanitize_filename(filename: str) -> str:
    """Sanitizes a string to be a valid filename by removing or replacing invalid characters."""
    # Remove or replace characters invalid in Windows/Linux/MacOS filenames
    sanitized = re.sub(r'[\/*?"<>|:\']', '_', filename)
    # Replace multiple underscores with a single one
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores and spaces
    sanitized = sanitized.strip('_ ')
    # Truncate if too long (OS limits are around 255-260 characters for the whole path)
    return sanitized[:100] # Keep it reasonably short for the filename part itself.

def _make_api_request(url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Makes a request to the Pixabay API and returns the JSON response."""
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        # Log rate limit headers
        logger.debug(f"X-RateLimit-Limit: {response.headers.get('X-RateLimit-Limit')}")
        logger.debug(f"X-RateLimit-Remaining: {response.headers.get('X-RateLimit-Remaining')}")
        logger.debug(f"X-RateLimit-Reset: {response.headers.get('X-RateLimit-Reset')}")
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"Pixabay API request timed out for URL: {url} with params: {params}")
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"Pixabay API HTTP error: {http_err} - Response: {http_err.response.text}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Pixabay API request failed: {req_err}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during Pixabay API request: {e}")
    return None

def search_pixabay_images(api_key: str, search_params: PixabayImageSearchParams) -> Optional[PixabayImageSearchResponse]:
    """
    Search Pixabay for images.

    Args:
        api_key: Your Pixabay API key.
        search_params: Parameters for the image search.

    Returns:
        A PixabayImageSearchResponse object or None on failure.
    """
    if not api_key:
        logger.error("Pixabay API key is missing.")
        return None

    params_dict = search_params.model_dump(exclude_none=True)
    params_dict['key'] = api_key

    logger.info(f"Searching Pixabay images with params: {params_dict}")
    json_response = _make_api_request(BASE_URL, params_dict)
    if json_response:
        try:
            return PixabayImageSearchResponse(**json_response)
        except Exception as e: # Catches Pydantic validation errors too
            logger.error(f"Error parsing Pixabay image search response: {e}. Response: {json_response}")
    return None

def search_pixabay_videos(api_key: str, search_params: PixabayVideoSearchParams) -> Optional[PixabayVideoSearchResponse]:
    """
    Search Pixabay for videos.

    Args:
        api_key: Your Pixabay API key.
        search_params: Parameters for the video search.

    Returns:
        A PixabayVideoSearchResponse object or None on failure.
    """
    if not api_key:
        logger.error("Pixabay API key is missing.")
        return None

    params_dict = search_params.model_dump(exclude_none=True)
    params_dict['key'] = api_key

    logger.info(f"Searching Pixabay videos with params: {params_dict}")
    json_response = _make_api_request(VIDEO_URL, params_dict)
    if json_response:
        try:
            return PixabayVideoSearchResponse(**json_response)
        except Exception as e:
            logger.error(f"Error parsing Pixabay video search response: {e}. Response: {json_response}")
    return None

def download_pixabay_media(media_url: str, output_dir: str, desired_filename: str) -> Optional[str]:
    """
    Downloads a media file (image or video) from a given URL.

    Args:
        media_url (str): The direct URL to the media file.
        output_dir (str): Directory to save the downloaded media.
        desired_filename (str): The base name for the downloaded file (extension will be derived).

    Returns:
        Optional[str]: The file path of the downloaded media, or None on failure.
    """
    if not media_url:
        logger.error("Media URL is missing for download.")
        return None

    try:
        # Ensure the output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Get the file extension from the URL or headers
        # A simple way is to split by '?' then by '.' for the extension from path
        file_ext = Path(media_url.split('?')[0]).suffix
        if not file_ext: # Fallback if no extension in URL path (e.g. some dynamic URLs)
            # Try to get from content-type header later if needed, for now assume .jpg or .mp4 based on context if possible
            # For pixabay, URLs typically have extensions.
            logger.warning(f"Could not determine file extension from URL: {media_url}. Attempting download anyway.")
            # Default to .jpg for images, .mp4 for videos if truly unknown, but this function is generic.
            # For now, we'll rely on the caller to provide a somewhat reasonable desired_filename or ensure URL has extension.

        safe_base_filename = _sanitize_filename(desired_filename)
        output_filename = f"{safe_base_filename}{file_ext if file_ext else ''}"
        output_path = str(Path(output_dir) / output_filename)

        logger.info(f"Downloading media from {media_url} to {output_path}")
        media_response = requests.get(media_url, stream=True, timeout=60) # Increased timeout for download
        media_response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in media_response.iter_content(chunk_size=8192):
                f.write(chunk)

        if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
            logger.info(f"Successfully downloaded {output_path}")
            return output_path
        else:
            logger.error(f"Failed to download media correctly (file empty or not created at {output_path}).")
            if Path(output_path).exists(): # Remove empty file
                try: Path(output_path).unlink()
                except: pass
            return None

    except requests.exceptions.RequestException as download_err:
        logger.error(f"Error downloading media from {media_url}: {download_err}")
    except IOError as io_err:
        logger.error(f"File error during download to {output_path if 'output_path' in locals() else 'unknown'}: {io_err}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during media download: {e}")
    return None

def find_and_download_pixabay_images(api_key: str, query: str, count: int, output_dir: str, **kwargs) -> List[str]:
    """
    Search Pixabay for images matching the query and download a specified number.

    Args:
        api_key (str): Your Pixabay API key.
        query (str): The search query.
        count (int): The number of images to download.
        output_dir (str): Directory to save the downloaded images.
        **kwargs: Additional parameters for PixabayImageSearchParams.

    Returns:
        list[str]: A list of file paths for the downloaded images. Returns empty list on failure.
    """
    # Ensure per_page is at least 3, as per API requirements, even if count is small
    # Fetch more for randomness, up to API max (200)
    per_page_val = max(3, min(count * 2, 200))
    search_params = PixabayImageSearchParams(key=api_key, q=query, per_page=per_page_val, **kwargs)
    image_response = search_pixabay_images(api_key, search_params)
    downloaded_files = []

    if image_response and image_response.hits:
        logger.info(f"Found {len(image_response.hits)} potential images for '{query}'. Attempting to download {count}.")
        selected_hits = random.sample(image_response.hits, min(count, len(image_response.hits)))

        for hit in selected_hits:
            # Prefer largeImageURL, then webformatURL
            download_url = hit.largeImageURL or hit.webformatURL
            if download_url:
                # Construct a filename: pixabay_query_id.ext
                # Extract extension from the download_url itself
                file_ext = Path(str(download_url).split('?')[0]).suffix
                filename_base = f"pixabay_{_sanitize_filename(query)}_{hit.id}"

                file_path = download_pixabay_media(str(download_url), output_dir, filename_base)
                if file_path:
                    downloaded_files.append(file_path)
                if len(downloaded_files) >= count:
                    break
            else:
                logger.warning(f"No suitable download URL found for image ID {hit.id}.")
    else:
        logger.warning(f"No images found on Pixabay for query: '{query}' with params {search_params.model_dump(exclude_none=True)}")

    if len(downloaded_files) < count:
        logger.warning(f"Could only download {len(downloaded_files)} out of {count} requested images for query '{query}'.")
    return downloaded_files

def find_and_download_pixabay_videos(api_key: str, query: str, count: int, output_dir: str, **kwargs) -> List[str]:
    """
    Search Pixabay for videos matching the query and download a specified number.

    Args:
        api_key (str): Your Pixabay API key.
        query (str): The search query.
        count (int): The number of videos to download.
        output_dir (str): Directory to save the downloaded videos.
        **kwargs: Additional parameters for PixabayVideoSearchParams.

    Returns:
        list[str]: A list of file paths for the downloaded videos. Returns empty list on failure.
    """
    # Ensure per_page is at least 3, as per API requirements, even if count is small
    # Fetch more for randomness, up to API max (200)
    per_page_val = max(3, min(count * 2, 200))
    search_params = PixabayVideoSearchParams(key=api_key, q=query, per_page=per_page_val, **kwargs)
    logger.info(f"Finding and downloading Pixabay videos. Query: '{query}', Count: {count}, Output Dir: '{output_dir}'")
    logger.info(f"Using search_params: {search_params.model_dump(exclude_none=True)}")

    video_response = search_pixabay_videos(api_key, search_params)
    downloaded_files = []

    if video_response:
        logger.info(f"Pixabay API response for query '{query}': Total: {video_response.total}, TotalHits: {video_response.totalHits}, Received Hits: {len(video_response.hits) if video_response.hits else 0}")
        if video_response.hits:
            logger.info(f"Found {len(video_response.hits)} potential videos for '{query}'. Attempting to download {count}.")
            selected_hits = random.sample(video_response.hits, min(count, len(video_response.hits)))

            for i, hit in enumerate(selected_hits):
                logger.info(f"Processing selected hit {i+1}/{len(selected_hits)}: ID {hit.id}, Tags: '{hit.tags}'")
                logger.debug(f"Video hit details: {hit.model_dump_json(indent=2)}")

                chosen_video_detail = None
                choice_log = f"Video ID {hit.id} - Available versions: "
                versions_available = []
                if hit.videos.large and hit.videos.large.url: versions_available.append("large")
                if hit.videos.medium and hit.videos.medium.url: versions_available.append("medium")
                if hit.videos.small and hit.videos.small.url: versions_available.append("small")
                if hit.videos.tiny and hit.videos.tiny.url: versions_available.append("tiny")
                choice_log += ", ".join(versions_available) if versions_available else "None"
                logger.info(choice_log)

                # Prefer medium, then small, then tiny. Large might be too big or not always available.
                if hit.videos.medium and hit.videos.medium.url:
                    chosen_video_detail = hit.videos.medium
                    logger.info(f"Video ID {hit.id}: Selected 'medium' quality for download.")
                elif hit.videos.small and hit.videos.small.url:
                    chosen_video_detail = hit.videos.small
                    logger.info(f"Video ID {hit.id}: Selected 'small' quality for download (medium not available/no URL).")
                elif hit.videos.tiny and hit.videos.tiny.url:
                    chosen_video_detail = hit.videos.tiny
                    logger.info(f"Video ID {hit.id}: Selected 'tiny' quality for download (medium/small not available/no URL).")
                elif hit.videos.large and hit.videos.large.url: # Fallback to large if others not present
                    chosen_video_detail = hit.videos.large
                    logger.info(f"Video ID {hit.id}: Selected 'large' quality for download (medium/small/tiny not available/no URL).")
                else:
                    logger.warning(f"Video ID {hit.id}: No suitable video stream found in any quality (large, medium, small, tiny) with a valid URL. Skipping this video.")
                    logger.debug(f"Full video details for ID {hit.id} with missing URLs: {hit.videos.model_dump_json(indent=2)}")
                    continue # Skip to the next video hit

                if chosen_video_detail and chosen_video_detail.url:
                    download_url = chosen_video_detail.url
                    # Sanitize query for filename, taking first few words if query is long
                    safe_query_part = "_" .join(_sanitize_filename(query).split('_')[:3]) # Max 3 words from query
                    filename_base = f"pixabay_{safe_query_part}_{hit.id}_vid"

                    logger.info(f"Attempting download for video ID {hit.id} from URL: {download_url}")
                    file_path = download_pixabay_media(str(download_url), output_dir, filename_base)
                    if file_path:
                        downloaded_files.append(file_path)
                    else:
                        logger.warning(f"Download failed for video ID {hit.id} from {download_url}.")

                    if len(downloaded_files) >= count:
                        logger.info(f"Reached desired download count ({count}). Stopping further downloads for query '{query}'.")
                        break
                # This else should ideally not be reached if the logic above correctly assigns chosen_video_detail or continues
                # else:
                # logger.warning(f"No suitable download URL found for video ID {hit.id} after selection. Video details: {hit.videos.model_dump_json(indent=2)}")
        else:
            logger.warning(f"No video hits returned by API for query: '{query}' with params {search_params.model_dump(exclude_none=True)}")
    else:
        logger.warning(f"API call for video search failed or returned no response for query: '{query}' with params {search_params.model_dump(exclude_none=True)}")

    if len(downloaded_files) < count:
        logger.warning(f"Could only download {len(downloaded_files)} out of {count} requested videos for query '{query}'.")
    return downloaded_files


# Example Usage
if __name__ == "__main__":
    load_dotenv()
    pixabay_api_key = os.getenv("PIXABAY_API_KEY")

    if not pixabay_api_key:
        print("Error: PIXABAY_API_KEY not found in environment variables. Please set it in your .env file.")
    else:
        print("Testing Pixabay Client...")
        current_dir = Path(__file__).parent
        # Create a general 'downloads' directory at the same level as 'assets' or 'script_parser.py'
        # Adjust this path as per your project structure if needed.
        # Assuming 'backend' is the root for this client.
        test_output_dir_base = current_dir.parent / "downloads" / "pixabay_test_downloads"
        test_output_dir_base.mkdir(parents=True, exist_ok=True)
        print(f"Test media will be saved in subdirectories under: {test_output_dir_base.resolve()}")

        # Test Image Search and Download
        image_test_output_dir = test_output_dir_base / "images"
        print("\n--- Testing Image Search & Download ---")
        img_query = "yellow flowers"
        print(f"Searching for 2 images with query: '{img_query}', orientation: horizontal")
        downloaded_images = find_and_download_pixabay_images(
            pixabay_api_key,
            img_query,
            2,
            str(image_test_output_dir),
            orientation="horizontal",
            editors_choice=True # try to get high quality ones
        )
        if downloaded_images:
            print(f"Downloaded images: {downloaded_images}")
        else:
            print(f"No images downloaded for query: '{img_query}'.")

        img_query_cats = "office background"
        print(f"\nSearching for 1 image with query: '{img_query_cats}', category: 'business'")
        downloaded_images_cats = find_and_download_pixabay_images(
            pixabay_api_key,
            img_query_cats,
            1,
            str(image_test_output_dir),
            category="business",
            min_width=1920
        )
        if downloaded_images_cats:
            print(f"Downloaded images: {downloaded_images_cats}")
        else:
            print(f"No images downloaded for query: '{img_query_cats}'.")

        # Test Video Search and Download
        video_test_output_dir = test_output_dir_base / "videos"
        print("\n--- Testing Video Search & Download ---")
        vid_query = "abstract animation"
        print(f"Searching for 2 videos with query: '{vid_query}', video_type: animation")
        downloaded_videos = find_and_download_pixabay_videos(
            pixabay_api_key,
            vid_query,
            2,
            str(video_test_output_dir),
            video_type="animation",
            safesearch=True
        )
        if downloaded_videos:
            print(f"Downloaded videos: {downloaded_videos}")
        else:
            print(f"No videos downloaded for query: '{vid_query}'.")

        vid_query_nature = "ocean waves short"
        print(f"\nSearching for 1 video with query: '{vid_query_nature}', category: 'nature', order: latest")
        downloaded_videos_nature = find_and_download_pixabay_videos(
            pixabay_api_key,
            vid_query_nature,
            1,
            str(video_test_output_dir),
            category="nature",
            order="latest"
        )
        if downloaded_videos_nature:
            print(f"Downloaded videos: {downloaded_videos_nature}")
        else:
            print(f"No videos downloaded for query: '{vid_query_nature}'.")

        print("\nPixaBay client test finished.")
