"""Configurable health alerts with urgency and next-step guidance. Wording is non-diagnostic."""
from datetime import date, timedelta

from app.core.db import get_db
from app.services import labs

DEFAULTS = {
    "systolic_high": 140, "diastolic_high": 90, "systolic_urgent": 180, "diastolic_urgent": 120,
    "fasting_sugar_high": 126, "fasting_sugar_urgent": 300, "postmeal_sugar_high": 200,
    "spo2_low": 94, "spo2_urgent": 90, "heart_rate_high": 110, "heart_rate_low": 45, "temperature_high": 38.0,
    "sleep_low": 5, "stress_high": 8, "pain_high": 8, "adherence_low": 70,
}
LIMITS = {"systolic_high": (100, 200), "diastolic_high": (60, 130), "systolic_urgent": (140, 260), "diastolic_urgent": (90, 160),
          "fasting_sugar_high": (90, 250), "fasting_sugar_urgent": (200, 600), "postmeal_sugar_high": (120, 400),
          "spo2_low": (85, 99), "spo2_urgent": (70, 95), "heart_rate_high": (80, 200), "heart_rate_low": (30, 70),
          "temperature_high": (37.0, 41.0), "sleep_low": (2, 8), "stress_high": (4, 10), "pain_high": (4, 10), "adherence_low": (30, 100)}
URGENCY = {"urgent": 3, "soon": 2, "routine": 1}
GUIDE = {
    "urgent": "Do not wait for the next routine visit. Contact a clinician today, or emergency services if you feel unwell, "
              "have chest pain, trouble breathing, confusion or fainting.",
    "soon": "Worth discussing with a clinician within the next few days. Re-measure after resting and note the readings.",
    "routine": "Keep tracking and bring this up at your next routine appointment.",
}


async def get_settings_for(pid: str) -> dict:
    row = await get_db().alert_settings.find_one({"_id": pid})
    return {**DEFAULTS, **((row or {}).get("thresholds") or {})}


def validate(patch: dict) -> dict:
    out = {}
    for k, v in patch.items():
        if k not in DEFAULTS:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"{k} must be a number")
        lo, hi = LIMITS[k]
        if not lo <= f <= hi:
            raise ValueError(f"{k} must be between {lo} and {hi}")
        out[k] = f if isinstance(DEFAULTS[k], float) else int(f)
    return out


def _a(key, title, detail, urgency, href, when):
    return {"key": key, "title": title, "detail": detail, "urgency": urgency, "guidance": GUIDE[urgency], "href": href, "date": when}


async def evaluate(pid: str) -> list[dict]:
    db, t, out = get_db(), None, []
    t = await get_settings_for(pid)
    since = (date.today() - timedelta(days=14)).isoformat()
    for v in sorted(await db.vitals.find({"profile_id": pid, "entry_date": {"$gte": since}}).to_list(500), key=lambda r: r["entry_date"]):
        d, k = v["entry_date"], v["_id"]
        s, di = v.get("systolic"), v.get("diastolic")
        if s and di:
            if s >= t["systolic_urgent"] or di >= t["diastolic_urgent"]:
                out.append(_a(f"bp-{k}", "Very high blood pressure reading", f"{s}/{di} mmHg on {d}", "urgent", "/vitals", d))
            elif s >= t["systolic_high"] or di >= t["diastolic_high"]:
                out.append(_a(f"bp-{k}", "Blood pressure above your threshold", f"{s}/{di} mmHg on {d}", "soon", "/vitals", d))
        fs = v.get("fasting_sugar")
        if fs:
            if fs >= t["fasting_sugar_urgent"]:
                out.append(_a(f"fs-{k}", "Very high fasting sugar", f"{fs} mg/dL on {d}", "urgent", "/vitals", d))
            elif fs >= t["fasting_sugar_high"]:
                out.append(_a(f"fs-{k}", "Fasting sugar above your threshold", f"{fs} mg/dL on {d}", "soon", "/vitals", d))
        if v.get("postmeal_sugar") and v["postmeal_sugar"] >= t["postmeal_sugar_high"]:
            out.append(_a(f"pm-{k}", "Post-meal sugar above your threshold", f"{v['postmeal_sugar']} mg/dL on {d}", "soon", "/vitals", d))
        sp = v.get("spo2")
        if sp:
            if sp < t["spo2_urgent"]:
                out.append(_a(f"sp-{k}", "Low oxygen saturation", f"SpO2 {sp}% on {d}", "urgent", "/vitals", d))
            elif sp < t["spo2_low"]:
                out.append(_a(f"sp-{k}", "Oxygen saturation below your threshold", f"SpO2 {sp}% on {d}", "soon", "/vitals", d))
        hrt = v.get("heart_rate")
        if hrt and (hrt > t["heart_rate_high"] or hrt < t["heart_rate_low"]):
            out.append(_a(f"hr-{k}", "Heart rate outside your range", f"{hrt} bpm on {d}", "soon", "/vitals", d))
        if v.get("temperature_c") and v["temperature_c"] >= t["temperature_high"]:
            out.append(_a(f"tp-{k}", "Raised temperature", f"{v['temperature_c']} °C on {d}", "soon", "/vitals", d))
    for r in await db.tracker_entries.find({"profile_id": pid, "entry_date": {"$gte": since}}).to_list(500):
        d, k = r["entry_date"], r["_id"]
        if r.get("pain_level") is not None and r["pain_level"] >= t["pain_high"]:
            out.append(_a(f"pain-{k}", "Severe pain logged", f"Pain {r['pain_level']}/10 on {d}", "soon", "/tracker", d))
        if r.get("stress_level") is not None and r["stress_level"] >= t["stress_high"]:
            out.append(_a(f"st-{k}", "High stress logged", f"Stress {r['stress_level']}/10 on {d}", "routine", "/tracker", d))
        if r.get("sleep_hours") is not None and r["sleep_hours"] < t["sleep_low"]:
            out.append(_a(f"sl-{k}", "Short sleep logged", f"{r['sleep_hours']} h on {d}", "routine", "/tracker", d))
    from app.services import health_rules as hr
    taken, expected = await hr.adherence(pid, 7)
    if expected and round(100 * taken / expected) < t["adherence_low"]:
        out.append(_a(f"adh-{date.today()}", "Missed medicine doses this week", f"{taken} of {expected} doses taken ({round(100 * taken / expected)}%)", "soon", "/medicines", date.today().isoformat()))
    reports = await db.reports.find({"profile_id": pid}).to_list(300)
    for a in labs.latest_abnormal(labs.build_lab_series(reports))[:5]:
        out.append(_a(f"lab-{a.get('label')}-{a.get('date')}", f"{a.get('label')} outside reference range",
                      f"{a.get('value')} {a.get('unit') or ''} on {a.get('date')}".strip(), "routine", "/labs", a.get("date") or ""))
    out.sort(key=lambda x: x["date"], reverse=True)
    out.sort(key=lambda x: -URGENCY[x["urgency"]])
    return out
