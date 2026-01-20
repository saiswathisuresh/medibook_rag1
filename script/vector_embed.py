import os
import json
import uuid
import time
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer

# =========================================================
# LOAD ENV
# =========================================================
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

# =========================================================
# CONFIG
# =========================================================
COLLECTION_NAME = "medical_chunks_bge_small"
VECTOR_DIM = 384              # ✅ BGE-SMALL dimension
BATCH_SIZE = 32               # AWS free-tier safe
SLEEP_BETWEEN_BATCH = 0.2

# =========================================================
# PATHS
# =========================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS_DIR = os.path.join(BASE_DIR, "data", "chunks")

print(f"[INFO] Using chunks folder: {CHUNKS_DIR}")

# =========================================================
# LOAD EMBEDDING MODEL (BGE-SMALL)
# =========================================================
print("[INFO] Loading BAAI/bge-small-en ...")
embedder = SentenceTransformer("BAAI/bge-small-en", device="cpu")

def embed_text(text: str) -> list:
    text = "Represent this sentence for retrieval: " + text
    return embedder.encode(text, normalize_embeddings=True).tolist()

# =========================================================
# INIT QDRANT
# =========================================================
print("[INFO] Connecting to Qdrant...")
client = QdrantClient(url=QDRANT_URL, timeout=60)

print("[INFO] Recreating collection...")
try:
    client.delete_collection(COLLECTION_NAME)
except Exception:
    pass

client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(
        size=VECTOR_DIM,
        distance=Distance.COSINE
    )
)

print("[INFO] Qdrant collection ready")

# =========================================================
# LOAD ALL CHUNKS
# =========================================================
all_chunks = []

for file in os.listdir(CHUNKS_DIR):
    if not file.endswith(".json"):
        continue

    path = os.path.join(CHUNKS_DIR, file)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
        all_chunks.extend(data.get("chunks", []))

total = len(all_chunks)
print(f"[INFO] Total chunks found: {total}")

if total == 0:
    print("❌ No chunks found. Exiting.")
    exit(1)

# =========================================================
# EMBED + UPSERT
# =========================================================
points = []
uploaded = 0

for idx, chunk in enumerate(all_chunks, 1):
    text = chunk.get("text", "").strip()
    meta = chunk.get("metadata", {})

    if not text or len(text) < 50:
        continue

    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=embed_text(text),
        payload={
            "text": text,
            "book_id": meta.get("book_id"),
            "book_name": meta.get("book_name"),
            "category": meta.get("category"),
            "chapter_title": meta.get("chapter_title"),
            "chapter_number": meta.get("chapter_number"),
            "page_range": meta.get("page_range"),
            "chunk_type": meta.get("chunk_type", "text"),
            "source_type": meta.get("source_type", "book")
        }
    )

    points.append(point)

    if len(points) >= BATCH_SIZE:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True
        )
        uploaded += len(points)
        print(f"[INFO] Uploaded {uploaded}/{total}")
        points = []
        time.sleep(SLEEP_BETWEEN_BATCH)

# Remaining points
if points:
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True
    )
    uploaded += len(points)

print(f"\n✅ VECTOR EMBEDDING COMPLETE")
print(f"📊 Total vectors stored: {uploaded}")
print(f"📦 Collection name: {COLLECTION_NAME}")
