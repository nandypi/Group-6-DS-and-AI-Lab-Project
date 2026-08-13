"""LLM-based question router for the Numeric Fidelity Layer.

Classifies each incoming question as either:
  FACT_DB  – numerical lookup or calculation answerable from the structured
             fact database (operating margin, revenue, TCV, attrition, EPS…)
  VECTOR   – descriptive, explanatory, or qualitative question that requires
             semantic retrieval from the Chroma vector store.

The router calls gpt-4o-mini once per question and expects a single-word reply.
When the reply is ambiguous, it defaults to VECTOR so the user always gets an
answer.

Example:
    from router import route_question
    route, reasoning = route_question("What was the average margin in FY26?", client)
    # route == 'FACT_DB'
"""

import os
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI

# Allow direct execution.
sys.path.insert(0, str(Path(__file__).resolve().parent))

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

_ROUTER_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """\
You are a routing classifier for a financial information system about Infosys.

You have access to two retrieval systems:

1. FACT_DB — A structured SQLite database of financial metrics extracted from
   Infosys quarterly fact sheets for Q1 FY26 through Q4 FY26. It contains:
   operating margin (%), revenue (USD mn, QoQ/YoY growth in reported and CC),
   large-deal TCV (USD bn) and net-new deal mix (%), EPS (basic and diluted),
   net profit (USD mn), free cash flow (USD mn), employee headcount, voluntary
   attrition (%), utilization rates, and segment/geography revenue mix (%).
   Use FACT_DB for questions that ask for: specific numbers, averages, totals,
   minimums, maximums, comparisons of financial metrics across quarters, or any
   calculation on those metrics.

2. VECTOR — A semantic search index over all Infosys financial documents:
   earnings call transcripts, press releases, analyst reports, NSE filings,
   news articles, and investor-relations documents. Use VECTOR for questions
   that ask for: explanations, reasons, strategies, qualitative analysis,
   management commentary, event descriptions, or topics not captured as
   structured metrics in the fact database.

Decision rules:
  - If the question contains "average", "total", "highest", "lowest", "minimum",
    "maximum", "how much", "what was the [metric]", or asks to compare specific
    numbers across time periods → FACT_DB.
  - If the question asks "why", "how does", "what is the strategy", "explain",
    "describe", "what factors", "what recognition", "who", "which partnership" → VECTOR.
  - When uncertain, default to VECTOR.

Reply with exactly one word: FACT_DB or VECTOR\
"""


def route_question(
    question: str,
    client: OpenAI,
) -> tuple[Literal["FACT_DB", "VECTOR"], str]:
    """Classify *question* and return (route, reasoning).

    Makes one gpt-4o-mini call.  The reasoning string is derived from the
    raw model reply and is useful for the workflow display in the frontend.

    Example:
        route, reasoning = route_question(
            "What was the average operating margin over Q1–Q4 FY26?", client
        )
        # ('FACT_DB', 'Numerical average over multiple quarters → FACT_DB')
    """
    response = client.chat.completions.create(
        model=_ROUTER_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": f"Route: \"{question}\""},
        ],
        temperature=0,
        max_tokens=10,
    )
    raw = (response.choices[0].message.content or "").strip().upper()

    if "FACT_DB" in raw:
        route: Literal["FACT_DB", "VECTOR"] = "FACT_DB"
    elif "VECTOR" in raw:
        route = "VECTOR"
    else:
        # Ambiguous reply → safe default.
        route = "VECTOR"

    reasoning = f"Model replied '{raw}' → routed to {route}"
    return route, reasoning


# ---------------------------------------------------------------------------
# CLI (quick test)
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in .env")
    client = OpenAI(api_key=api_key)

    test_questions = [
        "What was the average operating margin of Infosys over Q1–Q4 FY26?",
        "Which quarter in FY26 had the lowest operating margin?",
        "What large deal TCV did Infosys report in Q3 FY26?",
        "Why did Infosys's operating margin drop in Q3 FY26?",
        "What is the strategic rationale behind the Infosys–Intel partnership?",
        "What factors drove Infosys's revenue growth in Europe?",
        "What was Infosys's net profit for Q4 FY26?",
        "How does Infosys plan to expand its AI capabilities?",
    ]

    print("Router test\n" + "=" * 50)
    for q in test_questions:
        route, reasoning = route_question(q, client)
        print(f"[{route:7}]  {q}")
    print()


if __name__ == "__main__":
    main()
