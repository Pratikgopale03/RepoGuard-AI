"""
plans_30.py — Variant where Pro token limit is 30 (default production-like behavior).
"""

PLANS: dict = {
    "free": {
        "name": "Free",
        "price": "$0",
        "period": "forever",
        "token_limit": 3,
        "analyses_per_day": 3,
        "features": [
            "3 analyses per day",
            "3 tokens per day",
            "Basic health & security insights",
            "PDF export",
            "Community support",
        ],
        "not_included": ["Priority support", "Unlimited analyses"],
        "highlight": False,
        "cta": "Get Started Free",
    },
    "pro": {
        "name": "Pro",
        "price": "Rs 499",
        "period": "per month",
        "token_limit": 30,
        "analyses_per_day": 30,
        "features": [
            "30 analyses per day",
            "30 tokens per day",
            "Advanced AI insights",
            "PDF export",
            "Priority support",
            "Early access to new features",
        ],
        "not_included": [],
        "highlight": True,
        "cta": "Upgrade to Pro",
    },
}

def get_plan(plan_name: str) -> dict:
    return PLANS.get(plan_name, PLANS["free"])

def plan_token_limit(plan_name: str) -> int:
    return get_plan(plan_name)["token_limit"]

def plan_analyses_limit(plan_name: str) -> int:
    return get_plan(plan_name)["analyses_per_day"]
