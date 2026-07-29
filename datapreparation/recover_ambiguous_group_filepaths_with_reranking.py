"""Recover ambiguous group filepaths by rerunning Chroma retrieval and BGE reranking.

Flow: read ambiguous questions from the Chroma findings report -> batch-embed
their questions -> retrieve 10 candidates from Chroma -> rerank the candidates
with BGE -> replace logged ``group_xxx.md`` entries with the selected full
filepaths -> save the CSV after every question -> write a recovery report.

The answer LLM is never called by this script.

Run from the repository root with:

    python datapreparation/recover_ambiguous_group_filepaths_with_reranking.py

ASSUMPTION: the benchmark CSV and the Chroma findings report were created from
the same index and reranker configuration.
"""

import csv
import os
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMBEDDINGS_SCRIPT = PROJECT_ROOT / "embeddings_script"
BENCHMARK_FILE = PROJECT_ROOT / "data" / "test_with_reranking.csv"
FINDINGS_FILE = PROJECT_ROOT / "data" / "group_filepath_recovery_findings.md"
RECOVERY_REPORT = PROJECT_ROOT / "data" / "reranking_filepath_recovery_findings.md"
GROUP_SCORE_PATTERN = re.compile(r"(group_\d+\.md) \(score=([0-9.]+)\)")

sys.path.insert(0, str(EMBEDDINGS_SCRIPT))
import retriever


def read_ambiguous_questions():
    """Return the questions marked ambiguous in the Chroma-only report."""
    questions = []
    question = None
    for line in FINDINGS_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            question = line.split(". ", maxsplit=1)[1]
        if "Finding: **Ambiguous: reranking recovery required**" in line:
            questions.append(question)
    return questions


def read_rows():
    """Read the current benchmark CSV and retain its original column order."""
    with BENCHMARK_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        return reader.fieldnames, list(reader)


def write_rows(fieldnames, rows):
    """Save progress after each question so a long BGE run can resume safely."""
    with BENCHMARK_FILE.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_logged_group_entries(retrieved_documents):
    """Return the group filename and four-decimal score logged for one row."""
    return GROUP_SCORE_PATTERN.findall(retrieved_documents or "")


def replace_group_entries(row, selected_documents):
    """Replace logged group names with reranked full paths when uniquely matched.

    A filename and its recorded four-decimal BGE score identify the selected
    reranked document. The return value lists any entries that could not be
    matched, so the report records unresolved cases rather than guessing.
    """
    updated_documents = row["retrieved_documents"]
    unresolved = []

    for filename, logged_score in get_logged_group_entries(updated_documents):
        matching_documents = []
        for document in selected_documents:
            same_name = document["filename"] == filename
            same_score = f"{document['final_score']:.4f}" == logged_score
            if same_name and same_score:
                matching_documents.append(document)

        if len(matching_documents) != 1:
            unresolved.append(f"{filename} (score={logged_score})")
            continue

        original_text = f"{filename} (score={logged_score})"
        replacement_text = (
            f"{matching_documents[0]['filepath']} (score={logged_score})"
        )
        updated_documents = updated_documents.replace(original_text, replacement_text, 1)

    row["retrieved_documents"] = updated_documents
    return unresolved


def write_recovery_report(results):
    """Write the reranking recovery outcome for each formerly ambiguous row."""
    recovered = sum(not item["unresolved"] for item in results)
    unresolved = len(results) - recovered
    lines = [
        "# Reranking filepath recovery findings",
        "",
        "This report reran Chroma top-10 retrieval and BGE reranking only.",
        "It did not send any question to the answer LLM.",
        "",
        f"- Ambiguous questions processed: {len(results)}",
        f"- Fully recovered: {recovered}",
        f"- Still unresolved: {unresolved}",
        "",
        "## Per-question findings",
        "",
    ]
    for index, result in enumerate(results, start=1):
        lines.extend([
            f"### {index}. {result['question']}",
            "",
            f"- Finding: **{result['status']}**",
        ])
        if result["unresolved"]:
            lines.append(f"- Unresolved entries: `{', '.join(result['unresolved'])}`")
        lines.append("")
    RECOVERY_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main():
    """Run BGE recovery for the Chroma-ambiguous benchmark rows only."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not retriever.DO_RERANKING:
        raise RuntimeError("DO_RERANKING must be True for filepath recovery.")

    os.chdir(EMBEDDINGS_SCRIPT)
    fieldnames, rows = read_rows()
    ambiguous_questions = read_ambiguous_questions()
    rows_by_question = {row["Question"]: row for row in rows}
    missing_questions = [
        question for question in ambiguous_questions if question not in rows_by_question
    ]
    if missing_questions:
        raise ValueError("Some findings-report questions are missing from the CSV.")

    openai_client, collection = retriever.get_clients()
    embedding_response = openai_client.embeddings.create(
        model=retriever.EMBEDDING_MODEL,
        input=ambiguous_questions,
    )
    embeddings = [item.embedding for item in embedding_response.data]
    reranker = retriever.BGEReranker(
        model_name=retriever.os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
        max_tokens=int(retriever.os.getenv("RERANKER_MAX_TOKENS", "8190")),
    )

    recovery_results = []
    for index, (question, embedding) in enumerate(
        zip(ambiguous_questions, embeddings),
        start=1,
    ):
        row = rows_by_question[question]
        print(f"[{index}/{len(ambiguous_questions)}] Reranking: {question}")
        results = collection.query(
            query_embeddings=[embedding],
            n_results=10,
        )
        selected_documents = retriever.rerank_results(results, question, reranker)
        unresolved = replace_group_entries(row, selected_documents)
        write_rows(fieldnames, rows)

        status = "Recovered with reranking"
        if unresolved:
            status = "Still unresolved after reranking"
        recovery_results.append({
            "question": question,
            "status": status,
            "unresolved": unresolved,
        })
        print(f"  {status}")

    write_recovery_report(recovery_results)
    print(f"Report written to {RECOVERY_REPORT}")


if __name__ == "__main__":
    main()
