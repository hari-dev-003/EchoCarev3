# EchoCare — AI Healthcare Companion

> A personal health record and decision-support companion for individuals and families. EchoCare organises what a person tells it (symptoms, vitals, medicines, lab reports), explains it in plain language with cited evidence, flags what is worth discussing with a clinician, and helps others trust the documents the person shares — **without ever diagnosing**.

**Stack:** React 18 + Vite + TypeScript · FastAPI · MongoDB Atlas · ChromaDB (RAG) · Google Gemini and Tavily (optional, consent-gated)
**Themes:** light and dark · **Languages:** English, தமிழ், हिन्दी · **Version:** 5.0.0 (covers feature-doc versions V1–V3)

> EchoCare supports, and does not replace, a licensed clinician. It does not diagnose, prescribe or predict disease. Sample data in this repository is fictional.

---

## 1. The problem

People keep their health information scattered: paper lab reports, WhatsApp photos, half-remembered symptoms, several family members' records. At the clinic they cannot tell the doctor a clear story. Doctors and employers who receive a shared report cannot easily tell whether it is genuine. AI tools that "answer health questions" often sound confident without evidence.

## 2. What EchoCare does

1. **Collects** health information in one place per person (self or family member).
2. **Understands** it: tags symptoms, builds a timeline, reads uploaded lab reports, tracks trends.
3. **Explains** it with *retrieval-augmented generation (RAG)*: answers are grounded in the person's own indexed records, with a sufficiency gate and a confidence score. If evidence is too thin, EchoCare says so instead of guessing.
4. **Protects** the person: emergency wording is detected *before* anything is stored or sent to an AI; consent is required before any external AI call.
5. **Builds trust** in shared documents: reports are hashed and versioned, checked by a verification engine, and confirmed only by a human reviewer.
6. **Shares safely**: caregivers and expiring links, with scoped and revocable access.

## 3. Architecture

```
React SPA (Vite)  ──HTTPS/JSON──▶  FastAPI  ──▶  MongoDB Atlas   (source of truth: users, records, files, audit)
 • light/dark theme                 • JWT auth     ChromaDB       (vector index of evidence, rebuilt from Mongo)
 • runtime ta/hi translation        • consent      Gemini         (optional: reasoning, vision, embeddings)
 • Recharts, Leaflet                  gating       Tavily         (optional: web search)
```

- **MongoDB Atlas** holds all records. For development, `DB_BACKEND=mock` (or no URI) uses an in-memory mock so the app runs with zero setup.
- **ChromaDB** stores 384-dimension evidence embeddings. Gemini embeddings are used only if the user consented to AI; otherwise a local hashing vectorizer is used. The index can always be rebuilt from MongoDB.
- **Consent gating:** `ai_processing` and `web_search` are **off by default**. The backend sets per-request flags from the user's privacy settings, so Gemini/Tavily are never called without consent.
- **Profiles:** every record belongs to a profile (self or family member). Access is checked per request (`X-Profile-Id`) for owners and for caregivers with a viewer/editor role and scopes.

### The Echo agent policy
`safety check → follow-up questions (if the input is vague) → RAG over the person's evidence → Tavily web search (if allowed and needed) → Gemini (if allowed)`. Every answer carries sources and a confidence value; with no key or consent it honestly reports "not configured" and still returns retrieved evidence.

### Department suggestion
A TF-IDF + logistic-regression classifier maps symptoms to one of 10 specialties (General Medicine, Neurology, Cardiology, Gastroenterology, Dermatology, ENT, Gynecology, Orthopedics, Pulmonology, Psychiatry). It is trained from the project's canonical keyword map, so its reported accuracy (`backend/ml/metrics.md`) reflects that synthetic keyword data, **not** real clinical performance.

## 4. Feature tour

### Record (V1)
| Module | What it does |
|---|---|
| **My Story** | Free-text health journal with mood; symptoms and timeline phrases are extracted; indexed for RAG. Emergency text is blocked from storage. |
| **Health Survey** | Structured intake: age, occupation, activity, main concern, duration, conditions, allergies, family history. |
| **Daily Tracker** | Sleep, water, stress, energy, pain, mood, steps, notes, with charts and averages. |
| **Vitals** | Weight/height (BMI), BP, heart rate, fasting/post-meal sugar, SpO₂, temperature, shown against usual target ranges. |
| **Medical Reports** | Upload PDF/image (OCR + Gemini vision when allowed) or enter values manually; out-of-range flags. |
| **Lab Trends** | Per-test history, latest reading, out-of-range count. |
| **Medicines** | Schedule by time slot, daily dose ticks, weekly adherence. |
| **Appointments** | Upcoming and past visits. |
| **Emergency Card** | Blood group, allergies, conditions, medicines, contact; optional public QR page showing only these fields. |
| **Family Profiles** | Separate records per family member. |
| **Doctors** | Directory with district, specialty, rating, experience, map (demo data; admin can import a real list). |
| **Consultation Report** | Doctor-friendly PDF of the person's own data with chosen sections. |
| **Learn** | Plain-language health explainers. |
| **Dashboard, Analytics, Timeline, Search** | Overviews and charts built from the above. |

