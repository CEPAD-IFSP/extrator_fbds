from extrator_fbds import __version__, FBDSAsyncScraper


def test_version_present():
    assert isinstance(__version__, str) and len(__version__) > 0 and __version__ != "0.0.0"


def test_version_semver_like():
    # Accepts forms like 0.1.0 or 0.1.0.post1
    parts = __version__.split('.')
    assert len(parts) >= 2


def test_scraper_init(tmp_path):
    scraper = FBDSAsyncScraper(download_root=tmp_path)
    assert scraper.download_root.exists()
