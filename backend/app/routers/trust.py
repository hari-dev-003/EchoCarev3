"""Trust & verification: KYC (e-mail OTP + admin identity review), document vault, report verification, reviewers,
trusted-issuer registry, public QR verification (no personal health data)."""
import hashlib
import hmac
import io
import secrets
from datetime import datetime, timedelta, timezone

import qrcode
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import audit, current_profile, current_user, is_admin, require_admin
from app.core.util import clean, clean_many, new_id, now_iso
from app.services import mailer, vault
from app.services.vault import ext_ct

router = APIRouter(prefix="/api", tags=["trust"])


# ======================= KYC =======================
def _otp_hash(uid: str, code: str) -> str:
    return hmac.new(get_settings().SECRET_KEY.encode(), f"{uid}:{code}".encode(), hashlib.sha256).hexdigest()


def kyc_view(u: dict) -> dict:
    k = u.get("kyc") or {}
    return {"status": k.get("status", "unverified"), "email": u["email"], "email_verified": bool(k.get("email_verified")),
            "email_verified_at": k.get("email_verified_at"), "identity": {
                "submitted_at": k.get("submitted_at"), "id_type": k.get("id_type"), "id_last4": k.get("id_last4"),
                "legal_name": k.get("legal_name"), "reviewed_at": k.get("reviewed_at"), "review_note": k.get("review_note")},
            "smtp_configured": mailer.smtp_configured(),
            "notes": ["An e-mail OTP only proves you can read this mailbox; it does not prove who you are.",
                      "Identity verification is a manual review by an administrator of what you submit. EchoCare never stores a full ID number."]}


@router.get("/kyc/status")
async def kyc_status(user=Depends(current_user)):
    return kyc_view(user)


@router.post("/kyc/otp/send")
async def otp_send(user=Depends(current_user)):
    db = get_db()
    row = await db.otps.find_one({"_id": user["_id"]})
    if row and (datetime.now(timezone.utc) - datetime.fromisoformat(row["sent_at"])).total_seconds() < 30:
        raise HTTPException(429, "Please wait 30 seconds before asking for another code")
    code = f"{secrets.randbelow(1_000_000):06d}"
    s = get_settings()
    exp = (datetime.now(timezone.utc) + timedelta(minutes=s.OTP_MINUTES)).isoformat()
    await db.otps.replace_one({"_id": user["_id"]}, {"_id": user["_id"], "hash": _otp_hash(user["_id"], code), "expires_at": exp,
                                                      "attempts": 0, "sent_at": now_iso()}, upsert=True)
    sent, info = await mailer.send_email(user["email"], "Your EchoCare verification code",
                                         f"Your EchoCare code is {code}. It expires in {s.OTP_MINUTES} minutes. If you did not ask for it, ignore this message.")
    await audit(user, "kyc_otp_sent", "e-mail" if sent else "dev-mode")
    out = {"sent": sent, "expires_in_minutes": s.OTP_MINUTES}
    if not sent:
        if s.ENV == "production":
            raise HTTPException(503, f"The code could not be e-mailed. {info}")
        out.update({"dev_mode": True, "dev_otp": code, "message": f"{info} Development mode: the code is shown here instead. Never use this in production."})
    return out


class OtpIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


@router.post("/kyc/otp/verify")
async def otp_verify(body: OtpIn, user=Depends(current_user)):
    db = get_db()
    row = await db.otps.find_one({"_id": user["_id"]})
    if not row:
        raise HTTPException(400, "Request a code first")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(400, "That code has expired. Request a new one")
    if row["attempts"] >= 5:
        raise HTTPException(429, "Too many wrong attempts. Request a new code")
    if not hmac.compare_digest(row["hash"], _otp_hash(user["_id"], body.code)):
        await db.otps.update_one({"_id": user["_id"]}, {"$inc": {"attempts": 1}})
        raise HTTPException(400, "Incorrect code")
    k = dict(user.get("kyc") or {})
    k.update({"email_verified": True, "email_verified_at": now_iso()})
    if k.get("status", "unverified") == "unverified":
        k["status"] = "contact_verified"
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"kyc": k}})
    await db.otps.delete_one({"_id": user["_id"]})
    await audit(user, "kyc_email_verified")
    return kyc_view(await db.users.find_one({"_id": user["_id"]}))


