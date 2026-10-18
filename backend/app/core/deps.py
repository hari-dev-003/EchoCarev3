import time

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import decode_token
from app.core.util import clean

bearer = HTTPBearer(auto_error=False)


async def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = await get_db().users.find_one({"_id": payload["sub"]})
    if not user or user.get("disabled"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not available")
    # Consent gating: Gemini / Tavily are only used when the user has switched them on in Privacy & consent.
    from app.services import llm
    priv = user.get("privacy") or {}
    llm.ai_allowed.set(bool(priv.get("ai_processing", False)))
    llm.web_allowed.set(bool(priv.get("web_search", False)))
    return user


SCOPE_BY_PATH = (("/reports", "reports"), ("/labs", "reports"), ("/vault", "reports"), ("/medicines", "medicines"), ("/doses", "medicines"),
                 ("/vitals", "vitals"), ("/tracker", "vitals"), ("/risk-flags", "vitals"), ("/insights", "insights"),
                 ("/evidence", "insights"), ("/chat", "insights"), ("/timeline", "insights"))
ALL_SCOPES = ["records", "reports", "vitals", "medicines", "insights"]
_seen: dict = {}


def scope_for(path: str) -> str:
    for frag, sc in SCOPE_BY_PATH:
        if frag in path:
            return sc
    return "records"


async def current_profile(request: Request, user: dict = Depends(current_user), x_profile_id: str | None = Header(default=None)) -> dict:
    """The profile (self, family member, or one a caregiver was granted access to) the request acts on.
    Owners have full access; caregivers need an accepted share, and are limited by role (viewer = read-only) and scope."""
    db = get_db()
    if x_profile_id:
        prof = await db.profiles.find_one({"_id": x_profile_id, "user_id": user["_id"]})
        if prof:
            return prof
        share = await db.profile_shares.find_one({"profile_id": x_profile_id, "grantee_user_id": user["_id"], "status": "accepted"})
        prof = await db.profiles.find_one({"_id": x_profile_id}) if share else None
        if not share or not prof:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
        sc = scope_for(request.url.path)
        if sc not in (share.get("scopes") or ALL_SCOPES):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"The owner has not shared '{sc}' with you")
        if request.method != "GET" and share.get("role") != "editor":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You have view-only access to this profile")
        key = (user["_id"], x_profile_id, request.method)
        if time.time() - _seen.get(key, 0) > 600:
            _seen[key] = time.time()
            await audit(user, "shared_access", f"{share.get('role')} {request.method} {request.url.path}"[:200], x_profile_id)
        prof = dict(prof)
        prof["_shared"] = {"role": share.get("role"), "owner_user_id": prof["user_id"]}
        return prof
    prof = await db.profiles.find_one({"user_id": user["_id"], "relation": "self"})
    if not prof:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No profile found for this account")
    return prof


async def owner_profile(user: dict = Depends(current_user), x_profile_id: str | None = Header(default=None)) -> dict:
    """Like current_profile but OWNER ONLY (used for sharing, privacy, destructive actions)."""
    q = {"_id": x_profile_id, "user_id": user["_id"]} if x_profile_id else {"user_id": user["_id"], "relation": "self"}
    prof = await get_db().profiles.find_one(q)
    if not prof:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found (or you are not its owner)")
    return prof


def is_admin(user: dict) -> bool:
    return bool(user.get("is_admin")) or user["email"].lower() in get_settings().admin_emails


async def require_admin(user: dict = Depends(current_user)) -> dict:
    if not is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


async def audit(user: dict | None, action: str, detail: str = "", profile_id: str | None = None) -> None:
    from app.core.util import new_id, now_iso
    try:
        await get_db().audit_logs.insert_one({
            "_id": new_id(), "user_id": user["_id"] if user else None, "email": user["email"] if user else None,
            "action": action, "detail": detail[:300], "profile_id": profile_id, "created_at": now_iso()})
    except Exception:
        pass
