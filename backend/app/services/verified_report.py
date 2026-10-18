"""Verified Report: one document in which every statement is labelled by where it came from.

Provenance labels: Verified identity · Verified document · Clinician-reviewed · Patient-entered · Extracted (AI/OCR) · AI-generated.
"""
import hashlib
import io
import json
from datetime import date
from xml.sax.saxutils import escape

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import get_settings
from app.core.db import get_db
from app.core.util import new_id, now_iso
from app.services import health_rules as hr, labs, llm, alerts as al
from app.services.report_pdf import BLUE, LINE, SLATE, _fonts, _table

LABELS = {"identity": "Verified identity", "document": "Verified document details", "reviewed": "Clinician/reviewer-reviewed",
          "patient": "Patient-entered", "extracted": "Extracted by AI/OCR", "ai": "AI-generated", "rule": "Rule-generated"}


async def collect(prof: dict, owner: dict) -> dict:
    db, pid = get_db(), prof["_id"]
    kyc = (owner.get("kyc") or {}).get("status", "unverified")
    ident = {"label": LABELS["identity"] if kyc == "identity_verified" else LABELS["patient"],
             "name": prof["name"], "relation": prof.get("relation"), "dob": prof.get("dob"), "gender": prof.get("gender"),
             "account_status": {"identity_verified": "Identity reviewed by an administrator", "contact_verified": "E-mail confirmed only (not identity)"}.get(kyc, "Not verified")}
    reports = []
    for r in sorted(await db.reports.find({"profile_id": pid}).to_list(300), key=lambda r: r["report_date"], reverse=True):
        v = r.get("verification") or {}
        status = v.get("status", "Unverified")
        reports.append({"id": r["_id"], "title": r["title"], "report_date": r["report_date"], "status": status,
                        "label": LABELS["reviewed"] if v.get("reviewer") else LABELS["document"] if status == "Verified" else
                        LABELS["patient"] if r.get("method") == "manual" else LABELS["extracted"],
                        "issuer": (r.get("extracted") or {}).get("issuer_name"), "sha256": r.get("file_sha256"),
                        "reviewer": (v.get("reviewer") or {}).get("name"), "fields": r["fields"][:30]})
    vit = sorted(await db.vitals.find({"profile_id": pid}).to_list(500), key=lambda r: r["entry_date"])[-5:]
    meds = await db.medicines.find({"profile_id": pid, "active": True}).to_list(100)
    sv = await db.survey_responses.find_one({"profile_id": pid})
    ins = sorted(await db.insights.find({"profile_id": pid}).to_list(50), key=lambda i: -i["confidence"])[:5]
    taken, expected = await hr.adherence(pid)
    alerts = await al.evaluate(pid)
    return {"identity": ident, "reports": reports,
            "vitals": {"label": LABELS["patient"], "rows": [{k: r.get(k) for k in ("entry_date", "weight_kg", "systolic", "diastolic", "heart_rate", "fasting_sugar", "postmeal_sugar", "spo2")} for r in vit]},
            "medicines": {"label": LABELS["patient"], "rows": [{k: m.get(k) for k in ("name", "dose", "frequency", "start_date")} for m in meds],
                          "adherence_7d": f"{taken}/{expected}" if expected else None},
            "concern": {"label": LABELS["patient"], "text": ((sv or {}).get("main_concern") or {}).get("primary_concern") or ""},
            "alerts": {"label": LABELS["rule"], "rows": [{k: a[k] for k in ("title", "detail", "urgency", "date")} for a in alerts[:8]]},
            "insights": {"label": LABELS["ai"], "rows": [{"theme": i["theme"], "text": i["text"], "confidence": i["confidence"], "label": i["confidence_label"], "basis": i["evidence_summary"], "generated_by": i["generated_by"]} for i in ins]}}


