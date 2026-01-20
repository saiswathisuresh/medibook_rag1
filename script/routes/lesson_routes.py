from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os, requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from fastembed import TextEmbedding

load_dotenv()
router = APIRouter()

GROK_API_KEY = os.getenv("GROK_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
GROK_URL = "https://api.x.ai/v1/chat/completions"
COLLECTION_NAME = "medical_chunks"
EMBEDDING_MODEL = "BAAI/bge-small-en"


# ✅ Add Qdrant + Embedder
qdrant = QdrantClient(url=QDRANT_URL)
embedder = TextEmbedding(model_name=EMBEDDING_MODEL)

class LessonRequest(BaseModel):
    lesson_plan_name: str
    topic: str

class LessonResponse(BaseModel):
    lesson_plan_name: str
    content: str

def search_medical_books(topic: str, top_k: int = 10):
    """Search YOUR 200 medical books for relevant content"""
    try:
        # Convert topic to vector
        embedding_gen = embedder.embed([topic])
        embedding = list(embedding_gen)[0]
        vector = list(embedding)
        
        # Search Qdrant
        results = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=top_k
        )
        
        # Extract text from results
        context = []
        for r in results:
            text = r.payload.get("content", "")
            if text:
                context.append(text)
        
        return context
    except:
        return []

def ask_grok(prompt):
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "grok-3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 3000
    }
    r = requests.post(GROK_URL, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        return None
    return r.json()["choices"][0]["message"]["content"]

@router.post("/generate-lesson-plan", response_model=LessonResponse)
async def generate_lesson(req: LessonRequest):
    # ✅ Step 1: Search YOUR medical books
    print(f"🔍 Searching medical books for: {req.topic}")
    medical_context = search_medical_books(req.topic, top_k=10)
    
    if medical_context:
        print(f"✅ Found {len(medical_context)} relevant chunks from medical books")
        context_text = "\n\n".join(medical_context)
        
        # ✅ Step 2: Create prompt WITH your book content
        prompt = f"""Create a detailed medical lesson plan on "{req.topic}" using the following medical textbook content as reference.

Medical Textbook Content:
{context_text}

Create a structured lesson plan with:
1. Learning Objectives
2. Key Concepts
3. Detailed Explanation
4. Clinical Applications
5. Summary

Topic: {req.topic}"""
    else:
        # Fallback if no content found
        print("⚠️ No medical content found, using general knowledge")
        prompt = f"Create a detailed medical lesson plan on {req.topic}"
    
    # ✅ Step 3: Generate lesson with Grok
    content = ask_grok(prompt)
    
    if not content:
        raise HTTPException(status_code=500, detail="AI failed")

    return LessonResponse(
        lesson_plan_name=req.lesson_plan_name,
        content=content
    )