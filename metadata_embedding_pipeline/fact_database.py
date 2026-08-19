"""Build and query the SQLite financial-facts database.

Reads every Markdown file from the Infosys IR source only:
  data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500_v2

This includes quarterly fact sheets, earnings call transcripts, IFRS press
releases, and analyst-day materials for FY25–FY26.  Restricting to this
authoritative Infosys-only source avoids unit confusion (INR vs USD) and
extraneous noise from NSE annual reports and general financial news.

Extracts structured facts with fact_extractor.py (both table cells and
prose-embedded metric sentences) and stores them in a persistent SQLite
database at ``metadata_embedding_pipeline/facts.db``.

Schema (table: facts)
---------------------
id            INTEGER PRIMARY KEY AUTOINCREMENT
file_path     TEXT    – project-relative POSIX path to the source file
document_name TEXT    – immediate parent folder or file stem
source_folder TEXT    – grandparent folder (the DATA_SOURCE directory)
section_title TEXT    – YAML section_title (may be empty)
table_heading TEXT    – nearest preceding heading before the table
row_label     TEXT    – left-most cell of the data row (the metric name)
column_label  TEXT    – column header for this cell
raw_value     TEXT    – cell text exactly as written
value_numeric REAL    – parsed numeric value (NULL when not parseable)
unit          TEXT    – detected unit string ('', '%', 'USD_bn', …)
period        TEXT    – normalised period like 'Q1_FY26' (may be empty)
inserted_at   TEXT    – ISO timestamp of insertion

Usage
-----
    python metadata_embedding_pipeline/fact_database.py
    python metadata_embedding_pipeline/fact_database.py --rebuild

After the first build, rerun with --rebuild to drop and recreate the table
(useful when fact_extractor logic changes).
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

# Allow direct execution and sibling imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fact_extractor import extract_facts_from_file
from metadata_embedding_utils import PROJECT_ROOT

# Restrict to the authoritative Infosys IR source only.
# Using all 5 DATA_SOURCES mixes NSE annual-report tables (INR, multi-year)
# and general news articles, causing unit confusion in SQL queries.
FACT_DB_SOURCES: list[Path] = [
    PROJECT_ROOT
    / "data"
    / "infosys_earning_calls_press_conf_fact_sheets_results"
    / "cleaned_section_files_1500_2500_v2",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH: Path = Path(__file__).resolve().parent / "facts.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS facts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path     TEXT    NOT NULL,
    document_name TEXT    NOT NULL,
    source_folder TEXT    NOT NULL,
    section_title TEXT    NOT NULL DEFAULT '',
    table_heading TEXT    NOT NULL DEFAULT '',
    row_label     TEXT    NOT NULL,
    column_label  TEXT    NOT NULL,
    raw_value     TEXT    NOT NULL,
    value_numeric REAL,
    unit          TEXT    NOT NULL DEFAULT '',
    period        TEXT    NOT NULL DEFAULT '',
    inserted_at   TEXT    NOT NULL
)
"""

_CREATE_INDICES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_facts_period       ON facts (period)",
    "CREATE INDEX IF NOT EXISTS idx_facts_row_label    ON facts (row_label)",
    "CREATE INDEX IF NOT EXISTS idx_facts_document     ON facts (document_name)",
    "CREATE INDEX IF NOT EXISTS idx_facts_source_folder ON facts (source_folder)",
    "CREATE INDEX IF NOT EXISTS idx_facts_file_path    ON facts (file_path)",
]


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def create_schema(conn: sqlite3.Connection) -> None:
    """Create the facts table and indices if they do not yet exist."""
    conn.execute(_CREATE_TABLE_SQL)
    for sql in _CREATE_INDICES_SQL:
        conn.execute(sql)
    conn.commit()


def drop_table(conn: sqlite3.Connection) -> None:
    """Drop the facts table and its indices (used by --rebuild)."""
    conn.execute("DROP TABLE IF EXISTS facts")
    conn.commit()


# ---------------------------------------------------------------------------
# Database population
# ---------------------------------------------------------------------------

def find_all_markdown_files() -> list[Path]:
    """Return all .md paths under the Infosys IR source directory, sorted.

    Skips missing directories with a warning so that a partial corpus
    still produces a useful fact database.
    """
    files: list[Path] = []
    for source in FACT_DB_SOURCES:
        if not source.is_dir():
            print(f"  [warn] source folder not found, skipping: {source}")
            continue
        files.extend(source.rglob("*.md"))
    return sorted(files)


