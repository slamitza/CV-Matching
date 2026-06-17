#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_DIR = ROOT_DIR / "data" / "browser-profiles" / "linkedin-job-search"
DEFAULT_URL = "https://www.linkedin.com/login"
DEFAULT_LOCALE = "en-US"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open LinkedIn in a dedicated persistent Playwright browser profile."
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
    print("Log in manually in the browser window. Do not put credentials in code.")
    print("Leave this Terminal window open while using LinkedIn.")
    print("Close the browser window when finished.")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            locale=args.locale,
            args=[f"--lang={args.locale}"],
            viewport={"width": 1440, "height": 1000},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(args.url, wait_until="domcontentloaded")
            while True:
                open_pages = [open_page for open_page in context.pages if not open_page.is_closed()]
                if not open_pages:
                    break
                open_pages[0].wait_for_timeout(1000)
        except KeyboardInterrupt:
            print("\nClosing browser...")
        except PlaywrightError:
            pass
        finally:
            context.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
