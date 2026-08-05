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
