"""
auth.py — JWT + bcrypt auth with lightweight file-backed storage.
"""

import datetime
import json
import os
from typing import Optional

import bcrypt
import jwt

USERS_FILE = os.path.join(os.path.dirname(__file__), ".users.json")
JWT_SECRET = os.environ.get("REPOGUARD_JWT_SECRET", "repoguard_dev_secret_change_me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7


# ── storage helpers ─────────────────────────────────────────────────────── #

def _load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_users(data: dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── password helpers ────────────────────────────────────────────────────── #

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT helpers ─────────────────────────────────────────────────────────── #

def create_jwt(email: str, plan: str) -> str:
    payload = {
        "sub": email,
        "plan": plan,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── CRUD ────────────────────────────────────────────────────────────────── #

def get_user(email: str) -> Optional[dict]:
    users = _load_users()
    return users.get(email.lower().strip())


def register_user(email: str, password: str) -> str:
    email = email.lower().strip()
    if not email or "@" not in email:
        raise ValueError("Invalid email address.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    users = _load_users()
    if email in users:
        raise ValueError("An account with this email already exists.")

    users[email] = {
        "email": email,
        "password_hash": hash_password(password),
        "plan": "free",
    }
    _save_users(users)
    return create_jwt(email, "free")


def login_user(email: str, password: str) -> str:
    email = email.lower().strip()
    user = get_user(email)
    if not user:
        raise ValueError("No account found with that email.")
    if not verify_password(password, user["password_hash"]):
        raise ValueError("Incorrect password.")
    return create_jwt(email, user.get("plan", "free"))


def upgrade_user_plan(email: str, new_plan: str) -> None:
    users = _load_users()
    email = email.lower().strip()
    if email not in users:
        raise ValueError("User not found")
    users[email]["plan"] = new_plan
    _save_users(users)
