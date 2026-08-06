# Milestone 5 Work Done - Shubham

## 2026-08-03 - Updated Long NSE Section Token Counts

Task: for the `docs > 10 pages` section-aware chunks, replace rough estimated
token counts with actual tokenizer counts before creating smaller chunks.

What changed:

- Added `datapreparation/sectioner/update_section_token_counts.py`.
- Renamed the section token field from the previous estimated-token name to
  `actual_tokens` in the sectioner scripts and section JSON manifests.
- Added `count_actual_tokens` in `datapreparation/sectioner/tokens.py` so stored
  token counts use the embedding-model tokenizer.
- Ran the script on:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/sections`.
- Used the `text-embedding-3-small` tokenizer through `tiktoken`, matching the
  embedding pipeline tokenizer.
- Replaced the previous estimated token field with `actual_tokens`, using the actual token count
  of that section's `text`.

ASSUMPTION: token size means the token count of the section `text`, not the full
JSON metadata around that text.

Run summary:

- JSON files updated: 28
- Sections updated: 1,376
- Token values changed: 1,376
- Smallest actual section token count: 27
- Largest actual section token count: 7,909

Verification:

- `python -m py_compile datapreparation/sectioner/update_section_token_counts.py`
  passed.
- `python -m py_compile` passed for the touched sectioner scripts.
- `python datapreparation/sectioner/update_section_token_counts.py` completed
  successfully.
- `rg` found no remaining old token-field references in Python, Markdown, or
  JSON files.

## 2026-08-03 - Generated Smaller NSE Long-Document Pre-KE Chunks

Task: create smaller pre-knowledge-extraction chunks for NSE filings longer
than 10 pages, using the existing section manifests as the source of truth.

What changed:

- Updated `datapreparation/sectioner/concatenate_sections.py` defaults:
  `SOFT_MIN = 1500`, `TOKEN_TARGET = 2500`, and `HARD_MAX = 3000`.
- Kept token counting on actual `text-embedding-3-small` tokens through
  `tiktoken`.
- Split manifest sections above the hard cap by Markdown blocks first, then
  lines, then words.
- Added a neighbor-merge post-pass so sub-1500 leftovers merge into an adjacent
  group whenever the merged file stays under 3000 actual tokens.
- Wrote the new pre-KE files to:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/sectioned_files_1500_2500`.
- Added optional `--input-dir` and `--output-dir` arguments to
  `datapreparation/run_prompts/run-section-prompt-on-all-docs.py` so the section
  KE runner can target `sectioned_files_1500_2500` and
  `cleaned_section_files_1500_2500` without changing the old defaults.

Run summary:

- Source manifest files processed: 28
- Source manifest sections: 1,376
- Working sections after oversized-section splits: 1,896
- Smaller grouped Markdown files written: 1,706
- Average generated file size: 2,194 actual tokens
- Smallest generated file: 510 actual tokens
- Largest generated file: 2,998 actual tokens
- Files in preferred 1,500-2,500 range: 961
- Boundary-preserving files in 2,501-3,000 range: 540
- Files below 1,500: 205

Verification:

- `python -m py_compile datapreparation/sectioner/concatenate_sections.py datapreparation/run_prompts/run-section-prompt-on-all-docs.py`
  passed.
- `python -m datapreparation.sectioner.concatenate_sections --manifests data\nse_files_final\knowledge_extraction\greater_than_10_pages\sections --output data\nse_files_final\knowledge_extraction\greater_than_10_pages\sectioned_files_1500_2500`
  completed successfully.
- Direct tokenizer verification over all generated Markdown files found:
  - Files above 3,000 actual tokens: 0
  - Missing required metadata fields: 0
  - `actual_tokens` metadata mismatches: 0
  - Below-1,500 chunks mergeable with previous neighbor by file-token sum: 0
  - Below-1,500 chunks mergeable with next neighbor by file-token sum: 0

ASSUMPTION: remaining chunks below 1,500 tokens are unavoidable isolated
remainders under the 3,000-token hard cap because neither adjacent file can be
merged with them without exceeding the cap.

