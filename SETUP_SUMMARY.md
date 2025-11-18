# Setup Summary: Converting extrator_fbds to an Airflow-Ready Package

## What Changed

### 1. Package Structure
- ✅ Renamed `scripts/` → `extrator_fbds/` (proper Python package name)
- ✅ Added `extrator_fbds/__init__.py` exposing main API:
  - `FBDSAsyncScraper`
  - `extract_year_and_datum`
- ✅ Fixed all internal imports to use absolute package imports

### 2. Packaging Files
- ✅ Created `pyproject.toml` with:
  - Project metadata and dependencies
  - CLI entrypoints: `fbds-scraper`, `fbds-ocr`, `fbds-ocr-mp`
  - Version 0.1.0
- ✅ Created `requirements.txt` for easier pip installs
- ✅ Updated `.gitignore` to exclude generated files

### 3. API Improvements
- ✅ Refactored `run_batch()` and `run_batch_mp()` to accept explicit parameters:
  - `download_root`: where data lives (no longer env-var only)
  - `output_csv`: where to save results
  - `max_workers`: control parallelism
  - All parameters optional with sensible defaults
- ✅ Added `city_concurrency` parameter to scraper for parallel city downloads

### 4. Documentation
- ✅ Updated README with:
  - Installation instructions (pip install from git)
  - Programmatic usage examples
  - Airflow integration guide
  - New CLI command names
- ✅ Created `examples/airflow_dag_example.py` with complete working DAG

### 5. Testing
- ✅ Package installs successfully: `pip install -e .`
- ✅ All imports work correctly
- ✅ CLI entrypoints functional: `fbds-scraper`, `fbds-ocr`, `fbds-ocr-mp`
- ✅ No compilation errors

## Installation for Airflow

### Option 1: Direct from GitHub (recommended)
```bash
pip install git+https://github.com/CEPAD-IFSP/extrator_fbds.git
```

### Option 2: Editable install (for development)
```bash
git clone https://github.com/CEPAD-IFSP/extrator_fbds.git
cd extrator_fbds
pip install -e .
```

### Option 3: In Airflow DAG with PythonVirtualenvOperator
```python
from airflow.operators.python import PythonVirtualenvOperator

task = PythonVirtualenvOperator(
    task_id="download_fbds",
    python_callable=my_function,
    requirements=["git+https://github.com/CEPAD-IFSP/extrator_fbds.git"],
)
```

## Using in Airflow DAGs

### Simple Example
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from extrator_fbds import FBDSAsyncScraper
from extrator_fbds.run_fbds_ocr_batch_mp import run_batch_mp
import asyncio
from pathlib import Path

def download_fbds_task():
    scraper = FBDSAsyncScraper(
        download_root=Path("/data/fbds"),
        max_concurrency=8,
        city_concurrency=3,
    )
    asyncio.run(scraper.download_state("SP", folder_filter=["MAPAS"]))
    scraper.save_exceptions()

def ocr_task():
    run_batch_mp(
        download_root=Path("/data/fbds"),
        output_csv=Path("/data/results/ocr.csv"),
        max_workers=4,
    )

with DAG("fbds_extraction", schedule_interval="@monthly") as dag:
    download = PythonOperator(task_id="download", python_callable=download_fbds_task)
    ocr = PythonOperator(task_id="ocr", python_callable=ocr_task)
    download >> ocr
```

See `examples/airflow_dag_example.py` for a complete production-ready example.

## CLI Usage (unchanged, but new command names)

### Old commands (no longer work):
```bash
python scripts/fbds_async_scraper.py --list-states
python scripts/run_fbds_ocr_batch.py
```

### New commands:
```bash
fbds-scraper --list-states
fbds-scraper --download-state SP --folders MAPAS --max-concurrency 8 --city-concurrency 3
fbds-ocr      # sequential
fbds-ocr-mp   # parallel (recommended)
```

## Key Benefits

1. **Single codebase**: Airflow DAGs import directly from this repo
2. **No duplication**: Changes here automatically propagate to Airflow
3. **Version control**: `pip install git+...@v0.2.0` for specific versions
4. **Programmatic API**: Pass parameters directly, no env vars needed
5. **Production ready**: Proper package structure, dependencies managed
6. **Flexible deployment**: Works in virtualenvs, containers, Airflow workers

## Next Steps

1. Test the DAG in your Airflow environment
2. Adjust paths, concurrency, and schedule to your needs
3. Consider adding monitoring/alerting hooks
4. Tag releases when you want stable versions: `git tag v0.1.0`

## Files to Commit

New/Modified:
- `extrator_fbds/` (renamed from scripts/)
- `pyproject.toml`
- `requirements.txt`
- `README.md`
- `examples/airflow_dag_example.py`
- `.gitignore`

Everything is ready to commit and push!
