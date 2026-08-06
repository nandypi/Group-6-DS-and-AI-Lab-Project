"""Fix unquoted YAML string values that contain colons.

Problem
-------
19 Markdown files across the five data-source directories have YAML front
matter where string values contain a literal colon character, e.g.:

    section_title: Financial Instruments: Carrying Value and Fair Value
    title: Launching Today: Infosys Customer Experience Suite for Salesforce

PyYAML's safe_load interprets the second colon as a mapping-value indicator
and raises:
    yaml.scanner.ScannerError: mapping values are not allowed here

Fix
---
For every key-value line in the YAML front matter whose value is an unquoted
plain scalar containing `: ` or ending with `:`, wrap the value in double
quotes.  List-item lines (`  - some value: with colon`) receive the same
treatment.  All other lines (already-quoted values, nested mapping keys,
block-scalar indicators, etc.) are left unchanged.

Usage
-----
    # Dry run – print what would change without writing anything:
    python fix_yaml_quoting.py --dry-run

    # Apply fixes in-place:
    python fix_yaml_quoting.py
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "metadata_embedding_pipeline"))
from metadata_embedding_utils import DATA_SOURCES, PROJECT_ROOT


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Matches a block key-value line:  [indent] key: value
# Group 1 = everything up to and including the space after the colon
# Group 2 = the unquoted scalar value (must not start with ", ', [, {, |, >, ~)
_KEY_VALUE = re.compile(
    r'^(\s*[\w][\w\s\-\.]*:\s+)([^\'\"\[\{\|\>\~\#\n\r].*)$'
)

# Matches a list-item line:  [indent] - value
# Group 1 = everything up to and including the space after the dash
# Group 2 = the unquoted scalar value
_LIST_ITEM = re.compile(
    r'^(\s*-\s+)([^\'\"\[\{\|\>\~\#\n\r].*)$'
)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _needs_quoting(value: str) -> bool:
    """Return True if an unquoted YAML scalar value would cause a parse error.

    The two problematic patterns are:
      - a colon followed by a space anywhere in the value  (e.g. "A: B")
      - a colon at the very end of the value               (e.g. "AI-first:")
    """
    stripped = value.rstrip()
    return ": " in value or stripped.endswith(":")


def _quote_value(value: str) -> str:
    """Wrap *value* in double quotes, escaping backslashes and double quotes."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def fix_yaml_line(raw_line: str) -> tuple[str, bool]:
    """Return (possibly fixed line, was_changed).

    Only the value portion of a key-value or list-item line is touched.
    Lines that are already quoted, are block-scalar starters, or contain
    no problematic colon are returned unchanged.
    """
    # Preserve the original line ending.
    body = raw_line.rstrip("\r\n")
    ending = raw_line[len(body):]

    for pattern in (_KEY_VALUE, _LIST_ITEM):
        m = pattern.fullmatch(body)
        if m:
            prefix, value = m.group(1), m.group(2)
            if _needs_quoting(value):
                fixed = prefix + _quote_value(value) + ending
                return fixed, True
            return raw_line, False

    return raw_line, False


def fix_yaml_block(yaml_lines: list[str]) -> tuple[list[str], int]:
    """Apply fix_yaml_line to every line in the YAML block.

    Returns (fixed_lines, number_of_lines_changed).
    """
    fixed = []
    changes = 0
    for line in yaml_lines:
        new_line, changed = fix_yaml_line(line)
        fixed.append(new_line)
        if changed:
            changes += 1
    return fixed, changes


def process_file(path: Path, dry_run: bool) -> str:
    """Inspect and optionally fix one Markdown file.

    Returns a short status string for reporting.
    """
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    # Must start with the YAML delimiter.
    if not lines or lines[0].rstrip("\r\n") != "---":
        return "no-yaml"

    # Find the closing delimiter.
    close_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            close_idx = i
            break

    if close_idx is None:
        return "no-close"

    yaml_lines = lines[1:close_idx]
    yaml_text = "".join(yaml_lines)

    # Already parses fine – nothing to fix.
    try:
        yaml.safe_load(yaml_text)
        return "ok"
    except yaml.YAMLError:
        pass

    fixed_yaml_lines, n_changes = fix_yaml_block(yaml_lines)
    fixed_yaml_text = "".join(fixed_yaml_lines)

    # Verify the fix actually resolves the parse error.
    try:
        yaml.safe_load(fixed_yaml_text)
    except yaml.YAMLError as exc:
        return f"fix-failed: {exc}"

    if dry_run:
        return f"would-fix ({n_changes} line(s) changed)"

    # Re-assemble the file: opening --- + fixed YAML + rest unchanged.
    new_content = (
        lines[0]
        + fixed_yaml_text
        + "".join(lines[close_idx:])
    )
    path.write_text(new_content, encoding="utf-8")
    return f"fixed ({n_changes} line(s) changed)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def read_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quote unquoted YAML string values that contain colons."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing any files.",
    )
    return parser.parse_args()


def main() -> None:
    args = read_arguments()
    mode = "DRY RUN" if args.dry_run else "APPLYING FIXES"
    print(f"fix_yaml_quoting.py — {mode}\n")

    counts: dict[str, int] = {}

    for source in DATA_SOURCES:
        if not source.is_dir():
            print(f"  [WARN] Source not found, skipping: {source}")
            continue
        for path in sorted(source.rglob("*.md")):
            status = process_file(path, dry_run=args.dry_run)
            counts[status.split(" ")[0]] = counts.get(status.split(" ")[0], 0) + 1
            if status not in ("ok", "no-yaml"):
                rel = path.relative_to(PROJECT_ROOT)
                print(f"  [{status}] {rel}")

    print()
    print("=== Summary ===")
    for status, n in sorted(counts.items()):
        print(f"  {status:20s}: {n}")


if __name__ == "__main__":
    main()
