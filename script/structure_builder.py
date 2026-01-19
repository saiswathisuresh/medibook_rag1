import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PAGES_DIR = BASE_DIR / "data" / "pages"
CHAPTER_JSON = BASE_DIR / "data" / "chapter.json"
NON_CHAPTER_JSON = BASE_DIR / "data" / "non_chapter.json"
STRUCTURES_DIR = BASE_DIR / "data" / "structures"
STRUCTURES_DIR.mkdir(exist_ok=True)

# ============================================================
# 🔥 ULTRA-STRICT PAGE HEADER PATTERNS
# ============================================================
PAGE_HEADER_PATTERNS = [
    r'^\d+\s+[A-Z][A-Za-z\s,&\-]+\s+\d+$',  # "5 Biology and Genetics 1"
    r'^\d+\s+Gynecologic Oncology\s+\d+$',  # "6 Gynecologic Oncology 1"
    r'^\d+\s+\d+\s+[A-Z][A-Za-z\s,&\-]+$',  # "2 12 Gynecologic Oncology"
    r'^Chapter\s+\d+.*?\d+$',                # "Chapter 5 Title 123"
    r'^\d{1,4}$',                            # Pure page numbers "123"
    r'^\[\d+\]$',                            # "[123]"
]

# Comprehensive noise patterns
NOISE_PATTERNS = [
    r'copyright.*?all rights reserved',
    r'©.*?\d{4}',
    r'published by.*?press',
    r'isbn.*?\d',
    r'printed in',
    r'(first|second|third) edition',
    r'all rights reserved',
    r'no part of this.*?reproduced',
    r'permission.*?publisher',
    r'table of contents',
    r'^contents$',
    r'chapter\s+\d+.*?\.\.\.',
    r'preface',
    r'foreword',
    r'acknowledgements?',
    r'dedication',
    r'about the (author|editor)s?',
    r'\bindex\b',
    r'\bbibliography\b',
    r'\breferences\b',
    r'\bappendix\b',
    r'\bglossary\b',
    r'contributors?$',
    r'editor[s]?:?\s*$',
    r'editorial board',
    r'department of',
    r'university of',
    r'medical center',
    r'division of',
    r'associate professor',
    r'assistant professor',
    r'fellowship',
    r'board of.*?gynecology',
    r'society of',
]

# Reference section patterns
REFERENCE_PATTERNS = [
    r'^\s*references\s*$',
    r'^\s*bibliography\s*$',
    r'^\s*further reading\s*$',
    r'^\s*cited works\s*$',
]

REFERENCE_LIST_INDICATORS = [
    r'^\d+\.\s+[A-Z]',      # "1. Author Name"
    r'^[A-Z][a-z]+\s+[A-Z]',  # "Smith J"
    r'\(\d{4}\)',           # (2020)
    r'et al\.',
    r'J\s+[A-Z][a-z]+',     # J Med
    r'doi:',
    r'PMID:',
]

CONTENT_INDICATORS = [
    r'\b(introduction|overview|background)\b',
    r'\b(methods|methodology|materials)\b',
    r'\b(results|findings|outcomes)\b',
    r'\b(discussion|conclusion)\b',
    r'\b(treatment|therapy|diagnosis)\b',
    r'\b(pathology|histology|epidemiology)\b',
    r'\b(clinical|surgical|medical)\b',
    r'\b(patient|tumor|cancer|disease)\b',
    r'\b(cell|molecular|genetic|gene)\b',
    r'\b(risk|survival|prognosis)\b',
]


# ============================================================
# 🔥 FIX #1: ULTRA-STRICT PAGE HEADER REMOVAL
# ============================================================
def remove_all_page_headers(text: str) -> str:
    """
    MOST AGGRESSIVE header removal for RAG.
    Removes EVERY line matching header patterns.
    """
    lines = text.splitlines()
    clean = []
    
    for line in lines:
        stripped = line.strip()
        
        # Check against ALL header patterns
        is_header = False
        for pattern in PAGE_HEADER_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                is_header = True
                break
        
        if not is_header:
            clean.append(line)
    
    return "\n".join(clean)


