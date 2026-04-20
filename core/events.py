"""
Event Bus
---------
Thread-safe event queue that agents emit to and the UI reads from.

Usage:
    from core.events import bus

    # In an agent:
    bus.emit("thinking", "planner", "Analyzing question...")

    # In the UI:
    events = bus.all()
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class Event:
    type: str     # "thinking" | "retrieving" | "found" | "reasoning" |
                  # "audit" | "anomaly" | "hitl" | "shadow_fail" | "done" |
                  # "complete" | "error"
    agent: str    # "planner" | "retriever" | "synthesizer" | "auditbot"
    message: str
    data: dict    = field(default_factory=dict)
    ts: str       = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


class EventBus:
    def __init__(self) -> None:
        self._events: List[Event] = []
        self._lock = threading.Lock()

    def emit(self, type: str, agent: str, message: str, **data) -> None:
        with self._lock:
            self._events.append(Event(type=type, agent=agent, message=message, data=data))

    def all(self) -> List[Event]:
        with self._lock:
            return list(self._events)

    def for_agent(self, agent: str) -> List[Event]:
        with self._lock:
            return [e for e in self._events if e.agent == agent]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


# Module-level singleton — import this everywhere
bus = EventBus()