def populate_database(conn: sqlite3.Connection, files: list[Path]) -> dict:
    """Extract facts from every file and insert them into the database.

    Returns a summary dict with counts for logging.
    """
    now = datetime.now(timezone.utc).isoformat()
    total_facts = 0
    files_with_facts = 0
    files_empty = 0

    batch: list[tuple] = []
    BATCH_SIZE = 500

    def flush(batch: list[tuple]) -> None:
        conn.executemany(
            """INSERT INTO facts
               (file_path, document_name, source_folder, section_title,
                table_heading, row_label, column_label, raw_value,
                value_numeric, unit, period, inserted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            batch,
        )
        conn.commit()

    for file_path in tqdm(files, desc="Extracting facts"):
        facts = extract_facts_from_file(file_path, PROJECT_ROOT)
        if not facts:
            files_empty += 1
            continue
        files_with_facts += 1
        total_facts += len(facts)
        for f in facts:
            batch.append(
                (
                    f["file_path"],
                    f["document_name"],
                    f["source_folder"],
                    f["section_title"],
                    f["table_heading"],
                    f["row_label"],
                    f["column_label"],
                    f["raw_value"],
                    f["value_numeric"],
                    f["unit"],
                    f["period"],
                    now,
                )
            )
            if len(batch) >= BATCH_SIZE:
                flush(batch)
                batch.clear()

    if batch:
        flush(batch)

    return {
        "total_facts": total_facts,
        "files_with_facts": files_with_facts,
        "files_empty": files_empty,
    }


# ---------------------------------------------------------------------------
# Schema description for the LLM
# ---------------------------------------------------------------------------

def get_schema_description(conn: sqlite3.Connection) -> str:
    """Return a compact schema + sample-data string for use in LLM prompts.

    Includes a few sample rows so the LLM understands the data shape.
    """
    sample_rows = conn.execute(
        """SELECT period, row_label, column_label, raw_value, value_numeric, unit,
                  document_name, file_path
           FROM facts
           WHERE value_numeric IS NOT NULL
             AND period != ''
           ORDER BY period, row_label
           LIMIT 10"""
    ).fetchall()

    sample_text = "\n".join(
        f"  period={r[0]!r:15} row_label={r[1]!r:40} "
        f"col={r[2]!r:35} value={r[4]} unit={r[5]!r} doc={r[6]!r}"
        for r in sample_rows
    )

    distinct_periods = conn.execute(
        "SELECT DISTINCT period FROM facts WHERE period != '' ORDER BY period"
    ).fetchall()
    period_list = ", ".join(r[0] for r in distinct_periods)

    # Dynamically query representative row_labels for key metrics.
    def _sample_labels(kw: str, col_filter: str = "") -> str:
        where = f"AND {col_filter}" if col_filter else ""
        rows_ = conn.execute(
            f"SELECT DISTINCT row_label FROM facts "
            f"WHERE LOWER(row_label) LIKE ? {where} LIMIT 3",
            (f"%{kw.lower()}%",),
        ).fetchall()
        return " | ".join(f"'{r[0]}'" for r in rows_)

    # For TCV specifically, look in prose.
    tcv_labels = conn.execute(
        "SELECT DISTINCT row_label FROM facts "
        "WHERE unit='USD_bn' AND column_label='prose' "
        "AND period LIKE 'Q%_FY26' LIMIT 3"
    ).fetchall()
    tcv_label_ex = " | ".join(f"'{r[0][:60]}'" for r in tcv_labels)

    return f"""SQLite table: facts

Columns:
  id            INTEGER  primary key
  file_path     TEXT     project-relative path to source markdown file
  document_name TEXT     parent folder or file stem (e.g. 'FY26-Q1-fact-sheet')
  source_folder TEXT     grandparent DATA_SOURCE folder name
  section_title TEXT     YAML section_title field
  table_heading TEXT     heading above the table in the markdown
  row_label     TEXT     left-most cell of the row (the metric name)
  column_label  TEXT     column header (e.g. 'Jun 30, 2025') OR 'prose'
  raw_value     TEXT     exact cell text
  value_numeric REAL     parsed numeric value (NULL if not a number)
  unit          TEXT     '%', 'USD_bn', 'USD_mn', 'INR_crore', or '' (bare number)
  period        TEXT     normalised quarter e.g. 'Q1_FY26' ('' if unknown)
  inserted_at   TEXT     ISO timestamp

Total rows: {conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]:,}
Rows with numeric values: {conn.execute("SELECT COUNT(*) FROM facts WHERE value_numeric IS NOT NULL").fetchone()[0]:,}
Known periods: {period_list}

