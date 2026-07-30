"""Generate one source-grounded answer for every RAGAS benchmark question.

FLOW:
1. Read the 50 benchmark questions.
2. Resolve each question's source filename inside its declared source category.
3. Read the complete source Markdown and insert it into the saved prompt.
4. Ask Codex with gpt-5.5 and medium reasoning effort.
5. Save the generated answer immediately in a separate CSV.
6. Skip successful rows when the script is run again.

TERM: a source-grounded answer is an answer created from the expected source
document only. It is a draft for human review before it becomes a RAGAS
reference answer.

ASSUMPTION: every source filename maps to exactly one Markdown file inside
the folder for its declared source category.
ASSUMPTION: this script uses the existing ChatGPT-authenticated Codex SDK,
not the OpenAI API key from .env.
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAGAS_FOLDER = Path(__file__).resolve().parent
INPUT_FILE = PROJECT_ROOT / "data" / "infosys_rag_test_dataset_50_queries.csv"
PROMPT_FILE = RAGAS_FOLDER / "prompt-to-generate-grounded-answers.md"
OUTPUT_FILE = RAGAS_FOLDER / "grounded_source_answers.csv"
MODEL = "gpt-5.5"
MAX_ATTEMPTS = 2
SOURCE_FOLDERS = {
    "NSE <=10": (
        PROJECT_ROOT
        / "data"
        / "nse_files_final"
        / "whole_document_cleaning"
        / "equal_or_less_than_10_pages"
    ),
    "NSE >10": (
        PROJECT_ROOT
        / "data"
        / "nse_files_final"
        / "knowledge_extraction"
        / "greater_than_10_pages"
        / "cleaned_section_files"
    ),
    "IR": (
        PROJECT_ROOT
        / "data"
        / "infosys_earning_calls_press_conf_fact_sheets_results"
        / "infosys_ir_earning_calls_clean_markdowns"
    ),
    "Trendlyne": PROJECT_ROOT / "data" / "trendlyne" / "clean-mds",
    "Yahoo Finance": PROJECT_ROOT / "data" / "yfinance" / "clean-mds",
}
SOURCE_COLUMNS = ["id", "query", "source_category", "source_document"]
RESULT_COLUMNS = [
    "source_document_path",
    "generated_grounded_answer",
    "model",
    "reasoning_effort",
    "latency_seconds",
    "generation_status",
    "generation_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS


def read_csv_rows(file_path):
    """Read benchmark rows from a UTF-8 CSV.

    Example: the standard test set returns 50 question dictionaries. This
    happens before Codex login so bad input files fail without model calls.
    """
    with file_path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def read_prompt_template(prompt_file):
    """Extract the saved prompt's one text code block.

    Example: a Markdown file containing ``{question}`` and ``{text}`` inside
    a ```text block returns just that prompt. The surrounding explanation is
    never sent to Codex.
    """
    prompt_file_text = prompt_file.read_text(encoding="utf-8-sig")
    matches = re.findall(r"```text\s*\n(.*?)\n```", prompt_file_text, re.DOTALL)
    if len(matches) != 1:
        raise ValueError("Prompt file must contain exactly one ```text code block.")

    prompt_template = matches[0].strip()
    if "{question}" not in prompt_template or "{text}" not in prompt_template:
        raise ValueError("Prompt code block must contain both {question} and {text}.")
    return prompt_template


def resolve_source_path(source_category, source_document):
    """Return the one source path matching a benchmark category and filename.

    Example: ``NSE <=10`` and ``report.md`` return the matching cleaned whole
    document. Multiple matches raise an error instead of selecting a possibly
    unrelated file with the same name.
    """
    source_folder = SOURCE_FOLDERS.get(source_category)
    if source_folder is None:
        raise ValueError(f"Unknown source category: {source_category}")
    if not source_folder.is_dir():
        raise FileNotFoundError(f"Source folder does not exist: {source_folder}")

    matches = sorted(source_folder.rglob(source_document))
    if not matches:
        raise FileNotFoundError(
            f"Source document was not found in {source_category}: {source_document}"
        )
    if len(matches) > 1:
        matching_paths = ", ".join(str(path.relative_to(PROJECT_ROOT)) for path in matches)
        raise ValueError(f"Source document is ambiguous: {matching_paths}")
    return matches[0]


def render_prompt(prompt_template, question, source_text):
    """Insert one question and its complete source Markdown into the prompt.

    Example: ``What is revenue?`` and ``Revenue was 10.`` become a complete
    grounded-answer request. Source text is kept whole and is never truncated.
    """
    return prompt_template.replace("{question}", question).replace("{text}", source_text)


def load_codex_sdk():
    """Load the official Codex SDK or explain how to install it.

    Called before the first model request. The repository's existing prompt
    runners use the same SDK and ChatGPT authentication flow.
    """
    try:
        from openai_codex import Codex
    except ImportError as error:
        raise RuntimeError(
            "The official Codex Python SDK is not installed. Run: "
            ".\\venv\\Scripts\\python.exe -m pip install openai-codex"
        ) from error
    return Codex


