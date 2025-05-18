import pytest
import asyncio
import os # For file cleanup
import random # For selecting a random item
from pathlib import Path # For path operations
from playwright.async_api import async_playwright, Locator # Added Locator
from typing import Optional # For type hinting

from backend.text_to_video.envato_client import (
    login_to_envato,
    get_envato_credentials,
    search_envato_music_by_url,
    logout_from_envato,
    download_envato_asset,
    search_envato_stock_video_by_url,
    search_envato_photos_by_url,
    search_envato_stock_video_by_ui,
    search_envato_photos_by_ui
)
from backend.text_to_video.models.envato_models import (
    EnvatoMusicSearchParams, EnvatoMusicGenre, EnvatoMusicMood, EnvatoMusicTempo, EnvatoMusicTheme,
    EnvatoStockVideoSearchParams, EnvatoVideoCategory, EnvatoVideoOrientation, EnvatoVideoResolution,
    EnvatoPhotoSearchParams, EnvatoPhotoOrientation, EnvatoPhotoNumberOfPeople
)

@pytest.mark.asyncio
async def test_envato_login_success():
    """Tests successful login to Envato Elements."""
    username, password = get_envato_credentials()
    if not username or not password:
        pytest.skip("ENVATO_USERNAME or ENVATO_PASSWORD not set in .env. Skipping login test.")

    browser = None # Initialize browser variable
    page: Optional[Page] = None # Define page here to be accessible in finally
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            success = await login_to_envato(page, username, password)

            assert success is True, "Envato login failed. Check credentials or selectors."
            assert "elements.envato.com" in page.url, f"Expected to be on elements.envato.com, but was on {page.url}"
        finally:
            if page: # Check if page was initialized
                await logout_from_envato(page)
            if browser:
                await browser.close()

@pytest.mark.asyncio
async def test_envato_music_search_by_url():
    """Tests music search on Envato Elements using direct URL construction after logging in."""
    username, password = get_envato_credentials()
    if not username or not password:
        pytest.skip("ENVATO_USERNAME or ENVATO_PASSWORD not set in .env. Skipping URL search test.")

    browser = None # Initialize browser variable
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            login_success = await login_to_envato(page, username, password)
            assert login_success, "Login failed, cannot proceed with URL music search test."
            print("Login successful for URL music search test.")

            search_params = EnvatoMusicSearchParams(
                keyword="energetic tech presentation",
                genres=[EnvatoMusicGenre.ELECTRONIC, EnvatoMusicGenre.CORPORATE],
                moods=[EnvatoMusicMood.UPBEAT, EnvatoMusicMood.INSPIRING],
                tempos=[EnvatoMusicTempo.UPBEAT, EnvatoMusicTempo.FAST],
                max_length="03:00",
                min_length="00:30"
            )
            num_results = 2

            print(f"Performing music search by URL for keyword: '{search_params.keyword}' with params, asking for {num_results} results.")
            constructed_url_path = search_params.build_url_path()
            print(f"Constructed URL path: https://elements.envato.com{constructed_url_path}")

            music_items = await search_envato_music_by_url(page, search_params, num_results_to_save=num_results)

            print(f"URL Search returned {len(music_items)} items.")
            for i, item in enumerate(music_items):
                print(f"Item {i+1}: Title: '{item.get('title')}', URL: '{item.get('item_page_url')}'")

            assert isinstance(music_items, list), "URL Search function should return a list."

            if music_items:
                assert len(music_items) <= num_results, f"Expected at most {num_results} items from URL search, but got {len(music_items)}."
                for item in music_items:
                    assert isinstance(item, dict), "Each item in the URL search results should be a dictionary."
                    assert "title" in item, "Each item dictionary from URL search must have a 'title' key."
                    assert "item_page_url" in item, "Each item dictionary from URL search must have an 'item_page_url' key."
                    item_url = item["item_page_url"] # Extract for clarity
                    assert item_url.startswith("https://elements.envato.com/"), \
                           f"Item URL '{item_url}' does not seem to be a valid Envato Elements item URL."
            else:
                print(f"No music items found via URL search for keyword '{search_params.keyword}'. This could be due to restrictive filters or an issue.")

            # Test with only keyword
            search_params_keyword_only = EnvatoMusicSearchParams(keyword="simple piano mood")
            print(f"Performing music search by URL for keyword: '{search_params_keyword_only.keyword}' (no extra params), asking for {num_results} results.")
            constructed_url_path_ko = search_params_keyword_only.build_url_path()
            print(f"Constructed URL path: https://elements.envato.com{constructed_url_path_ko}")
            music_items_ko = await search_envato_music_by_url(page, search_params_keyword_only, num_results_to_save=num_results)
            print(f"URL Search (keyword only) returned {len(music_items_ko)} items.")
            for i, item in enumerate(music_items_ko):
                print(f"Item {i+1} (KO): Title: '{item.get('title')}', URL: '{item.get('item_page_url')}'")
            assert isinstance(music_items_ko, list), "URL Search function (keyword only) should return a list."

        finally:
            if browser:
                await logout_from_envato(page)
                await browser.close()

