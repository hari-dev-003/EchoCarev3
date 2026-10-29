# EchoCare — control.md (run & deploy guide)

Stack: **React 18 + Vite** (frontend) · **FastAPI** (backend) · **MongoDB Atlas** (database) · **ChromaDB** (RAG vector store) · external AI only **Google Gemini** + **Tavily** (both optional, consent-gated).

> **Security first.** If you ever pasted your Atlas password or `SECRET_KEY` into a chat or a file, **rotate them now** (Atlas → Database Access → Edit user → new password; generate a new SECRET_KEY). This ZIP ships `.env.example` only — no secrets.

## 1. Run locally (VS Code)

Requirements: Python 3.11+ (3.13 tested), Node 18+ (20 recommended). Optional: Tesseract OCR (for scanned reports).

```bash
# Terminal 1 — backend
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env   then edit .env
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev                          # http://localhost:3000  (Vite proxies /api -> :8000)
```

With **no** `MONGODB_URI`, the backend uses an in-memory mock DB (data is lost on restart) — fine for a first look. The first registered user becomes **admin**. Use *Settings → Load demo data* for sample content.
API docs: http://localhost:8000/docs · Health: http://localhost:8000/api/health

Single-service mode: `cd frontend && npm run build` — FastAPI then serves `frontend/dist` itself at http://localhost:8000.

Tests: `pip install -r requirements-dev.txt && cd backend && python -m pytest -q` (47 tests).
VS Code: `.vscode/` has an interpreter setting, a debug launch config and a "Run all" task.

## 2. MongoDB Atlas

1. Create a free M0 cluster → *Database Access*: create a user (strong password).
2. *Network Access → Add IP Address*: add your current IP (local) or `0.0.0.0/0` for a hosted backend with changing IPs (then rely on a strong password).
3. *Connect → Drivers*: copy the `mongodb+srv://…` string into `backend/.env` as `MONGODB_URI` (URL-encode special characters in the password) and set `DB_BACKEND=atlas` (or `auto`).
4. Restart; `/api/health` should show the Atlas database. Indexes are created at startup.

## 3. Environment variables (`backend/.env`)

| Variable | Purpose |
|---|---|
| `ENV` | `development` or `production` (production disables dev-mode OTP echo) |
| `DB_BACKEND`, `MONGODB_URI`, `MONGODB_DB_NAME` | database |
| `SECRET_KEY` | JWT signing — long random, unique per deployment |
| `ADMIN_EMAILS` | extra admins (first user is admin anyway) |
| `FRONTEND_URL`, `EXTRA_CORS_ORIGINS` | allowed browser origins |
| `GOOGLE_API_KEY` | Gemini — enables AI only for users who consent in Privacy |
| `TAVILY_API_KEY` | web search — only for users who consent |
| `CHROMA_DIR` | ChromaDB persistence path |
| `SMTP_*`, `OTP_MINUTES` | real OTP e-mails |

Frontend: `VITE_API_URL` (blank locally; backend URL when the frontend is hosted separately).

## 4. ChromaDB persistence

Chroma stores vectors in `CHROMA_DIR`. MongoDB is the source of truth: if the folder is lost, evidence is re-indexed automatically (Admin → *Rebuild index from MongoDB*). On hosts with ephemeral disks (Render free) either attach a persistent disk and point `CHROMA_DIR` at it, or accept a re-index after each restart.

## 5. Deploy

**Option A — one service (simplest):** build the frontend (`npm run build`), deploy the backend on Render/Railway; FastAPI serves the UI.
**Option B — split (recommended):**
- *Backend on Render/Railway:* root `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set env vars from section 3 (`ENV=production`, `FRONTEND_URL=https://<your-site>`). Add a persistent disk for `CHROMA_DIR`.
- *Frontend on Vercel/Netlify:* root `frontend`, build `npm run build`, output `dist`, env `VITE_API_URL=https://<backend-url>`. Add an SPA rewrite: `/* → /index.html` (Netlify `_redirects`: `/* /index.html 200`; Vercel `vercel.json` rewrites).
- Add the frontend URL to `EXTRA_CORS_ORIGINS`.

