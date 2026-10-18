"""AI-powered endpoints: insights (LE-RAG), Echo agent, voice, diagnostic guard, reports/labs, risk flags, timeline."""
import io
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import audit, current_profile, current_user
from app.core.util import clean, clean_many, new_id, now_iso
from app.data.specialties import ALL_SPECIALTIES, SPECIALTIES
from app.services import agent, chat_store, department, docreader, health_rules as hr, labs, llm, rag, vault, vector, verification
from app.services.vault import ext_ct
from app.services.safety import check_emergency, EMERGENCY_MESSAGE, EMERGENCY_RESOURCES

router = APIRouter(prefix="/api", tags=["ai"])


def _lang(user, lang):
    return lang or user.get("language") or "en"


# ---------------- Status ----------------
@router.get("/ai/status")
async def ai_status():
    return {"gemini": llm.gemini_configured(), "tavily": llm.tavily_configured(), "classifier_trained": department.model_available(),
            "vector": await vector.stats()}


# ---------------- Insights ----------------
@router.get("/insights")
async def list_insights(prof=Depends(current_profile)):
    rows = await get_db().insights.find({"profile_id": prof["_id"]}).to_list(100)
    return clean_many(sorted(rows, key=lambda r: -r["confidence"]))


@router.post("/insights/generate")
async def gen_insights(lang: str | None = None, user=Depends(current_user), prof=Depends(current_profile)):
    res = await rag.generate_insights(user["_id"], prof["_id"], _lang(user, lang))
    await audit(user, "insights_generate", f"{len(res)} insights", prof["_id"])
    chunks = await get_db().evidence_chunks.count_documents({"profile_id": prof["_id"]})
    return {"insights": sorted(clean_many(res), key=lambda r: -r["confidence"]), "evidence_chunks": chunks,
            "gate": {"min_occurrences": rag.MIN_OCCURRENCES, "min_distinct_sources": rag.MIN_DISTINCT_SOURCES}}


@router.get("/evidence")
async def evidence(source_type: str | None = None, prof=Depends(current_profile)):
    q = {"profile_id": prof["_id"], **({"source_type": source_type} if source_type else {})}
    rows = sorted(await get_db().evidence_chunks.find(q).to_list(5000), key=lambda r: r["timestamp"], reverse=True)
    return clean_many(rows[:300])


@router.get("/evidence/stats")
async def evidence_stats(prof=Depends(current_profile)):
    rows = await get_db().evidence_chunks.find({"profile_id": prof["_id"]}).to_list(10000)
    by_source: dict[str, int] = {}
    by_theme: dict[str, int] = {}
    for r in rows:
        by_source[r["source_type"]] = by_source.get(r["source_type"], 0) + 1
        for t in r["theme_tags"]:
            by_theme[t] = by_theme.get(t, 0) + 1
    return {"total": len(rows), "indexed": sum(1 for r in rows if r.get("indexed")), "by_source": by_source, "by_theme": by_theme}


class SearchIn(BaseModel):
    query: str
    top_k: int = 6


@router.post("/evidence/search")
async def evidence_search(body: SearchIn, prof=Depends(current_profile)):
    hits, method = await rag.search(prof["_id"], body.query, body.top_k)
    return {"method": method, "results": [{**clean(c), "similarity": round(s, 3)} for c, s in hits]}


# ---------------- Echo agent ----------------
class ChatIn(BaseModel):
    message: str
    lang: str | None = None