@router.post("/kyc/identity")
async def identity_submit(legal_name: str = Form(...), id_type: str = Form(...), id_last4: str = Form(..., min_length=4, max_length=4),
                          file: UploadFile | None = File(None), user=Depends(current_user)):
    k = dict(user.get("kyc") or {})
    if not k.get("email_verified"):
        raise HTTPException(400, "Verify your e-mail first")
    if id_type not in ("aadhaar", "passport", "driving_licence", "voter_id", "other"):
        raise HTTPException(422, "Unsupported ID type")
    doc_id = None
    if file is not None and file.filename:
        data = await file.read()
        if len(data) > get_settings().MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, "File too large")
        doc_id = new_id()
        await get_db().kyc_documents.insert_one({"_id": doc_id, "user_id": user["_id"], "filename": file.filename,
                                                 "content_type": ext_ct(file.filename, file.content_type), "data": data,
                                                 "sha256": vault.sha256(data), "created_at": now_iso()})
    k.update({"status": "identity_pending", "legal_name": legal_name.strip()[:80], "id_type": id_type, "id_last4": id_last4[-4:],
              "submitted_at": now_iso(), "document_id": doc_id, "review_note": None})
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": {"kyc": k}})
    await audit(user, "kyc_identity_submitted", id_type)
    return kyc_view(await get_db().users.find_one({"_id": user["_id"]}))


@router.get("/kyc/admin/pending")
async def kyc_pending(admin=Depends(require_admin)):
    rows = await get_db().users.find({"kyc.status": "identity_pending"}).to_list(200)
    return [{"user_id": u["_id"], "name": u["name"], "email": u["email"], **{k: u["kyc"].get(k) for k in ("legal_name", "id_type", "id_last4", "submitted_at", "document_id")}} for u in rows]


@router.get("/kyc/admin/{uid}/document")
async def kyc_document(uid: str, admin=Depends(require_admin)):
    u = await get_db().users.find_one({"_id": uid})
    d = await get_db().kyc_documents.find_one({"_id": ((u or {}).get("kyc") or {}).get("document_id")})
    if not d:
        raise HTTPException(404, "No document submitted")
    await audit(admin, "kyc_document_viewed", u["email"])
    return Response(d["data"], media_type=d["content_type"], headers={"Content-Disposition": f'inline; filename="{d["filename"]}"'})


class DecideIn(BaseModel):
    decision: str
    note: str = ""


@router.post("/kyc/admin/{uid}/decide")
async def kyc_decide(uid: str, body: DecideIn, admin=Depends(require_admin)):
    u = await get_db().users.find_one({"_id": uid})
    if not u or (u.get("kyc") or {}).get("status") != "identity_pending":
        raise HTTPException(404, "No pending identity review for this user")
    if body.decision not in ("approve", "reject"):
        raise HTTPException(422, "decision must be approve or reject")
    k = dict(u["kyc"])
    k.update({"status": "identity_verified" if body.decision == "approve" else "identity_rejected", "reviewed_at": now_iso(),
              "reviewed_by": admin["email"], "review_note": body.note[:300]})
    await get_db().users.update_one({"_id": uid}, {"$set": {"kyc": k}})
    await audit(admin, f"kyc_{body.decision}", u["email"])
    return {"ok": True, "status": k["status"]}


# ======================= Vault =======================
def _file_meta(f: dict) -> dict:
    return {k: f[k] for k in ("version", "filename", "content_type", "size", "sha256", "uploaded_at")}


