"""
Reason this file exists:
Clean every Markdown file with 10 pages or fewer using the v6 whole-document
prompt and the official Codex Python SDK.

Project terms:
- Front matter: metadata between the two --- lines at the top of an input file.
- Cleaned document: Markdown returned by Codex after conversion noise and
  non-substantive filing content have been removed.

Code flow:
1. Load the v6 whole-document prompt.
2. Find every Markdown file in the <=10-page NSE document folder.
3. Read each file's front matter and document text.
4. Fill the prompt placeholders with that document's metadata and text.
5. Send the rendered prompt in a fresh read-only Codex thread.
6. Validate the Markdown response and save it in the separate output folder.
7. Skip valid existing outputs so an interrupted run can resume.

Example:
input/Infosys.md -> v6 prompt -> Codex ->
data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages/Infosys.md

ASSUMPTION: every input document is complete and has at most 10 pages.
ASSUMPTION: front-matter values are simple strings or numbers, not nested YAML.
ASSUMPTION: category supplies both document type and primary category because
the current front matter provides only one category field.
ASSUMPTION: every Codex request uses gpt-5.5 with medium reasoning effort.
"""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "nse_files_final"
    / "categorisation_by_pages"
    / "equal_or_less_than_10_pages"
)
OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "nse_files_final"
    / "whole_document_cleaning"
    / "equal_or_less_than_10_pages"
)
PROMPT_PATH = (
    PROJECT_ROOT
    / "prompts"
    / "KE-prompts-for-nse-docs"
    / "KE-whole-document-prompt-v6.md"
)
MODEL = "gpt-5.5"
MAX_ATTEMPTS = 2


def remove_matching_quotes(value):
    """
    Remove one matching pair of quotes from a front-matter value.

    Called while reading metadata. For example, '"Updates"' returns 'Updates'.
    """
    if len(value) < 2:
        return value

    has_double_quotes = value[0] == '"' and value[-1] == '"'
    has_single_quotes = value[0] == "'" and value[-1] == "'"

    if has_double_quotes or has_single_quotes:
        return value[1:-1]

    return value


def read_markdown_document(path):
    """
    Return a document's front matter and body text.

    Called before rendering a prompt. A file containing front matter followed
    by "Hello" returns its metadata dictionary and "Hello".
    """
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)

    if not lines or lines[0].strip() != "---":
        raise ValueError("missing front matter at the top of the file")

    metadata = {}
    closing_line = None

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_line = index
            break

        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        metadata[key.strip()] = remove_matching_quotes(value.strip())

    if closing_line is None:
        raise ValueError("front matter does not have a closing --- line")

    document_text = "".join(lines[closing_line + 1 :]).strip()
    if not document_text:
        raise ValueError("document text is empty")

    return metadata, document_text


def metadata_value(metadata, key):
    """
    Return a printable metadata value or "Unknown" when it is unavailable.

    Called while rendering the prompt so no metadata placeholder is left empty.
    """
    value = metadata.get(key)

    if value is None or str(value).strip() == "":
        return "Unknown"

    return str(value)


def render_prompt(prompt_template, path, metadata, document_text):
    """
    Fill the v6 prompt placeholders for one input document.

    Called after reading the input. The result is sent directly to Codex.
    """
    category = metadata_value(metadata, "category")
    values = {
        "{DOCUMENT_NAME}": path.name,
        "{DOCUMENT_URL}": metadata_value(metadata, "source_url"),
        "{DOCUMENT_TYPE}": category,
        "{PRIMARY_CATEGORY}": category,
        "{ANNOUNCEMENT_DATE}": metadata_value(metadata, "document_date"),
        "{DOCUMENT_TEXT}": document_text,
    }

    rendered_prompt = prompt_template
    for placeholder, value in values.items():
        rendered_prompt = rendered_prompt.replace(placeholder, value)

    return rendered_prompt


def validate_markdown(response_text):
    """
    Return stripped Markdown or raise ValueError for an unusable response.

    Called after Codex responds and when checking saved output. For example,
    "# Results\n\nDetails" is returned unchanged, while a fenced response fails.
    """
    if not response_text or not response_text.strip():
        raise ValueError("Codex returned an empty response")

    markdown = response_text.strip()

    if markdown.startswith("```") and markdown.endswith("```"):
        raise ValueError("Codex wrapped the Markdown in a code fence")

    if "<DOCUMENT>" in markdown or "</DOCUMENT>" in markdown:
        raise ValueError("Codex copied the prompt's document boundary")

    return markdown


