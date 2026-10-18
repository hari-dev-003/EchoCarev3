from datetime import date

from tests.conftest import register


def H(auth, pid=None):
    return {**auth, **({"X-Profile-Id": pid} if pid else {})}


def test_health_and_auth_flow(client):
    assert client.get("/api/health").json()["status"] == "ok"
    h, user = register(client)
    assert user["is_admin"] is True  # first user
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrongpass1"}).status_code == 401
    assert client.get("/api/auth/me", headers=h).json()["email"] == "a@example.com"
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/register", json={"name": "x", "email": "a@example.com", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/register", json={"name": "x", "email": "b@example.com", "password": "short"}).status_code == 422


def test_second_user_not_admin_and_blocked(client):
    register(client)
    h2, u2 = register(client, "b@example.com", "Bala")
    assert u2["is_admin"] is False
    assert client.get("/api/admin/overview", headers=h2).status_code == 403


def test_story_emergency_not_stored(client, auth):
    r = client.post("/api/story", json={"text": "I have severe chest pain right now"}, headers=auth).json()
    assert r["is_emergency"] is True and r["resources"]
    assert client.get("/api/story", headers=auth).json() == []


def test_story_to_evidence_and_chroma_search(client, auth):
    client.post("/api/story", json={"text": "Throbbing migraine with dizziness for two weeks."}, headers=auth)
    r = client.post("/api/evidence/search", json={"query": "migraine"}, headers=auth).json()
    assert r["results"] and "chromadb" in r["method"]
    stats = client.get("/api/evidence/stats", headers=auth).json()
    assert stats["total"] >= 1 and stats["indexed"] == stats["total"]


def test_insight_gate_needs_two_sources(client, auth):
    client.post("/api/story", json={"text": "Bad migraine again today."}, headers=auth)
    client.post("/api/story", json={"text": "Dizziness and a headache this morning."}, headers=auth)
    assert client.post("/api/insights/generate", headers=auth).json()["insights"] == []  # one source type only
    client.put("/api/survey", json={"main_concern": {"primary": "recurring headache and migraine"}}, headers=auth)
    ins = client.post("/api/insights/generate", headers=auth).json()["insights"]
    neuro = [i for i in ins if i["theme"] == "Neurology"]
    assert neuro and 0 < neuro[0]["confidence"] <= 1 and neuro[0]["confidence_breakdown"]["retrieval"]
    assert "unavailable" in neuro[0]["generated_by"]  # honest: no Gemini key -> no fabricated text


def test_profile_isolation_and_cascade(client, auth):
    fam = client.post("/api/profiles", json={"name": "Mum", "relation": "mother"}, headers=auth).json()
    client.post("/api/story", json={"text": "Knee pain when walking."}, headers=auth)
    assert client.get("/api/story", headers=H(auth, fam["id"])).json() == []
    client.post("/api/story", json={"text": "Joint pain and stiffness in the morning."}, headers=H(auth, fam["id"]))
    assert len(client.get("/api/story", headers=H(auth, fam["id"])).json()) == 1
    assert len(client.get("/api/story", headers=auth).json()) == 1
    # another user cannot use this profile id
    h2, _ = register(client, "z@example.com", "Zed")
    assert client.get("/api/story", headers=H(h2, fam["id"])).status_code == 404
    assert client.delete(f"/api/profiles/{fam['id']}", headers=auth).status_code == 200
    assert client.get("/api/story", headers=H(auth, fam["id"])).status_code == 404


def test_cannot_delete_self_profile(client, auth):
    me = client.get("/api/profiles", headers=auth).json()[0]
    assert client.delete(f"/api/profiles/{me['id']}", headers=auth).status_code == 400


def test_vitals_validation_and_classification(client, auth):
    assert client.post("/api/vitals", json={"systolic": 5}, headers=auth).status_code == 422
    r = client.post("/api/vitals", json={"weight_kg": 70, "height_cm": 170, "systolic": 150, "diastolic": 95, "fasting_sugar": 130}, headers=auth).json()
    assert r["bmi"] == 24.2 and r["bp_cat"][1] == "alert" and r["fasting_cat"][1] == "alert"
    flags = client.get("/api/risk-flags", headers=auth).json()
    assert any("Blood pressure" in f["title"] for f in flags)