Next step:

- Run section KE on the new input/output pair when Codex SDK authentication and
  runtime budget are available:
  `python datapreparation/run_prompts/run-section-prompt-on-all-docs.py --input-dir data\nse_files_final\knowledge_extraction\greater_than_10_pages\sectioned_files_1500_2500 --output-dir data\nse_files_final\knowledge_extraction\greater_than_10_pages\cleaned_section_files_1500_2500`

## 2026-08-03 - Prepared Section KE Runner for Prompt v2

Task: prepare the section knowledge-extraction runner to process the newly
grouped 1,500-2,500 token NSE sections with the new v2 prompt.

What changed:

- Added `prompts/KE-prompts-for-nse-docs/KE-section-prompt-v2.md`.
- Tightened `KE-section-prompt-v2.md` by adding a placeholder-only output
  example that shows the required shape:
  original YAML metadata block, generated YAML metadata block, then cleaned
  Markdown content.
- The prompt example uses only placeholder values and explicitly says not to
  copy placeholder text into the output.
- Updated `datapreparation/run_prompts/run-section-prompt-on-all-docs.py` to
  load `KE-section-prompt-v2.md`.
- Set the current Codex model to `gpt-5.6-luna`.
- Set reasoning effort to `medium`.
- Resolved CLI input and output directories before writing saved-path messages,
  so relative `--input-dir` and `--output-dir` values work cleanly.
- Kept the runner resumable: valid existing outputs are skipped.
- Kept the old default input and output folders, while supporting explicit
  `--input-dir` and `--output-dir` arguments for the smaller grouped sections.

Prompt v1 to v2 changes:

- Changed the role from a general document editor to an editor preparing noisy
  Markdown for a long-term equity-investor knowledge base.
- Changed the cleaning goal from preserving all broadly substantive information
  to preserving information useful for investor retrieval, including business,
  financial, operating, strategy, risk, governance, ESG, corporate-action, and
  table content.
- Added clearer rules for compressing generic boilerplate, promotional text,
  exchange filing wrappers, and mixed paragraphs that contain both useful facts
  and low-value language.
- Added stronger guardrails against investment advice, valuation opinions,
  outside inference, reconstructed context, and unsupported conclusions.
- Expanded metadata guidance so `topics` and `sample_queries` scale with the
  richness of the section instead of using a fixed small range.
- Aligned the metadata field names with the runner validation contract:
  `section_title`, `section_description`, `topics`, and `sample_queries`.
- Removed ambiguous v1 wording that said the response should begin directly
  with the title even though the runner requires the original YAML block first.
- Added the placeholder-only output example to make the two-YAML-block output
  contract explicit for the model.

Why v2 is better:

- It is more aligned with the final retrieval use case: long-term investor Q&A,
  not generic document cleanup.
- It should reduce noisy chunks by removing or compressing filing mechanics,
  promotional language, boilerplate, and conversion artifacts more deliberately.
- It should preserve high-value facts more reliably because the prompt names the
  exact investor-useful categories to keep, especially numbers, tables, periods,
  risks, governance, and corporate actions.
- It should produce better retrieval metadata because topics and sample queries
  are proportional to section density and must be directly supported by the
  cleaned section.
- It should be easier for the runner to validate because the output structure is
  explicit, example-backed, and consistent with the two-YAML-block contract.

Verification:

- `python -m py_compile datapreparation\sectioner\concatenate_sections.py datapreparation\sectioner\models.py datapreparation\sectioner\splitter.py datapreparation\sectioner\tokens.py datapreparation\sectioner\writer.py datapreparation\sectioner\update_section_token_counts.py datapreparation\run_prompts\run-section-prompt-on-all-docs.py`
  passed.
- One-file smoke test on
  `sectioned_files_1500_2500\Infosys_01072025210240_Form20F_July012025_1__1_\group_001.md`
  passed with `gpt-5.6-luna` and `medium` reasoning after the prompt example
  was added.
- The smoke-test output preserved the original YAML block, added the generated
  YAML block, and saved successfully.

Commit summary:

