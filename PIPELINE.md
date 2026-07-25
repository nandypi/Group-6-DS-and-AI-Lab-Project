# Data Pipeline

This document records the current data-preparation workflow for the Infosys
investor-information project. It ends with clean Markdown prepared for later
use.

## Scope

- Primary company: Infosys
- Primary source: NSE corporate announcements from the last year
- Supporting sources: Infosys investor-relations documents, Trendlyne, and
  yfinance
- Initial NSE download: 240 PDF announcements

## NSE Announcement Pipeline

### 1. Download and Convert

NSE announcement PDFs were downloaded and converted to Markdown with Docling.

- Download notebook: `datapreparation/download_data/download_nse_filings.ipynb`
- Conversion notebook:
  `datapreparation/data-preprocessing/NSE_PDFs_Extraction_and_Conversion_to_MD.ipynb`

The converted Markdown files were then renamed from their original source URLs
and deduplicated.

- Rename script:
  `datapreparation/data-preprocessing/rename_markdown_from_source_url.py`
- Deduplication script: `datapreparation/data-preprocessing/file-dedup.py`

### 2. Categorise and Review

The Markdown files were classified into `keep`, `reject`, and `review` groups
with keyword rules.

- Categorisation script: `datapreparation/data-preprocessing/pdf_seperate.py`

The `review` group was then assessed with Codex. Review decisions are stored
in `metadata/processed/review_decisions.json`, and the decision-copy script is:

`datapreparation/data-preprocessing/copy_review_decision_files.py`

The resulting final NSE source files are in:

- `data/nse_files_final/keep`
- `data/nse_files_final/final_categorisation_by_gpt-5.5/accepted_by_gpt`

This produced 137 final NSE documents: 65 from `keep` and 72 accepted after
review.

### 3. Split by Page Count

Final NSE documents are split using the `pages` value in their front matter.

- Script: `datapreparation/data-preprocessing/copy_files_by_page_count.py`
- Ten pages or fewer:
  `data/nse_files_final/categorisation_by_pages/equal_or_less_than_10_pages`
- More than ten pages:
  `data/nse_files_final/categorisation_by_pages/more_than_10_pages`

Current counts:

- Ten pages or fewer: 109 documents
- More than ten pages: 28 documents

### 4. Clean Documents with Ten Pages or Fewer

Documents with ten pages or fewer are cleaned as complete documents with the
v6 whole-document prompt. The cleaning preserves substantive content, tables,
and figures while removing filing wrappers, conversion noise, and other
non-substantive formatting.

- Prompt: `prompts/KE-prompts-for-nse-docs/KE-whole-document-prompt-v6.md`
- Script: `datapreparation/run-whole-doc-prompt-on-all-docs.py`
- Input:
  `data/nse_files_final/categorisation_by_pages/equal_or_less_than_10_pages`
- Output:
  `data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages`

The script uses the Codex Python SDK with ChatGPT authentication, medium
reasoning effort, output validation, one retry for invalid responses, and
resume support for valid existing outputs.

### 5. Section and Clean Documents Longer than Ten Pages

Documents longer than ten pages are first split into logical sections and then
grouped into prompt-sized Markdown files.

- Sectioner module: `datapreparation/sectioner`
- Section manifests:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/sections`
- Validation reports:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/reports`
- Grouped sections:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/sectioned_files`

The grouped output preserves one folder per source document. It retains the
original document name and source-section identifiers, but does not include
estimated page-range metadata.

The grouped sections are cleaned with the v1 section prompt.

- Prompt: `prompts/KE-prompts-for-nse-docs/KE-section-prompt-v1.md`
- Script: `datapreparation/run-section-prompt-on-all-docs.py`
- Cleaned-section output:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files`

The section-cleaning script preserves the original YAML metadata block, adds a
second generated metadata block, validates both, retries invalid responses
once, and can resume from valid outputs.

## Demo Documents

Ten representative NSE documents were selected for demo validation.

- Input: `data/demo-bot-data`
- Cleaned output: `data/demo-bot-output`
- Script: `datapreparation/run-whole-doc-prompt-on-demo-bot.py`
- Prompt: `prompts/KE-prompts-for-nse-docs/KE-whole-document-prompt-v6.md`

## Infosys Investor-Relations Documents

Earnings calls, press conferences, fact sheets, and IFRS/INR press releases
are treated as whole documents because they are within the ten-page processing
scope. The same whole-document cleaning approach is applied.

- Source: `data/infosys_earning_calls_press_conf_fact_sheets_results`
- Cleaned Markdown:
  `data/infosys_earning_calls_press_conf_fact_sheets_results/infosys_ir_earning_calls_clean_markdowns`

## Supplementary Market Sources

Trendlyne and yfinance provide supporting Infosys market and research context.
Each source has raw PDFs, extracted Markdown, and cleaned Markdown.

- Trendlyne: `data/trendlyne`
- yfinance: `data/yfinance`
- Raw PDFs: `pdfs/`
- Extracted Markdown: `mds/`
- Clean Markdown: `clean-mds/`

For these sources, raw PDFs were supplied directly to ChatGPT to create clean,
readable Markdown for the project knowledge base. The conversion used the
source-specific templates in `prompts/KE-prompts`:

- `prompts/KE-prompts/brokerage-reports-ke.md` for brokerage-report material
- `prompts/KE-prompts/yfinance-ke.md` for yfinance material

## Embedding, Retrieval, and Q&A Prototype

The current retrieval prototype indexes the cleaned demo corpus and uses it to
answer investor questions. It is implemented in `embeddings_script` and has
three stages.

### 1. Index Markdown Documents

`embeddings_script/index_documents.py` recursively reads Markdown files from its
`DATA_FOLDER`, creates one OpenAI `text-embedding-3-small` vector per complete
file, and stores the document, vector, and file metadata in a persistent
Chroma collection.

- Current collection name: `finance_documents`
- Current source corpus: the 10 cleaned demo documents in `data/demo-bot-output`
- Persistent database: `embeddings_script/chroma_db`
- Stored metadata: filename, full file path, and parent-folder name as company

The script currently contains a machine-specific absolute `DATA_FOLDER` path.
Before indexing, update that value to the intended local Markdown folder. The
collection name and database path can instead be set with the
`COLLECTION_NAME` and `CHROMA_DB_PATH` environment variables.

### 2. Similarity Search

`embeddings_script/search.py` embeds its example question, queries the
`finance_documents` collection, and prints the three nearest documents with a
short preview. It is a quick check that the index is available and returning
relevant source material.

### 3. Retrieval-Augmented Answers

`embeddings_script/retriever.py` is an interactive command-line question and
answer loop. For each question, it:

1. creates a `text-embedding-3-small` query vector;
2. retrieves the three closest Chroma documents;
3. prints the retrieved filenames, metadata, distances when available, and
   previews;
4. sends the complete retrieved documents to `gpt-4o-mini`; and
5. instructs the model to answer only from that context or report that the
   information was not found.

The prototype does not currently chunk long documents, apply metadata filters,
or provide citations in the generated answer. These are important constraints
when interpreting retrieval quality.

### Run the Prototype

Set `OPENAI_API_KEY` in a repository-root `.env` file. The Python environment
must include `openai`, `chromadb`, `python-dotenv`, and `tqdm`. Run from the
embedding-script directory so the relative Chroma path resolves correctly:

```powershell
Set-Location embeddings_script
..\venv\Scripts\python.exe index_documents.py # after setting DATA_FOLDER
..\venv\Scripts\python.exe search.py
..\venv\Scripts\python.exe retriever.py
```
