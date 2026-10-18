from fastapi import APIRouter, Depends, HTTPException

from app.core.db import get_db
from app.core.deps import audit, current_user
from app.core.util import clean_many, new_id, now_iso
from app.services import rag

router = APIRouter(prefix="/api/profiles", tags=["profiles"])
PROFILE_COLLECTIONS = ["story_entries", "survey_responses", "tracker_entries", "vitals", "reports", "medicines", "dose_logs",
                       "appointments", "insights", "chat_messages", "opinions", "goals", "emergency_cards", "evidence_chunks",
                       "notifications_read", "quiz_results", "flashcard_progress", "report_files", "profile_shares", "share_links", "verified_reports"]


@router.get("")
async def list_profiles(user: dict = Depends(current_user)):
    return clean_many(await get_db().profiles.find({"user_id": user["_id"]}).to_list(100))


@router.post("")
async def create_profile(body: dict, user: dict = Depends(current_user)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(422, "Name is required")
    doc = {"_id": new_id(), "user_id": user["_id"], "name": name, "relation": body.get("relation") or "family",
           "dob": body.get("dob"), "gender": body.get("gender"), "created_at": now_iso()}
    await get_db().profiles.insert_one(doc)
    await audit(user, "profile_create", name)
    return clean_many([doc])[0]


@router.patch("/{pid}")
async def update_profile(pid: str, body: dict, user: dict = Depends(current_user)):
    allowed = {k: v for k, v in body.items() if k in ("name", "relation", "dob", "gender")}
    res = await get_db().profiles.update_one({"_id": pid, "user_id": user["_id"]}, {"$set": allowed})
    if not res.matched_count:
        raise HTTPException(404, "Profile not found")
    return {"ok": True}


@router.delete("/{pid}")
async def delete_profile(pid: str, user: dict = Depends(current_user)):
    db = get_db()
    prof = await db.profiles.find_one({"_id": pid, "user_id": user["_id"]})
    if not prof:
        raise HTTPException(404, "Profile not found")
    if prof["relation"] == "self":
        raise HTTPException(400, "Your own profile cannot be deleted")
    for c in PROFILE_COLLECTIONS:
        await db[c].delete_many({"profile_id": pid})
    await db.alert_settings.delete_one({"_id": pid})
    await rag.delete_for_profile(pid)
    await db.profiles.delete_one({"_id": pid})
    await audit(user, "profile_delete", prof["name"])
    return {"ok": True}
