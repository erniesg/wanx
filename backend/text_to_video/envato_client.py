import os
import logging
from dotenv import load_dotenv
from playwright.async_api import Page
from typing import List, Dict, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        logger.info(f"Login successful, current URL: {page.url}")
        return True
    except Exception as e:
        logger.error(f"Error during Envato login: {e}")
        # You might want to take a screenshot here for debugging
        # await page.screenshot(path="envato_login_error.png")
        return False

async def search_envato_music(page: Page, keyword: str, num_results_to_save: int = 10) -> List[Dict[str, str]]:
    """
    Searches for music on Envato Elements and returns potential download targets.
    Assumes the user is already logged in and the page object is on an Envato Elements domain.

    Args:
        page: Playwright Page object.
        keyword: The search term for music.
        num_results_to_save: The number of top results to identify.

    Returns:
        A list of dictionaries, each containing 'title' and 'item_page_url'.
    """
    logger.info(f"Starting Envato music search for keyword: '{keyword}'")
    search_results: List[Dict[str, str]] = []

    try:
        # 1. Ensure we are on a page where search is possible (e.g., homepage)
        if "elements.envato.com" not in page.url:
            logger.info("Not on Envato Elements domain, navigating to homepage.")
            await page.goto("https://elements.envato.com/", wait_until="networkidle")

        # 2. Click "All Items" filter button to open the dropdown
        # Envato's specific selector for the button that shows "All items" / current filter
        all_items_button_selector = 'button[data-testid="search-header-package-filter-button"]'
        logger.info(f"Clicking 'All Items' filter button: {all_items_button_selector}")
        try:
            await page.locator(all_items_button_selector).click()
        except Exception as e_button:
            logger.warning(f"Could not click filter button by primary selector '{all_items_button_selector}': {e_button}. Trying fallback.")
            # Fallback if the specific testid isn't found or changes.
            # This looks for a button that typically contains the current filter type text.
            await page.get_by_role("button", name="All items").first.click() # Or regex for more flexibility if text changes

        await page.wait_for_timeout(1000) # Brief pause for menu to open

        # 3. Click "Music" from the opened dropdown
        # Envato's specific selector for the "Music" option in the filter dropdown
        music_category_selector = 'a[data-testid="search-header-package-filter-option-music"]'
        logger.info(f"Selecting 'Music' category using: {music_category_selector}")
        try:
            await page.locator(music_category_selector).click()
        except Exception as e_music_option:
            logger.warning(f"Could not click 'Music' category by primary selector '{music_category_selector}': {e_music_option}. Trying text-based fallback.")
            await page.get_by_role("link", name="Music").first.click() # General fallback

        await page.wait_for_timeout(1500) # Wait for filter to apply and UI to update

        # 4. Enter keyword in search input
        search_input_selector = 'input[data-testid="search-form-input"]'
        logger.info(f"Entering keyword '{keyword}' into search input: {search_input_selector}")
        await page.fill(search_input_selector, keyword)

        # 5. Submit search (press Enter)
        logger.info("Submitting search by pressing Enter.")
        await page.press(search_input_selector, "Enter")

        # 6. Wait for search results to load
        await page.wait_for_load_state("networkidle", timeout=30000)
        logger.info(f"Search results page loaded. Current URL: {page.url}")

        # 7. Identify top N music tracks
        # Envato search result cards usually are <article> elements with a data-testid
        item_card_selector = "article[data-testid*='search-card']" # Catches variations like 'search-card-AUDIO'

        logger.info(f"Looking for search result item cards with selector: {item_card_selector}")
        # Wait for at least one card to be present
        try:
            await page.wait_for_selector(item_card_selector, timeout=20000)
        except Exception as e_no_cards:
            logger.warning(f"No item cards found with selector '{item_card_selector}' for keyword '{keyword}'. Search might have yielded no results or page structure changed. {e_no_cards}")
            return []


        item_cards = await page.locator(item_card_selector).all()
        logger.info(f"Found {len(item_cards)} potential item cards on the page.")

        for i, card_locator in enumerate(item_cards):
            if len(search_results) >= num_results_to_save:
                break
            try:
                # The primary link to the item page often has a specific data-testid or structure
                # Example: a[data-testid*='search-card-react-router-link'] or similar
                # Let's try a more general approach first for the link
                item_link_element = card_locator.locator("a[href*='/item/'], a[href*='/music/']").first

                # Try to find a more specific link if the general one is problematic
                specific_link_selectors = [
                    "a[data-testid*='search-card-react-router-link']", # Common for main link
                    "a[data-testid*='search-card-preview-button']",   # Preview button often also links to item
                    "a[data-testid*='title-link']"                    # If a title has a specific testid link
                ]
                for sel in specific_link_selectors:
                    candidate_link = card_locator.locator(sel).first
                    if await candidate_link.is_visible():
                        item_link_element = candidate_link
                        break

                item_page_url_relative = await item_link_element.get_attribute("href")
                if not item_page_url_relative:
                    logger.warning(f"Could not find item page URL for card {i+1}. Skipping.")
                    continue

                item_page_url = page.urljoin(item_page_url_relative) # Ensure absolute URL

                # Extract title: often in an <h3>, or a dedicated element, or aria-label of the link
                title_text = ""
                # Try common title selectors
                title_selectors = [
                    "h3[data-testid*='card-title']",
                    "h3",
                    "[data-testid*='item-title']" # Generic title element
                ]
                for sel in title_selectors:
                    title_element = card_locator.locator(sel).first
                    if await title_element.is_visible():
                        title_text = (await title_element.text_content() or "").strip()
                        if title_text: break

                if not title_text: # Fallback to link's text or aria-label
                    title_text = (await item_link_element.text_content() or "").strip()
                    if not title_text:
                        title_text = (await item_link_element.get_attribute("aria-label") or "").strip()

                if not title_text: # Ultimate fallback
                    title_text = f"Envato Music Item {i+1} (Title not found)"

                logger.info(f"Result {i+1}: Title='{title_text}', URL='{item_page_url}'")
                search_results.append({
                    "title": title_text,
                    "item_page_url": item_page_url
                })

            except Exception as e_item:
                logger.warning(f"Error processing search result item {i+1} for '{keyword}': {e_item}. Skipping this item.")
                # Consider screenshotting the card: await card_locator.screenshot(path=f"error_card_{i+1}.png")

        if not search_results:
            logger.warning(f"No music items could be successfully parsed for keyword '{keyword}'.")
        else:
            logger.info(f"Successfully extracted {len(search_results)} music items for '{keyword}'.")

    except Exception as e_search:
        logger.error(f"Overall error during Envato music search for '{keyword}': {e_search}")
        # await page.screenshot(path=f"envato_search_error_{keyword}.png")

    return search_results

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