- `7443629 Use actual tokens for NSE section grouping`
- `5a04ccc Add NSE section prompt v2 runner flow`

Next step:

- Run section KE with prompt v2 on the smaller grouped files:
  `python datapreparation/run_prompts/run-section-prompt-on-all-docs.py --input-dir data\nse_files_final\knowledge_extraction\greater_than_10_pages\sectioned_files_1500_2500 --output-dir data\nse_files_final\knowledge_extraction\greater_than_10_pages\cleaned_section_files_1500_2500`

## 2026-08-04 - NSE Long-Document Section KE Run State

Task: document the current state of sectioning and cleaning for NSE documents
longer than 10 pages.

What is complete:

- Section-aware chunking for NSE `docs > 10 pages` is complete.
- Grouped pre-KE input folder:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/sectioned_files_1500_2500`.
- Grouped pre-KE Markdown files present: 1,706
- Document folders present under grouped pre-KE input: 28
- Cleaned output folder:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500`.
- Cleaned document folders present: 28
- Cleaned Markdown files present: 1,699

Cleaning status:

- Current cleaned coverage: 1,699 of 1,706 grouped NSE section files.
- Remaining grouped files without matching cleaned output:
  - `Infosys_18112025182523_SE_letter_LoF_18112025\group_003.md`
  - `Infosys_22102025144043_SE_Draft_LOA_22102025\group_031.md`
  - `Infosys_29052026202126_Infosys_Integrated_Annual_Report_2025-26\group_115.md`
  - `Infosys_30062026163341_SE_Infosys_45th_AGM_transcript\group_009.md`
  - `INFY_30052026200807_SE_Integrated_Annual_Report_2025-26\group_096.md`
  - `INFY_30052026200807_SE_Integrated_Annual_Report_2025-26\group_113.md`
  - `INFY_30052026200807_SE_Integrated_Annual_Report_2025-26\group_117.md`

ASSUMPTION: because the runner is resumable, rerunning the same NSE command will
skip valid cleaned outputs and process only missing or invalid cleaned files.

Resume command:

- `python datapreparation\run_prompts\run-section-prompt-on-all-docs.py --input-dir data\nse_files_final\knowledge_extraction\greater_than_10_pages\sectioned_files_1500_2500 --output-dir data\nse_files_final\knowledge_extraction\greater_than_10_pages\cleaned_section_files_1500_2500`

## 2026-08-04 - Sectioned and Prepared Infosys IR Docs for Section KE

Task: run a similar section-aware chunking and cleaning flow for the direct
Markdown files in `data/infosys_earning_calls_press_conf_fact_sheets_results`.

What changed:

- Added `--direct-only` to `datapreparation/sectioner/cli.py` so the sectioner
  can process only Markdown files directly inside a selected input folder.
- Used `--direct-only` for the Infosys IR folder to avoid reprocessing the
  nested `infosys_ir_earning_calls_clean_markdowns` folder.
- Generated section manifests, reports, raw section files, and grouped pre-KE
  files for the Infosys IR documents.
- Wrote the final grouped pre-KE files to:
  `data/infosys_earning_calls_press_conf_fact_sheets_results/sectioned_files_1500_2500`.
- Added `prompts/KE-prompts-for-infosys-docs/KE-section-prompt-v1.md`.
- Based the Infosys prompt on the NSE section prompt v2 output contract:
  original YAML block, generated YAML block, then cleaned Markdown.
- Customized the Infosys prompt for earnings calls, press conferences, fact
  sheets, quarterly results, press releases, participant/speaker artifacts,
  safe-harbor blocks, awards and recognitions, and financial tables.
- Tightened the Infosys prompt to preserve investor-useful tables and add
  substantive table summaries describing periods, units, row groups, and
  comparison dimensions.
- Tightened `sample_queries` guidance so sections with tables include
  table-oriented queries for retrieval, such as period comparisons, segment mix,
  geography mix, margins, cash flow, balance sheet lines, client metrics,
  headcount, utilization, attrition, deal TCV, and guidance ranges.
- Added prompt guidance to repair obvious text-encoding artifacts when the
  intended character is clear.
