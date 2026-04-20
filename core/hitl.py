"""
HITL — Human-in-the-Loop Risk Classifier
-----------------------------------------
Classifies agent actions into three risk tiers and handles them accordingly.

Tier 1  (Low)   — auto-approve, just log
Tier 2  (Medium)— queue for async human review (SLA: 1 hour)
Tier 3  (High)  — synchronous block, human must act before agent continues
"""

from typing import List, Optional
from core.auditor import Auditor

# ── Risk tier keyword sets ────────────────────────────────────────────────────
_TIER_3 = {
    "send_email", "send_notification", "issue_document", "publish",
    "delete_record", "drop_table", "modify_database", "execute_sql",
    "broadcast", "dispatch", "forward", "transfer_funds",
}
_TIER_2 = {
    "draft_document", "update_record", "create_record",
    "schedule_meeting", "assign_task", "generate_report",
}


def classify_risk(action_type: str) -> int:
    a = action_type.lower().replace(" ", "_")
    if any(k in a for k in _TIER_3):
        return 3
    if any(k in a for k in _TIER_2):
        return 2
    return 1


# ── Manager ───────────────────────────────────────────────────────────────────
class HITLManager:
    def __init__(self, auditor: Auditor):
        self.auditor = auditor

    def handle(
        self,
        session_id: str,
        action_type: str,
        action_detail: str,
        reasoning_chain: List[dict],
    ) -> dict:
        """
        Returns a dict with:
            status      "approved" | "queued" | "pending"
            tier        int (1-3)
            review_id   int | None
        """
        tier = classify_risk(action_type)

        if tier == 1:
            print(f"[HITL] ✅ Tier 1 — '{action_type}' auto-approved")
            return {"status": "approved", "tier": 1, "review_id": None}

        review_id = self.auditor.add_pending_review(
            session_id=session_id,
            action_type=action_type,
            action_detail=action_detail,
            reasoning_chain=reasoning_chain,
            risk_tier=tier,
        )

        if tier == 2:
            print(
                f"[HITL] 🟡 Tier 2 — '{action_type}' queued for async review "
                f"(review_id={review_id})"
            )
            return {"status": "queued", "tier": 2, "review_id": review_id}

        # Tier 3 — synchronous block
        print(
            f"\n[HITL] 🔴 Tier 3 — '{action_type}' BLOCKED, pending human review "
            f"(review_id={review_id})"
        )
        print("       Open the reviewer UI:  python ui/reviewer.py")
        return {"status": "pending", "tier": 3, "review_id": review_id}