### AI and safety (V2)
- **AI Insights:** explainable observations with confidence and "discuss with your clinician" framing.
- **Echo Companion:** chat grounded in the person's evidence; shows sources.
- **Diagnostic Guard:** safety-first symptom/photo helper. Photos get a quality check and follow-up questions; if AI is allowed it adds cautious *visible-feature* observations and broad possible categories — never a disease name or a prediction.
- **Second-opinion compare:** side-by-side diff of two opinions with conflict signals.
- **Goals, Wellness, notifications, Analytics.**

### Trust, safety and privacy (V3)
- **KYC levels:** e-mail OTP proves *access to the contact*, nothing more. Identity details plus an uploaded ID go to a human reviewer.
- **Report Vault:** every file is stored with a SHA-256 hash, versions and a history; an integrity check detects changes.
- **Verification engine:** checks name match, date sanity, internal consistency, trusted-issuer registry, and file signals (editing tools, modified-after-created). Automatic result is capped at **Partially Verified**; **Verified requires a human reviewer** (who cannot review their own report).
- **Verified Report:** a shareable summary (PDF + QR) that separates what is *verified identity*, *verified document*, *patient-entered*, *extracted*, *AI-generated* and *reviewed*. The public QR page exposes **no health data**.
- **Alerts:** configurable thresholds (BP, sugar, SpO₂, heart rate, temperature, sleep, stress, pain, adherence) with urgent/soon/routine levels.
- **Privacy centre:** consents, retention period, data export, delete-all, and an audit trail.
- **Caregiver sharing and share links:** viewer/editor roles with scopes (records, reports, vitals, medicines, insights); links with expiry, optional passcode, view limits and revoke.
- **Accessibility:** skip link, landmarks, focus states, ARIA labels. **Languages:** Tamil/Hindi UI through a runtime translation layer.

## 5. Project structure
```
backend/
  app/
    main.py            app factory, routers, static frontend
    core/              config, db (Atlas/mock), security (JWT, bcrypt), deps (auth, profile access, consent)
    routers/           auth, profiles, records, ai, dashboard, directory, admin, trust, safety_net, verified
    services/          rag, vector (Chroma), agent, llm (Gemini/Tavily), safety, department, labs, docreader (OCR),
                       verification, vault, verified_report, alerts, report_pdf, mailer, doctors, compare, i18n, demo
    data/              canonical SPECIALTIES, learn content
  ml/                  classifier training script, model, metrics
  tests/               47 automated tests (pytest)
  requirements.txt  requirements-dev.txt  .env.example  Dockerfile
frontend/
  src/pages/           34 pages     src/components/  layout, charts, UI kit
  src/lib/             api, store, i18n, translate (ta/hi)    src/locales/  ta.json, hi.json
control.md   FEATURES.md   .vscode/
```

## 6. Quick start
```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
python -m uvicorn app.main:app --reload --port 8000
# frontend (second terminal)
cd frontend && npm install && npm run dev       # http://localhost:3000
```
Register the first account (it becomes admin), then **Settings → Load demo data**. API docs: `http://localhost:8000/docs`. Full run, Atlas and deployment steps: **[control.md](control.md)**.

## 7. Configuration
Copy `backend/.env.example` to `backend/.env`. Key settings: `MONGODB_URI`, `DB_BACKEND`, `SECRET_KEY`, `GOOGLE_API_KEY`, `TAVILY_API_KEY`, `CHROMA_DIR`, `FRONTEND_URL`, optional `SMTP_*`. **Never commit `.env`.** Use a unique `SECRET_KEY` per deployment and rotate any credential that was ever shared in plain text.

## 8. Testing
```bash
pip install -r backend/requirements-dev.txt
cd backend && python -m pytest -q          # 47 tests: auth, records, RAG, safety, verification, sharing, privacy, alerts
```
Sample fictional reports, a sample ID image and step-by-step test data for every module are provided separately in the test-data pack (`TEST_ALL_MODULES.md`).

## 9. Security and privacy design
- Passwords hashed with bcrypt; JWT sessions; role checks on admin and reviewer actions.
- No external AI or web call without explicit per-user consent; emergency/safety screening runs before storage or any model call.
- Profile-scoped queries everywhere; caregiver access enforced server-side by role and scope, and audited.
- Public pages (emergency card, verify page, share links) reveal the minimum: the verify page shows only report id, status, date and hash.
- Share links: expiry, optional passcode, view limit, revocation.

## 10. Honest limitations
- **Not a medical device.** No diagnosis, treatment advice or risk prediction.
- **"Verified" needs a human.** OTP proves contact access only; AI extraction cannot prove a hospital issued a document.
- **OTP e-mail** needs SMTP; in development the code is returned in the API response (never in production).
- **AI features** need keys *and* consent; otherwise the app says "not configured".
- **Server PDFs are English only**; Tamil/Hindi reports use the printable page ("Save as PDF").
- **Translations** are applied at runtime; user-entered text and demo doctor names stay as typed.
- **Doctor directory** is demo data. **Classifier metrics** come from synthetic keyword data.
- Uploaded files are stored in MongoDB (size limit `MAX_UPLOAD_MB`); not intended for very large archives.

## 11. Roadmap ideas
Real doctor-directory import, SMS OTP, DigiLocker/issuer-API verification, wearable sync, server-side Tamil/Hindi PDF fonts, mobile app, clinician portal, background retention jobs, automated end-to-end browser tests.

## 12. Documentation map
`control.md` run/deploy/troubleshoot · `FEATURES.md` version-wise status · `backend/.env.example` configuration · `/docs` live API reference.