@router.post("/chat")
async def chat(body: ChatIn, user=Depends(current_user), prof=Depends(current_profile)):
    db = get_db()
    hist_rows = await chat_store.history(prof["_id"], 500)
    # One-time compatibility import for conversations created before Chroma became primary.
    if not hist_rows:
        try:
            legacy = await db.chat_messages.find({"profile_id": prof["_id"]}).to_list(500)
            legacy.sort(key=lambda m: m.get("created_at", ""))
            for row in legacy:
                await chat_store.save(row)
            hist_rows = await chat_store.history(prof["_id"], 500)
        except Exception as e:
            import logging
            logging.getLogger("echocare.chat").warning("Could not import legacy MongoDB chat history: %s", e)
    recent_rows = hist_rows[-12:]
    related_rows = await chat_store.search(prof["_id"], body.message, 5)
    known = {(m["role"], m["content"]) for m in recent_rows}
    context_rows = recent_rows + [m for m in related_rows if (m["role"], m["content"]) not in known]
    context_rows.sort(key=lambda m: m.get("created_at", ""))
    history = [{"role": m["role"], "content": m["content"], "kind": m.get("kind")} for m in context_rows]
    user_message = {"_id": new_id(), "user_id": user["_id"], "profile_id": prof["_id"], "role": "user",
                    "content": body.message, "created_at": now_iso()}
    await chat_store.save(user_message)
    try:
        await db.chat_messages.insert_one(user_message.copy())
    except Exception as e:
        import logging
        logging.getLogger("echocare.chat").warning("Chat is stored in ChromaDB; MongoDB mirror failed: %s", e)
    out = await agent.run_agent(prof["_id"], body.message, history, _lang(user, body.lang))
    if not out["is_emergency"] and out["kind"] != "followup":
        await rag.add_evidence(user["_id"], prof["_id"], "chat", body.message)
    assistant_message = {"_id": new_id(), "user_id": user["_id"], "profile_id": prof["_id"], "role": "assistant",
                         "content": out["content"], "kind": out.get("kind"), "tools_used": out["tools_used"],
                         "web_sources": out.get("web_sources", []), "is_emergency": out["is_emergency"],
                         "created_at": now_iso()}
    await chat_store.save(assistant_message)
    try:
        await db.chat_messages.insert_one(assistant_message.copy())
    except Exception as e:
        import logging
        logging.getLogger("echocare.chat").warning("Chat is stored in ChromaDB; MongoDB mirror failed: %s", e)
    return out


@router.get("/chat")
async def chat_history(prof=Depends(current_profile)):
    return clean_many(await chat_store.history(prof["_id"], 1000))


@router.delete("/chat")
async def chat_clear(prof=Depends(current_profile)):
    await chat_store.clear(prof["_id"])
    try:
        await get_db().chat_messages.delete_many({"profile_id": prof["_id"]})
    except Exception as e:
        import logging
        logging.getLogger("echocare.chat").warning("Chat cleared in ChromaDB; MongoDB mirror could not be cleared: %s", e)
    return {"ok": True}


@router.post("/voice/transcribe")
async def voice(file: UploadFile = File(...), user=Depends(current_user)):
    data = await file.read()
    if len(data) > get_settings().MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, "Audio too large")
    res = await llm.transcribe(data, file.content_type or "audio/wav")
    if not res["ok"]:
        return {"ok": False, "text": None, "reason": res["reason"]}
    return {"ok": True, "text": (res["text"] or "").strip(), "emergency": check_emergency(res["text"] or "")}


# ---------------- Diagnostic guard ----------------
class DeptIn(BaseModel):
    text: str


@router.post("/guard/department")
async def guard_department(body: DeptIn):
    if check_emergency(body.text):
        return {"is_emergency": True, "message": EMERGENCY_MESSAGE, "resources": [{"label": a, "value": b} for a, b in EMERGENCY_RESOURCES]}
    return {"is_emergency": False, **department.predict_department(body.text)}


@router.get("/guard/gaps")
async def guard_gaps(prof=Depends(current_profile)):
    return await hr.symptom_gaps(prof["_id"])


@router.get("/guard/specialties")
async def guard_specialties():
    return {"specialties": SPECIALTIES}


