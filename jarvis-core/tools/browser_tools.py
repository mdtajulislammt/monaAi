"""Headless Playwright browser automation and external web research tools for JARVIS."""
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


def search_web_research(
    query: str,
    max_results: int = 5,
) -> Dict[str, Any]:
    """Execute external web research search using headless Playwright or fast HTTP fallback.

    Args:
        query: Research search query.
        max_results: Max number of organic search results to return.
    """
    settings = get_settings()
    results: List[Dict[str, str]] = []

    # Attempt Playwright research via DuckDuckGo HTML
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.browser_headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            page.goto(search_url, timeout=15000, wait_until="domcontentloaded")

            # Extract search snippets
            elements = page.query_selector_all(".result__body")
            for el in elements[:max_results]:
                title_el = el.query_selector(".result__title a")
                snippet_el = el.query_selector(".result__snippet")
                if title_el:
                    title = title_el.inner_text().strip()
                    link = title_el.get_attribute("href") or ""
                    snippet = snippet_el.inner_text().strip() if snippet_el else ""
                    # Filter internal duckduckgo redirect link if needed
                    if "/l/?" in link:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                        link = parsed.get("uddg", [link])[0]

                    results.append({
                        "title": title,
                        "url": link,
                        "snippet": snippet,
                    })
            browser.close()

            return {
                "status": "success",
                "query": query,
                "count": len(results),
                "results": results,
            }
    except Exception as e:
        logger.warning(f"Playwright web search encountered error: {e}. Attempting HTTP fallback.")

    # HTTP Fallback via urllib / requests
    try:
        import urllib.request
        from bs4 import BeautifulSoup
    except ImportError:
        pass

    try:
        import requests
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
        encoded_query = urllib.parse.quote_plus(query)
        resp = requests.get(f"https://html.duckduckgo.com/html/?q={encoded_query}", headers=headers, timeout=10)
        if resp.status_code == 200:
            # Simple regex parser for DDG results
            matches = re.findall(
                r'<a[^>]*class="result__url"[^>]*href="([^"]+)"[^>]*>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                resp.text,
                re.DOTALL,
            )
            for href, snip in matches[:max_results]:
                clean_snip = re.sub(r"<[^>]+>", "", snip).strip()
                results.append({"title": query, "url": href, "snippet": clean_snip})
            return {"status": "success", "query": query, "count": len(results), "results": results}
    except Exception as http_err:
        logger.error(f"HTTP fallback also failed: {http_err}")

    return {
        "status": "error",
        "query": query,
        "results": [],
        "message": "Web search could not retrieve external results at this time.",
    }


def extract_web_page_content(
    url: str,
    max_chars: int = 4000,
) -> Dict[str, Any]:
    """Navigate to a URL with headless Playwright, extract clean text content.

    Args:
        url: Web URL to inspect.
        max_chars: Maximum character length to return.
    """
    settings = get_settings()
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.browser_headless)
            page = browser.new_page()
            page.goto(url, timeout=20000, wait_until="domcontentloaded")

            # Extract title and body text
            title = page.title()
            body_text = page.evaluate("() => document.body.innerText")
            browser.close()

            cleaned = re.sub(r"\n{3,}", "\n\n", body_text).strip()
            truncated = cleaned[:max_chars]

            return {
                "status": "success",
                "url": url,
                "title": title,
                "content_length": len(cleaned),
                "extracted_content": truncated,
            }
    except Exception as e:
        logger.error(f"Failed to extract web page content from {url}: {e}")
        return {"status": "error", "url": url, "message": str(e)}


def capture_web_screenshot(
    url: str,
    output_path: str = "screenshot.png",
) -> Dict[str, Any]:
    """Capture a screenshot of a target webpage using headless Playwright.

    Args:
        url: URL to navigate and screenshot.
        output_path: File destination for the PNG screenshot.
    """
    settings = get_settings()
    try:
        from playwright.sync_api import sync_playwright

        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.browser_headless)
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 800})
            page.goto(url, timeout=20000, wait_until="networkidle")
            page.screenshot(path=str(dest), full_page=False)
            browser.close()

        return {
            "status": "success",
            "url": url,
            "output_path": str(dest),
            "size_kb": round(dest.stat().st_size / 1024, 1),
        }
    except Exception as e:
        logger.error(f"Failed to capture screenshot of {url}: {e}")
        return {"status": "error", "url": url, "message": str(e)}