- Updated `datapreparation/run_prompts/run-section-prompt-on-all-docs.py` to
  choose the prompt from `--input-dir`:
  - paths containing `nse_files_final` use the NSE section prompt v2
  - paths containing `infosys_earning_calls` use the Infosys section prompt v1

Sectioning run summary:

- Direct source Markdown files processed: 16
- Section manifest files written: 16
- Grouped Markdown files written: 58
- Document folders written under `sectioned_files_1500_2500`: 16
- Largest grouped file: 2,966 actual tokens
- Files above 3,000 actual tokens: 0
- Files missing required grouped-file metadata: 0
- Below-1,500 chunks mergeable with a neighbor under 3,000 tokens: 0

Cleaning run state:

- Cleaned output folder:
  `data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500`.
- Current cleaned Markdown files present: 6
- Current cleaned document folders present: 1
- The runner remains resumable, so reruns skip valid cleaned Markdown outputs
  and continue processing the remaining Infosys grouped sections.

Verification:

- `python -m py_compile datapreparation\sectioner\cli.py datapreparation\sectioner\concatenate_sections.py`
  passed after the sectioning CLI change.
- Infosys sectioning completed successfully with `--direct-only`.
- Infosys grouping completed successfully and wrote 58 grouped files.
- Token and metadata validation over `sectioned_files_1500_2500` found no
  chunk above 3,000 actual tokens and no missing required metadata fields.
- One-file smoke test on
  `data\infosys_earning_calls_press_conf_fact_sheets_results\sectioned_files_1500_2500\FY26-Q1-ifrs-inr-press-release\group_002.md`
  succeeded with `gpt-5.6-luna` and `medium` reasoning.
- The smoke-test output preserved the original YAML block, added generated YAML
  metadata, removed low-value press-release/contact noise, preserved financial
  tables, and added table summaries plus table-aware sample queries.
- `python -m py_compile datapreparation\run_prompts\run-section-prompt-on-all-docs.py`
  passed after prompt selection was added.

Command for Infosys section KE:

- `python datapreparation\run_prompts\run-section-prompt-on-all-docs.py --input-dir data\infosys_earning_calls_press_conf_fact_sheets_results\sectioned_files_1500_2500 --output-dir data\infosys_earning_calls_press_conf_fact_sheets_results\cleaned_section_files_1500_2500`

## 2026-08-04 - Regenerated Embeddings for Updated Corpus

Task: recreate embeddings from scratch after switching to the new cleaned
section chunk sources for NSE long documents and Infosys IR documents.

What changed:

- Updated `embeddings_script/index_documents.py` to embed from the current
  cleaned section folders:
  - `data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500`
  - `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500`
- Updated `embeddings_script/token_counter.py` to use the same source folders
  as the indexer.
- Added a from-scratch embedding rebuild flow to
  `embeddings_script/rag_pipeline_README.md`.
- Regenerated `embeddings_script/token_counts.json` for the updated corpus.

Embedding rebuild summary:

- Deleted the old local Chroma database at `embeddings_script/chroma_db`.
- Rebuilt the `finance_file_embeddings` collection from scratch.
- Total Markdown files embedded: 1,877
- Final Chroma collection count: 1,877
- Embedding model: `text-embedding-3-small`
- One source file exceeded the embedding token limit and was truncated by the
  existing indexer logic:
  `data/trendlyne/clean-mds/INFY-StockReport-20260709-2007.md`
  at 10,673 tokens.

Verification:

- `python -m py_compile embeddings_script\index_documents.py embeddings_script\token_counter.py`
  passed.
- `python embeddings_script\token_counter.py` completed and reported 1,877
  source Markdown files.
- `.\venv\Scripts\python.exe embeddings_script\index_documents.py` completed
  successfully after network access was allowed.
- A retrieval smoke test with `embeddings_script/search.py` succeeded and
  returned relevant AI-risk sections from the rebuilt Chroma collection.

Commit:

- `19d0602 Update embeddings for sectioned corpus`

## 2026-08-05 - Compared Milestone 4 and Milestone 5 Retrieval Recall

