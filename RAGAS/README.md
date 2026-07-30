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
- `reference_answers_template.csv`: the manually filled expected answers.
- `run_ragas_evaluation.py`: evaluates saved answers and contexts with RAGAS.
- `no_reranking_ragas_results.csv`: row-level RAGAS scores, created by the evaluator.
- `no_reranking_ragas_summary.md`: average scores and lowest-scoring questions.

## Run locally

From the project root, activate the existing environment and install all app
dependencies. `requirements.txt` is intentionally kept at the project root.

```powershell
.\venv\Scripts\Activate.ps1
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create the manual reference-answer sheet:

```powershell
.\venv\Scripts\python.exe RAGAS\generate_reference_template.py
```

Open `RAGAS/reference_answers_template.csv` and fill every
`reference_answer` cell with a concise, human-approved answer. Do not change
the `id` values.

Run a two-question check first:

```powershell
.\venv\Scripts\python.exe RAGAS\run_ragas_evaluation.py --limit 2
```

Then continue until all unanswered rows are evaluated:

```powershell
.\venv\Scripts\python.exe RAGAS\run_ragas_evaluation.py
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
.\venv\Scripts\python.exe RAGAS\run_ragas_evaluation.py `
  --answers-file path\to\future_results.csv `
  --output-file RAGAS\future_ragas_results.csv `
  --summary-file RAGAS\future_ragas_summary.md
```
