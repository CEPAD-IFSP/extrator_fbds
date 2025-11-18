"""FBDS Extractor - Async scraper and OCR for geo.fbds.org.br data.

This package provides tools to:
- Download geodata from FBDS (FBDSAsyncScraper)
- Extract year and datum information from MAPAS images (OCR)
- Batch process downloaded images

Main components:
- FBDSAsyncScraper: Async HTTP client for downloading FBDS data
- extract_year_and_datum: OCR function to extract metadata from map images
- run_batch: Batch OCR processor for downloaded MAPAS directories
"""

from extrator_fbds.fbds_core import FBDSAsyncScraper
from extrator_fbds.fbds_ocr import extract_year_and_datum

__version__ = "0.1.0"
__all__ = ["FBDSAsyncScraper", "extract_year_and_datum"]
