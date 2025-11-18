"""Example Airflow DAG for FBDS data extraction.

This DAG demonstrates how to:
1. Download FBDS geodata for specific states using FBDSAsyncScraper
2. Run OCR on downloaded MAPAS images to extract year and datum information
3. Store results in a timestamped CSV file

Prerequisites:
- Install extrator_fbds package in your Airflow environment:
  pip install git+https://github.com/CEPAD-IFSP/extrator_fbds.git
- Ensure Tesseract OCR is installed on Airflow workers
- Configure appropriate file paths and concurrency settings

Usage:
- Place this file in your Airflow dags/ folder, or
- Use it as a reference to create your own DAG
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

# Import the package functions
from extrator_fbds import FBDSAsyncScraper
from extrator_fbds.run_fbds_ocr_batch_mp import run_batch_mp


# Configuration - adjust these for your environment
DEFAULT_ARGS = {
    "owner": "cepad",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# Paths - use a shared volume or network storage for multi-worker setups
DOWNLOAD_ROOT = Path("/data/fbds/downloads")
OUTPUT_ROOT = Path("/data/fbds/results")

# States to download (adjust as needed)
STATES_TO_DOWNLOAD = ["SP", "MG", "RJ"]

# Concurrency settings
MAX_CONCURRENCY = 8  # per-file downloads
CITY_CONCURRENCY = 3  # parallel cities
OCR_MAX_WORKERS = 4  # OCR processes


def download_fbds_data(**context):
    """Task 1: Download FBDS data for specified states."""
    execution_date = context["execution_date"]
    print(f"Starting FBDS download for execution date: {execution_date}")

    # Create scraper instance
    scraper = FBDSAsyncScraper(
        download_root=DOWNLOAD_ROOT,
        max_concurrency=MAX_CONCURRENCY,
        city_concurrency=CITY_CONCURRENCY,
    )

    # Run the download asynchronously
    results = asyncio.run(
        scraper.download_all(
            state_filter=STATES_TO_DOWNLOAD,
            folder_filter=["MAPAS"],  # Only download MAPAS for OCR
        )
    )

    # Save exceptions log
    scraper.save_exceptions()

    print(f"Downloaded data for {len(results)} cities")
    print(f"Exceptions logged to: {DOWNLOAD_ROOT / 'exceptions.json'}")

    return {"cities_processed": len(results)}


def run_ocr_processing(**context):
    """Task 2: Run OCR on downloaded MAPAS images."""
    execution_date = context["execution_date"]
    date_str = execution_date.strftime("%Y%m%d")

    output_csv = OUTPUT_ROOT / f"fbds_mapas_ocr_{date_str}.csv"
    print(f"Starting OCR processing, output to: {output_csv}")

    # Run batch OCR with multiprocessing
    run_batch_mp(
        download_root=DOWNLOAD_ROOT,
        output_csv=output_csv,
        max_workers=OCR_MAX_WORKERS,
    )

    print(f"OCR completed. Results saved to: {output_csv}")

    return {"output_file": str(output_csv)}


def cleanup_old_data(**context):
    """Task 3 (optional): Clean up downloads older than N days."""
    # This is just a placeholder - implement your cleanup logic
    print("Cleanup task - implement retention policy if needed")
    # Example: delete downloads older than 30 days, keep only recent CSVs, etc.


# Define the DAG
with DAG(
    dag_id="fbds_monthly_extraction",
    default_args=DEFAULT_ARGS,
    description="Monthly FBDS geodata extraction and OCR processing",
    schedule_interval="0 2 1 * *",  # Run at 2 AM on the 1st of each month
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["fbds", "geodata", "ocr"],
) as dag:

    # Task 1: Download FBDS data
    download_task = PythonOperator(
        task_id="download_fbds_data",
        python_callable=download_fbds_data,
        execution_timeout=timedelta(hours=6),
    )

    # Task 2: Run OCR on downloaded images
    ocr_task = PythonOperator(
        task_id="run_ocr_processing",
        python_callable=run_ocr_processing,
        execution_timeout=timedelta(hours=2),
    )

    # Task 3: Optional cleanup
    cleanup_task = PythonOperator(
        task_id="cleanup_old_data",
        python_callable=cleanup_old_data,
        execution_timeout=timedelta(minutes=30),
    )

    # Define task dependencies
    download_task >> ocr_task >> cleanup_task


# Alternative: Use PythonVirtualenvOperator for isolated environment
# Uncomment and modify if you want each task to run in its own virtualenv:
"""
from airflow.operators.python import PythonVirtualenvOperator

download_task_venv = PythonVirtualenvOperator(
    task_id="download_fbds_data_venv",
    python_callable=download_fbds_data,
    requirements=[
        "git+https://github.com/CEPAD-IFSP/extrator_fbds.git",
    ],
    system_site_packages=False,
    execution_timeout=timedelta(hours=6),
)
"""
