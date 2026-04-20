"""
POST /api/query      — start a pipeline run, returns session_id immediately
GET  /api/events/{session_id}  — SSE stream of EventBus events
GET  /api/result/{session_id}  — final result once done
"""

import asyncio
import json
import threading
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.deps import store, auditor, shadow, get_bus, drop_bus
from core.rbac import get_user

router = APIRouter(prefix="/api")

# session_id → final result dict (populated when pipeline finishes)
_results: dict[str, Optional[dict]] = {}
_done_flags: dict[str, bool] = {}


# ── Request model ─────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    user_id: str
    mode: str = "audited"   # "audited" | "baseline"


# ── POST /api/query ───────────────────────────────────────────────────────────
@router.post("/query")
def start_query(req: QueryRequest):
    try:
        user = get_user(req.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session_id = str(uuid.uuid4())[:8]
    bus = get_bus(session_id)
    _results[session_id] = None
    _done_flags[session_id] = False

    def _run():
        try:
            if req.mode == "baseline":
                from core.baseline import run_baseline
                result = run_baseline(
                    question=req.question,
                    user=user,
                    vectorstore=store,
                    bus=bus,
                )
            else:
                from core import agent as _agent
                result = _agent.run(
                    question=req.question,
                    user=user,
                    vectorstore=store,
                    auditor=auditor,
                    shadow=shadow,
                    bus=bus,
                )
            _results[session_id] = result
        except Exception as exc:
            bus.emit("error", "auditbot", f"Pipeline error: {exc}")
            _results[session_id] = {"error": str(exc)}
        finally:
            _done_flags[session_id] = True

    threading.Thread(target=_run, daemon=True).start()
    return {"session_id": session_id}


# ── GET /api/events/{session_id} — SSE ───────────────────────────────────────
@router.get("/events/{session_id}")
async def event_stream(session_id: str):
    bus = get_bus(session_id)
    sent_count = 0

    async def _generate():
        nonlocal sent_count
        while True:
            events = bus.all()
            # send any new events
            for evt in events[sent_count:]:
                payload = json.dumps({
                    "type":    evt.type,
                    "agent":   evt.agent,
                    "message": evt.message,
                    "data":    evt.data,
                    "ts":      evt.ts,
                })
                yield f"data: {payload}\n\n"
                sent_count += 1

            # send done sentinel when pipeline finishes
            if _done_flags.get(session_id):
                result = _results.get(session_id) or {}
                yield f"data: {json.dumps({'type': '__done__', 'result': result})}\n\n"
                break

            await asyncio.sleep(0.1)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── GET /api/result/{session_id} ──────────────────────────────────────────────
@router.get("/result/{session_id}")
def get_result(session_id: str):
    if session_id not in _results:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "done":   _done_flags.get(session_id, False),
        "result": _results.get(session_id),
    }


# ── GET /api/users ────────────────────────────────────────────────────────────
@router.get("/users")
def list_users():
    from core.rbac import DEMO_USERS
    return [
        {"user_id": u.user_id, "name": u.name, "level": u.level, "department": u.department}
        for u in DEMO_USERS.values()
    ]
