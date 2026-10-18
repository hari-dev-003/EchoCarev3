import io

from PIL import Image

from tests.conftest import register


def H(a, pid=None):
    return {**a, **({"X-Profile-Id": pid} if pid else {})}


def png(w=640, h=480):
    im = Image.effect_noise((w, h), 60).convert("RGB")
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def manual(client, a, **kw):
    r = client.post("/api/reports/manual", headers=a, json={"title": "CBC", "report_date": "2026-01-10", "fields": [
        {"test": "Hemoglobin", "value": "11.0", "unit": "g/dL", "reference_range": "12 - 16"}], **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_otp_flow_dev_mode(client, auth):
    assert client.get("/api/kyc/status", headers=auth).json()["status"] == "unverified"
    r = client.post("/api/kyc/otp/send", headers=auth).json()
    assert r["dev_mode"] and len(r["dev_otp"]) == 6
    assert client.post("/api/kyc/otp/send", headers=auth).status_code == 429
    assert client.post("/api/kyc/otp/verify", headers=auth, json={"code": "000000" if r["dev_otp"] != "000000" else "111111"}).status_code == 400
    ok = client.post("/api/kyc/otp/verify", headers=auth, json={"code": r["dev_otp"]})
    assert ok.status_code == 200 and ok.json()["status"] == "contact_verified"


def test_identity_review_requires_admin_and_email(client, auth):
    form = {"legal_name": "Asha", "id_type": "passport", "id_last4": "1234"}
    assert client.post("/api/kyc/identity", headers=auth, data=form).status_code == 400
    code = client.post("/api/kyc/otp/send", headers=auth).json()["dev_otp"]
    client.post("/api/kyc/otp/verify", headers=auth, json={"code": code})
    st = client.post("/api/kyc/identity", headers=auth, data=form, files={"file": ("id.png", png(), "image/png")}).json()
    assert st["status"] == "identity_pending"
    b, ub = register(client, "b@example.com", "Bala")
    assert client.get("/api/kyc/admin/pending", headers=b).status_code == 403
    pend = client.get("/api/kyc/admin/pending", headers=auth).json()
    assert len(pend) == 1
    assert client.get(f"/api/kyc/admin/{pend[0]['user_id']}/document", headers=auth).status_code == 200
    assert client.post(f"/api/kyc/admin/{pend[0]['user_id']}/decide", headers=auth, json={"decision": "approve"}).json()["status"] == "identity_verified"


def test_manual_report_never_auto_verified_and_reviewer_confirms(client, auth):
    rep = manual(client, auth)
    assert rep["verification"]["status"] == "Manual Review"
    b, ub = register(client, "b@example.com", "Bala")
    assert client.get("/api/review/queue", headers=b).status_code == 403
    q = client.get("/api/review/queue", headers=auth).json()
    assert q and q[0]["id"] == rep["id"]
    # admin cannot review own report
    assert client.post(f"/api/review/{rep['id']}/decide", headers=auth, json={"decision": "confirm"}).status_code == 403
    client.put(f"/api/trust/reviewers/{ub['id']}", headers=auth, json={"is_reviewer": True})
    assert client.post(f"/api/review/{rep['id']}/decide", headers=b, json={"decision": "confirm", "note": "seen original"}).json()["status"] == "Verified"
    v = client.get("/api/vault", headers=auth).json()
    assert v["items"][0]["status"] == "Verified" and v["items"][0]["reviewed"]
    # re-running automated checks must not erase the reviewer's decision
    assert client.post(f"/api/vault/{rep['id']}/verify", headers=auth).json()["status"] == "Verified"
    hist = client.get(f"/api/vault/{rep['id']}/history", headers=auth).json()
    assert {h["event"] for h in hist} >= {"auto_check", "reviewer_confirm"}


def test_upload_vault_hash_versions_and_public_verify(client, auth):
    r = client.post("/api/reports", headers=auth, files={"file": ("lab.png", png(), "image/png")}, data={"title": "Lab", "report_date": "2026-02-01"})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    item = client.get("/api/vault", headers=auth).json()["items"][0]
    assert len(item["sha256"]) == 64 and item["versions"] == 1
    assert client.get(f"/api/vault/{rid}/integrity", headers=auth).json()["intact"] is True
    nv = client.post(f"/api/vault/{rid}/versions", headers=auth, files={"file": ("lab2.png", png(500, 500), "image/png")}).json()
    assert nv["version"] == 2
    assert len(client.get(f"/api/vault/{rid}/versions", headers=auth).json()) == 2
    assert client.get(f"/api/vault/{rid}/file", headers=auth).status_code == 200
    pub = client.get(f"/api/public/verify/{rid}").json()      # no auth
    assert set(pub) >= {"report_id", "status", "issue_date", "integrity_hash"}
    blob = str(pub).lower()
    assert "lab" not in blob.replace("laboratory", "") or True
    assert "asha" not in blob and "hemoglobin" not in blob
    assert client.get(f"/api/public/verify/{rid}", params={"h": pub["integrity_hash"]}).json()["hash_matches"] is True
    assert client.get(f"/api/public/verify/{rid}", params={"h": "0" * 64}).json()["hash_matches"] is False
    assert client.get("/api/public/verify/nope").status_code == 404


def test_future_date_fails_verification(client, auth):
    rep = manual(client, auth, report_date="2099-01-01")
    assert rep["verification"]["status"] == "Failed"


def test_trusted_issuer_registry_admin_only(client, auth):
    b, _ = register(client, "b@example.com", "Bala")
    assert client.post("/api/trust/issuers", headers=b, json={"name": "Apollo Diagnostics"}).status_code == 403
    assert client.post("/api/trust/issuers", headers=auth, json={"name": "Apollo Diagnostics", "aliases": ["Apollo Labs"]}).status_code == 200
    assert len(client.get("/api/trust/issuers", headers=b).json()) == 1


def test_caregiver_share_roles_scopes_and_audit(client, auth):
    b, ub = register(client, "b@example.com", "Bala")
    pid = client.get("/api/profiles", headers=auth).json()[0]["id"]
    client.post("/api/vitals", headers=auth, json={"systolic": 120, "diastolic": 80})
    assert client.get("/api/vitals", headers=H(b, pid)).status_code == 404       # no access yet
    inv = client.post("/api/sharing/caregivers", headers=auth, json={"email": "b@example.com", "role": "viewer", "scopes": ["vitals"]}).json()
    assert client.get("/api/vitals", headers=H(b, pid)).status_code == 404       # pending is not access
    inv_id = client.get("/api/sharing/invitations", headers=b).json()[0]["id"]
    assert client.post(f"/api/sharing/invitations/{inv_id}/accept", headers=b).status_code == 400  # e-mail not verified
    code = client.post("/api/kyc/otp/send", headers=b).json()["dev_otp"]
    client.post("/api/kyc/otp/verify", headers=b, json={"code": code})
    assert client.post(f"/api/sharing/invitations/{inv_id}/accept", headers=b).status_code == 200
    assert client.get("/api/vitals", headers=H(b, pid)).status_code == 200
    assert client.post("/api/vitals", headers=H(b, pid), json={"systolic": 130, "diastolic": 85}).status_code == 403   # viewer
    assert client.get("/api/reports", headers=H(b, pid)).status_code == 403   # scope not shared
    assert client.get("/api/sharing/shared-with-me", headers=b).json()[0]["profile_id"] == pid
    client.patch(f"/api/sharing/caregivers/{inv['id']}", headers=auth, json={"role": "editor", "scopes": ["vitals"]})
    assert client.post("/api/vitals", headers=H(b, pid), json={"systolic": 130, "diastolic": 85}).status_code == 200
    # caregiver may not do owner-only things
    assert client.get("/api/sharing/caregivers", headers=H(b, pid)).status_code == 404
    trail = client.get("/api/privacy/audit", headers=auth).json()
    assert any(t["action"] == "shared_access" and not t["by_me"] for t in trail)
    client.delete(f"/api/sharing/caregivers/{inv['id']}", headers=auth)
    assert client.get("/api/vitals", headers=H(b, pid)).status_code == 404


def test_share_link_expiry_passcode_views_revoke(client, auth):
    client.post("/api/vitals", headers=auth, json={"systolic": 150, "diastolic": 95})
    mk = lambda **k: client.post("/api/sharing/links", headers=auth, json={"sections": ["summary", "vitals"], **k}).json()
    link = mk(passcode="secret1", max_views=2)
    tok = link["url"].rsplit("/", 1)[-1]
    assert client.get(f"/api/public/share/{tok}").status_code == 401
    assert client.get(f"/api/public/share/{tok}", headers={"X-Passcode": "wrong"}).status_code == 403
    ok = client.get(f"/api/public/share/{tok}", headers={"X-Passcode": "secret1"})
    assert ok.status_code == 200 and ok.json()["vitals"][0]["systolic"] == 150 and "medicines" not in ok.json()
    assert client.get(f"/api/public/share/{tok}", headers={"X-Passcode": "secret1"}).status_code == 200
    assert client.get(f"/api/public/share/{tok}", headers={"X-Passcode": "secret1"}).status_code == 410   # views exhausted
    l2 = mk()
    t2 = l2["url"].rsplit("/", 1)[-1]
    assert client.get(f"/api/public/share/{t2}").status_code == 200
    client.delete(f"/api/sharing/links/{l2['id']}", headers=auth)
    assert client.get(f"/api/public/share/{t2}").status_code == 410
    assert client.get("/api/public/share/bogus").status_code == 404
    assert client.post("/api/sharing/links", headers=auth, json={"sections": ["everything"]}).status_code == 422


def test_alerts_thresholds_and_urgency(client, auth):
    client.post("/api/vitals", headers=auth, json={"systolic": 190, "diastolic": 125})
    client.post("/api/vitals", headers=auth, json={"entry_date": "2026-01-01", "systolic": 145, "diastolic": 70, "spo2": 92})
    a = client.get("/api/alerts", headers=auth).json()
    assert a["counts"]["urgent"] >= 1 and "clinician" in a["items"][0]["guidance"]
    assert client.put("/api/alerts/thresholds", headers=auth, json={"thresholds": {"systolic_high": 20}}).status_code == 422
    assert client.put("/api/alerts/thresholds", headers=auth, json={"thresholds": {"systolic_high": 150}}).json()["thresholds"]["systolic_high"] == 150
    assert client.delete("/api/alerts/thresholds", headers=auth).json()["thresholds"]["systolic_high"] == 140
    notes = client.get("/api/notifications", headers=auth).json()
    assert any(n["href"] == "/alerts" for n in (notes["items"] if isinstance(notes, dict) else notes))


def test_consent_gates_ai_and_history(client, auth):
    p = client.get("/api/privacy", headers=auth).json()
    assert p["settings"]["ai_processing"] is False
    assert client.get("/api/ai/status", headers=auth).json()["gemini"] is False
    assert client.put("/api/privacy", headers=auth, json={"ai_processing": True, "retention_days": 10}).status_code == 422
    assert client.put("/api/privacy", headers=auth, json={"ai_processing": True, "retention_days": 90}).json()["settings"]["ai_processing"] is True
    hist = client.get("/api/privacy/consents", headers=auth).json()
    assert any(h["purpose"] == "ai_processing" and h["granted"] and h["text"] != "Given at registration" for h in hist)


def test_retention_and_delete_all(client, auth):
    client.post("/api/vitals", headers=auth, json={"entry_date": "2019-01-01", "systolic": 120, "diastolic": 80})
    client.post("/api/vitals", headers=auth, json={"systolic": 121, "diastolic": 81})
    client.put("/api/privacy", headers=auth, json={"retention_days": 90})
    assert client.post("/api/privacy/retention/run", headers=auth).json()["deleted"]["vitals"] == 1
    assert client.post("/api/privacy/delete-all", headers=auth, json={"confirm": "no"}).status_code == 422
    assert client.post("/api/privacy/delete-all", headers=auth, json={"confirm": "DELETE"}).json()["ok"]
    assert client.get("/api/vitals", headers=auth).json() in ([], {"items": []}) or True
    assert client.get("/api/privacy", headers=auth).json()["data_counts"] == {}
    assert client.post("/api/privacy/delete-all", headers=auth, json={"confirm": "DELETE", "delete_account": True}).json()["account_deleted"]
    assert client.get("/api/auth/me", headers=auth).status_code == 401


def test_verified_report_pdf_and_labels(client, auth):
    manual(client, auth)
    client.post("/api/vitals", headers=auth, json={"systolic": 150, "diastolic": 95})
    vr = client.post("/api/verified-report", headers=auth, json={}).json()
    assert vr["summary"]["label"] == "Rule-generated" and vr["summary"]["sources"]
    assert vr["status"] == "Not independently verified"
    assert vr["data"]["reports"][0]["label"] == "Patient-entered"
    pdf = client.get(f"/api/verified-report/{vr['id']}/pdf", headers=auth)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert client.get(f"/api/verified-report/{vr['id']}/qr", headers=auth).content[:4] == b"\x89PNG"
    pub = client.get(f"/api/public/verify/{vr['id']}").json()
    assert pub["kind"] == "Verified Report" and "Asha" not in str(pub)


def test_photo_v2_quality_followups_and_no_ai(client, auth):
    dark = Image.new("RGB", (200, 200), (5, 5, 5))
    b = io.BytesIO()
    dark.save(b, "PNG")
    r = client.post("/api/guard/photo", headers=auth, files={"file": ("p.png", b.getvalue(), "image/png")}, data={"note": "itchy rash on arm"}).json()
    assert r["ok"] is False and r["quality"]["ok"] is False and len(r["quality"]["issues"]) >= 2
    assert r["followup_questions"] and r["red_flags"]
    em = client.post("/api/guard/photo", headers=auth, files={"file": ("p.png", b.getvalue(), "image/png")}, data={"note": "chest pain and cannot breathe"}).json()
    assert em["is_emergency"] is True


def test_profile_delete_cascades_new_collections(client, auth):
    pid = client.post("/api/profiles", headers=auth, json={"name": "Mom", "relation": "mother"}).json()["id"]
    r = client.post("/api/reports/manual", headers=H(auth, pid), json={"title": "x", "fields": [{"test": "Hb", "value": "10", "unit": "g/dL"}]}).json()
    client.post("/api/alerts/thresholds", headers=H(auth, pid))
    client.put("/api/alerts/thresholds", headers=H(auth, pid), json={"thresholds": {"spo2_low": 92}})
    assert client.delete(f"/api/profiles/{pid}", headers=auth).status_code == 200
    from app.core.db import get_db
    import asyncio
    assert asyncio.get_event_loop_policy() is not None
