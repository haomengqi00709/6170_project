"""
AuditBot Demo UI
----------------
Rich terminal UI with live left/right panels.

Left  — Agent workflow: Planner → Retriever → Synthesizer
Right — AuditBot monitor: audit log, drift scores, HITL status

Usage (from Build/):
    from ui.demo_ui import run_demo
    run_demo("your question", "bob", store, auditor, shadow)

Or directly:
    python ui/demo_ui.py "your question" bob
"""

import sys
import threading
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.events import Event, EventBus, bus as _default_bus

# ── Style constants ───────────────────────────────────────────────────────────
_AGENT_COLOR = {
    "planner":     "cyan",
    "retriever":   "blue",
    "synthesizer": "green",
    "auditbot":    "yellow",
}

_EVENT_ICON = {
    "thinking":    "💭",
    "retrieving":  "🔍",
    "found":       "📄",
    "reasoning":   "🧠",
    "audit":       "✅",
    "anomaly":     "🔴",
    "hitl":        "🚨",
    "shadow_fail": "⚠️",
    "done":        "✓",
    "complete":    "🏁",
    "error":       "❌",
}

_AGENTS = [
    ("planner",     "1. PLANNER"),
    ("retriever",   "2. RETRIEVER"),
    ("synthesizer", "3. SYNTHESIZER"),
]


# ── Helper: agent status ──────────────────────────────────────────────────────
def _agent_status(events: list[Event], agent: str) -> tuple[str, str]:
    """Returns (icon, style) based on the agent's event history."""
    mine = [e for e in events if e.agent == agent]
    if not mine:
        return "○", "dim"

    has_anomaly = any(
        e.type == "anomaly" and e.data.get("agent_step") == agent
        for e in events
        if e.agent == "auditbot"
    )
    if has_anomaly:
        return "✗", "bold red"

    done = [e for e in mine if e.type == "done"]
    if done:
        return "✓", "bold green"

    return "●", "bold yellow"   # still running


# ── Helper: score bar ─────────────────────────────────────────────────────────
def _score_bar(score: float, width: int = 14) -> Text:
    filled = round(score * width)
    bar    = "█" * filled + "░" * (width - filled)
    style  = "green" if score >= 0.80 else "yellow" if score >= 0.65 else "red"
    t = Text()
    t.append(bar, style=style)
    t.append(f"  {score:.3f}", style="white")
    return t


# ── Left panel ────────────────────────────────────────────────────────────────
def _build_left(events: list[Event]) -> Panel:
    renderables = []

    for i, (agent_id, label) in enumerate(_AGENTS):
        color        = _AGENT_COLOR[agent_id]
        icon, istyle = _agent_status(events, agent_id)
        mine         = [e for e in events if e.agent == agent_id]

        # Agent box content
        content = Text()
        for e in mine[-5:]:
            ev_icon = _EVENT_ICON.get(e.type, "•")
            line    = f"{ev_icon} {e.message[:55]}"
            style   = "dim" if e.type == "done" else "white"
            content.append(line + "\n", style=style)

        if not content:
            content = Text("Waiting…", style="dim")

        title = Text()
        title.append(f" {icon} ", style=istyle)
        title.append(label, style=f"bold {color}")

        renderables.append(
            Panel(content, title=title, border_style=color, padding=(0, 1))
        )

        if i < len(_AGENTS) - 1:
            renderables.append(Align.center(Text("↓", style="dim white")))

    return Panel(
        Group(*renderables),
        title="[bold white]AGENT WORKFLOW[/bold white]",
        border_style="white",
        padding=(0, 1),
    )


