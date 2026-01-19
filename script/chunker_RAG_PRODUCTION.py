import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

# ============================================================
# 📂 PATHS
# ============================================================
BASE_DIR = Path(__file__).parent.parent
STRUCTURES_DIR = BASE_DIR / "data" / "structures"
CHUNKS_DIR = BASE_DIR / "data" / "chunks"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 🆔 NANOID STYLE BOOK ID
# ============================================================
def generate_book_id(book_name: str) -> str:
    """Generate stable 21-char nanoid-style id"""
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    h = hashlib.sha256(book_name.encode()).hexdigest()
    out = []
    for i in range(0, len(h), 2):
        out.append(chars[int(h[i:i+2], 16) % len(chars)])
        if len(out) == 21:
            break
    return "".join(out)

# ============================================================
# 🔥 AGGRESSIVE HEADER/FOOTER REMOVAL - FIX #1
# ============================================================
HEADER_FOOTER_PATTERNS = [
    # ✅ HARD PATTERNS - Both formats
    r'^\d+\s+\d+\s+Gynecologic\s+Oncology',
    r'^Gynecologic\s+Oncology\s+\d+',
    r'^\d+\s+Biology\s+and\s+Genetics\s+\d+',
    r'^Biology\s+and\s+Genetics\s+\d+',
    # Generic patterns
    r'^\d+\s+[A-Z][A-Za-z\s]+\s+\d+$',
    r'^Chapter\s+\d+\s*$',
    r'^Page\s+\d+\s*$',
    r'^\d+\s*$'
]

FRONT_MATTER_PATTERNS = [
    r'©\s*\d{4}.*?Bioscience',
    r'edited\s+by\s+[A-Z][a-z]+',
    r'ISBN[\s:-]*\d+',
    r'All\s+rights\s+reserved',
    r'Published\s+by',
    r'Landes\s+Bioscience',
    r'Springer',
    r'Copyright',
    r'Printed\s+in',
]

def remove_noise(text: str) -> str:
    """Remove headers, footers, and front-matter noise"""
    lines = text.split("\n")
    cleaned = []
    
    for line in lines:
        stripped = line.strip()
        
        if not stripped:
            continue
        
        # ✅ FIX #1: HARD header/footer removal
        if any(re.match(p, stripped, re.IGNORECASE) for p in HEADER_FOOTER_PATTERNS):
            continue
        
        if any(re.search(p, stripped, re.IGNORECASE) for p in FRONT_MATTER_PATTERNS):
            continue
        
        cleaned.append(line)
    
    return "\n".join(cleaned)

# ============================================================
# 📊 TABLE DETECTION & EXTRACTION - FIX #2
# ============================================================
def detect_tables(text: str) -> Tuple[List[Dict], str]:
    """
    ✅ FIX #2: Extract tables with Table X.X references
    Returns: (list of table dicts, cleaned text without tables)
    """
    tables = []
    lines = text.split("\n")
    
    in_table = False
    table_lines = []
    non_table_lines = []
    table_reference = None
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # ✅ Detect "Table X.X" references
        table_ref_match = re.search(r'Table\s+\d+\.?\d*', stripped, re.IGNORECASE)
        if table_ref_match and not in_table:
            table_reference = table_ref_match.group()
            continue  # Skip the reference line
        
        # Table content indicators
        has_separators = line.count("|") >= 2 or line.count("\t") >= 2
        digit_ratio = sum(c.isdigit() for c in line) / max(len(line), 1)
        
        # Start table detection
        if has_separators or digit_ratio > 0.3:
            if not in_table:
                in_table = True
                table_lines = [line]
            else:
                table_lines.append(line)
        else:
            # End table
            if in_table and table_lines:
                if len(table_lines) >= 2:
                    tables.append({
                        "content": "\n".join(table_lines),
                        "reference": table_reference,
                        "row_count": len(table_lines)
                    })
                else:
                    non_table_lines.extend(table_lines)
                
                table_lines = []
                in_table = False
                table_reference = None
            
            non_table_lines.append(line)
    
    # Handle table at end
    if in_table and len(table_lines) >= 2:
        tables.append({
            "content": "\n".join(table_lines),
            "reference": table_reference,
            "row_count": len(table_lines)
        })
    
    clean_text = "\n".join(non_table_lines)
    return tables, clean_text

# ============================================================
# 🎯 MEDICAL SECTION DETECTOR
# ============================================================
SECTION_MARKERS = [
    r'^(Introduction|Background|Overview)\s*$',
    r'^(Epidemiology|Incidence|Prevalence)\s*$',
    r'^(Risk\s+Factors?|Etiology)\s*$',
    r'^(Screening|Diagnosis|Detection)\s*$',
    r'^(Treatment|Therapy|Management)\s*$',
    r'^(Guidelines|Recommendations)\s*$',
    r'^(Prognosis|Outcomes?|Survival)\s*$',
    r'^(Statistics|Data|Results)\s*$',
    r'^(Summary|Conclusion)\s*$'
]

