"""Demo data seeder: a believable 45-day history so every chart, flag and insight is populated.
Texts avoid emergency phrases on purpose (the safety guard would, correctly, refuse to store them)."""
import random
from datetime import date, datetime, timedelta, timezone

from app.core.db import get_db
from app.core.util import new_id, now_iso
from app.services import rag


async def wipe_profile_data(pid: str):
    db = get_db()
    for c in ["story_entries", "survey_responses", "tracker_entries", "vitals", "reports", "medicines", "dose_logs", "appointments",
              "insights", "opinions", "goals"]:
        await db[c].delete_many({"profile_id": pid})
    await rag.delete_for_profile(pid)


async def seed_profile(user_id: str, pid: str, name: str = "Demo", days: int = 45, reset: bool = True) -> dict:
    db = get_db()
    if reset:
        await wipe_profile_data(pid)
    rng = random.Random(42)
    today = date.today()
    base = {"user_id": user_id, "profile_id": pid}

    # tracker
    for i in range(days, -1, -1):
        d = today - timedelta(days=i)
        bad = i < 14  # a rougher recent fortnight tells a story
        sleep = round(rng.uniform(5.0, 6.2) if bad else rng.uniform(6.6, 8.0), 1)
        stress = rng.randint(6, 9) if bad else rng.randint(2, 6)
        energy = rng.randint(2, 5) if bad else rng.randint(5, 8)
        pain = rng.randint(3, 8) if bad and i % 2 == 0 else rng.randint(0, 3)
        note = None
        if i in (12, 8, 3):
            note = "Felt a dull headache behind my eyes again, along with some dizziness when I stood up quickly."
        elif i in (10, 5):
            note = "Lower back pain and stiffness in the morning after sitting at the desk."
        elif i == 6:
            note = "Racing heartbeat and palpitations after climbing stairs, plus feeling anxious most days."
        eid = new_id()
        await db.tracker_entries.insert_one({**base, "_id": eid, "entry_date": d.isoformat(), "sleep_hours": sleep, "water_glasses": rng.randint(3, 9),
                                             "stress_level": stress, "energy_level": energy, "pain_level": pain, "steps": rng.randint(2500, 11000),
                                             "mood": rng.choice(["calm", "tired", "anxious", "happy", "calm", "focused"]), "notes": note, "updated_at": now_iso()})
        if note:
            await rag.add_evidence(user_id, pid, "tracker", note, {"source_id": eid})

    # stories
    stories = [
        (30, "I have been getting a throbbing headache most afternoons for the last two weeks, sometimes with light sensitivity."),
        (21, "Dizziness and a mild migraine again today. My sleep has been poor and work stress is high."),
        (14, "Joint pain in my knees when walking and back pain in the evening. Stiffness in the morning is getting worse."),
        (9, "Feeling anxious most days and having trouble sleeping due to racing thoughts. Irritability and stress at work."),
        (4, "Palpitations after climbing stairs and some chest tightness when I rush. It settles when I rest."),
        (2, "Headache again this morning, about 6 out of 10, worse after skipping breakfast."),
    ]
    for ago, text in stories:
        sid = new_id()
        ts = (datetime.now(timezone.utc) - timedelta(days=ago)).replace(microsecond=0).isoformat()
        await db.story_entries.insert_one({**base, "_id": sid, "text": text, "mood": None, "extracted_symptoms": rag.tag_themes(text),
                                           "timeline": rag.extract_timeline(text), "created_at": ts})
        n = await rag.add_evidence(user_id, pid, "story", text, {"source_id": sid})
        await db.evidence_chunks.update_many({"profile_id": pid, "metadata.source_id": sid}, {"$set": {"timestamp": ts}})

    # survey
    sid = new_id()
    mc = {"primary_concern": "Recurring headaches, dizziness and poor sleep with rising stress", "since_when": "about two months",
          "what_helps": "Rest in a dark room helps a little"}
    await db.survey_responses.insert_one({**base, "_id": sid, "about_you": {"age": "34", "gender": "Female", "occupation": "Software engineer", "activity_level": "Low"},
                                          "main_concern": mc, "care_context": {"conditions": "None known", "allergies": "Penicillin", "family_history": "Hypertension"}, "updated_at": now_iso()})
    await rag.add_evidence(user_id, pid, "survey", " ".join(mc.values()) + ". Also feeling anxious most days and trouble sleeping due to racing thoughts.", {"source_id": sid})

    # vitals
    for ago, w, sys_, dia, fs, ps in [(40, 71.0, 124, 80, 96, 128), (28, 71.8, 128, 82, 101, 138), (14, 72.6, 134, 86, 104, 146), (3, 73.1, 138, 88, 108, 152)]:
        await db.vitals.insert_one({**base, "_id": new_id(), "entry_date": (today - timedelta(days=ago)).isoformat(), "weight_kg": w, "height_cm": 165,
                                    "systolic": sys_, "diastolic": dia, "heart_rate": rng.randint(70, 92), "fasting_sugar": fs, "postmeal_sugar": ps,
                                    "spo2": 98, "temperature_c": 36.7, "created_at": now_iso()})

    # medicines
    meds = []
    for nme, dose, slots in [("Vitamin D3", "60,000 IU weekly", ["morning"]), ("Magnesium", "250 mg", ["night"]), ("Pantoprazole", "40 mg", ["morning"])]:
        mid = new_id()
        meds.append((mid, slots))
        await db.medicines.insert_one({**base, "_id": mid, "name": nme, "dose": dose, "frequency": "Daily", "slots": slots,
                                       "start_date": (today - timedelta(days=days)).isoformat(), "end_date": None, "active": True, "created_at": now_iso()})
    for i in range(14, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        for mid, slots in meds:
            for s in slots:
                if rng.random() < (0.55 if i < 7 else 0.9):
                    await db.dose_logs.insert_one({**base, "_id": new_id(), "medicine_id": mid, "slot": s, "log_date": d, "taken": True})

    # lab reports (3 over time)
    def f(t, v, u, r):
        from app.services.labs import is_out_of_range
        return {"test": t, "value": str(v), "unit": u, "reference_range": r, "out_of_range": is_out_of_range(v, r)}
    for ago, title, flds in [
        (75, "Routine blood panel", [f("Hemoglobin", 12.4, "g/dL", "12.0-15.5"), f("HbA1c", 5.5, "%", "4.0-5.6"), f("Total Cholesterol", 188, "mg/dL", "<200"), f("Vitamin D", 24, "ng/mL", "30-100"), f("TSH", 3.1, "mIU/L", "0.4-4.0")]),
        (38, "Follow-up panel", [f("Hemoglobin", 12.1, "g/dL", "12.0-15.5"), f("HbA1c", 5.7, "%", "4.0-5.6"), f("Total Cholesterol", 204, "mg/dL", "<200"), f("Vitamin D", 22, "ng/mL", "30-100"), f("TSH", 3.4, "mIU/L", "0.4-4.0")]),
        (6, "Annual health check", [f("Hemoglobin", 11.8, "g/dL", "12.0-15.5"), f("HbA1c", 5.9, "%", "4.0-5.6"), f("Total Cholesterol", 218, "mg/dL", "<200"), f("Vitamin D", 19, "ng/mL", "30-100"), f("TSH", 3.9, "mIU/L", "0.4-4.0")])]:
        rid = new_id()
        summ = "Several values sit just outside their reference ranges, including vitamin D and cholesterol, with a gentle upward drift across reports."
        await db.reports.insert_one({**base, "_id": rid, "title": title, "filename": None, "report_date": (today - timedelta(days=ago)).isoformat(), "method": "demo",
                                     "fields": flds, "summary": summ, "text_preview": "", "created_at": now_iso()})
    await rag.add_evidence(user_id, pid, "report", "Lab values for vitamin D and cholesterol are outside the reference range, with fatigue-related markers drifting.", {"source_id": "demo"})

    # appointments
    for ahead, doc, sp, hosp in [(3, "Dr. Anitha Krishnan", "Neurology", "Chennai General Hospital"), (11, "Dr. Karthik Raman", "General Medicine", "Chennai Care Hospital"), (-20, "Dr. Priya Iyer", "Orthopedics", "Chennai Medical Centre")]:
        await db.appointments.insert_one({**base, "_id": new_id(), "doctor_name": doc, "specialty": sp, "hospital": hosp, "appt_date": (today + timedelta(days=ahead)).isoformat(),
                                          "appt_time": "10:30", "notes": "Bring recent lab reports", "status": "scheduled" if ahead > 0 else "completed", "created_at": now_iso()})

    # opinions
    for nme, dep, text in [("Dr. Priya Iyer", "Orthopedics", "Mild degenerative changes are not expected. Recommend posture correction and physiotherapy. No medication needed now."),
                           ("Dr. Suresh Nair", "General Medicine", "Back stiffness is likely related to posture and low activity. Recommend exercise, and repeat vitamin D testing. Medication may be needed if pain persists.")]:
        oid = new_id()
        await db.opinions.insert_one({**base, "_id": oid, "specialist_name": nme, "department": dep, "opinion_text": text, "opinion_date": (today - timedelta(days=20)).isoformat(), "created_at": now_iso()})
        await rag.add_evidence(user_id, pid, "opinion", text, {"source_id": oid})

    # goals
    for t, tgt, unit, cur, metric in [("Sleep 7+ hours", 7, "h/night", 6.1, "sleep_hours"), ("Drink water", 8, "glasses/day", 5.5, "water_glasses"), ("Daily steps", 8000, "steps", 6200, "steps"), ("Weekly walks", 5, "walks", 3, None)]:
        await db.goals.insert_one({**base, "_id": new_id(), "title": t, "target": tgt, "unit": unit, "current": cur, "metric": metric, "due_date": None, "created_at": now_iso()})

    await rag.generate_insights(user_id, pid)
    return {"seeded": True, "days": days}