async def _report(rid: str, prof: dict) -> dict:
    r = await get_db().reports.find_one({"_id": rid, "profile_id": prof["_id"]})
    if not r:
        raise HTTPException(404, "Report not found")
    return r


@router.get("/vault")
async def vault_list(prof=Depends(current_profile)):
    db = get_db()
    out = []
    for r in sorted(await db.reports.find({"profile_id": prof["_id"]}).to_list(500), key=lambda r: r["report_date"], reverse=True):
        files = await db.report_files.find({"report_id": r["_id"]}).to_list(100)
        v = r.get("verification") or {}
        out.append({"id": r["_id"], "title": r["title"], "report_date": r["report_date"], "filename": r.get("filename"),
                    "method": r.get("method"), "provenance": r.get("provenance", "extracted"), "versions": len(files),
                    "current_version": r.get("current_version", 1), "sha256": r.get("file_sha256"), "size": r.get("file_size"),
                    "status": v.get("status", "Unverified"), "reason": v.get("reason"), "score": v.get("score"),
                    "reviewed": bool(v.get("reviewer")), "review_requested": bool(r.get("review_requested")),
                    "extracted": r.get("extracted") or {}, "checks": v.get("checks", []), "checked_at": v.get("checked_at")})
    counts: dict = {}
    for o in out:
        counts[o["status"]] = counts.get(o["status"], 0) + 1
    return {"items": out, "counts": counts, "storage_bytes": sum(o["size"] or 0 for o in out)}


@router.get("/vault/{rid}/file")
async def vault_file(rid: str, version: int | None = None, user=Depends(current_user), prof=Depends(current_profile)):
    await _report(rid, prof)
    f = await vault.latest_file(rid, version)
    if not f:
        raise HTTPException(404, "No file is stored for this report")
    await audit(user, "vault_file_view", f"{rid} v{f['version']}", prof["_id"])
    return Response(f["data"], media_type=f["content_type"], headers={"Content-Disposition": f'inline; filename="{f["filename"] or "report"}"'})


@router.get("/vault/{rid}/versions")
async def vault_versions(rid: str, prof=Depends(current_profile)):
    await _report(rid, prof)
    rows = await get_db().report_files.find({"report_id": rid}).to_list(100)
    return sorted((_file_meta(r) for r in rows), key=lambda r: r["version"], reverse=True)


@router.post("/vault/{rid}/versions")
async def vault_new_version(rid: str, file: UploadFile = File(...), user=Depends(current_user), prof=Depends(current_profile)):
    r = await _report(rid, prof)
    data = await file.read()
    if len(data) > get_settings().MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, "File too large")
    if (file.filename or "").lower().rsplit(".", 1)[-1] not in ("pdf", "png", "jpg", "jpeg", "webp"):
        raise HTTPException(415, "Upload a PDF or an image")
    v = r.get("current_version", 1) + 1 if await vault.latest_file(rid) else 1
    rr = dict(r, filename=file.filename)
    await vault.store_file(rr, data, ext_ct(file.filename, file.content_type), user, v)
    await get_db().reports.update_one({"_id": rid}, {"$set": {"filename": file.filename, "review_requested": False}})
    await vault.history(rid, "new_version", "Unverified", f"Version {v} uploaded ({file.filename})", user)
    ver = await vault.auto_verify(rid, user, prof)
    await audit(user, "vault_new_version", f"{rid} v{v}", prof["_id"])
    return {"version": v, "verification": {"status": ver["status"], "reason": ver["reason"]}}


@router.post("/vault/{rid}/verify")
async def vault_verify(rid: str, user=Depends(current_user), prof=Depends(current_profile)):
    await _report(rid, prof)
    ver = await vault.auto_verify(rid, user, prof)
    await audit(user, "report_verify", f"{rid} -> {ver['status']}", prof["_id"])
    return ver


