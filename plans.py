"""
plans.py — Plan definitions for RepoGuard AI.
Two plans: Free and Pro.
"""

"""
plans.py — Canonical plan loader.

This module exposes `get_plan`, `plan_token_limit`, and `plan_analyses_limit`.
If the environment variable `PLANS_VARIANT` is set to `3` or `30`, the loader will
prefer the corresponding `plans_3.py` or `plans_30.py` variant. This lets you
switch behavior quickly for testing without editing source logic.
"""

import os
from importlib import import_module


def _load_variant():
    variant = os.environ.get('PLANS_VARIANT', '').strip()
    if variant == '3':
        try:
            return import_module('plans_3').PLANS
        except Exception:
            pass
    if variant == '30':
        try:
            return import_module('plans_30').PLANS
        except Exception:
            pass
    # fallback: builtin default
    return {
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


PLANS = _load_variant()


def get_plan(plan_name: str) -> dict:
    return PLANS.get(plan_name, PLANS["free"])


def plan_token_limit(plan_name: str) -> int:
    return get_plan(plan_name)["token_limit"]


def plan_analyses_limit(plan_name: str) -> int:
    return get_plan(plan_name)["analyses_per_day"]
