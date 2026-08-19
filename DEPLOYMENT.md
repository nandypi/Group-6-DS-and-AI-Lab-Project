# FinQuery — Deployment Guide

An investor-focused Q&A application over Infosys public disclosures.
Questions are automatically routed to the right pipeline:

- **Numerical questions** (revenue, margin, EPS, TCV, attrition) → SQLite fact database queried with LLM-generated SQL
- **Descriptive questions** (strategy, outlook, analyst commentary) → ChromaDB vector search + cross-encoder reranking + GPT-4o-mini

Both pipelines return a 4-step workflow trace and source citations.

---

## Prerequisites

- [Docker Engine](https://docs.docker.com/engine/install/) v24+ with the `docker compose` plugin
- An OpenAI API key
- The pre-built data files (see step 3 below)

No Python installation is required on the host machine.

---

## Deploying with Docker

### 1. Clone the repository

```bash
git clone https://github.com/nandypi/Group-6-DS-and-AI-Lab-Project.git
cd Group-6-DS-and-AI-Lab-Project
```

### 2. Create the `.env` file

Create a file named `.env` in the repository root with the following contents:

```
OPENAI_API_KEY=sk-...            # required — used for embeddings and GPT-4o-mini answers
APP_USERNAME=admin               # login username shown on the UI
APP_PASSWORD=finquery2026        # login password
JWT_SECRET_KEY=change-me-in-prod # any long random string; change before exposing publicly
APP_RATE_LIMIT_PER_HOUR=30       # max queries per user per hour
DO_RERANKING=True
```

### 3. Add the pre-built data files

The indexes and source documents are not tracked by Git. Place the following in
the cloned directory before building:

| Path | Size | What it is |
|---|---|---|
| `metadata_embedding_pipeline/facts.db` | ~88 MB | SQLite fact database (numerical facts extracted from IR documents) |
| `metadata_embedding_pipeline/chroma_db/` | ~42 MB | ChromaDB vector store (1,875 embedded documents) |
| `data/` | ~205 MB | Markdown source files read by the VECTOR pipeline for answer context |

These files are available from the project shared drive or can be rebuilt —
see [Rebuilding the Indexes](#rebuilding-the-indexes) at the end of this guide.

### 4. Build the image and start both services

```bash
docker compose up --build -d
```

The first build takes several minutes. It:
- Pulls `python:3.11-slim` as the base image
- Installs CPU-only PyTorch and all other dependencies
- Pre-downloads the cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2`)
  from HuggingFace so the first VECTOR query is not delayed at runtime

Subsequent `docker compose up` calls reuse the cached image and start in seconds.

### 5. Open in your browser

| Service | URL |
|---|---|
| Streamlit UI | `http://localhost:8501` |
| FastAPI docs | `http://localhost:8000/docs` |

Log in with the `APP_USERNAME` and `APP_PASSWORD` from your `.env` file.

### Stop the application

```bash
docker compose down
```

---

## Deploying on a Remote VM

### Transfer the project files

Run from your local machine:

```bash
rsync -av --exclude='.git' --exclude='__pycache__' \
  /path/to/Group-6-DS-and-AI-Lab-Project/ \
  user@<vm-ip>:/opt/finquery/
```

Total transfer size is approximately 340 MB (indexes + source files + code).

### Start on the VM

```bash
ssh user@<vm-ip>
cd /opt/finquery
docker compose up --build -d
```

Access the UI at `http://<vm-ip>:8501`.

Make sure ports **8000** and **8501** are open in the VM's firewall / security group.

---

## Running Locally Without Docker

Requires Python 3.11+.

```bash
# Install dependencies
pip install -r requirements.txt
pip install fastapi "uvicorn[standard]" streamlit PyJWT requests

# Terminal 1 — FastAPI backend
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Streamlit frontend
streamlit run streamlit_app.py --server.port 8501 --server.headless true
```

---

## What the Application Does

1. **Login** — enter credentials on the Streamlit UI
2. **Ask a question** — any Infosys financial question in natural language
3. **Step 1 — Embed** — the query is embedded with `text-embedding-3-small`
4. **Step 2 — Route** — GPT-4o-mini classifies the question as `FACT_DB` or `VECTOR`
5. **Step 3 — Retrieve**
   - `FACT_DB`: GPT-4o-mini generates a SELECT query against the SQLite fact database; results are returned in milliseconds
   - `VECTOR`: top-20 candidates are retrieved from ChromaDB, then reranked by the cross-encoder; top-3 document bodies are passed to the LLM
6. **Step 4 — Answer** — GPT-4o-mini synthesises a natural-language answer
7. **Result** — answer, pipeline badge, latency, SQL (if FACT_DB), and source citations are displayed

---

## Benchmark Results

| Metric | Score |
|---|---|
| Routing accuracy (40 questions) | 40 / 40 = **100%** |
| SQL execution success rate (15 questions) | 15 / 15 = **100%** |
| Numeric fidelity — answer within 5% of expected (15 questions) | 15 / 15 = **100%** |
| Average end-to-end latency | ~4 s / question |

---

## Key Files

```
Group-6-DS-and-AI-Lab-Project/
├── api.py                          # FastAPI backend (auth, rate limiting, /query endpoint)
├── streamlit_app.py                # Streamlit frontend
├── Dockerfile                      # Single-stage image
├── docker-compose.yml              # api (:8000) + streamlit (:8501)
├── .env                            # Secrets — create this, do not commit
└── metadata_embedding_pipeline/
    ├── router.py                   # FACT_DB / VECTOR classifier
    ├── fact_query.py               # SQL generation + execution + NL answer
    ├── fact_database.py            # SQLite fact DB builder
    ├── fact_extractor.py           # Markdown table + prose extraction
    ├── metadata_embedding_pipeline.py      # ChromaDB indexing
    ├── metadata_embedding_reranker_benchmark.py  # Cross-encoder reranker
    ├── facts.db                    # Pre-built fact DB (volume-mounted)
    ├── chroma_db/                  # Pre-built vector store (volume-mounted)
    ├── run_routing_benchmark.py    # Routing accuracy benchmark
    ├── run_numeric_fidelity_benchmark.py   # Numeric fidelity benchmark
    └── numerical_benchmark.csv    # 15-question numeric evaluation set
```

---

## Rebuilding the Indexes

If you need to recreate the databases from the raw markdown files:

```bash
# Rebuild the SQLite fact database
python metadata_embedding_pipeline/fact_database.py --rebuild

# Re-index all documents into ChromaDB
python metadata_embedding_pipeline/metadata_embedding_pipeline.py
```

Both scripts read from `data/infosys_earning_calls_press_conf_fact_sheets_results/`
and require `OPENAI_API_KEY` in `.env` (ChromaDB indexing uses the OpenAI embedding API).
