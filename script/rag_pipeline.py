import os
import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# =========================================================
# LOAD ENV
# =========================================================
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
XAI_API_KEY = os.getenv("GROK_API_KEY")  # Using GROK_API_KEY from your .env

# =========================================================
# CONFIG
# =========================================================
COLLECTION_NAME = "medical_chunks_v3_bge_large"
TOP_K = 5
TEMPERATURE = 0.1
XAI_API_URL = "https://api.x.ai/v1/chat/completions"

# =========================================================
# INIT MODELS
# =========================================================
print("[INFO] Loading BGE-LARGE embedding model...")
embedding_model = SentenceTransformer(
    "BAAI/bge-large-en-v1.5",
    device="cpu"
)

print("[INFO] Connecting to Qdrant...")
qdrant_client = QdrantClient(url=QDRANT_URL, timeout=30)

# Verify API key
if not XAI_API_KEY or not XAI_API_KEY.startswith('xai-'):
    print("\n❌ ERROR: Invalid GROK_API_KEY in .env file!")
    print("Your API key should start with 'xai-'")
    exit(1)

# =========================================================
# EMBEDDING FUNCTION
# =========================================================
def get_query_embedding(query: str) -> list:
    query_text = "Represent this sentence for searching relevant passages: " + query
    return embedding_model.encode(
        query_text,
        normalize_embeddings=True
    ).tolist()

# =========================================================
# RETRIEVE RELEVANT CHUNKS
# =========================================================
def retrieve_chunks(query: str, top_k: int = TOP_K):
    print(f"\n🔍 Searching for: '{query}'")

    query_vector = get_query_embedding(query)

    results = qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        with_payload=True
    )

    chunks = []
    for i, hit in enumerate(results, 1):
        payload = hit.payload
        chunks.append({
            "rank": i,
            "score": hit.score,
            "text": payload.get("text", ""),
            "book_name": payload.get("book_name", "Unknown"),
            "chapter_title": payload.get("chapter_title") or payload.get("section_title", "Unknown"),
            "page_range": payload.get("page_range", "N/A"),
            "chunk_type": payload.get("chunk_type", "text"),
            "category": payload.get("category", "Unknown")
        })

    return chunks

