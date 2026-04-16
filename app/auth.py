"""
JWT-based authentication helpers.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from .db import get_conn

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-secret-replace-me")
ALGORITHM  = "HS256"
TOKEN_TTL_HOURS = 24 * 7  # 1 week

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer  = HTTPBearer(auto_error=False)


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM
    )

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token")


# ── User helpers ──────────────────────────────────────────────────────────────

def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_conn()
    row  = conn.execute(
        "SELECT id, email, hashed_pw FROM users WHERE email = ?", [email]
    ).fetchone()
    if row:
        return {"id": row[0], "email": row[1], "hashed_pw": row[2]}
    return None

def create_user(email: str, password: str) -> dict:
    conn = get_conn()
    hashed = hash_password(password)
    conn.execute(
        "INSERT INTO users (email, hashed_pw) VALUES (?, ?)", [email, hashed]
    )
    row = conn.execute(
        "SELECT id, email FROM users WHERE email = ?", [email]
    ).fetchone()
    return {"id": row[0], "email": row[1]}


# ── FastAPI dependency ────────────────────────────────────────────────────────

def current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)
) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    return {"id": int(payload["sub"]), "email": payload["email"]}
