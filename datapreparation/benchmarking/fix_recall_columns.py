"""One-time script: recompute correct recall@k columns in all result CSVs.

THE BUG: the original recall evaluation used normalize_filename() which strips
everything to just the basename (e.g. group_001.md -> group001md). But 44
different source documents each have a chunk named group_001.md, so ANY
group_001.md retrieval was counted as a hit regardless of source document.

THE FIX:
- If current_source_document contains '/' (is a full filepath), compare the
  normalized full path against the reranked_filepaths column.
- If current_source_document is a plain filename, compare the normalized
  basename against filenames extracted from the reranked_documents column.

This script reads each CSV, overwrites only the recall columns, and writes
back. No pipeline reruns or LLM calls are needed.
"""

import csv
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"
QA_FILE = DATA_FOLDER / "infosys_rag_test_dataset_50_queries.csv"

RANK_ENTRY_PATTERN = re.compile(r"^#(\d+)\s+(.*)\s+\(score=")


def normalize(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def true_recall_at_k(gt, reranked_docs_cell, reranked_fps_cell, k):
    """Return True when the correct source document is in the top-k results.

    Uses full-path comparison when ground truth is a filepath (IDs 11-45),
    and basename comparison when it is a plain filename (IDs 1-10, 46-50).
    """
    is_path = "/" in gt or "\\" in gt

    if is_path:
        gt_norm = normalize(gt)
        fps = reranked_fps_cell.split(" | ")[:k]
        return any(normalize(fp).endswith(gt_norm) for fp in fps)
    else:
        gt_norm = normalize(Path(gt).name)
        entries = reranked_docs_cell.split(" | ")[:k]
        for entry in entries:
            match = RANK_ENTRY_PATTERN.match(entry.strip())
            if match and normalize(match.group(2)) == gt_norm:
                return True
        return False


def fix_csv(csv_path, gt_by_id, docs_col, fps_col):
    """Recompute recall columns in one results CSV and write back."""
    if not csv_path.exists():
        print(f"Skipping (not found): {csv_path.relative_to(PROJECT_ROOT)}")
        return

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []

    changed = 0
    for row in rows:
        if row.get("pipeline_status") != "Success":
            continue
        gt = gt_by_id.get(row["id"], {}).get("current_source_document", "").strip()
        if not gt:
            continue

        docs_cell = row.get(docs_col, "")
        fps_cell = row.get(fps_col, "")

        for k in [3, 5, 7, 9]:
            col = f"recall@{k}"
            if col not in row:
                continue
            correct = str(true_recall_at_k(gt, docs_cell, fps_cell, k))
            if row[col] != correct:
                row[col] = correct
                changed += 1

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"Fixed {csv_path.relative_to(PROJECT_ROOT)}: {changed} recall cell(s) corrected."
    )


def main():
    with QA_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        gt_by_id = {r["id"]: r for r in csv.DictReader(f)}

    # (csv_path, ranked_docs_column, ranked_filepaths_column)
    TARGETS = [
        (
            DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_minilm_reranking_top_25_recall_results.csv",
            "reranked_documents_top_25",
            "reranked_filepaths_top_25",
        ),
        (
            DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_minilm_reranking_with_answers_baseline_results.csv",
            "reranked_documents",
            "reranked_filepaths",
        ),
        (
            DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_minilm_reranking_with_answers_improved_results.csv",
            "reranked_documents",
            "reranked_filepaths",
        ),
        (
            DATA_FOLDER / "infosys_rag_test_dataset_50_queries_with_hybrid_bm25_results.csv",
            "reranked_documents",
            "reranked_filepaths",
        ),
    ]

    for csv_path, docs_col, fps_col in TARGETS:
        fix_csv(csv_path, gt_by_id, docs_col, fps_col)


if __name__ == "__main__":
    main()
