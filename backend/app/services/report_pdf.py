"""One-click PDF consultation report (reportlab). Patient-recorded data organised for a clinician; never a diagnosis."""
import io
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.db import get_db
from app.services import health_rules as hr
from app.services import labs

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
BLUE, SLATE, LINE = colors.HexColor("#2563EB"), colors.HexColor("#64748B"), colors.HexColor("#E2E8F0")

SECTIONS = {
    "survey": "Survey summary", "story": "Recent story entries", "tracker": "30-day tracker averages",
    "vitals": "Vitals (BMI, BP, sugar)", "labs": "Lab values outside range", "medicines": "Current medicines",
    "insights": "AI insights (with confidence)", "flags": "Risk flags to discuss", "guard": "Diagnostic Guard",
    "appointments": "Upcoming appointments", "goals": "Health goals",
}


def _fonts():
    try:
        pdfmetrics.registerFont(TTFont("DV", str(FONTS / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DV-B", str(FONTS / "DejaVuSans-Bold.ttf")))
        return "DV", "DV-B"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def _table(rows, widths=None):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


async def build_pdf(profile: dict, include: dict[str, bool] | None = None) -> bytes:
    db = get_db()
    pid = profile["_id"]
    include = include or {k: True for k in SECTIONS}
    bf, bb = _fonts()
    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["Normal"], fontName=bf, fontSize=9.2, leading=13)
    small = ParagraphStyle("small", parent=body, fontSize=7.8, textColor=SLATE, leading=11)
    h1 = ParagraphStyle("h1", parent=body, fontName=bb, fontSize=20, textColor=colors.HexColor("#0F172A"), spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=body, fontName=bb, fontSize=12, textColor=BLUE, spaceBefore=12, spaceAfter=5)
    cell = ParagraphStyle("cell", parent=body, fontSize=8.5, leading=11)
    P = lambda t, s=body: Paragraph(escape(str(t)), s)
    C = lambda t: Paragraph(escape(str(t)), cell)
    story = [Paragraph("Consultation Preparation Summary", h1),
             P(f"Patient: {profile['name']}   ·   Generated {date.today().strftime('%d %b %Y')}   ·   EchoCare", small), Spacer(1, 4),
             P("This document organises information the patient recorded themselves so it can be discussed with a licensed "
               "clinician. It is not a diagnosis and does not replace medical advice.", small)]

    async def section(key, title, fn):
        if include.get(key):
            story.append(Paragraph(title, h2))
            await fn()

    async def s_survey():
        sv = await db.survey_responses.find_one({"profile_id": pid})
        if not sv:
            return story.append(P("No survey on file."))
        rows = [["Field", "Answer"]]
        for grp in ("about_you", "main_concern", "care_context"):
            rows += [[C(k.replace("_", " ").title()), C(v)] for k, v in (sv.get(grp) or {}).items() if v not in ("", None)]
        story.append(_table(rows, [50 * mm, 120 * mm]))

    async def s_story():
        es = sorted(await db.story_entries.find({"profile_id": pid}).to_list(500), key=lambda e: e["created_at"], reverse=True)[:5]
        if not es:
            return story.append(P("No story entries."))
        story.append(_table([["Date", "What the patient reported", "Tagged areas"]] +
                            [[C(e["created_at"][:10]), C(e["text"]), C(", ".join(e.get("extracted_symptoms", [])))] for e in es],
                            [24 * mm, 110 * mm, 36 * mm]))

    async def s_tracker():
        rows = await db.tracker_entries.find({"profile_id": pid, "entry_date": {"$gte": (date.today() - timedelta(days=30)).isoformat()}}).to_list(100)
        if not rows:
            return story.append(P("No tracker data in the last 30 days."))
        avg = lambda k: (lambda v: f"{sum(v) / len(v):.1f}" if v else "n/a")([r[k] for r in rows if r.get(k) is not None])
        story.append(_table([["Sleep (h)", "Water", "Stress /10", "Energy /10", "Pain /10", "Days logged"],
                             [avg("sleep_hours"), avg("water_glasses"), avg("stress_level"), avg("energy_level"), avg("pain_level"), len(rows)]]))

    async def s_vitals():
        v = sorted(await db.vitals.find({"profile_id": pid}).to_list(500), key=lambda r: r["entry_date"])
        if not v:
            return story.append(P("No vitals recorded."))
        rows = [["Date", "Weight", "BMI", "BP", "Fasting sugar", "Post-meal sugar"]]
        for r in v[-6:]:
            b, _ = hr.bmi(r.get("weight_kg"), r.get("height_cm"))
            bp = f"{r['systolic']}/{r['diastolic']}" if r.get("systolic") and r.get("diastolic") else "n/a"
            rows.append([r["entry_date"], f"{r['weight_kg']:g} kg" if r.get("weight_kg") else "n/a", b or "n/a", bp,
                         f"{r['fasting_sugar']:g}" if r.get("fasting_sugar") else "n/a",
                         f"{r['postmeal_sugar']:g}" if r.get("postmeal_sugar") else "n/a"])
        story.append(_table(rows))

    async def s_labs():
        alerts = labs.latest_abnormal(labs.build_lab_series(await db.reports.find({"profile_id": pid}).to_list(500)))
        if not alerts:
            return story.append(P("No out-of-range lab values on file."))
        rows = [["Test", "Latest", "Reference", "Direction", "Trend", "Date"]]
        for a in alerts:
            rows.append([C(a["label"]), C(f"{a['value']:g} {a.get('unit') or ''}"),
                         C(f"{a['low']} - {a['high']}" if a['low'] is not None and a['high'] is not None else (f"< {a['high']}" if a['high'] is not None else (f"> {a['low']}" if a['low'] is not None else "n/a"))),
                         C(a["direction"]), C(a.get("trend") or "n/a"), C(a["date"])])
        story.append(_table(rows))

    async def s_meds():
        meds = await db.medicines.find({"profile_id": pid, "active": True}).to_list(200)
        if not meds:
            return story.append(P("No active medicines."))
        story.append(_table([["Medicine", "Dose", "Frequency", "Since"]] +
                            [[C(m["name"]), C(m.get("dose", "")), C(m.get("frequency", "")), C(m.get("start_date", ""))] for m in meds]))
        taken, expected = await hr.adherence(pid)
        if expected:
            story.append(P(f"7-day adherence: {taken}/{expected} doses logged ({round(100 * taken / expected)}%).", small))

    async def s_insights():
        ins = sorted(await db.insights.find({"profile_id": pid}).to_list(50), key=lambda i: -i["confidence"])[:6]
        if not ins:
            return story.append(P("No insights generated."))
        story.append(_table([["Theme", "Observation (discussion point)", "Confidence"]] +
                            [[C(i["theme"].replace("_", " ")), C(i["text"]), C(f"{i['confidence_label']} ({round(i['confidence'] * 100)}%)")] for i in ins],
                            [32 * mm, 108 * mm, 30 * mm]))

    async def s_flags():
        flags = await hr.compute_risk_flags(pid)
        if not flags:
            return story.append(P("Nothing flagged."))
        story.append(_table([["Priority", "Topic", "Detail"]] + [[C(f["level"]), C(f["title"]), C(f["detail"])] for f in flags],
                            [22 * mm, 55 * mm, 93 * mm]))

    async def s_guard():
        gaps = await hr.symptom_gaps(pid)
        ops = await db.opinions.find({"profile_id": pid}).to_list(100)
        story.append(P("Recurring symptoms with no recorded resolution: " + ("; ".join(f"{g['symptom']} ({g['occurrences']}x)" for g in gaps) or "none")))
        if ops:
            story.append(Spacer(1, 4))
            story.append(_table([["Specialist", "Department", "Opinion"]] +
                                [[C(o.get("specialist_name") or "n/a"), C(o.get("department") or "n/a"), C(o["opinion_text"])] for o in ops],
                                [35 * mm, 32 * mm, 103 * mm]))

    async def s_appts():
        up = [a for a in await db.appointments.find({"profile_id": pid}).to_list(500)
              if a.get("status") == "scheduled" and a["appt_date"] >= date.today().isoformat()]
        if not up:
            return story.append(P("No upcoming appointments."))
        story.append(_table([["Date", "Time", "Doctor", "Hospital"]] +
                            [[C(a["appt_date"]), C(a.get("appt_time", "")), C(a["doctor_name"]), C(a.get("hospital", ""))] for a in sorted(up, key=lambda x: x["appt_date"])]))

    async def s_goals():
        gs = await db.goals.find({"profile_id": pid}).to_list(100)
        if not gs:
            return story.append(P("No goals set."))
        story.append(_table([["Goal", "Target", "Progress"]] + [[C(g["title"]), C(f"{g['target']} {g.get('unit', '')}"), C(f"{g.get('current', 0)} / {g['target']}")] for g in gs]))

    for key, title, fn in [("survey", "Survey summary", s_survey), ("story", "Recent story entries", s_story),
                           ("tracker", "30-day tracker averages", s_tracker), ("vitals", "Vitals", s_vitals),
                           ("labs", "Lab values outside reference range", s_labs), ("medicines", "Current medicines", s_meds),
                           ("insights", "AI insights (discussion points)", s_insights), ("flags", "Risk flags worth discussing", s_flags),
                           ("guard", "Diagnostic Guard", s_guard), ("appointments", "Upcoming appointments", s_appts),
                           ("goals", "Health goals", s_goals)]:
        await section(key, title, fn)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="EchoCare Consultation Summary", author="EchoCare")

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont(bf, 7.5)
        canvas.setFillColor(SLATE)
        canvas.drawString(18 * mm, 9 * mm, "EchoCare · patient-reported information, not a diagnosis")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
