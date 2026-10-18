"""Dashboard, analytics, notifications, global search, data export."""
import statistics
from collections import Counter
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.db import get_db
from app.core.deps import current_profile, current_user
from app.core.util import clean_many, new_id, now_iso
from app.services import alerts as alerts_svc, health_rules as hr, labs, rag

router = APIRouter(prefix="/api", tags=["dashboard"])


def _avg(v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 2) if v else None


async def _streak(pid: str) -> int:
    dates = {r["entry_date"] for r in await get_db().tracker_entries.find({"profile_id": pid}).to_list(2000)}
    n, d = 0, date.today()
    if d.isoformat() not in dates:
        d -= timedelta(days=1)
    while d.isoformat() in dates:
        n += 1
        d -= timedelta(days=1)
    return n


def wellness_score(flags, adherence_pct, sleep_avg, stress_avg, streak) -> dict:
    """Transparent, self-reported composite (NOT a clinical score). Every component is returned for display."""
    parts = []
    base = 100
    for f in flags:
        pen = 8 if f["level"] == "discuss" else 4
        parts.append({"label": f["title"], "points": -pen})
        base -= pen
    if adherence_pct is not None and adherence_pct < 60:
        parts.append({"label": "Medicine adherence below 60%", "points": -5})
        base -= 5
    if sleep_avg is not None and sleep_avg >= 7:
        parts.append({"label": "Healthy sleep average", "points": 3})
        base += 3
    if stress_avg is not None and stress_avg <= 4:
        parts.append({"label": "Low stress this week", "points": 2})
        base += 2
    if streak >= 3:
        bonus = min(streak, 10) // 2
        parts.append({"label": f"{streak}-day check-in streak", "points": bonus})
        base += bonus
    return {"score": max(0, min(100, base)), "components": parts,
            "note": "Self-reported wellness indicator built from your own data. It is not a medical score."}


@router.get("/dashboard")
async def dashboard(prof=Depends(current_profile), user=Depends(current_user)):
    db, pid = get_db(), prof["_id"]
    since14 = (date.today() - timedelta(days=13)).isoformat()
    trk = sorted(await db.tracker_entries.find({"profile_id": pid, "entry_date": {"$gte": since14}}).to_list(100), key=lambda r: r["entry_date"])
    flags = await hr.compute_risk_flags(pid)
    taken, expected = await hr.adherence(pid, 7)
    pct = round(100 * taken / expected) if expected else None
    week = trk[-7:]
    sleep_avg, stress_avg = _avg([r.get("sleep_hours") for r in week]), _avg([r.get("stress_level") for r in week])
    streak = await _streak(pid)
    vit = sorted(await db.vitals.find({"profile_id": pid}).to_list(1000), key=lambda r: (r["entry_date"], r["created_at"]))
    latest_vital = None
    if vit:
        lv = vit[-1]
        latest_vital = {**{k: v for k, v in lv.items() if k not in ("_id", "user_id", "profile_id")}, **hr.classify_vital(lv)}
    reports = await db.reports.find({"profile_id": pid}).to_list(500)
    alerts = labs.latest_abnormal(labs.build_lab_series(reports))
    appts = [a for a in await db.appointments.find({"profile_id": pid}).to_list(500)
             if a.get("status") == "scheduled" and a["appt_date"] >= date.today().isoformat()]
    appts.sort(key=lambda a: (a["appt_date"], a["appt_time"]))
    ev = await db.evidence_chunks.find({"profile_id": pid}).to_list(10000)
    themes = Counter(t for c in ev for t in c["theme_tags"] if t != "general_wellbeing")
    goals = await db.goals.find({"profile_id": pid}).to_list(100)
    return {
        "profile": {"id": pid, "name": prof["name"]},
        "counts": {"story": await db.story_entries.count_documents({"profile_id": pid}), "reports": len(reports),
                   "medicines": await db.medicines.count_documents({"profile_id": pid, "active": True}),
                   "evidence": len(ev), "insights": await db.insights.count_documents({"profile_id": pid}),
                   "appointments": len(appts)},
        "score": wellness_score(flags, pct, sleep_avg, stress_avg, streak),
        "streak": streak, "flags": flags[:6], "flag_count": len(flags),
        "tracker": [{k: r.get(k) for k in ("entry_date", "sleep_hours", "water_glasses", "stress_level", "energy_level", "pain_level", "steps")} for r in trk],
        "week_avg": {"sleep": sleep_avg, "stress": stress_avg, "energy": _avg([r.get("energy_level") for r in week]),
                     "water": _avg([r.get("water_glasses") for r in week]), "pain": _avg([r.get("pain_level") for r in week])},
        "adherence": {"taken": taken, "expected": expected, "percent": pct},
        "vitals_trend": [{"date": v["entry_date"], "systolic": v.get("systolic"), "diastolic": v.get("diastolic"), "fasting": v.get("fasting_sugar")} for v in vit[-8:]],
        "lab_history": [{"date": r["report_date"], "title": r["title"], "in_range": sum(1 for f in r["fields"] if not f.get("out_of_range")), "out_of_range": sum(1 for f in r["fields"] if f.get("out_of_range"))} for r in sorted(reports, key=lambda r: r["report_date"])[-6:]],
        "latest_vital": latest_vital, "lab_alerts": alerts[:6],
        "upcoming": [{"id": a["_id"], **{k: a.get(k) for k in ("doctor_name", "hospital", "appt_date", "appt_time", "specialty")}} for a in appts[:4]],
        "themes": [{"theme": k, "count": v} for k, v in themes.most_common()],
        "goals": [{"id": g["_id"], "title": g["title"], "target": g["target"], "current": g.get("current", 0), "unit": g.get("unit", "")} for g in goals],
    }


