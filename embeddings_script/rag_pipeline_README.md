# RAG Retrieval, Re-ranking, and Source Paths

## Current pipeline

The system indexes cleaned Markdown from five sources: NSE whole documents,
NSE grouped sections, Infosys investor-relations documents, Trendlyne, and
yfinance. Chroma stores one vector per Markdown file with both its filename and
complete relative filepath.

Current embedding source folders:

```text
data/yfinance/clean-mds
data/trendlyne/clean-mds
data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500
data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages
data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500
```

For each question, OpenAI creates a query embedding and Chroma retrieves
candidates. The pipeline mode is controlled by `DO_RERANKING`:

- `False`: use Chroma's closest three documents directly.
- `True`: retrieve 25 candidates, use `BAAI/bge-reranker-v2-m3` to score YAML
  metadata and body independently, combine them with
  `0.8 * body_score + 0.2 * metadata_score`, and select the top three.

Only document bodies are passed to `gpt-4o-mini`; YAML metadata and scores are
not part of the answer prompt. The default reranking candidate count is 25 and
can be recorded explicitly with `RERANKING_RETRIEVAL_TOP_K=25` in `.env`.

For retrieval-quality evaluation, the recall-only benchmark retrieves and
reranks 25 candidates, records Recall@3/5/7 and full paths, and does not call
the answer model. Run it from the repository root with:

```powershell
.\venv\Scripts\python.exe datapreparation\benchmarking\run_reranking_recall_benchmark.py
```

Set `DO_RERANKING=True`. Its results are written to
`data/infosys_rag_test_dataset_50_queries_with_reranking_top_25_recall_results.csv`.

## Why can Chroma have multiple files named group_xx.md?

Yes, Chroma supports this correctly.

During indexing, each document receives a unique ID based on its full relative path:

```text
data/nse_files_final/.../Infosys_01072025210240.../group_035.md
```

Chroma also stores:

- `filename`: only `group_035.md`
- `filepath`: the complete unique source path
- `source_folder`
- other metadata

Therefore, multiple `group_035.md` files from different source documents are treated as separate documents because their full paths and IDs differ.

For example, the repository contains multiple distinct files named `group_035.md`, including ones under:

```text
Infosys_01072025210240_Form20F...
Infosys_14012026160405_BM_Outcome...
Infosys_16102025160458_BM_Outcome...
Infosys_23042026170027_outcome
```

However, the original benchmark CSV logged only `filename`, not the full
`filepath`. Therefore, from `group_035.md` alone, we could not know exactly
which source document was sent to the LLM.

The pipeline itself does know the difference internally and uses `filepath` for deduplication. The benchmark logger now records both:

```text
filename
full filepath
reranking score
```

## Recovering the source path for historic benchmark results

The original 50-question reranking benchmark was completed before full
filepaths were recorded. As a result, the `retrieved_documents` column in
`data/test_with_reranking.csv` contained ambiguous names such as
`group_035.md`.

We resolved this without rerunning the answer LLM for all 50 questions.

1. We inspected each question's logged retrieved filenames.
2. Questions without a `group_xxx.md` filename needed no recovery.
3. For questions with a group filename, we embedded the question and retrieved
   only Chroma's top 10 candidates. BGE reranking and the answer LLM were not
   used in this first pass.
4. If exactly one of those 10 candidates had the logged group filename, we
   replaced the basename in the CSV with that candidate's full `filepath`.
5. If more than one top-10 candidate had the same group filename, the Chroma
   result was ambiguous. We reran Chroma top-10 retrieval plus BGE reranking
   only for those questions, then matched the selected filename and reranking
   score to its exact `filepath`.

### Recovery results

| Result | Questions |
| --- | ---: |
| No group filename logged; no recovery needed | 21 |
| Resolved from Chroma top-10 only | 9 |
| Initially ambiguous; resolved with BGE reranking only | 20 |
| Still unresolved | 0 |

All 29 rows that originally contained a group filename now show the exact
filepath in `data/test_with_reranking.csv`. No answer-model calls were made
while recovering these paths.

### What is now stored in the benchmark CSV

For this historic benchmark run, the recovered full paths were written back
into `retrieved_documents`, replacing only the ambiguous `group_xxx.md`
basenames. The original scores and all answer and latency results were left
unchanged.

For current recall-only benchmark runs,
`datapreparation/benchmarking/run_reranking_recall_benchmark.py` records two
separate fields from the start:

- `reranked_documents_top_25`: reranked filename plus final score for each
  candidate.
- `reranked_filepaths_top_25`: complete indexed source path for each candidate.

This means a current result can be traced to its source document directly. The
historic CSV is also traceable for every row that contained a `group_xxx.md`
filename.

The detailed reports are:

- `data/group_filepath_recovery_findings.md`
- `data/reranking_filepath_recovery_findings.md`

The reusable scripts are:

- `datapreparation/analyze_group_filepath_recovery.py`
- `datapreparation/apply_resolved_group_filepaths.py`
- `datapreparation/recover_ambiguous_group_filepaths_with_reranking.py`

## Recreate embeddings from scratch

Use this when the source corpus changes enough that old Chroma IDs should not
remain in the retrieval collection. This rebuild uses the source folders listed
above.

1. Optional preflight: count files and embedding tokens.

```powershell
.\venv\Scripts\python.exe embeddings_script\token_counter.py
```

2. Delete the old local Chroma database.

```powershell
Remove-Item -Recurse -Force embeddings_script\chroma_db
```

3. Rebuild all embeddings.

```powershell
.\venv\Scripts\python.exe embeddings_script\index_documents.py
```

4. Quick retrieval smoke test.

```powershell
.\venv\Scripts\python.exe embeddings_script\search.py
```

Do not use `--skip-existing` for a from-scratch rebuild. That flag is only for
resuming an interrupted run against an existing Chroma database.
