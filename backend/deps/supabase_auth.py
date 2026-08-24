"""
Supabase-only identity verification for the FastAPI backend.

Replaces the previous three parallel auth systems (custom users table +
password hashing, hand-rolled OAuth, and a partially-wired Supabase check)
with a single flow:

  1. Frontend authenticates the user with Supabase Auth (email/password,
     Google, GitHub, LinkedIn -- whatever Supabase is configured for).
  2. Frontend sends the Supabase access token as a normal `Authorization:
     Bearer <token>` header on every backend request.
  3. This module verifies that token's signature against
     SUPABASE_JWT_SECRET and resolves `role` from our own `profile_roles`
     table -- never from the token's `user_metadata`, which is writable by
     the end user via the Supabase client SDK and therefore cannot be
     trusted for authorization decisions.
"""
import os
import jwt
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db
from backend.models import ProfileRole

SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")


class CurrentUser(BaseModel):
    profile_id: str
    email: str
    role: str


def decode_supabase_jwt(token: str) -> dict:
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_JWT_SECRET is not configured on the backend.",
        )
    if token.count(".") != 2:
        raise HTTPException(status_code=401, detail="Malformed access token.")
    try:
        return jwt.decode(
            token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated"
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid session token: {e}")


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    return auth_header.split(" ", 1)[1]


def get_verified_claims(request: Request) -> dict:
    """Verifies the token's signature/expiry only. Does NOT resolve a role --
    used by /auth/sync-profile, which runs before a ProfileRole row exists."""
    token = _extract_bearer_token(request)
    return decode_supabase_jwt(token)


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> CurrentUser:
    """Verifies the token AND resolves the caller's role from our own
    profile_roles table. Use this (or require_role) on every route that
    needs to know who's calling."""
    payload = get_verified_claims(request)

    profile_id = payload.get("sub")
    email = payload.get("email")
    if not profile_id or not email:
        raise HTTPException(status_code=401, detail="Token payload missing sub/email.")

    record = db.query(ProfileRole).filter(ProfileRole.profile_id == profile_id).first()
    if not record:
        raise HTTPException(
            status_code=403,
            detail="No profile on file for this account. Call /auth/sync-profile first.",
        )

    return CurrentUser(profile_id=profile_id, email=email, role=record.role)


def require_role(*allowed_roles: str):
    """Dependency factory: Depends(require_role("recruiter", "tpo"))"""

    def _dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"This action requires role: {', '.join(allowed_roles)}.",
            )
        return user

    return _dependency
