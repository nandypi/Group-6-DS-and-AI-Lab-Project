# RAGAS evaluation

This folder evaluates answers already produced by the RAG pipeline. It does
not run Chroma retrieval, BGE reranking, or answer generation again.

RAGAS is an LLM-based evaluator. It uses `gpt-4o-mini` to score four things:

- `faithfulness`: Is the saved answer supported by its retrieved context?
- `answer_relevancy`: Does the saved answer address the question?
- `context_precision`: Is the retrieved context useful for the reference answer?
- `context_recall`: Does the retrieved context contain the facts in the reference answer?

Scores are useful for comparing pipeline versions. They are not a replacement
for human review.

## Files

- `generate_reference_template.py`: creates the editable reference-answer CSV.
- `generate_grounded_source_answers.py`: creates source-grounded answer drafts with Codex.
- `prompt-to-generate-grounded-answers.md`: the prompt used for those drafts.
- `reference_answers_template.csv`: the manually filled expected answers.
- `run_ragas_evaluation.py`: evaluates saved answers and contexts with RAGAS.
- `no_reranking_ragas_results.csv`: row-level RAGAS scores, created by the evaluator.
- `no_reranking_ragas_summary.md`: average scores and lowest-scoring questions.

## Run locally

From the project root, use the isolated RAGAS environment and install all app
dependencies. `requirements.txt` is intentionally kept at the project root.
The isolated environment uses Python 3.13; RAGAS 0.2.15 is not compatible
with Python 3.14's asynchronous runtime.

```powershell
.\RAGAS\.venv\Scripts\Activate.ps1
.\RAGAS\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Generate grounded reference-answer drafts

This optional step uses the expected source document for each question to make
a draft answer. It uses the existing ChatGPT-authenticated Codex SDK with
`gpt-5.5` and medium reasoning effort. It does not use the OpenAI API key.

Check all source paths without calling Codex:

```powershell
.\RAGAS\.venv\Scripts\python.exe RAGAS\generate_grounded_source_answers.py --dry-run
```

Generate drafts for all 50 questions:

```powershell
.\RAGAS\.venv\Scripts\python.exe RAGAS\generate_grounded_source_answers.py
```

After reviewing the generated answers, copy them into currently blank template
cells. This leaves any non-blank, manually revised reference answer unchanged:

```powershell
.\RAGAS\.venv\Scripts\python.exe RAGAS\copy_grounded_answers_to_reference_template.py
```

The script saves `RAGAS/grounded_source_answers.csv` after every question. It
records the full source path, answer, latency, model settings, and any error.
Review each generated answer before copying it into `reference_answer` in the
reference-answer template. A generated `NOT_FOUND` value should also be
reviewed rather than copied automatically.

Create the manual reference-answer sheet:

```powershell
.\RAGAS\.venv\Scripts\python.exe RAGAS\generate_reference_template.py
```

Open `RAGAS/reference_answers_template.csv` and fill every
`reference_answer` cell with a concise, human-approved answer. Do not change
the `id` values.

Run a two-question check first:

```powershell
.\RAGAS\.venv\Scripts\python.exe RAGAS\run_ragas_evaluation.py --limit 2
```

Then continue until all unanswered rows are evaluated:

```powershell
.\RAGAS\.venv\Scripts\python.exe RAGAS\run_ragas_evaluation.py
```

The evaluator saves after every question. Re-running the same command skips
successful rows and retries unfinished or failed rows.

## Inputs and safeguards

The default evaluation reads:

- `data/infosys_rag_test_dataset_50_queries_without_reranking_results.csv`
- `RAGAS/reference_answers_template.csv`

It rebuilds the exact answer context from each row's saved
`llm_context_filepaths_top_3`, removes YAML front matter, and sends that text
with the saved answer to RAGAS. It requires `OPENAI_API_KEY` in the project
`.env` file, but never prints the key.

Reference answers are required for context precision and context recall. A
blank or duplicate reference-answer row stops before RAGAS makes any OpenAI
call. Missing source files and RAGAS failures are recorded per row, allowing
the remaining questions to continue.

## Evaluate a future answer-result CSV

The evaluator accepts an alternate result CSV when a future reranking benchmark
also stores `query`, `llm_answer`, and `llm_context_filepaths_top_3` columns:

```powershell
.\RAGAS\.venv\Scripts\python.exe RAGAS\run_ragas_evaluation.py `
  --answers-file path\to\future_results.csv `
  --output-file RAGAS\future_ragas_results.csv `
  --summary-file RAGAS\future_ragas_summary.md
```