**Docker (optional):** from the project root `docker build -f backend/Dockerfile -t echocare .` then `docker run -p 8000:8000 --env-file backend/.env -v echocare_data:/data echocare` (Dockerfile includes Tesseract).

**Single-VM Docker Compose deployment:** the repository includes `docker-compose.yml`, which runs Nginx/React on port 80 and FastAPI on a private container network. MongoDB remains MongoDB Atlas, while ChromaDB is stored in the named `echocare_chroma` volume.

```bash
# On the VM, from the repository root
cp backend/.env.example backend/.env
# Edit backend/.env:
# ENV=production
# DB_BACKEND=atlas
# MONGODB_URI=<MongoDB Atlas connection string>
# SECRET_KEY=<unique long random value>
# FRONTEND_URL=http://<vm-public-ip-or-domain>
# CHROMA_DIR=/data/chroma

docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

Open `http://<vm-public-ip-or-domain>/`. The frontend proxies `/api/*` to FastAPI, so no public backend port or `VITE_API_URL` is needed. Allow inbound TCP port 80 in the VM firewall/security group. The Compose volume persists ChromaDB data across container recreation; MongoDB Atlas persists application records.

For HTTPS, put a TLS reverse proxy such as Caddy or Traefik in front of this stack, then set `FRONTEND_URL` to the final `https://` origin and recreate the backend container. Never commit `backend/.env`; rotate any credential that has been exposed.

## 6. What needs real configuration (honest limits)

- **OTP e-mail:** without SMTP, development mode returns the OTP in the API response (never in production). Configure `SMTP_*` for real delivery.
- **"Verified" needs a human.** Automatic checks cap at *Partially Verified*; an admin/reviewer must confirm for *Verified*. OTP proves contact access only; AI extraction cannot prove a hospital issued a document.
- **AI features** (insights, report extraction, photo guard, chat answers) need `GOOGLE_API_KEY` **and** user consent; otherwise the app says "not configured" — it never fabricates AI output. Rule-based and RAG-retrieval features work without a key (local embeddings).
- **Server PDFs are English only** (reportlab cannot shape Tamil/Hindi). Tamil/Hindi reports use the printable page → browser "Save as PDF".
- **Tamil/Hindi UI** is a runtime translation layer; user-entered content and demo doctor names stay as typed.
- **Doctor directory** is a demo set; import a real one in Admin.
- EchoCare is a companion, **not a diagnostic tool**; emergency/safety checks run before anything is stored.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `ServerSelectionTimeoutError` / Atlas won't connect | IP not allow-listed; wrong password/URL-encoding; use `DB_BACKEND=mock` to confirm the app itself works |
| CORS error in browser | add the frontend origin to `FRONTEND_URL`/`EXTRA_CORS_ORIGINS` |
| 401 after restart | `SECRET_KEY` changed — log in again |
| `bcrypt` / passlib error | keep `bcrypt==4.0.1` |
| Scanned PDFs give no text | install Tesseract (`apt install tesseract-ocr` / Windows installer) |
| Chroma empty after redeploy | persistent disk missing — run Admin → Rebuild index |
| Port in use | `--port 8001` and set `VITE_API_PROXY=http://127.0.0.1:8001` |
| Blank page when hosted | missing SPA rewrite or wrong `VITE_API_URL` |
| `npm run build` type errors | Node ≥18, run `npm install` again |

## 8. Project map

`backend/app/routers`: auth, profiles, records, ai, dashboard, directory, admin, **trust** (KYC, vault, reviewer, issuers, public verify), **safety_net** (alerts, privacy, sharing), **verified** (Verified Report). `services/`: llm, rag/vector store, verification, vault, alerts, verified_report, mailer. `frontend/src/pages`: 34 pages (see `FEATURES.md`).