# =========================================================
# GENERATE ANSWER WITH GROK
# =========================================================
def generate_answer(query: str, chunks: list):
    """Generate answer using Grok (xAI)"""

    context_parts = []
    for chunk in chunks:
        source = f"{chunk['book_name']} - {chunk['chapter_title']} (Page {chunk['page_range']})"
        context_parts.append(f"[Source: {source}]\n{chunk['text']}")

    context = "\n\n---\n\n".join(context_parts)

    system_msg = """You are a medical AI assistant. Answer questions accurately based ONLY on the provided context.

Guidelines:
- Use ONLY information from the context provided
- If the answer is not in the context, say "I don't have enough information to answer this question"
- Cite sources by mentioning the book/chapter name
- Be concise and clinical
- Use medical terminology appropriately"""

    user_msg = f"""Context from medical textbooks:

{context}

Question: {query}

Please provide a detailed answer based on the context above."""

    payload = {
        "model": "grok-3",  # ✅ Latest model (Jan 2026)
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        "temperature": TEMPERATURE,
        "max_tokens": 1000,
        "stream": False
    }

    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }

    print("\n🤖 Generating answer with Grok-3...")

    try:
        response = requests.post(
            XAI_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code != 200:
            error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
            error_msg = error_data.get("error", response.text)
            raise Exception(f"xAI API Error {response.status_code}: {error_msg}")

        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    except requests.exceptions.Timeout:
        return "⚠️ Request timed out. Please try again."
    except Exception as e:
        raise Exception(f"Grok API Error: {str(e)}")

# =========================================================
# DISPLAY RESULTS
# =========================================================
def display_results(query: str, chunks: list, answer: str):
    print("\n" + "=" * 80)
    print("📊 RAG PIPELINE RESULTS")
    print("=" * 80)
    print(f"\n❓ QUERY: {query}\n")

    print("📚 RETRIEVED CHUNKS:")
    print("-" * 80)

    for chunk in chunks:
        print(f"\n[{chunk['rank']}] Score: {chunk['score']:.4f} | Type: {chunk['chunk_type']}")
        print(f"    Source: {chunk['book_name']} - {chunk['chapter_title']}")
        print(f"    Pages: {chunk['page_range']} | Category: {chunk['category']}")
        print(f"    Text: {chunk['text'][:200]}...")

    print("\n" + "-" * 80)
    print("💡 GENERATED ANSWER:")
    print("-" * 80)
    print(answer)
    print("\n" + "=" * 80)

# =========================================================
# MAIN RAG PIPELINE
# =========================================================
def run_rag_pipeline(query: str, top_k: int = TOP_K):
    chunks = retrieve_chunks(query, top_k)

    if not chunks:
        print("\n❌ No relevant chunks found!")
        return None

    answer = generate_answer(query, chunks)
    display_results(query, chunks, answer)

    return {
        "query": query,
        "chunks": chunks,
        "answer": answer
    }

# =========================================================
# QUICK TEST
# =========================================================
def quick_test():
    query = "What are the screening guidelines for cervical cancer?"
    print("\n🚀 QUICK TEST MODE")
    print("=" * 80)
    run_rag_pipeline(query)

# =========================================================
# INTERACTIVE MODE
# =========================================================
def interactive_mode():
    print("\n🎯 MEDICAL RAG - INTERACTIVE MODE")
    print("=" * 80)
    print("Type your medical questions. Type 'exit' to quit.\n")

    while True:
        try:
            query = input("❓ Your question: ").strip()

            if query.lower() in ["exit", "quit", "q"]:
                print("\n👋 Bye!")
                break

            if not query:
                print("⚠️ Enter a question\n")
                continue

            run_rag_pipeline(query)
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")

# =========================================================
# CHECK COLLECTION
# =========================================================
def check_collection():
    try:
        info = qdrant_client.get_collection(COLLECTION_NAME)
        print(f"\n✅ Qdrant collection ready: {COLLECTION_NAME}")
        print(f"📊 Total vectors: {info.points_count}")
        print(f"📐 Vector dimension: {info.config.params.vectors.size}")
        return True
    except Exception as e:
        print(f"\n❌ Qdrant error: {e}")
        return False

# =========================================================
# BATCH TEST
# =========================================================
def batch_test():
    test_queries = [
        "What are the screening guidelines for cervical cancer?",
        "What are the risk factors for ovarian cancer?",
        "Explain BRCA1 and BRCA2 mutations",
        "What is Lynch syndrome?",
        "What are HPV vaccination guidelines?"
    ]
    
    print("\n🧪 BATCH TEST MODE")
    print("=" * 80)
    print(f"Running {len(test_queries)} test queries...\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i}/{len(test_queries)}")
        print(f"{'=' * 80}")
        
        try:
            run_rag_pipeline(query)
            if i < len(test_queries):
                input("\nPress Enter for next test...")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue

# =========================================================
# MAIN MENU
# =========================================================
def main():
    if not check_collection():
        return

    print("\n" + "=" * 80)
    print("🏥 MEDICAL RAG PIPELINE - GROK EDITION")
    print("=" * 80)
    print("\n1. Quick Test (single query)")
    print("2. Interactive Mode (ask multiple questions)")
    print("3. Batch Test (5 test queries)")
    print("4. Exit")
    print("=" * 80)

    while True:
        try:
            choice = input("\nChoose (1-4): ").strip()

            if choice == "1":
                quick_test()
            elif choice == "2":
                interactive_mode()
            elif choice == "3":
                batch_test()
            elif choice == "4":
                print("\n👋 Goodbye!")
                break
            else:
                print("⚠️ Invalid option. Choose 1-4.")
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break

if __name__ == "__main__":
    main()