# ============================================================
# 🔥 FIX #2: SMART CHAPTER TITLE EXTRACTION
# ============================================================
def extract_real_chapter_title(page_text: str, fallback_title: str) -> str:
    """
    Extracts ACTUAL chapter title from page content.
    Ignores metadata title if real one exists.
    """
    # First remove ALL headers
    cleaned = remove_all_page_headers(page_text)
    lines = [l.strip() for l in cleaned.split('\n') if l.strip()]
    
    if not lines:
        return fallback_title
    
    # Look in first 10 non-header lines
    for i, line in enumerate(lines[:10]):
        # Skip very short lines
        if len(line) < 5:
            continue
        
        # Skip pure numbers
        if re.match(r'^\d+$', line):
            continue
        
        # Title characteristics:
        # - 10-80 chars
        # - Starts with capital
        # - Not all caps
        # - No sentence connectors
        if (10 <= len(line) <= 80 and
            line[0].isupper() and
            not line.isupper() and
            not re.match(r'^(The|This|It|In|A|An|For|With)\s', line) and
            not re.search(r'\.\s+[A-Z]', line)):  # Not mid-paragraph
            
            # Clean chapter prefix if exists
            cleaned_title = re.sub(r'^Chapter\s+\d+:?\s*', '', line, flags=re.IGNORECASE)
            return cleaned_title.strip()
    
    return fallback_title



# ============================================================
# 🔥 FIX #3: COMPLETE REFERENCE STRIPPING
# ============================================================
def strip_all_references(text: str) -> str:
    """
    Strips EVERYTHING after references section starts.
    NO references in content.
    """
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_lower = line.strip().lower()
        
        # Check if this line starts references
        for ref_pattern in REFERENCE_PATTERNS:
            if re.match(ref_pattern, line_lower):
                # Return ONLY content before this point
                return '\n'.join(lines[:i]).strip()
    
    # Also check for numbered reference lists
    ref_start_idx = None
    consecutive_refs = 0
    
    for i, line in enumerate(lines):
        # Check if line looks like a reference
        is_ref_line = False
        for pattern in REFERENCE_LIST_INDICATORS:
            if re.search(pattern, line):
                is_ref_line = True
                break
        
        if is_ref_line:
            consecutive_refs += 1
            if consecutive_refs >= 3 and ref_start_idx is None:
                ref_start_idx = i - 2  # Start from 3 lines back
        else:
            consecutive_refs = 0
    
    if ref_start_idx:
        return '\n'.join(lines[:ref_start_idx]).strip()
    
    return text.strip()


# ============================================================
# 🔥 FIX #4: PROPER CHAPTER BOUNDARY DETECTION
# ============================================================
def detect_chapter_boundaries(pages, chapter_titles):
    """
    Detects REAL chapter boundaries by finding title matches.
    No more guessing with page math.
    """
    boundaries = {}
    
    for idx, page in enumerate(pages):
        text_clean = remove_all_page_headers(page.get('text', ''))
        
        # Check first 15 lines for chapter title match
        lines = [l.strip() for l in text_clean.split('\n') if l.strip()][:15]
        
        for chapter_idx, chapter_title in enumerate(chapter_titles):
            title_lower = chapter_title.lower()
            keywords = [w for w in title_lower.split() if len(w) > 3]
            
            for line in lines:
                line_lower = line.lower()
                
                # Count keyword matches
                matches = sum(1 for kw in keywords if kw in line_lower)
                
                # If 60%+ keywords match, this is chapter start
                if len(keywords) > 0 and (matches / len(keywords)) >= 0.6:
                    if chapter_idx not in boundaries:
                        boundaries[chapter_idx] = idx
                        break
    
    return boundaries


def clean_page_text(text):
    """Clean page by removing headers"""
    return remove_all_page_headers(text)


def is_reference_section(page_text):
    """Detect if page is references"""
    text_lower = page_text.lower().strip()
    lines = [l.strip() for l in text_lower.split('\n') if l.strip()]
    
    if not lines:
        return False
    
    # Check first few lines
    for line in lines[:5]:
        for pattern in REFERENCE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True
    
    # Count reference-like lines
    ref_count = sum(1 for line in lines 
                   for pattern in REFERENCE_LIST_INDICATORS 
                   if re.search(pattern, line))
    
    if len(lines) > 5 and (ref_count / len(lines)) > 0.4:
        return True
    
    return False


