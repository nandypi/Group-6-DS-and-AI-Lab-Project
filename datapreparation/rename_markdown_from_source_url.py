"""
Reason this file exists:
Rename converted markdown files using the original PDF filename from each
file's source_url metadata, removing Docling's truncated names and hash suffixes.

Code flow:
1. Scan temp/markdown-data/final for markdown files.
2. Read each file's front-matter metadata until source_url is found.
3. Convert the source_url basename from .pdf to .md.
4. Rename the markdown file when the target name is available.
5. Print how many files were renamed and why any files were skipped.
"""

import os
import re
from urllib.parse import unquote, urlparse


FINAL_DIR = os.path.join("temp", "markdown-data", "final")
SOURCE_URL_RE = re.compile(r'^source_url:\s*["\']?(.+?)["\']?\s*$')


def read_source_url(path):
    """
    Read the source_url value from a markdown file's top metadata block.

    Called once for each markdown file scanned in temp/markdown-data/final
    during the main rename loop at the bottom of this script.
    """
    with open(path, "r", encoding="utf-8") as f:
        first_line = f.readline()
        if first_line.strip() != "---":
            return None

        for line in f:
            if line.strip() == "---":
                return None

            match = SOURCE_URL_RE.match(line.strip())
            if match:
                return match.group(1)

    return None


def markdown_name_from_source_url(source_url):
    """
    Convert a source_url PDF path into the desired markdown filename.

    Called by the main rename loop immediately after read_source_url returns a
    source URL for the current markdown file.
    """
    parsed = urlparse(source_url)
    filename = os.path.basename(unquote(parsed.path))
    stem, _ = os.path.splitext(filename)
    return f"{stem}.md"


renamed = 0
skipped = []

for entry in os.scandir(FINAL_DIR):
    if not entry.is_file() or not entry.name.lower().endswith(".md"):
        continue

    source_url = read_source_url(entry.path)
    if source_url is None:
        skipped.append((entry.name, "missing source_url metadata"))
        continue

    new_name = markdown_name_from_source_url(source_url)
    new_path = os.path.join(FINAL_DIR, new_name)

    if entry.path == new_path:
        skipped.append((entry.name, "already named correctly"))
        continue

    if os.path.exists(new_path):
        skipped.append((entry.name, f"target already exists: {new_name}"))
        continue

    os.rename(entry.path, new_path)
    renamed += 1

print(f"Renamed {renamed} markdown files in {FINAL_DIR}")

if skipped:
    print(f"Skipped {len(skipped)} files:")
    for filename, reason in skipped:
        print(f"- {filename}: {reason}")
