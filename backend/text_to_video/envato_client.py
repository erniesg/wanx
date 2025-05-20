import os
import logging
import re # Ensure re is imported for sanitize_filename
import uuid # For unique filenames
import zipfile # Added for unzipping
from pathlib import Path # For path operations
from urllib.parse import urljoin # Added import
from dotenv import load_dotenv
from playwright.async_api import Page, Download, Locator # Added Locator
from typing import List, Dict, Tuple, Optional, Any # Added Any for locator in dict

from backend.text_to_video.models.envato_models import EnvatoMusicSearchParams, EnvatoStockVideoSearchParams, EnvatoPhotoSearchParams, EnvatoVideoCategory, EnvatoVideoResolution, EnvatoPhotoNumberOfPeople # Added EnvatoPhotoSearchParams

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define an absolute path for the logs directory
# __file__ is the path to the current script (envato_client.py)
# .resolve() makes it an absolute path
# .parent gives the directory of the script (backend/text_to_video)
# .parent again gives the parent of that (backend)
# / "logs" appends the logs directory name
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
logger.info(f"Global LOGS_DIR defined as: {LOGS_DIR.absolute()}")

# Load environment variables from .env file
load_dotenv()

def get_envato_credentials() -> Tuple[str | None, str | None]:
    """Loads Envato credentials from environment variables."""
    username = os.getenv("ENVATO_USERNAME")
    password = os.getenv("ENVATO_PASSWORD")
    if not username or not password:
        logger.warning("ENVATO_USERNAME or ENVATO_PASSWORD not found in .env file.")
    return username, password

async def login_to_envato(page: Page, username: str, password: str) -> bool:
    """
    Logs into Envato Elements.

    Args:
        page: Playwright Page object.
        username: Envato username.
        password: Envato password.

    Returns:
        True if login is likely successful, False otherwise.
    """
    login_url = "https://elements.envato.com/sign-in"
    logger.info(f"Navigating to Envato login page: {login_url}")
    try:
        await page.goto(login_url, wait_until="networkidle")

        # Fill in username and password
        username_selector = "#username"
        password_selector = "#password"
        submit_button_selector = "#sso-forms__submit"

        logger.info(f"Attempting to fill username: {username_selector}")
        await page.fill(username_selector, username)
        logger.info(f"Attempting to fill password: {password_selector}")
        await page.fill(password_selector, password)

        logger.info(f"Attempting to click submit button: {submit_button_selector}")
        await page.click(submit_button_selector)

        # Wait for navigation to the homepage or a dashboard URL
        # Example: Wait for the URL to change to the main elements page
        await page.wait_for_url("https://elements.envato.com/**", timeout=30000) # Increased timeout
        logger.info(f"Initial login navigation successful, current URL: {page.url}")

        # Add explicit visit to homepage and a small delay to help session stabilization
        logger.info("Explicitly navigating to Envato Elements homepage to help stabilize session...")
        await page.goto("https://elements.envato.com/", wait_until="networkidle")
        logger.info(f"Navigated to homepage, current URL: {page.url}. Waiting for 3 seconds...")
        # await page.wait_for_timeout(3000) # Small delay

        logger.info("Login and session stabilization steps completed. Adding a final short delay before returning.")
        # await page.wait_for_timeout(2000) # Additional short delay
        return True
    except Exception as e:
        logger.error(f"Error during Envato login: {e}")
        # You might want to take a screenshot here for debugging
        # await page.screenshot(path="envato_login_error.png")
        return False

