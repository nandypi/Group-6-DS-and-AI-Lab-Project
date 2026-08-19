"""Extract structured financial facts from cleaned Markdown files.

Parses every markdown table in a file and stores each cell as a structured
fact with row label, column label, raw value, parsed numeric value, unit,
and period.  No LLM calls are made; this is pure programmatic parsing.

Handles all five DATA_SOURCES defined in metadata_embedding_utils:
  - data/yfinance/clean-mds
  - data/trendlyne/clean-mds
  - data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500_v2
  - data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages
  - data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500_v2

Files with no markdown tables return an empty list — the caller skips them
rather than erroring.

Example:
    facts = extract_facts_from_file(Path("data/.../FY26-Q1-fact-sheet/group_001.md"), PROJECT_ROOT)
    # returns a list of dicts, one per table cell, with keys:
    # file_path, document_name, source_folder, section_title,
    # table_heading, row_label, column_label, raw_value,
    # value_numeric, unit, period
"""

import re
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Infosys fiscal-quarter date mapping.
# Infosys FY runs April → March.  "Quarter ended Jun 30 YEAR" = Q1 FY(YEAR+1).
# ---------------------------------------------------------------------------

_QUARTER_END_TO_FQ: dict[tuple[int, int], tuple[str, int]] = {
    (3, 31):  ("Q4", 0),   # Mar 31 YEAR  → Q4_FY{YEAR}
    (6, 30):  ("Q1", 1),   # Jun 30 YEAR  → Q1_FY{YEAR+1}
    (9, 30):  ("Q2", 1),   # Sep 30 YEAR  → Q2_FY{YEAR+1}
    (12, 31): ("Q3", 1),   # Dec 31 YEAR  → Q3_FY{YEAR+1}
}

_MONTH_NAMES: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,  "may": 5,  "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Compiled regex patterns used across multiple functions.
_RE_DATE_COL = re.compile(
    r"(?:quarter\s+ended\s+)?(?:(\w+)\s+(\d{1,2}),?\s+(\d{4})|"
    r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4}))",
    re.IGNORECASE,
)
_RE_FQ_DIRECT = re.compile(
    r"\bQ([1-4])\s*FY(\d{2,4})\b", re.IGNORECASE
)
_RE_FOLDER_PERIOD = re.compile(
    r"FY(\d{2,4})[_\-]Q([1-4])", re.IGNORECASE
)

# Value parsing patterns — tried in order until one matches.
# Each entry: (pattern, unit, sign_multiplier)
_VALUE_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    # Explicit negative in parentheses with % e.g. "(6.6)%", "(6.6) %"
    (re.compile(r"^\s*\((\d[\d,]*(?:\.\d+)?)\)\s*%\s*$"), "%", -1.0),
    # Explicit negative in parentheses no unit e.g. "(6.6)"
    (re.compile(r"^\s*\((\d[\d,]*(?:\.\d+)?)\)\s*$"), "", -1.0),
    # Percentage e.g. "20.8%", "20.8 %"
    (re.compile(r"^\s*(-?\d[\d,]*(?:\.\d+)?)\s*%\s*$"), "%", 1.0),
    # USD billion e.g. "$3.8 Bn", "US$3.8 Bn", "$3.8 billion"
    (re.compile(r"^\s*(?:US)?\$\s*(-?\d[\d,]*(?:\.\d+)?)\s*(?:Bn|bn|billion)\s*$", re.IGNORECASE), "USD_bn", 1.0),
    # INR crore e.g. "₹18,000 crore", "18,000 crore"
    (re.compile(r"^\s*₹?\s*(-?\d[\d,]*(?:\.\d+)?)\s*(?:crore|Crore|cr)\s*$"), "INR_crore", 1.0),
    # Plain number with optional sign e.g. "5,076", "20.8", "-1.2"
    (re.compile(r"^\s*(-?\d[\d,]*(?:\.\d+)?)\s*$"), "", 1.0),
]

_RE_SEPARATOR = re.compile(r"^\|[\s\-:|]+\|")
_RE_TABLE_ROW = re.compile(r"^\|.+\|")

# ---------------------------------------------------------------------------
# Prose extraction patterns — used by the supplementary prose pass.
# ---------------------------------------------------------------------------

