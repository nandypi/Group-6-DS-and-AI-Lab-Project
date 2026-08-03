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
- `sectioner/` contains the sectioning and grouping modules.
- `benchmarking/` contains the reproducible RAG benchmark runners and analysis
  utility described below.

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

The batch-cleaning runner is
`datapreparation/run_prompts/run-whole-doc-prompt-on-all-docs.py`.

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

## How is header aware chunking/sectioning done?

Header-aware sectioning means it uses Markdown headings (`#`, `##`, `###`, etc.) as the main boundaries—not arbitrary fixed-size chunks.

1. It reads the Markdown line by line and identifies headings, paragraphs, tables, lists, images, and page markers.

2. It builds a heading hierarchy:
   - `# Financial Results`
     - `## Revenue`
     - `## Expenses`
   - `# Risk Factors`

   Content after a heading belongs to that heading until another heading at the same or higher level appears.

3. It keeps a complete heading section together if it is at most about **8,000 estimated tokens**. For example, “Financial Results” and all its subheadings stay together if they fit.

4. If a heading section is too large, it splits it first at its child headings. So “Revenue” and “Expenses” become separate sections rather than cutting halfway through their text.

5. Very small neighbouring sibling sections are merged, but only if they share the same parent heading and the combined size stays below 8,000 tokens.

6. If even a single leaf section is too large, it tries safer boundaries in this order:
   - numbered sub-sections such as `Note 1` / `1.`
   - table boundaries (tables are kept whole)
   - page boundaries
   - paragraph boundaries
   A huge single table is split by rows with its table header repeated; a huge single paragraph is split by sentences.

7. It records the full heading path on every output section. For example, a piece under `# Financial Results` → `## Revenue` receives that path as metadata, even when it had to be split further.

It also ignores repeated headers/footers, images, blanks, and known boilerplate while calculating size, so those do not cause unnecessary splits. The original Markdown text itself is preserved in the resulting section.

## Section Cleaning

Grouped sections are cleaned with:

- Prompt: `prompts/KE-prompts-for-nse-docs/KE-section-prompt-v1.md`
- Input: `data/nse_files_final/knowledge_extraction/greater_than_10_pages/sectioned_files`
- Output: `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files`

The batch section-cleaning runner is
`datapreparation/run_prompts/run-section-prompt-on-all-docs.py`.

## RAG Benchmarking and Reproducibility

The benchmark scripts are in `datapreparation/benchmarking/`. They use the
indexed Chroma collection in `chroma_db/`, the OpenAI embedding model and answer
model configured in `embeddings_script/retriever.py`, and the environment values
loaded from the repository `.env` file. Do not commit the `.env` file.

Before any benchmark run:

1. Activate the project virtual environment.
2. Ensure `chroma_db/` was built from the current cleaned source documents. A
   benchmark is only comparable with another run that uses the same indexed
   collection.
3. Ensure the `.env` file contains a valid OpenAI API key and the intended
   `COLLECTION_NAME`.
4. Set `DO_RERANKING` to the mode required by the runner. Each runner refuses
   to start if the setting is incorrect.

### Chroma-Only 50-Question Benchmark

Use this runner to measure the original Chroma order without BGE reranking:

```powershell
.\venv\Scripts\python.exe datapreparation\benchmarking\run_without_reranking_benchmark.py
```

Set `DO_RERANKING=False` before running it. The input file is
`data/infosys_rag_test_dataset_50_queries.csv`. It must contain exactly 50 rows
and these columns:

```text
id, query, source_category, source_document
```

The runner never changes that input. It writes all results to the separate file
`data/infosys_rag_test_dataset_50_queries_without_reranking_results.csv` and
saves it after every completed question. The output retains the four input
columns and adds:

- `llm_answer`
- `retrieved_documents_top_10` and `retrieved_filepaths_top_10`
- `llm_context_filepaths_top_3`
- `recall@3`, `recall@5`, and `recall@7`
- input-token count, per-stage latency, total latency, status, and error fields

For every question, the runner embeds the query and retrieves ten Chroma
candidates. Recall is a per-row `True` or `False` check that the expected
`source_document` appears in ranks 1-3, 1-5, or 1-7, respectively. It sends
only the original ranks 1-3 to `gpt-4o-mini`; it does not load or call the BGE
reranker.

The full filepath is logged for every top-10 candidate. This is important for
long-document section files named `group_001.md`, `group_002.md`, and so on:
their basenames can repeat under different source-document folders. For an
unambiguous recall metric, the input `source_document` should be a unique
filename. If the expected source is a repeated `group_xxx.md` filename, add an
expected full filepath to the dataset and update the matching rule before using
the resulting recall values.

The runner supports small reproducibility trials and continuation runs:

```powershell
# Process only questions 1 and 2.
.\venv\Scripts\python.exe datapreparation\benchmarking\run_without_reranking_benchmark.py --limit 2

# Preserve completed output rows and process questions 3 through 50.
.\venv\Scripts\python.exe datapreparation\benchmarking\run_without_reranking_benchmark.py --start 3 --limit 48
```

The runner matches existing output rows by `id` before a continuation run. To
repeat an experiment from scratch, use a new output filename or remove the old
results CSV manually before starting.

### Recall-Only BGE Reranking Benchmark

Use `run_reranking_recall_benchmark.py` to compare BGE reranking without an
answer-model call. It reads the current 50-question input CSV, retrieves and
reranks 25 Chroma candidates per question, and records the reranked Recall@3,
Recall@5, and Recall@7 values.

```powershell
.\venv\Scripts\python.exe datapreparation\benchmarking\run_reranking_recall_benchmark.py
```

Set `DO_RERANKING=True`. The runner does not call `gpt-4o-mini`, build an LLM
context, or write an answer. Its independent output is
`data/infosys_rag_test_dataset_50_queries_with_reranking_top_25_recall_results.csv`.
For each row, it logs all 25 reranked filenames, full paths, combined BGE
scores, Recall@3/5/7 flags, embedding latency, Chroma latency, reranking
latency, total latency, and status/error fields.

Because the candidate count changed from 10 to 25, do not compare or append to
the earlier 10-candidate reranking-recall CSV. Use this new output file for the
25-candidate experiment.

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
