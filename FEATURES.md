# Version-wise feature status

Legend: ✅ built & tested/verified · 🔑 built, needs a key/config to be live · ⚠️ built with a stated limit

## V1 — Core companion
✅ Accounts (JWT, bcrypt, admin role) · multi-profile family · health story journal · survey/symptom intake · daily tracker (mood, sleep, water, stress, energy, pain) · vitals (BMI, BP, sugar) with charts · medicines & adherence · appointments · lab values with ranges · timeline · dashboard · emergency card + public emergency page · department suggestion (TF-IDF + LogReg over the 10 specialties) · doctor directory & map (⚠️ demo data) · learn hub · consult summary PDF · light/dark theme · admin console & audit log.

## V2 — AI layer
✅ ChromaDB RAG with sufficiency gate + confidence · agent policy (safety → follow-up → RAG → Tavily → Gemini) · emergency/safety guard · evidence indexing/re-index · explainable insights with confidence · analytics.
🔑 Gemini insights, report extraction (vision), chat answers, photo guard analysis; Tavily web search — require keys **and** user consent; otherwise honest "not configured". Photo guard still returns quality checks and follow-up questions without AI.

## V3-A — Experience & intelligence
✅ Wellness, Echo companion chat, goals, notifications, consult export, tamil/hindi UI (⚠️ runtime layer; user content untranslated; server PDF English only), accessibility (skip link, landmarks, focus states, aria).

## V3-B — Trust, safety, privacy
✅ KYC levels (⚠️ OTP e-mail needs SMTP; dev mode echoes OTP) · report vault with SHA-256, versions, history, integrity check · verification engine (name/date/consistency/issuer/file-edit signals) · reviewer desk — **Verified only by a human reviewer**; automatic max = Partially Verified · trusted-issuer registry · Verified Report (PDF + QR, provenance labels; ⚠️ English PDF) · public verify page (no PHI) · configurable health alerts · privacy centre (consents, retention, export, delete-all, audit) · caregiver sharing (viewer/editor, scopes) · expiring, passcode, view-limited share links.

## Not claimed
No diagnosis, no proof that a hospital issued a document by AI alone, no real directory data, no mobile apps/ wearable sync.
