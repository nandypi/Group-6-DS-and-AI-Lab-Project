# Hybrid Retrieval Setup Guide: Chroma + BM25 with RRF

## Overview

This guide explains how to set up and use the hybrid retrieval system that combines:
- **Chroma** (dense vector search using OpenAI embeddings)
- **BM25** (lexical/keyword-based search)
- **RRF** (Reciprocal Rank Fusion to combine both rankings)

The system returns the top 3 chunks without reranking, providing a balance between semantic and keyword-based relevance.

## System Architecture

```
Question
   │
   ├─────────────────┬─────────────────┐
   ▼                 ▼                 
Embed Query       Tokenize Query
   │                 │
   ▼                 ▼
Chroma Query    BM25 Query
(Dense Search)  (Lexical Search)
   │                 │
   └────────┬────────┘
            ▼
        RRF Fusion
        (Combine & Rank)
            │
            ▼
        Top 3 Chunks
            │
            ▼
        Remove YAML Front Matter
            │
            ▼
        LLM Answer
```

## Setup Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

The key additional package is:
- `rank_bm25` - Python implementation of BM25 ranking algorithm

### 2. Build BM25 Index

Before using the hybrid retriever, you must build the BM25 index from your Markdown files.

```bash
cd embeddings_script
python bm25_indexer.py
```

This script:
- Scans the same 5 approved data sources used by Chroma
- Tokenizes each document
- Builds and saves the BM25 index to `bm25_index.pkl`
- Saves document metadata to `bm25_docs.pkl`

**To rebuild the index (e.g., after updating source documents):**

```bash
python bm25_indexer.py --force
```

**Output:**
```
Found 125 Markdown files.
Processing documents...
Tokenizing files: 100%|████████| 125/125
Building BM25 index...
Saving BM25 index to .../bm25_index.pkl...
Saving document metadata to .../bm25_docs.pkl...
✓ Completed: BM25 index built with 125 documents.
```

### 3. Verify Chroma Index

Ensure Chroma is already indexed. If not, run:

```bash
python index_documents.py
```

This creates embeddings for all documents in `chroma_db/`.

## Using retrieve1.py (Hybrid Retriever)

### Option A: Interactive CLI

```bash
cd embeddings_script
python retrieve1.py
```

This loads both indices and accepts questions interactively:

```
================================================================================
Ask a question (type 'exit' to quit): What are Infosys revenue trends?

Searching (Chroma + BM25 with RRF)...

================================================================================
HYBRID RETRIEVAL (CHROMA + BM25 with RRF)
================================================================================
Rank #1: infosys_financial_report.md | sources=[dense, lexical] | rrf_score=0.0278
Rank #2: revenue_analysis.md | sources=[dense] | rrf_score=0.0185
Rank #3: earnings_call_transcript.md | sources=[lexical] | rrf_score=0.0142
Final context estimate: 2450 tokens

================================================================================
ANSWER
================================================================================
Based on the provided documents, Infosys revenue trends show...

PIPELINE LATENCY
--------------------------------------------------------------------------------
Embedding: 0.234 seconds
Dense retrieval (Chroma): 0.045 seconds
Lexical retrieval (BM25): 0.012 seconds
RRF fusion: 0.003 seconds
Context preparation: 0.018 seconds
LLM request: 1.234 seconds
Total question latency: 1.546 seconds
```

### Option B: Backend API Integration

Update your `backend/app.py` to use `retrieve1.py`:

```python
from embeddings_script.retrieve1 import answer_question

# ... rest of your FastAPI code remains the same
# The QueryResponse model is compatible with both retrievers
```

Then restart your FastAPI server:

```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Query it:

```bash
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What are Infosys earnings and revenue trends?"}'
```

### Option C: Programmatic Usage

```python
from embeddings_script.retrieve1 import answer_question

result = answer_question("What is Infosys quarterly revenue?")

print("Answer:", result["answer"])
print("Citations:")
for citation in result["citations"]:
    print(f"  - {citation['filename']} (score: {citation['score']:.4f})")
print("Timings:", result["timings"])
```

## Configuration

Edit `.env` to customize behavior:

```bash
# Core settings
COLLECTION_NAME=finance_file_embeddings
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini
FINAL_DOCUMENT_COUNT=3           # Top N chunks to return
LLM_MAX_INPUT_TOKENS=128000      # Max prompt size