async def _parse_envato_item_search_results_page(page: Page, keyword_identifier: str, item_type: str, num_results_to_save: int) -> List[Dict[str, Any]]:
    """
    Private helper to parse item cards from an Envato Elements search results page (audio, video, or photo).
    Finds all item cards based on item_type, then extracts title and download button from each card.
    Args:
        page: Playwright Page object, assumed to be on a search results page.
        keyword_identifier: The original keyword or a descriptor for logging.
        item_type: 'audio', 'video', or 'photo' for logging.
        num_results_to_save: Max number of successfully parsed items to return.
    """
    search_results: List[Dict[str, Any]] = []

    # Selectors for elements within each card
    title_link_selector_in_card = "a[data-testid='title-link']"
    download_button_selector_in_card = "button[data-testid='button-download']"

    # Determine the main card selector based on item_type
    card_selector_str = ""
    if item_type == "video":
        card_selector_str = "[data-testid='video-card']"
    elif item_type == "audio":
        card_selector_str = "[data-testid='audio-card']"
    elif item_type == "photo":
        card_selector_str = "[data-testid='photo-card']"
    else:
        logger.error(f"Unknown item_type '{item_type}' for parsing. Cannot determine card selector.")
        return []

    logger.info(f"_parse_envato_item_search_results_page: Received item_type='{item_type}', using card_selector_str='{card_selector_str}'")

    # Use the global absolute LOGS_DIR
    if not LOGS_DIR.exists():
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created logs directory at: {LOGS_DIR.absolute()}")
        except Exception as e_mkdir:
            logger.error(f"Failed to create logs directory at {LOGS_DIR.absolute()}: {e_mkdir}")
            # Fallback or re-raise if critical, for now just log error and continue (screenshots might fail)
    else:
        logger.info(f"Using existing logs directory: {LOGS_DIR.absolute()}")

    logger.info(f"Starting to parse {item_type} results for '{keyword_identifier}'. Looking for item cards: '{card_selector_str}'. Max items: {num_results_to_save}")

    try:
        logger.info(f"Waiting for at least one item card ('{card_selector_str}') to be attached...")
        await page.wait_for_selector(card_selector_str, timeout=20000, state="attached")
        logger.info(f"Initial item card found. Proceeding to locate all: '{card_selector_str}'")

        card_locators = await page.locator(card_selector_str).all()
        logger.info(f"Found {len(card_locators)} potential {item_type} item cards on the page. Attempting to process up to {num_results_to_save}.")

        if not card_locators:
            screenshot_path = LOGS_DIR / f"debug_parse_{item_type}_no_item_cards_{sanitize_filename(keyword_identifier)}.png"
            html_dump_path = LOGS_DIR / f"debug_parse_{item_type}_no_item_cards_DOM_{sanitize_filename(keyword_identifier)}.html"
            logger.warning(f"No item cards ('{card_selector_str}') found for '{keyword_identifier}' after initial check. Page might not have loaded correctly or selector needs update. Screenshot: {screenshot_path}, HTML Dump: {html_dump_path}")
            await page.screenshot(path=str(screenshot_path))
            try:
                page_content = await page.content()
                with open(html_dump_path, "w", encoding="utf-8") as f:
                    f.write(page_content)
                logger.info(f"Full page HTML content dumped to {html_dump_path}")
            except Exception as e_html_dump:
                logger.error(f"Failed to dump page HTML: {e_html_dump}")
            return []

        for i, card_locator in enumerate(card_locators):
            if len(search_results) >= num_results_to_save:
                logger.info(f"Reached max {num_results_to_save} items to save. Stopping parse for '{keyword_identifier}'.")
                break

            item_page_url = "N/A"
            title_text = f"Envato {item_type.capitalize()} Item (Processing Card {i+1})"

            try:
                if not await card_locator.is_visible(): # Check if the card itself is visible
                    logger.warning(f"Card {i+1} ({item_type}): Card locator found but card is not visible. Skipping.")
                    # card_locator.screenshot(path=str(logs_dir / f"debug_parse_{item_type}_card_not_visible_{i+1}.png")) # Optional: screenshot non-visible card
                    continue

                title_link_locator = card_locator.locator(title_link_selector_in_card)

                # Explicitly wait for the title link to be present and visible *within this card*
                try:
                    await title_link_locator.wait_for(state="visible", timeout=5000) # Short timeout for already-scoped element
                except Exception as e_title_wait:
                    screenshot_path_title_not_visible = LOGS_DIR / f"debug_parse_{item_type}_title_not_visible_in_card{i+1}_{sanitize_filename(keyword_identifier)}.png"
                    logger.warning(f"Card {i+1} ({item_type}): Title link ('{title_link_selector_in_card}') in card was not visible after explicit 5s wait. Error: {e_title_wait}. Skipping card. Screenshot: {screenshot_path_title_not_visible}")
                    await card_locator.screenshot(path=str(screenshot_path_title_not_visible))
                    continue

                download_button_locator_in_card = card_locator.locator(download_button_selector_in_card)

                if await title_link_locator.count() == 0: # This check might be redundant now with wait_for visible, but keep for safety
                    screenshot_path = LOGS_DIR / f"debug_parse_{item_type}_no_title_in_card{i+1}_{sanitize_filename(keyword_identifier)}.png"
                    logger.warning(f"Card {i+1} ({item_type}): Title link ('{title_link_selector_in_card}') not found within card. Skipping. Screenshot: {screenshot_path}")
                    await card_locator.screenshot(path=str(screenshot_path))
                    continue

                item_page_url_relative = await title_link_locator.get_attribute("href")
                if not item_page_url_relative:
                    logger.warning(f"Card {i+1} ({item_type}): Could not find href attribute for title link within card. Skipping.")
                    continue
                item_page_url = urljoin(page.url, item_page_url_relative)

                title_text_from_attr = await title_link_locator.get_attribute("title")
                title_text_from_span = ""
                # Adjusted to locate span within the title_link_locator context
                if await title_link_locator.locator("span").count() > 0:
                     title_text_from_span = await title_link_locator.locator("span").first.text_content()
                elif await title_link_locator.locator("div > span").count() > 0:
                     title_text_from_span = await title_link_locator.locator("div > span").first.text_content()
                title_text_from_content = await title_link_locator.text_content()

                title_text = (title_text_from_attr or title_text_from_span or title_text_from_content or f"Envato {item_type.capitalize()} Item (No Title {i+1})").strip()
                if not title_text:
                    title_text = f"Envato {item_type.capitalize()} Item (Empty Title Card {i+1})"

                if await download_button_locator_in_card.count() > 0 and await download_button_locator_in_card.is_visible():
                    logger.debug(f"Successfully processed item {len(search_results)+1} from card {i+1} ({item_type}): '{title_text}'. Download button found.")
                    search_results.append({
                        "title": title_text,
                        "item_page_url": item_page_url,
                        "download_button_locator": download_button_locator_in_card # This is now scoped to the card
                    })
                else:
                    screenshot_path = LOGS_DIR / f"debug_parse_{item_type}_no_dl_button_in_card_{sanitize_filename(title_text)}.png"
                    dl_button_exists = await download_button_locator_in_card.count() > 0
                    dl_button_visible = await download_button_locator_in_card.is_visible() if dl_button_exists else False
                    logger.warning(f"Item '{title_text}' (Card {i+1}, {item_type}): Download button ('{download_button_selector_in_card}') NOT found (exists: {dl_button_exists}, visible: {dl_button_visible}) within its card. URL: {item_page_url}. Screenshot: {screenshot_path}")
                    await card_locator.screenshot(path=str(screenshot_path))

            except Exception as e_item_processing:
                screenshot_path = LOGS_DIR / f"error_parse_{item_type}_card_proc_card{i+1}_{sanitize_filename(keyword_identifier)}.png"
                logger.error(f"Error processing {item_type} card {i+1} (Title: '{title_text}', URL: {item_page_url}): {e_item_processing}. Screenshot: {screenshot_path}")
                try:
                    await card_locator.screenshot(path=str(screenshot_path))
                except Exception as e_screenshot:
                    logger.error(f"Failed to take screenshot for item card processing error: {e_screenshot}")

        logger.info(f"Finished iterating through {len(card_locators)} potential item cards. Successfully processed {len(search_results)} {item_type} items for '{keyword_identifier}'.")

        if not search_results and len(card_locators) > 0: # Cards were found, but none yielded results
            screenshot_path = LOGS_DIR / f"debug_parse_{item_type}_zero_results_from_cards_{sanitize_filename(keyword_identifier)}.png"
            logger.warning(f"Found {len(card_locators)} {item_type} cards, but none were successfully parsed for '{keyword_identifier}'. Screenshot: {screenshot_path}")
            await page.screenshot(path=str(screenshot_path)) # Screenshot of the whole page for context
        elif not search_results: # No cards were found in the first place (already logged with screenshot)
             logger.warning(f"No {item_type} items were successfully parsed as no cards were found for '{keyword_identifier}'.")

        logger.info(f"Returning {len(search_results)} successfully processed {item_type} items for '{keyword_identifier}' (requested up to {num_results_to_save}).")
        return search_results

    except Exception as e_page_parsing:
        screenshot_path = LOGS_DIR / f"error_parse_{item_type}_page_level_cards_{sanitize_filename(keyword_identifier)}.png"
        logger.error(f"General error parsing {item_type} results page when looking for cards ('{card_selector_str}') for '{keyword_identifier}': {e_page_parsing}. Screenshot: {screenshot_path}")
        await page.screenshot(path=str(screenshot_path))
        return []

