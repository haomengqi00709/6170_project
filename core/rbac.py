"""
Role-Based Access Control
-------------------------
Defines permission levels and user model.
Hierarchy (ascending): public < junior < senior < executive
"""

from dataclasses import dataclass
from typing import List, Dict

# Permission hierarchy — order matters (index = rank)
PERMISSION_LEVELS: List[str] = ["public", "junior", "senior", "executive"]


@dataclass
class User:
    user_id: str
    name: str
    level: str        # must be in PERMISSION_LEVELS
    department: str


def levels_at_or_below(level: str) -> List[str]:
    """Return all permission levels this user is allowed to access."""
    if level not in PERMISSION_LEVELS:
        raise ValueError(f"Unknown permission level '{level}'. Valid: {PERMISSION_LEVELS}")
    idx = PERMISSION_LEVELS.index(level)
    return PERMISSION_LEVELS[: idx + 1]


# ── Demo users ────────────────────────────────────────────────────────────────
DEMO_USERS: Dict[str, User] = {
    "alice":     User("alice",     "Alice Chen",  "junior",    "Finance"),
    "bob":       User("bob",       "Bob Wang",    "senior",    "Finance"),
    "carol":     User("carol",     "Carol Liu",   "executive", "Finance"),
    "guest":     User("guest",     "Guest",       "public",    "Public"),
}


def get_user(user_id: str) -> User:
    user = DEMO_USERS.get(user_id)
    if not user:
        raise ValueError(f"User '{user_id}' not found. Demo users: {list(DEMO_USERS)}")
    return user
