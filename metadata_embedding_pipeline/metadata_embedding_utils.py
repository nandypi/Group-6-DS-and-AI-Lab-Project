"""Shared constants and pure helpers for the metadata-only embedding pipeline.

All functions here are side-effect free.  Import them from both
metadata_embedding_pipeline.py and metadata_embedding_benchmark.py to avoid
duplication while keeping the two scripts independently executable.
"""

import re
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

# Chroma database written by the embedding pipeline and read by the benchmark.
DB_PATH: Path = Path(__file__).resolve().parent / "chroma_db"

# Benchmark input / output files (same dataset used by the existing pipelines).
BENCHMARK_INPUT_CSV: Path = (
    PROJECT_ROOT / "data" / "infosys_rag_test_dataset_50_queries_v2.csv"
)
BENCHMARK_OUTPUT_CSV: Path = (
    PROJECT_ROOT
    / "data"
    / "infosys_rag_test_dataset_50_queries_v2_metadata_embeddings_results.csv"
)

RERANKER_BENCHMARK_OUTPUT_CSV: Path = (
    PROJECT_ROOT
    / "data"
    / "infosys_rag_test_dataset_50_queries_v2_metadata_reranker_results.csv"
)

# Mirrors the five DATA_SOURCES in index_documents.py, with the two section-chunk
# directories replaced by their _v2 counterparts (first YAML block stripped).
# The other three sources are identical to the existing pipeline.
DATA_SOURCES: list[Path] = [
    PROJECT_ROOT / "data" / "yfinance" / "clean-mds",
    PROJECT_ROOT / "data" / "trendlyne" / "clean-mds",
    # v2: first YAML block (document_name / group_id metadata) removed.
    PROJECT_ROOT
    / "data"
    / "infosys_earning_calls_press_conf_fact_sheets_results"
    / "cleaned_section_files_1500_2500_v2",
    PROJECT_ROOT
    / "data"
    / "nse_files_final"
    / "whole_document_cleaning"
    / "equal_or_less_than_10_pages",
    # v2: first YAML block (document_name / group_id metadata) removed.
    PROJECT_ROOT
    / "data"
    / "nse_files_final"
    / "knowledge_extraction"
    / "greater_than_10_pages"
    / "cleaned_section_files_1500_2500_v2",
]

# ---------------------------------------------------------------------------
# Embedding / collection settings (mirror the existing pipeline exactly)
# ---------------------------------------------------------------------------

EMBEDDING_MODEL: str = "text-embedding-3-small"
COLLECTION_NAME: str = "metadata_embeddings"
MAX_EMBEDDING_TOKENS: int = 8191
BATCH_SIZE: int = 20


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_markdown_files() -> list[Path]:
    """Return all .md paths under the five approved source directories, sorted.

    Mirrors find_markdown_files in index_documents.py but uses DATA_SOURCES
    defined above (two of the five point to _v2 directories).
    Raises FileNotFoundError if any source directory is missing.
    """
    files: list[Path] = []
    for source in DATA_SOURCES:
        if not source.is_dir():
            raise FileNotFoundError(f"ERROR: source folder not found: {source}")
        files.extend(source.rglob("*.md"))
    return sorted(files)


# ---------------------------------------------------------------------------
# YAML extraction
# ---------------------------------------------------------------------------

def extract_yaml_front_matter(content: str) -> dict[str, Any]:
    """Parse the single YAML front matter block that begins each v2 file.

    The v2 files each start with exactly one '---' … '---' block after the
    first YAML block was removed by strip_first_yaml.py.  Returns an empty
    dict when no valid YAML block is found or the block cannot be parsed.

    Example: a file whose first line is not '---' returns {}.
    """
    lines = content.splitlines(keepends=True)

    if not lines or lines[0].rstrip("\r\n") != "---":
        return {}

    # Find the matching closing delimiter.
    close_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            close_idx = i
            break

    if close_idx is None:
        return {}

    yaml_text = "".join(lines[1:close_idx])

    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return {}

    if not isinstance(parsed, dict):
        return {}

    return parsed


# ---------------------------------------------------------------------------
# YAML → readable embedding text
# ---------------------------------------------------------------------------

def _key_to_label(key: str) -> str:
    """Convert a snake_case YAML key to a human-readable Title Case label.

    Example: 'section_title' → 'Section Title'.
    Example: 'sample_queries' → 'Sample Queries'.
    """
    words = re.sub(r"[_\-]+", " ", key).split()
    return " ".join(w.capitalize() for w in words)


