"""Answer numerical questions from the SQLite fact database.

Pipeline:
  1. Get the schema description + sample rows.
  2. Call gpt-4o-mini to generate a safe SELECT query.
  3. Execute the query on a read-only connection.
  4. Call gpt-4o-mini again to convert the rows into a natural-language answer
     with provenance citations.

Safety: the database is opened in read-only URI mode so no DML can run even
if the LLM generates an INSERT/UPDATE/DELETE by mistake.  An additional
keyword check refuses to execute any statement that does not start with SELECT.

Example:
    result = answer_from_fact_db(
        "What was the average operating margin over Q1–Q4 FY26?", DB_PATH, client
    )
    print(result["answer"])   # 'The average operating margin was 20.3%.'
    print(result["citations"]) # ['data/.../FY26-Q1-fact-sheet/group_001.md', …]
"""

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fact_database import DB_PATH, get_schema_description

_SQL_MODEL    = "gpt-4o-mini"
_ANSWER_MODEL = "gpt-4o-mini"

_MAX_RESULT_ROWS = 200   # cap rows returned to the answer LLM
_MAX_SAMPLE_ROWS_IN_SCHEMA = 10


# ---------------------------------------------------------------------------
# SQL generation
# ---------------------------------------------------------------------------

_SQL_SYSTEM = """\
You are a SQL expert for a financial facts SQLite database about Infosys.
The schema description includes a METRIC LOOKUP section with exact WHERE clauses for each
key metric. Always consult and use those exact patterns.

Hard rules:
  - Only SELECT statements are allowed. Never generate INSERT, UPDATE, DELETE, DROP, or DDL.
  - Always include file_path in every SELECT for citations.
  - Always WHERE value_numeric IS NOT NULL and (period != '' when period matters).
  - Return ONLY the raw SQL — no markdown fences, no explanation.

Critical data-quality rules:
  - The schema has a METRIC LOOKUP section — always read and use those exact WHERE patterns.
  - For REPORTED operating margin: add column_label NOT LIKE '%Growth%'
    AND column_label NOT LIKE '%YoY%' AND column_label NOT LIKE '%QoQ%'
    AND column_label NOT LIKE '%Adjusted%' AND column_label NOT LIKE '%non-IFRS%'
    AND value_numeric BETWEEN 15 AND 25.
  - For TCV (large deal): use column_label = 'prose' and unit = 'USD_bn'
    AND value_numeric < 6 (quarterly TCV is always < $6Bn; full-year $15Bn and H1 $6.9Bn
    also appear in prose and must be excluded with this guard).
  - For net-new %: add value_numeric BETWEEN 45 AND 70 (outlier 100% values and regional 80%
    values for EURS/segments also exist and must be excluded with this guard).
  - For revenue: exact row_label is 'Revenues' (plural); add unit = 'USD_mn'.
  - For EPS: use row_label = 'Basic EPS ($)' and unit = 'USD_mn'.
  - For net profit in USD: add unit = 'USD_mn' and document_name LIKE '%fact-sheet%'.\
"""


def _generate_sql(question: str, schema_desc: str, client: OpenAI) -> str:
    """Ask the LLM to produce a SELECT statement for *question*.

    Returns the raw SQL string (may still be malformed — caller validates).
    """
    response = client.chat.completions.create(
        model=_SQL_MODEL,
        messages=[
            {"role": "system", "content": _SQL_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Schema:\n{schema_desc}\n\n"
                    f"Question: {question}\n\n"
                    "SQL:"
                ),
            },
        ],
        temperature=0,
        max_tokens=400,
    )
    raw = (response.choices[0].message.content or "").strip()
    # Strip markdown code fences if the model included them.
    raw = re.sub(r"^```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _is_safe_sql(sql: str) -> bool:
    """Return True only if *sql* is a SELECT statement with no write keywords.

    Example: 'SELECT AVG(value_numeric) FROM facts WHERE …' → True
    Example: 'DROP TABLE facts' → False
    """
    normalized = sql.strip().upper()
    if not normalized.startswith("SELECT"):
        return False
    forbidden = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|DETACH|PRAGMA)\b"
    )
    return not forbidden.search(normalized)


# ---------------------------------------------------------------------------
# Safe SQL execution
# ---------------------------------------------------------------------------

def execute_safe_sql(sql: str) -> tuple[list[dict], str]:
    """Open the DB read-only and execute *sql*.

    Returns (rows, error_message).  On success error_message is ''.
    On failure rows is [] and error_message describes the problem.

    If the LLM returns multiple statements separated by ';', only the first
    SELECT is executed to avoid the SQLite "one statement at a time" error.
    """
    # Extract only the first non-empty statement (LLMs sometimes emit two).
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    sql = statements[0] if statements else sql

    if not _is_safe_sql(sql):
        return [], f"Unsafe SQL rejected: statement does not start with SELECT or contains forbidden keywords."

    uri = f"file:{DB_PATH}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = [dict(row) for row in cursor.fetchmany(_MAX_RESULT_ROWS)]
        conn.close()
        return rows, ""
    except sqlite3.OperationalError as exc:
        return [], f"SQL error: {exc}"
    except Exception as exc:
        return [], f"Unexpected error executing SQL: {exc}"