@pytest.mark.asyncio
async def test_envato_music_download(tmp_path: Path):
    """Tests downloading and unzipping a music asset from Envato Elements."""
    username, password = get_envato_credentials()
    if not username or not password:
        pytest.skip("ENVATO_USERNAME or ENVATO_PASSWORD not set. Skipping download test.")

    project_license_val_for_test = os.getenv("ENVATO_TEST_PROJECT_LICENSE_VALUE", "ai-video")
    if project_license_val_for_test == "ai-video" and not os.getenv("ENVATO_TEST_PROJECT_LICENSE_VALUE"):
        print(f"WARN: Using default 'ai-video' for project license. Set ENVATO_TEST_PROJECT_LICENSE_VALUE if different.")

    browser = None
    page: Optional[Page] = None
    download_output_path_str: Optional[str] = None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            login_success = await login_to_envato(page, username, password)
            assert login_success, "Login failed for download test."

            search_keyword = "short upbeat ident logo"
            search_params = EnvatoMusicSearchParams(keyword=search_keyword, max_length="00:30", min_length="00:05")
            music_items = await search_envato_music_by_url(page, search_params, num_results_to_save=5)
            assert music_items, f"No music items found for '{search_keyword}'."
            downloadable_items = [item for item in music_items if item.get("download_button_locator")]
            assert downloadable_items, f"No items with download button for '{search_keyword}'."
            item_to_download = random.choice(downloadable_items)
            item_title = item_to_download["title"]
            button_locator = item_to_download["download_button_locator"]
            item_detail_url = item_to_download["item_page_url"]
            download_and_extract_base_dir = tmp_path / "envato_assets"
            download_and_extract_base_dir.mkdir(exist_ok=True)

            download_output_path_str = await download_envato_asset(
                page, item_title, button_locator, project_license_val_for_test,
                str(download_and_extract_base_dir), item_page_url=item_detail_url
            )
            assert download_output_path_str is not None, f"DL function returned None for '{item_title}'."

            output_path = Path(download_output_path_str)
            assert output_path.is_dir(), f"Expected dir path for extracted files, got: {output_path}"
            assert output_path.exists(), f"Extraction directory does not exist: {output_path}"

            # Check if the extraction directory and its potential subdirectories contain audio files
            # Uses rglob to search recursively
            found_audio_files = []
            for ext in ('*.mp3', '*.wav', '*.MP3', '*.WAV'): # Check for common audio extensions, case-insensitive friendly
                found_audio_files.extend(list(output_path.rglob(ext)))

            assert found_audio_files, f"No .mp3 or .wav files found recursively in {output_path}. Contents: {list(output_path.glob('**/*'))}"
            print(f"Successfully downloaded, unzipped '{item_title}'. Found audio file(s): {[f.name for f in found_audio_files]} in {output_path}.")

        finally:
            if page: await logout_from_envato(page)
            if browser: await browser.close()

