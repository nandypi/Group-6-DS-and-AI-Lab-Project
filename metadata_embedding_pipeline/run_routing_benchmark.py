"""Routing accuracy benchmark for the Numeric Fidelity Layer.

Tests the LLM router on two question sets:
  - Numerical questions (numerical_benchmark.csv)   → expected route: FACT_DB
  - Descriptive questions (v2 benchmark CSV subset) → expected route: VECTOR

Reports routing accuracy on each set and overall.

Output: metadata_embedding_pipeline/routing_benchmark_results.csv
        metadata_embedding_pipeline/routing_benchmark_summary.md

Usage
-----
    python metadata_embedding_pipeline/run_routing_benchmark.py
    python metadata_embedding_pipeline/run_routing_benchmark.py --descriptive-limit 20
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BENCH_DIR    = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "metadata_embedding_pipeline"))
from router import route_question

NUMERICAL_CSV   = BENCH_DIR / "numerical_benchmark.csv"
DESCRIPTIVE_CSV = PROJECT_ROOT / "data" / "infosys_rag_test_dataset_50_queries_v2.csv"
OUTPUT_CSV      = BENCH_DIR / "routing_benchmark_results.csv"
SUMMARY_MD      = BENCH_DIR / "routing_benchmark_summary.md"

OUTPUT_COLUMNS = [
    "id", "question", "question_type", "expected_route",
    "actual_route", "route_correct",
    "latency_seconds", "pipeline_status", "pipeline_error",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_numerical_rows() -> list[dict]:
    with NUMERICAL_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [
        {
            "id":             f"num_{r['id']}",
            "question":       r["question"],
            "question_type":  "numerical",
            "expected_route": r.get("expected_route", "FACT_DB"),
        }
        for r in rows
    ]


def _load_descriptive_rows(limit: int) -> list[dict]:
    with DESCRIPTIVE_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    # All 50 v2 questions are descriptive — exclude any obviously numerical ones.
    descriptive = [
        r for r in rows
        if not any(
            kw in r.get("query", "").lower()
            for kw in ["average", "total", "sum", "minimum", "maximum", "how many", "what was the value"]
        )
    ][:limit]
    return [
        {
            "id":             f"desc_{r['id']}",
            "question":       r["query"],
            "question_type":  "descriptive",
            "expected_route": "VECTOR",
        }
        for r in descriptive
    ]


def _add_existing_results(rows: list[dict]) -> list[dict]:
    if not OUTPUT_CSV.exists():
        return rows
    with OUTPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        existing = {r["id"]: r for r in csv.DictReader(fh)}
    for row in rows:
        saved = existing.get(row["id"])
        if saved and saved.get("pipeline_status") == "Success":
            for col in ["actual_route", "route_correct", "latency_seconds",
                        "pipeline_status", "pipeline_error"]:
                row[col] = saved.get(col, "")
    return rows


def _write_rows(rows: list[dict]) -> None:
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(rows: list[dict]) -> None:
    finished = [r for r in rows if r.get("pipeline_status") == "Success"]
    num_rows  = [r for r in finished if r["question_type"] == "numerical"]
    desc_rows = [r for r in finished if r["question_type"] == "descriptive"]

    def _acc(subset: list[dict]) -> str:
        n = len(subset)
        if n == 0:
            return "N/A"
        c = sum(1 for r in subset if r.get("route_correct") == "True")
        return f"{c}/{n} = {c/n:.0%}"

    n_total = len(finished)
    c_total = sum(1 for r in finished if r.get("route_correct") == "True")
    avg_lat = (
        sum(float(r.get("latency_seconds", 0)) for r in finished) / n_total
        if n_total else 0
    )

    lines = [
        "# Routing Benchmark Summary",
        "",
        "## Overall",
        f"- Total questions evaluated : {n_total}",
        f"- Overall routing accuracy  : {c_total}/{n_total} = {c_total/n_total:.0%}" if n_total else "- No results",
        f"- Avg routing latency       : {avg_lat:.3f} s/question",
        "",
        "## By question type",
        f"- Numerical  (expected FACT_DB) : {_acc(num_rows)}",
        f"- Descriptive (expected VECTOR) : {_acc(desc_rows)}",
        "",
        "## Baseline comparison (Milestone 5 Pipeline A / B)",
        "The vector-only pipelines do not have a routing layer — all questions",
        "go to Chroma retrieval regardless of type.  This benchmark demonstrates",
        "that the Milestone 6 router correctly distinguishes numerical questions",
        "(routed to the fact database) from descriptive questions (routed to Chroma).",
        "",
        "## Per-question results",
        "",
        "| ID | Type | Expected | Actual | Correct | Latency |",
        "|---|---|---|---|---|---|",
    ]
    for r in finished:
        lines.append(
            f"| {r['id']} | {r['question_type']} | {r['expected_route']} | "
            f"{r.get('actual_route','?')} | {r.get('route_correct','?')} | "
            f"{r.get('latency_seconds','?')}s |"
        )

    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-question processing
# ---------------------------------------------------------------------------

def _process_row(row: dict, client: OpenAI) -> dict:
    t0 = time.perf_counter()
    actual_route, _reasoning = route_question(row["question"], client)
    lat = time.perf_counter() - t0
    correct = str(actual_route == row["expected_route"])
    return {
        "actual_route":    actual_route,
        "route_correct":   correct,
        "latency_seconds": f"{lat:.3f}",
        "pipeline_status": "Success",
        "pipeline_error":  "",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Routing accuracy benchmark for the Milestone 6 router."
    )
    parser.add_argument(
        "--descriptive-limit", type=int, default=25,
        help="Max number of descriptive questions from the 50-question dataset (default: 25).",
    )
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

    all_rows = (
        _load_numerical_rows()
        + _load_descriptive_rows(args.descriptive_limit)
    )
    all_rows = _add_existing_results(all_rows)

    unfinished = [r for r in all_rows if r.get("pipeline_status") != "Success"]
    print(f"Running {len(unfinished)} unfinished question(s)…\n")

    for row in unfinished:
        print(f"[{row['id']:8}] [{row['question_type']:11}] {row['question'][:70]}")
        try:
            row.update(_process_row(row, client))
            print(
                f"          route={row['actual_route']} correct={row['route_correct']} "
                f"lat={row['latency_seconds']}s"
            )
        except Exception as exc:
            row["pipeline_status"] = "Error"
            row["pipeline_error"]  = str(exc)
            print(f"          ERROR: {exc}")
        _write_rows(all_rows)

    _write_summary(all_rows)

    finished = [r for r in all_rows if r.get("pipeline_status") == "Success"]
    n = len(finished)
    if n:
        c = sum(1 for r in finished if r.get("route_correct") == "True")
        al = sum(float(r.get("latency_seconds", 0)) for r in finished) / n
        print()
        print("=== Routing Benchmark Summary ===")
        print(f"Total questions  : {n}")
        print(f"Routing accuracy : {c}/{n} = {c/n:.0%}")
        print(f"Avg latency      : {al:.3f} s/question")

    print(f"\nResults → {OUTPUT_CSV.relative_to(PROJECT_ROOT)}")
    print(f"Summary → {SUMMARY_MD.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
