"""Batch OCR over MAPAS JPGs using extract_year_and_datum.

This script walks the local FBDS download tree (produced by
`fbds_async_scraper.py`) and, for every JPG file inside a `MAPAS`
folder, runs `extract_year_and_datum` from `fbds_ocr.py`.

Results are written to a CSV with columns:

    ESTADO,CIDADE,ANO_BASE,ANO_SIRGAS,FULL

By default it looks under the `downloads` directory at the repo root,
but you can override this with the DOWNLOAD_ROOT environment variable.
"""

from __future__ import annotations

import csv
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List, Tuple

from fbds_ocr import extract_year_and_datum


def iter_mapas_images(download_root: Path) -> Iterable[Tuple[str, str, Path]]:
    """Yield (state, city, image_path) for every JPG in a MAPAS folder.

    Expected structure (created by fbds_async_scraper):
        download_root/STATE/CITY/MAPAS/*.jpg
    """

    for state_dir in sorted(download_root.iterdir()):
        if not state_dir.is_dir():
            continue
        state = state_dir.name
        # Very light filter: state code should be two letters.
        if len(state) != 2 or not state.isalpha():
            continue

        for city_dir in sorted(state_dir.iterdir()):
            if not city_dir.is_dir():
                continue
            city = city_dir.name
            mapas_dir = city_dir / "MAPAS"
            if not mapas_dir.exists() or not mapas_dir.is_dir():
                continue

            for img_path in sorted(mapas_dir.iterdir()):
                if not img_path.is_file():
                    continue
                if img_path.suffix.lower() not in {".jpg", ".jpeg"}:
                    continue
                yield state, city, img_path


def _process_single_image(args: Tuple[str, str, Path]) -> List[str]:
    """Worker function for a single image.

    Runs extract_year_and_datum and returns a list of CSV fields:
        [ESTADO, CIDADE, ANO_BASE, ANO_SIRGAS, FULL]
    """

    state, city, img_path = args
    ocr_result = extract_year_and_datum(str(img_path))
    raw_text = ocr_result.get("raw_text") or ""

    # Clean FULL text for nicer CSV visualization:
    # - replace newlines with spaces
    # - collapse multiple spaces
    # - remove commas
    # - replace double quotes with single quotes
    full = raw_text.replace("\r", " ").replace("\n", " ")
    full = " ".join(full.split())
    full = full.replace(",", " ")
    full = full.replace('"', "'")

    return [
        state,
        city,
        ocr_result.get("ano"),
        ocr_result.get("sirgas"),
        full,
    ]


def run_batch(
    download_root: Path,
    output_csv: Path,
) -> None:
    """Run OCR over all MAPAS JPGs with multiprocessing and write a CSV."""

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    # Collect all work first so we can parallelize safely.
    jobs: List[Tuple[str, str, Path]] = list(iter_mapas_images(download_root))
    total = len(jobs)
    if total == 0:
        print("No MAPAS JPGs found. Nothing to do.")
        return

    max_workers = os.cpu_count() or 1
    print(f"Found {total} images. Using {max_workers} processes for OCR.")

    with open(output_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ESTADO", "CIDADE", "ANO_BASE", "ANO_SIRGAS", "FULL"])

        done = 0
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_job = {
                executor.submit(_process_single_image, job): job for job in jobs
            }

            for future in as_completed(future_to_job):
                row = future.result()
                writer.writerow(row)
                done += 1
                if done % 50 == 0 or done == total:
                    print(f"Processed {done}/{total} images...")

    print(f"Done. Wrote {total} rows to {output_csv}")


def main() -> None:
    # Default to the same root as fbds_async_scraper, but let the user
    # override via environment variable if needed.
    download_root = Path(os.environ.get("DOWNLOAD_ROOT", "downloads")).resolve()
    output_csv = Path("fbds_mapas_ocr.csv").resolve()

    print(f"Scanning MAPAS JPEGs under: {download_root}")
    run_batch(download_root=download_root, output_csv=output_csv)


if __name__ == "__main__":
    main()