def calculate_noise_score(text):
    """Calculate noise score (0-1)"""
    if not text or len(text.strip()) < 30:
        return 1.0
    
    text_lower = text.lower().strip()
    lines = [l.strip() for l in text_lower.split('\n') if l.strip()]
    
    if not lines:
        return 1.0
    
    noise_lines = sum(1 for line in lines 
                     for pattern in NOISE_PATTERNS 
                     if re.search(pattern, line, re.IGNORECASE))
    
    content_lines = sum(1 for line in lines 
                       for pattern in CONTENT_INDICATORS 
                       if re.search(pattern, line, re.IGNORECASE))
    
    total_lines = len(lines)
    noise_ratio = noise_lines / total_lines if total_lines > 0 else 0
    content_ratio = content_lines / total_lines if total_lines > 0 else 0
    
    if len(text_lower) < 200:
        noise_ratio += 0.3
    
    noise_score = noise_ratio - (content_ratio * 0.5)
    return max(0, min(1, noise_score))


def is_noise_page(page_data, threshold=0.4):
    """Determine if page is noise"""
    text = page_data.get('text', '')
    return calculate_noise_score(text) > threshold


def filter_noise_pages(pages, verbose=False):
    """Filter noise pages"""
    filtered = []
    removed = []
    
    for page in pages:
        if not is_noise_page(page):
            filtered.append(page)
        else:
            removed.append(page['page_no'])
    
    if removed and verbose:
        print(f"      🗑️  Removed {len(removed)} noise pages")
    
    return filtered


def find_reference_start(pages, start_idx=0):
    """Find where references start"""
    for i in range(start_idx, len(pages)):
        if is_reference_section(pages[i].get('text', '')):
            return i
    return None


