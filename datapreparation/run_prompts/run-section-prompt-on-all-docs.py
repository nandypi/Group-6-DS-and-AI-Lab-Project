"""
Reason this file exists:
Clean every grouped section from the NSE documents longer than 10 pages with
the v1 section prompt and the official Codex Python SDK.

Project terms:
- Section folder: one document's folder of grouped Markdown sections.
- Original YAML: the first front matter block in a section. It identifies the
  source document, page range, and source section IDs.
- Cleaned section: Codex's Markdown output, which preserves the original YAML
  and adds generated section metadata immediately after it.

Code flow:
1. Load the v1 section prompt.
2. Find every Markdown section in every document folder, or one --folder.
3. Read the complete section, including its original YAML metadata.
4. Insert the section into the prompt and send it in a read-only Codex thread.
5. Confirm the response preserves the original YAML and has a second YAML block.
6. Save the cleaned section under the matching output document folder.
7. Skip valid existing outputs so an interrupted run can resume.

Example:
sectioned_files/report/group_001.md -> v1 prompt -> Codex ->
cleaned_section_files/report/group_001.md

ASSUMPTION: every input section starts with one YAML front matter block.
ASSUMPTION: document folders contain their section files directly, not in nested folders.
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
    / "knowledge_extraction"
    / "greater_than_10_pages"
    / "sectioned_files"
)
OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "nse_files_final"
    / "knowledge_extraction"
    / "greater_than_10_pages"
    / "cleaned_section_files"
)
PROMPT_PATH = (
    PROJECT_ROOT
    / "prompts"
    / "KE-prompts-for-nse-docs"
    / "KE-section-prompt-v1.md"
)
MODEL = "gpt-5.5"
MAX_ATTEMPTS = 2
REQUIRED_GENERATED_METADATA_FIELDS = (
    "section_title",
    "section_description",
    "topics",
    "sample_queries",
)


def read_section(path):
    """
    Return the complete section and its original YAML block.

    Called before rendering a prompt and validating its output. A section
    beginning with YAML followed by "# Results" returns the full text and the
    YAML block, including its opening and closing --- lines.
    """
    section_text = path.read_text(encoding="utf-8-sig")
    lines = section_text.splitlines(keepends=True)

    if not lines or lines[0].strip() != "---":
        raise ValueError("missing original YAML front matter at the top of the file")

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            original_yaml = "".join(lines[: index + 1])
            if not "".join(lines[index + 1 :]).strip():
                raise ValueError("section text is empty")
            return section_text, original_yaml

    raise ValueError("original YAML front matter does not have a closing --- line")


def render_prompt(prompt_template, section_text):
    """
    Insert one complete section into the v1 prompt.

    Called after read_section. The original YAML stays in the supplied text so
    Codex can preserve it exactly in the cleaned result.
    """
    return prompt_template.replace("{DOCUMENT_TEXT}", section_text)


def validate_markdown(response_text, original_yaml):
    """
    Return clean Markdown only when the YAML output contract is met.

    Called after Codex responds and when checking saved output. The response
    must start with the unchanged original YAML and then contain a second YAML
    block for the generated section metadata.
    """
    if not response_text or not response_text.strip():
        raise ValueError("Codex returned an empty response")

    markdown = response_text.strip() + "\n"
    expected_yaml = original_yaml.replace("\r\n", "\n")

    if markdown.startswith("```") and markdown.rstrip().endswith("```"):
        raise ValueError("Codex wrapped the Markdown in a code fence")

    if "<DOCUMENT>" in markdown or "</DOCUMENT>" in markdown:
        raise ValueError("Codex copied the prompt's document boundary")

    if not markdown.startswith(expected_yaml):
        raise ValueError("Codex did not preserve the original YAML block exactly")

    after_original_yaml = markdown[len(expected_yaml) :].lstrip("\r\n")
    if not after_original_yaml.startswith("---\n"):
        raise ValueError("Codex did not add a second YAML metadata block")

    second_yaml_end = after_original_yaml.find("\n---", 4)
    if second_yaml_end == -1:
        raise ValueError("the generated YAML metadata block has no closing --- line")

    generated_yaml = after_original_yaml[: second_yaml_end + 4]
    for field in REQUIRED_GENERATED_METADATA_FIELDS:
        has_field = any(
            line.startswith(f"{field}:")
            for line in generated_yaml.splitlines()
        )
        if not has_field:
            raise ValueError(f"the generated YAML metadata is missing {field}")

    if not after_original_yaml[second_yaml_end + 4 :].strip():
        raise ValueError("the cleaned section text is empty")

    return markdown


def existing_output_is_valid(output_path, original_yaml):
    """
    Return true when an existing output meets the section output contract.

    Called before each request so reruns preserve completed cleaned sections.
    """
    if not output_path.is_file():
        return False

    try:
        validate_markdown(output_path.read_text(encoding="utf-8"), original_yaml)
    except (OSError, ValueError):
        return False

    return True


def ensure_chatgpt_login(codex):
    """
    Ensure the SDK is authenticated with ChatGPT, never with an API key.

    Called once before processing. If signed out, it shows device-login details
    and waits for the user to complete authentication.
    """
    account = codex.account(refresh_token=True).account

    if account is not None and account.root.type == "chatgpt":
        print(f"Authenticated as {account.root.email or 'ChatGPT account'}")
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

    if codex.account(refresh_token=True).account is None:
        raise RuntimeError("ChatGPT login did not complete")

    print("ChatGPT login completed")


def ask_codex(codex, prompt, original_yaml):
    """
    Send one rendered section prompt in a fresh read-only Codex thread.

    Called once or twice per section. The second attempt is used only when the
    first response violates the Markdown and YAML contract.
    """
    from openai_codex import Sandbox
    from openai_codex.types import ReasoningEffort

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        thread = codex.thread_start(
            cwd=str(PROJECT_ROOT),
            developer_instructions=(
                "Use only the section supplied in the user prompt. Do not use tools "
                "or read files. Return only the requested Markdown."
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
            return validate_markdown(result.final_response, original_yaml)
        except ValueError as error:
            last_error = error
            print(f"  Attempt {attempt} returned invalid output: {error}")

    raise ValueError(f"Codex failed after {MAX_ATTEMPTS} attempts: {last_error}")


def load_codex_sdk():
    """
    Import the SDK or raise an error containing the install command.

    Called before processing so a missing dependency fails early.
    """
    try:
        from openai_codex import Codex
    except ImportError as error:
        raise RuntimeError(
            "The official Codex Python SDK is not installed. Run: "
            ".\\venv\\Scripts\\python.exe -m pip install openai-codex"
        ) from error

    return Codex


def select_document_folders(folder_name):
    """
    Return all document folders or one direct child selected with --folder.

    For example, --folder report processes only sectioned_files/report and
    rejects paths that could point outside the sectioned-files folder.
    """
    if folder_name is None:
        return sorted(path for path in INPUT_DIR.iterdir() if path.is_dir())

    if Path(folder_name).name != folder_name:
        raise ValueError("--folder must contain a folder name, not a path")

    folder_path = INPUT_DIR / folder_name
    if not folder_path.is_dir():
        raise ValueError(f"section folder not found: {folder_path}")

    return [folder_path]


def find_section_files(document_folders):
    """
    Return each section file and its output path, preserving folder names.

    Called after the folder selection. A file in sectioned_files/report is
    mapped to cleaned_section_files/report with the same filename.
    """
    selected_files = []

    for folder_path in document_folders:
        output_folder = OUTPUT_DIR / folder_path.name
        for input_path in sorted(folder_path.glob("*.md")):
            selected_files.append((input_path, output_folder / input_path.name))

    return selected_files


def write_markdown(path, markdown):
    """
    Save one cleaned section as UTF-8 Markdown.

    Called immediately after a successful response so later failures do not
    lose completed work.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def main():
    """
    Clean all selected long-document sections and print a final summary.

    This entry point returns 0 when every section succeeds, 1 for setup or
    processing failures, and 2 for invalid command-line input.
    """
    parser = argparse.ArgumentParser(
        description="Clean grouped NSE document sections with the v1 section prompt."
    )
    parser.add_argument(
        "--folder",
        help="Process one direct folder from sectioned_files instead of every folder.",
    )
    args = parser.parse_args()

    if not PROMPT_PATH.is_file():
        print(f"ERROR: prompt file not found: {PROMPT_PATH}", file=sys.stderr)
        return 1

    if not INPUT_DIR.is_dir():
        print(f"ERROR: input folder not found: {INPUT_DIR}", file=sys.stderr)
        return 1

    try:
        document_folders = select_document_folders(args.folder)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    input_files = find_section_files(document_folders)
    if not input_files:
        print("ERROR: no Markdown section files found in the selected folders", file=sys.stderr)
        return 1

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    processed = 0
    skipped = 0
    failures = []

    try:
        Codex = load_codex_sdk()

        with Codex() as codex:
            ensure_chatgpt_login(codex)

            for number, (input_path, output_path) in enumerate(input_files, start=1):
                print(f"[{number}/{len(input_files)}] {input_path.relative_to(INPUT_DIR)}")

                try:
                    section_text, original_yaml = read_section(input_path)

                    if existing_output_is_valid(output_path, original_yaml):
                        print("  Skipped: valid Markdown output already exists")
                        skipped += 1
                        continue

                    prompt = render_prompt(prompt_template, section_text)
                    markdown = ask_codex(codex, prompt, original_yaml)
                    write_markdown(output_path, markdown)
                    print(f"  Saved: {output_path.relative_to(PROJECT_ROOT)}")
                    processed += 1
                except Exception as error:
                    print(f"  ERROR: {error}", file=sys.stderr)
                    failures.append((str(input_path.relative_to(INPUT_DIR)), str(error)))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print()
    print(f"Document folders selected: {len(document_folders)}")
    print(f"Markdown sections found: {len(input_files)}")
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
