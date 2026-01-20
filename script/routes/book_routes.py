from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import json
from pathlib import Path
import re

router = APIRouter()

print("=" * 50)
print("🚀 book_routes.py loaded successfully!")
print("=" * 50)

# ======================================================
# PATH DETECTION
# ======================================================
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent

possible_paths = [
    project_root / "data" / "chunks",
    Path("/home/ubuntu/medibook_rag1/data/chunks"),
    script_dir.parent / "data" / "chunks",
]

CHUNKS_FOLDER = next((p for p in possible_paths if p.exists()), project_root / "data" / "chunks")
DATA_FOLDER = CHUNKS_FOLDER.parent

# Structure files
CHAPTER_STRUCTURE_FILE = DATA_FOLDER / "chapter.json"
NON_CHAPTER_STRUCTURE_FILE = DATA_FOLDER / "non_chapter.json"

print(f"📂 DATA_FOLDER: {DATA_FOLDER}")
print(f"📂 CHUNKS_FOLDER: {CHUNKS_FOLDER}")
print(f"📂 CHUNKS_FOLDER exists: {CHUNKS_FOLDER.exists()}")
print(f"📋 Chapter structure file exists: {CHAPTER_STRUCTURE_FILE.exists()}")
print(f"📋 Non-chapter structure file exists: {NON_CHAPTER_STRUCTURE_FILE.exists()}")
print(f"📄 JSON chunk files: {len(list(CHUNKS_FOLDER.glob('*.json')))}")
if CHUNKS_FOLDER.exists():
    print(f"📋 Files found: {[f.name for f in CHUNKS_FOLDER.glob('*.json')]}")
print("=" * 50)

# ======================================================
# MODELS
# ======================================================
class Chapter(BaseModel):
    chapter_id: str
    chapter_name: str
    subheadings: List[str] = []

class Book(BaseModel):
    book_id: str
    book_name: str
    title: str
    has_chapters: bool
    chapters: List[Chapter] = []

class BooksResponse(BaseModel):
    total_books: int
    books: List[Book]

# ======================================================
# HELPER FUNCTIONS
# ======================================================
def load_chapter_structure():
    """Load chapter structure from chapter.json"""
    try:
        if CHAPTER_STRUCTURE_FILE.exists():
            print(f"📖 Loading chapter structure from: {CHAPTER_STRUCTURE_FILE}")
            with open(CHAPTER_STRUCTURE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"   ✅ Loaded: {data.get('book_title', 'Unknown')}")
                print(f"   ✅ Chapters: {len(data.get('chapters', []))}")
                return data
        else:
            print(f"⚠️ Chapter structure file not found: {CHAPTER_STRUCTURE_FILE}")
    except Exception as e:
        print(f"❌ Chapter structure load failed: {e}")
        import traceback
        traceback.print_exc()
    return None

def load_non_chapter_structure():
    """Load non-chapter structure from non_chapter.json"""
    try:
        if NON_CHAPTER_STRUCTURE_FILE.exists():
            print(f"📖 Loading non-chapter structure from: {NON_CHAPTER_STRUCTURE_FILE}")
            with open(NON_CHAPTER_STRUCTURE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"   ✅ Loaded: {data.get('title', 'Unknown')}")
                print(f"   ✅ Headings: {len(data.get('headings', []))}")
                return data
        else:
            print(f"⚠️ Non-chapter structure file not found: {NON_CHAPTER_STRUCTURE_FILE}")
    except Exception as e:
        print(f"❌ Non-chapter structure load failed: {e}")
        import traceback
        traceback.print_exc()
    return None

def extract_book_id_from_filename(filename: str) -> Optional[str]:
    """Extract book_id from filename pattern"""
    match = re.search(r'(?:non_chapter_|chapter_)([A-Za-z0-9]+)_chunks\.json', filename)
    if match:
        return match.group(1)
    return None

