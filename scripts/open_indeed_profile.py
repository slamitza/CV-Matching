#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse

from patchright.sync_api import Error as BrowserError
from patchright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_DIR = ROOT_DIR / "data" / "browser-profiles" / "indeed-job-search"
DEFAULT_URL = "https://ch.indeed.com/jobs"
DEFAULT_LOCALE = "en-US"
ACTION_TIMEOUT_MS = 15_000
NAVIGATION_TIMEOUT_MS = 90_000


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open Indeed in the dedicated persistent Patchright browser profile."
    )
    parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent browser profile directory.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="URL to open first.",
    )
    parser.add_argument(
        "--locale",
        default=DEFAULT_LOCALE,
        help="Browser locale to request from websites.",
    )
    args = parser.parse_args()

    profile_dir = Path(args.profile_dir).expanduser()
    if not profile_dir.is_absolute():
        profile_dir = ROOT_DIR / profile_dir
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"Using browser profile: {profile_dir}")
    print(f"Browser locale: {args.locale}")
    print("Handle any Indeed CAPTCHA, cookie prompt, or sign-in prompt manually.")
    print("Leave this Terminal window open while using Indeed.")
    print("Close the browser window when finished.")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            locale=args.locale,
            args=[f"--lang={args.locale}"],
            viewport={"width": 1440, "height": 1000},
        )
        context.set_default_timeout(ACTION_TIMEOUT_MS)
        context.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(args.url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            while True:
                open_pages = [open_page for open_page in context.pages if not open_page.is_closed()]
                if not open_pages:
                    break
                open_pages[0].wait_for_timeout(1000)
        except KeyboardInterrupt:
            print("\nClosing browser...")
        except BrowserError:
            pass
        finally:
            context.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
