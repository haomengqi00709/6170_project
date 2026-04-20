"""
Karpathy-style RAG
------------------
Pipeline:
  compile  →  raw docs → LLM extracts concepts → writes wiki articles + index.md
  query    →  LLM reads index → selects relevant articles → reads them → answers
  lint     →  LLM health-checks the wiki for gaps / inconsistencies

Wiki layout (auto-created):
  wiki/
  ├── index.md          ← master index: concept list + one-line summaries
  └── concepts/
      ├── ConceptA.md
      └── ConceptB.md

Usage:
    python karpathy_rag.py compile         # build wiki from data/raw/
    python karpathy_rag.py query "..."     # ask a question
    python karpathy_rag.py lint            # health-check the wiki
"""

import json
import os
import sys
import glob
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from core import llm as _llm

# ── Config ────────────────────────────────────────────────────────────────────
RAW_DIR      = "data/raw"
WIKI_DIR     = "wiki"
CONCEPTS_DIR = f"{WIKI_DIR}/concepts"
INDEX_FILE   = f"{WIKI_DIR}/index.md"


# ── Helpers ───────────────────────────────────────────────────────────────────
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


def _llm_call(system: str, user: str, json_mode: bool = False) -> str:
    """Thin wrapper: build messages list and call the abstraction layer."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    return _llm.chat(messages, json_mode=json_mode)


def safe_filename(name: str) -> str:
    return name.replace(" ", "_").replace("/", "-").replace("\\", "-")


# ── Core: compile ─────────────────────────────────────────────────────────────
def compile_wiki(raw_dir: str = RAW_DIR) -> None:
    """
    Step 1  Extract concepts from all raw documents.
    Step 2  Write a structured wiki article for each concept.
    Step 3  Write a master index.md.
    """
    docs = load_documents(raw_dir)
    if not docs:
        print(f"No documents found in {raw_dir}/")
        return

    os.makedirs(CONCEPTS_DIR, exist_ok=True)

    # ── Step 1: extract concepts ──────────────────────────────────────────────
    preview = "\n\n".join(
        f"=== {name} ===\n{content[:1500]}" for name, content in docs.items()
    )

    raw_json = _llm_call(
        system="You are a knowledge base compiler. Extract key concepts from documents.",
        user=f"""Documents preview:
{preview}

Extract 5-15 key concepts that best represent the content of these documents.
Return ONLY a JSON object in this exact format:
{{
  "concepts": [
    {{
      "concept": "Concept Name",
      "description": "One sentence description",
      "relevant_docs": ["filename1.txt", "filename2.md"]
    }}
  ]
}}""",
        json_mode=True,
    )

    data = json.loads(raw_json)
    concepts: list[dict] = data.get("concepts", [])
    print(f"[karpathy_rag] Extracted {len(concepts)} concepts.")

    # ── Step 2: write a wiki article per concept ──────────────────────────────
    for concept in concepts:
        name     = concept["concept"]
        relevant = concept.get("relevant_docs", list(docs.keys()))

        source_text = "\n\n".join(
            f"=== {n} ===\n{docs[n]}" for n in relevant if n in docs
        )
        if not source_text:
            source_text = "\n\n".join(
                f"=== {n} ===\n{c}" for n, c in list(docs.items())[:3]
            )

        article = _llm_call(
            system="You are a wiki editor. Write comprehensive, well-structured markdown articles.",
            user=f"""Write a wiki article about "{name}" using the source documents below.

Requirements:
- Clear introduction paragraph
- Sections with ## headers for key aspects
- Precise, factual language
- At the end, a ## Related Concepts section listing related concept names as [[Concept Name]]

Source documents:
{source_text}

Write the full markdown article (do not repeat the title — it will be prepended):""",
        )

        filepath = Path(CONCEPTS_DIR) / (safe_filename(name) + ".md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {name}\n\n{article}\n")

        print(f"  Written: {filepath.name}")

    # ── Step 3: write master index ────────────────────────────────────────────
    entries = "\n".join(
        f"- [[{c['concept']}]]: {c['description']}" for c in concepts
    )

    index_body = _llm_call(
        system="You are a wiki editor.",
        user=f"""Write a master index.md for a knowledge base.