@router.get("/vault/{rid}/integrity")
async def vault_integrity(rid: str, prof=Depends(current_profile)):
    r = await _report(rid, prof)
    f = await vault.latest_file(rid)
    if not f:
        return {"has_file": False, "intact": None}
    now = vault.sha256(f["data"])
    return {"has_file": True, "intact": now == f["sha256"], "stored_sha256": f["sha256"], "recomputed_sha256": now, "version": f["version"]}


@router.get("/vault/{rid}/history")
async def vault_history(rid: str, prof=Depends(current_profile)):
    await _report(rid, prof)
    rows = await get_db().verification_history.find({"report_id": rid}).to_list(300)
    return clean_many(sorted(rows, key=lambda r: r["created_at"], reverse=True))


@router.post("/vault/{rid}/request-review")
async def vault_request_review(rid: str, user=Depends(current_user), prof=Depends(current_profile)):
    r = await _report(rid, prof)
    await get_db().reports.update_one({"_id": rid}, {"$set": {"review_requested": True, "review_requested_at": now_iso()}})
    await vault.history(rid, "review_requested", (r.get("verification") or {}).get("status", "Unverified"), "Owner asked for a reviewer to confirm this document", user)
    await audit(user, "report_review_requested", rid, prof["_id"])
    return {"ok": True}


