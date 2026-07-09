# Data Preparation

This folder contains the scripts and notebooks used to collect, filter, convert,
and prepare market announcement data for downstream analysis.

## Folder Layout

- `notebooks/` - exploratory and workflow notebooks for data collection,
  extraction, conversion, and analysis.
- `scripts/` - runnable Python scripts for repeatable file processing tasks.
- `__pycache__/` - generated Python bytecode cache.

## Notebooks

- `download_nse_filings.ipynb` - download NSE filing data.
- `NSE_PDFs_Extraction_and_Conversion_to_MD.ipynb` - extract PDF content and
  convert it to markdown.
- `Earning_calls_and_quarterly_updates_parsing.ipynb` - parse earning calls and
  quarterly update content.
- `getting_data_from_yfinance.ipynb` - collect related market/news data from
  yfinance.

## Scripts

- `pdf_seperate.py` - classify announcement metadata into keep, reject, and
  review buckets.
- `create_keep_file_list.py` - create reduced JSON file lists for keep and
  review records.
- `copy_markdown_file_lists.py` - copy selected markdown files into keep and
  review folders.
- `rename_markdown_from_source_url.py` - rename converted markdown files using
  their original source PDF filenames.