# API keys
OPENAI_API_KEY=sk-...
CORS_ORIGINS=*
```

### RRF Parameters

The RRF parameter `k` is hardcoded in `retrieve1.py`:

```python
RRF_K = 60  # RRF score = 1 / (60 + rank)
```

To adjust, edit `retrieve1.py` line 32:

```python
RRF_K = 60  # Increase for more balanced contribution from both sources
            # Decrease for more weight on top results
```

## Understanding RRF (Reciprocal Rank Fusion)

RRF combines two ranked lists by assigning each result a score based on its rank:

```
RRF_score = Σ(1 / (k + rank_in_list))
```

Example with k=60:
- If a document ranks #1 in both Chroma and BM25:
  - Score = 1/(60+1) + 1/(60+1) = 0.0165 + 0.0165 = 0.0330
  
- If a document ranks #1 in Chroma but doesn't appear in BM25 top 10:
  - Score = 1/(60+1) = 0.0165

This approach naturally:
- ✓ Rewards documents found by both methods (high confidence)
- ✓ Still considers documents from only one method
- ✓ Avoids requiring threshold tuning or weighted averages

## Troubleshooting

### "BM25 index not found"

**Problem:** `retrieve1.py` fails with "BM25 index not found"

**Solution:**
```bash
cd embeddings_script
python bm25_indexer.py
```

### "Chroma collection not found"

**Problem:** Chroma database doesn't exist

**Solution:**
```bash
cd embeddings_script
python index_documents.py
```

### Slow performance

**Diagnosis:** Run with `--verbose` (add to code) to see individual latencies.

**Optimizations:**
- BM25 is in-memory; already fast (~10ms)
- Dense search (Chroma) typically takes 50-100ms
- Embedding generation takes 200-400ms (network dependent)

### Different results between retrieve.py and retrieve1.py

This is expected! 
- `retrieve.py` uses only Chroma (dense vectors)
- `retrieve1.py` uses Chroma + BM25 + RRF (hybrid)

The hybrid approach may retrieve documents missed by pure semantic search and vice versa.

## Comparing Pipelines

| Feature | retrieve.py | retrieve1.py |
|---------|-------------|--------------|
| Dense Search | ✓ | ✓ |
| Lexical Search | ✗ | ✓ |
| Reranking | Optional | ✗ (RRF instead) |
| Top Results | 3 | 3 |
| Retrieval Speed | ~50-100ms | ~60-120ms |
| Latency Overhead | Low | Medium (hybrid search) |
| Best For | Semantic queries | General Q&A |

## File Structure

```
embeddings_script/
├── retriever.py          # Original Chroma-only retriever
├── retrieve1.py          # NEW: Hybrid retriever (Chroma + BM25 + RRF)
├── bm25_indexer.py       # NEW: Build BM25 index
├── bm25_index.pkl        # NEW: Serialized BM25 index (generated)
├── bm25_docs.pkl         # NEW: Document metadata (generated)
├── index_documents.py    # Original: Build Chroma index
├── chroma_db/            # Chroma persistent storage
├── reranker.py           # Reranking utilities (used by retrieve.py)
└── rag_pipeline_README.md # This file
```

## Next Steps

1. Run `python bm25_indexer.py` to build the BM25 index
2. Test with `python retrieve1.py` and ask a question
3. Update `backend/app.py` to import from `retrieve1` instead of `retriever`
4. Restart your API server and test via HTTP

## Performance Notes

- **First run latency:** Slightly higher (index loading)
- **Subsequent runs:** 60-120ms per query (excluding embedding)
- **Memory usage:** BM25 index + document texts ≈ 50-100MB
- **Index rebuild:** ~5-10 seconds for 100+ documents

## References

- [BM25 Algorithm](https://en.wikipedia.org/wiki/Okapi_BM25)
- [Reciprocal Rank Fusion](https://en.wikipedia.org/wiki/Reciprocal_rank_fusion)
- [rank_bm25 Library](https://github.com/dorianbrown/rank_bm25)
- [Chroma Documentation](https://docs.trychroma.com/)
