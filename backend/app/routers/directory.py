"""Doctor directory & maps, appointments helpers, emergency card (public QR), consultation PDF, learning hub."""
import io
import secrets

import pandas as pd
import qrcode
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import current_profile, current_user
from app.core.util import clean, new_id, now_iso
from app.data import learn_content as lc
from app.data.specialties import ALL_SPECIALTIES, SPECIALTIES
from app.services import doctors as dr, report_pdf

router = APIRouter(prefix="/api", tags=["directory"])


# ---------------- Doctors ----------------
@router.get("/doctors/meta")
async def doctors_meta():
    directory, source = await dr.get_directory()
    centers: dict[str, list] = {}
    for d in directory:
        centers.setdefault(d["district"], []).append((d["lat"], d["lon"]))
    districts = {k: [sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)] for k, v in sorted(centers.items())}
    present = {d["specialty"] for d in directory}
    specs = [s for s in ALL_SPECIALTIES if s in present] + sorted(present - set(ALL_SPECIALTIES))
    return {"source": source, "districts": districts, "specialties": specs, "total": len(directory),
            "disclaimer": "Demo directory: representative names and approximate coordinates. Import a real directory in Admin." if source == "demo" else "Imported directory."}


@router.get("/doctors")
async def find_doctors(district: str | None = None, specialty: str | None = None, lat: float | None = None, lon: float | None = None,
                       min_rating: float = 0, q: str | None = None, limit: int = Query(200, le=1000)):
    directory, source = await dr.get_directory()
    res = directory
    if district and district != "All":
        res = [d for d in res if d["district"] == district]
    if specialty and specialty != "All":
        res = [d for d in res if d["specialty"] == specialty]
    if min_rating:
        res = [d for d in res if d["rating"] >= min_rating]
    if q:
        ql = q.lower()
        res = [d for d in res if ql in d["name"].lower() or ql in d["hospital"].lower()]
    ranked = dr.rank_doctors(res, lat, lon)[:limit]
    return {"source": source, "count": len(ranked), "items": ranked}


@router.get("/doctors/stats")
async def doctors_stats():
    directory, source = await dr.get_directory()
    by_sp, by_di = {}, {}
    for d in directory:
        by_sp.setdefault(d["specialty"], []).append(d)
        by_di[d["district"]] = by_di.get(d["district"], 0) + 1
    return {"source": source, "by_specialty": [{"specialty": k, "count": len(v), "avg_rating": round(sum(x["rating"] for x in v) / len(v), 2),
                                                 "avg_fee": round(sum(x["consultation_fee_inr"] for x in v) / len(v))} for k, v in by_sp.items()],
            "by_district": [{"district": k, "count": v} for k, v in sorted(by_di.items(), key=lambda x: -x[1])]}


# ---------------- Emergency card ----------------
async def _card(user, prof):
    db = get_db()
    c = await db.emergency_cards.find_one({"profile_id": prof["_id"]})
    if not c:
        c = {"_id": new_id(), "profile_id": prof["_id"], "user_id": user["_id"], "token": secrets.token_urlsafe(12), "blood_group": "",
             "allergies": "", "conditions": "", "medicines": "", "contact_name": "", "contact_phone": "", "doctor": "", "notes": "",
             "public_enabled": True, "updated_at": now_iso()}
        await db.emergency_cards.insert_one(c)
    return c


@router.get("/emergency/card")
async def get_card(user=Depends(current_user), prof=Depends(current_profile)):
    c = clean(await _card(user, prof))
    c["profile_name"] = prof["name"]
    c["public_url"] = f"{get_settings().FRONTEND_URL.rstrip('/')}/e/{c['token']}"
    return c


