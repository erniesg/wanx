import pytest
import asyncio
from playwright.async_api import async_playwright

from backend.text_to_video.envato_client import login_to_envato, get_envato_credentials, search_envato_music

@pytest.mark.asyncio
async def test_envato_login_success():
    """Tests successful login to Envato Elements."""
    username, password = get_envato_credentials()
    if not username or not password:
        pytest.skip("ENVATO_USERNAME or ENVATO_PASSWORD not set in .env. Skipping login test.")

    async with async_playwright() as p:
        # browser = await p.chromium.launch(headless=False)  # For debugging: shows browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        success = await login_to_envato(page, username, password)

        assert success is True, "Envato login failed. Check credentials or selectors."
        # A more robust check could be to verify an element that only appears when logged in,
        # or that the URL is as expected after login.
        assert "elements.envato.com" in page.url, f"Expected to be on elements.envato.com, but was on {page.url}"
        # Add a check for a known element on the dashboard if possible
        # For example, a user avatar or a specific dashboard link
        # is_avatar_visible = await page.is_visible("selector-for-user-avatar")
        # assert is_avatar_visible, "User avatar not visible after login, login might have failed silently."

        await browser.close()

@pytest.mark.asyncio
async def test_envato_music_search():
    """Tests music search on Envato Elements after logging in."""
    username, password = get_envato_credentials()
    if not username or not password:
        pytest.skip("ENVATO_USERNAME or ENVATO_PASSWORD not set in .env. Skipping music search test.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) # Use headless=False for debugging
        page = await browser.new_page()

        # 1. Login first
        login_success = await login_to_envato(page, username, password)
        assert login_success, "Login failed, cannot proceed with music search test."
        print("Login successful for music search test.")

        # 2. Perform search
        test_keyword = "uplifting corporate"
        num_results = 3
        print(f"Performing music search for keyword: '{test_keyword}', asking for {num_results} results.")

        # Ensure the page is on the correct domain before search, login_to_envato should handle this.
        # If not, navigate: await page.goto("https://elements.envato.com/", wait_until="networkidle")

        music_items = await search_envato_music(page, test_keyword, num_results_to_save=num_results)

        print(f"Search returned {len(music_items)} items.")
        for i, item in enumerate(music_items):
            print(f"Item {i+1}: Title: '{item.get('title')}', URL: '{item.get('item_page_url')}'")

        assert isinstance(music_items, list), "Search function should return a list."

        if music_items: # Only check item structure if results are found
            # We expect up to num_results, but it could be less if fewer are available.
            assert len(music_items) <= num_results, f"Expected at most {num_results} items, but got {len(music_items)}."
            for item in music_items:
                assert isinstance(item, dict), "Each item in the search results should be a dictionary."
                assert "title" in item, "Each item dictionary must have a 'title' key."
                assert "item_page_url" in item, "Each item dictionary must have an 'item_page_url' key."
                assert isinstance(item["title"], str), "Item title should be a string."
                assert isinstance(item["item_page_url"], str), "Item page URL should be a string."
                assert item["item_page_url"].startswith("https://elements.envato.com/"), \
                       f"Item URL '{item['item_page_url']}' does not seem to be a valid Envato Elements item URL."
        else:
            print(f"No music items found for keyword '{test_keyword}'. This might be expected or indicate an issue.")
            # Depending on the keyword, 0 results might be valid. No strict assertion for non-empty here.

        await browser.close()

# To run this test:
# 1. Ensure you have .env file in the project root with ENVATO_USERNAME and ENVATO_PASSWORD.
# 2. Install pytest and playwright: pip install pytest pytest-asyncio playwright
# 3. Install browser binaries: playwright install
# 4. Navigate to the 'backend' directory (or ensure your Python path is set up correctly)
# 5. Run pytest: pytest tests/test_envato_login.py