Task: compare the earlier Chroma-only benchmark with the new recall-only
benchmark after replacing long NSE and Infosys IR source documents with
sectioned and cleaned chunks.

Compared files:

- Earlier results:
  `data/csv_files_from_milestone4/infosys_rag_test_dataset_50_queries_without_reranking_results.csv`
- New results:
  `data/csv_files_from_milestone5/infosys_rag_test_dataset_50_queries_recall_results.csv`

Both files contain the same 50 test questions and use top-10 Chroma retrieval
without answer-generation evaluation. The new run also did not use the BGE
reranker or an answer LLM. The new benchmark adds Recall@9.

Overall comparison:

| Metric | Milestone 4 | Milestone 5 | Change |
|---|---:|---:|---:|
| Recall@3 | 20/50 (40%) | 17/50 (34%) | -3 questions, -6 percentage points |
| Recall@5 | 25/50 (50%) | 19/50 (38%) | -6 questions, -12 percentage points |
| Recall@7 | 27/50 (54%) | 20/50 (40%) | -7 questions, -14 percentage points |
| Recall@9 | Not available | 20/50 (40%) | New metric |

Category-level comparison:

| Source category | Questions | Recall@3 | Recall@5 | Recall@7 |
|---|---:|---:|---:|---:|
| NSE <=10 | 10 | 9 -> 9 | 9 -> 9 | 9 -> 9 |
| NSE >10 | 30 | 9 -> 5 | 12 -> 6 | 14 -> 7 |
| IR | 5 | 0 -> 1 | 1 -> 2 | 1 -> 2 |
| Trendlyne | 4 | 1 -> 1 | 2 -> 1 | 2 -> 1 |
| Yahoo Finance | 1 | 1 -> 1 | 1 -> 1 | 1 -> 1 |

The largest decrease is in the NSE >10 category, which is the category whose
retrieval representation changed most substantially: one large source file
was replaced by multiple cleaned section chunks. The IR category improved at
all three comparable cutoffs, although it contains only five questions.

Interpretation and assumptions:

- This is an observed retrieval comparison, not proof that the new cleaning
  pipeline is intrinsically worse. The indexed corpus, document boundaries,
  metadata, and expected source paths changed between runs.
- The earlier CSV stored source basenames. The new CSV uses exact full paths
  for re-sectioned NSE and IR chunks and basenames for unchanged categories.
- For re-sectioned documents, a question is counted as recalled only when the
  exact expected current chunk appears in the requested top-k results.
- Recall measures whether the expected source was retrieved; it does not judge
  whether the retrieved content can fully answer the question.

Verification:

- Both CSV files contained 50 rows.
- All 50 new benchmark rows completed successfully.
- New Recall@3, @5, @7, and @9 values were populated for every row.
- No answer-model calls or reranker calls were made during the new run.

## 2026-08-05 - 35-Candidate BGE Reranking Recall Benchmark

Task: measure whether BGE reranking improves retrieval recall when Chroma first
returns 35 candidates for each of the 50 test questions.

What changed:

- Added `datapreparation/benchmarking/run_reranking_35_candidates_recall_benchmark.py`.
- The benchmark uses the same `BAAI/bge-reranker-v2-m3` model as the interactive
  RAG pipeline.
- Each question is embedded with `text-embedding-3-small`, followed by retrieval
  of exactly 35 Chroma candidates.
- All 35 candidates are reranked in batches for the document body and YAML
  metadata separately.
- The final score uses 80% body relevance and 20% metadata relevance.
- Document bodies are truncated to the existing 8,190-token reranker limit when
  necessary.
- Duplicate filepaths are removed before final ranking.
- Recall is calculated at k = 3, 5, 7, and 9 without calling an answer LLM.
- Exact filepath matching is used for re-sectioned NSE and Infosys IR chunks;
  basename matching remains used for unchanged source categories.
- The runner saves its CSV after every question and supports resumable
  `--start` and `--limit` ranges.

Run and recovery:

- The initial long-running execution was interrupted after terminal output
  handling caused invalid-argument errors for unfinished rows.