# ---------------------------------------------------------------------------
# Natural-language answer generation
# ---------------------------------------------------------------------------

_ANSWER_SYSTEM = """\
You are a precise financial analyst answering a question about Infosys.
You are given the question, the SQL query used to retrieve data, and the query results.
Write a concise, accurate answer using the retrieved data.
Include specific numbers and mention the quarters or time periods.
If the results are empty, say the information was not found in the fact database.
Do not add information beyond what the query results contain.\
"""


def _generate_answer(
    question: str,
    sql: str,
    rows: list[dict],
    client: OpenAI,
) -> str:
    """Convert SQL result rows into a natural-language answer."""
    # Limit result size for the prompt.
    rows_text = json.dumps(rows[:50], indent=2, default=str)

    response = client.chat.completions.create(
        model=_ANSWER_MODEL,
        messages=[
            {"role": "system", "content": _ANSWER_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"SQL used:\n{sql}\n\n"
                    f"Query results ({len(rows)} row(s)):\n{rows_text}\n\n"
                    "Answer:"
                ),
            },
        ],
        temperature=0,
        max_tokens=500,
    )
    return (response.choices[0].message.content or "").strip()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def answer_from_fact_db(
    question: str,
    client: OpenAI,
) -> dict[str, Any]:
    """Run the full fact-database QA pipeline for one question.

    Returns a dict with keys:
        answer      str   – natural-language answer (or error message)
        sql         str   – the generated SELECT statement
        rows        list  – raw result rows (for inspection / debugging)
        citations   list  – deduplicated file_path strings from the result rows
        error       str   – non-empty string when something failed
        row_count   int   – number of rows returned by SQL
    """
    if not DB_PATH.exists():
        return {
            "answer": "The fact database has not been built yet. Run fact_database.py first.",
            "sql": "",
            "rows": [],
            "citations": [],
            "error": "facts.db not found",
            "row_count": 0,
        }

    # Step 1: get schema for the LLM.
    conn = sqlite3.connect(str(DB_PATH))
    try:
        schema_desc = get_schema_description(conn)
    finally:
        conn.close()

    # Step 2: generate SQL.
    try:
        sql = _generate_sql(question, schema_desc, client)
    except Exception as exc:
        return {
            "answer": "Failed to generate SQL query.",
            "sql": "",
            "rows": [],
            "citations": [],
            "error": str(exc),
            "row_count": 0,
        }

    # Step 3: execute safely.
    rows, sql_error = execute_safe_sql(sql)
    if sql_error:
        # Try a fallback: ask the LLM to fix the SQL.
        try:
            fix_prompt = (
                f"The following SQL caused an error: {sql_error}\n"
                f"Original SQL: {sql}\n"
                f"Schema:\n{schema_desc}\n"
                f"Question: {question}\n"
                "Please write a corrected SELECT query."
            )
            response = client.chat.completions.create(
                model=_SQL_MODEL,
                messages=[
                    {"role": "system", "content": _SQL_SYSTEM},
                    {"role": "user",   "content": fix_prompt},
                ],
                temperature=0,
                max_tokens=400,
            )
            sql2 = (response.choices[0].message.content or "").strip()
            sql2 = re.sub(r"^```(?:sql)?\s*", "", sql2, flags=re.IGNORECASE)
            sql2 = re.sub(r"\s*```$", "", sql2)
            sql2 = sql2.strip()
            rows, sql_error2 = execute_safe_sql(sql2)
            if not sql_error2:
                sql = sql2  # use the corrected query
            else:
                return {
                    "answer": f"Could not retrieve data. SQL error: {sql_error}",
                    "sql": sql,
                    "rows": [],
                    "citations": [],
                    "error": sql_error,
                    "row_count": 0,
                }
        except Exception as exc:
            return {
                "answer": f"Could not retrieve data. SQL error: {sql_error}",
                "sql": sql,
                "rows": [],
                "citations": [],
                "error": str(exc),
                "row_count": 0,
            }

    # Step 4: extract citations from results.
    citations: list[str] = []
    seen: set[str] = set()
    for row in rows:
        fp = row.get("file_path", "")
        if fp and fp not in seen:
            citations.append(fp)
            seen.add(fp)

    # Step 5: generate natural-language answer.
    if not rows:
        answer = (
            "No matching financial data was found in the fact database for this question. "
            "The metric or time period may not be available in the extracted fact table."
        )
    else:
        try:
            answer = _generate_answer(question, sql, rows, client)
        except Exception as exc:
            answer = f"Data retrieved but answer generation failed: {exc}"

    return {
        "answer": answer,
        "sql": sql,
        "rows": rows,
        "citations": citations,
        "error": "",
        "row_count": len(rows),
    }
