"""Profile-scoped health records: story, survey, tracker, vitals, medicines, appointments, goals, opinions."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.core.db import get_db
from app.core.deps import current_profile, current_user
from app.core.util import clean, clean_many, new_id, now_iso, today_iso
from app.services import compare, health_rules as hr, rag
from app.services.safety import EMERGENCY_MESSAGE, EMERGENCY_RESOURCES, check_emergency

router = APIRouter(prefix="/api", tags=["records"])


def _emergency_payload():
    return {"is_emergency": True, "message": EMERGENCY_MESSAGE, "resources": [{"label": a, "value": b} for a, b in EMERGENCY_RESOURCES]}


# ---------------- Story ----------------
class StoryIn(BaseModel):
    text: str = Field(min_length=3, max_length=4000)
    mood: str | None = None


@router.post("/story")
async def add_story(body: StoryIn, user=Depends(current_user), prof=Depends(current_profile)):
    if check_emergency(body.text):  # safety guard runs BEFORE anything is stored or sent to a model
        return _emergency_payload()
    db = get_db()
    doc = {"_id": new_id(), "user_id": user["_id"], "profile_id": prof["_id"], "text": body.text.strip(), "mood": body.mood,
           "extracted_symptoms": rag.tag_themes(body.text), "timeline": rag.extract_timeline(body.text), "created_at": now_iso()}
    await db.story_entries.insert_one(doc)
    n = await rag.add_evidence(user["_id"], prof["_id"], "story", body.text, {"source_id": doc["_id"]})
    return {"is_emergency": False, "entry": clean(doc), "chunks": n}


@router.get("/story")
async def list_story(prof=Depends(current_profile)):
    rows = await get_db().story_entries.find({"profile_id": prof["_id"]}).to_list(2000)
    return clean_many(sorted(rows, key=lambda r: r["created_at"], reverse=True))


@router.delete("/story/{eid}")
async def del_story(eid: str, prof=Depends(current_profile)):
    await get_db().story_entries.delete_one({"_id": eid, "profile_id": prof["_id"]})
    await rag.delete_by_source(prof["_id"], eid)
    return {"ok": True}


# ---------------- Survey ----------------
@router.get("/survey")
async def get_survey(prof=Depends(current_profile)):
    return clean(await get_db().survey_responses.find_one({"profile_id": prof["_id"]}))


@router.put("/survey")
async def put_survey(body: dict, user=Depends(current_user), prof=Depends(current_profile)):
    groups = {g: {k: v for k, v in (body.get(g) or {}).items()} for g in ("about_you", "main_concern", "care_context")}
    text = " ".join(str(v) for v in groups["main_concern"].values() if v)
    if check_emergency(text):
        return _emergency_payload()
    db = get_db()
    old = await db.survey_responses.find_one({"profile_id": prof["_id"]})
    sid = old["_id"] if old else new_id()
    await db.survey_responses.replace_one({"_id": sid}, {"_id": sid, "user_id": user["_id"], "profile_id": prof["_id"],
                                                          **groups, "updated_at": now_iso()}, upsert=True)
    await rag.delete_by_source(prof["_id"], sid)
    await rag.add_evidence(user["_id"], prof["_id"], "survey", text, {"source_id": sid})
    return {"is_emergency": False, "ok": True}


# ---------------- Tracker ----------------
class TrackerIn(BaseModel):
    entry_date: str | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    water_glasses: int | None = Field(default=None, ge=0, le=40)
    stress_level: int | None = Field(default=None, ge=0, le=10)
    energy_level: int | None = Field(default=None, ge=0, le=10)
    pain_level: int | None = Field(default=None, ge=0, le=10)
    mood: str | None = None
    steps: int | None = Field(default=None, ge=0, le=100000)
    notes: str | None = Field(default=None, max_length=2000)


@router.post("/tracker")
async def save_tracker(body: TrackerIn, user=Depends(current_user), prof=Depends(current_profile)):
    if body.notes and check_emergency(body.notes):
        return _emergency_payload()
    db = get_db()
    d = body.entry_date or today_iso()
    old = await db.tracker_entries.find_one({"profile_id": prof["_id"], "entry_date": d})
    eid = old["_id"] if old else new_id()
    doc = {**body.model_dump(), "_id": eid, "entry_date": d, "user_id": user["_id"], "profile_id": prof["_id"], "updated_at": now_iso()}
    await db.tracker_entries.replace_one({"_id": eid}, doc, upsert=True)
    await rag.delete_by_source(prof["_id"], eid)
    if body.notes:
        await rag.add_evidence(user["_id"], prof["_id"], "tracker", body.notes, {"source_id": eid})
    return {"is_emergency": False, "entry": clean(doc)}


@router.get("/tracker")
async def list_tracker(days: int = Query(60, ge=1, le=730), prof=Depends(current_profile)):
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = await get_db().tracker_entries.find({"profile_id": prof["_id"], "entry_date": {"$gte": since}}).to_list(2000)
    return clean_many(sorted(rows, key=lambda r: r["entry_date"]))


@router.delete("/tracker/{eid}")
async def del_tracker(eid: str, prof=Depends(current_profile)):
    await get_db().tracker_entries.delete_one({"_id": eid, "profile_id": prof["_id"]})
    await rag.delete_by_source(prof["_id"], eid)
    return {"ok": True}


# ---------------- Vitals ----------------
class VitalIn(BaseModel):
    entry_date: str | None = None
    weight_kg: float | None = Field(default=None, gt=0, lt=500)
    height_cm: float | None = Field(default=None, gt=30, lt=272)
    systolic: int | None = Field(default=None, gt=40, lt=300)
    diastolic: int | None = Field(default=None, gt=20, lt=200)
    heart_rate: int | None = Field(default=None, gt=20, lt=260)
    fasting_sugar: float | None = Field(default=None, gt=10, lt=900)
    postmeal_sugar: float | None = Field(default=None, gt=10, lt=900)
    spo2: int | None = Field(default=None, ge=50, le=100)
    temperature_c: float | None = Field(default=None, gt=30, lt=45)


@router.post("/vitals")
async def add_vital(body: VitalIn, user=Depends(current_user), prof=Depends(current_profile)):
    doc = {**body.model_dump(), "_id": new_id(), "entry_date": body.entry_date or today_iso(), "user_id": user["_id"],
           "profile_id": prof["_id"], "created_at": now_iso()}
    await get_db().vitals.insert_one(doc)
    return {**clean(doc), **hr.classify_vital(doc)}


@router.get("/vitals")
async def list_vitals(prof=Depends(current_profile)):
    rows = sorted(await get_db().vitals.find({"profile_id": prof["_id"]}).to_list(2000), key=lambda r: (r["entry_date"], r["created_at"]))
    return {"items": [{**clean(r), **hr.classify_vital(r)} for r in rows], "targets": hr.TARGETS}


@router.delete("/vitals/{vid}")
async def del_vital(vid: str, prof=Depends(current_profile)):
    await get_db().vitals.delete_one({"_id": vid, "profile_id": prof["_id"]})
    return {"ok": True}


# ---------------- Medicines ----------------
class MedIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    dose: str = ""
    frequency: str = "Daily"
    slots: list[str] = Field(default_factory=lambda: ["morning"])
    start_date: str | None = None
    end_date: str | None = None
    notes: str | None = None


@router.post("/medicines")
async def add_med(body: MedIn, user=Depends(current_user), prof=Depends(current_profile)):
    doc = {**body.model_dump(), "_id": new_id(), "start_date": body.start_date or today_iso(), "active": True,
           "user_id": user["_id"], "profile_id": prof["_id"], "created_at": now_iso()}
    await get_db().medicines.insert_one(doc)
    return clean(doc)


@router.get("/medicines")
async def list_meds(active_only: bool = False, prof=Depends(current_profile)):
    q = {"profile_id": prof["_id"], **({"active": True} if active_only else {})}
    return clean_many(await get_db().medicines.find(q).to_list(500))


@router.patch("/medicines/{mid}")
async def patch_med(mid: str, body: dict, prof=Depends(current_profile)):
    allowed = {k: v for k, v in body.items() if k in MedIn.model_fields or k == "active"}
    await get_db().medicines.update_one({"_id": mid, "profile_id": prof["_id"]}, {"$set": allowed})
    return {"ok": True}


@router.delete("/medicines/{mid}")
async def del_med(mid: str, prof=Depends(current_profile)):
    db = get_db()
    await db.medicines.delete_one({"_id": mid, "profile_id": prof["_id"]})
    await db.dose_logs.delete_many({"medicine_id": mid})
    return {"ok": True}


class DoseIn(BaseModel):
    medicine_id: str
    slot: str
    log_date: str | None = None
    taken: bool = True


@router.post("/medicines/dose")
async def log_dose(body: DoseIn, user=Depends(current_user), prof=Depends(current_profile)):
    db = get_db()
    d = body.log_date or today_iso()
    key = {"profile_id": prof["_id"], "medicine_id": body.medicine_id, "slot": body.slot, "log_date": d}
    old = await db.dose_logs.find_one(key)
    did = old["_id"] if old else new_id()
    await db.dose_logs.replace_one({"_id": did}, {"_id": did, **key, "taken": body.taken, "user_id": user["_id"]}, upsert=True)
    return {"ok": True}


@router.get("/medicines/doses")
async def dose_logs(days: int = 14, prof=Depends(current_profile)):
    since = (date.today() - timedelta(days=days)).isoformat()
    return clean_many(await get_db().dose_logs.find({"profile_id": prof["_id"], "log_date": {"$gte": since}}).to_list(10000))


@router.get("/medicines/adherence")
async def adherence(prof=Depends(current_profile)):
    out = []
    for i in range(6, -1, -1):
        day = date.today() - timedelta(days=i)
        t, e = await hr.adherence(prof["_id"], 1, day)
        out.append({"date": day.isoformat(), "taken": t, "expected": e})
    t, e = await hr.adherence(prof["_id"], 7)
    return {"taken": t, "expected": e, "percent": round(100 * t / e) if e else None, "daily": out}


# ---------------- Appointments ----------------
class ApptIn(BaseModel):
    doctor_name: str = Field(min_length=1)
    specialty: str | None = None
    hospital: str = ""
    appt_date: str
    appt_time: str = "10:00"
    notes: str | None = None
    status: str = "scheduled"


@router.post("/appointments")
async def add_appt(body: ApptIn, user=Depends(current_user), prof=Depends(current_profile)):
    doc = {**body.model_dump(), "_id": new_id(), "user_id": user["_id"], "profile_id": prof["_id"], "created_at": now_iso()}
    await get_db().appointments.insert_one(doc)
    return clean(doc)


@router.get("/appointments")
async def list_appt(prof=Depends(current_profile)):
    rows = await get_db().appointments.find({"profile_id": prof["_id"]}).to_list(1000)
    return clean_many(sorted(rows, key=lambda r: (r["appt_date"], r["appt_time"])))


@router.patch("/appointments/{aid}")
async def patch_appt(aid: str, body: dict, prof=Depends(current_profile)):
    allowed = {k: v for k, v in body.items() if k in ApptIn.model_fields}
    await get_db().appointments.update_one({"_id": aid, "profile_id": prof["_id"]}, {"$set": allowed})
    return {"ok": True}


@router.delete("/appointments/{aid}")
async def del_appt(aid: str, prof=Depends(current_profile)):
    await get_db().appointments.delete_one({"_id": aid, "profile_id": prof["_id"]})
    return {"ok": True}


@router.get("/appointments/{aid}/ics")
async def appt_ics(aid: str, prof=Depends(current_profile)):
    a = await get_db().appointments.find_one({"_id": aid, "profile_id": prof["_id"]})
    if not a:
        raise HTTPException(404, "Not found")
    start = datetime.fromisoformat(f"{a['appt_date']}T{a['appt_time']}")
    end = start + timedelta(minutes=30)
    f = lambda d: d.strftime("%Y%m%dT%H%M%S")
    ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//EchoCare//EN\r\nBEGIN:VEVENT\r\n"
           f"UID:{a['_id']}@echocare\r\nDTSTAMP:{f(datetime.utcnow())}Z\r\nDTSTART:{f(start)}\r\nDTEND:{f(end)}\r\n"
           f"SUMMARY:Appointment with {a['doctor_name']}\r\nLOCATION:{a.get('hospital', '')}\r\n"
           f"DESCRIPTION:{a.get('notes') or 'EchoCare appointment'}\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
    return Response(ics, media_type="text/calendar", headers={"Content-Disposition": "attachment; filename=appointment.ics"})


# ---------------- Goals ----------------
class GoalIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    target: float = Field(gt=0)
    unit: str = ""
    current: float = 0
    metric: str | None = None  # sleep_hours | water_glasses | steps | custom
    due_date: str | None = None


@router.post("/goals")
async def add_goal(body: GoalIn, user=Depends(current_user), prof=Depends(current_profile)):
    doc = {**body.model_dump(), "_id": new_id(), "user_id": user["_id"], "profile_id": prof["_id"], "created_at": now_iso()}
    await get_db().goals.insert_one(doc)
    return clean(doc)


@router.get("/goals")
async def list_goals(prof=Depends(current_profile)):
    return clean_many(await get_db().goals.find({"profile_id": prof["_id"]}).to_list(200))


@router.patch("/goals/{gid}")
async def patch_goal(gid: str, body: dict, prof=Depends(current_profile)):
    allowed = {k: v for k, v in body.items() if k in GoalIn.model_fields}
    await get_db().goals.update_one({"_id": gid, "profile_id": prof["_id"]}, {"$set": allowed})
    return {"ok": True}


@router.delete("/goals/{gid}")
async def del_goal(gid: str, prof=Depends(current_profile)):
    await get_db().goals.delete_one({"_id": gid, "profile_id": prof["_id"]})
    return {"ok": True}


# ---------------- Specialist opinions ----------------
class OpinionIn(BaseModel):
    specialist_name: str | None = None
    department: str | None = None
    opinion_text: str = Field(min_length=3, max_length=5000)
    opinion_date: str | None = None


@router.post("/opinions")
async def add_opinion(body: OpinionIn, user=Depends(current_user), prof=Depends(current_profile)):
    doc = {**body.model_dump(), "_id": new_id(), "user_id": user["_id"], "profile_id": prof["_id"], "created_at": now_iso()}
    await get_db().opinions.insert_one(doc)
    await rag.add_evidence(user["_id"], prof["_id"], "opinion", body.opinion_text, {"source_id": doc["_id"]})
    return clean(doc)


@router.get("/opinions")
async def list_opinions(prof=Depends(current_profile)):
    return clean_many(await get_db().opinions.find({"profile_id": prof["_id"]}).to_list(500))


@router.delete("/opinions/{oid}")
async def del_opinion(oid: str, prof=Depends(current_profile)):
    await get_db().opinions.delete_one({"_id": oid, "profile_id": prof["_id"]})
    await rag.delete_by_source(prof["_id"], oid)
    return {"ok": True}


class CompareIn(BaseModel):
    a: str
    b: str


@router.post("/opinions/compare")
async def compare_opinions(body: CompareIn):
    sa, sb = compare.diff_segments(body.a, body.b)
    return {"a": sa, "b": sb, "signals": compare.conflict_signals(body.a, body.b)}
