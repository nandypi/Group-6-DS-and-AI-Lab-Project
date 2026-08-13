FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/.cache/huggingface

# Minimal build deps (needed by some pip packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first to avoid pulling multi-GB CUDA wheels
RUN pip install --no-cache-dir \
    torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu

# Install all remaining runtime dependencies at pinned versions
RUN pip install --no-cache-dir \
    fastapi==0.141.1 \
    "uvicorn[standard]==0.52.0" \
    streamlit==1.61.1 \
    PyJWT==2.3.0 \
    requests==2.32.3 \
    "pydantic==2.11.4" \
    openai==1.78.0 \
    chromadb==1.5.9 \
    "transformers==4.51.3" \
    tqdm==4.67.1 \
    PyYAML==6.0.3 \
    tiktoken==0.9.0 \
    python-dotenv==1.1.0

# Pre-download the cross-encoder model so the first VECTOR request is not delayed
RUN python -c "\
from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
AutoTokenizer.from_pretrained('cross-encoder/ms-marco-MiniLM-L-6-v2'); \
AutoModelForSequenceClassification.from_pretrained('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Copy application source (data files are provided via volume mounts)
COPY api.py streamlit_app.py ./
COPY metadata_embedding_pipeline/*.py ./metadata_embedding_pipeline/

# Create placeholder directories for the volume-mounted data
RUN mkdir -p metadata_embedding_pipeline/chroma_db data

EXPOSE 8000 8501
