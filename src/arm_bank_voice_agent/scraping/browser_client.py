from __future__ import annotations

import logging

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


def fetch_with_browser(
    url: str,
    timeout_ms: int = 20000,
    wait_for_selector: str | None = None,
) -> str:
    """
    Fetch a JS-rendered page with Playwright.

    If wait_for_selector is given, waits for that CSS selector to appear
    before extracting HTML — ensures dynamic content (rate tables, branch
    lists) is fully rendered before we read the page.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            # Disable images/fonts — faster, we only need text
            java_script_enabled=True,
        )
        page = context.new_page()

        # Block images, fonts, media — we only need the DOM text
        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ("image", "font", "media", "stylesheet")
            else route.continue_(),
        )

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            if wait_for_selector:
                try:
                    page.wait_for_selector(
                        wait_for_selector, timeout=8000, state="visible"
                    )
                    logger.info("Selector '%s' appeared on %s", wait_for_selector, url)
                except PlaywrightTimeoutError:
                    logger.warning(
                        "Selector '%s' never appeared on %s — using page as-is",
                        wait_for_selector, url,
                    )
            else:
                # Default: wait for network to settle
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except PlaywrightTimeoutError:
                    pass  # Some pages never go fully idle — that's OK

            # Extra wait for any JS animations / lazy renders
            page.wait_for_timeout(1500)
            html = page.content()

        finally:
            browser.close()

    return html