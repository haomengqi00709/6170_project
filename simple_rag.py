"""
Simple RAG
----------
Pipeline: raw docs → chunk → embed → Chroma → retrieve top-k → LLM answer

Usage:
    python simple_rag.py ingest          # index documents in data/raw/
    python simple_rag.py query "..."     # ask a question
"""

import os
import sys
import glob
from pathlib import Path

import chromadb
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from core import llm as _llm

# ── Config ────────────────────────────────────────────────────────────────────
RAW_DIR       = "data/raw"
CHROMA_DIR    = "chroma_db_simple"
COLLECTION    = "simple_rag"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100
TOP_K         = 5

# ── Clients ───────────────────────────────────────────────────────────────────
_chroma = chromadb.PersistentClient(path=CHROMA_DIR)


# ── Helpers ───────────────────────────────────────────────────────────────────
def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start: start + size])
        start += size - overlap
    return chunks


def load_documents(raw_dir: str) -> dict[str, str]:
    docs = {}
    for path in glob.glob(f"{raw_dir}/**/*", recursive=True):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                docs[Path(path).name] = f.read()
        except Exception:
            pass
    return docs


# ── Core functions ────────────────────────────────────────────────────────────
def ingest(raw_dir: str = RAW_DIR) -> None:
    """Chunk and embed all documents, store in Chroma."""
    docs = load_documents(raw_dir)
    if not docs:
        print(f"No documents found in {raw_dir}/")
        return

    collection = _chroma.get_or_create_collection(
        name=COLLECTION, embedding_function=_llm.get_chroma_embedding_fn()
    )

    ids, texts, metas = [], [], []
    for filename, content in docs.items():
        for i, chunk in enumerate(chunk_text(content)):
            ids.append(f"{filename}__chunk_{i}")
            texts.append(chunk)
            metas.append({"source": filename, "chunk_index": i})

    collection.upsert(documents=texts, ids=ids, metadatas=metas)
    print(f"[simple_rag] Ingested {len(texts)} chunks from {len(docs)} files.")


def query(question: str, k: int = TOP_K) -> dict:
    """Retrieve relevant chunks and answer the question."""
    collection = _chroma.get_collection(
        name=COLLECTION, embedding_function=_llm.get_chroma_embedding_fn()
    )

    results = collection.query(query_texts=[question], n_results=k)
    chunks  = results["documents"][0]
    metas   = results["metadatas"][0]

    context = "\n\n---\n\n".join(
        f"[Source: {m['source']}]\n{chunk}"
        for chunk, m in zip(chunks, metas)
    )

    answer = _llm.chat([
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. Answer the question using only "
                "the provided context. If the answer is not in the context, say so."
            ),
        },
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}",
        },
    ])

    return {
        "answer":  answer,
        "sources": list({m["source"] for m in metas}),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "ingest":
        ingest()

    elif cmd == "query":
        if len(sys.argv) < 3:
            print('Usage: python simple_rag.py query "your question"')
            sys.exit(1)
        result = query(sys.argv[2])
        print(f"\nAnswer:\n{result['answer']}")
        print(f"\nSources: {', '.join(result['sources'])}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
