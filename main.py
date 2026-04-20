"""
AuditBot — Main Entry Point
----------------------------
Interactive CLI to run the full audited agent pipeline.

Usage:
    python main.py                          # interactive mode
    python main.py --user bob --q "..."    # single query
    python main.py --ingest                # ingest data/raw/ into vector store

Commands in interactive mode:
    ask     — run a query through the full AuditBot pipeline
    compare — run a query through both simple_rag and karpathy_rag
    ingest  — (re)ingest documents from data/raw/
    review  — list pending HITL reviews and resolve them in terminal
    exit    — quit
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from core.rbac import get_user, DEMO_USERS
from core.vectorstore import AuditBotVectorStore
from core.auditor import Auditor
from core.shadow import ShadowVerifier
from core import agent

# ── Shared instances ──────────────────────────────────────────────────────────
STORE   = AuditBotVectorStore(db_dir="chroma_db")
AUDITOR = Auditor(db_file="audit_logs.db")
SHADOW  = ShadowVerifier()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _ask(user_id: str, question: str) -> None:
    try:
        user = get_user(user_id)
    except ValueError as e:
        print(f"Error: {e}")
        return

    print(f"\n[AuditBot] User: {user.name} ({user.level}) | Question: {question}")
    print("-" * 60)

    result = agent.run(question, user, STORE, AUDITOR, SHADOW)

    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nStatus  : {result['session_status']}")
    print(f"Session : {result['session_id']}")

    if result.get("hitl_result"):
        hr = result["hitl_result"]
        print(f"HITL    : Tier {hr['tier']} — {hr['status'].upper()}", end="")
        if hr.get("review_id"):
            print(f" (review_id={hr['review_id']})", end="")
        print()
        if hr["status"] == "pending":
            print("         → Run: streamlit run ui/reviewer.py")

    print("\nAudit trail:")
    for step in result["steps"]:
        score = step.get("anomaly_score")
        flag  = "🔴" if (score and score < 0.65) else "✅"
        print(f"  {flag} [{step['action']}]  drift={score}")


def _ingest(reset: bool = False) -> None:
    from data.ingest import ingest
    ingest(reset=reset)


def _review_terminal() -> None:
    reviews = AUDITOR.get_pending_reviews()
    if not reviews:
        print("No pending reviews.")
        return

    print(f"\n{len(reviews)} pending review(s):\n")
    for r in reviews:
        print(f"  [{r['id']}] Tier {r['risk_tier']} | {r['action_type']} | Session {r['session_id']}")
        print(f"       {r['action_detail'][:120]}")
        print()

    try:
        rid = int(input("Enter review ID to resolve (0 to skip): "))
    except ValueError:
        return

    if rid == 0:
        return

    decision = input("Decision [approve / reject / clarify]: ").strip().lower()
    if decision not in ("approve", "reject", "clarify"):
        print("Invalid decision.")
        return
    decision_map = {"approve": "approved", "reject": "rejected", "clarify": "clarification_requested"}
    note = input("Note (optional): ").strip()
    AUDITOR.resolve_review(rid, decision_map[decision], note)
    print(f"Review {rid} resolved as '{decision_map[decision]}'.")


def _compare(question: str) -> None:
    import time
    import simple_rag
    import karpathy_rag

    print(f"\n{'='*60}")
    print(f"Comparing: {question}")
    print(f"{'='*60}\n")

    print("── Simple RAG ──────────────────────────────────────────")
    t0 = time.time()
    try:
        r = simple_rag.query(question)
        print(f"Answer:\n{r['answer']}")
        print(f"Sources: {', '.join(r['sources'])}")
        print(f"Latency: {time.time()-t0:.2f}s")
    except Exception as e:
        print(f"Error: {e} (run: python simple_rag.py ingest)")

    print("\n── Karpathy RAG ────────────────────────────────────────")
    t0 = time.time()
    try:
        r = karpathy_rag.query(question)
        print(f"Answer:\n{r['answer']}")
        print(f"Wiki articles: {', '.join(r['sources'])}")
        print(f"Latency: {time.time()-t0:.2f}s")
    except Exception as e:
        print(f"Error: {e} (run: python karpathy_rag.py compile)")


# ── Interactive mode ──────────────────────────────────────────────────────────
def interactive() -> None:
    print("\n🔍 AuditBot Interactive CLI")
    print(f"   Demo users: {', '.join(DEMO_USERS.keys())}")
    print("   Commands: ask | compare | ingest | review | exit\n")

    while True:
        try:
            cmd = input("auditbot> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not cmd:
            continue

        if cmd == "exit":
            break

        elif cmd == "ask":
            user_id  = input("  User ID: ").strip()
            question = input("  Question: ").strip()
            _ask(user_id, question)

        elif cmd == "compare":
            question = input("  Question: ").strip()
            _compare(question)

        elif cmd == "ingest":
            reset = input("  Reset DB first? [y/N]: ").strip().lower() == "y"
            _ingest(reset=reset)

        elif cmd == "review":
            _review_terminal()

        else:
            print(f"  Unknown command: '{cmd}'")


# ── CLI flags ─────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="AuditBot CLI")
    parser.add_argument("--user",   help="User ID for a single query")
    parser.add_argument("--q",      help="Question for a single query")
    parser.add_argument("--ingest", action="store_true", help="Ingest data/raw/")
    parser.add_argument("--reset",  action="store_true", help="Reset DB before ingest")
    args = parser.parse_args()

    if args.ingest:
        _ingest(reset=args.reset)
    elif args.user and args.q:
        _ask(args.user, args.q)
    else:
        interactive()


if __name__ == "__main__":
    main()
