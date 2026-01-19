from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import chat_routes, lesson_routes, exam_routes, book_routes
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Medical Education API",
    version="1.0.0",
    description="Unified API for Chat, Lesson Plans, Exams, and Books"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ CORRECT ROUTER CONFIGURATION
print("📍 Registering routers...")

app.include_router(
    chat_routes.router, 
    prefix="/api/chat",  # ← CHANGED!
    tags=["Chat"]
)
print("✅ Chat routes registered: /api/chat")

app.include_router(
    lesson_routes.router, 
    prefix="/api/lesson", 
    tags=["Lesson Plans"]
)
print("✅ Lesson routes registered: /api/lesson")

app.include_router(
    exam_routes.router, 
    prefix="/api/exam", 
    tags=["Exams"]
)
print("✅ Exam routes registered: /api/exam")

app.include_router(
    book_routes.router, 
    prefix="/api/books",  # ← CHANGED!
    tags=["Books"]
)
print("✅ Book routes registered: /api/books")

@app.get("/")
async def root():
    return {
        "message": "Medical Education API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "chat": "/api/chat",
            "lessons": "/api/lesson/generate-lesson-plan",
            "exams": "/api/exam/generate-exam",
            "books": "/api/books",
            "books_stats": "/api/books/stats/summary",
            "books_debug": "/api/books/debug/chunks-path"
        }
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "api_version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)