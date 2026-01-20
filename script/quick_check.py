import json
from pathlib import Path

file1 = Path("/home/ubuntu/medibook_rag1/data/chunks/chapter_G1vRkL5Eh6cyGwkT7wAD1_chunks.json")
file2 = Path("/home/ubuntu/medibook_rag1/data/chunks/non_chapter_H3Payb6LGB7uXHd1KPv9Z_chunks.json")

for f in [file1, file2]:
    print(f"\n{'='*60}")
    print(f"FILE: {f.name}")
    print('='*60)
    
    with open(f, 'r') as file:
        data = json.load(file)
    
    print(f"Top-level keys: {list(data.keys())}")
    
    if "chunks" in data:
        chunks = data["chunks"]
        print(f"Chunks: {len(chunks)}")
        
        if chunks:
            meta = chunks[0].get("metadata", {})
            print(f"\nFirst chunk metadata:")
            for k, v in meta.items():
                val = str(v)[:80]
                print(f"  {k}: {val}")
    else:
        print("NO CHUNKS KEY!")
        # Print first level
        for k in list(data.keys())[:5]:
            print(f"  {k}: {type(data[k])}")