@pytest.mark.asyncio
async def test_envato_stock_video_download(tmp_path: Path):
    """Test searching for stock video, downloading one item, handling potential zips, and verifying video files."""
    username, password = get_envato_credentials()
    if not username or not password:
        pytest.skip("ENVATO_USERNAME or ENVATO_PASSWORD not set. Skipping stock video download test.")

    project_license_value_fixture = os.getenv("ENVATO_TEST_PROJECT_LICENSE_VALUE", "ai-video")
    if project_license_value_fixture == "ai-video" and not os.getenv("ENVATO_TEST_PROJECT_LICENSE_VALUE"):
        print(f"WARN: Using default 'ai-video' for project license. Set ENVATO_TEST_PROJECT_LICENSE_VALUE if different.")

    browser = None
    page: Optional[Page] = None
    download_output_path_str: Optional[str] = None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            await login_to_envato(page, username, password)
            search_params = EnvatoStockVideoSearchParams(
                keyword="technology",
                category=EnvatoVideoCategory.STOCK_FOOTAGE,
            )
            num_results_to_save = 5
            print(f"Searching for stock video with params: {search_params.model_dump_json(indent=2)}")

            # Use a specific subdirectory within tmp_path for this test's downloads
            download_directory_fixture = tmp_path / "envato_video_assets"
            download_directory_fixture.mkdir(parents=True, exist_ok=True)

            video_items = await search_envato_stock_video_by_url(
                page,
                params=search_params,
                num_results_to_save=num_results_to_save
            )
            print(f"Found {len(video_items)} video items.")
            assert video_items, "No video items found for the given search criteria."

            downloadable_items = [item for item in video_items if item.get("download_button_locator")]
            assert downloadable_items, "No downloadable video items found in the search results."

            selected_item = random.choice(downloadable_items)
            item_title = selected_item["title"]
            download_button_locator = selected_item["download_button_locator"]
            item_page_url = selected_item["item_page_url"]

            print(f"Attempting to download video: {item_title}")

            download_path = await download_envato_asset(
                page,
                item_title=item_title,
                download_button_locator=download_button_locator,
                project_license_value=project_license_value_fixture,
                download_directory=str(download_directory_fixture),
                item_page_url=item_page_url,
            )

            assert download_path, "Download path was not returned."
            download_path_obj = Path(download_path)
            print(f"Asset supposedly downloaded/extracted to: {download_path_obj}")

            assert download_path_obj.exists(), f"Download/extraction path {download_path_obj} does not exist."

            if download_path_obj.is_file() and download_path_obj.suffix.lower() == ".zip":
                pytest.fail("download_envato_asset returned a zip file path, but should return extraction directory path if unzipped.")
            elif download_path_obj.is_dir():
                video_files_found = []
                for ext in ("*.mp4", "*.mov", "*.avi", "*.mkv"):
                    video_files_found.extend(list(download_path_obj.rglob(ext)))
                print(f"Video files found in {download_path_obj}: {video_files_found}")
                assert video_files_found, f"No video files (.mp4, .mov, .avi, .mkv) found in {download_path_obj} or its subdirectories."
            elif download_path_obj.is_file():
                allowed_extensions = [".mp4", ".mov", ".avi", ".mkv"]
                assert download_path_obj.suffix.lower() in allowed_extensions, f"Downloaded file {download_path_obj} is not a recognized video file type."
                print(f"Single video file downloaded: {download_path_obj}")
            else:
                pytest.fail(f"Downloaded path {download_path_obj} is neither a recognized file nor a directory.")

        finally:
            if page: await logout_from_envato(page)
            if browser: await browser.close()

