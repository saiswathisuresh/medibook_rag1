from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Literal
from datetime import datetime
import os, requests, re
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from fastembed import TextEmbedding

load_dotenv()

router = APIRouter()

GROK_API_KEY = os.getenv("GROK_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")

COLLECTION_NAME = "medical_chunks"
EMBEDDING_MODEL = "BAAI/bge-small-en"
GROK_MODEL = "grok-3"
GROK_URL = "https://api.x.ai/v1/chat/completions"

qdrant = QdrantClient(url=QDRANT_URL)
embedder = TextEmbedding(model_name=EMBEDDING_MODEL)

class Question(BaseModel):
    question_number: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: Literal["A", "B", "C", "D"]
    marks: int

class ExamRequest(BaseModel):
    exam_name: str
    topic: str
    num_questions: int = 10
    marks_per_question: int = 2

class ExamResponse(BaseModel):
    exam_name: str
    topic: str
    date: str
    total_questions: int
    total_marks: int
    questions: List[Question]

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
    r = requests.post(GROK_URL, headers=headers, json=payload)
    if r.status_code != 200:
        return None
    return r.json()["choices"][0]["message"]["content"]

@router.post("/generate-exam", response_model=ExamResponse)
async def generate_exam(req: ExamRequest):
    prompt = f"""
Create {req.num_questions} MCQs on topic {req.topic}.
Format:
Q1...
A)
B)
C)
D)
Correct Answer: A
"""
    ai = ask_grok(prompt)
    if not ai:
        raise HTTPException(status_code=500, detail="AI failed")

    questions = []
    blocks = re.split(r"Q\d+\.", ai)[1:]

    for i, b in enumerate(blocks, 1):
        opts = re.findall(r"[A-D]\)\s*(.+)", b)
        ans = re.search(r"Correct Answer:\s*([A-D])", b)
        if len(opts) == 4 and ans:
            questions.append(Question(
                question_number=i,
                question_text=b.split("A)")[0].strip(),
                option_a=opts[0],
                option_b=opts[1],
                option_c=opts[2],
                option_d=opts[3],
                correct_answer=ans.group(1),
                marks=req.marks_per_question
            ))

    return ExamResponse(
        exam_name=req.exam_name,
        topic=req.topic,
        date=datetime.now().strftime("%Y-%m-%d"),
        total_questions=len(questions),
        total_marks=len(questions) * req.marks_per_question,
        questions=questions
    )
