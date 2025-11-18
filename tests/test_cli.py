import subprocess
import sys


def test_cli_help_runs():
    # Run the module with --help, ensure it exits cleanly and prints expected text.
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "extrator_fbds.fbds_async_scraper",
            "--help",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Async scraper" in proc.stdout
