"""Vitals classification (BMI / BP / blood sugar) and the cross-source risk-flag engine.
Worded as 'in / above / below the usual target range' and 'worth discussing with your clinician': never a diagnosis."""
from datetime import date, datetime, timedelta

from app.core.db import get_db
from app.data.specialties import SPECIALTIES
from app.services import labs

TARGETS = [
    {"name": "BMI", "target": "18.5 – 24.9 kg/m²", "note": "Underweight < 18.5 · Overweight 25 – 29.9 · Obese ≥ 30 (WHO adult categories)"},
    {"name": "Blood pressure", "target": "< 120 / 80 mmHg", "note": "Elevated 120 – 129 / <80 · Stage 1: 130 – 139 or 80 – 89 · Stage 2: ≥ 140 or ≥ 90"},
    {"name": "Fasting sugar", "target": "70 – 99 mg/dL", "note": "100 – 125 above the usual target · ≥ 126 is in the range clinicians follow up"},
    {"name": "Post-meal sugar (2 h)", "target": "< 140 mg/dL", "note": "140 – 199 above target · ≥ 200 high"},
]


def bmi(w, h):
    if not w or not h:
        return None, None
    v = round(w / ((h / 100) ** 2), 1)
    if v < 18.5:
        return v, ("Below target range", "watch")
    if v < 25:
        return v, ("In target range", "ok")
    if v < 30:
        return v, ("Above target range", "watch")
    return v, ("Well above target range", "alert")


def bp_category(s, d):
    if not s or not d:
        return None
    if s > 180 or d > 120:
        return ("Very high, seek medical help now", "alert")
    if s >= 140 or d >= 90:
        return ("Stage 2 range", "alert")
    if s >= 130 or d >= 80:
        return ("Stage 1 range", "watch")
    if s >= 120:
        return ("Elevated", "watch")
    if s < 90 or d < 60:
        return ("Below usual range", "watch")
    return ("In target range", "ok")


def fasting_cat(v):
    if v is None:
        return None
    if v < 70:
        return ("Below target range", "alert")
    if v < 100:
        return ("In target range", "ok")
    if v < 126:
        return ("Above target range", "watch")
    return ("High, worth clinical follow-up", "alert")


def postmeal_cat(v):
    if v is None:
        return None
    if v < 140:
        return ("In target range", "ok")
    if v < 200:
        return ("Above target range", "watch")
    return ("High, worth clinical follow-up", "alert")


def classify_vital(r: dict) -> dict:
    b, bc = bmi(r.get("weight_kg"), r.get("height_cm"))
    bp = bp_category(r.get("systolic"), r.get("diastolic"))
    return {"bmi": b, "bmi_cat": bc, "bp_cat": bp, "fasting_cat": fasting_cat(r.get("fasting_sugar")),
            "postmeal_cat": postmeal_cat(r.get("postmeal_sugar"))}


async def adherence(profile_id: str, days: int = 7, today: date | None = None) -> tuple[int, int]:
    db = get_db()
    today = today or date.today()
    start = today - timedelta(days=days - 1)
    expected = 0
    for m in await db.medicines.find({"profile_id": profile_id, "active": True}).to_list(500):
        s = date.fromisoformat(m["start_date"]) if m.get("start_date") else start
        e = date.fromisoformat(m["end_date"]) if m.get("end_date") else today
        d0, d1 = max(s, start), min(e, today)
        if d1 >= d0:
            expected += ((d1 - d0).days + 1) * len(m.get("slots") or [1])
    logs = await db.dose_logs.find({"profile_id": profile_id, "log_date": {"$gte": start.isoformat()}}).to_list(5000)
    taken = sum(1 for l in logs if l.get("taken") and l["log_date"] <= today.isoformat())
    return taken, expected


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


