"""Compute ranking-quality metrics beyond recall@k, without touching any
existing result CSV.

Recall@k only says whether the expected source is somewhere in the first k
reranked candidates; it is blind to *where* in that window it landed. This
script adds two rank-sensitive metrics computed from data already saved by
the recall benchmarks:

- MRR (Mean Reciprocal Rank): the mean of 1/rank across all questions,
  scored 0 when the expected source is absent from the top 25. A reranker
  that consistently places the right document at rank 1 scores 1.0; one that
  usually needs rank 5 scores 0.2.
- Mean/median rank of the expected source, among only the questions where it
  was found in the top 25 (separate from the miss rate).
- Hit rate@25: the fraction of questions where the expected source appeared
  anywhere in the 25 reranked candidates (the ceiling any reranker can reach
  without changing initial Chroma retrieval).

FLOW: read one or more existing `*_recall_results.csv` files (read-only) ->
parse each row's `reranked_documents_top_25` column into a rank-ordered
filename list -> find the rank of the expected source -> aggregate MRR,
mean/median rank, and hit rate@25 -> write a new comparison report.

This script never modifies its input CSVs; it only reads them and writes a
new report file.
"""

import csv
import re
import statistics
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"
REPORT_FILE = Path(__file__).resolve().parent / "ranking_metrics_report.md"
RANK_ENTRY_PATTERN = re.compile(r"^#(\d+)\s+(.*)\s+\(score=")

# Each entry: (label, results CSV, expected-source column, ranked-documents column).
# The expected-source column differs because the BGE CSV predates the
# old_source_document/current_source_document split of the input dataset.
# The ranked-documents column differs between recall-only CSVs (reranked_documents_top_25)
# and the combined answer+rank CSVs (reranked_documents).
# Each entry: (label, results CSV, expected-source column, ranked-docs column, ranked-filepaths column).
# The filepaths column is used for ground-truth values that are full paths (IDs 11-45),
# avoiding false positives from the 44+ chunks all named group_001.md.
PIPELINES = [
    (
        "BGE reranker (bge-reranker-v2-m3)",
        DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_reranking_top_25_recall_results.csv",
        "source_document",
        "reranked_documents_top_25",
        "reranked_filepaths_top_25",
    ),
    (
        "MiniLM reranker (ms-marco-MiniLM-L-6-v2)",
        DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_minilm_reranking_top_25_recall_results.csv",
        "current_source_document",
        "reranked_documents_top_25",
        "reranked_filepaths_top_25",
    ),
    (
        "MiniLM reranker — baseline (TOP_K=25, top-3 context, gpt-4o-mini)",
        DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_minilm_reranking_with_answers_baseline_results.csv",
        "current_source_document",
        "reranked_documents",
        "reranked_filepaths",
    ),
    (
        "MiniLM reranker — improved (TOP_K=40, top-5 context, gpt-4o-mini)",
        DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_minilm_reranking_with_answers_improved_results.csv",
        "current_source_document",
        "reranked_documents",
        "reranked_filepaths",
    ),
    (
        "Hybrid BM25+dense — MiniLM reranker (TOP_K=40, top-5 context, gpt-4o-mini)",
        DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_hybrid_bm25_results.csv",
        "current_source_document",
        "reranked_documents",
        "reranked_filepaths",
    ),
]


