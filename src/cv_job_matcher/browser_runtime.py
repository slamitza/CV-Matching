from __future__ import annotations

from typing import Any


ACTION_TIMEOUT_MS = 15_000
NAVIGATION_TIMEOUT_MS = 90_000


def load_browser_runtime() -> tuple[Any, Any]:
    try:
        from patchright.sync_api import Error as BrowserError
        from patchright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Patchright is not installed. Run: python -m pip install -e . "
            "and patchright install chromium"
        ) from exc
    return BrowserError, sync_playwright


def configure_browser_context(context: object) -> None:
    for method_name, timeout in [
        ("set_default_timeout", ACTION_TIMEOUT_MS),
        ("set_default_navigation_timeout", NAVIGATION_TIMEOUT_MS),
    ]:
        try:
            getattr(context, method_name)(timeout)
        except AttributeError:
            continue


def goto_domcontentloaded(page: object, url: str) -> object:
    return page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=NAVIGATION_TIMEOUT_MS,
    )