def photo_quality(data: bytes) -> dict:
    """Simple, local image-quality checks (no AI) so poor photos are retaken instead of over-interpreted."""
    from PIL import Image, ImageFilter, ImageStat
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return {"ok": False, "issues": ["The file could not be read as an image."], "metrics": {}}
    g = im.convert("L")
    w, h = g.size
    small = g.resize((min(w, 640), max(1, int(h * min(w, 640) / w))))
    bright = ImageStat.Stat(small).mean[0]
    sharp = ImageStat.Stat(small.filter(ImageFilter.FIND_EDGES)).var[0]
    contrast = ImageStat.Stat(small).stddev[0]
    issues = []
    if min(w, h) < 300:
        issues.append("The photo is very small. Take it closer or at a higher resolution.")
    if bright < 60:
        issues.append("The photo is too dark. Use natural daylight if you can.")
    elif bright > 215:
        issues.append("The photo is over-exposed or washed out. Avoid direct flash.")
    if sharp < 60:
        issues.append("The photo looks blurry. Hold the phone steady and tap to focus.")
    if contrast < 25:
        issues.append("The photo has very little contrast, so details may be lost.")
    return {"ok": not issues, "issues": issues, "metrics": {"width": w, "height": h, "brightness": round(bright), "sharpness": round(sharp), "contrast": round(contrast)}}


PHOTO_RED_FLAGS = ["Rapid spread over hours, or spreading red streaks", "Fever, chills or feeling very unwell", "Severe or worsening pain",
                   "Swelling of the face, lips or tongue, or trouble breathing", "Bleeding that will not stop, or a wound with pus, heat or a bad smell",
                   "A mole or spot that is changing in size, shape or colour, bleeds, or itches persistently"]
PHOTO_FOLLOWUPS = ["How long has this been there, and has it changed?", "Is it painful, itchy, burning or numb?",
                   "Any fever, new medicines, new foods, cosmetics or insect bites around the time it started?",
                   "Has it spread, or are there similar areas elsewhere on the body?", "Have you had anything like this before?"]


@router.post("/guard/photo")
async def photo_analysis(file: UploadFile = File(...), note: str = Form(""), body_area: str = Form(""), lang: str | None = Form(None),
                         user=Depends(current_user)):
    data = await file.read()
    if len(data) > get_settings().MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, "Image too large")
    if check_emergency(note):
        return {"is_emergency": True, "message": EMERGENCY_MESSAGE}
    quality = photo_quality(data)
    base = {"quality": quality, "followup_questions": PHOTO_FOLLOWUPS, "red_flags": PHOTO_RED_FLAGS,
            "disclaimer": "These are observations and general possibilities, not a diagnosis. Only a clinician who examines you can tell what this is."}
    spec = None
    try:
        if note and department.model_available():
            spec = department.predict_department(note)["top_department"]
    except Exception:
        spec = None
    prompt = ("You are describing a photo a person took of a body area. Return JSON only with keys: "
              '"visible_features" (list of short strings: colour, size, shape, borders, texture, distribution, swelling, only what is visible), '
              '"possible_explanations" (list of up to 3 objects {"category": str, "why": str}; use broad CATEGORIES such as "irritation or allergic-type reaction", '
              '"infection-type", "injury or bruising", "chronic skin condition", "pigment change"; NEVER name a specific disease and NEVER say it is or is not serious), '
              '"specialist" (one kind of specialist the person could show this to), "specialist_reason" (one sentence), '
              '"image_limits" (one sentence on what a photo cannot show). '
              f"Body area: {body_area or 'not stated'}. Patient note: {note or 'none'}.")
    res = await llm.vision([(data, file.content_type or "image/jpeg")], prompt, _lang(user, lang))
    parsed = labs.parse_json_loose(res["text"]) if res["ok"] else None
    if not parsed:
        return {"ok": False, "reason": res.get("reason") or "The AI response could not be read.", **base, "specialist": spec,
                "note": "Showing the quality check, follow-up questions and warning signs, which do not need AI."}
    return {"ok": True, "provider": res["provider"], "visible_features": parsed.get("visible_features") or [],
            "possible_explanations": (parsed.get("possible_explanations") or [])[:3], "specialist": parsed.get("specialist") or spec,
            "specialist_reason": parsed.get("specialist_reason"), "image_limits": parsed.get("image_limits"),
            "text": "; ".join(parsed.get("visible_features") or []), **base}


