"""
Reason this file exists:
Apply the v4 whole-document knowledge-extraction prompt to every Markdown file
in the final 10-page-or-fewer NSE folder by using the official Codex Python SDK.

Project terms:
- Whole-document prompt: the prompt used when the complete document is at most
  10 pages and can be sent in one request.
- Front matter: the metadata block between the two --- lines at the top of a
  Markdown file.
- Output file: one validated JSON result written to the matching knowledge-
  extraction output folder.

Code flow:
1. Load prompts/KE-prompts-for-nse-docs/KE-whole-document-prompt-v5.md.
2. Find each .md file directly inside the final 10-page-or-fewer NSE folder.
3. Read its front matter and complete document text.
4. Replace the prompt placeholders with that document's values.
5. Start a fresh read-only Codex thread and send the rendered prompt.
6. Validate the final response as JSON and save it immediately.
7. Skip valid existing outputs so an interrupted run can resume.

Example:
Infosys_02022026183006_PR_02022026.md -> rendered prompt -> Codex ->
data/nse_files_final/knowledge_extraction/equal_or_less_than_10_pages/
Infosys_02022026183006_PR_02022026.json

ASSUMPTION: every input document is complete and has at most 10 pages.
ASSUMPTION: front-matter values are simple strings or numbers, not nested YAML.
ASSUMPTION: the category is used for both document type and primary category
because the current front matter provides only one category field.
ASSUMPTION: every Codex request uses gpt-5.5 with low reasoning effort.
"""

import argparse
import json
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
    / "knowledge_extraction"
    / "equal_or_less_than_10_pages"
)
PROMPT_PATH = (
    PROJECT_ROOT
    / "prompts"
    / "KE-prompts-for-nse-docs"
    / "KE-whole-document-prompt-v5.md"
)
MODEL = "gpt-5.5"
MAX_ATTEMPTS = 2

REQUIRED_OUTPUT_FIELDS = {
    "document_name",
    "is_material",
    "title",
    "detailed_summary",
    "key_facts",
    "financial_metrics",
    "corporate_actions",
    "partnerships_or_deals",
    "leadership_changes",
    "litigation_or_regulatory_matters",
    "risk_factors",
    "esg_or_csr_items",
    "products_or_platforms",
    "important_text_spans",
    "search_keywords",
    "sample_questions",
    "processing_notes",
}


def remove_matching_quotes(value):
    """
    Remove one matching pair of quotes from a front-matter value.

    Called while reading metadata. For example, '"Updates"' returns 'Updates'.
    """
    if len(value) < 2:
        return value

    starts_and_ends_with_double_quote = value[0] == '"' and value[-1] == '"'
    starts_and_ends_with_single_quote = value[0] == "'" and value[-1] == "'"

    if starts_and_ends_with_double_quote or starts_and_ends_with_single_quote:
        return value[1:-1]

    return value


def read_markdown_document(path):
    """
    Return a document's front matter and body text.

    Called once before rendering a prompt. A file beginning with
    '---\npages: 3\n---\nHello' returns ({'pages': '3'}, 'Hello').
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
    Return a printable metadata value or 'Unknown' when it is unavailable.

    Called while rendering the prompt. For example, a missing source_url
    returns 'Unknown' instead of leaving a template placeholder unresolved.
    """
    value = metadata.get(key)

    if value is None or str(value).strip() == "":
        return "Unknown"

    return str(value)


def render_prompt(prompt_template, path, metadata, document_text):
    """
    Fill the whole-document prompt for one Markdown file.

    Called after read_markdown_document. The returned string is sent directly
    to Codex and contains no unresolved project template placeholders.
    """
    category = metadata_value(metadata, "category")
    page_end = metadata_value(metadata, "pages")

    values = {
        "{DOCUMENT_NAME}": path.name,
        "{DOCUMENT_URL}": metadata_value(metadata, "source_url"),
        "{DOCUMENT_TYPE}": category,
        "{PRIMARY_CATEGORY}": category,
        "{ANNOUNCEMENT_DATE}": metadata_value(metadata, "document_date"),
        "{PAGE_START}": "1",
        "{PAGE_END}": page_end,
        "{DOCUMENT_TEXT}": document_text,
    }

    rendered_prompt = prompt_template
    for placeholder, value in values.items():
        rendered_prompt = rendered_prompt.replace(placeholder, value)

    return rendered_prompt