def metadata_to_text(metadata: dict[str, Any]) -> str:
    """Convert an arbitrary YAML metadata dict to embeddable plain text.

    Works dynamically for any schema – no keys are hardcoded.  Lists become
    bullet-pointed lines; scalar values are inlined after the label.  Empty
    or None values are silently skipped.

    Example input:
        {
            'section_title': 'Q1 FY26 Results',
            'topics': ['Revenue', 'Margin'],
            'sample_queries': ['What was revenue?'],
        }

    Example output:
        Section Title: Q1 FY26 Results

        Topics:
        - Revenue
        - Margin

        Sample Queries:
        - What was revenue?
    """
    if not metadata:
        return ""

    parts: list[str] = []
    for key, value in metadata.items():
        if value is None or value == "":
            continue
        label = _key_to_label(key)
        if isinstance(value, list):
            items = [str(item) for item in value if item is not None]
            if not items:
                continue
            parts.append(label + ":\n" + "\n".join(f"- {item}" for item in items))
        else:
            parts.append(f"{label}: {value}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# File text helper (used by the re-ranking benchmark)
# ---------------------------------------------------------------------------

def get_metadata_text_for_filepath(filepath: str) -> str:
    """Read the v2 file at *filepath* and return its YAML front matter as text.

    Used by the re-ranking benchmark to obtain the passage text for each
    retrieved candidate so the cross-encoder can score (query, passage) pairs.
    Returns the raw filepath string as a fallback when the file cannot be read
    or yields no YAML front matter.

    Example:
        'data/nse_files_final/…/group_001.md'
        → 'Section Title: AI Day Transcript\\n\\nTopics:\\n- AI strategy\\n- …'
    """
    path = PROJECT_ROOT / filepath
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return filepath
    metadata = extract_yaml_front_matter(content)
    text = metadata_to_text(metadata)
    return text if text else filepath


# ---------------------------------------------------------------------------
# Recall helpers
# ---------------------------------------------------------------------------

def normalize_filename(filename: str) -> str:
    """Strip directories, non-alphanumeric chars, and lowercase for matching.

    Example: 'FY26-Q1-earningscall.md' → 'fy26q1earningscallmd'.
    """
    return re.sub(r"[^a-z0-9]+", "", Path(filename).name.lower())


def _recall_key(source: str) -> str:
    """Return the key used for recall comparison.

    When *source* is a full path (contains a path separator), the key is
    ``parent_directory/filename`` — this uniquely identifies a group chunk
    across different parent documents while being insensitive to whether the
    path uses the old ``cleaned_section_files_1500_2500`` or the new ``_v2``
    directory name.

    When *source* is a bare filename the key is just the normalised filename,
    matching the existing benchmark behaviour.

    Example (full path):
        '.../cleaned_section_files_1500_2500_v2/INFY_xxx/group_001.md'
        → 'infy_xxx/group_001md'   (parent + file, separating slash kept)

    Example (bare filename):
        'FY26-Q1-earningscall.md'  →  'fy26q1earningscallmd'
    """
    p = Path(source)
    if len(p.parts) > 1:
        parent = re.sub(r"[^a-z0-9]+", "", p.parent.name.lower())
        name   = re.sub(r"[^a-z0-9]+", "", p.name.lower())
        return f"{parent}/{name}"
    return re.sub(r"[^a-z0-9]+", "", p.name.lower())


def expected_document_is_in_rank(
    expected_document: str,
    retrieved_documents: list[dict],
    rank_limit: int,
) -> bool:
    """Return True when the expected source appears within rank_limit results.

    Two matching modes depending on the shape of *expected_document*:

    Full path (e.g. ``data/.../cleaned_section_files_1500_2500_v2/INFY_xxx/group_001.md``):
        Compares ``parent_directory/filename`` from *expected_document*
        against the same key derived from the stored ``filepath`` in Chroma.
        This keeps group files from different parent documents distinct while
        being insensitive to the ``_v2`` prefix difference.

    Bare filename (e.g. ``Infosys_24062026172502_PR_24062026.md``):
        Compares only the normalised basename — identical to the existing
        run_without_reranking_benchmark.py behaviour.
    """
    is_full_path = len(Path(expected_document).parts) > 1
    expected_key = _recall_key(expected_document)

    for document in retrieved_documents[:rank_limit]:
        if is_full_path:
            # Use stored filepath for parent_dir/filename comparison.
            candidate = document.get("filepath") or document.get("filename", "")
        else:
            # Use stored filename (basename) for bare-filename comparison.
            candidate = document.get("filename") or document.get("filepath", "")
        if _recall_key(candidate) == expected_key:
            return True
    return False
