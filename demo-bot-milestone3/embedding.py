'''loads embedding model'''

from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"

print("Loading embedding model...")

model = SentenceTransformer(MODEL_NAME)

print("Embedding model loaded.")