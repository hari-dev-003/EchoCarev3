"""District-wise doctor directory: DEMO data out of the box (clearly labelled), real data via CSV/Excel import."""
import math
import random
import urllib.parse

from app.core.db import get_db
from app.data.specialties import ALL_SPECIALTIES

DISTRICTS = {
    "Chennai": (13.0827, 80.2707), "Coimbatore": (11.0168, 76.9558), "Madurai": (9.9252, 78.1198),
    "Tiruchirappalli": (10.7905, 78.7047), "Salem": (11.6643, 78.1460), "Tirunelveli": (8.7139, 77.7567),
    "Erode": (11.3410, 77.7172), "Vellore": (12.9165, 79.1325), "Thanjavur": (10.7870, 79.1378),
    "Tiruppur": (11.1085, 77.3411),
}
HOSPITAL_SUFFIXES = ["General Hospital", "Multispeciality Clinic", "Medical Centre", "Care Hospital", "Health Institute"]
FIRST = ["Anitha", "Karthik", "Priya", "Suresh", "Meena", "Ramesh", "Divya", "Arun", "Lakshmi", "Vikram"]
LAST = ["Krishnan", "Raman", "Subramaniam", "Iyer", "Pillai", "Nair", "Reddy", "Chandran", "Murthy", "Rao"]


def _jitter(rng, lat, lon, km=6):
    r = km / 111.0
    a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0, r)
    return lat + d * math.cos(a), lon + d * math.sin(a)


def _generate() -> list[dict]:
    rng = random.Random(7)
    out, i = [], 1
    for district, (lat, lon) in DISTRICTS.items():
        for sp in ALL_SPECIALTIES:
            for _ in range(rng.choice([1, 1, 2])):
                la, lo = _jitter(rng, lat, lon)
                out.append({"id": f"demo-{i}", "name": f"Dr. {rng.choice(FIRST)} {rng.choice(LAST)}", "specialty": sp,
                            "district": district, "hospital": f"{district} {rng.choice(HOSPITAL_SUFFIXES)}",
                            "lat": round(la, 5), "lon": round(lo, 5), "rating": round(rng.uniform(3.6, 4.9), 1),
                            "years_experience": rng.randint(3, 28), "consultation_fee_inr": rng.choice([300, 400, 500, 600, 800, 1000]),
                            "phone": f"+91 {rng.randint(70000, 99999)}{rng.randint(10000, 99999)}", "is_demo_data": True})
                i += 1
    return out


DEMO_DOCTORS = _generate()


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


async def get_directory() -> tuple[list[dict], str]:
    docs = await get_db().doctors.find({}).to_list(50000)
    if docs:
        out = []
        for d in docs:
            d = dict(d)
            d["id"] = d.pop("_id")
            out.append(d)
        return out, "imported"
    return DEMO_DOCTORS, "demo"


def navigate_url(lat, lon) -> str:
    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"


def maps_search_url(q: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(q)


def rank_doctors(doctors, user_lat=None, user_lon=None) -> list[dict]:
    ranked = []
    for d in doctors:
        rs, es = d["rating"] / 5, min(d["years_experience"] / 25, 1.0)
        if user_lat is not None and user_lon is not None:
            dist = haversine_km(user_lat, user_lon, d["lat"], d["lon"])
            score = 0.35 * rs + 0.25 * es + 0.4 * max(0, 1 - dist / 50)
        else:
            dist, score = None, 0.55 * rs + 0.45 * es
        ranked.append({**d, "distance_km": round(dist, 1) if dist is not None else None, "score": round(score, 3),
                       "navigate_url": navigate_url(d["lat"], d["lon"])})
    return sorted(ranked, key=lambda x: -x["score"])


REQUIRED = ["name", "specialty", "district", "hospital"]
ALIASES = {
    "psychiatry": "Psychiatry / Mental Health", "mental health": "Psychiatry / Mental Health",
    "psychiatrist": "Psychiatry / Mental Health", "gynaecology": "Gynecology", "gynecologist": "Gynecology",
    "orthopaedics": "Orthopedics", "orthopedic": "Orthopedics", "orthopaedic": "Orthopedics",
    "general physician": "General Medicine", "physician": "General Medicine", "general": "General Medicine",
    "gastro": "Gastroenterology", "ent specialist": "ENT", "cardiologist": "Cardiology",
    "neurologist": "Neurology", "dermatologist": "Dermatology", "pulmonologist": "Pulmonology"}


def normalize_specialty(raw) -> tuple[str, bool]:
    s = str(raw).strip()
    for c in ALL_SPECIALTIES:
        if s.lower() == c.lower():
            return c, True
    if s.lower() in ALIASES:
        return ALIASES[s.lower()], True
    return s.title(), False


def template_csv() -> str:
    return (",".join(REQUIRED + ["lat", "lon", "rating", "years_experience", "consultation_fee_inr", "phone"]) + "\n"
            "Dr. A. Kumar,Cardiology,Chennai,Example Heart Hospital,13.0827,80.2707,4.6,18,700,+91 9000000001\n"
            "Dr. S. Devi,Dermatology,Coimbatore,Example Skin Clinic,,,4.3,9,500,+91 9000000002\n")


def parse_upload(df) -> tuple[list[dict], list[str], list[str]]:
    df = df.rename(columns={c: str(c).strip().lower() for c in df.columns})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return [], [f"Missing required column(s): {', '.join(missing)}"], []
    centers = {k.lower(): v for k, v in DISTRICTS.items()}
    rng = random.Random(11)
    rows, errors, warnings = [], [], []

    def num(v, cast, default):
        try:
            return cast(float(v)) if str(v).strip() not in ("", "nan", "None") else default
        except (ValueError, TypeError):
            return default

    for i, r in df.iterrows():
        line = i + 2
        name, district, hospital = (str(r.get(c, "")).strip() for c in ("name", "district", "hospital"))
        if not name or name == "nan" or not district or district == "nan":
            errors.append(f"Row {line}: name and district are required, row skipped.")
            continue
        sp, known = normalize_specialty(r.get("specialty", ""))
        if not known:
            warnings.append(f"Row {line}: unrecognised specialty '{sp}' imported as-is.")
        lat, lon = num(r.get("lat"), float, None), num(r.get("lon"), float, None)
        if lat is None or lon is None:
            c = centers.get(district.lower())
            if not c:
                errors.append(f"Row {line}: no lat/lon and district '{district}' is not a known district, row skipped.")
                continue
            lat, lon = _jitter(rng, *c)
            warnings.append(f"Row {line}: no coordinates, placed near the {district} centre.")
        phone = str(r.get("phone", ""))
        rows.append({"name": name, "specialty": sp, "district": district.title(), "hospital": "" if hospital == "nan" else hospital,
                     "lat": round(lat, 5), "lon": round(lon, 5), "rating": min(max(num(r.get("rating"), float, 4.0), 0.0), 5.0),
                     "years_experience": num(r.get("years_experience"), int, 0), "consultation_fee_inr": num(r.get("consultation_fee_inr"), int, 0),
                     "phone": "" if phone in ("nan", "None") else phone.strip(), "is_demo_data": False})
    return rows, errors, warnings