@router.put("/emergency/card")
async def put_card(body: dict, user=Depends(current_user), prof=Depends(current_profile)):
    c = await _card(user, prof)
    allowed = {k: v for k, v in body.items() if k in ("blood_group", "allergies", "conditions", "medicines", "contact_name", "contact_phone", "doctor", "notes", "public_enabled")}
    allowed["updated_at"] = now_iso()
    await get_db().emergency_cards.update_one({"_id": c["_id"]}, {"$set": allowed})
    return {"ok": True}


@router.post("/emergency/rotate")
async def rotate_card(user=Depends(current_user), prof=Depends(current_profile)):
    c = await _card(user, prof)
    await get_db().emergency_cards.update_one({"_id": c["_id"]}, {"$set": {"token": secrets.token_urlsafe(12)}})
    return {"ok": True}


@router.get("/emergency/qr")
async def card_qr(user=Depends(current_user), prof=Depends(current_profile)):
    c = await _card(user, prof)
    img = qrcode.make(f"{get_settings().FRONTEND_URL.rstrip('/')}/e/{c['token']}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


@router.get("/public/emergency/{token}")
async def public_card(token: str):
    c = await get_db().emergency_cards.find_one({"token": token})
    if not c or not c.get("public_enabled"):
        raise HTTPException(404, "This emergency card is not available")
    prof = await get_db().profiles.find_one({"_id": c["profile_id"]})
    return {"name": prof["name"] if prof else "", **{k: c.get(k, "") for k in ("blood_group", "allergies", "conditions", "medicines", "contact_name", "contact_phone", "doctor", "notes")},
            "updated_at": c.get("updated_at")}


# ---------------- Consultation PDF ----------------
class ReportOpts(BaseModel):
    include: dict[str, bool] | None = None


@router.get("/consult/sections")
async def consult_sections():
    return report_pdf.SECTIONS


@router.post("/consult/pdf")
async def consult_pdf(body: ReportOpts, prof=Depends(current_profile)):
    data = await report_pdf.build_pdf(prof, body.include)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="EchoCare_Consultation_Summary.pdf"'})


# ---------------- Learning hub ----------------
@router.get("/learn")
async def learn():
    return {"flashcards": lc.FLASHCARDS, "decks": lc.SLIDE_DECKS, "wellness": lc.WELLNESS_PROGRAMS,
            "quiz": [{k: v for k, v in q.items() if k not in ("answer", "why")} for q in lc.QUIZ], "specialties": SPECIALTIES}


class QuizSubmit(BaseModel):
    answers: dict[str, int]


@router.post("/learn/quiz")
async def grade_quiz(body: QuizSubmit, user=Depends(current_user), prof=Depends(current_profile)):
    results, score = [], 0
    for q in lc.QUIZ:
        given = body.answers.get(q["id"])
        ok = given == q["answer"]
        score += ok
        results.append({"id": q["id"], "correct": ok, "answer": q["answer"], "why": q["why"]})
    await get_db().quiz_results.insert_one({"_id": new_id(), "user_id": user["_id"], "profile_id": prof["_id"], "score": score, "total": len(lc.QUIZ), "created_at": now_iso()})
    hist = sorted(await get_db().quiz_results.find({"profile_id": prof["_id"]}).to_list(100), key=lambda r: r["created_at"])
    return {"score": score, "total": len(lc.QUIZ), "results": results, "history": [{"score": h["score"], "total": h["total"], "date": h["created_at"][:10]} for h in hist[-10:]]}


@router.get("/learn/flashcard-progress")
async def fc_progress(prof=Depends(current_profile)):
    doc = await get_db().flashcard_progress.find_one({"profile_id": prof["_id"]})
    return {"known": (doc or {}).get("known", [])}


@router.put("/learn/flashcard-progress")
async def fc_progress_put(body: dict, prof=Depends(current_profile)):
    known = [k for k in body.get("known", []) if isinstance(k, str)]
    await get_db().flashcard_progress.update_one({"profile_id": prof["_id"]}, {"$set": {"known": known}, "$setOnInsert": {"_id": new_id()}}, upsert=True)
    return {"ok": True}
