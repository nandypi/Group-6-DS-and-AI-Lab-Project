import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from embeddings_script.retriever import answer_question


app = FastAPI(title="Finance RAG API", version="1.0.0")

# Local development is intentionally unauthenticated.
allow_origins = os.getenv("CORS_ORIGINS", "*").split(",")
allow_origins = [origin.strip() for origin in allow_origins if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


class Citation(BaseModel):
    filename: str
    filepath: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    context: str = ""
    timings: dict = {}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/query", response_model=QueryResponse)
def query_api(payload: QueryRequest):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        result = answer_question(question)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"RAG query failed: {exc}",
        ) from exc

    return {
        "answer": result["answer"],
        "citations": [
            {
                "filename": citation["filename"],
                "filepath": citation["filepath"],
                "score": citation["score"],
            }
            for citation in result.get("citations", [])
        ],
        "context": result.get("context", ""),
        "timings": result.get("timings", {}),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