Concepts covered:
{entries}

Source documents: {', '.join(docs.keys())}

The index should:
1. One paragraph introducing what this knowledge base covers
2. A ## Concepts section listing every concept with its description
3. A ## Source Documents section listing the original files

Write in markdown:""",
    )

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(index_body + "\n")

    print(f"\n[karpathy_rag] Wiki compiled → {len(concepts)} articles + index.md")


# ── Core: query ───────────────────────────────────────────────────────────────
def query(question: str) -> dict:
    """
    Step 1  LLM reads index.md and selects relevant concept articles.
    Step 2  Read those articles.
    Step 3  LLM answers the question from the article content.
    """
    if not os.path.exists(INDEX_FILE):
        raise FileNotFoundError("Wiki not found. Run: python karpathy_rag.py compile")

    with open(INDEX_FILE, encoding="utf-8") as f:
        index = f.read()

    available = [p.stem.replace("_", " ") for p in Path(CONCEPTS_DIR).glob("*.md")]

    # Step 1: select relevant articles
    raw_json = _llm_call(
        system="You are a research assistant. Select the most relevant wiki articles for a question.",
        user=f"""Knowledge base index:
{index}

Available concept articles: {', '.join(available)}

Question: {question}

Return ONLY a JSON object:
{{
  "relevant_concepts": ["Concept Name 1", "Concept Name 2"],
  "reasoning": "brief explanation of why these are relevant"
}}""",
        json_mode=True,
    )

    selection       = json.loads(raw_json)
    chosen: list[str] = selection.get("relevant_concepts", [])

    # Step 2: read the chosen articles
    context_parts, sources_used = [], []
    for concept in chosen:
        filepath = Path(CONCEPTS_DIR) / (safe_filename(concept) + ".md")
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                context_parts.append(f"## Wiki: {concept}\n\n{f.read()}")
            sources_used.append(concept)

    if not context_parts:
        context_parts = [f"## Index\n\n{index}"]
        sources_used  = ["index"]

    context = "\n\n---\n\n".join(context_parts)

    # Step 3: answer
    answer = _llm_call(
        system=(
            "You are a knowledgeable assistant. Answer questions based strictly on "
            "the provided wiki articles. Cite section headers when relevant."
        ),
        user=f"""Wiki articles:
{context}

Question: {question}

Answer:""",
    )

    return {
        "answer":    answer,
        "sources":   sources_used,
        "reasoning": selection.get("reasoning", ""),
    }


# ── Core: lint ────────────────────────────────────────────────────────────────
def lint_wiki() -> None:
    """LLM health-check: find gaps, inconsistencies, missing links."""
    articles = {}
    for path in Path(CONCEPTS_DIR).glob("*.md"):
        with open(path, encoding="utf-8") as f:
            articles[path.stem] = f.read()

    if not articles:
        print("No wiki articles to lint.")
        return

    summaries = "\n\n".join(
        f"=== {name} ===\n{content[:600]}..." for name, content in articles.items()
    )

    report = _llm_call(
        system="You are a wiki quality reviewer.",
        user=f"""Review these wiki articles:

{summaries}

Report on:
1. Factual inconsistencies between articles
2. Concepts mentioned but missing as articles
3. Articles that could be merged
4. Gaps where information seems incomplete

Format as a markdown health report:""",
    )

    print("\n=== Wiki Health Report ===")
    print(report)


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "compile":
        compile_wiki()

    elif cmd == "query":
        if len(sys.argv) < 3:
            print('Usage: python karpathy_rag.py query "your question"')
            sys.exit(1)
        result = query(sys.argv[2])
        print(f"\nAnswer:\n{result['answer']}")
        print(f"\nWiki articles used: {', '.join(result['sources'])}")
        print(f"Reasoning: {result['reasoning']}")

    elif cmd == "lint":
        lint_wiki()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
