import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from openai import OpenAI

# =========================================================
# LOAD ENV
# =========================================================
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
XAI_API_KEY = os.getenv("XAI_API_KEY")  # Use xAI instead of OpenAI

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
embedding_model = SentenceTransformer("BAAI/bge-large-en-v1.5", device="cpu")

print("[INFO] Connecting to Qdrant...")
qdrant_client = QdrantClient(url=QDRANT_URL, timeout=30)

# Verify xAI API key
if not XAI_API_KEY or not XAI_API_KEY.startswith('xai-'):
    print("\n❌ ERROR: Invalid XAI_API_KEY in .env file!")
    print("Your API key should start with 'xai-' and be around 100+ characters")
    print("Get your key from: https://console.x.ai")
    exit(1)

# =========================================================
# EMBEDDING FUNCTION
# =========================================================
def get_query_embedding(query: str) -> list:
    """Generate query embedding with BGE-LARGE"""
    query_text = "Represent this sentence for searching relevant passages: " + query
    return embedding_model.encode(query_text, normalize_embeddings=True).tolist()

# =========================================================
# RETRIEVE RELEVANT CHUNKS
# =========================================================
def retrieve_chunks(query: str, top_k: int = TOP_K):
    """Retrieve top-k relevant chunks from Qdrant"""
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
# GENERATE ANSWER WITH GROK (xAI)
# =========================================================
def generate_answer(query: str, chunks: list):
    """Generate answer using Grok via xAI API"""
    import requests
    
    # Build context from chunks
    context_parts = []
    for chunk in chunks:
        source = f"{chunk['book_name']} - {chunk['chapter_title']} (Page {chunk['page_range']})"
        context_parts.append(f"[Source: {source}]\n{chunk['text']}\n")
    
    context = "\n---\n".join(context_parts)
    
    # System message
    system_msg = """You are a medical AI assistant. Answer questions accurately based ONLY on the provided context.

Guidelines:
- Use ONLY information from the context provided
- If the answer is not in the context, say "I don't have enough information to answer this question"
- Cite sources by mentioning the book/chapter name
- Be concise and clinical
- Use medical terminology appropriately"""

    # User message
    user_msg = f"""Context from medical textbooks:

{context}

Question: {query}

Please provide a detailed answer based on the context above."""

    print("\n🤖 Generating answer with Grok...")
    
    # xAI API call
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "grok-2-latest",  # ✅ Updated model
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        "temperature": TEMPERATURE,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(
            XAI_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
            error_msg = response.json().get("error", response.text)
            raise Exception(f"xAI API Error {response.status_code}: {error_msg}")
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    except requests.exceptions.Timeout:
        return "⚠️ Request timed out. Please try again."
    except Exception as e:
        raise Exception(f"xAI API Error: {str(e)}")

# =========================================================
# DISPLAY RESULTS
# =========================================================
def display_results(query: str, chunks: list, answer: str):
    """Pretty print results"""
    print("\n" + "="*80)
    print("📊 RAG PIPELINE RESULTS")
    print("="*80)
    print(f"\n❓ QUERY: {query}\n")
    
    print("📚 RETRIEVED CHUNKS:")
    print("-"*80)
    for chunk in chunks:
        print(f"\n[{chunk['rank']}] Score: {chunk['score']:.4f} | Type: {chunk['chunk_type']}")
        print(f"    Source: {chunk['book_name']} - {chunk['chapter_title']}")
        print(f"    Pages: {chunk['page_range']} | Category: {chunk['category']}")
        print(f"    Text: {chunk['text'][:200]}...")
    
    print("\n" + "-"*80)
    print("💡 GENERATED ANSWER:")
    print("-"*80)
    print(answer)
    print("\n" + "="*80)

# =========================================================
# MAIN RAG PIPELINE
# =========================================================
def run_rag_pipeline(query: str, top_k: int = TOP_K):
    """Complete RAG pipeline: Retrieve + Generate"""
    
    # Step 1: Retrieve
    chunks = retrieve_chunks(query, top_k)
    
    if not chunks:
        print("\n❌ No relevant chunks found!")
        return None
    
    # Step 2: Generate
    answer = generate_answer(query, chunks)
    
    # Step 3: Display
    display_results(query, chunks, answer)
    
    return {
        "query": query,
        "chunks": chunks,
        "answer": answer
    }

# =========================================================
# TEST QUERIES
# =========================================================
TEST_QUERIES = [
    # Screening questions
    "What is the recommended screening age for cervical cancer?",
    "What are the HPV vaccination guidelines?",
    "How often should women get mammograms?",
    
    # Clinical questions
    "What are the risk factors for ovarian cancer?",
    "What is the FIGO staging system for cervical cancer?",
    "What are the treatment options for endometrial cancer?",
    
    # Epidemiology
    "What is the incidence of breast cancer in women?",
    "What percentage of ovarian cancers are hereditary?",
    
    # Specific medical terms
    "What is Lynch syndrome and its cancer risk?",
    "Explain BRCA1 and BRCA2 mutations",
]

# =========================================================
# INTERACTIVE MODE
# =========================================================
def interactive_mode():
    """Interactive Q&A session"""
    print("\n🎯 RAG PIPELINE - INTERACTIVE MODE")
    print("="*80)
    print("Type your medical questions. Type 'exit' to quit.\n")
    
    while True:
        query = input("❓ Your question: ").strip()
        
        if query.lower() in ['exit', 'quit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if not query:
            print("⚠️  Please enter a question!\n")
            continue
        
        try:
            run_rag_pipeline(query)
        except Exception as e:
            print(f"\n❌ Error: {e}\n")

# =========================================================
# BATCH TEST MODE
# =========================================================
def batch_test_mode():
    """Test with predefined queries"""
    print("\n🧪 RAG PIPELINE - BATCH TEST MODE")
    print("="*80)
    print(f"Running {len(TEST_QUERIES)} test queries...\n")
    
    results = []
    
    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}/{len(TEST_QUERIES)}")
        print(f"{'='*80}")
        
        try:
            result = run_rag_pipeline(query)
            results.append(result)
        except Exception as e:
            print(f"\n❌ Error processing query: {e}")
            continue
        
        input("\nPress Enter to continue to next test...")
    
    # Summary
    print("\n" + "="*80)
    print("📊 BATCH TEST SUMMARY")
    print("="*80)
    print(f"Total queries tested: {len(TEST_QUERIES)}")
    print(f"Successful: {len(results)}")
    print(f"Failed: {len(TEST_QUERIES) - len(results)}")
    print("="*80)

# =========================================================
# QUICK TEST
# =========================================================
def quick_test():
    """Quick single query test"""
    test_query = "What are the screening guidelines for cervical cancer?"
    print("\n🚀 QUICK TEST MODE")
    print("="*80)
    run_rag_pipeline(test_query)

# =========================================================
# CHECK COLLECTION
# =========================================================
def check_collection():
    """Verify collection status"""
    print("\n🔍 CHECKING QDRANT COLLECTION")
    print("="*80)
    
    try:
        collection_info = qdrant_client.get_collection(COLLECTION_NAME)
        print(f"✅ Collection: {COLLECTION_NAME}")
        print(f"📊 Total vectors: {collection_info.points_count}")
        print(f"📐 Vector dimension: {collection_info.config.params.vectors.size}")
        print(f"📏 Distance metric: {collection_info.config.params.vectors.distance}")
        print("="*80)
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        print("="*80)
        return False

# =========================================================
# MAIN MENU
# =========================================================
def main():
    """Main entry point with menu"""
    
    # Check collection first
    if not check_collection():
        print("\n❌ Collection check failed! Exiting...")
        return
    
    print("\n" + "="*80)
    print("🏥 MEDICAL RAG PIPELINE - TEST SUITE")
    print("="*80)
    print("\nChoose a test mode:")
    print("1. Quick Test (single query)")
    print("2. Interactive Mode (ask multiple questions)")
    print("3. Batch Test (run all test queries)")
    print("4. Exit")
    print("="*80)
    
    while True:
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == "1":
            quick_test()
        elif choice == "2":
            interactive_mode()
        elif choice == "3":
            batch_test_mode()
        elif choice == "4":
            print("\n👋 Goodbye!")
            break
        else:
            print("⚠️  Invalid choice! Please select 1-4.")

# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    main()