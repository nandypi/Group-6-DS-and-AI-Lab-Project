"""FastAPI backend for the FinQuery application.

Endpoints
---------
POST /auth/token       – login with username/password → JWT access token
POST /query            – ask a question (requires auth, rate-limited)

Authentication
--------------
Credentials are read from .env:
    APP_USERNAME=<username>
    APP_PASSWORD=<password>
    JWT_SECRET_KEY=<random-secret>   (optional; generated randomly if absent)

Rate limiting
-------------
Per-user, per-hour sliding window.  Limit is set by APP_RATE_LIMIT_PER_HOUR
in .env (default: 20).

Query pipeline
--------------
1. Embed the question with text-embedding-3-small.
2. Route the question (LLM → FACT_DB or VECTOR).
3a. FACT_DB  → generate + execute SQL → generate natural-language answer.
3b. VECTOR   → top-20 metadata retrieval → cross-encoder rerank → top-3 context → gpt-4o-mini.
4. Return workflow steps, answer, citations, and route metadata.

Run
---
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import chromadb
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from openai import OpenAI
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Resolve paths and add metadata_embedding_pipeline to sys.path.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "metadata_embedding_pipeline"))

from fact_query import answer_from_fact_db  # noqa: E402
from metadata_embedding_utils import (  # noqa: E402
    COLLECTION_NAME,
    DB_PATH as CHROMA_DB_PATH,
    EMBEDDING_MODEL,
)
from router import route_question  # noqa: E402

# Pipeline B reranker (lazy-loaded on first VECTOR request).
_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from metadata_embedding_reranker_benchmark import CrossEncoderReranker  # noqa: E402
        _reranker = CrossEncoderReranker()
    return _reranker


# ---------------------------------------------------------------------------
# Configuration (loaded from .env).
# ---------------------------------------------------------------------------
load_dotenv(PROJECT_ROOT / ".env")

_APP_USERNAME         = os.getenv("APP_USERNAME", "admin")
_APP_PASSWORD         = os.getenv("APP_PASSWORD", "changeme")
_JWT_SECRET           = os.getenv("JWT_SECRET_KEY") or os.urandom(32).hex()
_JWT_ALGORITHM        = "HS256"
_JWT_EXPIRE_HOURS     = 8
_RATE_LIMIT_PER_HOUR  = int(os.getenv("APP_RATE_LIMIT_PER_HOUR", "20"))

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not _OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in .env")

_openai_client: OpenAI | None = None
_chroma_collection = None


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=_OPENAI_API_KEY)
    return _openai_client


def _get_chroma():
    global _chroma_collection
    if _chroma_collection is None:
        chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        _chroma_collection = chroma_client.get_collection(name=COLLECTION_NAME)
    return _chroma_collection


# ---------------------------------------------------------------------------
# Rate limiter (in-memory sliding window).
# ---------------------------------------------------------------------------
_request_log: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(username: str) -> None:
    now = time.time()
    window_start = now - 3600  # 1-hour window
    log = _request_log[username]
    # Prune old entries.
    _request_log[username] = [t for t in log if t > window_start]
    if len(_request_log[username]) >= _RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {_RATE_LIMIT_PER_HOUR} requests per hour.",
        )
    _request_log[username].append(now)


# ---------------------------------------------------------------------------
# JWT helpers.
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def _create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def _get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        username: str = payload.get("sub", "")
        if not username:
            raise credentials_error
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_error


# ---------------------------------------------------------------------------
# Pipeline B helpers (VECTOR path).
# ---------------------------------------------------------------------------

def _get_context_body(filepath: str, char_limit: int = 4000) -> str:
    """Read a markdown file body (YAML front matter stripped), truncated."""
    path = PROJECT_ROOT / filepath
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return f"[Could not read: {filepath}]"
    # Strip YAML front matter.
    if content.startswith("---"):
        lines = content.splitlines(keepends=True)
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                body = "".join(lines[i + 1:]).lstrip("\r\n")
                return body[:char_limit]
    return content[:char_limit]


def _run_vector_pipeline(question: str) -> dict[str, Any]:
    """Run Pipeline B: embed → top-20 Chroma → cross-encoder rerank → top-3 → LLM.

    Returns a dict with keys: answer, citations, retrieval_detail, llm_detail.
    """
    client     = _get_openai()
    collection = _get_chroma()

    # Embed the question.
    embedding = client.embeddings.create(
        model=EMBEDDING_MODEL, input=[question]
    ).data[0].embedding

    # Retrieve top-20 candidates.
    results = collection.query(
        query_embeddings=[embedding],
        n_results=20,
        include=["metadatas"],
    )
    candidates: list[dict] = []
    for rank, meta in enumerate(results.get("metadatas", [[]])[0], start=1):
        fp = meta.get("filepath", meta.get("filename", ""))
        candidates.append(
            {"rank": rank, "filename": meta.get("filename", fp), "filepath": fp}
        )

    retrieval_detail = f"Retrieved {len(candidates)} candidates from Chroma (metadata_embeddings)"

    # Cross-encoder rerank.
    reranker = _get_reranker()
    reranked = reranker.rerank(question, candidates)
    top3 = reranked[:3]
    reranked_detail = (
        f"Reranked with cross-encoder/ms-marco-MiniLM-L-6-v2; "
        f"top-3: {', '.join(d['filename'] for d in top3)}"
    )

    # Read context bodies.
    citations = [d["filepath"] for d in top3]
    bodies    = [_get_context_body(fp) for fp in citations]

    # Generate answer.
    context_section = "\n\n---\n\n".join(
        f"[Document {i+1}]\n{body}" for i, body in enumerate(bodies)
    )
    prompt = (
        f"Answer the following question using only the provided documents.\n\n"
        f"Question: {question}\n\nDocuments:\n{context_section}\n\nAnswer:"
    )
    llm_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer questions based only on the provided documents. "
                    "Be concise and accurate."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    answer = (llm_resp.choices[0].message.content or "").strip()

    return {
        "answer":           answer,
        "citations":        citations,
        "retrieval_detail": retrieval_detail,
        "reranked_detail":  reranked_detail,
    }


# ---------------------------------------------------------------------------
# FastAPI app.
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FinQuery API",
    description="Financial Q&A with Numeric Fidelity Layer and semantic retrieval.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models.
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    question: str


class WorkflowStep(BaseModel):
    step: int
    name: str
    detail: str


class QueryResponse(BaseModel):
    steps: list[WorkflowStep]
    answer: str
    citations: list[str]
    route: str
    sql: str | None
    latency_ms: int


# ---------------------------------------------------------------------------
# Auth endpoint.
# ---------------------------------------------------------------------------
@app.post("/auth/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate with username and password; return a JWT bearer token."""
    if form_data.username != _APP_USERNAME or form_data.password != _APP_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = _create_access_token(form_data.username)
    return {"access_token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Query endpoint.
# ---------------------------------------------------------------------------
@app.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    current_user: str = Depends(_get_current_user),
):
    """Process one financial question and return the answer with workflow steps."""
    _check_rate_limit(current_user)

    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    t_start = time.perf_counter()
    steps: list[WorkflowStep] = []
    client = _get_openai()

    # --- Step 1: embed ---
    t0 = time.perf_counter()
    embedding = client.embeddings.create(
        model=EMBEDDING_MODEL, input=[question]
    ).data[0].embedding
    embed_ms = int((time.perf_counter() - t0) * 1000)
    steps.append(WorkflowStep(
        step=1,
        name="Embedding Generated",
        detail=f"Query embedded with {EMBEDDING_MODEL} ({len(embedding)} dims) in {embed_ms} ms.",
    ))

    # --- Step 2: route ---
    t0 = time.perf_counter()
    route, routing_reasoning = route_question(question, client)
    route_ms = int((time.perf_counter() - t0) * 1000)
    steps.append(WorkflowStep(
        step=2,
        name="Route Identified",
        detail=f"→ {route} ({routing_reasoning}) in {route_ms} ms.",
    ))

    # --- Step 3: retrieve / query ---
    if route == "FACT_DB":
        t0 = time.perf_counter()
        fact_result = answer_from_fact_db(question, client)
        db_ms = int((time.perf_counter() - t0) * 1000)

        sql_summary = (
            fact_result.get("sql", "").split("\n")[0][:120]
            if fact_result.get("sql") else "—"
        )
        steps.append(WorkflowStep(
            step=3,
            name="Fact Database Queried",
            detail=(
                f"SQL: {sql_summary} | "
                f"{fact_result.get('row_count', 0)} row(s) returned in {db_ms} ms."
            ),
        ))
        steps.append(WorkflowStep(
            step=4,
            name="Answer Generated",
            detail=f"gpt-4o-mini summarized {fact_result.get('row_count', 0)} SQL result(s).",
        ))
        answer    = fact_result.get("answer", "No answer generated.")
        citations = fact_result.get("citations", [])
        sql_out   = fact_result.get("sql")

    else:
        t0 = time.perf_counter()
        vec_result = _run_vector_pipeline(question)
        vec_ms = int((time.perf_counter() - t0) * 1000)

        steps.append(WorkflowStep(
            step=3,
            name="Vector Pipeline Executed",
            detail=f"{vec_result['retrieval_detail']}. {vec_result['reranked_detail']} in {vec_ms} ms.",
        ))
        steps.append(WorkflowStep(
            step=4,
            name="Answer Generated",
            detail="gpt-4o-mini answered using top-3 reranked document bodies.",
        ))
        answer    = vec_result.get("answer", "No answer generated.")
        citations = vec_result.get("citations", [])
        sql_out   = None

    total_ms = int((time.perf_counter() - t_start) * 1000)
    return QueryResponse(
        steps=steps,
        answer=answer,
        citations=citations,
        route=route,
        sql=sql_out,
        latency_ms=total_ms,
    )


# ---------------------------------------------------------------------------
# Health check.
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}