async def summarise(data: dict, lang: str = "en") -> dict:
    """AI summary (Gemini, consent-gated) with its sources, else a deterministic summary labelled rule-generated."""
    srcs = []
    for r in data["reports"][:5]:
        srcs.append(f"Report '{r['title']}' ({r['report_date']}, {r['status']})")
    for i in data["insights"]["rows"][:3]:
        srcs.append(f"EchoCare insight '{i['theme']}' ({i['basis']})")
    if data["vitals"]["rows"]:
        srcs.append("Patient-entered vitals")
    abn = [f"{f['test']} {f['value']} {f.get('unit') or ''}" for r in data["reports"][:3] for f in r["fields"] if f.get("out_of_range")][:6]
    facts = {"concern": data["concern"]["text"], "alerts": [a["title"] for a in data["alerts"]["rows"][:5]], "out_of_range_labs": abn,
             "medicines": [m["name"] for m in data["medicines"]["rows"]][:8], "themes": [i["theme"] for i in data["insights"]["rows"]]}
    prompt = ("Write a 4-sentence plain-language summary for a clinician from these patient-recorded facts. Do not diagnose, do not suggest "
              "a disease or treatment, do not add facts. Mention that values are patient-recorded or extracted. Facts: " + json.dumps(facts))
    res = await llm.generate(prompt, lang=lang)
    if res["ok"] and res["text"]:
        return {"text": res["text"].strip(), "label": LABELS["ai"], "provider": res["provider"], "sources": srcs}
    parts = []
    if facts["concern"]:
        parts.append(f"The patient's main concern is recorded as: {facts['concern'][:200]}.")
    if facts["themes"]:
        parts.append("Recurring themes in their own records: " + ", ".join(facts["themes"]) + ".")
    if abn:
        parts.append("Lab values outside the printed reference range: " + "; ".join(abn) + ".")
    if facts["alerts"]:
        parts.append("Recent alerts from the patient's own thresholds: " + "; ".join(facts["alerts"]) + ".")
    if facts["medicines"]:
        parts.append("Current medicines recorded: " + ", ".join(facts["medicines"]) + ".")
    return {"text": " ".join(parts) or "Not enough recorded information for a summary yet.", "label": LABELS["rule"], "provider": "rules",
            "sources": srcs, "note": res.get("reason")}


def content_hash(data: dict, summary: dict) -> str:
    return hashlib.sha256(json.dumps({"d": data, "s": summary["text"]}, sort_keys=True, default=str).encode()).hexdigest()


async def create(prof: dict, owner: dict, user: dict, lang: str = "en") -> dict:
    data = await collect(prof, owner)
    summary = await summarise(data, lang)
    h = content_hash(data, summary)
    best = "Verified" if any(r["status"] == "Verified" for r in data["reports"]) else "Not independently verified"
    rec = {"_id": new_id(), "profile_id": prof["_id"], "user_id": user["_id"], "content_sha256": h, "summary": summary, "data": data,
           "status": best, "lang": lang, "generated_at": now_iso()}
    await get_db().verified_reports.insert_one(rec)
    return rec