async def search_envato_music_by_url(page: Page, params: EnvatoMusicSearchParams, num_results_to_save: int = 10) -> List[Dict[str, Any]]:
    search_path = params.build_url_path()
    full_search_url = f"https://elements.envato.com{search_path}"
    logger.info(f"Navigating to Envato music search URL: {full_search_url}")
    try:
        await page.goto(full_search_url, wait_until="networkidle", timeout=30000)
        if "/audio/" not in page.url and "content-not-found" not in page.url:
            logger.warning(f"Page URL '{page.url}' may not be audio results. Proceeding.")
        if "content-not-found" in page.url:
            logger.error(f"Envato: Content Not Found for music URL: {full_search_url}")
            return []
        return await _parse_envato_item_search_results_page(page, params.keyword, "audio", num_results_to_save)
    except Exception as e_url_search:
        logger.error(f"Error during Envato music search by URL for '{params.keyword}': {e_url_search}")
        return []

async def search_envato_stock_video_by_url(page: Page, params: EnvatoStockVideoSearchParams, num_results_to_save: int = 10) -> List[Dict[str, Any]]:
    """
    Searches for stock video on Envato Elements using a direct URL from parameters.
    """
    search_path = params.build_url_path()
    full_search_url = f"https://elements.envato.com{search_path}"
    logger.info(f"Navigating to Envato stock video search URL: {full_search_url}")
    try:
        await page.goto(full_search_url, wait_until="networkidle", timeout=30000)

        # Explicitly wait for a main container of search results to be visible
        # This selector is a guess; may need adjustment based on actual page structure.
        search_results_container_selector = "div[data-testid*='results']" # e.g., data-testid="search-results-view-content" or similar
        try:
            logger.info(f"Waiting for video search results container: {search_results_container_selector}")
            await page.wait_for_selector(search_results_container_selector, timeout=15000, state="visible")
            logger.info("Video search results container found.")
        except Exception as e_container:
            logger.warning(f"Video search results container ('{search_results_container_selector}') not found. Parsing might fail or be incomplete. {e_container}")
            # Consider a screenshot here if parsing then fails: await page.screenshot(path="debug_video_no_container.png")

        if "/stock-video/" not in page.url and "content-not-found" not in page.url:
            # The warning message in the test output ("Page URL ... may not be stock video results") came from this line.
            # This check seems okay, but the core issue was item parsing.
            logger.warning(f"Page URL '{page.url}' does not strictly match '/stock-video/'. Proceeding to parse if no 'content-not-found'.")
        if "content-not-found" in page.url:
            logger.error(f"Envato: Content Not Found for video URL: {full_search_url}")
            return []
        return await _parse_envato_item_search_results_page(page, params.keyword, "video", num_results_to_save)
    except Exception as e_url_search:
        logger.error(f"Error during Envato stock video search by URL for '{params.keyword}': {e_url_search}")
        return []