def normalize(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def parse_ranked_entries(reranked_documents_cell, reranked_filepaths_cell):
    """Return (rank, filename, filepath) tuples ordered by rank.

    Filenames come from the documents cell; filepaths from the filepaths cell.
    Both cells are pipe-separated and position-aligned.
    """
    doc_entries = []
    for entry in reranked_documents_cell.split(" | "):
        match = RANK_ENTRY_PATTERN.match(entry.strip())
        if match:
            doc_entries.append((int(match.group(1)), match.group(2)))
    doc_entries.sort(key=lambda item: item[0])

    fps = [fp.strip() for fp in reranked_filepaths_cell.split(" | ")]
    result = []
    for i, (rank, filename) in enumerate(doc_entries):
        filepath = fps[i] if i < len(fps) else ""
        result.append((rank, filename, filepath))
    return result


def rank_of_expected_source(expected_document, ranked_entries):
    """Return the 1-based rank of the expected source, or None if absent.

    Uses suffix matching against the full filepath when the ground truth is a
    path (IDs 11-45). This handles both the full-path format used in
    current_source_document (exact suffix match) and the relative-path format
    used in the older BGE source_document column (partial suffix match against
    the old index paths). Uses basename comparison for plain filenames (IDs
    1-10, 46-50).
    """
    is_path = "/" in expected_document or "\\" in expected_document
    if is_path:
        expected_norm = normalize(expected_document)
        for rank, _, filepath in ranked_entries:
            if normalize(filepath).endswith(expected_norm):
                return rank
    else:
        expected_norm = normalize(Path(expected_document).name)
        for rank, filename, _ in ranked_entries:
            if normalize(filename) == expected_norm:
                return rank
    return None


def compute_metrics_for_pipeline(results_file, expected_column, ranked_documents_column, ranked_filepaths_column):
    """Return per-question ranks and aggregate metrics for one results CSV."""
    with results_file.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))

    per_question = []
    for row in rows:
        if row.get("pipeline_status") != "Success":
            continue
        ranked_entries = parse_ranked_entries(
            row.get(ranked_documents_column, ""),
            row.get(ranked_filepaths_column, ""),
        )
        rank = rank_of_expected_source(row[expected_column], ranked_entries)
        per_question.append({
            "id": row["id"],
            "query": row["query"],
            "rank": rank,
            "reciprocal_rank": (1.0 / rank) if rank else 0.0,
        })

    found_ranks = [item["rank"] for item in per_question if item["rank"] is not None]
    total = len(per_question)
    mrr = sum(item["reciprocal_rank"] for item in per_question) / total if total else 0.0

    return {
        "total_questions": total,
        "hit_rate_at_25": len(found_ranks) / total if total else 0.0,
        "mrr": mrr,
        "mean_rank_when_found": statistics.mean(found_ranks) if found_ranks else None,
        "median_rank_when_found": statistics.median(found_ranks) if found_ranks else None,
        "per_question": per_question,
    }


def format_report(pipeline_results):
    """Build a Markdown comparison report across all evaluated pipelines."""
    lines = [
        "# Ranking-quality metrics (MRR and rank statistics)",
        "",
        "Computed from the already-saved ranked-documents columns in the",
        "result CSVs. No pipeline was rerun and no input CSV was modified.",
        "",
        "- **MRR** (Mean Reciprocal Rank): mean of `1/rank`, scored 0 when the",
        "  expected source is absent from the top 25. Rewards placing the",
        "  correct document as close to rank 1 as possible, unlike recall@k",
        "  which only asks whether it is within the first k.",
        "- **Mean/median rank (when found)**: how deep into the ranking the",
        "  correct document typically sits, among the questions where it was",
        "  retrieved at all.",
        "- **Hit rate@25**: the fraction of questions where the expected source",
        "  appears anywhere in Chroma's original top-25 candidates — the recall",
        "  ceiling reranking alone cannot exceed.",
        "",
        "| Pipeline | Questions | MRR | Mean rank (found) | Median rank (found) | Hit rate@25 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, metrics in pipeline_results:
        mean_rank = f"{metrics['mean_rank_when_found']:.2f}" if metrics["mean_rank_when_found"] is not None else "n/a"
        median_rank = f"{metrics['median_rank_when_found']:.1f}" if metrics["median_rank_when_found"] is not None else "n/a"
        lines.append(
            f"| {label} | {metrics['total_questions']} | {metrics['mrr']:.4f} | "
            f"{mean_rank} | {median_rank} | {metrics['hit_rate_at_25']*100:.0f}% |"
        )

    lines.extend(["", "## Lowest reciprocal-rank questions per pipeline", ""])
    for label, metrics in pipeline_results:
        lines.append(f"### {label}")
        lines.append("")
        worst = sorted(metrics["per_question"], key=lambda item: item["reciprocal_rank"])[:5]
        for item in worst:
            rank_text = item["rank"] if item["rank"] is not None else "not in top 25"
            lines.append(f"- ID {item['id']} (rank {rank_text}): {item['query']}")
        lines.append("")

    return "\n".join(lines) + "\n"


def main():
    pipeline_results = []
    for label, results_file, expected_column, ranked_documents_column, ranked_filepaths_column in PIPELINES:
        if not results_file.exists():
            print(f"Skipping {label}: {results_file.relative_to(PROJECT_ROOT)} not found.")
            continue
        metrics = compute_metrics_for_pipeline(results_file, expected_column, ranked_documents_column, ranked_filepaths_column)
        pipeline_results.append((label, metrics))
        print(
            f"{label}: MRR={metrics['mrr']:.4f} "
            f"mean_rank_found={metrics['mean_rank_when_found']} "
            f"hit_rate@25={metrics['hit_rate_at_25']*100:.0f}%"
        )

    if not pipeline_results:
        raise SystemExit("No pipeline result CSVs were found.")

    REPORT_FILE.write_text(format_report(pipeline_results), encoding="utf-8")
    print(f"Wrote {REPORT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
