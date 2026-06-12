"""
token_tracker.py — Lightweight per-user daily usage tracking (file-backed).
"""

import datetime
import json
import os
from typing import Dict

from plans import plan_token_limit, plan_analyses_limit
from auth import get_user

USAGE_FILE = os.path.join(os.path.dirname(__file__), ".usage.json")


def _today() -> str:
    return datetime.date.today().isoformat()


def _load_usage() -> Dict[str, dict]:
    if not os.path.exists(USAGE_FILE):
        return {}
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_usage(data: Dict[str, dict]) -> None:
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Write ────────────────────────────────────────────────────────────────── #

def record_usage(email: str, tokens: int) -> None:
    """Increment today's token + analysis count for the given user."""
    if not get_user(email):
        raise ValueError("User not found")
    usage = _load_usage()
    today = _today()
    user_entry = usage.setdefault(email, {})
    today_row = user_entry.setdefault(today, {"tokens_used": 0, "analyses_count": 0})
    today_row["tokens_used"] += max(0, int(tokens))
    today_row["analyses_count"] += 1
    _save_usage(usage)


# ── Read ─────────────────────────────────────────────────────────────────── #

def get_usage_today(email: str) -> dict:
    usage = _load_usage()
    today = _today()
    return usage.get(email, {}).get(today, {"tokens_used": 0, "analyses_count": 0})


def tokens_remaining(email: str, plan: str) -> int:
    limit = plan_token_limit(plan)
    used = get_usage_today(email).get("tokens_used", 0)
    return max(0, limit - used)


def analyses_remaining(email: str, plan: str) -> int:
    limit = plan_analyses_limit(plan)
    used = get_usage_today(email).get("analyses_count", 0)
    return max(0, limit - used)


def can_run_analysis(email: str, plan: str) -> bool:
    return analyses_remaining(email, plan) > 0 and tokens_remaining(email, plan) > 0


def estimate_tokens(text: str) -> int:
    # Simple heuristic: 1 token ≈ 4 chars
    return max(1, len(text) // 4)