def test_tracker_upsert(client, auth):
    d = date.today().isoformat()
    client.post("/api/tracker", json={"entry_date": d, "sleep_hours": 5, "stress_level": 9}, headers=auth)
    client.post("/api/tracker", json={"entry_date": d, "sleep_hours": 8, "stress_level": 2}, headers=auth)
    rows = client.get("/api/tracker", headers=auth).json()
    assert len(rows) == 1 and rows[0]["sleep_hours"] == 8
    assert client.post("/api/tracker", json={"stress_level": 99}, headers=auth).status_code == 422


def test_manual_report_labs_series(client, auth):
    for dt, hb in (("2026-01-01", 13.0), ("2026-03-01", 11.0)):
        client.post("/api/reports/manual", json={"title": "CBC", "report_date": dt, "fields": [{"test": "Hemoglobin", "value": str(hb), "unit": "g/dL", "reference_range": "12-15.5"}]}, headers=auth)
    s = client.get("/api/labs/series", headers=auth).json()
    pts = s["series"]["hemoglobin"]
    assert [p["value"] for p in pts] == [13.0, 11.0] and s["alerts"][0]["direction"] == "low" and s["alerts"][0]["trend"] == "falling"


def test_report_upload_without_ai_is_honest(client, auth):
    r = client.post("/api/reports", files={"file": ("x.png", b"not-an-image", "image/png")}, headers=auth)
    assert r.status_code == 200 and r.json()["method"] in ("ocr", "unreadable") and r.json()["fields"] == []
    assert client.post("/api/reports", files={"file": ("x.exe", b"1", "application/octet-stream")}, headers=auth).status_code == 415


def test_medicines_and_adherence(client, auth):
    m = client.post("/api/medicines", json={"name": "Vit D", "slots": ["morning", "night"]}, headers=auth).json()
    client.post("/api/medicines/dose", json={"medicine_id": m["id"], "slot": "morning"}, headers=auth)
    a = client.get("/api/medicines/adherence", headers=auth).json()
    assert a["expected"] == 2 and a["taken"] == 1 and a["percent"] == 50


def test_appointments_ics(client, auth):
    a = client.post("/api/appointments", json={"doctor_name": "Dr X", "appt_date": "2026-12-01", "appt_time": "09:30"}, headers=auth).json()
    ics = client.get(f"/api/appointments/{a['id']}/ics", headers=auth)
    assert "BEGIN:VEVENT" in ics.text and "20261201T093000" in ics.text


def test_agent_followup_then_ai_not_configured(client, auth):
    r1 = client.post("/api/chat", json={"message": "I have a headache"}, headers=auth).json()
    assert r1["kind"] == "followup" and "safety_check" in r1["tools_used"]
    r2 = client.post("/api/chat", json={"message": "for 3 days, about 6/10, worse in the morning"}, headers=auth).json()
    assert "rag_search" in r2["tools_used"] and "gemini_generate" not in r2["tools_used"] and "isn't configured" in r2["content"]


def test_agent_emergency(client, auth):
    r = client.post("/api/chat", json={"message": "I want to die"}, headers=auth).json()
    assert r["is_emergency"] and r["tools_used"] == ["safety_check"]


def test_doctors_directory(client, auth):
    meta = client.get("/api/doctors/meta").json()
    assert meta["source"] == "demo" and len(meta["districts"]) == 10 and "Neurology" in meta["specialties"]
    r = client.get("/api/doctors", params={"district": "Madurai", "specialty": "Cardiology"}).json()
    assert r["count"] >= 1 and all(d["district"] == "Madurai" for d in r["items"]) and r["items"][0]["navigate_url"].startswith("https://www.google.com/maps")
    near = client.get("/api/doctors", params={"lat": 13.08, "lon": 80.27}).json()["items"]
    assert near[0]["distance_km"] is not None


