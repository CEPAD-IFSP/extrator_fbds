"""FBDS Extractor - Async scraper and OCR for geo.fbds.org.br data.

Public API:
 - FBDSAsyncScraper: async HTTP client for downloading FBDS data
 - extract_year_and_datum: OCR function to extract metadata from MAPAS images

The package exposes a single version attribute ``__version__`` resolved
dynamically from the installed distribution metadata. A fallback is
kept for editable installs where the package name may not resolve.
"""

from extrator_fbds.fbds_core import FBDSAsyncScraper
from extrator_fbds.fbds_ocr import extract_year_and_datum

try:  # pragma: no cover - simple metadata access
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("extrator_fbds")
except Exception:  # noqa: BLE001 - broad to guarantee attribute exists
    # Fallback matches pyproject.toml version; update when releasing.
    __version__ = "0.1.2"

__all__ = ["FBDSAsyncScraper", "extract_year_and_datum", "__version__"]