def ensure_chatgpt_login(codex):
    """Confirm that the Codex SDK uses a ChatGPT account.

    Called once before processing. A signed-out user receives the device-login
    link and code; API-key authentication is rejected for this workflow.
    """
    account = codex.account(refresh_token=True).account
    if account is not None and account.root.type == "chatgpt":
        print(f"Authenticated as {account.root.email or 'ChatGPT account'}")
        return
    if account is not None:
        raise RuntimeError("Codex must use ChatGPT authentication for this workflow.")

    login = codex.login_chatgpt_device_code()
    print("ChatGPT login is required.")
    print(f"Open: {login.verification_url}")
    print(f"Enter code: {login.user_code}")
    login.wait()
    if codex.account(refresh_token=True).account is None:
        raise RuntimeError("ChatGPT login did not complete.")


def ask_codex(codex, prompt):
    """Generate one direct answer in a fresh read-only Codex thread.

    Example: a valid grounded-answer prompt returns only the model response.
    An empty response is retried once because it cannot be reviewed or used.
    """
    from openai_codex import Sandbox
    from openai_codex.types import ReasoningEffort

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        thread = codex.thread_start(
            cwd=str(PROJECT_ROOT),
            developer_instructions=(
                "Use only the source text supplied in the user prompt. Do not use "
                "tools or read files. Return only the requested answer."
            ),
            ephemeral=True,
            model=MODEL,
            sandbox=Sandbox.read_only,
        )
        result = thread.run(
            prompt,
            effort=ReasoningEffort.medium,
            model=MODEL,
            sandbox=Sandbox.read_only,
        )
        answer = (result.final_response or "").strip()
        if answer:
            return answer
        last_error = f"Attempt {attempt} returned an empty response."

    raise ValueError(last_error)


def add_existing_results(rows, output_file):
    """Keep earlier successful rows so reruns resume safely.

    Example: after ID 7 is saved successfully, a later run skips ID 7 and
    processes only unfinished or failed rows.
    """
    if not output_file.is_file():
        return rows

    existing_rows = {row["id"]: row for row in read_csv_rows(output_file)}
    for row in rows:
        existing = existing_rows.get(row["id"])
        if existing and existing.get("generation_status") == "Success":
            for column in RESULT_COLUMNS:
                row[column] = existing.get(column, "")
    return rows


def write_rows(rows, output_file):
    """Save all row results after every source-answer attempt.

    Example: a failure on ID 12 leaves IDs 1–11 safely stored for a future
    resume run.
    """
    with output_file.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_arguments():
    """Read optional paths, a row limit, and a no-model dry-run switch.

    Example: ``--limit 2`` processes two unfinished questions. ``--dry-run``
    checks every source path and prompt without logging into Codex.
    """
    parser = argparse.ArgumentParser(
        description="Generate source-grounded answers for the RAGAS benchmark."
    )
    parser.add_argument("--input-file", type=Path, default=INPUT_FILE)
    parser.add_argument("--prompt-file", type=Path, default=PROMPT_FILE)
    parser.add_argument("--output-file", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    if arguments.limit is not None and arguments.limit < 1:
        parser.error("--limit must be at least 1.")
    return arguments


def main():
    """Generate source-grounded drafts for all unfinished benchmark questions.

    Example: ``python RAGAS/generate_grounded_source_answers.py`` processes
    every unfinished question and writes a separate CSV after each one.
    """
    arguments = read_arguments()
    rows = read_csv_rows(arguments.input_file)
    if len(rows) != 50:
        raise ValueError(f"Expected 50 benchmark questions, found {len(rows)}.")
    if len({row.get('id', '') for row in rows}) != len(rows):
        raise ValueError("Benchmark question CSV contains duplicate IDs.")

    prompt_template = read_prompt_template(arguments.prompt_file)
    rows = add_existing_results(rows, arguments.output_file)
    unfinished_rows = [row for row in rows if row.get("generation_status") != "Success"]
    if arguments.limit is not None:
        unfinished_rows = unfinished_rows[: arguments.limit]

    if arguments.dry_run:
        for row in unfinished_rows:
            source_path = resolve_source_path(row["source_category"], row["source_document"])
            source_text = source_path.read_text(encoding="utf-8-sig")
            render_prompt(prompt_template, row["query"], source_text)
            print(f"ID {row['id']}: {source_path.relative_to(PROJECT_ROOT)}")
        print(f"Dry run completed for {len(unfinished_rows)} question(s).")
        return 0

    if not unfinished_rows:
        print("No unfinished questions.")
        return 0

    Codex = load_codex_sdk()
    failures = 0
    with Codex() as codex:
        ensure_chatgpt_login(codex)
        for number, row in enumerate(unfinished_rows, start=1):
            print(f"[{number}/{len(unfinished_rows)}] ID {row['id']}: {row['query']}")
            request_start = time.perf_counter()
            try:
                source_path = resolve_source_path(
                    row["source_category"], row["source_document"]
                )
                source_text = source_path.read_text(encoding="utf-8-sig")
                prompt = render_prompt(prompt_template, row["query"], source_text)
                row["generated_grounded_answer"] = ask_codex(codex, prompt)
                row["source_document_path"] = str(source_path.relative_to(PROJECT_ROOT))
                row["model"] = MODEL
                row["reasoning_effort"] = "medium"
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
            write_rows(rows, arguments.output_file)

    print(f"Completed: {len(unfinished_rows) - failures}")
    print(f"Failed: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
