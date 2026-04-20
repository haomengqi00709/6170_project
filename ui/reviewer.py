"""
AuditBot — HITL Reviewer (Terminal)
-------------------------------------
Rich terminal interface for reviewing and resolving pending HITL actions.
No web server required.

Usage (from Build/):
    python ui/reviewer.py           # list + resolve pending reviews
    python ui/reviewer.py --all     # show full history
"""

import json
import sys
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich.rule import Rule

DB_FILE = Path(__file__).parent.parent / "audit_logs.db"
console = Console()


# ── DB helpers ────────────────────────────────────────────────────────────────
def _conn():
    return sqlite3.connect(str(DB_FILE))


def get_reviews(pending_only: bool = True) -> list[dict]:
    cols = ["id","session_id","action_type","action_detail","reasoning_chain",
            "risk_tier","status","reviewer_decision","reviewer_note",
            "created_at","reviewed_at"]
    where = "WHERE status='pending'" if pending_only else ""
    with _conn() as c:
        rows = c.execute(
            f"SELECT * FROM pending_reviews {where} ORDER BY risk_tier DESC, id DESC"
        ).fetchall()
    return [dict(zip(cols, r)) for r in rows]


def get_steps(session_id: str) -> list[tuple]:
    with _conn() as c:
        return c.execute(
            """SELECT action_type, input_snapshot, output_snapshot,
                      anomaly_score, anomaly_detected, timestamp
               FROM audit_steps WHERE session_id=? ORDER BY id""",
            (session_id,),
        ).fetchall()


def resolve(review_id: int, decision: str, note: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            """UPDATE pending_reviews
               SET status='resolved', reviewer_decision=?,
                   reviewer_note=?, reviewed_at=?
               WHERE id=?""",
            (decision, note, now, review_id),
        )


# ── Display helpers ───────────────────────────────────────────────────────────
def _tier_color(tier: int) -> str:
    return {1: "green", 2: "yellow", 3: "red"}.get(tier, "white")


def _drift_badge(score: float) -> Text:
    style = "green" if score >= 0.80 else "yellow" if score >= 0.65 else "red"
    bar   = "█" * round(score * 10) + "░" * (10 - round(score * 10))
    t = Text()
    t.append(bar, style=style)
    t.append(f" {score:.3f}", style="white")
    return t


def _print_review(r: dict) -> None:
    tier  = r["risk_tier"]
    color = _tier_color(tier)

    console.print()
    console.rule(
        f"[bold {color}]Review #{r['id']}  |  Tier {tier}  |  "
        f"{r['action_type']}  |  Session {r['session_id']}[/bold {color}]"
    )

    # Action detail
    console.print(Panel(
        r["action_detail"],
        title="[bold]Proposed Action[/bold]",
        border_style=color,
    ))

    # Reasoning chain
    try:
        chain = json.loads(r["reasoning_chain"])
        table = Table(title="Reasoning Chain", box=box.SIMPLE_HEAVY,
                      show_header=True, header_style="bold")
        table.add_column("Step", width=14)
        table.add_column("Info")
        for step in chain:
            action = step.get("action", "?")
            detail = []
            if step.get("anomaly_score") is not None:
                detail.append(f"drift={step['anomaly_score']:.3f}")
            if step.get("shadow_flags"):
                detail.append(f"shadow: {'; '.join(step['shadow_flags'])[:60]}")
            if step.get("answer_preview"):
                detail.append(step["answer_preview"][:80])
            table.add_row(action, "  |  ".join(detail) or "—")
        console.print(table)
    except Exception:
        console.print(r["reasoning_chain"])

    # Audit trail
    steps = get_steps(r["session_id"])
    if steps:
        audit_table = Table(title="Audit Trail", box=box.SIMPLE,
                            show_header=True, header_style="bold yellow")
        audit_table.add_column("Action",  width=14)
        audit_table.add_column("Drift Score", width=20)
        audit_table.add_column("Anomaly", width=8)
        audit_table.add_column("Time")
        for action_type, _, _, score, detected, ts in steps:
            drift  = _drift_badge(score) if score else Text("—")
            anomaly = Text("YES", style="bold red") if detected else Text("no", style="dim")
            audit_table.add_row(action_type, drift, anomaly, ts)
        console.print(audit_table)

    console.print(f"Created: [dim]{r['created_at']}[/dim]")


# ── Main flow ─────────────────────────────────────────────────────────────────
def review_pending() -> None:
    if not DB_FILE.exists():
        console.print("[yellow]No audit database found. Run a demo scenario first.[/yellow]")
        return

    reviews = get_reviews(pending_only=True)

    if not reviews:
        console.print("\n[bold green]✅  No pending reviews — all clear.[/bold green]\n")
        return

    console.print(f"\n[bold red]{len(reviews)} pending review(s) require your attention.[/bold red]")

    for r in reviews:
        _print_review(r)
        console.print()

        decision = Prompt.ask(
            f"  Decision for Review #{r['id']}",
            choices=["approve", "reject", "skip"],
            default="skip",
        )

        if decision == "skip":
            console.print("  [dim]Skipped.[/dim]")
            continue

        note = Prompt.ask("  Note (optional)", default="")
        decision_key = {"approve": "approved", "reject": "rejected"}[decision]
        resolve(r["id"], decision_key, note)

        color = "green" if decision == "approve" else "red"
        console.print(
            f"  [bold {color}]Review #{r['id']} {decision_key.upper()}.[/bold {color}]"
        )

    console.print()


def show_history() -> None:
    if not DB_FILE.exists():
        console.print("[yellow]No audit database found.[/yellow]")
        return

    reviews = get_reviews(pending_only=False)
    if not reviews:
        console.print("No reviews yet.")
        return

    table = Table(title="Review History", box=box.SIMPLE_HEAVY,
                  show_header=True, header_style="bold")
    table.add_column("ID",       width=4)
    table.add_column("Tier",     width=5)
    table.add_column("Status",   width=12)
    table.add_column("Decision", width=12)
    table.add_column("Action",   width=20)
    table.add_column("Session",  width=10)
    table.add_column("Created")

    for r in reviews:
        tier   = r["risk_tier"]
        color  = _tier_color(tier)
        status = r["status"]
        s_color = "green" if status == "resolved" else "yellow"
        table.add_row(
            str(r["id"]),
            Text(str(tier), style=f"bold {color}"),
            Text(status, style=s_color),
            r["reviewer_decision"] or "—",
            r["action_type"],
            r["session_id"],
            r["created_at"],
        )

    console.print(table)


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--all" in sys.argv:
        show_history()
    else:
        review_pending()