async def search_envato_photos_by_url(page: Page, params: EnvatoPhotoSearchParams, num_results_to_save: int = 10) -> List[Dict[str, Any]]:
    """
    Searches for photos on Envato Elements using a direct URL from parameters.
    """
    search_path = params.build_url_path()
    full_search_url = f"https://elements.envato.com{search_path}"
    logger.info(f"Navigating to Envato photo search URL: {full_search_url}")
    try:
        await page.goto(full_search_url, wait_until="networkidle", timeout=30000)
        # Photo URLs look like /photos/keyword/filters...
        if "/photos/" not in page.url and "content-not-found" not in page.url:
            logger.warning(f"Page URL '{page.url}' may not be photo results. Proceeding cautiously.")
        if "content-not-found" in page.url:
            logger.error(f"Envato: Content Not Found for photo URL: {full_search_url}")
            return []
        return await _parse_envato_item_search_results_page(page, params.keyword, "photo", num_results_to_save)
    except Exception as e_url_search:
        logger.error(f"Error during Envato photo search by URL for '{params.keyword}': {e_url_search}")
        return []

async def search_envato_stock_video_by_ui(page: Page, params: EnvatoStockVideoSearchParams, num_results_to_save: int = 5) -> List[Dict[str, Any]]:
    """
    Searches for stock video on Envato Elements by interacting with the UI (dropdown, search box, filters).
    """
    logger.info(f"Starting UI-based stock video search for keyword: '{params.keyword}' with params: {params.model_dump_json(indent=2)}")
    try:
        # Ensure we are on a page where the main search bar is available, e.g., homepage
        current_url = page.url
        if "elements.envato.com" not in current_url:
            logger.info("Not on Envato Elements domain, navigating to homepage first.")
            await page.goto("https://elements.envato.com/", wait_until="networkidle")
        elif not (current_url == "https://elements.envato.com/" or current_url == "https://elements.envato.com" or "/s/" in current_url):
             logger.info(f"Current URL is {current_url}. Navigating to homepage for clean search start.")
             await page.goto("https://elements.envato.com/", wait_until="networkidle")

        logger.info(f"Ensuring search input is visible before interacting with category dropdown. Current URL: {page.url}")
        search_input_selector = 'input[data-testid="search-form-input"]'
        await page.wait_for_selector(search_input_selector, state="visible", timeout=20000)
        logger.info("Search input is visible.")

        # 1. Select "Stock Video" from the search category dropdown
        search_category_dropdown_trigger_selector = 'button[data-testid="search-filter-button"]'
        # More robust selector: find the search-box (dropdown menu) then the button by role and name.
        # This assumes the dropdown container that appears gets data-testid="search-box"
        stock_video_option_locator_factory = lambda page_obj: page_obj.locator('[data-testid="search-box"]').get_by_role('button', name='Stock Video')

        logger.info(f"Step 1: Clicking search category dropdown: {search_category_dropdown_trigger_selector}")
        await page.locator(search_category_dropdown_trigger_selector).click()

        # Get the locator for the option using the current page object
        stock_video_option_locator = stock_video_option_locator_factory(page)

        logger.info(f"Waiting for stock video option (within [data-testid='search-box']) to be visible after clicking dropdown.")
        await stock_video_option_locator.wait_for(state="visible", timeout=10000)

        logger.info(f"Step 2: Selecting 'Stock Video' option.")
        await stock_video_option_locator.click()
        await page.wait_for_timeout(1000) # Pause for selection to register and UI to update (e.g. main button label)

        # 2. Enter the keyword into the search input and submit
        logger.info(f"Step 3: Entering keyword '{params.keyword}' into search input: {search_input_selector}")
        await page.fill(search_input_selector, params.keyword)
        logger.info("Step 4: Pressing Enter to submit search.")
        await page.press(search_input_selector, "Enter")
        await page.wait_for_load_state("networkidle", timeout=30000)
        logger.info(f"Search submitted. Current URL: {page.url}. Now applying filters.")

        # 3. Apply filters (on the results page)
        if params.category:
            filter_aria_label = params.category.value.replace('-', ' ').title()
            if params.category == EnvatoVideoCategory.VIDEO_TEMPLATES:
                filter_aria_label = "Video Templates"

            logger.info(f"Attempting to apply video category filter: '{filter_aria_label}'")
            try:
                category_filter_locator = page.locator(f'a[role="checkbox"][aria-label="{filter_aria_label}"]')
                await category_filter_locator.click()
                await page.wait_for_load_state("networkidle", timeout=20000)
                logger.info(f"Video category filter '{filter_aria_label}' applied. Current URL: {page.url}")
            except Exception as e_cat_filter:
                logger.warning(f"Could not apply video category filter '{filter_aria_label}': {e_cat_filter}")

        if params.orientation:
            orientation_filter_label = params.orientation.value.title()
            logger.info(f"Attempting to apply video orientation filter: '{orientation_filter_label}'")
            try:
                orientation_filter_locator = page.locator(f'a[role="checkbox"][aria-label="{orientation_filter_label}"]')
                await orientation_filter_locator.click()
                await page.wait_for_load_state("networkidle", timeout=20000)
                logger.info(f"Video orientation filter '{orientation_filter_label}' applied. Current URL: {page.url}")
            except Exception as e_orient_filter:
                 logger.warning(f"Could not apply video orientation filter '{orientation_filter_label}': {e_orient_filter}")

        if params.resolutions:
            for res in params.resolutions:
                res_aria_label = ""
                if res == EnvatoVideoResolution.HD_1080P:
                    res_aria_label = "1080p (Full HD)"
                elif res == EnvatoVideoResolution.UHD_4K:
                    res_aria_label = "4K (UHD)"
                elif res == EnvatoVideoResolution.HD_2K:
                    res_aria_label = "2K"

                if res_aria_label:
                    logger.info(f"Attempting to apply video resolution filter: '{res_aria_label}'")
                    try:
                        res_filter_locator = page.locator(f'a[role="checkbox"][aria-label="{res_aria_label}"]')
                        await res_filter_locator.click()
                        await page.wait_for_load_state("networkidle", timeout=20000)
                        logger.info(f"Video resolution filter '{res_aria_label}' applied. Current URL: {page.url}")
                    except Exception as e_res_filter:
                        logger.warning(f"Could not apply video resolution filter '{res_aria_label}': {e_res_filter}")
                else:
                    logger.warning(f"No aria-label mapping for resolution enum value: {res.value}")

        logger.info("All UI filters applied (or skipped). Taking screenshot before parsing search results.")
        # Use the global absolute LOGS_DIR
        if not LOGS_DIR.exists():
            try:
                LOGS_DIR.mkdir(parents=True, exist_ok=True)
                logger.info(f"search_envato_stock_video_by_ui: Created logs directory at: {LOGS_DIR.absolute()}")
            except Exception as e_mkdir:
                logger.error(f"search_envato_stock_video_by_ui: Failed to create logs directory at {LOGS_DIR.absolute()}: {e_mkdir}")
        else:
            logger.info(f"search_envato_stock_video_by_ui: Using existing logs directory: {LOGS_DIR.absolute()}")

        pre_parse_screenshot_path = LOGS_DIR / f"ui_search_video_pre_parse_{sanitize_filename(params.keyword)}.png"
        await page.screenshot(path=str(pre_parse_screenshot_path))
        logger.info(f"Screenshot taken: {pre_parse_screenshot_path}")

        return await _parse_envato_item_search_results_page(page, params.keyword, "video", num_results_to_save)

    except Exception as e_ui_search:
        logger.error(f"Error during Envato stock video search by UI for '{params.keyword}': {e_ui_search}")
        return []