METRIC LOOKUP (use these exact patterns in WHERE clauses):

  Operating Margin — REPORTED IFRS only (quarterly, %):
      row_label LIKE '%Operating Margin%' AND column_label != 'prose'
      AND column_label NOT LIKE '%Growth%' AND column_label NOT LIKE '%YoY%'
      AND column_label NOT LIKE '%QoQ%' AND column_label NOT LIKE '%Adjusted%'
      AND column_label NOT LIKE '%non-IFRS%'
      AND unit = '%' AND value_numeric BETWEEN 15 AND 25
      (Note: Q3 FY26 fact sheet also stores an "Adjusted non-IFRS" margin at 21.0–21.2%.
       MUST exclude those with column_label NOT LIKE '%Adjusted%'.
       The REPORTED IFRS operating margin values are: Q1=20.8%, Q2=21.0%, Q3=18.4%, Q4=20.9%.)
      Sample labels: {_sample_labels('operating margin', "column_label != 'prose'")}

  Voluntary Attrition (IT Services, %):
      row_label LIKE '%Voluntary Attrition%' AND column_label != 'prose'
      AND unit = '%' AND value_numeric BETWEEN 0 AND 100
      Sample labels: {_sample_labels('voluntary attrition', "column_label != 'prose'")}

  Revenue (quarterly, USD millions):
      row_label = 'Revenues' AND unit = 'USD_mn'
      AND document_name LIKE '%fact-sheet%'
      (Note: the exact row_label is 'Revenues' with an 's', not 'Revenue')

  Net Profit (quarterly, USD millions):
      row_label LIKE '%Net Profit%' AND unit = 'USD_mn'
      AND document_name LIKE '%fact-sheet%' AND value_numeric > 0

  Basic EPS in USD (quarterly, USD per share):
      row_label = 'Basic EPS ($)' AND unit = 'USD_mn'
      AND document_name LIKE '%fact-sheet%'
      (Note: value is small, e.g. 0.23 — correct even though unit says USD_mn)

  Large Deal TCV (quarterly, USD billions) — stored ONLY in prose:
      unit = 'USD_bn' AND column_label = 'prose'
      AND (LOWER(row_label) LIKE '%large deal%' OR LOWER(row_label) LIKE '%tcv%'
           OR LOWER(row_label) LIKE '%total contract%')
      AND value_numeric < 6
      (Note: MUST add value_numeric < 6 — the FY26 full-year total ~$15Bn AND the H1
       cumulative ~$6.9Bn both appear in prose. Infosys quarterly TCV is always < $6Bn.)
      Sample labels (truncated): {tcv_label_ex}

  Net-New Deal percentage (quarterly, %):
      unit = '%' AND column_label = 'prose'
      AND (LOWER(row_label) LIKE '%net new%' OR LOWER(row_label) LIKE '%net-new%')
      AND value_numeric BETWEEN 45 AND 70
      (Note: MUST add value_numeric BETWEEN 45 AND 70 — 100% outliers exist from
       individual deal announcements ("100% net new") and should be excluded.
       Regional/segment net-new values (e.g. 80% for EURS region) also appear in prose
       and must be excluded. Quarterly net-new deal % for Infosys is always 50%–70%.)

Sample rows (from table-based facts with known periods):
{sample_text}

GENERAL SQL RULES:
  - Always SELECT file_path for citations.
  - Always WHERE value_numeric IS NOT NULL AND period != '' (when period matters).
  - For FY26 full-year use: period IN ('Q1_FY26','Q2_FY26','Q3_FY26','Q4_FY26').
  - TCV data is only in prose (column_label = 'prose') — do NOT add column_label != 'prose'.
  - For all other precise metrics, add AND column_label != 'prose'.
  - When aggregating across quarters also add value_numeric range guards to filter noise.
  - Return ONLY the raw SQL with no markdown fences.
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the SQLite financial-facts database from cleaned Markdown files."
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Drop and recreate the facts table before inserting (full rebuild).",
    )
    return parser.parse_args()


def main() -> None:
    """Build or rebuild the facts database from all DATA_SOURCES."""
    args = _read_arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print(f"Database : {DB_PATH}")
    print(f"Mode     : {'rebuild' if args.rebuild else 'incremental (append)'}")
    print()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    if args.rebuild:
        print("Dropping existing facts table…")
        drop_table(conn)

    create_schema(conn)

    if not args.rebuild:
        existing = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        if existing > 0:
            print(
                f"Database already contains {existing:,} rows. "
                "Use --rebuild to recreate. Exiting."
            )
            conn.close()
            return

    files = find_all_markdown_files()
    print(f"Found {len(files):,} Markdown files across {len(FACT_DB_SOURCES)} source director(y/ies).")
    print()

    summary = populate_database(conn, files)
    conn.close()

    print()
    print("=== Build Summary ===")
    print(f"Files processed (with facts) : {summary['files_with_facts']:,}")
    print(f"Files skipped (no tables)    : {summary['files_empty']:,}")
    print(f"Total facts inserted         : {summary['total_facts']:,}")
    print(f"Database written to          : {DB_PATH}")


if __name__ == "__main__":
    main()