- The run was resumed in a detached process with stdout and stderr redirected
  to log files, allowing it to continue without the interactive terminal.
- The resumed run completed all 50 questions successfully with zero final
  pipeline errors.

Final results:

| Metric | Chroma-only Milestone 5 | 35-candidate BGE reranking | Change |
|---|---:|---:|---:|
| Recall@3 | 17/50 (34%) | 20/50 (40%) | +3 questions, +6 percentage points |
| Recall@5 | 19/50 (38%) | 23/50 (46%) | +4 questions, +8 percentage points |
| Recall@7 | 20/50 (40%) | 25/50 (50%) | +5 questions, +10 percentage points |
| Recall@9 | 20/50 (40%) | 28/50 (56%) | +8 questions, +16 percentage points |

Latency summary on the local CPU run:

- Mean BGE reranking latency: 484.472 seconds per question.
- Median BGE reranking latency: 426.035 seconds per question.
- Mean overall latency, including embedding and Chroma retrieval: 486.439
  seconds per question.
- Median overall latency: 427.160 seconds per question.
- The high latency motivated a separate Google Colab notebook to compare the
  same 35-candidate workload on CPU and GPU:
  `datapreparation/benchmarking/colab_gpu_reranking_latency_benchmark.ipynb`.

Output files:

- Results:
  `data/csv_files_from_milestone5/infosys_rag_test_dataset_50_queries_reranking_35_candidates_recall_results.csv`
- Progress log:
  `data/csv_files_from_milestone5/reranking_35_candidates.stdout.log`

Interpretation and assumptions:

- Reranking improved recall at every measured cutoff in this benchmark.
- The comparison is directional because the Chroma-only baseline uses Chroma's
  original ordering, while the reranking run retrieves a larger top-35 pool and
  then changes its ordering with BGE.
- Reranking cannot recover a source that is absent from Chroma's initial 35
  candidates.

Verification:

- `python -m py_compile datapreparation\\benchmarking\\run_reranking_35_candidates_recall_benchmark.py`
  passed.
- The final result CSV contains 50 rows with `pipeline_status=Success`.
- No answer-generation calls were made.
- Recall@3, @5, @7, and @9 are populated for every completed row.

## 2026-08-05 - Compared Current Results with Milestone 4

Task: compare the current Milestone 5 retrieval results with the earlier
benchmarks documented in `Milestones/Milestone4.md`.

Recall comparison:

| Method | Recall@3 | Recall@5 | Recall@7 | Recall@9 |
|---|---:|---:|---:|---:|
| Milestone 4 Chroma-only, top 10 | 40% | 50% | 54% | Not available |
| Milestone 5 Chroma-only, top 10 | 34% | 38% | 40% | 40% |
| Milestone 4 BGE reranking, top 25 | 58% | 64% | 64% | Not available |
| Milestone 5 BGE reranking, top 35 | 40% | 46% | 50% | 56% |

Effect of current reranking:

- Recall@3 increased from 34% to 40%.
- Recall@5 increased from 38% to 46%.
- Recall@7 increased from 40% to 50%.
- Recall@9 increased from 40% to 56%.

Comparison with the earlier Milestone 4 reranking run:

- Recall@3 decreased from 58% to 40%.
- Recall@5 decreased from 64% to 46%.
- Recall@7 decreased from 64% to 50%.
- The current run adds Recall@9 at 56%; Milestone 4 did not record Recall@9.

Latency comparison:

| Reranking run | Candidate pool | Average latency per question |
|---|---:|---:|
| Milestone 4 BGE reranking | Top 25 | 245.342 seconds |
| Milestone 5 BGE reranking | Top 35 | 486.439 seconds |

The current 35-candidate run took approximately 1.98 times longer than the
Milestone 4 reranking run. Its average BGE reranking component alone was
484.472 seconds per question.

Interpretation and comparison limits:

- The current reranker still improves the current sectioned corpus at every
  measured recall cutoff.
- The Milestone 5 corpus contains newly sectioned and cleaned NSE >10-page and
  Infosys IR documents, while Milestone 4 used the earlier corpus and document
  boundaries.