def _pearson(x, y):
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 5:
        return None
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    if statistics.pstdev(xs) == 0 or statistics.pstdev(ys) == 0:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((a - mx) * (b - my) for a, b in pairs) / len(pairs)
    return round(cov / (statistics.pstdev(xs) * statistics.pstdev(ys)), 2)


@router.get("/analytics")
async def analytics(days: int = Query(90, ge=14, le=365), prof=Depends(current_profile)):
    db, pid = get_db(), prof["_id"]
    since = (date.today() - timedelta(days=days)).isoformat()
    trk = sorted(await db.tracker_entries.find({"profile_id": pid, "entry_date": {"$gte": since}}).to_list(1000), key=lambda r: r["entry_date"])
    metrics = ["sleep_hours", "stress_level", "energy_level", "pain_level", "water_glasses", "steps"]
    labels = ["Sleep", "Stress", "Energy", "Pain", "Water", "Steps"]
    corr = [[(1.0 if i == j else _pearson([r.get(a) for r in trk], [r.get(b) for r in trk])) for j, b in enumerate(metrics)] for i, a in enumerate(metrics)]
    weeks: dict[str, dict] = {}
    for r in trk:
        d = date.fromisoformat(r["entry_date"])
        key = (d - timedelta(days=d.weekday())).isoformat()
        w = weeks.setdefault(key, {k: [] for k in metrics})
        for k in metrics:
            if r.get(k) is not None:
                w[k].append(r[k])
    weekly = [{"week": k, **{m: _avg(v[m]) for m in metrics}} for k, v in sorted(weeks.items())]
    ev = await db.evidence_chunks.find({"profile_id": pid}).to_list(10000)
    heat: dict[str, Counter] = {}
    for c in ev:
        d = datetime.fromisoformat(c["timestamp"]).date()
        wk = (d - timedelta(days=d.weekday())).isoformat()
        for t in c["theme_tags"]:
            if t != "general_wellbeing":
                heat.setdefault(t, Counter())[wk] += 1
    all_weeks = sorted({w for c in heat.values() for w in c})
    moods = Counter(r.get("mood") for r in trk if r.get("mood"))
    sources = Counter(c["source_type"] for c in ev)
    insights = []
    s_e = corr[0][2]
    if s_e is not None and abs(s_e) >= 0.3:
        insights.append(f"Your sleep and energy move {'together' if s_e > 0 else 'in opposite directions'} (r = {s_e}).")
    st_p = corr[1][3]
    if st_p is not None and abs(st_p) >= 0.3:
        insights.append(f"Stress and pain scores are {'positively' if st_p > 0 else 'negatively'} related (r = {st_p}).")
    return {"labels": labels, "correlation": corr, "weekly": weekly, "theme_heatmap": {"weeks": all_weeks, "rows": [{"theme": t, "counts": [heat[t].get(w, 0) for w in all_weeks]} for t in sorted(heat)]},
            "moods": [{"mood": k, "count": v} for k, v in moods.most_common()], "sources": [{"source": k, "count": v} for k, v in sources.most_common()],
            "observations": insights, "days_logged": len(trk),
            "note": "Correlations describe patterns in your own logs; they do not imply cause."}


