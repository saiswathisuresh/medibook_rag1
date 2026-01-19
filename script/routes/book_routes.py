from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import json
import os
from pathlib import Path

router = APIRouter()

print("=" * 50)
print("🚀 book_routes.py loaded successfully!")
print("=" * 50)

# Auto-detect correct path
script_dir = Path(__file__).parent  # routes folder
project_root = script_dir.parent.parent  # medibook_rag folder

# Try multiple possible locations
possible_paths = [
    project_root / "data" / "chunks",  # Standard location
    Path("/home/ubuntu/medibook_rag/data/chunks"),  # Absolute path
    script_dir.parent / "data" / "chunks",  # scripts/../data/chunks
]

CHUNKS_FOLDER = None
for path in possible_paths:
    if path.exists():
        CHUNKS_FOLDER = path
        break

if CHUNKS_FOLDER is None:
    CHUNKS_FOLDER = project_root / "data" / "chunks"

METADATA_FILE = CHUNKS_FOLDER.parent / "books_metadata.json"

print(f"📂 CHUNKS_FOLDER: {CHUNKS_FOLDER}")
print(f"📋 METADATA_FILE: {METADATA_FILE}")
print(f"✅ Exists: {CHUNKS_FOLDER.exists()}")
if CHUNKS_FOLDER.exists():
    json_files = list(CHUNKS_FOLDER.glob("*.json"))
    print(f"📄 JSON files found: {len(json_files)}")
    for f in json_files[:3]:
        print(f"   - {f.name}")
print("=" * 50)

def load_metadata():
    """Load books metadata (chapter/non-chapter info)"""
    try:
        if METADATA_FILE.exists():
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"chapter_books": [], "non_chapter_books": []}
    except:
        return {"chapter_books": [], "non_chapter_books": []}

class Chapter(BaseModel):
    chapter_id: str
    chapter_name: str

class Book(BaseModel):
    book_id: str
    book_name: str
    title: str
    has_chapters: bool
    chapters: List[Chapter] = []

class BooksResponse(BaseModel):
    total_books: int
    books: List[Book]

def load_books_from_chunks():
    """Chunks folder la irunthu books data dynamically load pannum"""
    try:
        if not CHUNKS_FOLDER.exists():
            raise HTTPException(
                status_code=500, 
                detail=f"Chunks folder not found at {CHUNKS_FOLDER}"
            )
        
        metadata = load_metadata()
        chapter_books_list = metadata.get("chapter_books", [])
        books = []
        
        for json_file in CHUNKS_FOLDER.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    if isinstance(data, list) and len(data) > 0:
                        # Extract unique book_ids
                        book_ids = set()
                        for chunk in data:
                            if isinstance(chunk, dict) and "book_id" in chunk:
                                book_ids.add(chunk["book_id"])
                        
                        if book_ids:
                            book_id = list(book_ids)[0]
                            book_name = json_file.stem.replace("_chunks", "")
                            has_chapters = book_name in chapter_books_list
                            
                            # ✅ FIXED: Extract chapters based on structured data
                            chapters_list = []
                            if has_chapters:
                                # Build chapter map from structured data
                                chapter_map = {}
                                
                                for chunk in data:
                                    if not isinstance(chunk, dict):
                                        continue
                                    
                                    ch_id = chunk.get("chapter_id")
                                    if not ch_id:
                                        continue
                                    
                                    # Skip AUTO_CH chapters (they're meaningless)
                                    if ch_id.startswith("AUTO_CH"):
                                        continue
                                    
                                    # Get section/heading as chapter name
                                    section = chunk.get("section", "").strip()
                                    
                                    # Skip if section is "General" or empty
                                    if not section or section.lower() == "general":
                                        continue
                                    
                                    # Create unique chapter entry
                                    chapter_key = f"{ch_id}_{section}"
                                    
                                    if chapter_key not in chapter_map:
                                        chapter_map[chapter_key] = {
                                            "chapter_id": ch_id,
                                            "chapter_name": section
                                        }
                                
                                chapters_list = list(chapter_map.values())[:100]
                                
                                # ✅ FALLBACK: If no chapters found, create generic ones from chapter_ids
                                if len(chapters_list) == 0:
                                    unique_chapters = set()
                                    for chunk in data:
                                        if isinstance(chunk, dict):
                                            ch_id = chunk.get("chapter_id")
                                            if ch_id and not ch_id.startswith("AUTO_CH") and ch_id not in unique_chapters:
                                                unique_chapters.add(ch_id)
                                                chapters_list.append({
                                                    "chapter_id": ch_id,
                                                    "chapter_name": f"Chapter {ch_id.replace('ch_', '').replace('CH_', '')}"
                                                })
                                                if len(chapters_list) >= 100:
                                                    break
                            
                            # Create book object
                            book = {
                                "book_id": book_id,
                                "book_name": book_name,
                                "title": book_name.replace("_", " ").replace("-", " ").title(),
                                "has_chapters": has_chapters,
                                "chapters": chapters_list
                            }
                            
                            books.append(book)
                    
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"❌ Error in {json_file.name}: {e}")
                continue
        
        return books
        
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading books: {str(e)}")

