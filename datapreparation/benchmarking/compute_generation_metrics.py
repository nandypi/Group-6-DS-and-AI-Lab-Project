"""Score saved answers against human reference answers, without RAGAS.

RAGAS uses an LLM judge (gpt-4o-mini) for faithfulness/answer_relevancy/
context_precision/context_recall. This script computes two different,
deterministic, non-LLM-judge metrics instead, using only already-saved
answers:

- ROUGE-L F1: lexical longest-common-subsequence overlap between the saved
  answer and the human reference answer (`rouge-score` package).
- Semantic similarity: cosine similarity between the two texts' embeddings
  from a small local bi-encoder (`sentence-transformers/all-MiniLM-L6-v2`,
  ~22M parameters). This runs entirely offline; no OpenAI calls are made.

FLOW: read an existing pipeline-results CSV (must have `id`, `query`,
`llm_answer`) and the existing human reference-answer CSV (`id`,
`reference_answer`) -> join on `id` -> score each pair -> write a new
per-question CSV and a summary report.

Neither input CSV is modified; only new output files are written.
"""

import csv
import os
import statistics
from pathlib import Path

os.environ.setdefault("USE_TF", "0")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"
BENCHMARK_FOLDER = Path(__file__).resolve().parent
REFERENCES_FILE = PROJECT_ROOT / "RAGAS" / "reference_answers_template.csv"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REPORT_FILE = BENCHMARK_FOLDER / "generation_metrics_report.md"

# Each entry: (label, results CSV, output CSV for this pipeline's per-row scores).
PIPELINES = [
    (
        "No reranking (top-3 Chroma, gpt-4o-mini)",
        DATA_FOLDER / "infosys_rag_test_dataset_50_queries_without_reranking_results.csv",
        BENCHMARK_FOLDER / "generation_metrics_no_reranking.csv",
    ),
    (
        "HyDE, no reranking (top-3 Chroma, gpt-4o-mini)",
        DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_hyde_results.csv",
        BENCHMARK_FOLDER / "generation_metrics_hyde.csv",
    ),
    (
        "MiniLM reranker — baseline (TOP_K=25, top-3 context, gpt-4o-mini)",
        DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_minilm_reranking_with_answers_baseline_results.csv",
        BENCHMARK_FOLDER / "generation_metrics_minilm_baseline.csv",
    ),
    (
        "MiniLM reranker — improved (TOP_K=40, top-5 context, gpt-4o-mini)",
        DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_minilm_reranking_with_answers_improved_results.csv",
        BENCHMARK_FOLDER / "generation_metrics_minilm_improved.csv",
    ),
    (
        "Hybrid BM25+dense — MiniLM reranker (TOP_K=40, top-5 context, gpt-4o-mini)",
        DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_hybrid_bm25_results.csv",
        BENCHMARK_FOLDER / "generation_metrics_hybrid_bm25.csv",
    ),
]


def read_csv_rows(file_path):
    with file_path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def load_reference_answers():
    """Return {id: reference_answer} from the existing human-approved sheet."""
    references = {}
    for row in read_csv_rows(REFERENCES_FILE):
        reference_answer = row.get("reference_answer", "").strip()
        if reference_answer:
            references[row["id"]] = reference_answer
    return references


def join_answers_with_references(results_rows, references):
    """Return rows that have both a saved answer and a reference answer."""
    joined = []
    for row in results_rows:
        if row.get("pipeline_status") != "Success":
            continue
        answer = row.get("llm_answer", "").strip()
        reference = references.get(row["id"])
        if not answer or not reference:
            continue
        joined.append({
            "id": row["id"],
            "query": row["query"],
            "llm_answer": answer,
            "reference_answer": reference,
        })
    return joined


def score_rouge_l(rows):
    """Attach a `rouge_l_f1` score to each row using longest-common-subsequence overlap."""
    from rouge_score import rouge_scorer

    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    for row in rows:
        score = scorer.score(row["reference_answer"], row["llm_answer"])
        row["rouge_l_f1"] = score["rougeL"].fmeasure


