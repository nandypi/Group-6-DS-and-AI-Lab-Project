# Data Pipeline

This document tracks the data preparation pipeline completed so far for the NSE
data source.

## Scope

- Data source: NSE
- Company/stock: Infosys
- Time window: last one year of NSE PDF announcements
- Initial PDF count: 240

## Pipeline Stages

### Download NSE PDFs

Downloaded all NSE announcement PDFs from the last year for Infosys.

- Output count: 240 PDFs
- Script/notebook used: `datapreparation/download_data/download_nse_filings.ipynb`

### Convert PDFs to Markdown

Converted the downloaded PDFs into markdown files using the `docling` library.

- Script/notebook used:
  `datapreparation/data-preprocessing/NSE_PDFs_Extraction_and_Conversion_to_MD.ipynb`

### Rename Markdown Files

Renamed converted markdown files using their original source PDF URLs so the
markdown filenames remain traceable to the NSE source files.

- Script used: `datapreparation\data-preprocessing\rename_markdown_from_source_url.py`

### Deduplicate Markdown Files

Deduplicated markdown files where duplicate files had only a hash-code suffix
added to the original file name.

- Script used: `datapreparation/data-preprocessing/file-dedup.py`

### Rule-Based Document Categorisation

Classified the 240 documents into three groups using hardcoded keyword rules:

- `keep`: documents accepted by the rules
- `reject`: documents rejected by the rules
- `review`: documents that did not clearly fall into either group

- Script used: `datapreparation\data-preprocessing\pdf_seperate.py`

### GPT Review of Ambiguous Files

For the `review` group, we used Codex CLI with
`model=gpt-5.5-medium-reasoning` to make the final classification.

- Prompt used: `prompts/review-files-using-codex.txt`
- Review decision file: `metadata/processed/review_decisions.json`
- Script used to copy reviewed files:
  `datapreparation/data-preprocessing/copy_review_decision_files.py`

GPT-reviewed files were copied into:

- `data/nse_files_final/final_categorisation_by_gpt-5.5/accepted_by_gpt`
- `data/nse_files_final/final_categorisation_by_gpt-5.5/rejected_by_gpt`
- `data/nse_files_final/final_categorisation_by_gpt-5.5/uncateorised_by_gpt`

## Final NSE Files of Interest

For NSE preprocessing and downstream analysis, use files from:

- `data/nse_files_final/keep`
- `data/nse_files_final/final_categorisation_by_gpt-5.5/accepted_by_gpt`

Current file counts:

- `accepted_by_gpt`: 72 files
- `keep`: 65 files
- Total files: 137

## Page-Count Categorisation

The final NSE files of interest were further categorised using the top-level
`pages` metadata key in each markdown file.

- Script used: `datapreparation/data-preprocessing/copy_files_by_page_count.py`

Output folders:

- `data/nse_files_final/categorisation_by_pages/equal_or_less_than_10_pages`
- `data/nse_files_final/categorisation_by_pages/more_than_10_pages`

Current file counts:

- `equal_or_less_than_10_pages`: 109 files
- `more_than_10_pages`: 28 files
- Total files: 137