def load_pages_json(pages_file):
    """Load pages JSON"""
    try:
        with open(pages_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {pages_file}: {e}")
        return None


def load_chapter_info(book_id, category):
    """Load chapter info"""
    json_file = CHAPTER_JSON if category == "chapter" else NON_CHAPTER_JSON
    
    if not json_file.exists():
        return None
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "book_title" in data and "chapters" in data:
            return normalize_chapter_format(data)
        
        if "title" in data and "headings" in data:
            return convert_headings_to_chapters(data)
        
        for key in data.keys():
            if book_id in key or key in book_id:
                chapter_data = data[key]
                if "headings" in chapter_data:
                    return convert_headings_to_chapters(chapter_data)
                elif "chapters" in chapter_data:
                    return normalize_chapter_format(chapter_data)
        
        return None
    except Exception as e:
        print(f"      ❌ Error: {e}")
        return None


def normalize_chapter_format(data):
    """Normalize chapter formats"""
    chapters = data.get("chapters", [])
    
    if not chapters:
        return None
    
    normalized = []
    for ch in chapters:
        normalized.append({
            "chapter_number": ch.get("chapter_number") or ch.get("chapter") or len(normalized) + 1,
            "title": ch.get("title") or ch.get("heading") or f"Chapter {len(normalized) + 1}",
            "start_page": ch.get("start_page", 1),
            "end_page": ch.get("end_page", 10),
            "subheadings": ch.get("subheadings", [])
        })
    
    return {"total_chapters": len(normalized), "chapters": normalized}


def convert_headings_to_chapters(data):
    """Convert headings to chapters"""
    headings = data.get("headings", [])
    if not headings:
        return None
    
    chapters = []
    current_page = 1
    
    for i, h in enumerate(headings):
        est_pages = max(len(h.get("subheadings", [])) * 2, 10)
        chapters.append({
            "chapter_number": i + 1,
            "title": h.get("heading", f"Section {i+1}"),
            "start_page": current_page,
            "end_page": current_page + est_pages - 1,
            "subheadings": h.get("subheadings", [])
        })
        current_page += est_pages
    
    return {"total_chapters": len(chapters), "chapters": chapters}


# ============================================================
# 🔥 MAIN STRUCTURE BUILDER - RAG-OPTIMIZED
# ============================================================
def build_structure_with_chapters(pages_data, chapter_info):
    """Build RAG-ready structure"""
    book_id = pages_data['book_id']
    category = pages_data['category']
    pages = pages_data['pages']
    
    # Step 1: Filter noise
    clean_pages = filter_noise_pages(pages)
    if not clean_pages:
        return None
    
    print(f"      ✅ Clean pages: {len(clean_pages)}")
    
    # Step 2: Find references
    ref_start_idx = find_reference_start(clean_pages)
    
    if ref_start_idx:
        content_pages = clean_pages[:ref_start_idx]
        reference_pages = clean_pages[ref_start_idx:]
        print(f"      📚 References at index {ref_start_idx}")
    else:
        content_pages = clean_pages
        reference_pages = []
    
    chapters_meta = chapter_info.get('chapters', [])
    if not chapters_meta:
        return None
    
    # CRITICAL: Determine if this is truly a chapter-based book
    has_real_chapters = (category == "chapter")
    
    # Step 3: Detect REAL chapter boundaries
    chapter_titles = [ch['title'] for ch in chapters_meta]
    boundaries = detect_chapter_boundaries(content_pages, chapter_titles)
    
    chapters = []
    
    # Step 4: Build chapters with CORRECT boundaries
    for i, chapter_meta in enumerate(chapters_meta):
        # Get actual start from detected boundaries
        actual_start = boundaries.get(i, i * (len(content_pages) // len(chapters_meta)))
        
        # Get next chapter start
        if i + 1 in boundaries:
            actual_end = boundaries[i + 1] - 1
        elif i == len(chapters_meta) - 1:
            actual_end = len(content_pages) - 1
        else:
            actual_end = min(actual_start + (len(content_pages) // len(chapters_meta)), 
                           len(content_pages) - 1)
        
        chapter_pages = content_pages[actual_start:actual_end + 1]
        
        if not chapter_pages:
            continue
        
        # CRITICAL: Clean + strip references from EACH page
        cleaned_pages = []
        for p in chapter_pages:
            # Step 1: Remove headers
            text_no_headers = remove_all_page_headers(p['text'])
            # Step 2: Remove references
            text_final = strip_all_references(text_no_headers)
            
            cleaned_pages.append({
                **p,
                'text': text_final
            })
        
        # Extract REAL title from first page
        first_page_text = cleaned_pages[0].get('text', '')
        actual_title = extract_real_chapter_title(first_page_text, chapter_meta['title'])
        
        full_text = "\n\n".join([p['text'] for p in cleaned_pages])
        
        chapters.append({
            "chapter_number": chapter_meta['chapter_number'] if has_real_chapters else None,
            "section_number": None if has_real_chapters else len(chapters) + 1,
            "title": actual_title,
            "subheadings": chapter_meta.get('subheadings', []),
            "start_page": cleaned_pages[0]['page_no'],
            "end_page": cleaned_pages[-1]['page_no'],
            "total_pages": len(cleaned_pages),
            "full_text": full_text,
            "pages": cleaned_pages
        })
    
    # Step 5: References section
    reference_section = None
    if reference_pages:
        cleaned_refs = []
        for p in reference_pages:
            text_clean = remove_all_page_headers(p['text'])
            cleaned_refs.append({**p, 'text': text_clean})
        
        reference_section = {
            "section_type": "references",
            "title": "References",
            "start_page": cleaned_refs[0]['page_no'],
            "end_page": cleaned_refs[-1]['page_no'],
            "total_pages": len(cleaned_refs),
            "full_text": "\n\n".join([p['text'] for p in cleaned_refs]),
            "pages": cleaned_refs
        }
    
    return {
        "book_id": book_id,
        "category": category,
        "total_pages": pages_data['total_pages'],
        "extracted_pages": len(clean_pages),
        "has_chapters": has_real_chapters,  # FIXED: Based on category
        "total_chapters": len(chapters) if has_real_chapters else 0,
        "total_sections": 0 if has_real_chapters else len(chapters),
        "chapters": chapters if has_real_chapters else [],
        "sections": [] if has_real_chapters else chapters,
        "references": reference_section
    }


def build_structure_fallback(pages_data, chunk_size=20):
    """Fallback for books without chapter info"""
    clean_pages = filter_noise_pages(pages_data['pages'])
    if not clean_pages:
        return None
    
    ref_start = find_reference_start(clean_pages)
    content_pages = clean_pages[:ref_start] if ref_start else clean_pages
    reference_pages = clean_pages[ref_start:] if ref_start else []
    
    sections = []
    for i in range(0, len(content_pages), chunk_size):
        chunk = content_pages[i:i + chunk_size]
        if not chunk:
            continue
        
        cleaned = []
        for p in chunk:
            text_clean = strip_all_references(remove_all_page_headers(p['text']))
            cleaned.append({**p, 'text': text_clean})
        
        sections.append({
            "section_number": len(sections) + 1,
            "title": f"Section {len(sections) + 1}",
            "start_page": cleaned[0]['page_no'],
            "end_page": cleaned[-1]['page_no'],
            "total_pages": len(cleaned),
            "full_text": "\n\n".join([p['text'] for p in cleaned]),
            "pages": cleaned
        })
    
    reference_section = None
    if reference_pages:
        cleaned_refs = []
        for p in reference_pages:
            cleaned_refs.append({**p, 'text': remove_all_page_headers(p['text'])})
        
        reference_section = {
            "section_type": "references",
            "title": "References",
            "start_page": cleaned_refs[0]['page_no'],
            "end_page": cleaned_refs[-1]['page_no'],
            "total_pages": len(cleaned_refs),
            "full_text": "\n\n".join([p['text'] for p in cleaned_refs]),
            "pages": cleaned_refs
        }
    
    return {
        "book_id": pages_data['book_id'],
        "category": pages_data['category'],
        "total_pages": pages_data['total_pages'],
        "extracted_pages": len(clean_pages),
        "has_chapters": False,
        "total_sections": len(sections),
        "sections": sections,
        "references": reference_section
    }


def process_single_book(pages_file):
    """Process one book"""
    pages_data = load_pages_json(pages_file)
    if not pages_data:
        return None
    
    book_id = pages_data['book_id']
    category = pages_data['category']
    
    print(f"\n📖 {book_id}")
    print(f"   Category: {category}")
    
    chapter_info = load_chapter_info(book_id, category)
    
    if chapter_info and chapter_info.get('chapters'):
        print(f"   ✅ Using {len(chapter_info['chapters'])} chapters")
        structure = build_structure_with_chapters(pages_data, chapter_info)
    else:
        print(f"   ⚠️  Fallback mode")
        structure = build_structure_fallback(pages_data)
    
    if not structure:
        print(f"   ❌ Failed")
        return None
    
    output_file = STRUCTURES_DIR / f"{category}_{book_id}_structure.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(structure, f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ Saved: {output_file.name}")
    
    if structure.get('has_chapters'):
        for ch in structure['chapters'][:3]:
            ch_num = ch.get('chapter_number', '?')
            print(f"      Ch {ch_num}: {ch['title']} [{ch['total_pages']} pages]")
    else:
        for sec in structure.get('sections', [])[:3]:
            sec_num = sec.get('section_number', '?')
            print(f"      Sec {sec_num}: {sec['title']} [{sec['total_pages']} pages]")
    
    return output_file


def process_all_books():
    """Process all books"""
    print("="*60)
    print("🔥 RAG-READY STRUCTURE BUILDER v3.0")
    print("="*60)
    
    if not PAGES_DIR.exists():
        print(f"❌ Pages directory not found")
        return
    
    page_files = list(PAGES_DIR.glob("*_pages.json"))
    if not page_files:
        print("⚠️  No files found")
        return
    
    print(f"\nProcessing {len(page_files)} books\n")
    
    success = 0
    for pages_file in sorted(page_files):
        try:
            if process_single_book(pages_file):
                success += 1
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "="*60)
    print(f"✅ DONE: {success}/{len(page_files)}")
    print("="*60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        process_single_book(Path(sys.argv[1]))
    else:
        process_all_books()