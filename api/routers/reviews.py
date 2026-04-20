"""
GET  /api/reviews          — list pending (or all) HITL reviews
PUT  /api/reviews/{id}     — resolve a review (approve / reject)
GET  /api/sessions         — recent sessions with their steps
"""

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.deps import auditor

router = APIRouter(prefix="/api")

_REVIEW_COLS = [
    "id", "session_id", "action_type", "action_detail",
    "reasoning_chain", "risk_tier", "status",
    "reviewer_decision", "reviewer_note", "created_at", "reviewed_at",
]

_SESSION_COLS = ["session_id", "user_id", "question", "status", "started_at", "ended_at"]
_STEP_COLS    = ["id", "session_id", "step_id", "action_type",
                 "input_snapshot", "output_snapshot", "cited_sources",
                 "anomaly_score", "anomaly_detected", "timestamp"]


# ── GET /api/reviews ──────────────────────────────────────────────────────────
@router.get("/reviews")
def list_reviews(pending_only: bool = True):
    db = auditor.db_file
    where = "WHERE status='pending'" if pending_only else ""
    with sqlite3.connect(db) as c:
        rows = c.execute(
            f"SELECT * FROM pending_reviews {where} ORDER BY id DESC"
        ).fetchall()
    reviews = [dict(zip(_REVIEW_COLS, r)) for r in rows]
    # parse reasoning_chain JSON
    for r in reviews:
        try:
            r["reasoning_chain"] = json.loads(r["reasoning_chain"])
        except Exception:
            pass
    return reviews


# ── PUT /api/reviews/{id} ─────────────────────────────────────────────────────
class ResolveRequest(BaseModel):
    decision: str   # "approved" | "rejected"
    note: str = ""


@router.put("/reviews/{review_id}")
def resolve_review(review_id: int, body: ResolveRequest):
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    auditor.resolve_review(review_id, body.decision, body.note)
    return {"ok": True, "review_id": review_id, "decision": body.decision}


# ── GET /api/sessions ─────────────────────────────────────────────────────────
@router.get("/sessions")
def list_sessions(limit: int = 20):
    db = auditor.db_file
    with sqlite3.connect(db) as c:
        rows = c.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(zip(_SESSION_COLS, r)) for r in rows]


# ── GET /api/sessions/{session_id}/steps ─────────────────────────────────────
@router.get("/sessions/{session_id}/steps")
def get_steps(session_id: str):
    steps = auditor.get_session_steps(session_id)
    for s in steps:
        try:
            s["cited_sources"] = json.loads(s.get("cited_sources", "[]"))
        except Exception:
            pass
    return steps