@router.get("/vault/{rid}/qr")
async def vault_qr(rid: str, prof=Depends(current_profile)):
    await _report(rid, prof)
    img = qrcode.make(f"{get_settings().FRONTEND_URL.rstrip('/')}/verify/{rid}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


# ======================= Reviewers & trusted issuers =======================
def is_reviewer(u: dict) -> bool:
    return is_admin(u) or bool(u.get("is_reviewer"))


async def require_reviewer(user: dict = Depends(current_user)) -> dict:
    if not is_reviewer(user):
        raise HTTPException(403, "Reviewer access required")
    return user


@router.get("/review/queue")
async def review_queue(reviewer=Depends(require_reviewer)):
    db = get_db()
    rows = await db.reports.find({"$or": [{"review_requested": True}, {"verification.status": "Manual Review"}]}).to_list(300)
    out = []
    for r in rows:
        v = r.get("verification") or {}
        if v.get("reviewer") and v.get("file_version") == r.get("current_version", 1):
            continue
        prof = await db.profiles.find_one({"_id": r["profile_id"]}) or {}
        out.append({"id": r["_id"], "title": r["title"], "report_date": r["report_date"], "profile_name": prof.get("name"),
                    "status": v.get("status", "Unverified"), "reason": v.get("reason"), "checks": v.get("checks", []),
                    "extracted": r.get("extracted") or {}, "has_file": bool(r.get("file_sha256")), "provenance": r.get("provenance"),
                    "requested": bool(r.get("review_requested"))})
    return out


@router.get("/review/{rid}/file")
async def review_file(rid: str, reviewer=Depends(require_reviewer)):
    f = await vault.latest_file(rid)
    if not f:
        raise HTTPException(404, "No file stored")
    await audit(reviewer, "review_file_view", rid)
    return Response(f["data"], media_type=f["content_type"], headers={"Content-Disposition": f'inline; filename="{f["filename"] or "report"}"'})


class ReviewIn(BaseModel):
    decision: str  # confirm | reject
    note: str = ""


@router.post("/review/{rid}/decide")
async def review_decide(rid: str, body: ReviewIn, reviewer=Depends(require_reviewer)):
    db = get_db()
    r = await db.reports.find_one({"_id": rid})
    if not r:
        raise HTTPException(404, "Report not found")
    if body.decision not in ("confirm", "reject"):
        raise HTTPException(422, "decision must be confirm or reject")
    if r.get("user_id") == reviewer["_id"]:
        raise HTTPException(403, "You cannot review your own report")
    v = dict(r.get("verification") or {})
    v.update({"status": "Verified" if body.decision == "confirm" else "Failed", "file_version": r.get("current_version", 1),
              "reason": ("Confirmed by a human reviewer: " if body.decision == "confirm" else "Rejected by a human reviewer: ") + (body.note or "no note"),
              "reviewer": {"email": reviewer["email"], "name": reviewer["name"], "at": now_iso(), "note": body.note[:300], "decision": body.decision}})
    await db.reports.update_one({"_id": rid}, {"$set": {"verification": v, "review_requested": False}})
    await vault.history(rid, "reviewer_" + body.decision, v["status"], v["reason"], reviewer, v.get("checks"))
    await audit(reviewer, f"report_review_{body.decision}", rid, r["profile_id"])
    return {"ok": True, "status": v["status"]}


@router.put("/trust/reviewers/{uid}")
async def set_reviewer(uid: str, body: dict, admin=Depends(require_admin)):
    res = await get_db().users.update_one({"_id": uid}, {"$set": {"is_reviewer": bool(body.get("is_reviewer"))}})
    if not res.matched_count:
        raise HTTPException(404, "User not found")
    await audit(admin, "reviewer_set", f"{uid}={bool(body.get('is_reviewer'))}")
    return {"ok": True}


class IssuerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    aliases: list[str] = []
    kind: str = "laboratory"
    website: str | None = None
    active: bool = True


@router.get("/trust/issuers")
async def issuers_list(user=Depends(current_user)):
    return clean_many(await get_db().trusted_issuers.find({}).to_list(500))


@router.post("/trust/issuers")
async def issuers_add(body: IssuerIn, admin=Depends(require_admin)):
    doc = {"_id": new_id(), **body.model_dump(), "added_by": admin["email"], "created_at": now_iso()}
    await get_db().trusted_issuers.insert_one(doc)
    await audit(admin, "issuer_add", body.name)
    return clean(doc)


@router.patch("/trust/issuers/{iid}")
async def issuers_update(iid: str, body: dict, admin=Depends(require_admin)):
    allowed = {k: v for k, v in body.items() if k in ("name", "aliases", "kind", "website", "active")}
    res = await get_db().trusted_issuers.update_one({"_id": iid}, {"$set": allowed})
    if not res.matched_count:
        raise HTTPException(404, "Issuer not found")
    return {"ok": True}


@router.delete("/trust/issuers/{iid}")
async def issuers_delete(iid: str, admin=Depends(require_admin)):
    await get_db().trusted_issuers.delete_one({"_id": iid})
    await audit(admin, "issuer_delete", iid)
    return {"ok": True}


# ======================= Public verification (no PHI) =======================
@router.get("/public/verify/{rid}")
async def public_verify(rid: str, h: str | None = None):
    """Shows ONLY: short report ID, verification status, issue date, integrity hash. No names, values or documents."""
    vrp = await get_db().verified_reports.find_one({"_id": rid})
    if vrp:
        out = {"report_id": rid[:8].upper(), "kind": "Verified Report", "status": vrp["status"], "issue_date": vrp["generated_at"][:10],
               "integrity_hash": vrp["content_sha256"], "human_reviewed": any(r["status"] == "Verified" for r in vrp["data"]["reports"]),
               "notice": "This page confirms a Verified Report was generated by EchoCare on this date. It does not display any patient information."}
        if h:
            out["hash_matches"] = h.lower() == vrp["content_sha256"]
        return out
    r = await get_db().reports.find_one({"_id": rid})
    if not r:
        raise HTTPException(404, "No report with this ID")
    v = r.get("verification") or {}
    out = {"report_id": rid[:8].upper(), "status": v.get("status", "Unverified"), "issue_date": r.get("report_date"),
           "integrity_hash": r.get("file_sha256"), "human_reviewed": bool(v.get("reviewer")),
           "checked_at": v.get("checked_at"),
           "notice": "This page confirms the verification status EchoCare holds for this document. It does not display any patient information."}
    if h:
        out["hash_matches"] = bool(r.get("file_sha256")) and h.lower() == r["file_sha256"]
    return out