def score_semantic_similarity(rows):
    """Attach a `semantic_similarity` score to each row using local embeddings."""
    from sentence_transformers import SentenceTransformer, util

    model = SentenceTransformer(EMBEDDING_MODEL)
    answers = [row["llm_answer"] for row in rows]
    references = [row["reference_answer"] for row in rows]
    answer_embeddings = model.encode(answers, convert_to_tensor=True, normalize_embeddings=True)
    reference_embeddings = model.encode(references, convert_to_tensor=True, normalize_embeddings=True)
    similarities = util.cos_sim(answer_embeddings, reference_embeddings).diagonal()
    for row, similarity in zip(rows, similarities):
        row["semantic_similarity"] = float(similarity)


def write_rows(rows, output_file):
    fieldnames = ["id", "query", "llm_answer", "reference_answer", "rouge_l_f1", "semantic_similarity"]
    with output_file.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows):
    return {
        "questions": len(rows),
        "rouge_l_f1_mean": statistics.mean(row["rouge_l_f1"] for row in rows) if rows else None,
        "semantic_similarity_mean": statistics.mean(row["semantic_similarity"] for row in rows) if rows else None,
    }


def format_report(pipeline_summaries):
    lines = [
        "# Generation-quality metrics (ROUGE-L and semantic similarity, no RAGAS)",
        "",
        f"Reference answers: `{REFERENCES_FILE.relative_to(PROJECT_ROOT)}` (human-approved,",
        "reused as plain ground-truth data; the RAGAS library/methods were not used).",
        f"Semantic similarity uses the local bi-encoder `{EMBEDDING_MODEL}` — no OpenAI",
        "calls are made for scoring.",
        "",
        "| Pipeline | Questions scored | ROUGE-L F1 (mean) | Semantic similarity (mean) |",
        "|---|---:|---:|---:|",
    ]
    for label, summary, _ in pipeline_summaries:
        rouge = f"{summary['rouge_l_f1_mean']:.4f}" if summary["rouge_l_f1_mean"] is not None else "n/a"
        sim = f"{summary['semantic_similarity_mean']:.4f}" if summary["semantic_similarity_mean"] is not None else "n/a"
        lines.append(f"| {label} | {summary['questions']} | {rouge} | {sim} |")

    lines.extend(["", "## Lowest semantic-similarity questions per pipeline", ""])
    for label, summary, rows in pipeline_summaries:
        lines.append(f"### {label}")
        lines.append("")
        worst = sorted(rows, key=lambda row: row["semantic_similarity"])[:5]
        for row in worst:
            lines.append(
                f"- ID {row['id']} (semantic_similarity={row['semantic_similarity']:.4f}, "
                f"rouge_l_f1={row['rouge_l_f1']:.4f}): {row['query']}"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def main():
    references = load_reference_answers()
    pipeline_summaries = []

    for label, results_file, output_file in PIPELINES:
        if not results_file.exists():
            print(f"Skipping {label}: {results_file.relative_to(PROJECT_ROOT)} not found.")
            continue

        rows = join_answers_with_references(read_csv_rows(results_file), references)
        if not rows:
            print(f"Skipping {label}: no rows with both a saved answer and a reference answer.")
            continue

        score_rouge_l(rows)
        score_semantic_similarity(rows)
        write_rows(rows, output_file)

        summary = summarize(rows)
        pipeline_summaries.append((label, summary, rows))
        print(
            f"{label}: rouge_l_f1={summary['rouge_l_f1_mean']:.4f} "
            f"semantic_similarity={summary['semantic_similarity_mean']:.4f} "
            f"({summary['questions']} questions)"
        )
        print(f"  Wrote {output_file.relative_to(PROJECT_ROOT)}")

    if not pipeline_summaries:
        raise SystemExit("No pipeline had both saved answers and reference answers.")

    REPORT_FILE.write_text(format_report(pipeline_summaries), encoding="utf-8")
    print(f"Wrote {REPORT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