# ---------------- Reports & Labs ----------------
VISION_PROMPT = (
    "You are reading a medical lab report. Return JSON only: {\"report_title\": str, \"report_date\": \"YYYY-MM-DD\" or null, "
    "\"patient_name\": str|null, \"issuer_name\": str|null (lab/hospital that issued it), \"doctor_name\": str|null, "
    "\"registration_no\": str|null, \"summary\": str (2 sentences, non-diagnostic), \"fields\": [{\"test\": str, \"value\": str, \"unit\": str|null, "
    "\"reference_range\": str|null}]}. Include every measured value you can read. Do not invent values.")


@router.post("/reports")
async def upload_report(file: UploadFile = File(...), title: str = Form(""), report_date: str = Form(""),
                        user=Depends(current_user), prof=Depends(current_profile)):
    data = await file.read()
    if len(data) > get_settings().MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File larger than {get_settings().MAX_UPLOAD_MB} MB")
    name = file.filename or "report"
    ext = name.lower().rsplit(".", 1)[-1]
    if ext not in ("pdf", "png", "jpg", "jpeg", "webp"):
        raise HTTPException(415, "Upload a PDF or an image (png, jpg, webp)")
    fields, summary, method, text, hints = [], None, None, "", {}
    if llm.gemini_configured():
        parts = docreader.to_vision_parts(data, name)
        res = await llm.generate_json(VISION_PROMPT, parts)
        parsed = labs.parse_json_loose(res["text"]) if res["ok"] else None
        if parsed:
            fields = labs.normalize_vision_fields(parsed.get("fields"))
            summary = parsed.get("summary")
            title = title or parsed.get("report_title") or ""
            report_date = report_date or parsed.get("report_date") or ""
            hints = {k: parsed.get(k) for k in ("patient_name", "issuer_name", "doctor_name", "registration_no") if parsed.get(k)}
            method = "gemini-vision"
    if not method:
        text, how = docreader.extract_text(data, name)
        fields = labs.extract_fields(text)
        hints = verification.extract_identity_hints(text)
        method = how if text else "unreadable"
    doc = {"_id": new_id(), "user_id": user["_id"], "profile_id": prof["_id"], "title": title or name, "filename": name,
           "report_date": report_date or now_iso()[:10], "method": method, "fields": fields, "summary": summary,
           "text_preview": (text or "")[:1500], "created_at": now_iso(),
           "extracted": hints, "provenance": "extracted", "current_version": 1}
    await get_db().reports.insert_one(doc)
    await vault.store_file(doc, data, ext_ct(name, file.content_type), user, version=1)
    await vault.auto_verify(doc["_id"], user, prof)
    if summary:
        await rag.add_evidence(user["_id"], prof["_id"], "report", summary, {"source_id": doc["_id"]})
    await audit(user, "report_upload", name, prof["_id"])
    doc = await get_db().reports.find_one({"_id": doc["_id"]})
    note = None
    if method == "unreadable":
        note = "No text could be extracted. Configure GOOGLE_API_KEY for Gemini Vision, or enter values manually."
    return {**clean(doc), "note": note}


class ManualReport(BaseModel):
    title: str
    report_date: str | None = None
    fields: list[dict]
    summary: str | None = None


