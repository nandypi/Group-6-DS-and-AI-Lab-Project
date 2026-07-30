# RAGAS evaluation for the no-reranking pipeline

## Summary

Create a self-contained RAGAS evaluation workspace inside `RAGAS/`. It will evaluate the existing 50 no-reranking answers without rerunning Chroma retrieval, BGE reranking, or `gpt-4o-mini` answer generation.

RAGAS will use `gpt-4o-mini` as the judge and report:

- Faithfulness — whether the generated answer is supported by retrieved context.
- Answer relevancy — whether the answer addresses the question.
- Context precision — whether retrieved context is useful for the known answer.
- Context recall — whether retrieved context contains what is needed for the known answer.

RAGAS supports these RAG metrics and uses OpenAI by default in its documented setup. [RAGAS quick start](https://docs.ragas.io/en/stable/getstarted/quickstart/)

## Implementation changes

- Keep every RAGAS-specific script, dependency file, template, result CSV, report, and README inside `RAGAS/`. Do not modify the existing retrieval or reranking code.
- Add a RAGAS-local dependency file. Pin the RAGAS version only after confirming it installs and runs correctly in the existing Python 3.14 virtual environment; RAGAS declares Python 3.9+ support. [RAGAS on PyPI](https://pypi.org/project/ragas/)
- Add a template-generation script that reads:
  - `data/infosys_rag_test_dataset_50_queries.csv`
  - `data/infosys_rag_test_dataset_50_queries_without_reranking_results.csv`
  
  It will create `RAGAS/reference_answers_template.csv` with:
  `id`, `question`, `source_category`, `source_document`, and blank `reference_answer`.
- Team members fill one concise, human-approved `reference_answer` for each of the 50 questions in that template. The original benchmark CSV remains unchanged.
- Add an evaluation script that:
  - validates that all 50 reference answers are present;
  - reads the stored answer and exact `llm_context_filepaths_top_3`;
  - reopens those source Markdown files and removes YAML front matter, recreating the context that was sent to the answer model;
  - evaluates each row with the four selected RAGAS metrics;
  - writes progress after every row to `RAGAS/no_reranking_ragas_results.csv`;
  - logs a clear per-row error if a stored context file is missing, a reference answer is blank, or RAGAS/OpenAI evaluation fails.
- Produce `RAGAS/no_reranking_ragas_summary.md` containing metric averages, number of successful/failed rows, evaluator model, input file paths, and the lowest-scoring questions for review.
- Make the evaluation runner accept an input-results CSV argument so the same evaluator can later assess a reranking-with-answers benchmark, without changing the evaluator code.

## Documentation and local workflow

Add `RAGAS/README.md` in simple language explaining:

1. Activate the existing virtual environment.
2. Install dependencies from `RAGAS/requirements.txt`.
3. Run the template generator.
4. Fill `reference_answers_template.csv`.
5. Run the evaluator.
6. Read the row-level CSV and summary report.

It will also explain that RAGAS is an LLM-based judge, so scores are useful comparative signals rather than absolute proof, and that evaluation makes additional OpenAI calls.

## Test plan

- Template generation creates exactly 50 rows and preserves IDs/questions/source details.
- Blank or duplicate reference-answer rows stop before any evaluation call.
- Valid stored context paths recreate context with YAML removed.
- Missing source files become clear row-level errors, without losing already-scored rows.
- Mocked RAGAS output is written to the correct CSV columns and included in the summary averages.
- A manual two-question run confirms OpenAI/RAGAS integration, result persistence, and readable output before evaluating all 50.

## Assumptions

- The completed no-reranking result CSV is the first evaluation target.
- Reference answers will be entered manually in the generated CSV template.
- `gpt-4o-mini` is the RAGAS evaluator model; the existing OpenAI API key from `.env` is used but never printed.
- Future reranking answer-quality comparison requires a separate reranking benchmark that generates answers and records its final context paths.

# Actual implementation

- Added RAGAS and its compatible LangChain dependencies to the root `requirements.txt` and installed them in the existing virtual environment.
- Created `RAGAS/generate_reference_template.py` to create a separate 50-row reference-answer template without changing the original benchmark CSV.
- Generated `RAGAS/reference_answers_template.csv` with the question, expected source document, and a blank `reference_answer` column for human-approved answers.
- Created `RAGAS/run_ragas_evaluation.py` to evaluate saved no-reranking answers without running Chroma, BGE reranking, or answer generation again.
- Configured the evaluator to reconstruct the saved top-three source contexts, remove YAML front matter, and score faithfulness, answer relevancy, context precision, and context recall with `gpt-4o-mini`.
- Made the evaluator resumable: it saves results after every row, skips successful rows on a later run, and records row-level errors.
- Added `RAGAS/README.md` with the installation, reference-answer, and evaluation workflow.
- Added local tests for template creation, blank and duplicate reference answers, YAML removal, and summary generation; all five tests passed.
- Saved the grounded-answer prompt in `RAGAS/prompt-to-generate-grounded-answers.md`.
- Created `RAGAS/generate_grounded_source_answers.py` to resolve each expected source document, send its complete Markdown content with the saved prompt to Codex, and save a separate result CSV after every question.
- Ran the new script's dry run across all 50 questions; every expected source path resolved uniquely, including the long-document `group_xxx.md` files.
- Ran the grounded-answer generator with Codex using `gpt-5.5` and medium reasoning effort.
- Created `RAGAS/grounded_source_answers.csv` with 50 successful rows, zero errors, full source paths, generated grounded answers, and per-question latency.
- The generated answers are drafts for review before they are copied into `reference_answers_template.csv` and used for RAGAS scoring.