def remove_json_code_fence(response_text):
    """
    Remove an optional Markdown code fence around a Codex JSON response.

    Called before json.loads. For example, ```json\n{}\n``` returns {}.
    """
    text = response_text.strip()

    if not text.startswith("```"):
        return text

    first_newline = text.find("\n")
    if first_newline == -1 or not text.endswith("```"):
        return text

    return text[first_newline + 1 : -3].strip()


def parse_result(response_text):
    """
    Parse and validate the minimum contract required by the extraction prompt.

    Called after each Codex turn and when checking an existing output. A valid
    result returns a dict; malformed JSON or missing fields raises ValueError.
    """
    if not response_text:
        raise ValueError("Codex returned an empty response")

    try:
        result = json.loads(remove_json_code_fence(response_text))
    except json.JSONDecodeError as error:
        raise ValueError(f"Codex did not return valid JSON: {error}") from error

    if not isinstance(result, dict):
        raise ValueError("Codex returned JSON that is not an object")

    missing_fields = sorted(REQUIRED_OUTPUT_FIELDS - set(result))
    if missing_fields:
        missing_text = ", ".join(missing_fields)
        raise ValueError(f"Codex response is missing fields: {missing_text}")

    if not isinstance(result["is_material"], bool):
        raise ValueError("is_material must be true or false")

    return result


def existing_output_is_valid(path):
    """
    Return true when an output file contains a valid extraction result.

    Called before processing each input so reruns preserve completed work.
    """
    if not path.exists():
        return False

    try:
        parse_result(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False

    return True


def ensure_chatgpt_login(codex):
    """
    Ensure the SDK is authenticated with ChatGPT, never with an API key.

    Called once before processing files. When signed out, it starts a device
    login, prints the verification URL and code, and waits for completion.
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

    Called once or twice per document. A second attempt is made only when the
    first final response is missing or does not match the JSON contract.
    """
    from openai_codex import Sandbox
    from openai_codex.types import ReasoningEffort

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        thread = codex.thread_start(
            cwd=str(PROJECT_ROOT),
            developer_instructions=(
                "Analyze only the document text supplied in the user prompt. "
                "Do not use tools or read other files. Return only the requested JSON."
            ),
            ephemeral=True,
            model=MODEL,
            sandbox=Sandbox.read_only,
        )

        result = thread.run(
            prompt,
            effort=ReasoningEffort.low,
            model=MODEL,
            sandbox=Sandbox.read_only,
        )

        try:
            return parse_result(result.final_response)
        except ValueError as error:
            last_error = error
            print(f"  Attempt {attempt} returned invalid output: {error}")

    raise ValueError(f"Codex failed after {MAX_ATTEMPTS} attempts: {last_error}")


def write_result(path, result):
    """
    Write one completed result immediately using readable UTF-8 JSON.

    Called after a document succeeds so progress survives later failures.
    """
    json_text = json.dumps(result, ensure_ascii=False, indent=2)
    path.write_text(json_text + "\n", encoding="utf-8")


def load_codex_sdk():
    """
    Import the official SDK or raise an error with the exact install command.

    Called before any files are processed so a missing dependency fails early.
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
    Return either every input file or one explicitly requested file.

    Called by main after parsing --file. For example, --file sample.md returns
    only INPUT_DIR/sample.md and rejects paths outside that folder.
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
    Process every 10-page-or-fewer Markdown file and print a final summary.

    This is the script entry point. It returns 0 when every file succeeds and
    1 when setup fails or at least one document could not be processed.
    """
    parser = argparse.ArgumentParser(
        description="Apply the whole-document prompt with the Codex Python SDK."
    )
    parser.add_argument(
        "--file",
        help="Process one filename from the input folder instead of all files.",
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
                output_path = OUTPUT_DIR / f"{input_path.stem}.json"
                print(f"[{number}/{len(input_files)}] {input_path.name}")

                if existing_output_is_valid(output_path):
                    print("  Skipped: valid output already exists")
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
                    result = ask_codex(codex, prompt)
                    write_result(output_path, result)
                    print(f"  Saved: {output_path.relative_to(PROJECT_ROOT)}")
                    processed += 1
                except Exception as error:
                    print(f"  ERROR: {error}", file=sys.stderr)
                    failures.append((input_path.name, str(error)))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print()
    print(f"Input files selected: {len(input_files)}")
    print(f"Model: {MODEL}")
    print("Reasoning effort: low")
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