async def search_envato_photos_by_ui(page: Page, params: EnvatoPhotoSearchParams, num_results_to_save: int = 5) -> List[Dict[str, Any]]:
    """
    Searches for photos on Envato Elements by interacting with the UI (dropdown, search box, filters).
    """
    logger.info(f"Starting UI-based photo search for keyword: '{params.keyword}' with params: {params.model_dump_json(indent=2)}")
    try:
        current_url = page.url
        if "elements.envato.com" not in current_url:
            logger.info("Not on Envato Elements domain, navigating to homepage first.")
            await page.goto("https://elements.envato.com/", wait_until="networkidle")
        elif not (current_url == "https://elements.envato.com/" or current_url == "https://elements.envato.com" or "/s/" in current_url):
             logger.info(f"Current URL is {current_url}. Navigating to homepage for clean search start.")
             await page.goto("https://elements.envato.com/", wait_until="networkidle")

        logger.info(f"Ensuring search input is visible before interacting with category dropdown. Current URL: {page.url}")
        search_input_selector = 'input[data-testid="search-form-input"]'
        await page.wait_for_selector(search_input_selector, state="visible", timeout=20000)
        logger.info("Search input is visible.")

        search_category_dropdown_trigger_selector = 'button[data-testid="search-filter-button"]'
        photos_option_locator_factory = lambda page_obj: page_obj.locator('[data-testid="search-box"]').get_by_role('button', name='Photos')

        logger.info(f"Step 1: Clicking search category dropdown: {search_category_dropdown_trigger_selector}")
        await page.locator(search_category_dropdown_trigger_selector).click()

        photo_option_locator = photos_option_locator_factory(page)
        logger.info(f"Waiting for Photos option (using factory) to be visible after clicking dropdown.")
        await photo_option_locator.wait_for(state="visible", timeout=10000)

        logger.info(f"Step 2: Selecting 'Photos' option (using factory)")
        await photo_option_locator.click()
        await page.wait_for_timeout(1000) # Pause for selection to register and UI to update

        logger.info(f"Step 3: Entering keyword '{params.keyword}' into search input: {search_input_selector}")
        await page.fill(search_input_selector, params.keyword)
        logger.info("Step 4: Pressing Enter to submit search.")
        await page.press(search_input_selector, "Enter")
        await page.wait_for_load_state("networkidle", timeout=30000)
        logger.info(f"Search submitted. Current URL: {page.url}. Now applying filters.")

        # Apply Photo Filters (on the results page)
        if params.orientations:
            for orientation in params.orientations:
                orientation_label = orientation.value.title()
                logger.info(f"Attempting to apply photo orientation filter: '{orientation_label}'")
                try:
                    orientation_filter_locator = page.locator(f'a[role="checkbox"][aria-label="{orientation_label}"]')
                    await orientation_filter_locator.click()
                    await page.wait_for_load_state("networkidle", timeout=20000)
                    logger.info(f"Photo orientation filter '{orientation_label}' applied. Current URL: {page.url}")
                except Exception as e_orient_filter:
                    logger.warning(f"Could not apply photo orientation filter '{orientation_label}': {e_orient_filter}")

        if params.number_of_people:
            people_label = ""
            if params.number_of_people == EnvatoPhotoNumberOfPeople.NO_PEOPLE:
                people_label = "No People"
            elif params.number_of_people == EnvatoPhotoNumberOfPeople.ONE_PERSON:
                people_label = "1 person"
            elif params.number_of_people == EnvatoPhotoNumberOfPeople.TWO_PEOPLE:
                people_label = "2 people"
            elif params.number_of_people == EnvatoPhotoNumberOfPeople.THREE_PLUS_PEOPLE:
                people_label = "3+ people"

            if people_label:
                logger.info(f"Attempting to apply number of people filter: '{people_label}'")
                try:
                    people_filter_locator = page.locator(f'a[role="checkbox"][aria-label="{people_label}"]')
                    await people_filter_locator.click()
                    await page.wait_for_load_state("networkidle", timeout=20000)
                    logger.info(f"Number of people filter '{people_label}' applied. Current URL: {page.url}")
                except Exception as e_people_filter:
                    logger.warning(f"Could not apply number of people filter '{people_label}': {e_people_filter}")
            else:
                logger.warning(f"No aria-label mapping for number_of_people enum value: {params.number_of_people.value}")

        logger.info("All UI filters applied (or skipped). Taking screenshot before parsing photo search results.")
        # Use the global absolute LOGS_DIR
        if not LOGS_DIR.exists():
            try:
                LOGS_DIR.mkdir(parents=True, exist_ok=True)
                logger.info(f"search_envato_photos_by_ui: Created logs directory at: {LOGS_DIR.absolute()}")
            except Exception as e_mkdir:
                logger.error(f"search_envato_photos_by_ui: Failed to create logs directory at {LOGS_DIR.absolute()}: {e_mkdir}")
        else:
            logger.info(f"search_envato_photos_by_ui: Using existing logs directory: {LOGS_DIR.absolute()}")

        pre_parse_screenshot_path = LOGS_DIR / f"ui_search_photo_pre_parse_{sanitize_filename(params.keyword)}.png"
        await page.screenshot(path=str(pre_parse_screenshot_path))
        logger.info(f"Screenshot taken: {pre_parse_screenshot_path}")

        return await _parse_envato_item_search_results_page(page, params.keyword, "photo", num_results_to_save)

    except Exception as e_ui_search:
        logger.error(f"Error during Envato photo search by UI for '{params.keyword}': {e_ui_search}")
        return []