async def compute_risk_flags(profile_id: str, today: date | None = None) -> list[dict]:
    db = get_db()
    today = today or date.today()
    flags: list[dict] = []

    def add(level, title, detail, sources):
        flags.append({"level": level, "title": title, "detail": detail, "sources": sources})

    since = (today - timedelta(days=6)).isoformat()
    week = sorted(await db.tracker_entries.find({"profile_id": profile_id, "entry_date": {"$gte": since}}).to_list(100),
                  key=lambda e: e["entry_date"])
    sleep = [e["sleep_hours"] for e in week if e.get("sleep_hours") is not None]
    stress, energy = _avg([e.get("stress_level") for e in week]), _avg([e.get("energy_level") for e in week])
    sleep_avg = _avg(sleep)
    pain_days = sum(1 for e in week[-5:] if (e.get("pain_level") or 0) >= 7)
    pain_avg = _avg([e.get("pain_level") for e in week])
    if len(sleep) >= 3 and sleep_avg < 6:
        add("watch", "Short-sleep pattern", f"You averaged {sleep_avg:.1f} h of sleep over the last {len(sleep)} logged days.", ["tracker"])
    if pain_days >= 2:
        add("discuss", "Repeated high pain days", f"Pain was rated 7 or higher on {pain_days} of your last 5 check-ins.", ["tracker"])
    if stress is not None and len(week) >= 3 and stress >= 8:
        add("watch", "Sustained high stress", f"Average stress {stress:.1f}/10 this week.", ["tracker"])
    if energy is not None and len(week) >= 3 and energy <= 3:
        add("watch", "Persistently low energy", f"Average energy {energy:.1f}/10 this week.", ["tracker"])

    vitals = sorted(await db.vitals.find({"profile_id": profile_id}).to_list(1000), key=lambda v: v["entry_date"])
    bp = next(((v["systolic"], v["diastolic"]) for v in reversed(vitals) if v.get("systolic") and v.get("diastolic")), None)
    bpc = bp_category(*bp) if bp else None
    if bpc and bpc[1] == "alert":
        add("discuss", "Blood pressure above usual target", f"Latest reading {bp[0]}/{bp[1]} mmHg ({bpc[0]}).", ["vitals"])
    fs = next((v["fasting_sugar"] for v in reversed(vitals) if v.get("fasting_sugar")), None)
    fsc = fasting_cat(fs)
    if fsc and fsc[1] != "ok":
        add("discuss" if fsc[1] == "alert" else "watch", "Fasting sugar outside target", f"Latest fasting value {fs:g} mg/dL ({fsc[0]}).", ["vitals"])
    w = next(((v["weight_kg"], v["height_cm"]) for v in reversed(vitals) if v.get("weight_kg") and v.get("height_cm")), None)
    if w:
        b, cat = bmi(*w)
        if cat[1] != "ok":
            add("watch", "BMI outside target range", f"BMI {b} ({cat[0]}).", ["vitals"])

    reports = await db.reports.find({"profile_id": profile_id}).to_list(500)
    abnormal = labs.latest_abnormal(labs.build_lab_series(reports))
    if abnormal:
        names = ", ".join(sorted({a["label"] for a in abnormal})[:5])
        add("discuss" if len(abnormal) >= 2 else "watch", "Lab values outside reference range",
            f"{len(abnormal)} test(s) on your latest reports are out of range: {names}.", ["reports"])

    taken, expected = await adherence(profile_id, 7, today)
    if expected >= 5 and taken / expected < 0.6:
        add("watch", "Missed medicine doses", f"You logged {taken} of {expected} expected doses this week ({round(100 * taken / expected)}%).", ["medicines"])

    stats: dict[str, dict] = {}
    for c in await db.evidence_chunks.find({"profile_id": profile_id}).to_list(10000):
        for t in c["theme_tags"]:
            if t in SPECIALTIES:
                s = stats.setdefault(t, {"n": 0, "sources": set()})
                s["n"] += 1
                s["sources"].add(c["source_type"])
    recurring = {t: s for t, s in stats.items() if s["n"] >= 3 and len(s["sources"]) >= 2}
    for t, s in recurring.items():
        add("discuss", f"Recurring {t} symptoms", f"{s['n']} mentions across {', '.join(sorted(s['sources']))}. Consider raising this with a {t} specialist.", sorted(s["sources"]))
    if "Cardiology" in recurring and bpc and bpc[1] != "ok":
        add("discuss", "Combined signal: heart-related symptoms + blood pressure",
            "Recurring cardiology-type symptoms appear alongside a blood pressure reading outside the usual target.", ["story/survey", "vitals"])
    if "Psychiatry / Mental Health" in recurring and ((stress or 0) >= 7 or (sleep_avg is not None and sleep_avg < 6)):
        add("discuss", "Combined signal: mood symptoms + stress/sleep",
            "Recurring mood-related symptoms appear alongside high stress or short sleep in your tracker.", ["story/survey", "tracker"])
    if "Orthopedics" in recurring and (pain_avg or 0) >= 5:
        add("discuss", "Combined signal: joint/back symptoms + pain scores",
            "Recurring musculoskeletal symptoms appear alongside consistently elevated pain scores.", ["story/survey", "tracker"])
    order = {"discuss": 0, "watch": 1}
    return sorted(flags, key=lambda f: order[f["level"]])


async def symptom_gaps(profile_id: str) -> list[dict]:
    by_theme: dict[str, list] = {}
    for c in await get_db().evidence_chunks.find({"profile_id": profile_id}).to_list(10000):
        for tag in c["theme_tags"]:
            if tag != "general_wellbeing":
                by_theme.setdefault(tag, []).append(datetime.fromisoformat(c["timestamp"]))
    gaps = []
    for theme, stamps in by_theme.items():
        weeks = {(t.isocalendar()[0], t.isocalendar()[1]) for t in stamps}
        if len(weeks) >= 2 or len(stamps) >= 3:
            gaps.append({"symptom": theme, "occurrences": len(stamps), "first": min(stamps).isoformat(), "last": max(stamps).isoformat()})
    return sorted(gaps, key=lambda g: -g["occurrences"])
