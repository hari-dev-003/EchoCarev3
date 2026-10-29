from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.db import get_db
from app.core.deps import audit, current_user, is_admin
from app.core.security import create_token, hash_password, verify_password
from app.core.util import clean, new_id, now_iso

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    consent_ai: bool = False
    consent_web: bool = False


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


def user_out(u: dict) -> dict:
    o = clean(u)
    o["is_admin"] = is_admin(u)
    return o


@router.post("/register")
async def register(body: RegisterIn):
    db = get_db()
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "An account with this email already exists")
    first = await db.users.count_documents({}) == 0
    uid = new_id()
    user = {"_id": uid, "name": body.name.strip(), "email": email, "password_hash": hash_password(body.password),
            "is_admin": first, "language": "en", "created_at": now_iso(),
            "privacy": {"ai_processing": body.consent_ai, "web_search": body.consent_web, "caregiver_sharing": True, "retention_days": None}}
    await db.users.insert_one(user)
    for purpose, granted in (("ai_processing", body.consent_ai), ("web_search", body.consent_web)):
        await db.consents.insert_one({"_id": new_id(), "user_id": uid, "purpose": purpose, "granted": granted,
                                      "text": "Given at registration", "created_at": now_iso()})
    await db.profiles.insert_one({"_id": new_id(), "user_id": uid, "name": body.name.strip(), "relation": "self",
                                  "created_at": now_iso()})
    await audit(user, "register")
    return {"token": create_token(uid), "user": user_out(user)}


@router.post("/login")
async def login(body: LoginIn):
    u = await get_db().users.find_one({"email": body.email.lower()})
    password_hash = u.get("password_hash") if u else None
    if not isinstance(password_hash, str) or not verify_password(body.password, password_hash):
        raise HTTPException(401, "Incorrect email or password")
    await audit(u, "login")
    try:
        from app.routers.safety_net import run_retention
        await run_retention(u)
    except Exception:
        pass
    return {"token": create_token(u["_id"]), "user": user_out(u)}


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return user_out(user)


@router.patch("/me")
async def update_me(body: dict, user: dict = Depends(current_user)):
    allowed = {k: v for k, v in body.items() if k in ("name", "language")}
    if allowed:
        await get_db().users.update_one({"_id": user["_id"]}, {"$set": allowed})
    return user_out(await get_db().users.find_one({"_id": user["_id"]}))


@router.post("/password")
async def change_password(body: PasswordIn, user: dict = Depends(current_user)):
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    await audit(user, "password_change")
    return {"ok": True}
