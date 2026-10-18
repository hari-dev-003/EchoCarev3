"""Alerts (configurable thresholds), privacy & consent, audit trail, caregiver sharing, secure share links."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import ALL_SCOPES, audit, current_profile, current_user, owner_profile
from app.core.util import clean, clean_many, new_id, now_iso
from app.routers.profiles import PROFILE_COLLECTIONS
from app.services import alerts as al, health_rules as hr, labs, rag

router = APIRouter(prefix="/api", tags=["safety-net"])


# ======================= Alerts =======================
@router.get("/alerts")
async def alerts_list(prof=Depends(current_profile)):
    items = await al.evaluate(prof["_id"])
    return {"items": items, "counts": {u: sum(1 for i in items if i["urgency"] == u) for u in ("urgent", "soon", "routine")},
            "thresholds": await al.get_settings_for(prof["_id"]), "defaults": al.DEFAULTS, "limits": al.LIMITS,
            "disclaimer": "Alerts compare your own readings with thresholds you can change. They are prompts to seek care, not diagnoses."}


@router.put("/alerts/thresholds")
async def alerts_set(body: dict, user=Depends(current_user), prof=Depends(current_profile)):
    try:
        patch = al.validate(body.get("thresholds", body))
    except ValueError as e:
        raise HTTPException(422, str(e))
    cur = await al.get_settings_for(prof["_id"])
    await get_db().alert_settings.replace_one({"_id": prof["_id"]}, {"_id": prof["_id"], "thresholds": {**cur, **patch}, "updated_at": now_iso()}, upsert=True)
    await audit(user, "alert_thresholds_update", ", ".join(patch)[:200], prof["_id"])
    return {"thresholds": {**cur, **patch}}


@router.delete("/alerts/thresholds")
async def alerts_reset(user=Depends(current_user), prof=Depends(current_profile)):
    await get_db().alert_settings.delete_one({"_id": prof["_id"]})
    await audit(user, "alert_thresholds_reset", "", prof["_id"])
    return {"thresholds": al.DEFAULTS}


# ======================= Privacy & consent =======================
CONSENT_TEXT = {
    "ai_processing": "Send my health notes, reports and photos I choose to analyse to Google Gemini to generate insights, summaries and chat replies.",
    "web_search": "Allow Echo to run web searches (Tavily) using non-identifying parts of my questions.",
    "caregiver_sharing": "Allow me to invite caregivers and create secure share links to my records.",
}
PRIV_DEFAULT = {"ai_processing": False, "web_search": False, "caregiver_sharing": True, "retention_days": None}


def _priv(u: dict) -> dict:
    return {**PRIV_DEFAULT, **(u.get("privacy") or {})}


@router.get("/privacy")
async def privacy_get(user=Depends(current_user)):
    db = get_db()
    profs = await db.profiles.find({"user_id": user["_id"]}).to_list(100)
    counts = {}
    for c in PROFILE_COLLECTIONS:
        n = 0
        for p in profs:
            n += await db[c].count_documents({"profile_id": p["_id"]})
        counts[c] = n
    files = []
    for p in profs:
        files += await db.report_files.find({"profile_id": p["_id"]}).to_list(1000)
    return {"settings": _priv(user), "consent_text": CONSENT_TEXT, "data_counts": {k: v for k, v in counts.items() if v},
            "stored_files": len(files), "stored_bytes": sum(f["size"] for f in files),
            "ai_key_present": bool(get_settings().GOOGLE_API_KEY.strip()), "web_key_present": bool(get_settings().TAVILY_API_KEY.strip()),
            "notes": ["Nothing is sent to Gemini or Tavily unless you switch the matching consent on.",
                      "Your records stay in your own MongoDB database. Turning consent off stops future sends; it cannot recall data already processed by a provider."]}


@router.put("/privacy")
async def privacy_set(body: dict, user=Depends(current_user)):
    db = get_db()
    cur = _priv(user)
    new = dict(cur)
    for k in ("ai_processing", "web_search", "caregiver_sharing"):
        if k in body:
            new[k] = bool(body[k])
    if "retention_days" in body:
        rd = body["retention_days"]
        if rd in (None, "", 0):
            new["retention_days"] = None
        else:
            try:
                rd = int(rd)
            except (TypeError, ValueError):
                raise HTTPException(422, "retention_days must be a whole number")
            if not 30 <= rd <= 3650:
                raise HTTPException(422, "retention_days must be between 30 and 3650")
            new["retention_days"] = rd
    for k in CONSENT_TEXT:
        if new[k] != cur[k]:
            await db.consents.insert_one({"_id": new_id(), "user_id": user["_id"], "purpose": k, "granted": new[k], "text": CONSENT_TEXT[k], "created_at": now_iso()})
            await audit(user, f"consent_{'granted' if new[k] else 'withdrawn'}", k)
    if new["retention_days"] != cur["retention_days"]:
        await audit(user, "retention_set", str(new["retention_days"]))
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"privacy": new}})
    if new["ai_processing"] != cur["ai_processing"]:  # the active embedding backend may change, so rebuild the vector index
        for p in await db.profiles.find({"user_id": user["_id"]}).to_list(100):
            try:
                from app.services import llm
                llm.ai_allowed.set(new["ai_processing"])
                await rag.reindex_all(p["_id"])
            except Exception:
                pass
    return {"settings": new}


@router.get("/privacy/consents")
async def consent_history(user=Depends(current_user)):
    rows = await get_db().consents.find({"user_id": user["_id"]}).to_list(500)
    return clean_many(sorted(rows, key=lambda r: r["created_at"], reverse=True))


RETENTION_COLLS = {"story_entries": "created_at", "tracker_entries": "entry_date", "vitals": "entry_date", "chat_messages": "created_at", "dose_logs": "log_date"}


async def run_retention(user: dict) -> dict:
    days = _priv(user).get("retention_days")
    if not days:
        return {"enabled": False, "deleted": {}}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    db, deleted = get_db(), {}
    pids = [p["_id"] for p in await db.profiles.find({"user_id": user["_id"]}).to_list(100)]
    for coll, field in RETENTION_COLLS.items():
        r = await db[coll].delete_many({"profile_id": {"$in": pids}, field: {"$lt": cutoff}})
        if r.deleted_count:
            deleted[coll] = r.deleted_count
    if deleted:
        for pid in pids:
            await rag.reindex_all(pid)
        await audit(user, "retention_run", str(deleted))
    return {"enabled": True, "days": days, "cutoff": cutoff, "deleted": deleted}


@router.post("/privacy/retention/run")
async def retention_run(user=Depends(current_user)):
    return await run_retention(user)


class DeleteIn(BaseModel):
    confirm: str
    delete_account: bool = False


@router.post("/privacy/delete-all")
async def delete_all(body: DeleteIn, user=Depends(current_user)):
    """Erases every health record of this account (all profiles, vault files, shares, links, alert settings)."""
    if body.confirm != "DELETE":
        raise HTTPException(422, "Type DELETE to confirm")
    db = get_db()
    profs = await db.profiles.find({"user_id": user["_id"]}).to_list(100)
    for p in profs:
        pid = p["_id"]
        for c in PROFILE_COLLECTIONS + ["report_files", "profile_shares", "share_links", "alert_settings"]:
            await db[c].delete_many({"profile_id": pid} if c != "alert_settings" else {"_id": pid})
        await rag.delete_for_profile(pid)
        if body.delete_account and p["relation"] != "self":
            await db.profiles.delete_one({"_id": pid})
    await db.verification_history.delete_many({"report_id": {"$in": [r["_id"] async for r in db.reports.find({"user_id": user["_id"]})]}})
    await db.reports.delete_many({"user_id": user["_id"]})
    await db.profile_shares.delete_many({"grantee_user_id": user["_id"]})
    await audit(user, "delete_all_data", "account deleted" if body.delete_account else "records erased")
    if body.delete_account:
        for c in ("kyc_documents", "otps", "consents"):
            await db[c].delete_many({"user_id": user["_id"]} if c != "otps" else {"_id": user["_id"]})
        await db.profiles.delete_many({"user_id": user["_id"]})
        await db.users.delete_one({"_id": user["_id"]})
    return {"ok": True, "account_deleted": body.delete_account}


# ======================= Audit trail =======================
@router.get("/privacy/audit")
async def audit_trail(limit: int = Query(100, le=500), profile_id: str | None = None, user=Depends(current_user)):
    """Everything done by you, plus everything done by others (caregivers) on profiles you own."""
    db = get_db()
    mine = [p["_id"] for p in await db.profiles.find({"user_id": user["_id"]}).to_list(100)]
    q = {"$or": [{"user_id": user["_id"]}, {"profile_id": {"$in": mine}}]}
    if profile_id:
        if profile_id not in mine:
            raise HTTPException(404, "Profile not found")
        q = {"profile_id": profile_id}
    rows = await db.audit_logs.find(q).to_list(5000)
    rows = sorted(rows, key=lambda r: r["created_at"], reverse=True)[:limit]
    names = {p["_id"]: p["name"] for p in await db.profiles.find({"_id": {"$in": mine}}).to_list(100)}
    out = []
    for r in rows:
        o = clean(r)
        o["by_me"] = r.get("user_id") == user["_id"]
        o["profile_name"] = names.get(r.get("profile_id"))
        out.append(o)
    return out


# ======================= Caregiver sharing =======================
class CaregiverIn(BaseModel):
    email: str
    role: str = "viewer"
    scopes: list[str] = Field(default_factory=lambda: list(ALL_SCOPES))
    note: str = ""


def _check_roles(role, scopes):
    if role not in ("viewer", "editor"):
        raise HTTPException(422, "role must be viewer or editor")
    if not scopes or any(s not in ALL_SCOPES for s in scopes):
        raise HTTPException(422, f"scopes must be a non-empty subset of {ALL_SCOPES}")


@router.post("/sharing/caregivers")
async def invite_caregiver(body: CaregiverIn, user=Depends(current_user), prof=Depends(owner_profile)):
    _check_roles(body.role, body.scopes)
    if not _priv(user)["caregiver_sharing"]:
        raise HTTPException(403, "Caregiver sharing is switched off in Privacy & consent")
    email = body.email.strip().lower()
    if "@" not in email or email == user["email"]:
        raise HTTPException(422, "Enter another person's e-mail address")
    db = get_db()
    if await db.profile_shares.find_one({"profile_id": prof["_id"], "grantee_email": email, "status": {"$in": ["pending", "accepted"]}}):
        raise HTTPException(409, "This person already has an active invitation or access")
    g = await db.users.find_one({"email": email})
    doc = {"_id": new_id(), "profile_id": prof["_id"], "owner_user_id": user["_id"], "owner_name": user["name"], "profile_name": prof["name"],
           "grantee_email": email, "grantee_user_id": g["_id"] if g else None, "role": body.role, "scopes": body.scopes,
           "note": body.note[:200], "status": "pending", "created_at": now_iso()}
    await db.profile_shares.insert_one(doc)
    await audit(user, "caregiver_invite", f"{email} as {body.role}", prof["_id"])
    return clean(doc)


@router.get("/sharing/caregivers")
async def list_caregivers(user=Depends(current_user), prof=Depends(owner_profile)):
    rows = await get_db().profile_shares.find({"profile_id": prof["_id"]}).to_list(200)
    return clean_many(sorted(rows, key=lambda r: r["created_at"], reverse=True))


@router.patch("/sharing/caregivers/{sid}")
async def update_caregiver(sid: str, body: dict, user=Depends(current_user), prof=Depends(owner_profile)):
    role, scopes = body.get("role"), body.get("scopes")
    _check_roles(role or "viewer", scopes or ALL_SCOPES)
    patch = {k: v for k, v in (("role", role), ("scopes", scopes)) if v}
    res = await get_db().profile_shares.update_one({"_id": sid, "profile_id": prof["_id"]}, {"$set": patch})
    if not res.matched_count:
        raise HTTPException(404, "Share not found")
    await audit(user, "caregiver_update", sid + " " + str(patch)[:120], prof["_id"])
    return {"ok": True}


@router.delete("/sharing/caregivers/{sid}")
async def revoke_caregiver(sid: str, user=Depends(current_user), prof=Depends(owner_profile)):
    res = await get_db().profile_shares.update_one({"_id": sid, "profile_id": prof["_id"]}, {"$set": {"status": "revoked", "revoked_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Share not found")
    await audit(user, "caregiver_revoke", sid, prof["_id"])
    return {"ok": True}


@router.get("/sharing/invitations")
async def my_invitations(user=Depends(current_user)):
    rows = await get_db().profile_shares.find({"grantee_email": user["email"], "status": "pending"}).to_list(100)
    return [{k: r[k] for k in ("role", "scopes", "owner_name", "profile_name", "note", "created_at")} | {"id": r["_id"]} for r in rows]


@router.post("/sharing/invitations/{sid}/{action}")
async def answer_invitation(sid: str, action: str, user=Depends(current_user)):
    db = get_db()
    r = await db.profile_shares.find_one({"_id": sid, "grantee_email": user["email"], "status": "pending"})
    if not r:
        raise HTTPException(404, "Invitation not found")
    if action == "accept":
        if not (user.get("kyc") or {}).get("email_verified"):
            raise HTTPException(400, "Verify your e-mail (Verification page) before accepting access to someone's health data")
        await db.profile_shares.update_one({"_id": sid}, {"$set": {"status": "accepted", "grantee_user_id": user["_id"], "accepted_at": now_iso()}})
    elif action == "decline":
        await db.profile_shares.update_one({"_id": sid}, {"$set": {"status": "declined"}})
    else:
        raise HTTPException(404, "Unknown action")
    await audit(user, f"caregiver_{action}", sid, r["profile_id"])
    return {"ok": True}


@router.get("/sharing/shared-with-me")
async def shared_with_me(user=Depends(current_user)):
    rows = await get_db().profile_shares.find({"grantee_user_id": user["_id"], "status": "accepted"}).to_list(100)
    return [{"profile_id": r["profile_id"], "profile_name": r["profile_name"], "owner_name": r["owner_name"], "role": r["role"], "scopes": r["scopes"]} for r in rows]


# ======================= Secure share links =======================
LINK_SECTIONS = ("summary", "vitals", "medicines", "reports", "alerts")


class LinkIn(BaseModel):
    label: str = Field(default="", max_length=60)
    sections: list[str] = Field(default_factory=lambda: ["summary"])
    expires_hours: int = Field(default=24, ge=1, le=720)
    max_views: int | None = Field(default=10, ge=1, le=1000)
    passcode: str | None = Field(default=None, min_length=4, max_length=40)


def _pc(token: str, pc: str) -> str:
    return hmac.new(get_settings().SECRET_KEY.encode(), f"{token}:{pc}".encode(), hashlib.sha256).hexdigest()


@router.post("/sharing/links")
async def create_link(body: LinkIn, user=Depends(current_user), prof=Depends(owner_profile)):
    if not _priv(user)["caregiver_sharing"]:
        raise HTTPException(403, "Sharing is switched off in Privacy & consent")
    if not body.sections or any(s not in LINK_SECTIONS for s in body.sections):
        raise HTTPException(422, f"sections must be a subset of {list(LINK_SECTIONS)}")
    token = secrets.token_urlsafe(24)
    doc = {"_id": new_id(), "token": token, "profile_id": prof["_id"], "user_id": user["_id"], "label": body.label, "sections": body.sections,
           "expires_at": (datetime.now(timezone.utc) + timedelta(hours=body.expires_hours)).isoformat(), "max_views": body.max_views,
           "views": 0, "passcode_hash": _pc(token, body.passcode) if body.passcode else None, "revoked": False, "created_at": now_iso()}
    await get_db().share_links.insert_one(doc)
    await audit(user, "share_link_create", f"{body.label or 'link'} · {','.join(body.sections)} · {body.expires_hours}h", prof["_id"])
    return {**_link_view(doc), "url": f"{get_settings().FRONTEND_URL.rstrip('/')}/s/{token}"}


def _link_view(d: dict) -> dict:
    exp = datetime.fromisoformat(d["expires_at"])
    state = "revoked" if d["revoked"] else "expired" if exp < datetime.now(timezone.utc) else "exhausted" if d["max_views"] and d["views"] >= d["max_views"] else "active"
    return {"id": d["_id"], "label": d["label"], "sections": d["sections"], "expires_at": d["expires_at"], "max_views": d["max_views"],
            "views": d["views"], "has_passcode": bool(d["passcode_hash"]), "state": state, "created_at": d["created_at"]}


@router.get("/sharing/links")
async def list_links(user=Depends(current_user), prof=Depends(owner_profile)):
    rows = await get_db().share_links.find({"profile_id": prof["_id"]}).to_list(200)
    return [{**_link_view(r), "url": f"{get_settings().FRONTEND_URL.rstrip('/')}/s/{r['token']}"} for r in sorted(rows, key=lambda r: r["created_at"], reverse=True)]


@router.delete("/sharing/links/{lid}")
async def revoke_link(lid: str, user=Depends(current_user), prof=Depends(owner_profile)):
    res = await get_db().share_links.update_one({"_id": lid, "profile_id": prof["_id"]}, {"$set": {"revoked": True}})
    if not res.matched_count:
        raise HTTPException(404, "Link not found")
    await audit(user, "share_link_revoke", lid, prof["_id"])
    return {"ok": True}


@router.get("/public/share/{token}")
async def public_share(token: str, x_passcode: str | None = Header(default=None)):
    """Read-only, time-limited view. No token enumeration: every failure is the same 404/403 message class."""
    db = get_db()
    d = await db.share_links.find_one({"token": token})
    if not d:
        raise HTTPException(404, "This link is not valid")
    v = _link_view(d)
    if v["state"] != "active":
        raise HTTPException(410, f"This link is {v['state']}")
    if d["passcode_hash"]:
        if not x_passcode:
            raise HTTPException(401, "passcode_required")
        if not hmac.compare_digest(d["passcode_hash"], _pc(token, x_passcode)):
            raise HTTPException(403, "Incorrect passcode")
    await db.share_links.update_one({"_id": d["_id"]}, {"$inc": {"views": 1}})
    pid = d["profile_id"]
    prof = await db.profiles.find_one({"_id": pid}) or {}
    await db.audit_logs.insert_one({"_id": new_id(), "user_id": None, "email": "share-link viewer", "action": "share_link_view",
                                    "detail": (d["label"] or "link")[:100], "profile_id": pid, "created_at": now_iso()})
    out = {"profile_name": prof.get("name"), "label": d["label"], "expires_at": d["expires_at"], "sections": d["sections"],
           "notice": "Read-only snapshot shared by the patient. It is self-recorded information, not a diagnosis."}
    if "summary" in d["sections"]:
        tr = await db.tracker_entries.find({"profile_id": pid}).to_list(200)
        tr = sorted(tr, key=lambda r: r["entry_date"])[-30:]
        avg = lambda k: round(sum(r[k] for r in tr if r.get(k) is not None) / max(1, sum(1 for r in tr if r.get(k) is not None)), 1) if any(r.get(k) is not None for r in tr) else None
        out["summary"] = {"days_logged": len(tr), "avg_sleep_hours": avg("sleep_hours"), "avg_stress": avg("stress_level"), "avg_pain": avg("pain_level"),
                          "risk_flags": [{"title": f["title"], "detail": f["detail"]} for f in await hr.compute_risk_flags(pid)][:6]}
    if "vitals" in d["sections"]:
        vs = sorted(await db.vitals.find({"profile_id": pid}).to_list(500), key=lambda r: r["entry_date"])[-10:]
        out["vitals"] = [{k: v for k, v in r.items() if k in ("entry_date", "weight_kg", "height_cm", "systolic", "diastolic", "heart_rate", "fasting_sugar", "postmeal_sugar", "spo2", "temperature_c")} for r in vs]
    if "medicines" in d["sections"]:
        out["medicines"] = [{k: m.get(k) for k in ("name", "dosage", "frequency", "slots", "start_date")} for m in await db.medicines.find({"profile_id": pid, "active": True}).to_list(100)]
    if "reports" in d["sections"]:
        rs = sorted(await db.reports.find({"profile_id": pid}).to_list(200), key=lambda r: r["report_date"], reverse=True)[:10]
        out["reports"] = [{"title": r["title"], "report_date": r["report_date"], "verification": (r.get("verification") or {}).get("status", "Unverified"),
                           "fields": [{k: f.get(k) for k in ("test", "value", "unit", "reference_range", "out_of_range")} for f in r["fields"]][:25]} for r in rs]
    if "alerts" in d["sections"]:
        out["alerts"] = [{k: a[k] for k in ("title", "detail", "urgency", "date")} for a in await al.evaluate(pid)][:10]
    return out
