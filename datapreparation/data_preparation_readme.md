# Data Preparation

This folder contains the scripts and notebooks that prepare Infosys data from
multiple sources for the project workflows. The first part of this guide covers
NSE announcements; the later sections cover Infosys investor-relations,
Trendlyne, and yfinance sources.

## Current NSE Workflow

1. Download NSE announcement PDFs.
2. Convert the PDFs to Markdown.
3. Rename, deduplicate, categorise, and review the Markdown files.
4. Split the final documents by page count.
5. Clean documents with 10 pages or fewer as complete documents.
6. Split documents longer than 10 pages into grouped Markdown sections, then
   clean each section separately.

The final NSE source documents are split into these folders:

- `data/nse_files_final/categorisation_by_pages/equal_or_less_than_10_pages`
- `data/nse_files_final/categorisation_by_pages/more_than_10_pages`

## Scripts and Notebooks

- `download_data/download_nse_filings.ipynb` downloads NSE filing data.
- `data-preprocessing/NSE_PDFs_Extraction_and_Conversion_to_MD.ipynb` converts
  PDFs to Markdown with Docling.
- `data-preprocessing/rename_markdown_from_source_url.py` renames converted
  Markdown files from their source URLs.
- `data-preprocessing/file-dedup.py` removes duplicate Markdown files.
- `data-preprocessing/pdf_seperate.py` classifies files into `keep`, `reject`,
  and `review` groups.
- `data-preprocessing/copy_review_decision_files.py` copies GPT-reviewed files
  into the final categorisation folders.
- `run-whole-doc-prompt-on-demo-bot.py` cleans the demo Markdown documents.
- `run-whole-doc-prompt-on-all-docs.py` cleans all final NSE documents with 10
  pages or fewer.
- `run-section-prompt-on-all-docs.py` cleans grouped sections from documents
  longer than 10 pages.
- `sectioner/` contains the sectioning and grouping modules.

## Final NSE Source Set

Rule-based categorisation places Markdown files into `keep`, `reject`, and
`review` groups. The review files are then assessed with GPT/Codex using the
decisions in `metadata/processed/review_decisions.json`.

The final NSE data source is the union of:

- Files accepted directly by the hardcoded rules:
  `data/nse_files_final/keep`
- Files from the `review` group accepted by GPT:
  `data/nse_files_final/final_categorisation_by_gpt-5.5/accepted_by_gpt`

The decision-copy script also writes rejected and uncategorised review files
to sibling folders, but those files are not part of the final NSE source set.

Run the decision-copy script from the repository root:

```powershell
.\venv\Scripts\python.exe datapreparation\data-preprocessing\copy_review_decision_files.py
```

The combined final NSE source set is then split by page count for cleaning.

## Whole-Document Cleaning

Documents with 10 pages or fewer are cleaned with:

- Prompt: `prompts/KE-prompts-for-nse-docs/KE-whole-document-prompt-v6.md`
- Input: `data/nse_files_final/categorisation_by_pages/equal_or_less_than_10_pages`
- Output: `data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages`

Run all eligible documents from the repository root:

```powershell
.\venv\Scripts\python.exe datapreparation\run-whole-doc-prompt-on-all-docs.py
```

Run one document only:

```powershell
.\venv\Scripts\python.exe datapreparation\run-whole-doc-prompt-on-all-docs.py --file example.md
```

The script uses the official Codex Python SDK with ChatGPT authentication. It
uses medium reasoning effort, validates Markdown output, retries an invalid
response once, and skips valid existing output files so a run can resume.

Use `--overwrite` only when every existing output should be regenerated.

## Infosys Investor-Relations Documents

The documents in `data/infosys_earning_calls_press_conf_fact_sheets_results`
are processed with the same whole-document cleaning approach as the NSE
documents with 10 pages or fewer. This collection contains Infosys earnings
calls, press conferences, fact sheets, and IFRS/INR press releases.

- Source Markdown: `data/infosys_earning_calls_press_conf_fact_sheets_results`
- Cleaned Markdown: `data/infosys_earning_calls_press_conf_fact_sheets_results/infosys_ir_earning_calls_clean_markdowns`
- Cleaning approach: the v6 whole-document prompt and ChatGPT/Codex workflow

All documents in this collection are within the whole-document processing
scope, so they are cleaned as complete documents rather than being split into
sections. The resulting Markdown is ready to be used alongside the cleaned NSE
filings in the downstream investor-information workflow.

## Long-Document Sectioning and Grouping

Documents longer than 10 pages are processed in two steps.

First, generate JSON manifests, individual section files, and reports:

```powershell
.\venv\Scripts\python.exe -m datapreparation.sectioner.cli `
  --input data\nse_files_final\categorisation_by_pages\more_than_10_pages `
  --output data\nse_files_final\knowledge_extraction\greater_than_10_pages\sections
```

Then group consecutive sections for prompt processing:

```powershell
.\venv\Scripts\python.exe -m datapreparation.sectioner.concatenate_sections `
  --manifests data\nse_files_final\knowledge_extraction\greater_than_10_pages\sections `
  --output data\nse_files_final\knowledge_extraction\greater_than_10_pages\sectioned_files
```

The sectioner outputs are:

- Manifests: `data/nse_files_final/knowledge_extraction/greater_than_10_pages/sections`
- Reports: `data/nse_files_final/knowledge_extraction/greater_than_10_pages/reports`
- Grouped sections: `data/nse_files_final/knowledge_extraction/greater_than_10_pages/sectioned_files`

The grouped-section layout is preserved per source document:

```text
sectioned_files/
  source_document_name/
    group_001.md
    group_002.md
```

Grouped section files retain the original `document_name` and source-section
identifiers. They do not include estimated `page_start` or `page_end` metadata.

## Section Cleaning

Grouped sections are cleaned with:

- Prompt: `prompts/KE-prompts-for-nse-docs/KE-section-prompt-v1.md`
- Input: `data/nse_files_final/knowledge_extraction/greater_than_10_pages/sectioned_files`
- Output: `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files`

Run all grouped sections:

```powershell
.\venv\Scripts\python.exe datapreparation\run-section-prompt-on-all-docs.py
```

Run one source-document folder only:

```powershell
.\venv\Scripts\python.exe datapreparation\run-section-prompt-on-all-docs.py `
  --folder Infosys_02072025225219_SEfiling_AGMtranscript_2025
```

The section-cleaning script preserves each input section's original YAML block,
adds a generated YAML block with section metadata, validates both blocks, uses
medium reasoning effort, retries an invalid response once, and resumes by
skipping valid existing outputs.

## Supplementary Market Sources

The project also includes supporting Infosys research material from Trendlyne
and yfinance. These sources broaden the dataset beyond stock-exchange filings
by adding market context, company research, and news-oriented information.

- Trendlyne data: `data/trendlyne`
- yfinance data: `data/yfinance`

Each source follows the same simple, traceable layout:

```text
pdfs/       Raw source PDFs
mds/        Markdown extracted from the PDFs
clean-mds/  Clean Markdown used for downstream retrieval
```

For these supplementary sources, the raw PDFs were supplied directly to
ChatGPT to produce clean, readable Markdown. This direct cleaning workflow
preserves the substantive research content while removing conversion noise and
unnecessary formatting, creating a more retrieval-ready knowledge base for
the investor-information workflow.

The ChatGPT conversion used the source-specific templates in
`prompts/KE-prompts`:

- `prompts/KE-prompts/brokerage-reports-ke.md` for brokerage-report material
- `prompts/KE-prompts/yfinance-ke.md` for yfinance material