def test_directory_import_admin(client, auth):
    csv = b"name,specialty,district,hospital,rating\nDr. T,cardiologist,Chennai,Test Hosp,4.5\n,Neurology,Chennai,X,4\n"
    r = client.post("/api/admin/doctors/import", files={"file": ("d.csv", csv, "text/csv")}, headers=auth).json()
    assert r["imported"] == 1 and len(r["errors"]) == 1
    meta = client.get("/api/doctors/meta").json()
    assert meta["source"] == "imported" and meta["total"] == 1
    assert client.get("/api/doctors", params={"specialty": "Cardiology"}).json()["items"][0]["specialty"] == "Cardiology"


def test_emergency_card_public(client, auth):
    client.put("/api/emergency/card", json={"blood_group": "O+", "allergies": "Penicillin"}, headers=auth)
    card = client.get("/api/emergency/card", headers=auth).json()
    pub = client.get(f"/api/public/emergency/{card['token']}").json()
    assert pub["blood_group"] == "O+" and "id" not in pub and "user_id" not in pub
    assert client.get("/api/emergency/qr", headers=auth).content[:4] == b"\x89PNG"
    client.put("/api/emergency/card", json={"public_enabled": False}, headers=auth)
    assert client.get(f"/api/public/emergency/{card['token']}").status_code == 404
    assert client.get("/api/public/emergency/nope").status_code == 404


def test_demo_seed_dashboard_analytics_pdf(client, auth):
    assert client.post("/api/demo/seed", headers=auth).json()["seeded"]
    d = client.get("/api/dashboard", headers=auth).json()
    assert d["counts"]["evidence"] > 10 and d["flag_count"] >= 3 and 0 <= d["score"]["score"] <= 100 and d["tracker"]
    a = client.get("/api/analytics", headers=auth).json()
    assert len(a["correlation"]) == 6 and a["weekly"] and a["theme_heatmap"]["rows"]
    ins = client.post("/api/insights/generate", headers=auth).json()["insights"]
    assert len(ins) >= 3
    pdf = client.post("/api/consult/pdf", json={}, headers=auth)
    assert pdf.content[:5] == b"%PDF-" and len(pdf.content) > 4000
    n = client.get("/api/notifications", headers=auth).json()
    assert n["items"]
    client.post("/api/notifications/read", json={"keys": [n["items"][0]["key"]]}, headers=auth)
    assert client.get("/api/notifications", headers=auth).json()["unread"] == n["unread"] - 1
    assert client.get("/api/timeline", headers=auth).json()
    s = client.get("/api/search", params={"q": "headache"}, headers=auth).json()
    assert s["results"]
    assert client.get("/api/export", headers=auth).json()["story_entries"]
    # reindex rebuilds chroma from Mongo
    r = client.post("/api/admin/reindex", headers=auth).json()
    assert r["chunks_indexed"] == r["chunks_total"] > 0


def test_learn_and_quiz(client, auth):
    L = client.get("/api/learn").json()
    assert len(L["flashcards"]) >= 15 and L["decks"] and "answer" not in L["quiz"][0]
    res = client.post("/api/learn/quiz", json={"answers": {"q1": 2, "q2": 1}}, headers=auth).json()
    assert res["score"] == 2 and res["total"] == 5
    client.put("/api/learn/flashcard-progress", json={"known": ["fc1"]}, headers=auth)
    assert client.get("/api/learn/flashcard-progress", headers=auth).json()["known"] == ["fc1"]


def test_opinions_compare(client, auth):
    r = client.post("/api/opinions/compare", json={"a": "No surgery needed now", "b": "Surgery needed soon"}, headers=auth).json()
    assert r["a"] and r["b"] and "similarity" in r["signals"]


def test_department_endpoint_and_emergency(client, auth):
    assert client.post("/api/guard/department", json={"text": "skin rash and itching"}, headers=auth).json()["top_department"] == "Dermatology"
    assert client.post("/api/guard/department", json={"text": "chest pain"}, headers=auth).json()["is_emergency"]


def test_admin_overview_and_system(client, auth):
    assert client.get("/api/admin/overview", headers=auth).json()["counts"]["users"] == 1
    sysinfo = client.get("/api/admin/system", headers=auth).json()
    assert sysinfo["database"]["ok"] and sysinfo["gemini"] is False
    assert client.get("/api/admin/audit", headers=auth).json()
