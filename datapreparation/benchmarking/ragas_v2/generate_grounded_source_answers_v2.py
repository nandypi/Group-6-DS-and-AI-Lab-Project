"""Generate one source-grounded answer for every v2 benchmark question.

FLOW:
1. Read the 50 v2 benchmark questions.  source_document is already a full
   project-relative filepath (e.g. "data/yfinance/clean-mds/Goldman…md"),
   so no folder-search step is needed.
2. Read the complete source Markdown and insert it into the shared prompt.
3. Ask gpt-4o-mini via the OpenAI Chat Completions API.
4. Save the generated answer after every question.
5. Skip successful rows when the script is run again.
6. Write reference_answers_v2_template.csv when processing is complete,
   with one row per question for human review and editing.

TERM: a source-grounded answer is created from the expected source document
only.  It is a draft for human review before it becomes a RAGAS reference
answer.

ASSUMPTION: every source_document value in the v2 CSV is a project-relative
path and the file exists on disk.  The original (v1) dataset used bare
filenames; v2 always uses full relative paths so no directory search is needed.
"""

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


RAGAS_V2_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROMPT_FILE = PROJECT_ROOT / "RAGAS" / "prompt-to-generate-grounded-answers.md"
INPUT_FILE = PROJECT_ROOT / "data" / "infosys_rag_test_dataset_50_queries_v2.csv"
OUTPUT_FILE = RAGAS_V2_DIR / "grounded_source_answers_v2.csv"
REFERENCE_TEMPLATE_FILE = RAGAS_V2_DIR / "reference_answers_v2_template.csv"
MODEL = "gpt-4o-mini"
MAX_ATTEMPTS = 2

