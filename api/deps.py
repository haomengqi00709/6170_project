"""
Shared FastAPI dependencies — singletons initialized once on startup.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from core.vectorstore import AuditBotVectorStore
from core.auditor import Auditor
from core.shadow import ShadowVerifier
from core.events import EventBus

# ── Singletons ────────────────────────────────────────────────────────────────
store   = AuditBotVectorStore(db_dir="chroma_db")
auditor = Auditor(db_file="audit_logs.db")
shadow  = ShadowVerifier()

# One EventBus per session — keyed by session_id
# (we create a fresh bus per query so streams don't bleed)
_buses: dict[str, EventBus] = {}


def get_bus(session_id: str) -> EventBus:
    if session_id not in _buses:
        _buses[session_id] = EventBus()
    return _buses[session_id]


def drop_bus(session_id: str) -> None:
    _buses.pop(session_id, None)