@pytest.mark.asyncio
async def test_envato_photo_download(tmp_path: Path):
    """Test searching for photos, downloading one item, and verifying image files."""
    username, password = get_envato_credentials()
    if not username or not password:
        pytest.skip("ENVATO_USERNAME or ENVATO_PASSWORD not set. Skipping photo download test.")

    project_license_value_fixture = os.getenv("ENVATO_TEST_PROJECT_LICENSE_VALUE", "ai-video")
    if project_license_value_fixture == "ai-video" and not os.getenv("ENVATO_TEST_PROJECT_LICENSE_VALUE"):
        print(f"WARN: Using default 'ai-video' for project license. Set ENVATO_TEST_PROJECT_LICENSE_VALUE if different.")

    browser = None
    page: Optional[Page] = None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            await login_to_envato(page, username, password)

            search_params = EnvatoPhotoSearchParams(
                keyword="modern city skyline",
                orientations=[EnvatoPhotoOrientation.LANDSCAPE],
                # number_of_people=[EnvatoPhotoNumberOfPeople.NO_PEOPLE] # Optional filter
            )
            num_results_to_save = 5
            print(f"Searching for photos with params: {search_params.model_dump_json(indent=2)}")

            download_directory_fixture = tmp_path / "envato_photo_assets"
            download_directory_fixture.mkdir(parents=True, exist_ok=True)

            photo_items = await search_envato_photos_by_url(
                page,
                params=search_params,
                num_results_to_save=num_results_to_save
            )
            print(f"Found {len(photo_items)} photo items.")
            assert photo_items, "No photo items found for the given search criteria."

            downloadable_items = [item for item in photo_items if item.get("download_button_locator")]
            assert downloadable_items, "No downloadable photo items found in the search results."

            selected_item = random.choice(downloadable_items)
            item_title = selected_item["title"]
            download_button_locator = selected_item["download_button_locator"]
            item_page_url = selected_item["item_page_url"]

            print(f"Attempting to download photo: {item_title}")

            download_path = await download_envato_asset(
                page,
                item_title=item_title,
                download_button_locator=download_button_locator,
                project_license_value=project_license_value_fixture,
                download_directory=str(download_directory_fixture),
                item_page_url=item_page_url
            )

            assert download_path, "Download path was not returned for photo."
            download_path_obj = Path(download_path)
            print(f"Photo asset supposedly downloaded/extracted to: {download_path_obj}")

            assert download_path_obj.exists(), f"Photo download/extraction path {download_path_obj} does not exist."

            image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp") # Common image extensions

            if download_path_obj.is_dir(): # If it was a zip and got extracted
                image_files_found = []
                for ext_pattern in [f"*{ext}" for ext in image_extensions]:
                    image_files_found.extend(list(download_path_obj.rglob(ext_pattern)))
                print(f"Image files found in {download_path_obj}: {image_files_found}")
                assert image_files_found, f"No common image files ({', '.join(image_extensions)}) found in directory {download_path_obj}."
            elif download_path_obj.is_file(): # Single image file downloaded directly
                assert download_path_obj.suffix.lower() in image_extensions, f"Downloaded file {download_path_obj} is not a recognized image file type."
                print(f"Single image file downloaded: {download_path_obj}")
            else:
                pytest.fail(f"Downloaded path {download_path_obj} is neither a recognized file nor a directory.")

        finally:
            if page: await logout_from_envato(page)
            if browser: await browser.close()

@pytest.mark.asyncio
async def test_envato_stock_video_download_by_ui(tmp_path: Path):
    """Test searching stock video via UI, downloading, and verifying."""
    username, password = get_envato_credentials()
    if not username or not password:
        pytest.skip("ENVATO_USERNAME or ENVATO_PASSWORD not set. Skipping stock video UI download test.")

    project_license_value_fixture = os.getenv("ENVATO_TEST_PROJECT_LICENSE_VALUE", "ai-video")
    browser = None
    page: Optional[Page] = None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False) # Start headless, change to False for debugging UI
            page = await browser.new_page()
            await login_to_envato(page, username, password)

            search_params = EnvatoStockVideoSearchParams(
                keyword="futuristic cityscape",
                category=EnvatoVideoCategory.STOCK_FOOTAGE,
                orientation=EnvatoVideoOrientation.HORIZONTAL,
                resolutions=[EnvatoVideoResolution.HD_1080P]
            )
            num_results_to_save = 2 # Request fewer items for quicker UI test

            download_directory_fixture = tmp_path / "envato_video_ui_assets"
            download_directory_fixture.mkdir(parents=True, exist_ok=True)

            print(f"Starting UI video search for: {search_params.keyword}")
            video_items = await search_envato_stock_video_by_ui(
                page,
                params=search_params,
                num_results_to_save=num_results_to_save
            )
            print(f"UI Search found {len(video_items)} video items.")
            assert video_items, "No video items found via UI search."

            downloadable_items = [item for item in video_items if item.get("download_button_locator")]
            assert downloadable_items, "No downloadable video items found from UI search results."

            selected_item = random.choice(downloadable_items)
            item_title = selected_item["title"]
            download_button_locator = selected_item["download_button_locator"]
            item_page_url = selected_item["item_page_url"]
            print(f"Attempting to download video via UI search result: {item_title}")

            download_path = await download_envato_asset(
                page,
                item_title=item_title,
                download_button_locator=download_button_locator,
                project_license_value=project_license_value_fixture,
                download_directory=str(download_directory_fixture),
                item_page_url=item_page_url,
            )
            assert download_path, "Download path was not returned for video (UI search)."
            download_path_obj = Path(download_path)
            assert download_path_obj.exists(), f"Download/extraction path {download_path_obj} does not exist (UI search)."

            if download_path_obj.is_dir():
                video_files_found = [f for ext in ("*.mp4", "*.mov") for f in download_path_obj.rglob(ext)]
                assert video_files_found, f"No video files found in {download_path_obj} (UI search)."
            elif download_path_obj.is_file():
                assert download_path_obj.suffix.lower() in [".mp4", ".mov"], "Downloaded file is not a recognized video type (UI search)."
            else:
                pytest.fail(f"Downloaded path {download_path_obj} is neither file nor directory (UI search).")
            print(f"Video asset '{item_title}' downloaded and verified successfully via UI search.")

        finally:
            if page: await logout_from_envato(page)
            if browser: await browser.close()

