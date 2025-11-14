"""Core async scraper logic for FBDS (geo.fbds.org.br).

This module contains the FBDSAsyncScraper class and helpers, without
any CLI/argparse wiring. It is intended to be imported by small
scripts or notebooks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


@dataclass
class DirectoryEntry:
    """Parsed row from the fallback table."""

    name: str
    href: str
    entry_type: str
    modified: str
    size: str


def parse_directory_listing(html: str) -> List[DirectoryEntry]:
    """Parse the h5ai fallback table into structured entries."""

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#fallback table")
    if not table:
        return []

    entries: List[DirectoryEntry] = []
    for row in table.find_all("tr"):
        # header rows contain <th>
        if row.find("th"):
            continue
        cols = row.find_all("td")
        if len(cols) < 4:
            continue
        icon = cols[0].find("img")
        entry_type = icon["alt"].strip().lower() if icon and icon.has_attr("alt") else ""
        link = cols[1].find("a")
        if not link or not link.has_attr("href"):
            continue
        name = link.get_text(strip=True)
        href = link["href"].strip()
        modified = cols[2].get_text(strip=True)
        size = cols[3].get_text(strip=True)
        entries.append(
            DirectoryEntry(
                name=name,
                href=href,
                entry_type=entry_type,
                modified=modified,
                size=size,
            )
        )
    return entries


class FBDSAsyncScraper:
    """Async scraper that works with the FBDS h5ai fallback pages."""

    def __init__(
        self,
        base_url: str = "https://geo.fbds.org.br/",
        download_root: Optional[Path] = None,
        expected_folders: Optional[Iterable[str]] = None,
        max_concurrency: int = 5,
        city_concurrency: int = 1,
        request_timeout: float = 45.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.download_root = (download_root or Path("downloads")).resolve()
        self.download_root.mkdir(parents=True, exist_ok=True)
        self.expected_folders: Set[str] = set(expected_folders) if expected_folders else {
            "APP",
            "HIDROGRAFIA",
            "MAPAS",
            "USO",
        }
        self.max_concurrency = max_concurrency
        # Parallelism across cities (higher level than per-file downloads)
        # Default keeps previous behavior (sequential cities) when = 1
        self.city_concurrency = max(1, int(city_concurrency))
        self.request_timeout = request_timeout
        self.exceptions: List[Dict[str, object]] = []
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0 Safari/537.36"
        )

    # ------------------------------------------------------------------
    # Networking helpers
    # ------------------------------------------------------------------
    def _ensure_client(self, client: Optional[httpx.AsyncClient]) -> Tuple[httpx.AsyncClient, bool]:
        if client is not None:
            return client, False
        # Configure connection pool limits to avoid PoolTimeout when many coroutines
        # are contending for connections. The total limit is tied to max_concurrency
        # so that we never have more concurrent requests than available connections.
        limits = httpx.Limits(max_connections=self.max_concurrency, max_keepalive_connections=self.max_concurrency)
        new_client = httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": self._user_agent},
            timeout=self.request_timeout,
            http2=True,
            limits=limits,
        )
        return new_client, True

    async def _fetch_html(self, client: httpx.AsyncClient, url: str) -> str:
        """Fetch HTML with simple retries and backoff."""

        retries = 3
        delay = 2.0  # seconds

        for attempt in range(1, retries + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
            except (
                httpx.RemoteProtocolError,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
                httpx.PoolTimeout,
            ) as exc:
                # Transient networking / pool issues: retry with backoff, and
                # record a fetch_error on the final failed attempt.
                if attempt == retries:
                    self.exceptions.append(
                        {
                            "type": "fetch_error",
                            "url": url,
                            "error": str(exc),
                            "attempt": attempt,
                        }
                    )
                    raise
                await asyncio.sleep(delay)
            except Exception as exc:  # noqa: BLE001
                self.exceptions.append(
                    {
                        "type": "fetch_error",
                        "url": url,
                        "error": str(exc),
                        "attempt": attempt,
                    }
                )
                raise

    def _href_to_url(self, href: str) -> str:
        normalized = href.strip()
        if not normalized:
            normalized = "/"
        if normalized.startswith("http://") or normalized.startswith("https://"):
            url = normalized
        else:
            if not normalized.startswith("/"):
                normalized = "/" + normalized
            url = urljoin(self.base_url, normalized.lstrip("/"))
        if normalized.endswith("/") and not url.endswith("/"):
            url += "/"
        return url

    def _url_to_relative_path(self, url: str) -> Path:
        path = urlparse(url).path.lstrip("/")
        return Path(path)

    async def _download_file(self, client: httpx.AsyncClient, file_url: str, local_path: Path) -> None:
        async with self._semaphore:
            try:
                if local_path.exists():
                    return
                local_path.parent.mkdir(parents=True, exist_ok=True)
                async with client.stream("GET", file_url) as response:
                    response.raise_for_status()
                    with open(local_path, "wb") as fh:
                        async for chunk in response.aiter_bytes():
                            fh.write(chunk)
            except Exception as exc:  # noqa: BLE001
                self.exceptions.append(
                    {
                        "type": "download_error",
                        "url": file_url,
                        "path": str(local_path),
                        "error": str(exc),
                    }
                )

    async def _download_directory(
        self,
        client: httpx.AsyncClient,
        directory_href: str,
    ) -> None:
        directory_url = self._href_to_url(directory_href)
        html = await self._fetch_html(client, directory_url)
        entries = parse_directory_listing(html)

        file_tasks: List[asyncio.Task[None]] = []
        for entry in entries:
            if entry.name.lower() == "parent directory" or entry.href in {"..", "../"}:
                continue
            target_url = urljoin(directory_url, entry.href)
            if entry.entry_type.startswith("folder"):
                child_href = urlparse(target_url).path
                if not child_href.endswith("/"):
                    child_href += "/"
                await self._download_directory(client, child_href)
            elif entry.entry_type == "file":
                relative = self._url_to_relative_path(target_url)
                local_path = self.download_root / relative
                file_tasks.append(asyncio.create_task(self._download_file(client, target_url, local_path)))

        if file_tasks:
            await asyncio.gather(*file_tasks)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def fetch_states(self, client: Optional[httpx.AsyncClient] = None) -> List[str]:
        client, owns = self._ensure_client(client)
        try:
            html = await self._fetch_html(client, self.base_url)
            entries = parse_directory_listing(html)
            states = [
                e.name
                for e in entries
                if e.entry_type == "folder" and len(e.name) == 2 and e.name.isalpha()
            ]
            states.sort()
            return states
        finally:
            if owns:
                await client.aclose()

    async def fetch_cities(
        self,
        state: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[str]:
        state = state.strip().upper()
        state_href = f"/{state}/"
        client, owns = self._ensure_client(client)
        try:
            html = await self._fetch_html(client, self._href_to_url(state_href))
            entries = parse_directory_listing(html)
            cities = [
                e.name
                for e in entries
                if e.entry_type == "folder" and e.name.lower() != "parent directory"
            ]
            cities.sort()
            return cities
        finally:
            if owns:
                await client.aclose()

    async def describe_city(
        self,
        state: str,
        city: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, object]:
        state = state.strip().upper()
        city = city.strip()
        city_href = f"/{state}/{city}/"
        client, owns = self._ensure_client(client)
        try:
            html = await self._fetch_html(client, self._href_to_url(city_href))
            entries = parse_directory_listing(html)
            folders = [
                e.name
                for e in entries
                if e.entry_type == "folder" and e.name.lower() != "parent directory"
            ]
            files = [e.name for e in entries if e.entry_type == "file"]
            return {
                "state": state,
                "city": city,
                "url": self._href_to_url(city_href),
                "folders": folders,
                "files": files,
            }
        finally:
            if owns:
                await client.aclose()

    async def download_city(
        self,
        state: str,
        city: str,
        folder_filter: Optional[Sequence[str]] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, object]:
        state = state.strip().upper()
        city = city.strip()
        city_href = f"/{state}/{city}/"
        client, owns = self._ensure_client(client)

        try:
            html = await self._fetch_html(client, self._href_to_url(city_href))
            entries = parse_directory_listing(html)

            folder_entries = [
                e for e in entries if e.entry_type == "folder" and e.name.lower() != "parent directory"
            ]
            file_entries = [e for e in entries if e.entry_type == "file"]

            available_folders = [e.name for e in folder_entries]
            available_set = set(available_folders)

            # Track non standard structures
            expected_missing = sorted(self.expected_folders - available_set)
            expected_extra = sorted(available_set - self.expected_folders)
            if expected_missing or expected_extra:
                self.exceptions.append(
                    {
                        "type": "non_standard_structure",
                        "state": state,
                        "city": city,
                        "missing": expected_missing,
                        "extra": expected_extra,
                    }
                )

            if folder_filter:
                requested = [name.strip() for name in folder_filter if name.strip()]
                requested_set = set(requested)
                missing = sorted(requested_set - available_set)
                if missing:
                    self.exceptions.append(
                        {
                            "type": "missing_folders",
                            "state": state,
                            "city": city,
                            "requested": requested,
                            "available": available_folders,
                            "missing": missing,
                        }
                    )
                folders_to_download = [name for name in available_folders if name in requested_set]
            else:
                folders_to_download = available_folders

            # Ensure base directory exists before downloading
            (self.download_root / state / city).mkdir(parents=True, exist_ok=True)

            # Download folders recursively (print each folder when done)
            for entry in folder_entries:
                if entry.name not in folders_to_download:
                    continue
                await self._download_directory(client, entry.href)
                print(f"[{state}/{city}] Finished folder {entry.name}")

            # Download loose files in the city root if any
            file_tasks: List[asyncio.Task[None]] = []
            for entry in file_entries:
                file_url = urljoin(self._href_to_url(city_href), entry.href)
                relative = self._url_to_relative_path(file_url)
                local_path = self.download_root / relative
                file_tasks.append(asyncio.create_task(self._download_file(client, file_url, local_path)))
            if file_tasks:
                await asyncio.gather(*file_tasks)

            return {
                "state": state,
                "city": city,
                "downloaded_folders": folders_to_download,
                "skipped_folders": sorted(set(available_folders) - set(folders_to_download)),
                "root_files": [e.name for e in file_entries],
                "url": self._href_to_url(city_href),
            }
        finally:
            if owns:
                await client.aclose()

    async def download_state(
        self,
        state: str,
        city_filter: Optional[Sequence[str]] = None,
        folder_filter: Optional[Sequence[str]] = None,
        city_concurrency: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, object]]:
        state = state.strip().upper()
        client, owns = self._ensure_client(client)
        try:
            cities = await self.fetch_cities(state, client=client)
            if city_filter:
                keep = {city.strip() for city in city_filter}
                cities = [city for city in cities if city in keep]

            if not cities:
                print(f"[{state}] No cities to download.")
                return []

            results: List[Dict[str, object]] = []
            total = len(cities)

            # Allow parallel downloads across multiple cities while still
            # respecting the per-file max_concurrency via self._semaphore
            # inside _download_file.
            parallel = max(1, int(city_concurrency or self.city_concurrency))
            city_sem = asyncio.Semaphore(parallel)

            async def _run_city(city_name: str) -> Tuple[str, Dict[str, object]]:
                async with city_sem:
                    return city_name, await self.download_city(
                        state=state,
                        city=city_name,
                        folder_filter=folder_filter,
                        client=client,
                    )

            tasks = [asyncio.create_task(_run_city(city)) for city in cities]
            done = 0
            for fut in asyncio.as_completed(tasks):
                city_name, city_result = await fut
                done += 1
                pct = (done / total) * 100
                print(f"[{state}] {done}/{total} cities ({pct:5.1f}%) -> {city_name}")
                results.append(city_result)
                print(
                    f"[{state}] Finished {city_name} | downloaded folders: "
                    f"{city_result['downloaded_folders']}"
                )

            return results
        finally:
            if owns:
                await client.aclose()

    async def download_all(
        self,
        state_filter: Optional[Sequence[str]] = None,
        city_filter: Optional[Dict[str, Sequence[str]]] = None,
        folder_filter: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, object]]:
        client, owns = self._ensure_client(None)
        try:
            states = await self.fetch_states(client=client)
            if state_filter:
                keep_states = {state.strip().upper() for state in state_filter}
                states = [state for state in states if state in keep_states]
            results = []
            for state in states:
                cities_for_state = city_filter.get(state) if city_filter else None
                state_results = await self.download_state(
                    state=state,
                    city_filter=cities_for_state,
                    folder_filter=folder_filter,
                    client=client,
                )
                results.extend(state_results)
            return results
        finally:
            if owns:
                await client.aclose()

    def save_exceptions(self, output_path: Optional[Path] = None) -> None:
        """Persist the current exceptions list to disk.

        This can be called multiple times during a long run; the file will
        always contain the *current* in-memory list of exceptions. If there
        are no exceptions, we still create/overwrite the file with an empty
        JSON array so that progress is visible even when everything succeeds.
        """

        path = output_path or (self.download_root / "exceptions.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            import json

            json.dump(self.exceptions, fh, indent=2, ensure_ascii=False)

    def flush_exceptions(self, output_path: Optional[Path] = None) -> None:
        """Convenience alias for save_exceptions used for incremental writes."""

        self.save_exceptions(output_path=output_path)
