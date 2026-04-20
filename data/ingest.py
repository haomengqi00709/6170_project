"""
Document Ingestion
------------------
Reads documents from data/raw/ and loads them into the AuditBot vector store.

Directory structure (permission level = subfolder name):

    data/raw/
    ├── public/        ← anyone can access
    ├── junior/        ← junior + above
    ├── senior/        ← senior + above
    └── executive/     ← executive only

Usage:
    python data/ingest.py              # ingest all files
    python data/ingest.py --reset      # clear DB first, then ingest
"""

import sys
import os
import glob
from pathlib import Path

# make sure imports resolve from Build/
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from core.vectorstore import AuditBotVectorStore
from core.rbac import PERMISSION_LEVELS

RAW_DIR  = Path(__file__).parent / "raw"
DB_DIR   = Path(__file__).parent.parent / "chroma_db"
SUPPORTED = {".txt", ".md", ".csv", ".json"}


def ingest(reset: bool = False) -> None:
    store = AuditBotVectorStore(db_dir=str(DB_DIR))

    if reset:
        import chromadb
        client = chromadb.PersistentClient(path=str(DB_DIR))
        try:
            client.delete_collection("auditbot")
            print("[ingest] Collection cleared.")
        except Exception:
            pass
        store = AuditBotVectorStore(db_dir=str(DB_DIR))

    total_files  = 0
    total_chunks = 0

    for level in PERMISSION_LEVELS:
        level_dir = RAW_DIR / level
        if not level_dir.exists():
            continue

        files = [
            f for f in level_dir.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED
        ]

        for filepath in files:
            try:
                n = store.ingest_file(
                    filepath=filepath,
                    content_level=level,
                    department="general",
                )
                print(f"  [{level:10s}] {filepath.name} → {n} chunks")
                total_files  += 1
                total_chunks += n
            except Exception as e:
                print(f"  [ERROR] {filepath.name}: {e}")

    print(f"\n[ingest] Done — {total_files} files, {total_chunks} chunks total.")
    print(f"         Vector store size: {store.count()} chunks")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    ingest(reset=reset)
