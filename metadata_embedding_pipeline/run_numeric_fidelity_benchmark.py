"""Numeric Fidelity Layer benchmark.

Evaluates the full fact-database pipeline on 15 numerical questions:
  1. Routing accuracy  — did the router correctly classify as FACT_DB?
  2. SQL execution     — did the generated SQL run without errors?
  3. Numerical match   — does the answer contain the expected numeric value?

Input:  metadata_embedding_pipeline/numerical_benchmark.csv
Output: metadata_embedding_pipeline/numeric_fidelity_results.csv
        metadata_embedding_pipeline/numeric_fidelity_summary.md

Usage
-----
    python metadata_embedding_pipeline/run_numeric_fidelity_benchmark.py
    python metadata_embedding_pipeline/run_numeric_fidelity_benchmark.py --limit 5
"""

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BENCH_DIR    = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "metadata_embedding_pipeline"))
from router    import route_question
from fact_query import answer_from_fact_db

INPUT_CSV  = BENCH_DIR / "numerical_benchmark.csv"
OUTPUT_CSV = BENCH_DIR / "numeric_fidelity_results.csv"
SUMMARY_MD = BENCH_DIR / "numeric_fidelity_summary.md"

SOURCE_COLUMNS = [
    "id", "question", "expected_answer", "expected_answer_numeric",
    "expected_route", "relevant_metric", "relevant_periods", "notes",
]
RESULT_COLUMNS = [
    "actual_route",
    "route_correct",
    "sql_generated",
    "sql_error",
    "row_count",
    "llm_answer",
    "numeric_match",
    "citations",
    "routing_latency_seconds",
    "query_latency_seconds",
    "overall_latency_seconds",
    "pipeline_status",
    "pipeline_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contains_expected_number(answer: str, expected_numeric: str, tolerance: float = 0.05) -> bool:
    """Return True if *answer* contains a number within *tolerance* of *expected_numeric*.

    Also returns True on an exact substring match of the expected_answer text.

    Example: expected=20.275, answer='20.3%' → True (within 5% relative tolerance)
    Example: expected=4.8, answer='$4.8 billion' → True
    """
    if not expected_numeric:
        return False
    try:
        expected = float(expected_numeric)
    except ValueError:
        return False

    # Find all numbers in the answer string.
    numbers_in_answer = re.findall(r"-?\d[\d,]*(?:\.\d+)?", answer.replace(",", ""))
    for num_str in numbers_in_answer:
        try:
            num = float(num_str.replace(",", ""))
        except ValueError:
            continue
        if expected == 0:
            if abs(num) < 1e-6:
                return True
        else:
            relative_diff = abs(num - expected) / abs(expected)
            if relative_diff <= tolerance:
                return True

    return False


def _read_input() -> list[dict]:
    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _add_existing_results(rows: list[dict]) -> list[dict]:
    if not OUTPUT_CSV.exists():
        return rows
    with OUTPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        existing = {r["id"]: r for r in csv.DictReader(fh)}
    for row in rows:
        saved = existing.get(row["id"])
        if saved and saved.get("pipeline_status") == "Success":
            for col in RESULT_COLUMNS:
                row[col] = saved.get(col, "")
    return rows


def _write_rows(rows: list[dict]) -> None:
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(rows: list[dict]) -> None:
    finished = [r for r in rows if r.get("pipeline_status") == "Success"]
    n = len(finished)
    if n == 0:
        SUMMARY_MD.write_text("No completed rows yet.\n", encoding="utf-8")
        return

    route_correct  = sum(1 for r in finished if r.get("route_correct")  == "True")
    sql_ok         = sum(1 for r in finished if r.get("sql_error", "")  == "")
    numeric_match  = sum(1 for r in finished if r.get("numeric_match")  == "True")
    avg_lat        = sum(float(r.get("overall_latency_seconds", 0)) for r in finished) / n

    lines = [
        "# Numeric Fidelity Layer Benchmark Summary",
        "",
        f"- Questions evaluated : {n} / {len(rows)}",
        f"- Routing accuracy    : {route_correct}/{n} = {route_correct/n:.0%}",
        f"  (questions correctly routed to FACT_DB)",
        f"- SQL success rate    : {sql_ok}/{n} = {sql_ok/n:.0%}",
        f"- Numerical match     : {numeric_match}/{n} = {numeric_match/n:.0%}",
        f"  (answer within 5% of expected numeric value)",
        f"- Avg latency         : {avg_lat:.3f} s/question",
        "",
        "## Per-question results",
        "",
        "| ID | Question (abbrev.) | Expected | Route OK | SQL OK | Num match |",
        "|---|---|---|---|---|---|",
    ]
    for r in finished:
        q_short = r["question"][:60] + ("…" if len(r["question"]) > 60 else "")
        lines.append(
            f"| {r['id']} | {q_short} | {r['expected_answer']} | "
            f"{r.get('route_correct','?')} | "
            f"{'Yes' if not r.get('sql_error') else 'No'} | "
            f"{r.get('numeric_match','?')} |"
        )

    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-question processing
# ---------------------------------------------------------------------------

def _process_question(row: dict, client: OpenAI) -> dict:
    t0 = time.perf_counter()

    # Step 1: route.
    t_route = time.perf_counter()
    actual_route, _reasoning = route_question(row["question"], client)
    routing_lat = time.perf_counter() - t_route

    route_correct = str(actual_route == row.get("expected_route", "FACT_DB").strip())

    # Step 2: query fact DB.
    t_query = time.perf_counter()
    result  = answer_from_fact_db(row["question"], client)
    query_lat = time.perf_counter() - t_query

    # Step 3: evaluate numerical match.
    numeric_match = _contains_expected_number(
        result["answer"], row.get("expected_answer_numeric", "")
    )

    return {
        "actual_route":               actual_route,
        "route_correct":              route_correct,
        "sql_generated":              result.get("sql", ""),
        "sql_error":                  result.get("error", ""),
        "row_count":                  str(result.get("row_count", 0)),
        "llm_answer":                 result.get("answer", ""),
        "numeric_match":              str(numeric_match),
        "citations":                  " | ".join(result.get("citations", [])),
        "routing_latency_seconds":    f"{routing_lat:.3f}",
        "query_latency_seconds":      f"{query_lat:.3f}",
        "overall_latency_seconds":    f"{time.perf_counter() - t0:.3f}",
        "pipeline_status":            "Success",
        "pipeline_error":             "",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Numeric Fidelity Layer benchmark on the 15-question numerical dataset."
    )
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of unfinished questions to process.")
    parser.add_argument("--start", type=int, default=1,
                        help="1-based question number to begin from (default: 1).")
    return parser.parse_args()


def main() -> None:
    args = _read_arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in .env")
    client = OpenAI(api_key=api_key)

    rows = _add_existing_results(_read_input())
    start_idx = args.start - 1
    unfinished = [
        r for r in rows[start_idx:]
        if r.get("pipeline_status") != "Success"
    ]
    if args.limit:
        unfinished = unfinished[: args.limit]

    if not unfinished:
        print("All questions already completed.")
        _write_summary(rows)
        return

    print(f"Running {len(unfinished)} question(s)…\n")
    for row in unfinished:
        print(f"[{row['id']:2}] {row['question']}")
        try:
            row.update(_process_question(row, client))
            print(
                f"     route={row['actual_route']} correct={row['route_correct']} "
                f"num_match={row['numeric_match']} lat={row['overall_latency_seconds']}s"
            )
        except Exception as exc:
            row["pipeline_status"] = "Error"
            row["pipeline_error"]  = str(exc)
            print(f"     ERROR: {exc}")
        _write_rows(rows)

    _write_summary(rows)

    finished = [r for r in rows if r.get("pipeline_status") == "Success"]
    n = len(finished)
    if n:
        rc = sum(1 for r in finished if r.get("route_correct")  == "True")
        nm = sum(1 for r in finished if r.get("numeric_match") == "True")
        se = sum(1 for r in finished if not r.get("sql_error"))
        al = sum(float(r.get("overall_latency_seconds", 0)) for r in finished) / n
        print()
        print("=== Numeric Fidelity Benchmark Summary ===")
        print(f"Questions   : {n}")
        print(f"Routing OK  : {rc}/{n} = {rc/n:.0%}")
        print(f"SQL success : {se}/{n} = {se/n:.0%}")
        print(f"Numeric OK  : {nm}/{n} = {nm/n:.0%}")
        print(f"Avg latency : {al:.3f} s/question")
    print(f"\nResults → {OUTPUT_CSV.relative_to(PROJECT_ROOT)}")
    print(f"Summary → {SUMMARY_MD.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
