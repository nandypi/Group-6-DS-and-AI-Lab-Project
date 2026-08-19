# FinQuery — Developer Guide

Group 6 — Data Science and AI Lab (T2 - 2026)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Repository Structure](#3-repository-structure)
4. [Environment Configuration](#4-environment-configuration)
5. [Setting Up the Python Environment](#5-setting-up-the-python-environment)
6. [Rebuilding the Pipeline from Scratch](#6-rebuilding-the-pipeline-from-scratch)
7. [Running the Application Locally](#7-running-the-application-locally)
8. [Running with Docker Compose](#8-running-with-docker-compose)
9. [Script Reference](#9-script-reference)
10. [Configuration Reference](#10-configuration-reference)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Overview

FinQuery is a financial question-answering application over Infosys public disclosures. It consists of two services:

- **FastAPI backend** (`api.py`) — authenticates users, routes questions, executes retrieval, and calls GPT-4o-mini to generate answers.
- **Streamlit frontend** (`streamlit_app.py`) — browser-based chat interface that communicates with the backend.

Every incoming question is automatically routed to one of two pipelines:

| Route | Trigger | Mechanism |
| --- | --- | --- |
| `FACT_DB` | Numerical question (revenue, margin, EPS, attrition, TCV) | LLM-generated SQL → SQLite facts database → GPT-4o-mini answer |
| `VECTOR` | Descriptive / qualitative question | Hybrid retrieval (vector + BM25) with Reciprocal Rank Fusion → top-3 document bodies → GPT-4o-mini answer |

Both pipelines return a 4-step workflow trace, the generated answer, and source citations.

---

## 2. Prerequisites

### Local setup

| Requirement | Version |
| --- | --- |
| Python | 3.11 or later |
| pip | any recent version |
| OpenAI API key | required for embeddings and GPT-4o-mini calls |

### Docker setup

| Requirement | Notes |
| --- | --- |
| Docker Engine | v24+ with the `docker compose` plugin |
| OpenAI API key | passed via `.env` file |

No other cloud accounts or services are required.

---

## 3. Repository Structure

```text
Group-6-DS-and-AI-Lab-Project/
│
├── api.py                          # FastAPI backend
├── streamlit_app.py                # Streamlit frontend
├── Dockerfile                      # Single-stage Docker image
├── docker-compose.yml              # Orchestrates api (:8000) + streamlit (:8501)
├── .env                            # Secrets — create this locally, never commit
├── .env.example                    # Template for .env
├── requirements.txt                # All Python dependencies (single file)
│
├── metadata_embedding_pipeline/
│   ├── metadata_embedding_utils.py          # Shared constants and helpers
│   ├── metadata_embedding_pipeline.py       # ChromaDB indexing script
│   ├── metadata_embedding_benchmark.py      # Vector-only retrieval benchmark
│   ├── metadata_embedding_reranker_benchmark.py  # Cross-encoder reranker benchmark
│   ├── hybrid_bm25_benchmark.py             # Hybrid BM25 + vector benchmark (production)
│   ├── router.py                            # FACT_DB / VECTOR classifier
│   ├── fact_extractor.py                    # Extracts structured facts from Markdown
│   ├── fact_database.py                     # Builds and queries the SQLite fact DB
│   ├── fact_query.py                        # SQL generation + NL answer generation
│   ├── run_routing_benchmark.py             # Routing accuracy benchmark
│   ├── run_numeric_fidelity_benchmark.py    # Numeric fidelity benchmark
│   ├── sample_questions.csv                 # 29-question evaluation set
│   ├── facts.db                             # Pre-built SQLite fact database (not in Git)
│   └── chroma_db/                           # Pre-built ChromaDB vector store (not in Git)
│
├── data/
│   ├── infosys_earning_calls_press_conf_fact_sheets_results/
│   │   └── cleaned_section_files_1500_2500_v2/   # Source for fact DB + ChromaDB
│   ├── nse_files_final/                           # NSE filing Markdown files
│   ├── trendlyne/clean-mds/                       # Trendlyne research Markdown files
│   ├── yfinance/clean-mds/                        # yfinance data Markdown files
│   ├── infosys_rag_test_dataset_50_queries_v2.csv # 50-question retrieval benchmark input
│   └── ...                                        # Benchmark output CSVs
│
└── datapreparation/                # Data collection and preprocessing scripts (not covered here)
```

### Data files not tracked by Git

Three items must be present before running the application. Download them from the shared drive or rebuild from scratch (see Section 6):

**Download link:** [Google Drive — FinQuery data files](https://drive.google.com/drive/folders/1ZA-gJ2IrROZq0PpI_CuVM5A_VSQB9fbE?usp=sharing)

| Path | Approximate size | Description |
| --- | --- | --- |
| `metadata_embedding_pipeline/facts.db` | ~88 MB | SQLite fact database with 2,500+ financial facts |
| `metadata_embedding_pipeline/chroma_db/` | ~42 MB | ChromaDB vector store (1,875 embedded documents) |
| `data/` | ~205 MB | Markdown source files read by the VECTOR pipeline |

---

## 4. Environment Configuration

Create a `.env` file in the repository root. Use `.env.example` as a template:

```dotenv
OPENAI_API_KEY=sk-proj-...         # Required — used for embeddings and GPT-4o-mini
APP_USERNAME=admin                 # Login username shown on the Streamlit UI
APP_PASSWORD=finquery2026          # Login password
JWT_SECRET_KEY=change-me-in-prod  # Any long random string; change before exposing publicly
APP_RATE_LIMIT_PER_HOUR=30        # Max queries per user per hour (default: 20)
```

**Important:** Never commit `.env` to version control. It is listed in `.gitignore`.

`JWT_SECRET_KEY` is optional — if omitted, the backend generates a random key on each startup, which invalidates all existing tokens on restart. Set it explicitly for persistent sessions.

---

## 5. Setting Up the Python Environment

This section covers the local Python setup. Skip to Section 8 if you are using Docker.

### Step 1 — Create a virtual environment

```bash
python3 -m venv .venv
```

### Step 2 — Activate the virtual environment

On Linux / macOS:

```bash
source .venv/bin/activate
```

On Windows (Command Prompt):

```bat
.venv\Scripts\activate.bat
```

On Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

The prompt will change to show `(.venv)` when the environment is active. All subsequent `pip` and `python3` commands must be run with the environment active.

### Step 3 — Install all project dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` is configured for CPU-only machines. It includes `--extra-index-url https://download.pytorch.org/whl/cpu` and pins `torch==2.7.0+cpu`, so a single command installs everything — no separate PyTorch step is required.

### Notes on specific packages

- **`rank-bm25`** — required by `hybrid_bm25_benchmark.py` for the BM25 keyword index used in production retrieval.
- **`chromadb`** — requires a writable path for internal state even when performing read-only queries. See Troubleshooting (Section 11).
- **`torch` / `transformers` / `FlagEmbedding`** — only needed for the cross-encoder reranker benchmark (`metadata_embedding_reranker_benchmark.py`). The production pipeline does not invoke the cross-encoder at runtime.
- **`ragas` / `langchain`** — only needed for the RAGAS answer-quality evaluation notebook. Not required to run the application.

---

## 6. Rebuilding the Pipeline from Scratch

This section describes how to reconstruct all data artifacts from the cleaned Markdown files. **Data collection itself is not covered here.** Start from this section if you have the `data/` directory already populated with cleaned Markdown.

The rebuild has three stages that must be run in order:

```text
Stage 1 — ChromaDB indexing
Stage 2 — SQLite fact database build
Stage 3 — Verification (optional)
```

### Stage 1 — Build the ChromaDB vector index

The vector index embeds only the YAML front-matter block of each Markdown file (not the full body). This metadata-only approach was established in Milestone 5 and yields significantly better retrieval quality than full-document embedding.

**Source directories indexed (five total):**

| Directory | Contents |
| --- | --- |
| `data/yfinance/clean-mds` | yfinance market data documents |
| `data/trendlyne/clean-mds` | Trendlyne brokerage reports |
| `data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500_v2` | Infosys IR documents (earnings calls, fact sheets, press releases) |
| `data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages` | Short NSE filings |
| `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500_v2` | Long NSE filings (sectioned) |

**Run:**

```bash
python3 metadata_embedding_pipeline/metadata_embedding_pipeline.py
```

This script:

1. Reads all `.md` files from the five source directories.
2. Extracts only the YAML front-matter block from each file.
3. Embeds the YAML text with `text-embedding-3-small` (batch size 20, max 8,191 tokens).
4. Stores each document in the `metadata_embeddings` Chroma collection at `metadata_embedding_pipeline/chroma_db/`.

To skip files already present in the collection (resume an interrupted run):

```bash
python3 metadata_embedding_pipeline/metadata_embedding_pipeline.py --skip-existing
```

**Expected output:** `metadata_embedding_pipeline/chroma_db/` with 1,875 documents.

**Cost:** Approximately 1,875 × ~300 tokens ÷ 1,000,000 × $0.02 ≈ $0.01 USD.

---

### Stage 2 — Build the SQLite fact database

The fact database stores structured financial figures extracted from Infosys IR documents only. It is restricted to one authoritative source to avoid unit confusion between USD-denominated IR reports and INR-denominated NSE annual reports.

**Source directory:**

```text
data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500_v2
```

**Run (first time):**

```bash
python3 metadata_embedding_pipeline/fact_database.py
```

**Run (to rebuild after changing extraction logic):**

```bash
python3 metadata_embedding_pipeline/fact_database.py --rebuild
```

The `--rebuild` flag drops and recreates the `facts` table before inserting. Use it whenever `fact_extractor.py` logic changes.

**What the script does:**

1. Reads every `.md` file in the IR source directory.
2. Calls `fact_extractor.py` on each file to extract both table-cell facts and prose-embedded metric sentences.
3. Parses each raw value for a numeric component, unit, and normalised period (e.g., `Q1_FY26`).
4. Inserts all rows into `metadata_embedding_pipeline/facts.db`.

**Expected output:** `metadata_embedding_pipeline/facts.db` (~88 MB, 2,500+ rows).

This step does not call any OpenAI API and has no cost.

---

### Stage 3 — Verify the rebuild (optional)

Run the routing benchmark to confirm the router is working:

```bash
python3 metadata_embedding_pipeline/run_routing_benchmark.py
```

Run the numeric fidelity benchmark to confirm the fact database is correct:

```bash
python3 metadata_embedding_pipeline/run_numeric_fidelity_benchmark.py
```

Expected results: 40/40 routing accuracy, 15/15 numeric fidelity within 5% margin.

---

## 7. Running the Application Locally

Requires Python 3.11+, an active virtual environment (Section 5), and a `.env` file in the repository root (Section 4).

### Terminal 1 — Start the FastAPI backend

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

The API starts at `http://localhost:8000`. The interactive API documentation is available at `http://localhost:8000/docs`.

On the first VECTOR query after startup, the BM25 keyword index is built from the ChromaDB corpus (~3 seconds one-time cost, logged as `BM25 index ready (1875 documents, 2.8s)`). All subsequent queries use the cached index.

### Terminal 2 — Start the Streamlit frontend

```bash
streamlit run streamlit_app.py --server.port 8501 --server.headless true
```

The UI is available at `http://localhost:8501`.

Log in with the `APP_USERNAME` and `APP_PASSWORD` from your `.env` file.

### Running in the background

```bash
# API
nohup uvicorn api:app --host 0.0.0.0 --port 8000 > /tmp/finquery_api.log 2>&1 &

# Streamlit
nohup streamlit run streamlit_app.py --server.port 8501 --server.headless true \
  > /tmp/finquery_ui.log 2>&1 &
```

Check logs:

```bash
tail -f /tmp/finquery_api.log
tail -f /tmp/finquery_ui.log
```

### Stopping the application

**If running in the foreground** (no `nohup`): press `Ctrl+C` in each terminal to stop the respective process.

**If running in the background** (with `nohup`):

```bash
# Stop the API (port 8000)
pkill -f "uvicorn api:app"

# Stop Streamlit (port 8501)
pkill -f "streamlit run streamlit_app.py"
```

To confirm both processes have stopped:

```bash
lsof -i :8000
lsof -i :8501
```

---

## 8. Running with Docker Compose

No Python installation is needed on the host when using Docker.

### Step 1 — Clone the repository

```bash
git clone https://github.com/nandypi/Group-6-DS-and-AI-Lab-Project.git
cd Group-6-DS-and-AI-Lab-Project
```

### Step 2 — Create the `.env` file

```dotenv
OPENAI_API_KEY=sk-proj-...
APP_USERNAME=admin
APP_PASSWORD=finquery2026
JWT_SECRET_KEY=change-me-in-prod
APP_RATE_LIMIT_PER_HOUR=30
```

### Step 3 — Place the pre-built data files

Download the pre-built files from the shared drive:

**Download link:** [Google Drive — FinQuery data files](https://drive.google.com/drive/folders/1ZA-gJ2IrROZq0PpI_CuVM5A_VSQB9fbE?usp=sharing)

Copy the following into the repository root after downloading:

- `metadata_embedding_pipeline/facts.db`
- `metadata_embedding_pipeline/chroma_db/`
- `data/` (full directory)

Or rebuild them following Section 6 (requires Python 3.11+ and an activated venv).

### Step 4 — Build and start

```bash
docker compose up --build -d
```

The first build installs all dependencies including CPU-only PyTorch. Subsequent starts reuse the cached image and take only a few seconds.

The Streamlit service waits for the API service to pass its health check before starting.

### Step 5 — Open in a browser

| Service | URL |
| --- | --- |
| Streamlit UI | `http://localhost:8501` |
| FastAPI docs | `http://localhost:8000/docs` |

### Stop the application

```bash
docker compose down
```

### Deploying on a remote VM

Transfer the project files:

```bash
rsync -av --exclude='.git' --exclude='__pycache__' \
  /path/to/Group-6-DS-and-AI-Lab-Project/ \
  user@<vm-ip>:/opt/finquery/
```

Start on the VM:

```bash
ssh user@<vm-ip>
cd /opt/finquery
docker compose up --build -d
```

Ensure ports **8000** and **8501** are open in the VM firewall. The UI is then accessible at `http://<vm-ip>:8501`.

### Volume mounts explained

The Docker Compose configuration mounts three host paths into the container:

| Host path | Container path | Mode | Reason |
| --- | --- | --- | --- |
| `metadata_embedding_pipeline/facts.db` | `/app/metadata_embedding_pipeline/facts.db` | read-write | SQLite WAL mode requires write access even for reads |
| `metadata_embedding_pipeline/chroma_db` | `/app/metadata_embedding_pipeline/chroma_db` | read-write | ChromaDB writes internal state even on read-only queries |
| `data/` | `/app/data` | read-only | VECTOR pipeline reads document body Markdown files |

---

## 9. Script Reference

### Application scripts

#### `api.py`

FastAPI backend. Handles authentication, rate limiting, question routing, and answer generation.

**Run:**

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

**Endpoints:**

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/auth/token` | Login with username/password; returns a JWT bearer token valid for 8 hours |
| `POST` | `/query` | Submit a question (requires Bearer token); returns 4-step workflow trace, answer, citations, route, optional SQL, and latency |
| `GET` | `/health` | Returns `{"status": "ok"}` |

**Query pipeline:**

1. Embed the question with `text-embedding-3-small`.
2. Route: `gpt-4o-mini` classifies as `FACT_DB` or `VECTOR`.
3. `FACT_DB`: generate SELECT query → execute on SQLite → GPT-4o-mini generates answer.
4. `VECTOR`: Chroma top-20 + BM25 top-20 → Reciprocal Rank Fusion (k=60) → top-3 document bodies → GPT-4o-mini generates answer.

---

#### `streamlit_app.py`

Streamlit chat interface. Communicates with the FastAPI backend over HTTP.

**Run:**

```bash
streamlit run streamlit_app.py --server.port 8501
```

**Environment variable:** `API_BASE_URL` (default: `http://localhost:8000`). Override when running inside Docker Compose where the backend is at `http://api:8000`.

---

### Pipeline scripts

#### `metadata_embedding_pipeline.py`

Builds the ChromaDB vector index by embedding YAML front-matter metadata from all five source directories.

**Usage:**

```bash
python3 metadata_embedding_pipeline/metadata_embedding_pipeline.py
python3 metadata_embedding_pipeline/metadata_embedding_pipeline.py --skip-existing
```

**Inputs:** Five `data/` source directories (defined in `metadata_embedding_utils.py`).
**Output:** `metadata_embedding_pipeline/chroma_db/` (Chroma collection `metadata_embeddings`).
**Requires:** `OPENAI_API_KEY` in `.env`.

---

#### `fact_database.py`

Builds the SQLite fact database by extracting structured financial figures from Infosys IR Markdown files.

**Usage:**

```bash
python3 metadata_embedding_pipeline/fact_database.py
python3 metadata_embedding_pipeline/fact_database.py --rebuild
```

**Inputs:** `data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500_v2/`
**Output:** `metadata_embedding_pipeline/facts.db`
**Requires:** No API key (pure file parsing).

---

#### `fact_extractor.py`

Extracts structured facts from a single Markdown file. Used internally by `fact_database.py`.

Not intended for direct invocation. Exports `extract_facts_from_file(path)` which returns a list of fact dictionaries with keys: `row_label`, `column_label`, `raw_value`, `value_numeric`, `unit`, `period`, and provenance fields.

---

#### `router.py`

LLM-based question classifier. Routes each question to `FACT_DB` or `VECTOR`.

Not intended for direct invocation. Exports `route_question(question, openai_client)` which returns a `(route, reasoning)` tuple. Defaults to `VECTOR` when the LLM response is ambiguous.

---

#### `fact_query.py`

Answers numerical questions by generating a SQL SELECT statement, executing it against `facts.db`, and converting results to a natural-language answer.

Not intended for direct invocation. Exports `answer_from_fact_db(question, openai_client)` which returns a dictionary with keys: `answer`, `citations`, `sql`, `row_count`.

The database is opened in read-only URI mode to prevent any accidental writes. An additional keyword check refuses to execute statements that do not start with `SELECT`.

---

#### `metadata_embedding_utils.py`

Shared constants and pure helper functions. Imported by the indexing script, all benchmark scripts, and `api.py`.

Key exports: `PROJECT_ROOT`, `DB_PATH`, `DATA_SOURCES`, `EMBEDDING_MODEL`, `COLLECTION_NAME`, `find_markdown_files()`, `extract_yaml_front_matter()`, `metadata_to_text()`, `get_metadata_text_for_filepath()`.

Not intended for direct invocation.

---

### Benchmark scripts

#### `hybrid_bm25_benchmark.py`

**Production retrieval implementation.** Also serves as a three-way benchmark comparing vector-only, BM25-only, and hybrid RRF retrieval strategies.

**Usage:**

```bash
python3 metadata_embedding_pipeline/hybrid_bm25_benchmark.py
python3 metadata_embedding_pipeline/hybrid_bm25_benchmark.py --start 10 --limit 5
```

**Flags:**

| Flag | Default | Description |
| --- | --- | --- |
| `--start N` | 0 | Skip the first N questions (for resuming) |
| `--limit N` | all | Process only N questions |

**Inputs:** `data/infosys_rag_test_dataset_50_queries_v2.csv`, ChromaDB collection.
**Output:** `data/infosys_rag_test_dataset_50_queries_v2_hybrid_bm25_results.csv`
**Requires:** `OPENAI_API_KEY`, `rank-bm25`.

**Exported functions used by `api.py`:**

- `BM25Index(chroma_collection)` — builds a BM25Okapi index over YAML front-matter of all Chroma documents.
- `BM25Index.search(query, top_k)` — returns ranked list of documents.
- `rrf_fuse(vector_ranking, bm25_ranking, k=60)` — merges two ranked lists using Reciprocal Rank Fusion.

---

#### `metadata_embedding_benchmark.py`

Benchmark for vector-only retrieval (Chroma metadata embeddings, no reranking). Evaluates Recall@3/5/7.

**Usage:**

```bash
python3 metadata_embedding_pipeline/metadata_embedding_benchmark.py
python3 metadata_embedding_pipeline/metadata_embedding_benchmark.py --start 10 --limit 5
```

**Output:** `data/infosys_rag_test_dataset_50_queries_v2_metadata_embeddings_results.csv`

---

#### `metadata_embedding_reranker_benchmark.py`

Benchmark for vector retrieval with cross-encoder reranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`). Evaluates Recall@3/5/7.

**Usage:**

```bash
python3 metadata_embedding_pipeline/metadata_embedding_reranker_benchmark.py
```

**Output:** `data/infosys_rag_test_dataset_50_queries_v2_metadata_reranker_results.csv`
**Requires:** `transformers`, `torch`.

Note: This reranker is not used in production. Benchmark results showed it reduces Recall@3 on the hybrid list from 76% to 74% because the model (trained on MS MARCO web passages) is not calibrated for YAML metadata text.

---

#### `run_routing_benchmark.py`

Evaluates the FACT_DB / VECTOR router against the 40-question routing test set embedded in `sample_questions.csv`.

**Usage:**

```bash
python3 metadata_embedding_pipeline/run_routing_benchmark.py
```

**Output:** `datapreparation/benchmarking/routing_benchmark_results.csv` and a summary to stdout.
**Requires:** `OPENAI_API_KEY`.

---

#### `run_numeric_fidelity_benchmark.py`

Evaluates the end-to-end numeric accuracy of the FACT_DB pipeline against 15 representative numerical questions.

**Usage:**

```bash
python3 metadata_embedding_pipeline/run_numeric_fidelity_benchmark.py
```

**Output:** `datapreparation/benchmarking/numeric_fidelity_results.csv` and a summary to stdout.
**Requires:** `OPENAI_API_KEY`, `facts.db`.

---

## 10. Configuration Reference

All configuration is read from the `.env` file in the repository root.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key. Used for `text-embedding-3-small` embeddings and `gpt-4o-mini` calls. |
| `APP_USERNAME` | No | `admin` | Login username displayed on the Streamlit UI. |
| `APP_PASSWORD` | No | `changeme` | Login password. |
| `JWT_SECRET_KEY` | No | Random (regenerated on restart) | Secret for signing JWT tokens. Set explicitly to preserve sessions across restarts. |
| `APP_RATE_LIMIT_PER_HOUR` | No | `20` | Maximum number of queries per user per hour (sliding window). |

### Internal constants (not in `.env`)

These are defined in `metadata_embedding_utils.py` and `api.py` and require code changes to modify:

| Constant | Value | Description |
| --- | --- | --- |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model for both indexing and query-time embedding. |
| `COLLECTION_NAME` | `metadata_embeddings` | ChromaDB collection name. |
| `_JWT_ALGORITHM` | `HS256` | JWT signing algorithm. |
| `_JWT_EXPIRE_HOURS` | `8` | JWT token validity window in hours. |
| RRF `k` parameter | `60` | Reciprocal Rank Fusion constant. Higher values reduce the impact of top-ranked items from a single list. |

---

## 11. Troubleshooting

### Virtual environment not activated

If `uvicorn`, `streamlit`, or any import fails with `command not found` or `ModuleNotFoundError`, the virtual environment is likely not active.

**Fix:** Activate the environment before running any command:

```bash
source .venv/bin/activate   # Linux / macOS
.venv\Scripts\activate.bat  # Windows Command Prompt
```

---

### `OPENAI_API_KEY not set in .env`

The API server raises `RuntimeError: OPENAI_API_KEY not set in .env` at startup.

**Fix:** Create a `.env` file in the repository root with `OPENAI_API_KEY=sk-proj-...`. The file must be in the same directory as `api.py`.

---

### ChromaDB permission error on startup or first query

ChromaDB writes internal lock and state files even when performing read queries. If the `chroma_db/` directory or its parent is not writable, the client raises a `sqlite3.OperationalError` or similar permission error.

**Fix (local):** Ensure the process user has read-write access to `metadata_embedding_pipeline/chroma_db/`.

**Fix (Docker):** The `docker-compose.yml` mounts `chroma_db/` as read-write (no `:ro` suffix). If you modified the compose file to add `:ro`, remove it.

---

### BM25 index takes ~3 seconds on the first VECTOR query

This is expected. The BM25 index is built lazily on the first VECTOR request by reading all 1,875 YAML front-matter blocks from ChromaDB. The index is cached in memory for the lifetime of the process. All subsequent queries use the cached index instantly.

The log line `BM25 index ready (1875 documents, 2.8s)` confirms successful initialisation.

---

### `ModuleNotFoundError: No module named 'rank_bm25'`

`hybrid_bm25_benchmark.py` and therefore `api.py` require `rank-bm25`.

**Fix:**

```bash
pip install rank-bm25==0.2.2
```

---

### Rate limit exceeded (HTTP 429)

The API returns `429 Too Many Requests` when a user exceeds `APP_RATE_LIMIT_PER_HOUR` queries in a rolling one-hour window.

**Fix (development):** Set `APP_RATE_LIMIT_PER_HOUR=100` in `.env` and restart the API.

**Fix (temporary override without editing `.env`):**

```bash
APP_RATE_LIMIT_PER_HOUR=100 uvicorn api:app --host 0.0.0.0 --port 8000
```

---

### JWT token expired (HTTP 401 — "Token has expired")

Tokens are valid for 8 hours. After expiry, the Streamlit UI will show an authentication error.

**Fix:** Log out and log in again on the Streamlit UI to obtain a new token.

---

### `fact_database.py` returns wrong values for a metric

If the fact extraction logic in `fact_extractor.py` has been updated, the `facts.db` may contain stale rows from the previous logic.

**Fix:** Rebuild the database with the `--rebuild` flag:

```bash
python3 metadata_embedding_pipeline/fact_database.py --rebuild
```

---

### `metadata_embedding_pipeline.py` inserts fewer documents than expected

The script skips files that already exist in the ChromaDB collection when run with `--skip-existing`. If you need to re-embed all files (e.g., after changing the YAML extraction logic), delete the `chroma_db/` directory first:

```bash
rm -rf metadata_embedding_pipeline/chroma_db/
python3 metadata_embedding_pipeline/metadata_embedding_pipeline.py
```

---

### Streamlit shows a blank page or connection refused

The Streamlit frontend requires the FastAPI backend to be running. In Docker Compose, Streamlit waits for the API health check to pass before starting. Locally, start the API first (Terminal 1) and then Streamlit (Terminal 2).

**Check API health:**

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

---

### `docker compose up --build` fails with a pip error

If a package version in the `Dockerfile` is no longer available on PyPI (e.g., a yanked release), update the version pin in the `Dockerfile` `RUN pip install` layer. The packages most likely to need updates are `fastapi`, `uvicorn`, `streamlit`, `openai`, and `chromadb`.

---

### Answer is correct but the wrong unit is returned (e.g., INR instead of USD)

The fact database is restricted to the Infosys IR source only (`cleaned_section_files_1500_2500_v2`) to avoid mixing USD-denominated IR reports with INR-denominated NSE annual reports. If this restriction was accidentally removed from `fact_database.py`, rebuild the database.

The `FACT_DB_SOURCES` list in `fact_database.py` should contain only one entry:

```text
data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500_v2
```
