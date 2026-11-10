"""Open the showcase site in a real (headless) browser so Streamlit Community Cloud counts a visit.

A plain HTTP ping isn't enough: the app only registers a viewer when the page loads and connects. If the app is
already asleep, Streamlit shows a wake-up button instead, so the script clicks it and waits for the app.
Exits non-zero if the app doesn't come up, so a failed run shows in GitHub Actions (and emails the repo owner)."""
import sys
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

URL = "https://promo-finder-nrk.streamlit.app/"
WAKE_BUTTON = "Yes, get this app back up!"
APP_TIMEOUT_S = 300  # a sleeping app can take a few minutes to boot


def app_heading(page) -> str | None:
    """The first heading inside the app's iframe (the app itself, not the streamlit.app wrapper), if rendered."""
    for frame in page.frames:
        if "/~/+/" in frame.url:
            heading = frame.locator("h1").first
            if heading.count():
                return heading.inner_text()
    return None


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")  # Chrome is preinstalled on GitHub's Ubuntu runners
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        try:
            page.get_by_role("button", name=WAKE_BUTTON).click(timeout=15_000)
            print("The app was asleep: clicked the wake-up button.")
        except PlaywrightTimeout:
            print("The app was awake.")
        deadline = time.monotonic() + APP_TIMEOUT_S
        while (heading := app_heading(page)) is None and time.monotonic() < deadline:
            page.wait_for_timeout(5_000)
        browser.close()
    if heading is None:
        print(f"The app didn't render within {APP_TIMEOUT_S} s.", file=sys.stderr)
        return 1
    print(f"Visited {URL}: page heading {heading!r}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
