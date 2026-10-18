import io

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from app.core import db as dbmod
from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import audit, current_profile, current_user, is_admin, require_admin
from app.core.util import clean_many, new_id, now_iso
from app.services import department, doctors as dr, llm, rag, vector
from app.services.demo import seed_profile

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/health")
async def health():
    ok, backend = await dbmod.ping()
    return {"status": "ok" if ok else "degraded", "database": backend, "version": get_settings().APP_VERSION}


@router.post("/demo/seed")
async def demo_seed(user=Depends(current_user), prof=Depends(current_profile)):
    res = await seed_profile(user["_id"], prof["_id"], prof["name"])
    await audit(user, "demo_seed", "", prof["_id"])
    return res


@router.get("/admin/overview")
async def overview(admin=Depends(require_admin)):
    db = get_db()
    counts = {c: await db[c].count_documents({}) for c in ["users", "profiles", "story_entries", "tracker_entries", "vitals", "reports", "medicines",
                                                          "appointments", "evidence_chunks", "insights", "chat_messages", "doctors", "audit_logs"]}
    logs = await db.audit_logs.find({}).to_list(2000)
    from collections import Counter
    actions = Counter(l["action"] for l in logs)
    users = await db.users.find({}).to_list(10000)
    growth = Counter(u["created_at"][:10] for u in users)
    return {"counts": counts, "actions": [{"action": k, "count": v} for k, v in actions.most_common(12)],
            "signups": [{"date": k, "count": v} for k, v in sorted(growth.items())]}


@router.get("/admin/system")
async def system(admin=Depends(require_admin)):
    ok, backend = await dbmod.ping()
    s = get_settings()
    return {"version": s.APP_VERSION, "env": s.ENV, "database": {"ok": ok, "backend": backend, "name": s.MONGODB_DB_NAME},
            "vector": await vector.stats(), "gemini": llm.gemini_configured(), "tavily": llm.tavily_configured(),
            "classifier_trained": department.model_available(), "cors": s.cors_origins}


@router.get("/admin/users")
async def users(admin=Depends(require_admin)):
    out = []
    for u in await get_db().users.find({}).to_list(2000):
        out.append({"id": u["_id"], "name": u["name"], "email": u["email"], "is_admin": is_admin(u), "disabled": bool(u.get("disabled")), "created_at": u["created_at"]})
    return sorted(out, key=lambda x: x["created_at"])


@router.patch("/admin/users/{uid}")
async def patch_user(uid: str, body: dict, admin=Depends(require_admin)):
    if uid == admin["_id"]:
        raise HTTPException(400, "You cannot modify your own admin account here")
    allowed = {k: bool(v) for k, v in body.items() if k in ("disabled", "is_admin")}
    await get_db().users.update_one({"_id": uid}, {"$set": allowed})
    await audit(admin, "admin_user_update", f"{uid} {allowed}")
    return {"ok": True}


@router.get("/admin/audit")
async def audit_logs(limit: int = 200, admin=Depends(require_admin)):
    rows = sorted(await get_db().audit_logs.find({}).to_list(5000), key=lambda r: r["created_at"], reverse=True)[:limit]
    return clean_many(rows)


@router.post("/admin/reindex")
async def reindex(admin=Depends(require_admin)):
    res = await rag.reindex_all()
    await audit(admin, "vector_reindex", str(res))
    return res


@router.get("/admin/doctors/template")
async def template(admin=Depends(require_admin)):
    return Response(dr.template_csv(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=doctors_template.csv"})


@router.post("/admin/doctors/import")
async def import_doctors(file: UploadFile = File(...), replace: bool = True, admin=Depends(require_admin)):
    data = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(data)) if file.filename.lower().endswith(("xlsx", "xls")) else pd.read_csv(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(400, f"Could not read file: {e}")
    rows, errors, warnings = dr.parse_upload(df)
    if rows:
        db = get_db()
        if replace:
            await db.doctors.delete_many({})
        await db.doctors.insert_many([{"_id": new_id(), **r} for r in rows])
    await audit(admin, "doctors_import", f"{len(rows)} rows")
    return {"imported": len(rows), "errors": errors[:50], "warnings": warnings[:50]}


@router.delete("/admin/doctors")
async def clear_doctors(admin=Depends(require_admin)):
    await get_db().doctors.delete_many({})
    return {"ok": True}
