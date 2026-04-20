"""
Compare simple_rag vs karpathy_rag on the same question.

Usage:
    python compare.py "your question here"

Prerequisites:
    python simple_rag.py ingest
    python karpathy_rag.py compile
"""

import sys
import time
import simple_rag
import karpathy_rag


def compare(question: str) -> None:
    print(f"\n{'='*60}")
    print(f"Question: {question}")
    print(f"{'='*60}\n")

    # ── Simple RAG ────────────────────────────────────────────────
    print("── Simple RAG ──────────────────────────────────────────")
    t0 = time.time()
    try:
        r1 = simple_rag.query(question)
        t1 = time.time()
        print(f"Answer:\n{r1['answer']}")
        print(f"\nSources: {', '.join(r1['sources'])}")
        print(f"Latency: {t1 - t0:.2f}s")
    except Exception as e:
        print(f"Error: {e}")
        print("Did you run: python simple_rag.py ingest ?")

    print()

    # ── Karpathy RAG ──────────────────────────────────────────────
    print("── Karpathy RAG ────────────────────────────────────────")
    t0 = time.time()
    try:
        r2 = karpathy_rag.query(question)
        t1 = time.time()
        print(f"Answer:\n{r2['answer']}")
        print(f"\nWiki articles used: {', '.join(r2['sources'])}")
        print(f"Reasoning: {r2['reasoning']}")
        print(f"Latency: {t1 - t0:.2f}s")
    except Exception as e:
        print(f"Error: {e}")
        print("Did you run: python karpathy_rag.py compile ?")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    compare(sys.argv[1])
