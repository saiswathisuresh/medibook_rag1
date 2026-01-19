import json
import re
import hashlib
from pathlib import Path
from datetime import datetime

# ================= PATHS =================
BASE_DIR = Path(__file__).resolve().parent.parent
STRUCTURES_DIR = BASE_DIR / "data" / "structures"
CHUNKS_DIR = BASE_DIR / "data" / "chunks"

STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# ============ CHUNKING CONFIG ============
CHUNK_CONFIG = {
    "chunk_size": 512,
    "chunk_overlap": 128,
    "min_chunk_size": 100,
}

# ============ REGEX ============
TABLE_REGEX = re.compile(
    r'^Table\s+\d+(?:\.\d+)?[:\.\s]+(.+)$',
    re.IGNORECASE | re.MULTILINE
)

FIGURE_REGEX = re.compile(
    r'^Figure\s+\d+',
    re.IGNORECASE | re.MULTILINE
)

# ============ HELPERS ============
def generate_book_id(name: str) -> str:
    h = hashlib.sha256(name.encode()).hexdigest()
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return "".join(chars[int(h[i:i+2], 16) % len(chars)] for i in range(0, 42, 2))

def estimate_tokens(text: str) -> int:
    """Token estimation for RAG systems"""
    return int(len(text.split()) * 1.3)

def clean_text(text: str) -> str:
    """Clean text while preserving structure"""
    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove trailing/leading whitespace
    text = text.strip()
    return text

def detect_chunk_type(text: str) -> str:
    """
    Detect chunk type for RAG filtering
    """
    text_head = text[:400]
    
    # Check for tables
    if TABLE_REGEX.search(text_head):
        return "table"
    
    # Check for figures
    if FIGURE_REGEX.search(text_head):
        return "figure"
    
    return "content"

def split_sentences(text: str):
    """Smart sentence splitting for semantic chunking"""
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if s.strip()]

def semantic_chunks(text: str, target_size: int, overlap: int):
    """
    Create semantic chunks with overlap
    RAG-optimized: preserves sentence boundaries
    """
    sentences = split_sentences(text)
    chunks = []
    buffer = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = estimate_tokens(sentence)
        
        # If adding this sentence exceeds target, save current chunk
        if current_tokens + sentence_tokens > target_size and buffer:
            chunks.append(" ".join(buffer))
            
            # Keep last few sentences for overlap
            overlap_sentences = []
            overlap_tokens = 0
            for s in reversed(buffer):
                s_tokens = estimate_tokens(s)
                if overlap_tokens + s_tokens <= overlap:
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tokens
                else:
                    break
            
            buffer = overlap_sentences
            current_tokens = overlap_tokens
        
        buffer.append(sentence)
        current_tokens += sentence_tokens

    # Add remaining buffer
    if buffer:
        chunks.append(" ".join(buffer))
    
    return chunks