# ======================================================
# CORE LOADER
# ======================================================
def load_books_from_chunks():
    print("\n🔍 Starting load_books_from_chunks()...")
    
    if not CHUNKS_FOLDER.exists():
        print(f"❌ Chunks folder does not exist: {CHUNKS_FOLDER}")
        raise HTTPException(status_code=500, detail=f"Chunks folder not found")

    # Load structure files
    chapter_structure = load_chapter_structure()
    non_chapter_structure = load_non_chapter_structure()
    
    books = []
    json_files = list(CHUNKS_FOLDER.glob("*.json"))
    print(f"\n📂 Found {len(json_files)} chunk files to process\n")

    for json_file in json_files:
        print(f"📖 Processing: {json_file.name}")
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Get book_id
            book_id = data.get("book_id")
            if not book_id and "chunks" in data:
                chunks = data.get("chunks", [])
                if chunks:
                    book_id = chunks[0].get("metadata", {}).get("book_id")
            
            if not book_id:
                book_id = extract_book_id_from_filename(json_file.name)
            
            if not book_id:
                print(f"   ❌ No book_id found, skipping\n")
                continue
            
            print(f"   └─ book_id: {book_id}")
            
            # Determine if chapter book
            is_chapter_book = json_file.name.startswith("chapter_")
            print(f"   └─ is_chapter_book: {is_chapter_book}")
            
            # Use structure file for chapter books
            if is_chapter_book and chapter_structure:
                print(f"   └─ Using chapter structure file")
                
                # Check if it has 'book_title' and 'chapters' (correct format)
                if "book_title" in chapter_structure and "chapters" in chapter_structure:
                    book_name = chapter_structure.get("book_title", "Unknown")
                    chapters_data = chapter_structure.get("chapters", [])
                    
                    # Convert structure to chapter list with subheadings
                    chapter_list = []
                    for ch in chapters_data:
                        chapter_list.append({
                            "chapter_id": str(ch.get("chapter")),
                            "chapter_name": ch.get("heading"),
                            "subheadings": ch.get("subheadings", [])
                        })
                    
                    print(f"   └─ book_name: {book_name}")
                    print(f"   └─ chapters loaded: {len(chapter_list)}")
                    
                    books.append({
                        "book_id": book_id,
                        "book_name": book_name,
                        "title": book_name,
                        "has_chapters": True,
                        "chapters": chapter_list
                    })
                    print(f"   ✅ Book added from chapter structure\n")
                    continue
                elif "title" in chapter_structure and "headings" in chapter_structure:
                    # File is swapped - use non_chapter structure instead
                    print(f"   ⚠️ chapter.json has wrong format, checking non_chapter.json")
                    if non_chapter_structure and "book_title" in non_chapter_structure:
                        book_name = non_chapter_structure.get("book_title", "Unknown")
                        chapters_data = non_chapter_structure.get("chapters", [])
                        
                        chapter_list = []
                        for ch in chapters_data:
                            chapter_list.append({
                                "chapter_id": str(ch.get("chapter")),
                                "chapter_name": ch.get("heading"),
                                "subheadings": ch.get("subheadings", [])
                            })
                        
                        print(f"   └─ book_name: {book_name}")
                        print(f"   └─ chapters loaded from non_chapter.json: {len(chapter_list)}")
                        
                        books.append({
                            "book_id": book_id,
                            "book_name": book_name,
                            "title": book_name,
                            "has_chapters": True,
                            "chapters": chapter_list
                        })
                        print(f"   ✅ Book added (using swapped file)\n")
                        continue
            
            # Use structure file for non-chapter books
            if not is_chapter_book and non_chapter_structure:
                print(f"   └─ Using non-chapter structure file")
                
                # Check format
                if "title" in non_chapter_structure and "headings" in non_chapter_structure:
                    book_name = non_chapter_structure.get("title", "Unknown")
                    headings = non_chapter_structure.get("headings", [])
                    
                    # Convert headings to chapters with subheadings
                    chapter_list = []
                    for idx, heading_obj in enumerate(headings, 1):
                        chapter_list.append({
                            "chapter_id": str(idx),
                            "chapter_name": heading_obj.get("heading"),
                            "subheadings": heading_obj.get("subheadings", [])
                        })
                    
                    print(f"   └─ book_name: {book_name}")
                    print(f"   └─ sections loaded: {len(chapter_list)}")
                    
                    books.append({
                        "book_id": book_id,
                        "book_name": book_name,
                        "title": book_name,
                        "has_chapters": len(chapter_list) > 0,
                        "chapters": chapter_list
                    })
                    print(f"   ✅ Book added from non-chapter structure\n")
                    continue
                elif "book_title" in non_chapter_structure and "chapters" in non_chapter_structure:
                    # File is swapped - use chapter structure instead
                    print(f"   ⚠️ non_chapter.json has wrong format, checking chapter.json")
                    if chapter_structure and "title" in chapter_structure:
                        book_name = chapter_structure.get("title", "Unknown")
                        headings = chapter_structure.get("headings", [])
                        
                        chapter_list = []
                        for idx, heading_obj in enumerate(headings, 1):
                            chapter_list.append({
                                "chapter_id": str(idx),
                                "chapter_name": heading_obj.get("heading"),
                                "subheadings": heading_obj.get("subheadings", [])
                            })
                        
                        print(f"   └─ book_name: {book_name}")
                        print(f"   └─ sections loaded from chapter.json: {len(chapter_list)}")
                        
                        books.append({
                            "book_id": book_id,
                            "book_name": book_name,
                            "title": book_name,
                            "has_chapters": len(chapter_list) > 0,
                            "chapters": chapter_list
                        })
                        print(f"   ✅ Book added (using swapped file)\n")
                        continue
            
            # FALLBACK: Extract from chunks (if no structure file)
            print(f"   ⚠️ No structure file available, extracting from chunks")
            
            chunks = data.get("chunks", [])
            if not chunks:
                print(f"   ❌ No chunks, skipping\n")
                continue
            
            first_meta = chunks[0].get("metadata", {})
            book_name = first_meta.get("book_name", data.get("book_name", "Unknown"))
            category = first_meta.get("category", data.get("category", ""))
            
            has_chapters = category == "chapter" or is_chapter_book
            
            # Extract chapters from chunks
            chapter_map = {}
            if has_chapters:
                for chunk in chunks:
                    meta = chunk.get("metadata", {})
                    ch_no = meta.get("chapter_number")
                    ch_title = meta.get("chapter_title")
                    
                    if ch_no and ch_title:
                        key = str(ch_no)
                        if key not in chapter_map:
                            chapter_map[key] = {
                                "chapter_id": str(ch_no),
                                "chapter_name": ch_title,
                                "subheadings": []
                            }
                print(f"   └─ chapters extracted from chunks: {len(chapter_map)}")
            
            books.append({
                "book_id": book_id,
                "book_name": book_name,
                "title": book_name,
                "has_chapters": has_chapters,
                "chapters": list(chapter_map.values())
            })
            print(f"   ✅ Book added from chunks (fallback)\n")

        except Exception as e:
            print(f"   ❌ Error: {e}\n")
            import traceback
            traceback.print_exc()

    print(f"📊 Total books loaded: {len(books)}\n")
    return books

