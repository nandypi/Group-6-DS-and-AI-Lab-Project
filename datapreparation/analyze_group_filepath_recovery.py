"""Check whether logged group filenames can be mapped using Chroma top-10 results.

Flow: read benchmark rows -> find logged ``group_xxx.md`` basenames -> skip
rows without group files -> embed the question -> retrieve 10 Chroma candidates
without reranking -> compare basenames -> write a recovery findings report.

Run from the repository root with:

    python datapreparation/analyze_group_filepath_recovery.py

ASSUMPTION: the CSV's ``retrieved_documents`` field contains filenames in the
format produced by the reranking benchmark logger.
"""

import csv
import os
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMBEDDINGS_SCRIPT = PROJECT_ROOT / "embeddings_script"
BENCHMARK_FILE = PROJECT_ROOT / "data" / "test_with_reranking.csv"
REPORT_FILE = PROJECT_ROOT / "data" / "group_filepath_recovery_findings.md"
GROUP_PATTERN = re.compile(r"(?:^|[ |])(?P<name>group_\d+\.md)(?: |\(|$)", re.IGNORECASE)

sys.path.insert(0, str(EMBEDDINGS_SCRIPT))
import retriever


def read_rows():
    """Read the completed benchmark rows without changing the CSV."""
    with BENCHMARK_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def find_group_names(retrieved_documents):
    """Return unique ``group_xxx.md`` names logged for one question."""
    names = []
    for match in GROUP_PATTERN.finditer(retrieved_documents or ""):
        name = match.group("name")
        if name.lower() not in {item.lower() for item in names}:
            names.append(name)
    return names


def retrieve_top_ten(collection, embedding):
    """Return Chroma's ten candidates for one already-created embedding."""
    return collection.query(
        query_embeddings=[embedding],
        n_results=10,
        include=["metadatas"],
    )


def analyze_row(row, collection, embedding=None):
    """Compare logged group names with the current Chroma top-ten paths."""
    group_names = find_group_names(row.get("retrieved_documents", ""))
    if not group_names:
        return {
            "status": "Skipped: no group filename",
            "group_names": [],
            "matches": {},
        }

    results = retrieve_top_ten(collection, embedding)
    metadata_rows = results.get("metadatas", [[]])[0]
    paths = [metadata.get("filepath", "") for metadata in metadata_rows]
    matches = {}
    for group_name in group_names:
        matches[group_name] = [
            path for path in paths if Path(path).name.lower() == group_name.lower()
        ]

    match_counts = [len(paths_for_name) for paths_for_name in matches.values()]
    if any(count > 1 for count in match_counts):
        status = "Ambiguous: reranking recovery required"
    elif all(count == 1 for count in match_counts):
        status = "Resolved from Chroma top-10"
    else:
        status = "Not found in Chroma top-10"

    return {
        "status": status,
        "group_names": group_names,
        "matches": matches,
    }


def write_report(findings):
    """Write a human-readable record of every question's recovery finding."""
    resolved = sum(
        item["result"]["status"] == "Resolved from Chroma top-10"
        for item in findings
    )
    ambiguous = sum(
        item["result"]["status"].startswith("Ambiguous")
        for item in findings
    )
    not_found = sum(
        item["result"]["status"].startswith("Not found")
        for item in findings
    )
    skipped = sum(
        item["result"]["status"].startswith("Skipped")
        for item in findings
    )

    lines = [
        "# Group filepath recovery findings",
        "",
        "This report compares logged `group_xxx.md` basenames with Chroma's",
        "top-10 filepath metadata. It does not run BGE reranking or the LLM.",
        "",
        f"- Questions checked: {len(findings)}",
        f"- Resolved from Chroma top-10: {resolved}",
        f"- Ambiguous: reranking recovery required: {ambiguous}",
        f"- Not found in Chroma top-10: {not_found}",
        f"- Skipped because no group filename was logged: {skipped}",
        "",
        "## Per-question findings",
        "",
    ]

    for index, item in enumerate(findings, start=1):
        row = item["row"]
        result = item["result"]
        lines.extend([
            f"### {index}. {row['Question']}",
            "",
            f"- Benchmark document: `{row['Document']}`",
            f"- Logged group filename(s): `{', '.join(result['group_names']) or 'none'}`",
            f"- Finding: **{result['status']}**",
        ])
        for group_name, paths in result["matches"].items():
            lines.append(f"- Chroma matches for `{group_name}`:")
            if paths:
                lines.extend([f"  - `{path}`" for path in paths])
            else:
                lines.append("  - None")
        lines.append("")

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def main():
    """Run the top-10 Chroma-only analysis and save the findings report."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.chdir(EMBEDDINGS_SCRIPT)
    rows = read_rows()
    rows_with_groups = [
        row for row in rows if find_group_names(row.get("retrieved_documents", ""))
    ]
    openai_client, collection = retriever.get_clients()
    embedding_response = openai_client.embeddings.create(
        model=retriever.EMBEDDING_MODEL,
        input=[row["Question"] for row in rows_with_groups],
    )
    embeddings = [item.embedding for item in embedding_response.data]
    embeddings_by_question = {
        row["Question"]: embedding
        for row, embedding in zip(rows_with_groups, embeddings)
    }

    findings = []
    for index, row in enumerate(rows, start=1):
        result = analyze_row(
            row,
            collection,
            embeddings_by_question.get(row["Question"]),
        )
        findings.append({"row": row, "result": result})
        print(f"[{index}/{len(rows)}] {result['status']}")

    write_report(findings)
    print(f"Report written to {REPORT_FILE}")


if __name__ == "__main__":
    main()
