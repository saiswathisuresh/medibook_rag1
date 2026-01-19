from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import os
import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from fastembed import TextEmbedding
import traceback

# ----------------------------
# ENV + ROUTER
# ----------------------------
load_dotenv()
router = APIRouter()

print("🚀 chat_routes.py loaded")

# ----------------------------
# ENV VARIABLES
# ----------------------------
GROK_API_KEY = os.getenv("GROK_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")

print("🔑 GROK_API_KEY exists:", bool(GROK_API_KEY))
print("📦 QDRANT_URL:", QDRANT_URL)

COLLECTION_NAME = "medical_chunks"
EMBEDDING_MODEL = "BAAI/bge-small-en"
GROK_MODEL = "grok-3"
GROK_URL = "https://api.x.ai/v1/chat/completions"

# ----------------------------
# CLIENTS
# ----------------------------
try:
    qdrant = QdrantClient(url=QDRANT_URL)
    print("✅ Qdrant client initialized")
except Exception as e:
    print("❌ Qdrant init failed:", e)

try:
    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    print("✅ Embedder loaded:", EMBEDDING_MODEL)
except Exception as e:
    print("❌ Embedder load failed:", e)

# ----------------------------
# MODELS
# ----------------------------
class ChatRequest(BaseModel):
    question: str
    top_k: int = 5
    max_tokens: int = 1000
    temperature: float = 0.2

class SourceChunk(BaseModel):
    text: str
    score: float
    source: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    found_relevant_content: bool

# ----------------------------
# GROK CALL
# ----------------------------
def ask_grok(prompt: str, max_tokens: int, temperature: float):
    print("\n🤖 Calling Grok...")
    print("➡️ Prompt length:", len(prompt))
    print("➡️ Max tokens:", max_tokens, "Temp:", temperature)

    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:
        r = requests.post(
            GROK_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        print("📡 Grok status:", r.status_code)
        print("📡 Grok raw response:", r.text[:500])  # First 500 chars only

        if r.status_code != 200:
            return None

        data = r.json()
        content = data["choices"][0]["message"]["content"]

        # Grok content may be list or string
        if isinstance(content, list):
            content = content[0].get("text", "")

        return content

    except Exception as e:
        print("❌ Grok call exception:")
        traceback.print_exc()
        return None

# ----------------------------
# QDRANT SEARCH - ✅ FIXED
# ----------------------------
# ----------------------------
# QDRANT SEARCH - ULTIMATE FIX
# ----------------------------
def hybrid_search(query: str, top_k: int):
    print("\n🔎 Hybrid search started")
    print("➡️ Query:", query)
    print("➡️ top_k:", top_k)

    try:
        print("⏳ Generating embedding...")
        
        # ✅ ULTIMATE FIX - Multiple fallback methods
        vector = None
        
        # Method 1: Try direct conversion
        try:
            embedding_result = embedder.embed([query])
            
            # Check type
            print(f"Embedding result type: {type(embedding_result)}")
            
            # If it's a generator, convert
            if hasattr(embedding_result, '__iter__') and not isinstance(embedding_result, (list, tuple, str)):
                print("Converting generator to list...")
                embeddings_list = list(embedding_result)
                embedding = embeddings_list[0]
            else:
                # Direct indexing
                embedding = embedding_result[0]
            
            # Convert to list
            if hasattr(embedding, 'tolist'):
                vector = embedding.tolist()  # NumPy array
            elif hasattr(embedding, '__iter__'):
                vector = list(embedding)  # Iterable
            else:
                vector = [float(x) for x in embedding]  # Force convert
                
        except Exception as e1:
            print(f"⚠️ Method 1 failed: {e1}")
            
            # Method 2: Force double list conversion
            try:
                print("Trying method 2...")
                gen = embedder.embed([query])
                arr = list(list(gen)[0])
                vector = [float(x) for x in arr]
            except Exception as e2:
                print(f"⚠️ Method 2 failed: {e2}")
                
                # Method 3: Iterate manually
                try:
                    print("Trying method 3...")
                    gen = embedder.embed([query])
                    for item in gen:
                        vector = [float(x) for x in item]
                        break
                except Exception as e3:
                    print(f"❌ All methods failed!")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Embedding generation failed: {e1}, {e2}, {e3}"
                    )
        
        if vector is None or len(vector) == 0:
            raise HTTPException(status_code=500, detail="Failed to generate embedding vector")
            
        print(f"✅ Vector generated, dimension: {len(vector)}")

        # Search Qdrant
        print("⏳ Searching Qdrant...")
        results = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=top_k
        )

        print(f"✅ Found {len(results)} results")
        return results

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Search completely failed:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
# ----------------------------
# CHAT ENDPOINT
# ----------------------------
@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    print("\n" + "="*50)
    print("📩 /api/chat endpoint called")
    print(f"➡️ Question: {req.question}")
    print(f"➡️ top_k: {req.top_k}, max_tokens: {req.max_tokens}, temp: {req.temperature}")
    print("="*50)

    try:
        # Step 1: Search Qdrant
        print("\n📍 STEP 1: Searching medical knowledge base...")
        results = hybrid_search(req.question, req.top_k)

        if not results:
            print("⚠️ No relevant content found in Qdrant")
            return ChatResponse(
                answer="No relevant content found in the medical knowledge base.",
                sources=[],
                found_relevant_content=False
            )

        # Step 2: Extract context
        print("\n📍 STEP 2: Extracting context from search results...")
        context = []
        sources = []

        for idx, r in enumerate(results):
            payload = r.payload or {}
            text = payload.get("content", "")
            
            if text:
                context.append(text)
                print(f"  [{idx+1}] Score: {r.score:.3f} | Length: {len(text)} chars")
                
                sources.append(
                    SourceChunk(
                        text=text[:300] + "..." if len(text) > 300 else text,
                        score=round(r.score, 3),
                        source="vector"
                    )
                )

        print(f"✅ Extracted {len(context)} context chunks")

        # Step 3: Build prompt
        print("\n📍 STEP 3: Building prompt for Grok AI...")
        combined_context = "\n\n".join(context)
        
        prompt = f"""You are a medical expert assistant. Answer the following question based ONLY on the provided medical context. Do not use external knowledge.

Medical Context:
{combined_context}

Question: {req.question}

Instructions:
- Provide a clear, accurate medical answer
- Use information from the context above
- If the context doesn't contain enough information, say so
- Be concise but thorough

Answer:"""

        print(f"✅ Prompt built, length: {len(prompt)} chars")

        # Step 4: Call Grok
        print("\n📍 STEP 4: Calling Grok AI for answer generation...")
        answer = ask_grok(prompt, req.max_tokens, req.temperature)

        if not answer:
            print("❌ Grok returned empty/null answer")
            raise HTTPException(status_code=500, detail="AI service failed to generate answer")

        print(f"✅ Answer received, length: {len(answer)} chars")

        # Step 5: Return response
        print("\n📍 STEP 5: Returning final response...")
        response = ChatResponse(
            answer=answer.strip(),
            sources=sources,
            found_relevant_content=True
        )
        
        print("✅ Chat request completed successfully!")
        print("="*50 + "\n")
        
        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        # Catch-all for unexpected errors
        print("\n" + "🔥"*25)
        print("CRITICAL ERROR IN CHAT ENDPOINT")
        print("🔥"*25)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        traceback.print_exc()
        print("🔥"*25 + "\n")
        
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {type(e).__name__} - {str(e)}"
        )