- Milestone 5 retrieves 35 candidates before reranking, compared with 25 in
  Milestone 4, which increases reranking work and latency.
- Milestone 5 uses exact current filepath matching for re-sectioned chunks;
  this is stricter than matching the earlier source-document representation.
- The current recall-only runs do not call the answer LLM, so Chroma-only
  latency is not directly comparable to any Milestone 4 timing that included
  answer generation.
- Therefore, the results show a directional quality and latency change rather
  than a perfectly controlled model comparison.

## 2026-08-06 - YAML Front Matter and Reranking Decision

During a review of the reranking inputs, we found that the cleaned files for
the following two categories contain two YAML front matter blocks:

- NSE documents greater than 10 pages:
  `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500`
- Infosys earnings-call and investor-relations documents:
  `data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500`

The first block contains structural and provenance fields such as
`document_name`, `group_id`, `source_section_count`, `actual_tokens`, and
`source_section_ids`. The second block contains knowledge-extraction metadata:
`section_title`, `section_description`, `topics`, and `sample_queries`.

The current reranker extracts only the first YAML block as metadata. Therefore,
the existing 20% metadata score can unintentionally score the structural block,
which is not useful for semantic relevance. The second block currently remains
inside the body used for the 80% body score.

Decision not to remove the first YAML block:

- It preserves group and source-section provenance for auditing and debugging.
- The current section-cleaning script expects the original YAML block and
  validates that it is preserved.
- Removing or relocating it would require changing the cleaning and parsing
  contracts and regenerating the Chroma embeddings.
- Chroma separately stores the indexed file path and filename, but the YAML
  still provides useful data-lineage information in the Markdown artifacts.
- The block is small, and the current pipeline retrieves 35 candidates before
  reranking, so its embedding effect is considered acceptable for now.

Preferred reranking behavior:

- Use the filepath to identify the two affected categories.
- For paths containing `infosys_earning_calls` or `greater_than_10_pages`,
  attempt to use the second YAML block as semantic metadata.
- For all other paths, keep the existing first-block behavior.
- If the expected second block is absent or malformed, fall back safely to the
  first block or body-only scoring rather than failing the whole query.
- The same parsing decision should be used when removing YAML before body
  scoring and before building the final answer context.

Embedding decision:

The first YAML block is included in the text sent to the embedding model
because the indexing script embeds the complete Markdown file. Initially, the
embeddings were left unchanged because the block is small and the reranker was
the more important source of metadata bias. After the YAML quoting repairs, the
full approved corpus was subsequently re-embedded so Chroma contains the
current Markdown text. The structural block remains in the embedding input;
only its reranking treatment was changed.

## 2026-08-06 - Colab GPU Metadata and Body Weight Sweep

Task: evaluate how the BGE reranking recall changes when the body and semantic
metadata weights are varied on the GPU.

Colab experiment setup:

- Processed all 50 questions from
  `data/infosys_rag_test_dataset_50_queries.csv`.
- Retrieved 35 Chroma candidates for every question.
- Used the rebuilt Chroma collection containing 1,877 embeddings.
- Used the updated filepath-aware YAML parser.
- Used `BAAI/bge-reranker-v2-m3` on a Colab GPU with FP16.
- Used the same candidate body and metadata scores for every weight pair.
- Did not call the answer-generation LLM.
- Calculated Recall@3, Recall@5, Recall@7, and Recall@9.

The requested range from body weight 0.0 through 1.0 at a step of 0.1
produces 11 pairs, including both endpoints. Metadata weight was calculated as
`1 - body_weight`.

Weight-sweep results:

| Body weight | Metadata weight | Recall@3 | Recall@5 | Recall@7 | Recall@9 | Mean recall across cutoffs |
|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 1.0 | 42% | 44% | 50% | 54% | 47.5% |
| 0.1 | 0.9 | 36% | 48% | 48% | 54% | 46.5% |
| 0.2 | 0.8 | 36% | 42% | 50% | 54% | 45.5% |
| 0.3 | 0.7 | 38% | 42% | 48% | 50% | 44.5% |
| 0.4 | 0.6 | 36% | 40% | 42% | 48% | 41.5% |
| 0.5 | 0.5 | 36% | 42% | 42% | 44% | 41.0% |
| 0.6 | 0.4 | 36% | 40% | 42% | 42% | 40.0% |
| 0.7 | 0.3 | 38% | 40% | 40% | 42% | 40.0% |
| 0.8 | 0.2 | 38% | 40% | 40% | 42% | 40.0% |
| 0.9 | 0.1 | 36% | 40% | 40% | 42% | 39.5% |
| 1.0 | 0.0 | 32% | 38% | 40% | 42% | 38.0% |

Best weight by cutoff:

- Recall@3: body `0.0`, metadata `1.0`, at 42% or 21/50 questions.
- Recall@5: body `0.1`, metadata `0.9`, at 48% or 24/50 questions.
- Recall@7: body `0.0` or `0.2`, metadata `1.0` or `0.8`, at 50% or 25/50
  questions.
- Recall@9: body `0.0`, `0.1`, or `0.2`, metadata `1.0`, `0.9`, or `0.8`, at
  54% or 27/50 questions.

Latency behavior:

- Model loading took 29.429 seconds.
- Mean reranking latency was 3.278 seconds per question for every weight pair.
- Median reranking latency was 3.321 seconds per question for every weight
  pair.
- Mean end-to-end latency was 3.695 seconds per question for every weight pair.
- Median end-to-end latency was 3.547 seconds per question for every weight
  pair.

The identical latency values are expected. The notebook computes each body and
metadata BGE score once per question, then reuses those scores while changing
only the lightweight weighted sorting step.

Comparison with the earlier noisy first-YAML benchmark:

| Setup | Recall@3 | Recall@5 | Recall@7 | Recall@9 | Mean recall across cutoffs |
|---|---:|---:|---:|---:|---:|
| Earlier 35-candidate run with noisy first-block metadata and 0.8/0.2 weights | 40% | 46% | 50% | 56% | 48.0% |
| New semantic-metadata run with 0.0/1.0 weights | 42% | 44% | 50% | 54% | 47.5% |
| New semantic-metadata run with 0.1/0.9 weights | 36% | 48% | 48% | 54% | 46.5% |
| New semantic-metadata run with 0.2/0.8 weights | 36% | 42% | 50% | 54% | 45.5% |
| New run with the old 0.8/0.2 weights | 38% | 40% | 40% | 42% | 40.0% |

Interpretation:

- Within the new GPU experiment, metadata-heavy ranking consistently performs
  better than body-heavy ranking.
- Metadata-only ranking is the strongest overall new configuration by average
  recall, although it does not win every individual cutoff.
- The old noisy-metadata benchmark had a slightly higher average recall than
  the best new weight configuration, so the experiment does not prove that
  switching to semantic metadata improves absolute recall.
- The new 0.8/0.2 configuration performed substantially worse than the earlier
  0.8/0.2 run, especially at Recall@7 and Recall@9.
- The first YAML block should not be considered beneficial merely because the
  earlier run had higher recall. It was structural metadata and was not a
  semantically meaningful relevance signal.

Comparison limitations:

- The earlier run used the old Chroma embeddings and the old first-block
  metadata behavior.
- The new run used rebuilt embeddings, the filepath-aware parser, and GPU
  FP16 inference.
- GPU and CPU BGE scores can produce slightly different rankings because of
  numerical precision.
- Source document boundaries and current exact filepath matching differ from
  earlier benchmark representations.
- Recall only checks whether the expected source appears in the requested
  rank. It does not measure answer completeness or answer correctness.
- The generated `sample_queries` metadata may resemble user questions and can
  make metadata-only retrieval especially strong.

Conclusion and next step:

The current `0.8 body / 0.2 metadata` configuration should not be selected from
this sweep. The most promising configurations for further evaluation are
`0.0/1.0`, `0.1/0.9`, and `0.2/0.8`. Before selecting a production weighting,
compare these settings using answer quality and precision in addition to recall.