# ── Right panel ───────────────────────────────────────────────────────────────
def _build_right(events: list[Event], result: Optional[dict]) -> Panel:

    # ── Audit log table ───────────────────────────────────────────────────────
    log_table = Table(
        show_header=True,
        header_style="bold yellow",
        box=box.SIMPLE_HEAVY,
        padding=(0, 1),
        expand=True,
    )
    log_table.add_column("Time",  style="dim",    width=8,  no_wrap=True)
    log_table.add_column("Agent", width=11,                 no_wrap=True)
    log_table.add_column("Event",                           no_wrap=False)

    for e in events[-14:]:
        ev_icon = _EVENT_ICON.get(e.type, "•")
        color   = _AGENT_COLOR.get(e.agent, "white")
        is_bad  = e.type in ("anomaly", "hitl", "shadow_fail", "error")
        row_style = "bold red" if is_bad else "white"
        log_table.add_row(
            Text(e.ts, style="dim"),
            Text(e.agent, style=color),
            Text(f"{ev_icon} {e.message[:45]}", style=row_style),
        )

    # ── Drift score bars ──────────────────────────────────────────────────────
    audit_events = [
        e for e in events
        if e.agent == "auditbot"
        and e.type in ("audit", "anomaly")
        and "score" in e.data
    ]
    scores: dict[str, float] = {}
    for e in audit_events:
        step = e.data.get("agent_step", "?")
        scores[step] = e.data["score"]

    score_text = Text()
    if scores:
        for step, score in scores.items():
            score_text.append(f"  {step:<12} ")
            score_text.append_text(_score_bar(score))
            score_text.append("\n")
    else:
        score_text.append("  Waiting for data…", style="dim")

    # ── Status ────────────────────────────────────────────────────────────────
    status_text  = Text()
    anomalies    = [e for e in events if e.type == "anomaly"]
    hitl_events  = [e for e in events if e.type == "hitl"]
    complete_ev  = [e for e in events if e.type == "complete"]

    if anomalies:
        status_text.append("⚠  SUSPENDED\n", style="bold red")
        status_text.append(f"   {anomalies[-1].message[:60]}", style="red")
    elif hitl_events:
        last = hitl_events[-1]
        tier = last.data.get("tier", "?")
        rid  = last.data.get("review_id", "?")
        color = "bold red" if tier == 3 else "bold yellow"
        status_text.append(
            f"{'🔴' if tier==3 else '🟡'} {'BLOCKED' if tier==3 else 'QUEUED'}"
            f" — Tier {tier}\n",
            style=color,
        )
        status_text.append(f"   Action:    {result['action_type'] if result else '?'}\n")
        status_text.append(f"   Review ID: {rid}\n")
        status_text.append("   Run: python ui/reviewer.py", style="dim")
    elif complete_ev:
        status_text.append("🏁 COMPLETE", style="bold green")
        if result:
            status_text.append(
                f"\n   Action: {result.get('action_type', '?')}", style="green"
            )
    else:
        status_text.append("⏳ Running…", style="dim yellow")

    body = Group(
        Panel(log_table,   title="[bold yellow]AUDIT LOG[/bold yellow]",    border_style="yellow", padding=(0, 0)),
        Panel(score_text,  title="[bold yellow]DRIFT SCORES[/bold yellow]", border_style="yellow", padding=(0, 1)),
        Panel(status_text, title="[bold yellow]STATUS[/bold yellow]",       border_style="yellow", padding=(0, 1)),
    )

    return Panel(
        body,
        title="[bold yellow]AUDITBOT MONITOR[/bold yellow]",
        border_style="yellow",
        padding=(0, 0),
    )


# ── Main entry ────────────────────────────────────────────────────────────────
def run_demo(
    question: str,
    user_id: str,
    store,
    auditor,
    shadow,
    bus: EventBus = None,
) -> Optional[dict]:
    """
    Run the AuditBot pipeline and display the split-panel live UI.
    Blocks until the pipeline finishes, then waits for Enter.
    """
    if bus is None:
        bus = _default_bus

    bus.clear()

    from core.rbac import get_user
    from core import agent as _agent

    try:
        user = get_user(user_id)
    except ValueError as e:
        print(f"[demo_ui] Error: {e}")
        return None

    # Run pipeline in background thread
    result_holder: dict = {"result": None, "done": False}

    def _run():
        try:
            result_holder["result"] = _agent.run(
                question, user, store, auditor, shadow, bus
            )
        except Exception as exc:
            bus.emit("error", "auditbot", f"Pipeline error: {exc}")
        finally:
            result_holder["done"] = True

    threading.Thread(target=_run, daemon=True).start()

    # ── Build layout ──────────────────────────────────────────────────────────
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(name="left",  ratio=1),
        Layout(name="right", ratio=1),
    )

    def _refresh():
        events = bus.all()
        result = result_holder["result"]

        layout["header"].update(Panel(
            Text.assemble(
                ("User: ",     "bold"), (f"{user.name}  ",  _AGENT_COLOR["planner"]),
                ("Level: ",    "bold"), (f"{user.level}  ", "white"),
                ("Dept: ",     "bold"), (f"{user.department}\n", "white"),
                ("Question: ", "bold"), (question[:110], "white"),
            ),
            title="[bold cyan]AuditBot Demo[/bold cyan]",
            border_style="cyan",
        ))
        layout["left"].update(_build_left(events))
        layout["right"].update(_build_right(events, result))

    console = Console()

    with Live(layout, console=console, refresh_per_second=4, screen=True):
        while not result_holder["done"]:
            _refresh()
            time.sleep(0.25)
        _refresh()          # final render
        time.sleep(1.0)     # hold final state briefly

    # ── Post-demo summary (after Live exits, terminal is back to normal) ──────
    r = result_holder["result"]
    if r:
        console.rule("[cyan]Result[/cyan]")
        console.print(f"\n[bold]Answer:[/bold]\n{r['answer']}\n")
        console.print(f"[bold]Status:[/bold] {r['session_status']}")
        if r.get("hitl_result"):
            h = r["hitl_result"]
            console.print(
                f"[bold]HITL:[/bold] Tier {h['tier']} — "
                f"[{'red' if h['tier']==3 else 'yellow'}]{h['status'].upper()}[/]"
            )
        console.print()

    input("Press Enter to continue…")
    return r


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python ui/demo_ui.py \"question\" user_id")
        sys.exit(1)

    from dotenv import load_dotenv
    load_dotenv()

    from core.vectorstore import AuditBotVectorStore
    from core.auditor import Auditor
    from core.shadow import ShadowVerifier

    run_demo(
        question=sys.argv[1],
        user_id=sys.argv[2],
        store=AuditBotVectorStore(),
        auditor=Auditor(),
        shadow=ShadowVerifier(),
    )
