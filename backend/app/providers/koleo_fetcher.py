"""Opens Koleo search pages in a real browser and returns their text (Playwright).

Koleo needs JavaScript (the page is empty without it) and loads prices a few seconds after the
timetable, so the text is read only after it stops changing. Nothing is clicked, typed or
submitted: pages are only opened and read. A block, a captcha or a changed layout shows up as a
page without a timetable and raises `KoleoFetchError`; it is never worked around.
"""
import time
from typing import Protocol

PAGE_TIMEOUT_SEC = 30.0
POLL_SEC = 1.0
STABLE_POLLS = 2         # the text must stay the same this many polls in a row
NO_PRICE_WAIT_SEC = 8.0  # how long to wait for prices on a page that shows trips but no price


class KoleoFetchError(RuntimeError):
    """The page could not be loaded or does not contain a timetable."""


def _has_rows(text: str) -> bool:
    return "Bezpośrednie" in text or "przesiadk" in text


class PageReader(Protocol):
    def text(self, url: str, timeout_sec: float = PAGE_TIMEOUT_SEC) -> str: ...


class BrowserSession:
    """One browser for all pages of a search. Use as a context manager.

    Uses the installed Google Chrome (`channel="chrome"`); falls back to Playwright's own
    Chromium if Chrome is not installed.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None

    def __enter__(self) -> "BrowserSession":
        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            try:
                self._browser = self._playwright.chromium.launch(channel="chrome", headless=self.headless)
            except Exception:
                self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._context = self._browser.new_context(locale="pl-PL", timezone_id="Europe/Warsaw")
        except Exception as e:
            self.__exit__(None, None, None)
            raise KoleoFetchError(f"browser could not start: {type(e).__name__}: {e}") from e
        return self

    def __exit__(self, *exc) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self._playwright = self._browser = self._context = None

    def text(self, url: str, timeout_sec: float = PAGE_TIMEOUT_SEC) -> str:
        from playwright.sync_api import Error as PlaywrightError

        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
            deadline = time.monotonic() + timeout_sec
            last, same, rows_since = "", 0, None
            while time.monotonic() < deadline:
                try:
                    current = page.inner_text("main", timeout=1000)
                except PlaywrightError:
                    current = ""
                same = same + 1 if current and current == last else 0
                last = current
                if _has_rows(current) and rows_since is None:
                    rows_since = time.monotonic()
                # Koleo draws the trips first and the prices a second or two later, so a page
                # that is quiet but has no price yet is not finished. A page with trips and no
                # price at all (everything sold out) is accepted after NO_PRICE_WAIT_SEC.
                if _has_rows(current) and same >= STABLE_POLLS:
                    if "zł" in current or time.monotonic() - rows_since >= NO_PRICE_WAIT_SEC:
                        return current
                time.sleep(POLL_SEC)
            if last:
                return last  # still changing at the deadline: return what is there
            raise KoleoFetchError("the page stayed empty")
        except PlaywrightError as e:
            raise KoleoFetchError(f"page failed to load: {type(e).__name__}: {e}") from e
        finally:
            page.close()