# ---------------- Notifications ----------------
async def _build_notifications(user, prof) -> list[dict]:
    db, pid = get_db(), prof["_id"]
    items = []
    today = date.today()
    if not await db.tracker_entries.find_one({"profile_id": pid, "entry_date": today.isoformat()}):
        items.append({"key": f"tracker-{today}", "level": "info", "title": "Log today's check-in", "detail": "Your daily tracker has no entry for today.", "href": "/tracker"})
    for m in await db.medicines.find({"profile_id": pid, "active": True}).to_list(200):
        logged = {l["slot"] for l in await db.dose_logs.find({"profile_id": pid, "medicine_id": m["_id"], "log_date": today.isoformat(), "taken": True}).to_list(20)}
        pending = [s for s in (m.get("slots") or []) if s not in logged]
        if pending:
            items.append({"key": f"med-{m['_id']}-{today}", "level": "warn", "title": f"{m['name']}: dose pending", "detail": "Pending: " + ", ".join(pending), "href": "/medicines"})
    for a in await db.appointments.find({"profile_id": pid, "status": "scheduled"}).to_list(200):
        d = date.fromisoformat(a["appt_date"])
        if 0 <= (d - today).days <= 3:
            items.append({"key": f"appt-{a['_id']}", "level": "info", "title": f"Appointment with {a['doctor_name']}", "detail": f"{a['appt_date']} at {a['appt_time']}", "href": "/appointments"})
    for a in [x for x in await alerts_svc.evaluate(pid) if x["urgency"] != "routine"][:4]:
        items.append({"key": f"alert-{a['key']}", "level": "alert" if a["urgency"] == "urgent" else "warn", "title": a["title"], "detail": f"{a['detail']}. {a['guidance']}", "href": "/alerts"})
    for f in (await hr.compute_risk_flags(pid))[:3]:
        items.append({"key": f"flag-{f['title']}-{today}", "level": "warn" if f["level"] == "discuss" else "info", "title": f["title"], "detail": f["detail"], "href": "/insights"})
    return items


@router.get("/notifications")
async def notifications(user=Depends(current_user), prof=Depends(current_profile)):
    items = await _build_notifications(user, prof)
    read = {r["key"] async for r in get_db().notifications_read.find({"profile_id": prof["_id"]})}
    for i in items:
        i["read"] = i["key"] in read
    return {"items": items, "unread": sum(1 for i in items if not i["read"])}


class ReadIn(BaseModel):
    keys: list[str]


@router.post("/notifications/read")
async def mark_read(body: ReadIn, prof=Depends(current_profile)):
    db = get_db()
    for k in body.keys:
        if not await db.notifications_read.find_one({"profile_id": prof["_id"], "key": k}):
            await db.notifications_read.insert_one({"_id": new_id(), "profile_id": prof["_id"], "key": k})
    return {"ok": True}


# ---------------- Global search & export ----------------
@router.get("/search")
async def global_search(q: str = Query(min_length=2), prof=Depends(current_profile)):
    pid, ql = prof["_id"], q.lower()
    db = get_db()
    out = []
    for r in await db.story_entries.find({"profile_id": pid}).to_list(1000):
        if ql in r["text"].lower():
            out.append({"type": "Story", "title": r["text"][:90], "date": r["created_at"][:10], "href": "/story"})
    for r in await db.medicines.find({"profile_id": pid}).to_list(300):
        if ql in r["name"].lower():
            out.append({"type": "Medicine", "title": r["name"], "date": r.get("start_date", ""), "href": "/medicines"})
    for r in await db.reports.find({"profile_id": pid}).to_list(300):
        if ql in r["title"].lower() or any(ql in f["test"].lower() for f in r["fields"]):
            out.append({"type": "Report", "title": r["title"], "date": r["report_date"], "href": "/reports"})
    for r in await db.appointments.find({"profile_id": pid}).to_list(300):
        if ql in r["doctor_name"].lower() or ql in (r.get("hospital") or "").lower():
            out.append({"type": "Appointment", "title": r["doctor_name"], "date": r["appt_date"], "href": "/appointments"})
    hits, method = await rag.search(pid, q, 5)
    for c, s in hits:
        if s > 0.2:
            out.append({"type": f"Evidence ({c['source_type']})", "title": c["text"][:90], "date": c["timestamp"][:10], "href": "/insights", "similarity": round(s, 2)})
    return {"query": q, "retrieval": method, "results": out[:40]}


@router.get("/export")
async def export_all(user=Depends(current_user), prof=Depends(current_profile)):
    db, pid = get_db(), prof["_id"]
    data = {"exported_at": now_iso(), "profile": {"name": prof["name"], "relation": prof["relation"]}}
    for c in ["story_entries", "survey_responses", "tracker_entries", "vitals", "reports", "medicines", "dose_logs", "appointments", "goals", "opinions", "insights"]:
        data[c] = clean_many(await db[c].find({"profile_id": pid}).to_list(20000))
    return data