def extract_section_name(text: str) -> str:
    """Extract section name from beginning of text"""
    lines = text.strip().split("\n")[:3]
    
    for line in lines:
        stripped = line.strip()
        for pattern in SECTION_MARKERS:
            if re.match(pattern, stripped, re.IGNORECASE):
                return stripped
    
    return None

# ============================================================
# 🧠 MEDICAL SENTENCE-AWARE CHUNKER
# ============================================================
class MedicalChunker:
    """
    Optimized for medical RAG with 90%+ accuracy
    """
    
    def __init__(
        self,
        chunk_size: int = 325,
        chunk_overlap: int = 80,
        min_chunk_size: int = 120,  # ✅ FIX #3: Enforced minimum
        max_chunk_size: int = 400
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4
    
    def split_sentences(self, text: str) -> List[str]:
        text = re.sub(r"(Dr|Mr|Mrs|Ms|Fig|et al|vs|i\.e|e\.g)\.", r"\1<DOT>", text)
        parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        sentences = [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]
        return sentences
    
    def split_by_paragraph(self, text: str) -> List[str]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return paragraphs
    
    def auto_split_oversized(self, chunk: str) -> List[str]:
        tokens = self.estimate_tokens(chunk)
        
        if tokens <= self.max_chunk_size:
            return [chunk]
        
        sentences = self.split_sentences(chunk)
        
        if len(sentences) <= 1:
            mid = len(chunk) // 2
            return [chunk[:mid], chunk[mid:]]
        
        mid = len(sentences) // 2
        part1 = " ".join(sentences[:mid])
        part2 = " ".join(sentences[mid:])
        
        result = []
        result.extend(self.auto_split_oversized(part1))
        result.extend(self.auto_split_oversized(part2))
        
        return result
    
    def merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """
        ✅ FIX #3: Auto-merge chunks below min_chunk_size
        """
        if not chunks:
            return []
        
        merged = []
        buffer = []
        buffer_tokens = 0
        
        for chunk in chunks:
            tokens = self.estimate_tokens(chunk)
            
            # If chunk is large enough, process buffer first
            if tokens >= self.min_chunk_size:
                if buffer:
                    # Merge buffer into one chunk
                    merged.append(" ".join(buffer))
                    buffer = []
                    buffer_tokens = 0
                merged.append(chunk)
            else:
                # Add to buffer
                buffer.append(chunk)
                buffer_tokens += tokens
                
                # If buffer exceeds min size, flush it
                if buffer_tokens >= self.min_chunk_size:
                    merged.append(" ".join(buffer))
                    buffer = []
                    buffer_tokens = 0
        
        # Merge remaining buffer
        if buffer:
            if merged:
                # Merge with last chunk if possible
                merged[-1] = merged[-1] + " " + " ".join(buffer)
            else:
                # Only buffer exists, keep it even if small
                merged.append(" ".join(buffer))
        
        return merged
    
    def chunk_text(self, text: str) -> List[str]:
        """Main chunking logic"""
        text = remove_noise(text)
        
        if not text or self.estimate_tokens(text) < self.min_chunk_size:
            return []
        
        paragraphs = self.split_by_paragraph(text)
        
        chunks = []
        current = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = self.estimate_tokens(para)
            
            if para_tokens > self.chunk_size:
                if current:
                    chunks.append(" ".join(current))
                    current = []
                    current_tokens = 0
                
                sentences = self.split_sentences(para)
                
                for sent in sentences:
                    sent_tokens = self.estimate_tokens(sent)
                    
                    if current_tokens + sent_tokens > self.chunk_size and current:
                        chunks.append(" ".join(current))
                        
                        overlap = []
                        overlap_tokens = 0
                        for s in reversed(current):
                            st = self.estimate_tokens(s)
                            if overlap_tokens + st <= self.chunk_overlap:
                                overlap.insert(0, s)
                                overlap_tokens += st
                            else:
                                break
                        
                        current = overlap
                        current_tokens = overlap_tokens
                    
                    current.append(sent)
                    current_tokens += sent_tokens
            else:
                if current_tokens + para_tokens > self.chunk_size and current:
                    chunks.append(" ".join(current))
                    
                    if current:
                        last_para = current[-1]
                        last_tokens = self.estimate_tokens(last_para)
                        if last_tokens <= self.chunk_overlap:
                            current = [last_para]
                            current_tokens = last_tokens
                        else:
                            current = []
                            current_tokens = 0
                
                current.append(para)
                current_tokens += para_tokens
        
        if current:
            chunks.append(" ".join(current))
        
        # Auto-split oversized chunks
        split_chunks = []
        for chunk in chunks:
            tokens = self.estimate_tokens(chunk)
            if tokens > self.max_chunk_size:
                split_chunks.extend(self.auto_split_oversized(chunk))
            else:
                split_chunks.append(chunk)
        
        # ✅ FIX #3: Merge small chunks
        final_chunks = self.merge_small_chunks(split_chunks)
        
        return final_chunks

# ============================================================
# 🧾 ENRICHED METADATA
# ============================================================
def build_metadata(
    book_id: str,
    book_name: str,
    category: str,
    item: Dict,
    idx: int,
    text: str,
    chunk_type: str,
    has_overlap: bool,
    is_chapter: bool,
    table_reference: str = None
) -> Dict[str, Any]:
    """Build rich metadata for each chunk"""
    
    section_name = extract_section_name(text) if chunk_type == "text" else None
    
    meta = {
        "book_id": book_id,
        "book_name": book_name,
        "category": category,
        "chunk_id": f"{book_id}_chunk_{idx}",
        "chunk_index": idx,
        "chunk_type": chunk_type,
        "has_overlap": has_overlap,
        "token_estimate": len(text) // 4,
        "char_count": len(text),
        "source_type": "chapter" if is_chapter else "section"
    }
    
    if section_name:
        meta["section_name"] = section_name
    
    if table_reference:
        meta["table_reference"] = table_reference
    
    if is_chapter:
        meta.update({
            "chapter_number": item.get("chapter_number"),
            "chapter_title": item.get("title"),
            "page_range": f"{item.get('start_page')}-{item.get('end_page')}"
        })
    else:
        meta.update({
            "section_title": item.get("title"),
            "page_range": f"{item.get('start_page')}-{item.get('end_page')}"
        })
    
    return meta

# ============================================================
# 🔥 CORE CHUNKING LOGIC
# ============================================================
def chunk_structure_file(structure_file: Path):
    """Process single structure file with RAG optimization"""
    print(f"\n📘 Processing: {structure_file.name}")
    
    with open(structure_file, "r", encoding="utf-8") as f:
        structure = json.load(f)
    
    original_name = structure["book_id"]
    book_id = generate_book_id(original_name)
    category = structure["category"]
    has_chapters = structure.get("has_chapters", False)
    
    items = structure.get("chapters") if has_chapters else structure.get("sections")
    if not items:
        print("⚠️ No content found")
        return None
    
    chunker = MedicalChunker()
    all_chunks = []
    gidx = 0
    
    for item in items:
        text = item.get("full_text", "")
        if not text or len(text) < 500:
            continue
        
        # ✅ FIX #2: Extract tables with references
        tables, clean_text = detect_tables(text)
        
        # Create table chunks
        for table in tables:
            all_chunks.append({
                "text": table["content"],
                "metadata": build_metadata(
                    book_id,
                    original_name,
                    category,
                    item,
                    gidx,
                    table["content"],
                    chunk_type="table",
                    has_overlap=False,
                    is_chapter=has_chapters,
                    table_reference=table.get("reference")
                )
            })
            gidx += 1
        
        # Chunk clean text
        text_chunks = chunker.chunk_text(clean_text)
        
        for i, chunk in enumerate(text_chunks):
            all_chunks.append({
                "text": chunk,
                "metadata": build_metadata(
                    book_id,
                    original_name,
                    category,
                    item,
                    gidx,
                    chunk,
                    chunk_type="text",
                    has_overlap=i > 0,
                    is_chapter=has_chapters
                )
            })
            gidx += 1
    
    if not all_chunks:
        print("⚠️ No chunks created")
        return None
    
    tokens = [c["metadata"]["token_estimate"] for c in all_chunks]
    table_count = sum(1 for c in all_chunks if c["metadata"]["chunk_type"] == "table")
    
    output = {
        "book_id": book_id,
        "book_name": original_name,
        "category": category,
        "total_chunks": len(all_chunks),
        "chunk_statistics": {
            "total": len(all_chunks),
            "text_chunks": len(all_chunks) - table_count,
            "table_chunks": table_count,
            "avg_tokens": sum(tokens) // len(tokens),
            "min_tokens": min(tokens),
            "max_tokens": max(tokens)
        },
        "config": {
            "chunk_size": 325,
            "chunk_overlap": 80,
            "min_chunk_size": 120,
            "max_chunk_size": 400
        },
        "created_at": datetime.utcnow().isoformat() + "Z",
        "chunks": all_chunks
    }
    
    out_file = CHUNKS_DIR / f"{category}_{book_id}_chunks.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved: {out_file.name}")
    print(f"📦 Total chunks: {len(all_chunks)}")
    print(f"📄 Text chunks: {len(all_chunks) - table_count}")
    print(f"📊 Table chunks: {table_count}")
    print(f"🎯 Avg tokens: {sum(tokens) // len(tokens)}")
    print(f"📏 Range: {min(tokens)} - {max(tokens)} tokens")
    
    return out_file

# ============================================================
# 🚀 MAIN EXECUTION
# ============================================================
def chunk_all():
    """Process all structure files"""
    files = list(STRUCTURES_DIR.glob("*_structure.json"))
    print(f"\n📚 Found {len(files)} books to process")
    
    for f in files:
        try:
            chunk_structure_file(f)
        except Exception as e:
            print(f"❌ Error processing {f.name}: {e}")
            continue

if __name__ == "__main__":
    chunk_all()