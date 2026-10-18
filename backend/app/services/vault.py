"""Document vault: file bytes (MongoDB), sha256 integrity hash, versions, verification history."""
import hashlib

from app.core.db import get_db
from app.core.util import new_id, now_iso
from app.services import verification

CT = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}


def ext_ct(filename: str, declared: str | None = None) -> str:
    return CT.get((filename or "").lower().rsplit(".", 1)[-1], declared or "application/octet-stream")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def store_file(report: dict, data: bytes, content_type: str, user: dict, version: int) -> dict:
    row = {"_id": new_id(), "report_id": report["_id"], "profile_id": report["profile_id"], "version": version,
           "filename": report.get("filename"), "content_type": content_type, "size": len(data), "sha256": sha256(data),
           "data": data, "uploaded_by": user["_id"], "uploaded_at": now_iso()}
    await get_db().report_files.insert_one(row)
    await get_db().reports.update_one({"_id": report["_id"]}, {"$set": {"file_sha256": row["sha256"], "file_size": row["size"], "current_version": version}})
    return row


async def latest_file(report_id: str, version: int | None = None) -> dict | None:
    rows = await get_db().report_files.find({"report_id": report_id}).to_list(200)
    if version:
        rows = [r for r in rows if r["version"] == version]
    return max(rows, key=lambda r: r["version"]) if rows else None


async def history(report_id: str, event: str, status: str, detail: str, actor: dict | None, checks: list | None = None) -> None:
    await get_db().verification_history.insert_one({
        "_id": new_id(), "report_id": report_id, "event": event, "status": status, "detail": detail[:400],
        "actor": (actor or {}).get("email") if actor else "system", "checks": checks or [], "created_at": now_iso()})


async def auto_verify(report_id: str, user: dict, prof: dict) -> dict:
    """Runs the automated checks. Never overwrites a human reviewer's decision for the same file version."""
    db = get_db()
    rep = await db.reports.find_one({"_id": report_id})
    owner = await db.users.find_one({"_id": rep["user_id"]}) or user
    f = await latest_file(report_id)
    issuers = await db.trusted_issuers.find({"active": {"$ne": False}}).to_list(500)
    res = verification.run_checks(rep, prof, owner.get("kyc") or {}, issuers, f["data"] if f else None)
    cur = rep.get("verification") or {}
    reviewed = cur.get("reviewer") and cur.get("file_version") == rep.get("current_version", 1)
    ver = {**res, "file_version": rep.get("current_version", 1), "checked_at": now_iso()}
    if reviewed:
        ver.update({"status": cur["status"], "reviewer": cur["reviewer"], "reason": cur.get("reason", ver["reason"])})
    await db.reports.update_one({"_id": report_id}, {"$set": {"verification": ver}})
    await history(report_id, "auto_check", ver["status"], res["reason"], None, res["checks"])
    return ver