@pytest.mark.asyncio
async def test_envato_photo_download_by_ui(tmp_path: Path):
    """Test searching photos via UI, downloading, and verifying."""
    username, password = get_envato_credentials()
    if not username or not password:
        pytest.skip("ENVATO_USERNAME or ENVATO_PASSWORD not set. Skipping photo UI download test.")

    project_license_value_fixture = os.getenv("ENVATO_TEST_PROJECT_LICENSE_VALUE", "ai-video")
    browser = None
    page: Optional[Page] = None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True) # Start headless, change to False for debugging UI
            page = await browser.new_page()
            await login_to_envato(page, username, password)

            search_params = EnvatoPhotoSearchParams(
                keyword="tropical beach sunset",
                orientations=[EnvatoPhotoOrientation.LANDSCAPE],
                number_of_people=EnvatoPhotoNumberOfPeople.NO_PEOPLE
            )
            num_results_to_save = 2

            download_directory_fixture = tmp_path / "envato_photo_ui_assets"
            download_directory_fixture.mkdir(parents=True, exist_ok=True)

            print(f"Starting UI photo search for: {search_params.keyword}")
            photo_items = await search_envato_photos_by_ui(
                page,
                params=search_params,
                num_results_to_save=num_results_to_save
            )
            print(f"UI Search found {len(photo_items)} photo items.")
            assert photo_items, "No photo items found via UI search."

            downloadable_items = [item for item in photo_items if item.get("download_button_locator")]
            assert downloadable_items, "No downloadable photo items found from UI search results."

            selected_item = random.choice(downloadable_items)
            item_title = selected_item["title"]
            download_button_locator = selected_item["download_button_locator"]
            item_page_url = selected_item["item_page_url"]
            print(f"Attempting to download photo via UI search result: {item_title}")

            download_path = await download_envato_asset(
                page,
                item_title=item_title,
                download_button_locator=download_button_locator,
                project_license_value=project_license_value_fixture,
                download_directory=str(download_directory_fixture),
                item_page_url=item_page_url,
            )
            assert download_path, "Download path was not returned for photo (UI search)."
            download_path_obj = Path(download_path)
            assert download_path_obj.exists(), f"Download/extraction path {download_path_obj} does not exist (UI search)."

            image_extensions = (".jpg", ".jpeg", ".png")
            if download_path_obj.is_dir():
                image_files_found = [f for ext_pattern in [f"*{ext}" for ext in image_extensions] for f in download_path_obj.rglob(ext_pattern)]
                assert image_files_found, f"No image files found in {download_path_obj} (UI search)."
            elif download_path_obj.is_file():
                assert download_path_obj.suffix.lower() in image_extensions, "Downloaded file is not recognized image type (UI search)."
            else:
                pytest.fail(f"Downloaded path {download_path_obj} is neither file nor directory (UI search).")
            print(f"Photo asset '{item_title}' downloaded and verified successfully via UI search.")

        finally:
            if page: await logout_from_envato(page)
            if browser: await browser.close()

# Note on ENVATO_TEST_PROJECT_LICENSE_VALUE:
# The download test relies on a project existing in your Envato Elements account
# that corresponds to the project_license_val_for_test. If you use the default "ai-video",
# ensure you have a project named (or with a value attribute, inspect in browser) "ai-video".
# Otherwise, set the ENVATO_TEST_PROJECT_LICENSE_VALUE in your .env file to an existing project's value.

# To run this test:
# 1. Ensure you have .env file in the project root with ENVATO_USERNAME and ENVATO_PASSWORD.
# 2. Install pytest and playwright: pip install pytest pytest-asyncio playwright
# 3. Install browser binaries: playwright install
# 4. Navigate to the 'backend' directory (or ensure your Python path is set up correctly)
# 5. Run pytest: pytest tests/test_envato_login.py
