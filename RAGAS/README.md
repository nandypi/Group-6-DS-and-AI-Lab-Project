# RAGAS evaluation

This folder evaluates answers already produced by the RAG pipeline. It does
not run Chroma retrieval, BGE reranking, or answer generation again.

RAGAS is an LLM-based evaluator. In our case, it uses `gpt-4o-mini` to score four things:

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

## Results obtained for RAGAS

The completed evaluation used the no-reranking pipeline results for 50 Infosys
questions. It evaluated the saved answers against the saved top-3 retrieved
contexts and manually prepared reference answers. The evaluator used
`gpt-4o-mini`, and the pipeline used `text-embedding-3-small`.

All 50 rows completed successfully, with 0 failed rows. RAGAS scores range
from 0 to 1, where a higher score indicates better performance.

| Metric | Average score | What it measures |
| --- | ---: | --- |
| Faithfulness | 0.8101 | Whether the answer is supported by the retrieved context |
| Answer relevancy | 0.6655 | Whether the answer addresses the question |
| Context precision | 0.9117 | Whether the retrieved context is useful and focused for the reference answer |
| Context recall | 0.7769 | Whether the retrieved context contains the facts needed for the reference answer |

The results indicate that the retrieved context was generally precise and that
answers were mostly grounded in the available evidence. Answer relevancy was
the weakest average metric, suggesting that some answers did not address the
question as directly or completely as expected. The lower context recall also
indicates that the top-three context limit can exclude information needed for
some questions.

The five lowest-scoring questions, ranked by their mean score across the four
metrics, were:

| Question ID | Mean score | Question |
| ---: | ---: | --- |
| 20 | 0.0000 | What are the four pillars of Infosys' long-term corporate strategy? |
| 27 | 0.2500 | What percentage of Infosys' revenue comes from exports? |
| 48 | 0.3750 | Which business segments and geographies were the key growth drivers for Infosys in Q4 FY26? |
| 49 | 0.3750 | What are the key risks identified by analysts that could affect Infosys' future performance? |
| 32 | 0.4583 | What acquisitions and strategic investments did Infosys complete during FY2026? |

The complete row-level scores are available in
`no_reranking_ragas_results.csv`. The aggregate values and lowest-scoring
questions are also recorded in `no_reranking_ragas_summary.md`. These results
are specific to the no-reranking benchmark and should not be treated as a
comparison against the BGE-reranking pipeline, since a separate RAGAS run for
that pipeline has not been completed.

## Evaluate a future answer-result CSV

The evaluator accepts an alternate result CSV when a future reranking benchmark
also stores `query`, `llm_answer`, and `llm_context_filepaths_top_3` columns:

```powershell
.\RAGAS\.venv\Scripts\python.exe RAGAS\run_ragas_evaluation.py `
  --answers-file path\to\future_results.csv `
  --output-file RAGAS\future_ragas_results.csv `
  --summary-file RAGAS\future_ragas_summary.md
```