@router.get("", response_model=BooksResponse)
async def get_all_books(
    filter_type: Optional[str] = Query(None, description="Filter: 'chapter' or 'non-chapter'")
):
    """
    Get all books or filter by type
    
    Parameters:
    - filter_type: 'chapter', 'non-chapter', or None (all books)
    """
    try:
        all_books = load_books_from_chunks()
        filtered_books = all_books
        
        if filter_type == "chapter":
            filtered_books = [book for book in all_books if book.get("has_chapters", False)]
        elif filter_type == "non-chapter":
            filtered_books = [book for book in all_books if not book.get("has_chapters", False)]
        
        return BooksResponse(
            total_books=len(filtered_books),
            books=filtered_books
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{book_id}", response_model=Book)
async def get_book_by_id(book_id: str):
    """Get book details by book_id"""
    try:
        all_books = load_books_from_chunks()
        book = next((b for b in all_books if b["book_id"] == book_id), None)
        
        if not book:
            raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
        
        return book
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/name/{book_name}", response_model=Book)
async def get_book_by_name(book_name: str):
    """Get book details by book_name"""
    try:
        all_books = load_books_from_chunks()
        book = next((b for b in all_books if b["book_name"] == book_name), None)
        
        if not book:
            raise HTTPException(status_code=404, detail=f"Book '{book_name}' not found")
        
        return book
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{book_id}/chapters", response_model=List[Chapter])
async def get_book_chapters(book_id: str):
    """Get all chapters of a specific book"""
    try:
        all_books = load_books_from_chunks()
        book = next((b for b in all_books if b["book_id"] == book_id), None)
        
        if not book:
            raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
        
        if not book.get("has_chapters", False):
            raise HTTPException(
                status_code=400, 
                detail=f"Book '{book.get('title', book_id)}' does not have chapters"
            )
        
        return book.get("chapters", [])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/summary")
async def get_books_summary():
    """Get statistics about all books"""
    try:
        all_books = load_books_from_chunks()
        chapter_books = [b for b in all_books if b.get("has_chapters", False)]
        non_chapter_books = [b for b in all_books if not b.get("has_chapters", False)]
        
        return {
            "total_books": len(all_books),
            "chapter_books_count": len(chapter_books),
            "non_chapter_books_count": len(non_chapter_books),
            "chapter_books": [
                {"book_id": b["book_id"], "book_name": b["book_name"], "title": b["title"]} 
                for b in chapter_books
            ],
            "non_chapter_books": [
                {"book_id": b["book_id"], "book_name": b["book_name"], "title": b["title"]} 
                for b in non_chapter_books
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/chunks-path")
async def debug_chunks_path():
    """Debug: Check chunks folder path and files"""
    return {
        "chunks_folder": str(CHUNKS_FOLDER),
        "exists": CHUNKS_FOLDER.exists(),
        "json_files_count": len(list(CHUNKS_FOLDER.glob("*.json"))) if CHUNKS_FOLDER.exists() else 0,
        "json_files": [f.name for f in CHUNKS_FOLDER.glob("*.json")] if CHUNKS_FOLDER.exists() else []
    }