async def logout_from_envato(page: Page) -> None:
    """Logs out from Envato Elements by navigating to the sign-out URL."""
    logout_url = "https://elements.envato.com/sign-out"
    logger.info(f"Attempting to logout by navigating to: {logout_url}")
    try:
        await page.goto(logout_url, wait_until="domcontentloaded") # Wait for basic page load
        # Add a small delay or check for a specific element confirming logout if necessary
        await page.wait_for_timeout(2000) # Give it a moment
        logger.info(f"Logout successful. Current URL: {page.url}")
        # Typically, after sign-out, it redirects to the homepage or a sign-in page.
        # Check if we are on a page that indicates logout (e.g., sign-in page)
        if "sign-in" in page.url or page.url == "https://elements.envato.com/" or "signed_out=true" in page.url:
            logger.info("Logout confirmed by URL or page content.")
        else:
            logger.warning(f"Logout navigation completed, but URL is {page.url}, which might not confirm logout. Check manually if issues persist.")
    except Exception as e:
        logger.error(f"Error during Envato logout: {e}. Current URL: {page.url}")
        # await page.screenshot(path="envato_logout_error.png")

def sanitize_filename(filename: str) -> str:
    """Sanitizes a string to be a valid filename."""
    # Remove or replace invalid characters
    sanitized = re.sub(r'[\\/*?"<>|:]', '_', filename)
    # Truncate if too long (OS limits are around 255-260 characters for the whole path)
    # Keep it reasonably short for the filename part itself.
    return sanitized[:100]

def unzip_asset(zip_path_str: str, base_extract_dir_str: str) -> Optional[str]:
    """
    Unzips an asset and places its contents into a subdirectory named after the zip file (without extension).

    Args:
        zip_path_str: Path to the .zip file.
        base_extract_dir_str: The base directory where a new subdirectory will be created for extraction.

    Returns:
        Path to the extraction subdirectory if successful, otherwise None.
    """
    zip_path = Path(zip_path_str)
    base_extract_dir = Path(base_extract_dir_str)

    if not zip_path.exists() or not zip_path.is_file():
        logger.error(f"Zip file not found or is not a file: {zip_path_str}")
        return None

    # Create a subdirectory for extraction, named after the zip file (e.g., "item_title_abc123")
    extraction_subdir_name = zip_path.stem # Gets filename without extension
    extraction_path = base_extract_dir / extraction_subdir_name

    try:
        extraction_path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path_str, 'r') as zip_ref:
            zip_ref.extractall(extraction_path)
        logger.info(f"Successfully extracted '{zip_path.name}' to '{extraction_path}'")

        # Optional: Find the main audio file (e.g., first .mp3 or .wav)
        # For now, just returning the directory path is fine.
        return str(extraction_path)
    except zipfile.BadZipFile:
        logger.error(f"Error: '{zip_path.name}' is not a valid zip file or is corrupted.")
        return None
    except Exception as e:
        logger.error(f"Error unzipping '{zip_path.name}': {e}")
        return None