# Numbers with explicit units that are reliable to extract from prose.
_RE_PROSE_NUM = re.compile(
    r"""
    (?:US)?\$\s*(?P<usd_num>\d[\d,]*(?:\.\d+)?)\s*(?P<usd_unit>billion|Bn|bn|B\b|million|mn|Mn|M\b)
    |₹\s*(?P<inr_num>\d[\d,]*(?:\.\d+)?)\s*(?P<inr_unit>crore|cr|Crore)
    # Negative lookbehind (?<![%0-9]) prevents matching the '-22%' in '20%-22%'
    # (i.e. a dash that immediately follows a % or digit is a range separator, not a minus sign).
    |(?<![%0-9])(?P<pct_num>-?\d[\d,]*(?:\.\d+)?)\s*(?P<pct_unit>%)
    |(?P<bare_num>\d[\d,]*(?:\.\d+)?)\s*(?P<bare_unit>billion|Bn|bn|million|mn|Mn|crore|cr)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Only extract prose lines that mention at least one financial metric keyword.
_RE_METRIC_KW = re.compile(
    r"\b(revenue|tcv|total contract value|margin|profit|income|cash flow|ebitda|ebit|"
    r"attrition|headcount|employees|roe|return on equity|eps|earnings per share|"
    r"deal|booking|guidance|growth|yield|dividend|buyback|capex|"
    r"free cash|net cash|investment|client|account|utilization|utilisation)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# YAML front matter
# ---------------------------------------------------------------------------

def _extract_section_title(content: str) -> str:
    """Return the section_title from the YAML front matter, or empty string."""
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return ""
    close: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            close = i
            break
    if close is None:
        return ""
    try:
        parsed = yaml.safe_load("".join(lines[1:close]))
    except yaml.YAMLError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return str(parsed.get("section_title", "") or "")


# ---------------------------------------------------------------------------
# Period utilities
# ---------------------------------------------------------------------------

def _period_from_folder(path: Path) -> str:
    """Extract normalised period like 'Q1_FY26' from a folder name in the path.

    Example: 'FY26-Q1-fact-sheet' → 'Q1_FY26'.
    Example: 'FY26-Q32-earningscall' is treated as Q3_FY26 (typo in corpus).
    Returns empty string when no pattern matches.
    """
    for part in reversed(path.parts):
        m = _RE_FOLDER_PERIOD.search(part)
        if m:
            fy_raw = m.group(1)
            q_raw  = m.group(2)
            fy = int(fy_raw) if len(fy_raw) == 4 else 2000 + int(fy_raw)
            q = int(q_raw[0])  # handles 'Q32' → 3
            fy_suffix = fy % 100  # normalise to two-digit year: 2026 → 26
            return f"Q{q}_FY{fy_suffix}"
    return ""


def _period_from_column_header(header: str) -> str:
    """Try to extract a normalised period from a column header string.

    Handles:
      - 'Quarter ended Jun 30, 2025' → 'Q1_FY26'
      - 'Sep 30, 2025'              → 'Q2_FY26'
      - 'Q1 FY26'                   → 'Q1_FY26'
      - 'Mar 31, 2026'              → 'Q4_FY26'

    Returns empty string when no period can be determined.
    """
    header = header.strip()

    # Direct "Q1 FY26" or "Q1 FY2026" style.
    m = _RE_FQ_DIRECT.search(header)
    if m:
        q  = int(m.group(1))
        fy = int(m.group(2))
        if fy < 100:
            fy += 2000
        fy_suffix = fy % 100  # normalise to two-digit year: 2026 → 26
        return f"Q{q}_FY{fy_suffix}"

    # Month-day-year style.
    m = _RE_DATE_COL.search(header)
    if m:
        if m.group(1):  # named month e.g. "Jun 30, 2025"
            month_name = m.group(1)[:3].lower()
            month = _MONTH_NAMES.get(month_name)
            day   = int(m.group(2))
            year  = int(m.group(3))
        else:  # numeric date e.g. "30/06/2025"
            try:
                d1, d2, yr = int(m.group(4)), int(m.group(5)), int(m.group(6))
            except (TypeError, ValueError):
                return ""
            # Heuristic: if d1 > 12, d1 is day; otherwise assume MM/DD
            if d1 > 12:
                day, month, year = d1, d2, yr
            else:
                month, day, year = d1, d2, yr
            if year < 100:
                year += 2000

        if month is None:
            return ""
        key = (month, day)
        if key in _QUARTER_END_TO_FQ:
            q_str, fy_offset = _QUARTER_END_TO_FQ[key]
            fy = year + fy_offset
            fy_suffix = fy % 100  # normalise to two-digit year: 2026 → 26
            return f"{q_str}_FY{fy_suffix}"

    return ""


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------

def _parse_value(raw: str) -> tuple[float | None, str]:
    """Return (numeric_value, unit) for a raw cell string.

    Returns (None, '') for cells that cannot be parsed as numbers (e.g. '-',
    'N/A', empty, descriptive text).

    Example: '20.8%' → (20.8, '%')
    Example: '$3.8 Bn' → (3.8, 'USD_bn')
    Example: '(6.6)' → (-6.6, '')
    Example: '5,076' → (5076.0, '')
    Example: '-' → (None, '')
    """
    stripped = raw.strip()
    if not stripped or stripped in {"-", "—", "N/A", "n/a", "NA", "nil", "Nil"}:
        return None, ""

    for pattern, unit, multiplier in _VALUE_PATTERNS:
        m = pattern.match(stripped)
        if m:
            num_str = m.group(1).replace(",", "")
            try:
                value = float(num_str) * multiplier
                return value, unit
            except ValueError:
                continue

    return None, ""


def _detect_unit_from_context(context: str) -> str:
    """Guess the unit for bare numbers from surrounding table context.

    Example: a table heading containing 'US$ million' returns 'USD_mn'.
    Returns empty string when no unit hint is found.
    """
    ctx = context.lower()
    if "us$ million" in ctx or "usd million" in ctx or "in us$ mn" in ctx:
        return "USD_mn"
    if "us$ billion" in ctx or "usd billion" in ctx:
        return "USD_bn"
    if "₹ crore" in ctx or "inr crore" in ctx or "rs. crore" in ctx:
        return "INR_crore"
    if "₹ million" in ctx or "inr million" in ctx:
        return "INR_mn"
    if "%" in ctx:
        return "%"
    return ""


# ---------------------------------------------------------------------------
# Markdown table parser
# ---------------------------------------------------------------------------

def _split_table_row(line: str) -> list[str]:
    """Split a markdown table row into cell strings (stripped, no outer pipes).

    Example: '| Revenue | 5,076 | 4,894 |' → ['Revenue', '5,076', '4,894']
    """
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _find_tables(lines: list[str]) -> list[dict]:
    """Locate all markdown tables in the line list and return their raw data.

    Each returned dict has:
        heading      – nearest preceding heading or paragraph text
        unit_hint    – any unit hint found in surrounding text
        col_headers  – list[str] column header cells
        data_rows    – list[list[str]] data cell rows (separator row excluded)
        start_line   – 0-based index of first table line (for provenance)

    Tables are identified as consecutive blocks of '|…|' lines that include
    a separator line (|---|---|) as their second line.
    """
    tables: list[dict] = []
    i = 0
    last_heading = ""
    unit_hint_buffer = ""

    while i < len(lines):
        line = lines[i]

        # Track the nearest preceding heading.
        if re.match(r"^#{1,6}\s", line):
            last_heading = line.lstrip("#").strip()
            unit_hint_buffer = ""
        elif line.strip() and not _RE_TABLE_ROW.match(line):
            # Plain paragraph — may contain unit hints.
            unit_hint_buffer += " " + line

        if not _RE_TABLE_ROW.match(line):
            i += 1
            continue

        # Found a potential table start.
        table_start = i
        table_lines: list[str] = []
        while i < len(lines) and _RE_TABLE_ROW.match(lines[i]):
            table_lines.append(lines[i])
            i += 1

        if len(table_lines) < 2:
            continue  # need at least header + separator

        # Confirm the second line is a separator.
        if not _RE_SEPARATOR.match(table_lines[1]):
            continue

        col_headers = _split_table_row(table_lines[0])
        data_rows   = [_split_table_row(r) for r in table_lines[2:]]

        combined_context = last_heading + " " + unit_hint_buffer
        unit_hint = _detect_unit_from_context(combined_context)

        tables.append(
            {
                "heading": last_heading,
                "unit_hint": unit_hint,
                "col_headers": col_headers,
                "data_rows": data_rows,
                "start_line": table_start,
            }
        )

    return tables


# ---------------------------------------------------------------------------
# Prose / bullet-point extraction
# ---------------------------------------------------------------------------

def _parse_prose_match(m: re.Match) -> tuple[float, str, str] | None:
    """Return (numeric_value, unit, raw_text) from a _RE_PROSE_NUM match, or None."""
    g = m.groupdict()
    raw = m.group(0).strip()
    try:
        if g.get("usd_num") is not None:
            num = float(g["usd_num"].replace(",", ""))
            u = (g["usd_unit"] or "").lower()
            unit = "USD_bn" if u in ("billion", "bn", "b") else "USD_mn"
            return num, unit, raw
        if g.get("inr_num") is not None:
            num = float(g["inr_num"].replace(",", ""))
            return num, "INR_crore", raw
        if g.get("pct_num") is not None:
            num = float(g["pct_num"].replace(",", ""))
            return num, "%", raw
        if g.get("bare_num") is not None:
            num = float(g["bare_num"].replace(",", ""))
            u = (g["bare_unit"] or "").lower()
            if u in ("billion", "bn"):
                unit = "USD_bn"
            elif u in ("million", "mn"):
                unit = "USD_mn"
            elif u in ("crore", "cr"):
                unit = "INR_crore"
            else:
                return None
            return num, unit, raw
    except (ValueError, AttributeError):
        return None
    return None


def _extract_prose_facts(
    body_lines: list[str],
    folder_period: str,
    relative_path: str,
    document_name: str,
    source_folder: str,
    section_title: str,
) -> list[dict]:
    """Extract numerical facts from prose (non-table) lines.

    Targets bullet items and sentences that both:
      (a) mention at least one financial metric keyword, and
      (b) contain a number with an explicit unit (%, $Bn, $mn, ₹cr).

    Returns dicts in the same format as table extraction with
    column_label='prose' so callers can distinguish the source.
    """
    facts: list[dict] = []
    last_heading = ""
    in_table = False

    for line in body_lines:
        stripped = line.strip()

        # Track headings.
        if re.match(r"^#{1,6}\s", line):
            last_heading = stripped.lstrip("#").strip()
            in_table = False
            continue

        # Enter/exit table blocks — skip; handled by _find_tables.
        if _RE_TABLE_ROW.match(line):
            in_table = True
            continue
        if in_table and not _RE_TABLE_ROW.match(line):
            in_table = False

        if in_table or not stripped:
            continue

        # Only process lines with a financial metric keyword.
        if not _RE_METRIC_KW.search(stripped):
            continue

        # Extract all unit-bearing numbers from this line.
        for m in _RE_PROSE_NUM.finditer(stripped):
            parsed = _parse_prose_match(m)
            if parsed is None:
                continue
            num, unit, raw = parsed

            # Row label: stripped line without leading bullet marker (max 200 chars).
            row_label = re.sub(r"^[-*•+]\s*", "", stripped).strip()[:200]

            facts.append(
                {
                    "file_path":     relative_path,
                    "document_name": document_name,
                    "source_folder": source_folder,
                    "section_title": section_title,
                    "table_heading": last_heading,
                    "row_label":     row_label,
                    "column_label":  "prose",
                    "raw_value":     raw,
                    "value_numeric": num,
                    "unit":          unit,
                    "period":        folder_period,
                }
            )

    return facts


# ---------------------------------------------------------------------------
# Main extraction entry point
# ---------------------------------------------------------------------------

def extract_facts_from_file(file_path: Path, project_root: Path) -> list[dict]:
    """Parse all markdown tables in *file_path* and return a list of fact dicts.

    Each dict represents one table cell and contains:
        file_path       – project-relative POSIX path string
        document_name   – the immediate parent folder (or filename for flat sources)
        source_folder   – the grandparent folder name (the DATA_SOURCE directory name)
        section_title   – value of section_title from YAML front matter (may be '')
        table_heading   – nearest preceding heading before the table
        row_label       – left-most cell of the data row (the metric name)
        column_label    – column header for this cell
        raw_value       – the cell text exactly as written
        value_numeric   – parsed float or None
        unit            – detected unit string or ''
        period          – normalised period like 'Q1_FY26' or ''

    Two extraction passes are run:
      1. Table pass  – every cell of every markdown table (precise units/periods).
      2. Prose pass  – bullet items and metric-keyword sentences containing
                       numbers with explicit units (%, $Bn, $mn, ₹cr).
                       column_label is set to 'prose' for these rows.
    De-duplication removes prose facts whose (row_label, value, unit, period)
    tuple already exists from the table pass.

    Files with no tables AND no metric-keyword lines return [].
    Errors reading the file return [].

    Example:
        facts = extract_facts_from_file(
            Path('data/infosys.../FY26-Q1-fact-sheet/group_001.md'),
            PROJECT_ROOT,
        )
        facts[0]['row_label']  # e.g. 'Operating Margin%'
        facts[0]['period']     # e.g. 'Q1_FY26'
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    section_title = _extract_section_title(content)
    folder_period = _period_from_folder(file_path)

    # Remove YAML front matter before parsing tables.
    body = content
    lines = content.splitlines()
    if lines and lines[0].strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                body = "\n".join(lines[idx + 1:])
                break

    body_lines = body.splitlines()
    tables = _find_tables(body_lines)

    relative_path = file_path.relative_to(project_root).as_posix()
    # document_name: immediate parent folder if grouped (e.g. FY26-Q1-fact-sheet),
    # else the filename stem for flat sources.
    parent_name = file_path.parent.name
    document_name = (
        parent_name
        if parent_name not in {"clean-mds", "equal_or_less_than_10_pages"}
        else file_path.stem
    )
    source_folder = file_path.parents[1].name

    facts: list[dict] = []

    for table in tables:
        col_headers = table["col_headers"]
        unit_hint   = table["unit_hint"]
        heading     = table["heading"]

        # Pre-compute periods for each column.
        col_periods = [""] * len(col_headers)
        for ci, hdr in enumerate(col_headers):
            p = _period_from_column_header(hdr)
            col_periods[ci] = p if p else folder_period

        for data_row in table["data_rows"]:
            if not data_row:
                continue

            row_label = data_row[0].strip()
            # Skip rows that are effectively sub-headers or empty.
            if not row_label or row_label.startswith("**") and row_label.endswith("**"):
                # Strip bold markers if present but keep the label.
                row_label = row_label.strip("*").strip()
                if not row_label:
                    continue

            for ci in range(1, len(data_row)):
                if ci >= len(col_headers):
                    break
                raw = data_row[ci].strip()
                if not raw or raw in {"-", "—", ""}:
                    continue

                col_label = col_headers[ci].strip()
                # Skip columns that are growth-rate columns (e.g. "Growth% YoY")
                # unless the value itself is numeric — we still store them.

                numeric_val, unit = _parse_value(raw)
                # Fall back to context-based unit when cell has bare number.
                if numeric_val is not None and not unit:
                    rl_lower = row_label.lower()
                    # Rows whose label implies a percentage override the table context.
                    if (
                        row_label.endswith("%")
                        or any(
                            kw in rl_lower
                            for kw in [
                                "margin", "growth", "attrition", "utilization",
                                "utilisation", "mix", "contribution", "share",
                                "women", "onsite", "offshore",
                            ]
                        )
                    ):
                        unit = "%"
                    else:
                        unit = unit_hint

                period = col_periods[ci] if ci < len(col_periods) else folder_period

                facts.append(
                    {
                        "file_path": relative_path,
                        "document_name": document_name,
                        "source_folder": source_folder,
                        "section_title": section_title,
                        "table_heading": heading,
                        "row_label": row_label,
                        "column_label": col_label,
                        "raw_value": raw,
                        "value_numeric": numeric_val,
                        "unit": unit,
                        "period": period,
                    }
                )

    # Supplementary prose pass: captures numbers from bullet points and
    # metric-keyword sentences that don't appear in any table.
    prose_facts = _extract_prose_facts(
        body_lines, folder_period, relative_path,
        document_name, source_folder, section_title,
    )
    # De-duplicate prose facts that replicate values already found in tables
    # by checking (row_label[:60], value_numeric, unit, period) tuples.
    table_signatures: set[tuple] = {
        (f["row_label"][:60], f["value_numeric"], f["unit"], f["period"])
        for f in facts
        if f["value_numeric"] is not None
    }
    for pf in prose_facts:
        sig = (pf["row_label"][:60], pf["value_numeric"], pf["unit"], pf["period"])
        if sig not in table_signatures:
            facts.append(pf)
            table_signatures.add(sig)

    return facts
