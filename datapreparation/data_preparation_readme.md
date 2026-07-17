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
- `copy_review_decision_files.py` - copy reviewed markdown files into final GPT
  decision folders based on `metadata/processed/review_decisions.json`.

## Final GPT Review Categorisation

The reviewed markdown files are categorised using:

- Decision file: `metadata/processed/review_decisions.json`
- Source folder: `data/nse_files_final/review`
- Output root: `data/nse_files_final/final_categorisation_by_gpt-5.5`

Run the categorisation script from the repository root:

```bash
python datapreparation/copy_review_decision_files.py
```

Decision routing:

- `ACCEPT` -> `data/nse_files_final/final_categorisation_by_gpt-5.5/accepted_by_gpt`
- `REJECT` -> `data/nse_files_final/final_categorisation_by_gpt-5.5/rejected_by_gpt`
- Any other decision -> `data/nse_files_final/final_categorisation_by_gpt-5.5/uncateorised_by_gpt`

The script creates output folders if needed, preserves file metadata with
`shutil.copy2`, and prints counts for copied, missing, and skipped records.

Latest run status:

- Accepted files copied: 72
- Rejected files copied: 5
- Other-decision files copied: 0
- Missing source files: 38
- Skipped invalid records: 0

The 38 missing files were listed by the script because their `file_name` values
exist in `review_decisions.json` but the corresponding markdown files were not
found in `data/nse_files_final/review`.

## NSE Data Used Downstream

For NSE as a data source, the markdown files used for downstream analysis now
live in these folders:

- `data/nse_files_final/keep`
- `data/nse_files_final/final_categorisation_by_gpt-5.5/accepted_by_gpt`

The `keep` folder contains files accepted by the earlier rule-based filtering
stage. The `accepted_by_gpt` folder contains files from the review bucket that
were accepted after GPT review.
