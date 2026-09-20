"""Browser automation tools powered by Playwright."""
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import urllib.parse

from config.settings import get_settings
from core.safety import get_safety_validator

logger = logging.getLogger(__name__)


def _check_playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def open_url(url: str, headless: Optional[bool] = None) -> Dict[str, Any]:
    """Navigate to a website URL and return the page title and status.

    Args:
        url: Full URL to navigate to (e.g., 'https://github.com').
        headless: Whether to run in headless mode. Defaults to BROWSER_HEADLESS setting.

    Returns:
        Dictionary with navigation status, page title, and final URL.
    """
    if not _check_playwright_available():
        return {
            "status": "error",
            "message": "Playwright is not installed. Install with 'pip install playwright' and run 'playwright install chromium'.",
        }

    from playwright.sync_api import sync_playwright

    settings = get_settings()
    is_headless = headless if headless is not None else settings.browser_headless

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=is_headless)
            page = browser.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            status_code = response.status if response else 200
            title = page.title()
            final_url = page.url
            browser.close()

            return {
                "status": "success",
                "title": title,
                "url": final_url,
                "http_status": status_code,
            }
    except Exception as e:
        logger.error(f"Failed to open URL '{url}': {e}")
        return {"status": "error", "message": f"Browser navigation error: {str(e)}"}


def take_screenshot(
    url: str,
    output_path: str,
    full_page: bool = False,
) -> Dict[str, Any]:
    """Take a screenshot of a web page and save to a local path.

    Args:
        url: Web URL to screenshot.
        output_path: Destination file path for the screenshot image (.png).
        full_page: If True, captures entire scrollable page height.

    Returns:
        Dictionary with screenshot status and file path.
    """
    if not _check_playwright_available():
        return {
            "status": "error",
            "message": "Playwright is not installed. Install with 'pip install playwright' and run 'playwright install chromium'.",
        }

    from playwright.sync_api import sync_playwright

    validator = get_safety_validator()
    try:
        dest = validator.validate_path(output_path, must_exist=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"status": "error", "message": f"Invalid output path '{output_path}': {str(e)}"}

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.screenshot(path=str(dest), full_page=full_page)
            browser.close()

            return {
                "status": "success",
                "message": f"Screenshot saved to '{dest}'",
                "output_path": str(dest),
                "full_page": full_page,
            }
    except Exception as e:
        logger.error(f"Failed to take screenshot of '{url}': {e}")
        return {"status": "error", "message": f"Screenshot error: {str(e)}"}


def extract_page_content(
    url: str,
    selector: Optional[str] = None,
    max_chars: int = 4000,
) -> Dict[str, Any]:
    """Extract readable text content from a web page.

    Args:
        url: Web URL to fetch.
        selector: Optional CSS selector to extract specific container content.
        max_chars: Maximum characters to return.

    Returns:
        Dictionary with page title, text snippet, and length.
    """
    if not _check_playwright_available():
        return {
            "status": "error",
            "message": "Playwright is not installed. Install with 'pip install playwright' and run 'playwright install chromium'.",
        }

    from playwright.sync_api import sync_playwright

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = page.title()

            if selector:
                element = page.query_selector(selector)
                text = element.inner_text() if element else ""
            else:
                # Extract text from body, filtering out scripts and styles
                page.evaluate("""() => {
                    const elements = document.querySelectorAll('script, style, noscript, nav, footer');
                    elements.forEach(el => el.remove());
                }""")
                text = page.inner_text("body")

            browser.close()

            clean_text = " ".join(text.split())
            truncated = clean_text[:max_chars]

            return {
                "status": "success",
                "title": title,
                "url": url,
                "text": truncated,
                "length": len(truncated),
                "is_truncated": len(clean_text) > max_chars,
            }
    except Exception as e:
        logger.error(f"Failed to extract text from '{url}': {e}")
        return {"status": "error", "message": f"Extraction error: {str(e)}"}


def search_web(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Perform a web search and return the top search results.

    Args:
        query: Search keywords or question.
        num_results: Number of results to retrieve (default: 5).

    Returns:
        Dictionary with list of search results (title, snippet, url).
    """
    if not _check_playwright_available():
        return {
            "status": "error",
            "message": "Playwright is not installed. Install with 'pip install playwright' and run 'playwright install chromium'.",
        }

    from playwright.sync_api import sync_playwright

    encoded_query = urllib.parse.quote_plus(query)
    search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(search_url, wait_until="domcontentloaded", timeout=25000)

            results = []
            elements = page.query_selector_all(".result")

            for el in elements[:num_results]:
                title_el = el.query_selector(".result__title")
                snippet_el = el.query_selector(".result__snippet")
                url_el = el.query_selector(".result__url")

                title = title_el.inner_text().strip() if title_el else ""
                snippet = snippet_el.inner_text().strip() if snippet_el else ""
                raw_url = url_el.inner_text().strip() if url_el else ""

                if title:
                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": "https://" + raw_url if not raw_url.startswith("http") else raw_url,
                    })

            browser.close()
            return {
                "status": "success",
                "query": query,
                "count": len(results),
                "results": results,
            }
    except Exception as e:
        logger.error(f"Search error for query '{query}': {e}")
        return {"status": "error", "message": f"Search execution failed: {str(e)}"}