def existing_output_is_valid(path):
    """
    Return true when an output file contains usable Markdown.

    Called before each request so reruns preserve completed documents.
    """
    if not path.is_file():
        return False

    try:
        validate_markdown(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False

    return True


def ensure_chatgpt_login(codex):
    """
    Ensure the SDK is authenticated with ChatGPT, never with an API key.

    Called once before processing. If signed out, show the device login details
    and wait for the user to finish authentication.
    """
    account_response = codex.account(refresh_token=True)
    account = account_response.account

    if account is not None and account.root.type == "chatgpt":
        email = account.root.email or "ChatGPT account"
        print(f"Authenticated as {email}")
        return

    if account is not None:
        raise RuntimeError(
            "Codex is not using ChatGPT authentication. Sign out of the current "
            "Codex account before running this no-API-key workflow."
        )

    login = codex.login_chatgpt_device_code()
    print("ChatGPT login is required.")
    print(f"Open: {login.verification_url}")
    print(f"Enter code: {login.user_code}")
    login.wait()

    account_response = codex.account(refresh_token=True)
    if account_response.account is None:
        raise RuntimeError("ChatGPT login did not complete")

    print("ChatGPT login completed")


def ask_codex(codex, prompt):
    """
    Send one rendered prompt in a fresh read-only Codex thread.

    Called once or twice per document. A second request is made only when the
    first response is missing or violates the Markdown output contract.
    """
    from openai_codex import Sandbox
    from openai_codex.types import ReasoningEffort

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        thread = codex.thread_start(
            cwd=str(PROJECT_ROOT),
            developer_instructions=(
                "Use only the document supplied in the user prompt. "
                "Do not use tools or read files. Return only the requested Markdown."
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

        try:
            return validate_markdown(result.final_response)
        except ValueError as error:
            last_error = error
            print(f"  Attempt {attempt} returned invalid output: {error}")

    raise ValueError(f"Codex failed after {MAX_ATTEMPTS} attempts: {last_error}")


def write_markdown(path, markdown):
    """
    Save one cleaned document as readable UTF-8 Markdown.

    Called immediately after a successful response so later failures do not
    lose completed work.
    """
    path.write_text(markdown.rstrip() + "\n", encoding="utf-8")


def load_codex_sdk():
    """
    Import the SDK or raise an error containing the install command.

    Called before any requests so a missing dependency fails early.
    """
    try:
        from openai_codex import Codex
    except ImportError as error:
        raise RuntimeError(
            "The official Codex Python SDK is not installed. Run: "
            ".\\venv\\Scripts\\python.exe -m pip install openai-codex"
        ) from error

    return Codex


def select_input_files(file_name):
    """
    Return every eligible NSE document or the one requested with --file.

    For example, --file sample.md selects one file from the <=10-page folder
    and rejects paths that could point outside that folder.
    """
    if file_name is None:
        return sorted(INPUT_DIR.glob("*.md"))

    if Path(file_name).name != file_name:
        raise ValueError("--file must contain a filename, not a path")

    input_path = INPUT_DIR / file_name
    if not input_path.is_file():
        raise ValueError(f"input file not found: {input_path}")

    if input_path.suffix.lower() != ".md":
        raise ValueError("--file must name a Markdown file")

    return [input_path]


def main():
    """
    Clean the selected <=10-page NSE documents and print a final summary.

    This is the entry point. It returns 0 when every file succeeds, 1 for setup
    or processing failures, and 2 for invalid command-line input.
    """
    parser = argparse.ArgumentParser(
        description="Clean <=10-page NSE documents with the v6 whole-document prompt."
    )
    parser.add_argument(
        "--file",
        help="Process one filename from the <=10-page input folder instead of all files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reprocess files even when a valid Markdown output already exists.",
    )
    args = parser.parse_args()

    if not PROMPT_PATH.is_file():
        print(f"ERROR: prompt file not found: {PROMPT_PATH}", file=sys.stderr)
        return 1

    if not INPUT_DIR.is_dir():
        print(f"ERROR: input folder not found: {INPUT_DIR}", file=sys.stderr)
        return 1

    try:
        input_files = select_input_files(args.file)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if not input_files:
        print(f"ERROR: no Markdown files found in {INPUT_DIR}", file=sys.stderr)
        return 1

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    processed = 0
    skipped = 0
    failures = []

    try:
        Codex = load_codex_sdk()

        with Codex() as codex:
            ensure_chatgpt_login(codex)

            for number, input_path in enumerate(input_files, start=1):
                output_path = OUTPUT_DIR / input_path.name
                print(f"[{number}/{len(input_files)}] {input_path.name}")

                if not args.overwrite and existing_output_is_valid(output_path):
                    print("  Skipped: valid Markdown output already exists")
                    skipped += 1
                    continue

                try:
                    metadata, document_text = read_markdown_document(input_path)
                    prompt = render_prompt(
                        prompt_template,
                        input_path,
                        metadata,
                        document_text,
                    )
                    markdown = ask_codex(codex, prompt)
                    write_markdown(output_path, markdown)
                    print(f"  Saved: {output_path.relative_to(PROJECT_ROOT)}")
                    processed += 1
                except Exception as error:
                    print(f"  ERROR: {error}", file=sys.stderr)
                    failures.append((input_path.name, str(error)))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print()
    print(f"Markdown files found: {len(input_files)}")
    print(f"Model: {MODEL}")
    print("Reasoning effort: medium")
    print(f"Newly processed: {processed}")
    print(f"Already processed: {skipped}")
    print(f"Failed: {len(failures)}")

    if failures:
        for filename, reason in failures:
            print(f"- {filename}: {reason}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
