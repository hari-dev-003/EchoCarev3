"""Verified Report endpoints + image observation v2 helpers live in ai.py."""
import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import audit, current_profile, current_user
from app.core.util import clean_many
from app.services import verified_report as vr

router = APIRouter(prefix="/api/verified-report", tags=["verified-report"])


async def _owner(prof, user):
    return await get_db().users.find_one({"_id": prof.get("user_id")}) or user


@router.get("")
async def list_reports(prof=Depends(current_profile)):
    rows = await get_db().verified_reports.find({"profile_id": prof["_id"]}).to_list(200)
    return [{"id": r["_id"], "generated_at": r["generated_at"], "status": r["status"], "content_sha256": r["content_sha256"], "summary_label": r["summary"]["label"]}
            for r in sorted(rows, key=lambda r: r["generated_at"], reverse=True)]


@router.post("")
async def generate(body: dict | None = None, user=Depends(current_user), prof=Depends(current_profile)):
    lang = (body or {}).get("lang") or user.get("language") or "en"
    rec = await vr.create(prof, await _owner(prof, user), user, lang if lang in ("en", "ta", "hi") else "en")
    await audit(user, "verified_report_generate", rec["_id"], prof["_id"])
    return {"id": rec["_id"], "generated_at": rec["generated_at"], "status": rec["status"], "content_sha256": rec["content_sha256"], "summary": rec["summary"], "data": rec["data"],
            "verify_url": f"{get_settings().FRONTEND_URL.rstrip('/')}/verify/{rec['_id']}", "profile_name": prof["name"]}


async def _get(rid, prof):
    r = await get_db().verified_reports.find_one({"_id": rid, "profile_id": prof["_id"]})
    if not r:
        raise HTTPException(404, "Verified report not found")
    return r


@router.get("/{rid}")
async def get_one(rid: str, prof=Depends(current_profile)):
    r = await _get(rid, prof)
    return {"id": r["_id"], "generated_at": r["generated_at"], "status": r["status"], "content_sha256": r["content_sha256"], "summary": r["summary"], "data": r["data"],
            "verify_url": f"{get_settings().FRONTEND_URL.rstrip('/')}/verify/{rid}", "profile_name": prof["name"]}


@router.get("/{rid}/pdf")
async def pdf(rid: str, user=Depends(current_user), prof=Depends(current_profile)):
    r = await _get(rid, prof)
    await audit(user, "verified_report_pdf", rid, prof["_id"])
    return Response(vr.build_pdf(r, prof["name"]), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="EchoCare_Verified_Report_{rid[:8]}.pdf"'})


@router.get("/{rid}/qr")
async def qr(rid: str, prof=Depends(current_profile)):
    await _get(rid, prof)
    buf = io.BytesIO()
    qrcode.make(f"{get_settings().FRONTEND_URL.rstrip('/')}/verify/{rid}").save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")
