import json
from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_chroma import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain.schema import Document
import chromadb

RAW_DOCS_DIR = Path(__file__).parent / "raw_docs"
CHROMA_PATH   = Path(__file__).parent / "chroma_db"

# Optional JSON sources (e.g., market data) to ingest alongside markdown.
JSON_FILES = [
    Path(__file__).parent.parent / "backend" / "data" / "brb_market_data.json",
]

CHUNK_SIZE    = 500   # tokens ≈ characters/4; 500 tokens ≈ 2000 chars
CHUNK_OVERLAP = 75

def get_embeddings():
    return OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434",
    )

def load_and_chunk(md_path: Path) -> list:
    loader = UnstructuredMarkdownLoader(str(md_path))
    docs   = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks = splitter.split_documents(docs)
    # Tag each chunk with the source file name for provenance
    for chunk in chunks:
        chunk.metadata["source_file"] = md_path.name
    return chunks


def load_and_chunk_json(json_path: Path) -> list:
    """Load a JSON file (list or dict) and emit text chunks for embedding."""
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"JSON file not found: {json_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON parse error in {json_path}: {e}")
        return []

    # Normalize to a list of records
    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict):
        # Try common containers: events / data / records; fallback to the dict itself
        for key in ("events", "data", "records"):
            if key in raw and isinstance(raw[key], list):
                records = raw[key]
                break
        else:
            records = [raw]
    else:
        records = [raw]

    docs = []
    for idx, rec in enumerate(records):
        # Ensure a dict for stable key/value formatting
        if not isinstance(rec, dict):
            rec = {"value": rec}
        lines = [f"{k}: {v}" for k, v in rec.items()]
        content = "\n".join(lines)
        docs.append(
            Document(
                page_content=content,
                metadata={"source_file": json_path.name, "record_index": idx},
            )
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " "],
    )
    return splitter.split_documents(docs)

def main():
    md_files = sorted(RAW_DOCS_DIR.glob("*.md"))
    json_files = [p for p in JSON_FILES if p.exists()]

    if not md_files and not json_files:
        print("No markdown or JSON files found to ingest.")
        return

    print(f"Found {len(md_files)} markdown and {len(json_files)} JSON sources to ingest.")
    embeddings = get_embeddings()

    # Persistent ChromaDB — survives restarts
    vectorstore = Chroma(
        collection_name="brb_master_crisis",
        embedding_function=embeddings,
        persist_directory=str(CHROMA_PATH),
    )

    # Check which files are already embedded (avoid re-embedding on re-runs)
    existing = set(
        m["source_file"]
        for m in vectorstore.get()["metadatas"]
        if m and "source_file" in m
    )

    all_chunks = []
    # Markdown files
    for i, md_path in enumerate(md_files, 1):
        if md_path.name in existing:
            print(f"[{i}/{len(md_files)}] SKIP (already embedded): {md_path.name}")
            continue
        print(f"[{i}/{len(md_files)}] Chunking: {md_path.name}")
        chunks = load_and_chunk(md_path)
        all_chunks.extend(chunks)
        print(f"  → {len(chunks)} chunks")

    # JSON files
    for j, json_path in enumerate(json_files, 1):
        label = f"JSON {json_path.name}"
        if json_path.name in existing:
            print(f"[JSON {j}/{len(json_files)}] SKIP (already embedded): {json_path.name}")
            continue
        print(f"[JSON {j}/{len(json_files)}] Chunking: {json_path.name}")
        chunks = load_and_chunk_json(json_path)
        all_chunks.extend(chunks)
        print(f"  → {len(chunks)} chunks")

    if not all_chunks:
        print("Nothing new to embed.")
        return

    BATCH_SIZE = 100  # ChromaDB max batch varies by install; 100 is safe universally
    total = len(all_chunks)
    print(f"\nEmbedding {total} chunks via nomic-embed-text...")
    print(f"(Batching into {-(-total // BATCH_SIZE)} batches of {BATCH_SIZE} — normal on CPU, ~1–3 min per 100 chunks)")

    for batch_start in range(0, total, BATCH_SIZE):
        batch = all_chunks[batch_start : batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        num_batches = -(-total // BATCH_SIZE)
        print(f"  Batch {batch_num}/{num_batches} — chunks {batch_start + 1}–{min(batch_start + BATCH_SIZE, total)}")
        vectorstore.add_documents(batch)

    print(f"Done. ChromaDB now has {vectorstore._collection.count()} total chunks.")

if __name__ == "__main__":
    main()
