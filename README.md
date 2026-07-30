# Imp MD files for reference (keep adding when u create a new md file for documentation purpose)

Markdown files outside `data/`:

- `PIPELINE.md`
- `README.md`
- `datapreparation/benchmarking/reranking_knowledge.md`
- `datapreparation/benchmarking/results.md`
- `datapreparation/data_preparation_readme.md`
- `embeddings_script/rag_pipeline_README.md`
- `sample-input-output/reranking-tests.md`

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

Approved clean Markdown
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
|   +-- benchmarking/                            # Chroma-only and BGE benchmark runners
|   +-- data_preparation_readme.md
+-- metadata/                                    # Review decisions and metadata
+-- prompts/
|   +-- KE-prompts/                              # Trendlyne and yfinance prompts
|   +-- KE-prompts-for-nse-docs/                 # NSE cleaning prompts
+-- embeddings_script/                           # Vector indexing, retrieval, and Q&A
|   +-- index_documents.py                       # Creates embeddings for approved Markdown
|   +-- token_counter.py                         # Counts tokens before embedding
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

## Current Script Entry Points

Run commands from the repository root with the project virtual environment.

```powershell
Set-Location embeddings_script
..\venv\Scripts\python.exe index_documents.py
..\venv\Scripts\python.exe retriever.py
```

Run the benchmark runners from the repository root instead. The earlier batch
cleaning runners are archived and are not current entry points. See the data
preparation guide for the cleaned-data locations and benchmark commands.

## Embeddings and Retrieval

`embeddings_script` indexes the five approved clean-Markdown folders, searches
the resulting documents, and supports context-grounded Q&A. It uses OpenAI's
`text-embedding-3-small` model and a persistent Chroma collection named
`finance_file_embeddings`. Each Markdown file has one document vector; files
above the model's 8,192-token input limit are automatically shortened to their
first 8,191 tokens before embedding. Chroma metadata records the original token
count, embedded token count, and whether the file was shortened.

Create a `.env` file at the repository root with an OpenAI API key:

```text
OPENAI_API_KEY=your_api_key
```

The scripts require the packages in `requirements.txt`, including `tiktoken`
for token counting and safe truncation. Run them from `embeddings_script` so their relative
`./chroma_db` paths refer to the checked-in vector database:

```powershell
Set-Location embeddings_script

# Save exact token counts for all approved Markdown files.
..\venv\Scripts\python.exe token_counter.py

# Embed all approved Markdown files.
..\venv\Scripts\python.exe index_documents.py

# Inspect the three closest stored documents for the example question.
..\venv\Scripts\python.exe search.py

# Ask questions interactively; type exit to quit.
..\venv\Scripts\python.exe retriever.py
```

`index_documents.py` is configured with these folders: `data/yfinance/clean-mds`,
`data/trendlyne/clean-mds`, the Infosys investor-relations clean-Markdown
folder, the cleaned NSE whole-document folder, and the recursively scanned
cleaned NSE section folder. `token_counter.py` writes the exact counts to
`embeddings_script/token_counts.json`.

## Optional BGE Re-ranking

`retriever.py` supports two selectable retrieval pipelines. Set
`DO_RERANKING` in the repository-root `.env` file before starting the script:

```text
DO_RERANKING=True
```

With `True`, Chroma retrieves 25 candidates by default, the local
`BAAI/bge-reranker-v2-m3` cross-encoder scores each document's YAML metadata
and body separately, and combines the scores as
`0.8 * body_score + 0.2 * metadata_score`. The three highest weighted results
are sent to `gpt-4o-mini`. With `False`, BGE is not loaded; the three closest Chroma
documents are sent directly. In both modes, YAML front matter is removed from
the final answer context.

Set `RERANKING_RETRIEVAL_TOP_K=25` explicitly when recording an experiment;
25 is the default. Chroma stores both a display filename and a complete
filepath, so retrieved `group_xxx.md` section files can be traced back to their
source-document folder.

Each question also prints latency for the embedding call, Chroma retrieval,
the selected branch (BGE reranking or direct selection), context preparation,
the LLM request, and total question latency. This makes it easy to compare
the same questions with `DO_RERANKING=True` and `DO_RERANKING=False`.

Install the dependencies and run the interactive retriever from the
`embeddings_script` directory:

```powershell
Set-Location embeddings_script
..\venv\Scripts\python.exe -m pip install -r ..\requirements.txt
..\venv\Scripts\python.exe retriever.py
```

The first run with reranking downloads the BGE model, so it requires internet
access and additional disk space. Change `DO_RERANKING` to `False` when a
local run should use Chroma retrieval only. `OPENAI_API_KEY` is still required
in both modes for query embeddings and the final answer.

## Benchmarking Retrieval

The 50-question benchmark input is
`data/infosys_rag_test_dataset_50_queries.csv`. It contains the question and
expected source filename. Benchmark runners keep this file unchanged and write
separate result CSVs after every question.

- Chroma-only benchmark:
  `datapreparation/benchmarking/run_without_reranking_benchmark.py`
  retrieves 10 candidates, records Recall@3/5/7, sends the top 3 to
  `gpt-4o-mini`, and writes
  `data/infosys_rag_test_dataset_50_queries_without_reranking_results.csv`.
- Recall-only BGE benchmark:
  `datapreparation/benchmarking/run_reranking_recall_benchmark.py`
  retrieves and reranks 25 candidates, records Recall@3/5/7 and full paths,
  does not call `gpt-4o-mini`, and writes
  `data/infosys_rag_test_dataset_50_queries_with_reranking_top_25_recall_results.csv`.

Run either benchmark from the repository root. Set `DO_RERANKING=False` for
the Chroma-only runner and `DO_RERANKING=True` for the BGE runner. See the
[data preparation guide](datapreparation/data_preparation_readme.md) for the
exact commands and resume options.
