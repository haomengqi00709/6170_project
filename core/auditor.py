"""
Auditor — State Snapshot & Anomaly Detection
---------------------------------------------
Logs every agent step to SQLite.
Detects semantic drift between consecutive steps (possible prompt injection).

Tables:
  sessions         — one row per agent run
  audit_steps      — one row per agent step
  pending_reviews  — HITL queue
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np
from core import llm as _llm

DB_FILE                  = "audit_logs.db"
DRIFT_THRESHOLD          = 0.65   # chain drift: cosine sim between consecutive steps
QUESTION_ANCHOR_THRESHOLD = 0.45  # retriever vs original question; lower bar, catches data poisoning


# ── Math ──────────────────────────────────────────────────────────────────────
def _cosine(a: List[float], b: List[float]) -> float:
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 1e-8 else 1.0


def _embed(text: str) -> List[float]:
    return _llm.embed(text)


# ── Auditor ───────────────────────────────────────────────────────────────────
class Auditor:
    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self._init_db()

    # ── DB setup ──────────────────────────────────────────────────────────────
    def _init_db(self) -> None:
        with sqlite3.connect(self.db_file) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id  TEXT PRIMARY KEY,
                    user_id     TEXT,
                    question    TEXT,
                    status      TEXT,
                    started_at  TEXT,
                    ended_at    TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_steps (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id       TEXT,
                    step_id          TEXT,
                    action_type      TEXT,
                    input_snapshot   TEXT,
                    output_snapshot  TEXT,
                    cited_sources    TEXT,
                    anomaly_score    REAL,
                    anomaly_detected INTEGER,
                    timestamp        TEXT
                );

                CREATE TABLE IF NOT EXISTS pending_reviews (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id        TEXT,
                    action_type       TEXT,
                    action_detail     TEXT,
                    reasoning_chain   TEXT,
                    risk_tier         INTEGER,
                    status            TEXT DEFAULT 'pending',
                    reviewer_decision TEXT,
                    reviewer_note     TEXT,
                    created_at        TEXT,
                    reviewed_at       TEXT
                );
            """)

    # ── Session ───────────────────────────────────────────────────────────────
    def start_session(self, user_id: str, question: str) -> str:
        session_id = str(uuid.uuid4())[:8]
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?,?)",
                (session_id, user_id, question, "active",
                 _now(), None),
            )
        return session_id

    def end_session(self, session_id: str, status: str = "completed") -> None:
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "UPDATE sessions SET status=?, ended_at=? WHERE session_id=?",
                (status, _now(), session_id),
            )

    def suspend_session(self, session_id: str, reason: str = "") -> None:
        self.end_session(session_id, "suspended")
        print(f"\n[AUDIT] ⚠  Session {session_id} SUSPENDED — {reason}")

    # ── Step snapshot ─────────────────────────────────────────────────────────
    def snapshot(
        self,
        session_id: str,
        action_type: str,
        input_text: str,
        output_text: str,
        cited_sources: Optional[List[str]] = None,
        prev_embedding: Optional[List[float]] = None,
        question_embedding: Optional[List[float]] = None,
    ) -> dict:
        """
        Record one agent step. Returns:
            step_id                 str
            embedding               List[float]  — current step embedding
            anomaly_score           float        — cosine sim with previous step (1.0 if first)
            anomaly_detected        bool         — chain drift flag
            question_anchor_score   float|None   — cosine sim vs original question
            question_anchor_anomaly bool         — anchor drift flag (retriever data poisoning)
        """
        step_id        = str(uuid.uuid4())[:8]
        curr_embedding = _embed(output_text)

        anomaly_score    = 1.0
        anomaly_detected = False

        if prev_embedding is not None:
            sim = _cosine(prev_embedding, curr_embedding)
            anomaly_score    = sim
            anomaly_detected = sim < DRIFT_THRESHOLD

        # Question-anchor check (applied when question_embedding is provided)
        question_anchor_score   = None
        question_anchor_anomaly = False
        if question_embedding is not None:
            q_sim = _cosine(question_embedding, curr_embedding)
            question_anchor_score   = round(q_sim, 4)
            question_anchor_anomaly = q_sim < QUESTION_ANCHOR_THRESHOLD

        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                """INSERT INTO audit_steps
                   (session_id, step_id, action_type, input_snapshot,
                    output_snapshot, cited_sources, anomaly_score,
                    anomaly_detected, timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (session_id, step_id, action_type,
                 input_text[:2000], output_text[:2000],
                 json.dumps(cited_sources or []),
                 round(anomaly_score, 4), int(anomaly_detected),
                 _now()),
            )

        return {
            "step_id":                step_id,
            "embedding":              curr_embedding,
            "anomaly_score":          round(anomaly_score, 4),
            "anomaly_detected":       anomaly_detected,
            "question_anchor_score":  question_anchor_score,
            "question_anchor_anomaly": question_anchor_anomaly,
        }

    # ── Queries ───────────────────────────────────────────────────────────────
    def get_session_steps(self, session_id: str) -> List[dict]:
        with sqlite3.connect(self.db_file) as conn:
            rows = conn.execute(
                "SELECT * FROM audit_steps WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        cols = [
            "id", "session_id", "step_id", "action_type",
            "input_snapshot", "output_snapshot", "cited_sources",
            "anomaly_score", "anomaly_detected", "timestamp",
        ]
        return [dict(zip(cols, r)) for r in rows]

    # ── HITL queue ────────────────────────────────────────────────────────────
    def add_pending_review(
        self,
        session_id: str,
        action_type: str,
        action_detail: str,
        reasoning_chain: List[dict],
        risk_tier: int,
    ) -> int:
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.execute(
                """INSERT INTO pending_reviews
                   (session_id, action_type, action_detail,
                    reasoning_chain, risk_tier, status, created_at)
                   VALUES (?,?,?,?,?,'pending',?)""",
                (session_id, action_type, action_detail,
                 json.dumps(reasoning_chain), risk_tier, _now()),
            )
        return cur.lastrowid

    def get_pending_reviews(self) -> List[dict]:
        with sqlite3.connect(self.db_file) as conn:
            rows = conn.execute(
                "SELECT * FROM pending_reviews WHERE status='pending' ORDER BY id DESC"
            ).fetchall()
        return [dict(zip(_REVIEW_COLS, r)) for r in rows]

    def resolve_review(
        self, review_id: int, decision: str, note: str = ""
    ) -> None:
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                """UPDATE pending_reviews
                   SET status='resolved', reviewer_decision=?,
                       reviewer_note=?, reviewed_at=?
                   WHERE id=?""",
                (decision, note, _now(), review_id),
            )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_REVIEW_COLS = [
    "id", "session_id", "action_type", "action_detail",
    "reasoning_chain", "risk_tier", "status",
    "reviewer_decision", "reviewer_note", "created_at", "reviewed_at",
]
