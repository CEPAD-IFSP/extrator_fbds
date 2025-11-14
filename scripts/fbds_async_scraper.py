"""CLI entrypoint for FBDS async scraper.

This script wires argparse onto the core FBDSAsyncScraper in
`fbds_core.py` and adds a helper mode to retry failures from
an exceptions JSON file.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from fbds_core import FBDSAsyncScraper
from fbds_retry_failures import retry_failures_from_file


async def run_cli(args: argparse.Namespace) -> None:
    scraper = FBDSAsyncScraper(
        base_url=args.base_url,
        download_root=args.output,
        max_concurrency=args.max_concurrency,
        city_concurrency=args.city_concurrency,
    )

    if args.retry_failures:
        # Only retry failures; do not run a fresh scrape.
        exceptions_path = args.exceptions or (scraper.download_root / "exceptions.json")
        await retry_failures_from_file(exceptions_path, scraper)
        scraper.flush_exceptions(args.exceptions)
        return

    async with scraper._ensure_client(None)[0] as client:  # use scraper config
        if args.list_states:
            states = await scraper.fetch_states(client=client)
            print("States:", ", ".join(states))

        if args.list_cities:
            state = args.list_cities.strip().upper()
            cities = await scraper.fetch_cities(state, client=client)
            print(f"Cities in {state} ({len(cities)}):")
            for name in cities:
                print(" -", name)

        if args.describe_city:
            state, city = args.describe_city
            info = await scraper.describe_city(state, city, client=client)
            print(f"City {info['state']}/{info['city']}")
            print(" Folders:")
            for folder in info["folders"]:
                print("  -", folder)
            if info["files"]:
                print(" Files:")
                for file_name in info["files"]:
                    print("  -", file_name)

        folder_filter = args.folders

        if args.download_city:
            state = args.download_city[0]
            cities = args.download_city[1:] or []
            if not cities:
                raise SystemExit("--download-city requires at least one city name")
            for city in cities:
                result = await scraper.download_city(state, city, folder_filter, client=client)
                print(f"Downloaded {result['state']}/{result['city']}: {result['downloaded_folders']}")

        if args.download_state:
            state = args.download_state
            results = await scraper.download_state(
                state,
                folder_filter=folder_filter,
                city_concurrency=args.city_concurrency,
                client=client,
            )
            print(f"Downloaded state {state} ({len(results)} cities)")
            scraper.flush_exceptions(args.exceptions)

        if args.download_all:
            states = args.states or None
            results = await scraper.download_all(
                state_filter=states,
                folder_filter=folder_filter,
            )
            print(f"Downloaded {len(results)} cities across {len(states) if states else 'all'} states")
            scraper.flush_exceptions(args.exceptions)

    # Final flush to capture any errors from other commands
    scraper.flush_exceptions(args.exceptions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Async scraper for geo.fbds.org.br")
    parser.add_argument("--base-url", default="https://geo.fbds.org.br/", help="Root URL of the repository")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("downloads"),
        help="Directory where files will be saved",
    )
    parser.add_argument("--max-concurrency", type=int, default=5, help="Maximum concurrent downloads")
    parser.add_argument(
        "--city-concurrency",
        type=int,
        default=1,
        help="How many cities to download in parallel (in addition to per-file concurrency)",
    )
    parser.add_argument(
        "--folders",
        nargs="*",
        help="Limit downloads to these top-level folders (e.g. APP HIDROGRAFIA)",
    )
    parser.add_argument(
        "--exceptions",
        type=Path,
        help="Optional path to store/read the exceptions JSON log",
    )
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help="Read exceptions.json and retry only failed downloads/requests",
    )

    parser.add_argument("--list-states", action="store_true", help="List available state codes")
    parser.add_argument("--list-cities", help="List cities for the provided state code")
    parser.add_argument(
        "--describe-city",
        nargs=2,
        metavar=("STATE", "CITY"),
        help="Show folder structure for a specific city",
    )
    parser.add_argument(
        "--download-city",
        nargs="+",
        metavar=("STATE", "CITY"),
        help="Download specific city (usage: --download-city SP SAO_PAULO SANTOS)",
    )
    parser.add_argument("--download-state", help="Download all cities for a state")
    parser.add_argument(
        "--download-all",
        action="store_true",
        help="Download every state (combine with --states to filter)",
    )
    parser.add_argument(
        "--states",
        nargs="*",
        help="State codes to use with --download-all",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run_cli(args))


if __name__ == "__main__":
    main()