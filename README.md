# Public Update Analyser

Public Update Analyser (PUA) prepares public Infosys information for an
investor-focused application. It is intended to help retail and small
institutional investors work with company disclosures and supporting research
more easily.

## Current Data Sources

| Source | Content | Prepared output |
| --- | --- | --- |
| NSE | Corporate-announcement PDFs and Markdown | Clean Markdown from whole documents or grouped sections |
| Infosys investor relations | Earnings calls, press conferences, fact sheets, and IFRS/INR press releases | Clean whole-document Markdown |
| Trendlyne | Stock and research reports | Clean Markdown |
| yfinance | Supporting market and news material | Clean Markdown |

## Data Preparation Flow

```text
NSE PDFs
  -> Markdown conversion
  -> rename, deduplicate, and categorise
  -> hardcoded keep + GPT-accepted review files
  -> split by page count
     -> <=10 pages: clean complete document
     -> >10 pages: section, group, and clean each section

Infosys investor-relations PDFs
  -> clean complete document

Trendlyne and yfinance PDFs
  -> ChatGPT cleaning with source-specific prompts
  -> clean Markdown

Clean demo Markdown
  -> OpenAI embeddings
  -> persistent Chroma vector collection
  -> similarity retrieval
  -> context-grounded investor Q&A
```

For NSE, the final source set combines documents retained by the rule-based
`keep` category with files from the `review` category accepted by GPT. Documents
with 10 pages or fewer use the whole-document cleaning prompt; longer documents
are sectioned and grouped before cleaning.

## Main Data Locations

- Final NSE source folders: `data/nse_files_final/keep` and
  `data/nse_files_final/final_categorisation_by_gpt-5.5/accepted_by_gpt`
- Whole-document NSE output:
  `data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages`
- Grouped long-document NSE sections:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/sectioned_files`
- Cleaned long-document NSE sections:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files`
- Infosys investor-relations documents:
  `data/infosys_earning_calls_press_conf_fact_sheets_results`
- Trendlyne data: `data/trendlyne`
- yfinance data: `data/yfinance`

## Directory Structure

```text
Group-6-DS-and-AI-Lab-Project/
+-- data/
|   +-- demo-bot-data/                          # Demo source Markdown
|   +-- demo-bot-output/                        # Cleaned demo Markdown
|   +-- infosys_earning_calls_press_conf_fact_sheets_results/
|   |   +-- infosys_ir_earning_calls_clean_markdowns/
|   +-- nse_files_final/
|   |   +-- keep/                               # Rule-based accepted NSE files
|   |   +-- final_categorisation_by_gpt-5.5/     # GPT review outputs
|   |   +-- categorisation_by_pages/             # <=10-page and >10-page files
|   |   +-- whole_document_cleaning/             # Cleaned <=10-page NSE files
|   |   +-- knowledge_extraction/
|   |       +-- greater_than_10_pages/           # Sections and cleaned sections
|   +-- trendlyne/                               # PDFs, Markdown, clean Markdown
|   +-- yfinance/                                # PDFs, Markdown, clean Markdown
+-- datapreparation/
|   +-- data-preprocessing/                      # NSE conversion and filtering
|   +-- download_data/                           # NSE download notebooks
|   +-- sectioner/                               # Long-document sectioning tools
|   +-- run-whole-doc-prompt-on-all-docs.py
|   +-- run-section-prompt-on-all-docs.py
|   +-- data_preparation_readme.md
+-- metadata/                                    # Review decisions and metadata
+-- prompts/
|   +-- KE-prompts/                              # Trendlyne and yfinance prompts
|   +-- KE-prompts-for-nse-docs/                 # NSE cleaning prompts
+-- embeddings_script/                           # Vector indexing, retrieval, and Q&A
|   +-- index_documents.py                       # Creates embeddings for demo Markdown
|   +-- search.py                                # Runs a similarity-search example
|   +-- retriever.py                             # Interactive retrieval-augmented Q&A
|   +-- chroma_db/                               # Persistent Chroma collection
+-- PIPELINE.md
+-- README.md
```

## Documentation

- [Pipeline overview](PIPELINE.md) records the current preparation flow and
  outputs, including the embedding and retrieval stage.
- [Data preparation guide](datapreparation/data_preparation_readme.md) gives
  the detailed paths, scripts, prompts, and commands.

## Key Scripts

Run commands from the repository root with the project virtual environment.

```powershell
.\venv\Scripts\python.exe datapreparation\run-whole-doc-prompt-on-all-docs.py
.\venv\Scripts\python.exe datapreparation\run-section-prompt-on-all-docs.py
```

The first command cleans eligible NSE documents with 10 pages or fewer. The
second command cleans all grouped sections from longer NSE documents. See the
data-preparation guide for sectioning, grouping, single-file, and single-folder
commands.

## Embeddings and Retrieval

`embeddings_script` provides the current prototype for searching the cleaned
demo documents and answering questions from the retrieved context. It uses
OpenAI's `text-embedding-3-small` model and a persistent Chroma collection
named `finance_documents`. Each Markdown file is currently stored as one
document vector; the prototype does not chunk files before embedding.

Create a `.env` file at the repository root with an OpenAI API key:

```text
OPENAI_API_KEY=your_api_key
```

The scripts require the `openai`, `chromadb`, `python-dotenv`, and `tqdm`
Python packages. Run them from `embeddings_script` so their relative
`./chroma_db` paths refer to the checked-in vector database:

```powershell
Set-Location embeddings_script

# Set DATA_FOLDER in index_documents.py to the Markdown folder you want to index.
..\venv\Scripts\python.exe index_documents.py

# Inspect the three closest stored documents for the example question.
..\venv\Scripts\python.exe search.py

# Ask questions interactively; type exit to quit.
..\venv\Scripts\python.exe retriever.py
```

`index_documents.py` is presently configured to index the ten files in
`data/demo-bot-output` after its `DATA_FOLDER` value is updated to the local
repository path. It can also read `COLLECTION_NAME` and `CHROMA_DB_PATH` from
the environment. `retriever.py` retrieves the three nearest documents and uses
`gpt-4o-mini` to answer only from that retrieved context.