async def download_envato_asset(
    page: Page,
    item_title: str,
    download_button_locator: Optional[Page],
    project_license_value: str,
    download_directory: str,
    item_page_url: Optional[str] = None
) -> Optional[str]:
    """
    Downloads a music asset from Envato Elements by clicking a download button on the search results page.
    Args:
        page: Playwright Page object.
        item_title: The title of the item (for naming the downloaded file).
        download_button_locator: The Playwright Locator for the item's download button on the results page.
        project_license_value: The 'value' attribute of the project radio button to select.
        download_directory: The directory to save the downloaded file.
        item_page_url: Optional URL of the item page, for logging or fallback.

    Returns:
        The full path to the downloaded file if successful, otherwise None.
    """
    if not download_button_locator:
        logger.error(f"Download attempt for '{item_title}' failed: No download button locator provided.")
        return None

    logger.info(f"Attempting to download asset: '{item_title}' using provided button locator.")
    Path(download_directory).mkdir(parents=True, exist_ok=True)

    try:
        # 1. Click the item's download button (on search results page) to open the license modal
        logger.info(f"Clicking item's download button to open modal (Title: {item_title})...")
        await download_button_locator.click()
        # await page.wait_for_timeout(1000) # User removed this, respecting that for now

        # 2. Handle the license pop-up modal
        project_radio_selector = f'input[type="radio"][value="{project_license_value}"]'

        logs_dir = Path("backend/logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = logs_dir / f"error_modal_radio_timeout_{sanitize_filename(item_title)}.png"

        modal_visible = False
        modal_container_locator = None
        # Try to find and wait for the modal container first
        modal_selectors_to_try = ["div[role='dialog']", "div[aria-modal='true']", "section[aria-modal='true']"]
        logger.info("Waiting for license modal container to appear...")
        for modal_selector_str in modal_selectors_to_try:
            try:
                current_modal_container = page.locator(modal_selector_str).first
                # Wait for this specific container to be visible, short timeout per selector
                await current_modal_container.wait_for(state="visible", timeout=7000)
                logger.info(f"Modal container '{modal_selector_str}' found and visible.")
                modal_container_locator = current_modal_container
                modal_visible = True
                break
            except Exception:
                logger.info(f"Modal container '{modal_selector_str}' not found or not visible within 7s.")
                continue

        if not modal_visible:
            logger.error("License modal container did not appear after clicking download.")
            await page.screenshot(path=str(screenshot_path))
            return None

        # Now that modal container is visible, try to find the radio button within it or on the page
        logger.info(f"Modal container found. Waiting for project license radio button: {project_radio_selector}")
        try:
            # Try finding radio button within the modal first, then fall back to page-wide search if necessary
            radio_button_locator_in_modal = modal_container_locator.locator(project_radio_selector)
            if await radio_button_locator_in_modal.count() > 0:
                 await radio_button_locator_in_modal.wait_for(state="visible", timeout=15000) # Wait for it to be visible in modal
                 radio_button_to_check = radio_button_locator_in_modal
            else:
                 logger.info("Radio button not immediately found in modal container, trying page-wide search.")
                 await page.wait_for_selector(project_radio_selector, timeout=15000, state="visible")
                 radio_button_to_check = page.locator(project_radio_selector)

            # Check if the selected locator is indeed visible before interacting
            if not await radio_button_to_check.is_visible():
                raise Exception(f"Radio button '{project_radio_selector}' found in DOM but not visible.")

            logger.info(f"Selecting project radio button with value: '{project_license_value}'")
            await radio_button_to_check.check()
            assert await radio_button_to_check.is_checked(), f"Failed to check project radio button '{project_license_value}'"

        except Exception as e_radio_timeout:
            logger.error(f"Error with project radio button '{project_radio_selector}' within modal: {e_radio_timeout}")
            logger.info(f"Attempting to save screenshot to: {screenshot_path}")
            await page.screenshot(path=str(screenshot_path))
            try:
                modal_html = await modal_container_locator.evaluate("(element) => element.outerHTML", timeout=5000)
                logger.info(f"Modal content (after radio button failure):\n{modal_html}")
            except Exception as e_html:
                logger.warning(f"Could not get modal HTML after radio button failure: {e_html}")
            return None

        # 3. Click the "License & download" button in the modal
        license_and_download_button_selector = 'button[data-testid="add-download-button"]'
        logger.info(f"Clicking '{license_and_download_button_selector}' button...")

        # Start waiting for the download event BEFORE clicking the button that triggers it
        async with page.expect_download(timeout=60000) as download_info: # Increased timeout for download start
            await page.locator(license_and_download_button_selector).click()

        download = await download_info.value
        logger.info(f"Download started: {download.suggested_filename}")

        # 4. Save the download
        sanitized_title = sanitize_filename(item_title)
        raw_suggested_filename = download.suggested_filename
        download_filename = f"{sanitized_title}_{uuid.uuid4().hex[:8]}" # Base filename without extension

        is_zip_download = False
        final_file_extension = ""

        if raw_suggested_filename:
            logger.info(f"Using suggested filename: {raw_suggested_filename}")
            # Sanitize the suggested filename but try to preserve its extension
            base, ext = os.path.splitext(raw_suggested_filename)
            final_file_extension = ext.lower()
            download_filename = sanitize_filename(base) + final_file_extension
            if final_file_extension == ".zip":
                is_zip_download = True
            # If it's a known video type directly, also flag that it's not a zip we should force-unzip
            elif final_file_extension in [".mp4", ".mov", ".avi", ".mkv"]:
                 is_zip_download = False # Explicitly not a zip to unzip
            else:
                # If extension is unknown, or no extension, we might assume it *could* be a zip if not video
                # For now, if not a clear video type, and not .zip, let's assume it might be a zip if not a video
                # Or, more safely, if it's not .zip and not a video, it might be an error or an unexpected file type.
                # Let's default to assuming it's a zip if type is unclear and let unzip_asset handle failure.
                # Forcing .zip here was problematic. Let download_save_path use the ext from suggested.
                # is_zip_download will be determined by the actual unzipping attempt for these edge cases.
                # Fallback to is_zip_download = True if we decide to always try unzipping unknowns.
                # For now, only explicitly .zip files are treated as zips for unzipping.
                pass # is_zip_download remains False unless ext is .zip

        else:
            logger.warning("No suggested filename from download. Constructing filename, assuming .zip for safety, will attempt to unzip.")
            # This case implies we *expect* a zip because Envato usually provides them for licensed assets.
            download_filename = f"{sanitized_title}_{uuid.uuid4().hex[:8]}.zip"
            final_file_extension = ".zip"
            is_zip_download = True

        download_save_path = str(Path(download_directory) / download_filename)

        logger.info(f"Saving download to: {download_save_path}")
        await download.save_as(download_save_path)

        if Path(download_save_path).exists() and Path(download_save_path).stat().st_size > 0:
            logger.info(f"Successfully downloaded and saved asset to {download_save_path}")

            # Determine if we should attempt to unzip based on the final file extension or explicit flag
            should_unzip = False
            if final_file_extension == ".zip":
                should_unzip = True
            # Add any other extensions that are archives and need unzipping
            # Example: elif final_file_extension == ".rar": should_unzip = True

            if should_unzip:
                logger.info(f"Attempting to unzip: {download_save_path}")
                extracted_dir_path = unzip_asset(download_save_path, Path(download_save_path).parent)
                if extracted_dir_path:
                    logger.info(f"Asset '{item_title}' unzipped to: {extracted_dir_path}")
                    return extracted_dir_path
                else:
                    logger.error(f"Failed to unzip '{download_save_path}'. It might be corrupted or not a valid zip. Returning path to original file.")
                    return download_save_path # Fallback to original file path if unzip fails
            else:
                logger.info(f"File '{download_save_path}' is not a zip file based on extension ('{final_file_extension}'). Returning path to original file.")
                return download_save_path # It's not a zip, return the path to the downloaded file itself
        else:
            logger.error(f"Download saving failed or file is empty for {download_save_path}")
            return None

    except Exception as e:
        logger.error(f"An error occurred during asset download for '{item_title}': {e}")
        # await page.screenshot(path=f"envato_download_error_{sanitize_filename(item_title)}.png")
        return None

async def search_and_download_envato_stock_footage(
    page: Page,
    keyword: str,
    project_license_value: str,
    download_directory: str,
    num_results_to_save: int = 10
) -> List[str]: # Returns list of paths to downloaded & extracted footage folders/files
    """
    Placeholder for searching and downloading Envato stock footage.
    Currently logs a message and returns an empty list.
    """
    logger.info(f"Placeholder: Stock footage search for '{keyword}' requested. Num results: {num_results_to_save}.")
    logger.info(f"Output directory: {download_directory}, Project License: {project_license_value}")
    # In a real implementation:
    # 1. Adapt search_envato_music_by_url or search_envato_music for video (different category, selectors)
    #    - Video category in URL/filter might be "stock-footage" or similar.
    #    - Result parsing for video items (title, download button) will differ.
    # 2. Loop through results, call a modified download_envato_asset for video.
    #    - Video downloads might also be zips or direct .mp4 files.
    #    - Unzipping logic would apply if they are zips.
    return []

if __name__ == '__main__':
    # This is a placeholder for direct testing of the client if needed.
    # For actual tests, use the test_envato_login.py file.
    async def main_test_search_placeholder():
        logger.info("This is a placeholder for direct testing, use test_envato_*.py files for proper tests.")
        # from playwright.async_api import async_playwright
        # import asyncio

        # env_username, env_password = get_envato_credentials()
        # if not env_username or not env_password:
        #     logger.error("Please set ENVATO_USERNAME and ENVATO_PASSWORD in your .env file.")
        #     return

        # async with async_playwright() as p:
        #     browser = await p.chromium.launch(headless=False) # Run in headful mode for debugging
        #     page = await browser.new_page()

        #     logger.info("Attempting login for search test...")
        #     login_ok = await login_to_envato(page, env_username, env_password)
        #     if not login_ok:
        #         logger.error("Login failed, cannot proceed with search test.")
        #         await browser.close()
        #         return

        #     logger.info("Login successful. Now attempting music search...")
        #     test_keyword = "epic cinematic"
        #     music_items = await search_envato_music(page, test_keyword, num_results_to_save=3)

        #     if music_items:
        #         logger.info(f"Found {len(music_items)} music items for '{test_keyword}':")
        #         for item in music_items:
        #             logger.info(f"  Title: {item['title']}, URL: {item['item_page_url']}")
        #     else:
        #         logger.warning(f"No music items found for '{test_keyword}'.")

        #     await page.wait_for_timeout(5000) # Keep browser open for a bit
        #     await browser.close()

    # To run this placeholder (ensure .env is set up):
    # import asyncio
    # asyncio.run(main_test_search_placeholder())
    pass
