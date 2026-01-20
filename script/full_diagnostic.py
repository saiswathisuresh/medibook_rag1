import json
from pathlib import Path

CHUNKS_FOLDER = Path("/home/ubuntu/medibook_rag1/data/chunks")

print("=" * 80)
print("🔍 COMPLETE DIAGNOSTIC - JSON FILE INSPECTOR")
print("=" * 80)

json_files = list(CHUNKS_FOLDER.glob("*.json"))
print(f"\n📂 Total JSON files found: {len(json_files)}")
print(f"📂 Files: {[f.name for f in json_files]}\n")

for i, json_file in enumerate(json_files, 1):
    print("\n" + "=" * 80)
    print(f"FILE {i}/{len(json_files)}: {json_file.name}")
    print("=" * 80)
    
    try:
        # Read file
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print(f"\n✅ JSON loaded successfully")
        print(f"📋 File size: {json_file.stat().st_size / 1024:.2f} KB")
        
        # Check top-level keys
        print(f"\n🔑 TOP-LEVEL KEYS:")
        print(f"   {list(data.keys())}")
        
        # Check for 'chunks' key
        if "chunks" not in data:
            print(f"\n❌ ERROR: No 'chunks' key found!")
            print(f"   Available keys: {list(data.keys())}")
            
            # Show first 3 keys and their types
            print(f"\n📊 First 3 keys content type:")
            for key in list(data.keys())[:3]:
                val = data[key]
                print(f"   - {key}: {type(val).__name__}")
                if isinstance(val, list) and len(val) > 0:
                    print(f"     └─ First item type: {type(val[0]).__name__}")
            continue
        
        # Process chunks
        chunks = data["chunks"]
        print(f"\n✅ 'chunks' array found!")
        print(f"📦 Total chunks: {len(chunks)}")
        
        if not chunks or len(chunks) == 0:
            print(f"\n⚠️  WARNING: chunks array is EMPTY!")
            continue
        
        # Inspect first chunk
        first_chunk = chunks[0]
        print(f"\n📦 FIRST CHUNK STRUCTURE:")
        print(f"   Keys: {list(first_chunk.keys())}")
        
        # Check for metadata
        if "metadata" not in first_chunk:
            print(f"\n❌ ERROR: No 'metadata' key in first chunk!")
            print(f"   Available keys: {list(first_chunk.keys())}")
            continue
        
        # Inspect metadata
        metadata = first_chunk["metadata"]
        print(f"\n🏷️  METADATA STRUCTURE:")
        print(f"   Total keys: {len(metadata)}")
        print(f"   Keys: {list(metadata.keys())}")
        
        # Critical fields
        print(f"\n🎯 CRITICAL FIELDS:")
        print(f"   book_id: {metadata.get('book_id', '❌ MISSING')}")
        print(f"   book_name: {metadata.get('book_name', '❌ MISSING')}")
        print(f"   title: {metadata.get('title', '❌ MISSING')}")
        print(f"   chapter_number: {metadata.get('chapter_number', 'N/A')}")
        print(f"   chapter_title: {metadata.get('chapter_title', 'N/A')}")
        
        # Show ALL metadata fields with values
        print(f"\n📊 ALL METADATA FIELDS:")
        for key, value in sorted(metadata.items()):
            val_str = str(value)
            if len(val_str) > 60:
                val_str = val_str[:60] + "..."
            print(f"   {key:30} = {val_str}")
        
        # Check text content
        if "text" in first_chunk:
            text = first_chunk["text"]
            print(f"\n📝 TEXT CONTENT:")
            print(f"   Length: {len(text)} characters")
            print(f"   Preview: {text[:150]}...")
        
        # Check if it's a chapter book
        has_chapters = False
        chapter_count = 0
        chapter_map = {}
        
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            ch_no = meta.get("chapter_number")
            ch_title = meta.get("chapter_title")
            
            if ch_no and ch_title:
                has_chapters = True
                key = f"{ch_no}_{ch_title}"
                if key not in chapter_map:
                    chapter_map[key] = {
                        "chapter_id": str(ch_no),
                        "chapter_name": ch_title
                    }
        
        if has_chapters:
            print(f"\n📚 CHAPTER INFO:")
            print(f"   Has chapters: YES")
            print(f"   Unique chapters found: {len(chapter_map)}")
            print(f"   Chapters:")
            for ch in list(chapter_map.values())[:5]:  # Show first 5
                print(f"      - Chapter {ch['chapter_id']}: {ch['chapter_name']}")
            if len(chapter_map) > 5:
                print(f"      ... and {len(chapter_map) - 5} more")
        else:
            print(f"\n📚 CHAPTER INFO:")
            print(f"   Has chapters: NO")
        
        # Summary
        print(f"\n✅ FILE SUMMARY:")
        book_id = metadata.get('book_id', 'UNKNOWN')
        book_name = metadata.get('book_name', 'UNKNOWN')
        print(f"   Book ID: {book_id}")
        print(f"   Book Name: {book_name}")
        print(f"   Total Chunks: {len(chunks)}")
        print(f"   Has Chapters: {has_chapters}")
        print(f"   Chapter Count: {len(chapter_map)}")
        
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON DECODE ERROR:")
        print(f"   {str(e)}")
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("✅ DIAGNOSTIC COMPLETE")
print("=" * 80)