SOURCE_COLUMNS = ["id", "query", "source_category", "source_document"]
RESULT_COLUMNS = [
    "source_document_path",
    "generated_grounded_answer",
    "model",
    "latency_seconds",
    "generation_status",
    "generation_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS
# reference_answers_v2_template.csv uses "question" (not "query") to match
# the column name expected by run_ragas_evaluation_v2.py's reference reader.
REFERENCE_COLUMNS = [
    "id",
    "question",
    "source_category",
    "source_document",
    "reference_answer",
]


# ---------------------------------------------------------------------------
# Lazy OpenAI client
# ---------------------------------------------------------------------------

_openai_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Return the shared OpenAI client, initialising it on first call."""
    global _openai_client
    if _openai_client is None:
        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in .env.")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def read_prompt_template(prompt_file: Path) -> str:
    """Extract the text prompt block from the shared Markdown prompt file.

    Example: the prompt file contains one ```text … ``` block with
    {question} and {text} placeholders; those two placeholders are returned
    as a single template string.
    """
    content = prompt_file.read_text(encoding="utf-8-sig")
    matches = re.findall(r"```text\s*\n(.*?)\n```", content, re.DOTALL)
    if len(matches) != 1:
        raise ValueError("Prompt file must contain exactly one ```text code block.")
    template = matches[0].strip()
    if "{question}" not in template or "{text}" not in template:
        raise ValueError("Prompt template must contain both {question} and {text}.")
    return template


def render_prompt(template: str, question: str, source_text: str) -> str:
    """Insert one question and its complete source Markdown into the template."""
    return template.replace("{question}", question).replace("{text}", source_text)


# ---------------------------------------------------------------------------
# OpenAI answer generation
# ---------------------------------------------------------------------------

def ask_openai(client: OpenAI, prompt: str) -> str:
    """Call gpt-4o-mini and return the model's response text.

    An empty response is retried once because it cannot be used as a
    reference answer or reviewed by a human.
    """
    last_error: str = "No attempts made."
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Use only the source text supplied in the user message. "
                        "Return only the answer with no preamble."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        answer = (response.choices[0].message.content or "").strip()
        if answer:
            return answer
        last_error = f"Attempt {attempt} returned an empty response."
    raise ValueError(last_error)


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def read_csv_rows(file_path: Path) -> list[dict]:
    """Read a UTF-8 CSV into a list of row dictionaries."""
    with file_path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def add_existing_results(rows: list[dict]) -> list[dict]:
    """Copy earlier successful answers into the current row list for resuming.

    Example: after IDs 1–10 finish, a second run skips them and continues at
    ID 11.  This avoids repeating successful API calls.
    """
    if not OUTPUT_FILE.is_file():
        return rows
    existing = {row["id"]: row for row in read_csv_rows(OUTPUT_FILE)}
    for row in rows:
        saved = existing.get(row["id"])
        if saved and saved.get("generation_status") == "Success":
            for col in RESULT_COLUMNS:
                row[col] = saved.get(col, "")
    return rows


def write_rows(rows: list[dict]) -> None:
    """Write all rows to the output CSV after every completed question."""
    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_reference_template(rows: list[dict]) -> None:
    """Write the reference-answer template CSV for human review.

    The generated_grounded_answer is pre-filled into the reference_answer
    column so the reviewer can accept, edit, or replace each answer before
    running the RAGAS evaluation.
    """
    with REFERENCE_TEMPLATE_FILE.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REFERENCE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row.get("id", ""),
                    "question": row.get("query", ""),
                    "source_category": row.get("source_category", ""),
                    "source_document": row.get("source_document", ""),
                    "reference_answer": row.get("generated_grounded_answer", ""),
                }
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def read_arguments() -> argparse.Namespace:
    """Parse the optional --limit argument."""
    parser = argparse.ArgumentParser(
        description="Generate source-grounded answers for the v2 RAGAS benchmark."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of unfinished questions to process (default: all).",
    )
    arguments = parser.parse_args()
    if arguments.limit is not None and arguments.limit < 1:
        parser.error("--limit must be at least 1.")
    return arguments


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Generate source-grounded answers for all unfinished v2 questions."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    arguments = read_arguments()
    prompt_template = read_prompt_template(PROMPT_FILE)
    rows = read_csv_rows(INPUT_FILE)
    if len(rows) != 50:
        raise ValueError(f"Expected 50 benchmark questions, found {len(rows)}.")
    if len({row.get("id", "") for row in rows}) != len(rows):
        raise ValueError("Benchmark question CSV contains duplicate IDs.")

    rows = add_existing_results(rows)
    unfinished = [row for row in rows if row.get("generation_status") != "Success"]
    if arguments.limit is not None:
        unfinished = unfinished[: arguments.limit]

    if not unfinished:
        print("No unfinished questions.")
        write_reference_template(rows)
        print(f"Template written to {REFERENCE_TEMPLATE_FILE.relative_to(PROJECT_ROOT)}")
        return 0

    client = get_client()
    failures = 0
    for number, row in enumerate(unfinished, start=1):
        print(f"[{number}/{len(unfinished)}] ID {row['id']}: {row['query']}")
        request_start = time.perf_counter()
        try:
            source_path = PROJECT_ROOT / row["source_document"]
            if not source_path.is_file():
                raise FileNotFoundError(
                    f"Source document not found: {row['source_document']}"
                )
            source_text = source_path.read_text(encoding="utf-8", errors="replace")
            prompt = render_prompt(prompt_template, row["query"], source_text)
            answer = ask_openai(client, prompt)
            row["source_document_path"] = row["source_document"]
            row["generated_grounded_answer"] = answer
            row["model"] = MODEL
            row["latency_seconds"] = f"{time.perf_counter() - request_start:.3f}"
            row["generation_status"] = "Success"
            row["generation_error"] = ""
            print("  Saved grounded answer.")
        except Exception as error:
            row["latency_seconds"] = f"{time.perf_counter() - request_start:.3f}"
            row["generation_status"] = "Error"
            row["generation_error"] = str(error)
            failures += 1
            print(f"  ERROR: {error}", file=sys.stderr)
        write_rows(rows)

    write_reference_template(rows)
    print(f"\nCompleted : {len(unfinished) - failures}")
    print(f"Failed    : {failures}")
    print(f"Output    : {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Template  : {REFERENCE_TEMPLATE_FILE.relative_to(PROJECT_ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