# ============ CORE ============
def process_single_book(structure_file: Path):
    print(f"\n📘 Processing: {structure_file.name}")

    with open(structure_file, encoding="utf-8") as f:
        s = json.load(f)

    book_name = s.get("book_name") or s.get("book") or s.get("book_id") or structure_file.stem
    category = s.get("category", "unknown")
    has_chapters = s.get("has_chapters", False)

    book_id = generate_book_id(book_name)
    all_chunks = []
    chunk_id = 1

    # Get chapters or sections
    sections = s.get("chapters") if has_chapters else s.get("sections", [])

    for sec in sections:
        # Get CLEANED text from structure_builder
        text = clean_text(sec.get("full_text", ""))
        
        # Skip empty sections
        if not text or len(text.strip()) < CHUNK_CONFIG["min_chunk_size"]:
            print(f"   ⏭️  Skipped empty section: {sec.get('title', 'Unknown')}")
            continue

        # Create semantic chunks
        raw_chunks = semantic_chunks(
            text,
            CHUNK_CONFIG["chunk_size"],
            CHUNK_CONFIG["chunk_overlap"]
        )

        # Process chunks
        for idx, chunk_text in enumerate(raw_chunks, 1):
            # Skip too small chunks
            if len(chunk_text.strip()) < CHUNK_CONFIG["min_chunk_size"]:
                continue

            ctype = detect_chunk_type(chunk_text)

            meta = {
                "book_id": book_id,
                "book_name": book_name,
                "category": category,
                "chunk_id": f"{book_id}_chunk_{chunk_id}",
                "chunk_type": ctype,
                "chapter_title": sec.get("title"),
                "chapter_number": sec.get("chapter_number") or sec.get("section_number"),
                "page_range": f"{sec.get('start_page', 0)}-{sec.get('end_page', 0)}",
                "chunk_index": idx,
                "has_overlap": idx > 1,
            }

            # Mark tables for special handling
            if ctype == "table":
                meta["special_handling"] = "table"

            all_chunks.append({
                "text": chunk_text,
                "metadata": meta,
                "token_count": estimate_tokens(chunk_text),
                "char_count": len(chunk_text)
            })

            chunk_id += 1

    # Handle references section separately
    if s.get("references"):
        ref_section = s["references"]
        ref_text = clean_text(ref_section.get("full_text", ""))
        
        if ref_text and len(ref_text) >= CHUNK_CONFIG["min_chunk_size"]:
            ref_chunks = semantic_chunks(
                ref_text,
                CHUNK_CONFIG["chunk_size"],
                CHUNK_CONFIG["chunk_overlap"]
            )
            
            for idx, chunk_text in enumerate(ref_chunks, 1):
                if len(chunk_text.strip()) < CHUNK_CONFIG["min_chunk_size"]:
                    continue
                
                meta = {
                    "book_id": book_id,
                    "book_name": book_name,
                    "category": category,
                    "chunk_id": f"{book_id}_chunk_{chunk_id}",
                    "chunk_type": "reference",
                    "chapter_title": "References",
                    "chapter_number": None,
                    "page_range": f"{ref_section.get('start_page', 0)}-{ref_section.get('end_page', 0)}",
                    "chunk_index": idx,
                    "has_overlap": idx > 1,
                    "exclude_from_rag": True,  # Optional exclusion flag
                }
                
                all_chunks.append({
                    "text": chunk_text,
                    "metadata": meta,
                    "token_count": estimate_tokens(chunk_text),
                    "char_count": len(chunk_text)
                })
                
                chunk_id += 1

    if not all_chunks:
        print("⚠️  No chunks created")
        return None

    # Calculate statistics
    chunk_stats = {
        "total": len(all_chunks),
        "by_type": {},
        "avg_tokens": sum(c["token_count"] for c in all_chunks) // len(all_chunks),
        "avg_chars": sum(c["char_count"] for c in all_chunks) // len(all_chunks),
    }
    
    for c in all_chunks:
        ctype = c["metadata"]["chunk_type"]
        chunk_stats["by_type"][ctype] = chunk_stats["by_type"].get(ctype, 0) + 1

    # Save chunks
    out_file = CHUNKS_DIR / f"{book_id}.json"

    output = {
        "book_id": book_id,
        "book_name": book_name,
        "category": category,
        "total_chunks": len(all_chunks),
        "chunk_statistics": chunk_stats,
        "config": CHUNK_CONFIG,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "chunks": all_chunks
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✅ Created {len(all_chunks)} chunks")
    print(f"   📊 Types: {chunk_stats['by_type']}")
    print(f"   📏 Avg: {chunk_stats['avg_tokens']} tokens, {chunk_stats['avg_chars']} chars")
    print(f"   💾 Saved: {out_file.name}")
    
    return True

def process_all_books():
    files = list(STRUCTURES_DIR.glob("*_structure.json"))
    
    if not files:
        print("❌ No structure files found")
        return
    
    print("="*60)
    print("📚 RAG CHUNK BUILDER v3.0")
    print("   Uses CLEANED data from structure_builder.py")
    print("="*60)
    print(f"\n🔥 Found {len(files)} structure files\n")

    success = 0
    total_chunks = 0

    for f in sorted(files):
        try:
            if process_single_book(f):
                success += 1
                # Count chunks
                chunk_file = CHUNKS_DIR / f"{generate_book_id(f.stem)}.json"
                if chunk_file.exists():
                    with open(chunk_file) as cf:
                        data = json.load(cf)
                        total_chunks += data.get("total_chunks", 0)
        except Exception as e:
            print(f"❌ Error processing {f.name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print(f"✅ COMPLETED: {success}/{len(files)} books")
    print(f"📦 Total chunks: {total_chunks}")
    print("="*60)

# ============ RUN ============
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        structure_file = Path(sys.argv[1])
        if structure_file.exists():
            process_single_book(structure_file)
        else:
            print(f"❌ File not found: {structure_file}")
    else:
        process_all_books()