# ======================================================
# ROUTES
# ======================================================
@router.get("", response_model=BooksResponse)
async def get_all_books(filter_type: Optional[str] = Query(None)):
    print(f"🌐 GET /api/books (filter: {filter_type})")
    books = load_books_from_chunks()

    if filter_type == "chapter":
        books = [b for b in books if b["has_chapters"]]
    elif filter_type == "non-chapter":
        books = [b for b in books if not b["has_chapters"]]

    return BooksResponse(total_books=len(books), books=books)

@router.get("/debug/structure-files")
async def debug_structure_files():
    """Debug endpoint to check structure files"""
    chapter_data = None
    non_chapter_data = None
    
    if CHAPTER_STRUCTURE_FILE.exists():
        try:
            with open(CHAPTER_STRUCTURE_FILE, "r", encoding="utf-8") as f:
                chapter_data = json.load(f)
        except Exception as e:
            chapter_data = {"error": str(e)}
    
    if NON_CHAPTER_STRUCTURE_FILE.exists():
        try:
            with open(NON_CHAPTER_STRUCTURE_FILE, "r", encoding="utf-8") as f:
                non_chapter_data = json.load(f)
        except Exception as e:
            non_chapter_data = {"error": str(e)}
    
    return {
        "chapter_structure_file": {
            "path": str(CHAPTER_STRUCTURE_FILE),
            "exists": CHAPTER_STRUCTURE_FILE.exists(),
            "data": chapter_data
        },
        "non_chapter_structure_file": {
            "path": str(NON_CHAPTER_STRUCTURE_FILE),
            "exists": NON_CHAPTER_STRUCTURE_FILE.exists(),
            "data": non_chapter_data
        }
    }

@router.get("/debug/inspect-json")
async def inspect_json():
    """Detailed inspection of JSON chunk files"""
    result = []
    
    for json_file in CHUNKS_FOLDER.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            file_info = {
                "filename": json_file.name,
                "top_level_keys": list(data.keys()),
                "format": "unknown"
            }
            
            # Detect format
            if "book_id" in data and "chunks" in data:
                file_info["format"] = "top_level_book_id"
                file_info["book_id"] = data["book_id"]
                file_info["chunks_count"] = len(data.get("chunks", []))
            elif "chunks" in data:
                file_info["format"] = "chunks_with_metadata"
                chunks = data["chunks"]
                file_info["chunks_count"] = len(chunks)
                if chunks:
                    file_info["first_metadata"] = chunks[0].get("metadata", {})
            
            result.append(file_info)
        except Exception as e:
            result.append({"filename": json_file.name, "error": str(e)})
    
    return {"files": result}

@router.get("/debug/chunks-path")
async def debug_chunks():
    json_files = list(CHUNKS_FOLDER.glob("*.json"))
    
    return {
        "chunks_folder": str(CHUNKS_FOLDER),
        "exists": CHUNKS_FOLDER.exists(),
        "json_files_count": len(json_files),
        "json_files": [f.name for f in json_files]
    }

@router.get("/{book_id}", response_model=Book)
async def get_book(book_id: str):
    books = load_books_from_chunks()
    for b in books:
        if b["book_id"] == book_id:
            return b
    raise HTTPException(status_code=404, detail="Book not found")

@router.get("/{book_id}/chapters", response_model=List[Chapter])
async def get_chapters(book_id: str):
    """Get all chapters for a specific book"""
    book = next((b for b in load_books_from_chunks() if b["book_id"] == book_id), None)

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if not book["has_chapters"]:
        raise HTTPException(status_code=400, detail="This book has no chapters")

    return book["chapters"]