def build_pdf(rec: dict, profile_name: str) -> bytes:
    bf, bb = _fonts()
    base = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=base["Normal"], fontName=bf, fontSize=9.2, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=7.8, textColor=SLATE, leading=11)
    h1 = ParagraphStyle("h1", parent=body, fontName=bb, fontSize=20, textColor=colors.HexColor("#0F172A"))
    h2 = ParagraphStyle("h2", parent=body, fontName=bb, fontSize=11.5, textColor=BLUE, spaceBefore=11, spaceAfter=3)
    cell = ParagraphStyle("c", parent=body, fontSize=8.3, leading=10.5)
    P = lambda t, s=body: Paragraph(escape(str(t)), s)
    C = lambda t: Paragraph(escape("" if t is None else str(t)), cell)
    d = rec["data"]
    url = f"{get_settings().FRONTEND_URL.rstrip('/')}/verify/{rec['_id']}"
    qb = io.BytesIO()
    qrcode.make(url).save(qb, format="PNG")
    qb.seek(0)
    head = Table([[[Paragraph("Verified Health Report", h1), P(f"{profile_name} · generated {rec['generated_at'][:10]} · EchoCare", small),
                    P(f"Report ID {rec['_id'][:8].upper()} · integrity hash {rec['content_sha256'][:24]}…", small),
                    P("Scan the QR code to check this report's status. The page shows no patient information.", small)],
                   Image(qb, 26 * mm, 26 * mm)]], colWidths=[140 * mm, 30 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story = [head, Spacer(1, 4),
             P("Every section carries a label showing where its information came from. Only items labelled 'Verified' were confirmed by a "
               "human reviewer. AI-generated and extracted content may contain errors. This is not a diagnosis.", small)]
    story += [Paragraph("Identity", h2), P(f"[{d['identity']['label']}] {d['identity']['name']} ({d['identity'].get('relation') or 'self'}). Account: {d['identity']['account_status']}.")]
    story += [Paragraph(f"AI summary  [{rec['summary']['label']}]", h2), P(rec["summary"]["text"])]
    if rec["summary"].get("sources"):
        story.append(P("Sources: " + "; ".join(rec["summary"]["sources"]), small))
    if d["reports"]:
        story.append(Paragraph("Reports and verification status", h2))
        story.append(_table([["Report", "Date", "Status", "Provenance", "Issuer", "File hash"]] +
                            [[C(r["title"]), C(r["report_date"]), C(r["status"]), C(r["label"]), C(r["issuer"]), C((r["sha256"] or "")[:12])] for r in d["reports"]],
                            [42 * mm, 20 * mm, 26 * mm, 36 * mm, 28 * mm, 18 * mm]))
        out = [[C(r["title"]), C(f["test"]), C(f"{f['value']} {f.get('unit') or ''}"), C(f.get("reference_range")), C("outside" if f.get("out_of_range") else "within"), C(r["label"])]
               for r in d["reports"][:4] for f in r["fields"] if f.get("out_of_range")][:20]
        if out:
            story += [Paragraph("Lab values outside range (extracted values; check the original)", h2),
                      _table([["Report", "Test", "Value", "Reference", "Flag", "Provenance"]] + out, [38 * mm, 32 * mm, 24 * mm, 26 * mm, 16 * mm, 34 * mm])]
    if d["vitals"]["rows"]:
        story += [Paragraph(f"Recent vitals  [{d['vitals']['label']}]", h2),
                  _table([["Date", "Weight", "BP", "HR", "Fasting", "Post-meal", "SpO2"]] + [[C(r["entry_date"]), C(r.get("weight_kg")), C(f"{r['systolic']}/{r['diastolic']}" if r.get("systolic") else ""), C(r.get("heart_rate")), C(r.get("fasting_sugar")), C(r.get("postmeal_sugar")), C(r.get("spo2"))] for r in d["vitals"]["rows"]])]
    if d["medicines"]["rows"]:
        story += [Paragraph(f"Medicines  [{d['medicines']['label']}]", h2),
                  _table([["Medicine", "Dose", "Frequency", "Since"]] + [[C(m["name"]), C(m.get("dose")), C(m.get("frequency")), C(m.get("start_date"))] for m in d["medicines"]["rows"]])]
        if d["medicines"]["adherence_7d"]:
            story.append(P(f"7-day dose log: {d['medicines']['adherence_7d']}", small))
    if d["alerts"]["rows"]:
        story += [Paragraph(f"Alerts from the patient's own thresholds  [{d['alerts']['label']}]", h2),
                  _table([["Alert", "Detail", "Urgency", "Date"]] + [[C(a["title"]), C(a["detail"]), C(a["urgency"]), C(a["date"])] for a in d["alerts"]["rows"]])]
    if d["insights"]["rows"]:
        story += [Paragraph(f"Pattern insights  [{d['insights']['label']}]", h2),
                  _table([["Theme", "Confidence", "Basis"]] + [[C(i["theme"]), C(f"{i['confidence']:.0%} ({i['label']})"), C(i["basis"])] for i in d["insights"]["rows"]])]
    buf = io.BytesIO()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(bf, 7.5)
        canvas.setFillColor(SLATE)
        canvas.drawString(18 * mm, 9 * mm, f"EchoCare Verified Report {rec['_id'][:8].upper()} · not a diagnosis")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                      title="EchoCare Verified Report", author="EchoCare").build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