@router.post("/reports/manual")
async def manual_report(body: ManualReport, user=Depends(current_user), prof=Depends(current_profile)):
    fields = labs.normalize_vision_fields(body.fields)
    doc = {"_id": new_id(), "user_id": user["_id"], "profile_id": prof["_id"], "title": body.title, "filename": None,
           "report_date": body.report_date or now_iso()[:10], "method": "manual", "fields": fields, "summary": body.summary,
           "text_preview": "", "created_at": now_iso(), "extracted": {}, "provenance": "patient-entered", "current_version": 1}
    await get_db().reports.insert_one(doc)
    await vault.auto_verify(doc["_id"], user, prof)
    if body.summary:
        await rag.add_evidence(user["_id"], prof["_id"], "report", body.summary, {"source_id": doc["_id"]})
    return clean(await get_db().reports.find_one({"_id": doc["_id"]}))


@router.get("/reports")
async def list_reports(prof=Depends(current_profile)):
    rows = await get_db().reports.find({"profile_id": prof["_id"]}).to_list(500)
    return clean_many(sorted(rows, key=lambda r: r["report_date"], reverse=True))


@router.delete("/reports/{rid}")
async def delete_report(rid: str, prof=Depends(current_profile)):
    db = get_db()
    await db.reports.delete_one({"_id": rid, "profile_id": prof["_id"]})
    await db.report_files.delete_many({"report_id": rid, "profile_id": prof["_id"]})
    await db.verification_history.delete_many({"report_id": rid})
    await rag.delete_by_source(prof["_id"], rid)
    return {"ok": True}


@router.get("/labs/series")
async def lab_series(prof=Depends(current_profile)):
    reports = await get_db().reports.find({"profile_id": prof["_id"]}).to_list(500)
    series = labs.build_lab_series(reports)
    alerts = labs.latest_abnormal(series)
    return {"series": series, "alerts": alerts, "tests": sorted(series.keys())}


# ---------------- Risk flags & timeline ----------------
@router.get("/risk-flags")
async def risk_flags(prof=Depends(current_profile)):
    return await hr.compute_risk_flags(prof["_id"])


@router.get("/timeline")
async def timeline(prof=Depends(current_profile)):
    db, pid = get_db(), prof["_id"]
    ev = []
    for r in await db.story_entries.find({"profile_id": pid}).to_list(1000):
        ev.append({"date": r["created_at"][:10], "type": "story", "title": "Story entry", "detail": r["text"][:200], "tags": r["extracted_symptoms"]})
    for r in await db.tracker_entries.find({"profile_id": pid}).to_list(1000):
        if r.get("notes"):
            ev.append({"date": r["entry_date"], "type": "tracker", "title": "Tracker note", "detail": r["notes"][:200], "tags": rag.tag_themes(r["notes"])})
    for r in await db.vitals.find({"profile_id": pid}).to_list(1000):
        c = hr.classify_vital(r)
        bits = [f"BP {r['systolic']}/{r['diastolic']}" if r.get("systolic") else None, f"BMI {c['bmi']}" if c["bmi"] else None,
                f"Fasting {r['fasting_sugar']:g}" if r.get("fasting_sugar") else None]
        ev.append({"date": r["entry_date"], "type": "vitals", "title": "Vitals recorded", "detail": " · ".join(b for b in bits if b), "tags": []})
    for r in await db.reports.find({"profile_id": pid}).to_list(500):
        out = sum(1 for f in r["fields"] if f.get("out_of_range"))
        ev.append({"date": r["report_date"], "type": "report", "title": r["title"], "detail": f"{len(r['fields'])} values, {out} out of range", "tags": []})
    for r in await db.appointments.find({"profile_id": pid}).to_list(500):
        ev.append({"date": r["appt_date"], "type": "appointment", "title": f"Appointment: {r['doctor_name']}", "detail": r.get("hospital", ""), "tags": []})
    for r in await db.opinions.find({"profile_id": pid}).to_list(500):
        ev.append({"date": (r.get("opinion_date") or r["created_at"])[:10], "type": "opinion", "title": f"Opinion: {r.get('specialist_name') or 'specialist'}",
                   "detail": r["opinion_text"][:200], "tags": [r["department"]] if r.get("department") else []})
    return sorted(ev, key=lambda e: e["date"], reverse=True)
