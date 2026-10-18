"""Report verification engine.

Honest by design: automated checks can only gather *evidence*. They can never prove that a hospital or doctor issued a
document, so the best automatic outcome is 'Partially Verified'. 'Verified' is set only when a human reviewer confirms.
"""
import io
import re
from datetime import date, datetime
from difflib import SequenceMatcher

from app.services import labs

STATUSES = ("Unverified", "Manual Review", "Partially Verified", "Verified", "Failed")
EDIT_TOOLS = ("photoshop", "gimp", "canva", "paint", "pixlr", "snapseed", "picsart")


def _norm(s: str) -> str:
    s = re.sub(r"\b(mr|mrs|ms|miss|dr|shri|smt|master|baby)\b\.?", " ", (s or "").lower())
    return " ".join(re.sub(r"[^a-z\u0b80-\u0bff\u0900-\u097f ]", " ", s).split())


def name_similarity(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if set(a.split()) <= set(b.split()) or set(b.split()) <= set(a.split()):
        return 0.92
    return round(SequenceMatcher(None, " ".join(sorted(a.split())), " ".join(sorted(b.split()))).ratio(), 2)


def extract_identity_hints(text: str) -> dict:
    """Regex fallback (no AI): patient name, issuer and registration number from plain text."""
    out: dict = {}
    m = re.search(r"(?:patient\s*name|name\s*of\s*patient|patient|name)\s*[:\-]\s*([A-Za-z.஀-௿ ]{3,60})", text or "", re.I)
    if m:
        out["patient_name"] = re.split(r"\s{2,}|\b(?:age|sex|gender|dob|date|ref)\b", m.group(1), flags=re.I)[0].strip(" .")
    m = re.search(r"([A-Z][A-Za-z&.' ]{2,50}(?:Laborator(?:y|ies)|Diagnostics?|Hospital|Clinic|Medical Centre|Path Lab))", text or "")
    if m:
        out["issuer_name"] = m.group(1).strip()
    m = re.search(r"(?:reg(?:istration)?\.?\s*(?:no|number)|lab\s*id|nabl)\s*[:#\-]?\s*([A-Z0-9\-/]{4,20})", text or "", re.I)
    if m:
        out["registration_no"] = m.group(1)
    return out


def file_signals(data: bytes | None, filename: str) -> dict:
    """Metadata signals from the stored file (independent of what the document claims)."""
    sig = {"readable": False, "editing_tool": None, "pages": None, "pdf_modified_after_creation": False, "encrypted": False}
    if not data:
        return sig
    ext = filename.lower().rsplit(".", 1)[-1]
    try:
        if ext == "pdf":
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz
            with fitz.open(stream=data, filetype="pdf") as doc:
                sig["readable"] = True
                sig["pages"] = len(doc)
                sig["encrypted"] = bool(doc.is_encrypted)
                md = doc.metadata or {}
                blob = f"{md.get('creator', '')} {md.get('producer', '')}".lower()
                sig["editing_tool"] = next((t for t in EDIT_TOOLS if t in blob), None)
                c, m = md.get("creationDate") or "", md.get("modDate") or ""
                sig["pdf_modified_after_creation"] = bool(c and m and m[2:10] > c[2:10])
        else:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                sig["readable"] = True
                try:
                    sw = str((im.getexif() or {}).get(305, "")).lower()
                except Exception:
                    sw = ""
                sig["editing_tool"] = next((t for t in EDIT_TOOLS if t in sw), None)
    except Exception:
        sig["readable"] = False
    return sig


def _chk(key, label, state, detail, weight=1):
    return {"key": key, "label": label, "state": state, "detail": detail, "weight": weight}  # state: pass|warn|fail|na


def run_checks(report: dict, profile: dict, user_kyc: dict, issuers: list[dict], data: bytes | None) -> dict:
    ex = report.get("extracted") or {}
    checks = []
    manual = report.get("method") == "manual"

    # 1. Patient name vs profile
    pn = ex.get("patient_name")
    if manual:
        checks.append(_chk("name", "Patient name matches profile", "na", "Entered manually by the patient, so there is no document to compare.", 0))
    elif not pn:
        checks.append(_chk("name", "Patient name matches profile", "warn", "No patient name could be read from the document.", 2))
    else:
        sim = name_similarity(pn, profile.get("name", ""))
        st = "pass" if sim >= 0.8 else "warn" if sim >= 0.5 else "fail"
        checks.append(_chk("name", "Patient name matches profile", st, f"Document says '{pn}', profile is '{profile.get('name')}' (similarity {sim:.0%}).", 3))

    # 2. Date sanity
    d = None
    try:
        d = datetime.strptime((report.get("report_date") or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        pass
    if d is None:
        checks.append(_chk("date", "Report date is plausible", "warn", "The report date is missing or not a valid date.", 1))
    elif d > date.today():
        checks.append(_chk("date", "Report date is plausible", "fail", f"The report date {d.isoformat()} is in the future.", 3))
    elif (date.today() - d).days > 365 * 30:
        checks.append(_chk("date", "Report date is plausible", "warn", "The report is more than 30 years old.", 1))
    else:
        checks.append(_chk("date", "Report date is plausible", "pass", f"{d.isoformat()} is a valid past date.", 1))

    # 3. Internal consistency of values
    fields = report.get("fields") or []
    if not fields:
        checks.append(_chk("values", "Values are internally consistent", "warn" if not manual else "na", "No test values were found.", 1 if not manual else 0))
    else:
        bad, seen = [], {}
        for f in fields:
            v = labs.to_float(f.get("value"))
            if v is None:
                bad.append(f"{f.get('test')}: non-numeric value")
                continue
            key = labs.normalize_test_name(f.get("test", ""))
            if key in seen and abs(seen[key] - v) > 1e-9:
                bad.append(f"{f.get('test')}: listed twice with different values")
            seen[key] = v
            ref = f.get("reference_range")
            if ref and labs.parse_ref_range(ref) and bool(f.get("out_of_range")) != labs.is_out_of_range(v, ref):
                bad.append(f"{f.get('test')}: flag disagrees with its reference range")
        checks.append(_chk("values", "Values are internally consistent", "pass" if not bad else "warn",
                           "All values are numeric, unique and agree with their reference ranges." if not bad else "; ".join(bad[:4]), 2))

    # 4. Issuer in the trusted registry (evidence only)
    iss = ex.get("issuer_name")
    match = None
    if iss:
        for t in issuers:
            names = [t["name"]] + list(t.get("aliases") or [])
            if any(name_similarity(iss, n) >= 0.85 or _norm(n) in _norm(iss) for n in names if _norm(n)):
                match = t
                break
    if manual:
        checks.append(_chk("issuer", "Issuer is in the trusted registry", "na", "No issuing organisation for a manual entry.", 0))
    elif match:
        checks.append(_chk("issuer", "Issuer is in the trusted registry", "pass", f"'{iss}' matches trusted issuer '{match['name']}'. A matching name is not proof the document is genuine.", 2))
    elif iss:
        checks.append(_chk("issuer", "Issuer is in the trusted registry", "warn", f"'{iss}' is not in the admin-managed trusted issuer list.", 2))
    else:
        checks.append(_chk("issuer", "Issuer is in the trusted registry", "warn", "No issuing organisation could be read.", 2))

    # 5. File signals
    if manual:
        checks.append(_chk("file", "File looks unaltered", "na", "No file attached.", 0))
    else:
        sig = file_signals(data, report.get("filename", ""))
        if not sig["readable"]:
            checks.append(_chk("file", "File looks unaltered", "fail", "The stored file could not be opened.", 3))
        elif sig["editing_tool"]:
            checks.append(_chk("file", "File looks unaltered", "warn", f"File metadata shows an image/PDF editor ({sig['editing_tool']}).", 2))
        elif sig["pdf_modified_after_creation"]:
            checks.append(_chk("file", "File looks unaltered", "warn", "The PDF was modified after it was created.", 1))
        else:
            checks.append(_chk("file", "File looks unaltered", "pass", "File opens normally and metadata shows no editing software.", 1))

    # 6. Account identity level (supporting evidence only)
    lvl = (user_kyc or {}).get("status", "unverified")
    checks.append(_chk("account", "Uploader's identity", "pass" if lvl == "identity_verified" else "warn",
                       {"identity_verified": "The uploader's identity was reviewed by an administrator.",
                        "contact_verified": "Only the uploader's e-mail was confirmed (an OTP proves contact access, not identity)."}.get(lvl, "The uploader has not verified their e-mail or identity."), 1))

    scored = [c for c in checks if c["weight"] > 0]
    got = sum(c["weight"] for c in scored if c["state"] == "pass")
    tot = sum(c["weight"] for c in scored) or 1
    score = round(got / tot, 2)
    fails = [c for c in checks if c["state"] == "fail"]
    warns = [c for c in checks if c["state"] == "warn"]
    if fails:
        status, why = "Failed", "A hard check failed: " + fails[0]["label"] + "."
    elif manual:
        status, why = "Manual Review", "Manual entries have no source document; a reviewer must decide."
    elif score >= 0.75 and not any(c["key"] in ("name", "file") for c in warns):
        status, why = "Partially Verified", "Automated checks agree, but only a reviewer can confirm the document is genuine."
    else:
        status, why = "Manual Review", "Some checks were inconclusive, so a human reviewer should look at this report."
    return {"status": status, "reason": why, "score": score, "checks": checks, "issuer_matched": match["name"] if match else None}
