"""Helpers to retry failed downloads based on exceptions.json.

This module assumes exceptions were produced by FBDSAsyncScraper and
stored in a JSON array.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from extrator_fbds.fbds_core import FBDSAsyncScraper


async def retry_failures_from_file(
    exceptions_path: Path,
    scraper: FBDSAsyncScraper,
) -> None:
    """Retry failed operations listed in an exceptions.json file.

    Currently supports:
    - download_error: retries the file download by URL.
    - fetch_error: retries fetching the URL (useful for HTML pages).
    """

    if not exceptions_path.is_file():
        print(f"No exceptions file found at {exceptions_path}")
        return

    with open(exceptions_path, "r", encoding="utf-8") as fh:
        data: List[Dict[str, Any]] = json.load(fh)

    if not data:
        print("exceptions.json is empty – nothing to retry.")
        return

    # Basic classification by type
    download_errors = [e for e in data if e.get("type") == "download_error"]
    fetch_errors = [e for e in data if e.get("type") == "fetch_error"]

    async with FBDSAsyncScraper(
        base_url=scraper.base_url,
        download_root=scraper.download_root,
        max_concurrency=scraper.max_concurrency,
        request_timeout=scraper.request_timeout,
    )._ensure_client(None)[
        0
    ] as client:  # reuse config, new client
        # Retry file downloads
        download_tasks = []
        for err in download_errors:
            url = err.get("url")
            path_str = err.get("path")
            if not url or not path_str:
                continue
            local_path = Path(path_str)
            download_tasks.append(scraper._download_file(client, url, local_path))

        if download_tasks:
            print(f"Retrying {len(download_tasks)} download_error entries...")
            await asyncio.gather(*download_tasks)

        # For fetch_error we just try fetching the URL again so that
        # future runs are less likely to hit the same issue.
        fetch_tasks = []
        for err in fetch_errors:
            url = err.get("url")
            if not url:
                continue
            fetch_tasks.append(scraper._fetch_html(client, url))

        if fetch_tasks:
            print(f"Retrying {len(fetch_tasks)} fetch_error entries...")
            await asyncio.gather(*fetch_tasks)
