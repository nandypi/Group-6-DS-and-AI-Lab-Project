import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

load_dotenv()

# -----------------------
# Configuration
# -----------------------

DATA_FOLDER = r"C:\Users\Hp\Desktop\DS-AI-LAB\Group-6-DS-and-AI-Lab-Project\data\demo-bot-data"

COLLECTION_NAME = os.getenv(
    "COLLECTION_NAME",
    "finance_documents"
)

DB_PATH = os.getenv(
    "CHROMA_DB_PATH",
    "./chroma_db"
)

EMBEDDING_MODEL = "text-embedding-3-small"

# -----------------------
# OpenAI Client
# -----------------------

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# -----------------------
# ChromaDB
# -----------------------

chroma_client = chromadb.PersistentClient(path=DB_PATH)

collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME
)

# -----------------------
# Embedding Function
# -----------------------

def get_embedding(text: str):

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )

    return response.data[0].embedding

# -----------------------
# Read Markdown Files
# -----------------------

markdown_files = list(
    Path(DATA_FOLDER).rglob("*.md")
)

print(f"Found {len(markdown_files)} markdown files.")

for file in tqdm(markdown_files):

    with open(file, "r", encoding="utf-8") as f:
        text = f.read()

    embedding = get_embedding(text)

    document_id = str(file.relative_to(DATA_FOLDER))

    collection.add(
        ids=[document_id],

        documents=[text],

        embeddings=[embedding],

        metadatas=[{
            "filename": file.name,
            "filepath": str(file),
            "company": file.parent.name
        }]
    )

print("Embedding completed successfully.")